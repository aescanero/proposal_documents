"""Loading Terramate configuration files, following ``import`` blocks.

Two facts drive this module.

*Contracts are imported, not local.* The ``input`` and ``output`` blocks of a
stack live in ``imports/contracts/``, pulled in by ``import { source = ... }``.
An enricher that only read the files sitting in the stack directory would find
no ``input`` blocks at all and report every stack as consuming nothing -- the
G1 gate would then pass every repository, which is the worst possible outcome
for a gate whose reason to exist is risk R2.

*Globals are inherited.* ``from_stack_id = global.platform.network_stack_id``
resolves against globals defined anywhere from the repository root down to the
stack directory, so the chain has to be walked in order.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import hcl
from .hcl import UNRESOLVED, Block, Body, Expr

TM_SUFFIXES = (".tm.hcl", ".tm")

# Terramate's own skip list, plus the usual noise.
SKIP_DIRS = {".git", ".terraform", ".terramate", ".terramate-cache", "node_modules"}


class LoadedFile:
    __slots__ = ("path", "body")

    def __init__(self, path: str, body: Body) -> None:
        self.path = path
        self.body = body


class Loader:
    """Parses and caches Terramate files under a repository root."""

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        self._cache: Dict[str, Optional[Body]] = {}
        self.errors: List[str] = []

    # -- file access ------------------------------------------------------

    def rel(self, path: str) -> str:
        return os.path.relpath(os.path.abspath(path), self.root)

    def parse(self, path: str) -> Optional[Body]:
        path = os.path.abspath(path)
        if path in self._cache:
            return self._cache[path]
        try:
            body: Optional[Body] = hcl.parse_file(path)
        except (hcl.HCLError, OSError, UnicodeDecodeError) as exc:
            self.errors.append("%s: %s" % (self.rel(path), exc))
            body = None
        self._cache[path] = body
        return body

    def config_files(self, directory: str) -> List[str]:
        """The Terramate files directly in ``directory``, in a stable order."""
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return []
        return [
            os.path.join(directory, name)
            for name in names
            if name.endswith(TM_SUFFIXES)
            and os.path.isfile(os.path.join(directory, name))
        ]

    # -- imports ----------------------------------------------------------

    def resolve_import(self, source: str, importing_file: str) -> List[str]:
        """Resolve an ``import.source`` to concrete paths.

        A leading ``/`` is relative to the *project root*, not the filesystem
        root. Globs are supported, as Terramate supports them.
        """
        if source.startswith("/"):
            base = os.path.join(self.root, source.lstrip("/"))
        else:
            base = os.path.join(os.path.dirname(importing_file), source)
        base = os.path.normpath(base)

        if any(ch in source for ch in "*?["):
            import glob as globmod

            return sorted(p for p in globmod.glob(base) if os.path.isfile(p))
        return [base] if os.path.isfile(base) else []

    def expand(self, path: str, _seen: Optional[set] = None) -> List[LoadedFile]:
        """``path`` and everything it imports, imports first (lower precedence)."""
        seen = _seen if _seen is not None else set()
        path = os.path.abspath(path)
        if path in seen:
            return []  # import cycles are Terramate's error to report, not ours
        seen.add(path)

        body = self.parse(path)
        if body is None:
            return []

        out: List[LoadedFile] = []
        for block in body.of_type("import"):
            source = hcl.evaluate(block.body.attributes.get("source"), {})
            if not isinstance(source, str):
                self.errors.append(
                    "%s:%d: import.source is not a literal string" % (self.rel(path), block.line)
                )
                continue
            targets = self.resolve_import(source, path)
            if not targets:
                self.errors.append(
                    "%s:%d: import source %r resolves to nothing" % (self.rel(path), block.line, source)
                )
            for target in targets:
                out.extend(self.expand(target, seen))
        out.append(LoadedFile(path, body))
        return out

    def stack_files(self, stack_dir: str) -> List[LoadedFile]:
        """Every file whose blocks belong to the stack in ``stack_dir``."""
        out: List[LoadedFile] = []
        seen: set = set()
        for path in self.config_files(stack_dir):
            out.extend(self.expand(path, seen))
        return out

    # -- globals ----------------------------------------------------------

    def dir_chain(self, stack_dir: str) -> List[str]:
        """Root-first list of directories from the project root to ``stack_dir``."""
        stack_dir = os.path.abspath(stack_dir)
        chain = [stack_dir]
        current = stack_dir
        while True:
            if os.path.normpath(current) == self.root:
                break
            parent = os.path.dirname(current)
            if parent == current or len(parent) < len(self.root):
                break
            chain.append(parent)
            current = parent
        chain.reverse()
        return chain

    def globals_for(self, stack_dir: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate ``global.*`` as seen from ``stack_dir``.

        Precedence approximates Terramate: the deeper the directory the stronger,
        and within a directory an imported file is weaker than the file that
        imported it. Unresolvable globals are simply absent, which is what makes
        an unresolved ``from_stack_id`` visible downstream instead of silently
        wrong.
        """
        entries: List[Tuple[Tuple[str, ...], Expr]] = []
        for directory in self.dir_chain(stack_dir):
            for path in self.config_files(directory):
                for loaded in self.expand(path, set()):
                    _collect_globals(loaded.body, entries)

        # Later entries win; keep one expression per key path.
        resolved_exprs: Dict[Tuple[str, ...], Expr] = {}
        for key, expr in entries:
            resolved_exprs[key] = expr

        scope: Dict[str, Any] = {"global": {}, "terramate": metadata or {}}
        pending = dict(resolved_exprs)
        # Globals may reference other globals; iterate to a fixed point.
        for _ in range(len(pending) + 2):
            if not pending:
                break
            progressed = False
            for key in list(pending):
                value = hcl.evaluate(pending[key], scope)
                if value is UNRESOLVED:
                    continue
                _assign(scope["global"], key, value)
                del pending[key]
                progressed = True
            if not progressed:
                break
        return scope


def _collect_globals(body: Body, entries: List[Tuple[Tuple[str, ...], Expr]]) -> None:
    for block in body.of_type("globals"):
        prefix = tuple(block.labels)
        _collect_globals_body(block.body, prefix, entries)


def _collect_globals_body(
    body: Body, prefix: Tuple[str, ...], entries: List[Tuple[Tuple[str, ...], Expr]]
) -> None:
    for name, expr in body.attributes.items():
        entries.append((prefix + (name,), expr))
    # A nested `map`/`globals` block form is not used in this repository; nested
    # object values are handled as object expressions by the evaluator instead.


def _assign(target: Dict[str, Any], key: Sequence[str], value: Any) -> None:
    node = target
    for part in key[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[key[-1]] = value


def find_blocks(files: Sequence[LoadedFile], *types: str) -> List[Tuple[str, Block]]:
    """All blocks of the given types, paired with the file they came from."""
    out: List[Tuple[str, Block]] = []
    for loaded in files:
        for block in loaded.body.of_type(*types):
            out.append((loaded.path, block))
    return out
