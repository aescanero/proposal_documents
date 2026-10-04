#!/usr/bin/env python3
"""The schemas' enums equal the registry: R34 checked today, without registry-generate.

registry/ is the source of truth and schemas/ is generated from it (CLAUDE.md, "The registry is
load-bearing"). Until registry-generate exists, nothing proves the two agree, and a step that only
prints a notice is a gate that cannot run. This compares every enum that derives from the
registry and fails on any difference, naming the side that is missing each value.

registry-generate --check replaces it when it exists (roadmap phase 2c.1).
"""
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")


def registry(name):
    return yaml.safe_load((ROOT / "registry" / f"{name}.yaml").read_text())[name]


manifest = json.loads((ROOT / "schemas" / "archetype-manifest.schema.json").read_text())["$defs"]

# (what, values in the registry, the enum generated from them)
CHECKS = [
    ("capabilities", registry("capabilities"), manifest["capability"]["enum"]),
    ("traits", registry("traits"), manifest["trait"]["enum"]),
    # only allocatable zones can be claimed: growth is reserved, never allocated
    ("allocatable zones", [z["name"] for z in registry("zones") if z.get("allocatable")],
     manifest["claim"]["properties"]["zone"]["enum"]),
]

failed = False
for what, source, enum in CHECKS:
    if not source or not enum:          # an empty side compares equal to nothing and proves nothing
        print(f"::error::{what}: an empty list cannot be checked (registry {len(source)}, schema {len(enum)})")
        failed = True
        continue
    src, gen = set(source), set(enum)
    for v in sorted(src - gen):
        print(f"::error::{what}: '{v}' is in registry/ but not in the schema enum — regenerate, never hand-edit")
    for v in sorted(gen - src):
        print(f"::error::{what}: '{v}' is in the schema enum but not in registry/ — a hand-edited enum (R34)")
    if src != gen or len(source) != len(src):
        failed = True
    else:
        print(f"ok  {what}: {len(src)} values, registry == schema")

sys.exit(1 if failed else 0)
