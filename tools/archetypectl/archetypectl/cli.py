"""Command line entry point for archetypectl."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, List, Optional

from . import __version__
from .enrich import enrich_document

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_STRICT = 2


def find_root(start: str) -> str:
    """Walk up for the project root: a terramate config, else the git root."""
    current = os.path.abspath(start)
    while True:
        for marker in ("terramate.tm.hcl", "terramate.tm", ".git"):
            if os.path.exists(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(start)
        current = parent


def _read_json(path: str) -> Any:
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    text = text.strip()
    if not text:
        raise ValueError("input is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # terramate has emitted newline-delimited JSON in some versions.
        lines = [line for line in text.splitlines() if line.strip()]
        try:
            return [json.loads(line) for line in lines]
        except json.JSONDecodeError as exc:
            raise ValueError("input is not JSON or newline-delimited JSON: %s" % exc)


def cmd_enrich(args: argparse.Namespace) -> int:
    source = args.stacks
    try:
        document = _read_json(source)
    except (OSError, ValueError) as exc:
        print("archetypectl enrich: %s" % exc, file=sys.stderr)
        return EXIT_USAGE

    root = args.root or find_root(
        os.path.dirname(os.path.abspath(source)) if source != "-" else os.getcwd()
    )
    if not os.path.isdir(root):
        print("archetypectl enrich: --root %s is not a directory" % root, file=sys.stderr)
        return EXIT_USAGE

    try:
        result, errors = enrich_document(document, root)
    except ValueError as exc:
        print("archetypectl enrich: %s" % exc, file=sys.stderr)
        return EXIT_USAGE

    payload = (
        json.dumps(result, indent=args.indent, sort_keys=False, ensure_ascii=False) + "\n"
    )

    destination = args.output
    if destination is None:
        destination = "-" if source == "-" else source
    try:
        if destination == "-":
            sys.stdout.write(payload)
        else:
            with open(destination, "w", encoding="utf-8") as handle:
                handle.write(payload)
    except OSError as exc:
        print("archetypectl enrich: cannot write %s: %s" % (destination, exc), file=sys.stderr)
        return EXIT_USAGE

    summary = result["enrich"]
    for message in summary["errors"]:
        print("archetypectl enrich: %s" % message, file=sys.stderr)
    if not args.quiet:
        print(
            "archetypectl enrich: %d stacks, %d inputs, "
            "%d unresolved from_stack_id, %d unresolved after entries"
            % (
                summary["stacks"],
                summary["consumes"],
                summary["unresolved_inputs"],
                summary["unresolved_after"],
            ),
            file=sys.stderr,
        )

    if args.strict and (errors or summary["unresolved_inputs"] or summary["unresolved_after"]):
        print(
            "archetypectl enrich: --strict and the extraction is incomplete; "
            "the G1 gate would be checking a partial picture",
            file=sys.stderr,
        )
        return EXIT_STRICT
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archetypectl",
        description="Platform tooling for the archetype model.",
    )
    parser.add_argument("--version", action="version", version="archetypectl " + __version__)
    subparsers = parser.add_subparsers(dest="command")

    enrich = subparsers.add_parser(
        "enrich",
        help="add consumes[] and after_ids[] to the output of 'terramate list --json'",
        description=(
            "Read 'terramate list --json', scan each stack directory (following "
            "import blocks) for input/output blocks and stack.after, and write "
            "stacks.json with consumes[], produces[] and after_ids[] -- the input "
            "of the G1 policy."
        ),
    )
    enrich.add_argument(
        "stacks",
        nargs="?",
        default="-",
        help="the terramate list --json file; '-' reads stdin (default)",
    )
    enrich.add_argument(
        "-o",
        "--output",
        help="where to write; defaults to rewriting the input file in place, "
        "or stdout when reading stdin",
    )
    enrich.add_argument("--root", help="project root (default: nearest terramate config or git root)")
    enrich.add_argument("--indent", type=int, default=2, help="JSON indent (default: 2)")
    enrich.add_argument(
        "--strict",
        action="store_true",
        help="exit %d if anything could not be extracted, instead of reporting it "
        "in enrich.errors" % EXIT_STRICT,
    )
    enrich.add_argument("-q", "--quiet", action="store_true", help="suppress the summary line")
    enrich.set_defaults(func=cmd_enrich)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
