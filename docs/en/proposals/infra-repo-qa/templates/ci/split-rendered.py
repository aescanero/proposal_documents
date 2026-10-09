#!/usr/bin/env python3
"""Destination: ci/split-rendered.py — splits one `helm template` output (stdin) into _rendered/ files.

Called by ci/hydrate.sh. Fails on a Secret that carries a value: secrets reach the cluster through
ESO, never through git (source-hydration DH5, RH3).
"""
import hashlib
import pathlib
import sys

import yaml

out, name = pathlib.Path(sys.argv[1]), sys.argv[2]
manifest, hooks, crds = [], [], []
for doc in yaml.safe_load_all(sys.stdin):
    if not doc:
        continue
    kind = doc.get("kind")
    meta = doc.get("metadata") or {}
    if kind == "Secret" and (doc.get("data") or doc.get("stringData")):
        sys.exit(f"hydrate: {name}: Secret {meta.get('name')} carries a value; secrets come from ESO")
    if kind == "CustomResourceDefinition":
        digest = hashlib.sha256(yaml.safe_dump(doc, sort_keys=True).encode()).hexdigest()
        crds.append(f"{meta['name']} {digest}")
    elif "helm.sh/hook" in (meta.get("annotations") or {}):
        hooks.append(doc)
    else:
        manifest.append(doc)

if not manifest and not hooks and not crds:
    sys.exit(f"hydrate: {name}: the chart rendered nothing")
key = lambda d: (d.get("kind", ""), (d.get("metadata") or {}).get("namespace", ""), (d.get("metadata") or {}).get("name", ""))
dump = lambda docs: yaml.safe_dump_all(sorted(docs, key=key), sort_keys=True, default_flow_style=False)
(out / f"{name}.yaml").write_text(dump(manifest))
if hooks:
    (out / f"{name}.hooks.yaml").write_text(dump(hooks))
if crds:
    (out / f"{name}.crds.sha256").write_text("\n".join(sorted(crds)) + "\n")
