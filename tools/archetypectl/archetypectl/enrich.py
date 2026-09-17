"""``archetypectl enrich`` -- add ``consumes[]`` and ``after_ids[]`` to stacks.json.

``terramate list --json`` gives the inventory but not the sharing contract: it
does not expose ``input`` blocks, and ``stack.after`` is a list of *directory
paths or tag filters*, while the invariant to check is expressed in *stack IDs*.
This module closes both gaps so that the G1 policy is a comparison between two
lists of IDs and nothing more.

The extraction lives here rather than in Rego deliberately. HCL parsing, import
following and globals inheritance in Rego would be unreadable and untestable;
here they are ordinary code with fixtures. What the policy gets is flat JSON,
which is portable and can be tested against fixtures without a repository.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import hcl
from .hcl import UNRESOLVED, Block, Expr
from .loader import Loader

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------
# Inventory normalisation
# --------------------------------------------------------------------------

_DIR_KEYS = ("dir", "path", "directory")


def normalise_inventory(document: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return ``(stacks, envelope_extras)`` for the shapes terramate emits.

    Accepted: ``{"stacks": [...]}``, a bare array, and either with each entry
    wrapped as ``{"stack": {...}}``. The output envelope is always the object
    form, because the G1 policy reads ``input.stacks``.
    """
    extras: Dict[str, Any] = {}
    if isinstance(document, dict):
        if "stacks" in document and isinstance(document["stacks"], list):
            raw = document["stacks"]
            extras = {k: v for k, v in document.items() if k not in ("stacks", "enrich")}
        elif "stack" in document and isinstance(document["stack"], dict):
            raw = [document]
        else:
            raise ValueError("input JSON has no 'stacks' array")
    elif isinstance(document, list):
        raw = document
    else:
        raise ValueError("input JSON is neither an object nor an array")

    stacks: List[Dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("stack entry is not an object: %r" % (entry,))
        if set(entry) == {"stack"} and isinstance(entry["stack"], dict):
            entry = dict(entry["stack"])
        stacks.append(entry)
    return stacks, extras


def stack_dir_of(entry: Dict[str, Any]) -> Optional[str]:
    for key in _DIR_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            # Some versions nest {"path": {"absolute": "/x", "relative": "x"}}.
            for nested in ("absolute", "relative", "path"):
                candidate = value.get(nested)
                if isinstance(candidate, str) and candidate:
                    return candidate
    return None


def _project_path(path: str) -> str:
    """Normalise to a project-absolute, slash-prefixed, trailing-slash-free path."""
    path = path.replace(os.sep, "/").strip()
    if not path.startswith("/"):
        path = "/" + path
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def _tags_of(entry: Dict[str, Any]) -> List[str]:
    tags = entry.get("tags")
    if isinstance(tags, list):
        return [t for t in tags if isinstance(t, str)]
    return []


# --------------------------------------------------------------------------
# after-entry resolution
# --------------------------------------------------------------------------


class Index:
    """Lookup from directory path and tag to stack ID."""

    def __init__(self, stacks: Sequence[Dict[str, Any]]) -> None:
        self.by_dir: Dict[str, str] = {}
        self.by_tag: Dict[str, List[str]] = {}
        self.dirs: List[Tuple[str, str]] = []  # (dir, id), sorted
        for entry in stacks:
            stack_id = entry.get("id")
            directory = stack_dir_of(entry)
            if not isinstance(stack_id, str) or not directory:
                continue
            path = _project_path(directory)
            self.by_dir[path] = stack_id
            self.dirs.append((path, stack_id))
            for tag in _tags_of(entry):
                self.by_tag.setdefault(tag, []).append(stack_id)
        self.dirs.sort()

    def under(self, path: str) -> List[str]:
        """IDs of stacks at ``path`` or nested beneath it."""
        prefix = "/" if path == "/" else path + "/"
        out = []
        for directory, stack_id in self.dirs:
            if directory == path or directory.startswith(prefix):
                out.append(stack_id)
        return out

    def ancestors_of(self, path: str) -> List[str]:
        """IDs of stacks that contain ``path`` -- Terramate orders parents first."""
        out = []
        for directory, stack_id in self.dirs:
            if directory != path and path.startswith(directory + "/"):
                out.append(stack_id)
        return out

    def by_tag_filter(self, expression: str) -> Optional[List[str]]:
        """``tag:a:b`` is AND, ``tag:a,b`` is OR -- Terramate's filter syntax."""
        matched: List[str] = []
        any_known = False
        for group in expression.split(","):
            terms = [t for t in group.split(":") if t]
            if not terms:
                continue
            candidates: Optional[set] = None
            for term in terms:
                ids = set(self.by_tag.get(term, []))
                if term in self.by_tag:
                    any_known = True
                candidates = ids if candidates is None else (candidates & ids)
            if candidates:
                matched.extend(candidates)
        if not matched and not any_known:
            return None
        return sorted(set(matched))


def resolve_after_entry(entry: str, stack_path: str, index: Index) -> Optional[List[str]]:
    """Map one ``stack.after`` entry to the stack IDs it orders against.

    ``None`` means the entry could not be mapped. It is deliberately *not*
    mapped by stack ID: Terramate reads a bare string as a path, so accepting an
    ID here would let the enricher certify an ordering that Terramate never
    established -- exactly the silent failure (R2) this gate exists to catch.
    """
    entry = entry.strip()
    if not entry:
        return None
    if entry.startswith("tag:"):
        return index.by_tag_filter(entry[len("tag:") :])

    if entry.startswith("/"):
        target = _project_path(entry)
    else:
        target = _project_path(os.path.normpath(os.path.join(stack_path, entry)))

    exact = index.by_dir.get(target)
    if exact:
        return [exact]
    nested = index.under(target)
    return nested or None


# --------------------------------------------------------------------------
# Per-stack extraction
# --------------------------------------------------------------------------


def _eval_list(expr: Optional[Expr], scope: Dict[str, Any]) -> Tuple[List[Any], List[str]]:
    """Evaluate a list expression element by element.

    One unresolvable element must not discard the rest: a stack with three
    correct ``after`` entries and one computed one should still have the three
    checked.
    """
    if expr is None:
        return [], []
    value = hcl.evaluate(expr, scope)
    if isinstance(value, list):
        return value, []

    tokens = expr.tokens
    if len(tokens) >= 2 and tokens[0].is_punct("[") and tokens[-1].is_punct("]"):
        resolved: List[Any] = []
        unresolved: List[str] = []
        for chunk in hcl.split_top_level(tokens[1:-1], ","):
            if not chunk:
                continue
            item = hcl.evaluate(Expr(chunk, "", expr.line), scope)
            if item is UNRESOLVED:
                unresolved.append(hcl.tidy(" ".join(t.raw for t in chunk)))
            else:
                resolved.append(item)
        return resolved, unresolved
    return [], [expr.raw]


def _output_name(block: Block, label: str) -> str:
    """The producer-side output name, from ``value = outputs.<name>.value``."""
    expr = block.body.attributes.get("value")
    if expr is not None:
        path = hcl.traversal(expr.tokens)
        if path and len(path) >= 2 and path[0] == "outputs":
            return path[1]
    return label


def enrich_stack(
    entry: Dict[str, Any],
    loader: Loader,
    index: Index,
    errors: List[str],
) -> Dict[str, Any]:
    stack_id = entry.get("id")
    directory = stack_dir_of(entry)
    result = dict(entry)
    result["consumes"] = []
    result["produces"] = []
    result["after_ids"] = []
    result["after_unresolved"] = []
    result["implicit_after_ids"] = []

    if not directory:
        errors.append("stack %r has no directory in the inventory" % (stack_id,))
        return result

    stack_path = _project_path(directory)
    abs_dir = os.path.join(loader.root, stack_path.lstrip("/"))
    if not os.path.isdir(abs_dir):
        errors.append("stack %r: directory %s does not exist" % (stack_id, stack_path))
        return result

    metadata = {
        "stack": {
            "id": stack_id,
            "name": entry.get("name"),
            "path": stack_path,
            "tags": _tags_of(entry),
        }
    }
    scope = loader.globals_for(abs_dir, metadata)
    files = loader.stack_files(abs_dir)

    capability = scope.get("global", {}).get("capability")
    if isinstance(capability, str) and "capability" not in result:
        result["capability"] = capability

    # -- consumes ---------------------------------------------------------
    consumes: List[Dict[str, Any]] = []
    for path, block in _blocks(files, "input"):
        label = block.labels[0] if block.labels else ""
        expr = block.body.attributes.get("from_stack_id")
        if expr is None:
            errors.append(
                "%s:%d: input %r has no from_stack_id" % (loader.rel(path), block.line, label)
            )
            continue
        value = hcl.evaluate(expr, scope)
        resolved = isinstance(value, str) and value != ""
        consumes.append(
            {
                "name": label,
                "output": _output_name(block, label),
                "from_stack_id": value if resolved else None,
                "from_stack_id_expr": expr.raw,
                "resolved": resolved,
            }
        )
        if not resolved:
            errors.append(
                "%s:%d: input %r: from_stack_id %s does not resolve to a string"
                % (loader.rel(path), block.line, label, expr.raw)
            )
    result["consumes"] = consumes

    # -- produces ---------------------------------------------------------
    produces: List[str] = []
    for _path, block in _blocks(files, "output"):
        if block.labels and block.labels[0] not in produces:
            produces.append(block.labels[0])
    result["produces"] = produces

    # -- after ------------------------------------------------------------
    after_ids: List[str] = []
    unresolved_after: List[str] = []
    stack_blocks = [b for _p, b in _blocks(files, "stack")]
    for block in stack_blocks:
        entries, bad = _eval_list(block.body.attributes.get("after"), scope)
        unresolved_after.extend(bad)
        for item in entries:
            if not isinstance(item, str):
                unresolved_after.append(repr(item))
                continue
            ids = resolve_after_entry(item, stack_path, index)
            if ids is None:
                unresolved_after.append(item)
                continue
            for found in ids:
                if found != stack_id and found not in after_ids:
                    after_ids.append(found)

    if not stack_blocks:
        errors.append("stack %r: no stack block found under %s" % (stack_id, stack_path))

    result["after_ids"] = sorted(after_ids)
    result["after_unresolved"] = unresolved_after
    result["implicit_after_ids"] = sorted(
        i for i in index.ancestors_of(stack_path) if i != stack_id
    )
    return result


def _blocks(files: Iterable, *types: str) -> List[Tuple[str, Block]]:
    out: List[Tuple[str, Block]] = []
    for loaded in files:
        for block in loaded.body.of_type(*types):
            out.append((loaded.path, block))
    return out


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def enrich_document(document: Any, root: str) -> Tuple[Dict[str, Any], List[str]]:
    stacks, extras = normalise_inventory(document)
    loader = Loader(root)
    index = Index(stacks)
    errors: List[str] = []

    enriched = [enrich_stack(entry, loader, index, errors) for entry in stacks]
    errors = list(loader.errors) + errors

    unresolved_inputs = sum(
        1 for s in enriched for c in s["consumes"] if not c["resolved"]
    )
    unresolved_after = sum(len(s["after_unresolved"]) for s in enriched)

    out: Dict[str, Any] = dict(extras)
    out["stacks"] = enriched
    out["enrich"] = {
        "schema": SCHEMA_VERSION,
        "stacks": len(enriched),
        "consumes": sum(len(s["consumes"]) for s in enriched),
        "unresolved_inputs": unresolved_inputs,
        "unresolved_after": unresolved_after,
        "errors": sorted(set(errors)),
    }
    return out, errors
