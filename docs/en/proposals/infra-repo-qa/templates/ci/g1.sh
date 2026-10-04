#!/usr/bin/env bash
# Destination: ci/g1.sh — the G1 gate (architecture §14.4), the same locally and in CI
set -euo pipefail

registry-generate --check                     # the registry is the source of truth; also writes registry/registry.json
archetypectl resolve --dry-run > resolution.json
./ci/stacks-json.sh > stacks.json             # id, path, tags, after (architecture §14.4)
archetypectl enrich stacks.json               # adds consumes[] and after_ids[]
archetypectl cmdb check                       # the CMDB's declared half is current (cmdb-qa DI2)

conftest verify --policy policy/              # the policies' own tests

ct() {                                        # conftest that refuses to pass having evaluated nothing (§14.4)
  local out
  out=$(conftest test --all-namespaces --policy policy/ --data registry/registry.json -o json "$@") \
    || { jq -r '.[] | .filename as $f | .failures[]? | "FAIL \($f): \(.msg)"' <<<"$out"; return 1; }
  jq -e '[.[] | .successes + (.failures // [] | length)] | add > 0' <<<"$out" >/dev/null \
    || { echo "G1: no rule evaluated for $*" >&2; return 1; }
}

ct resolution.json stacks.json
for m in archetypes/*/manifest.yaml; do ct "$m"; done
for b in environments/*/binding.yaml; do ct "$b"; done     # public names: public_id and dns_suffix (§13.3)
