#!/usr/bin/env bash
# Destination: ci/g1.sh — the G1 gate (architecture §14.4), the same locally and in CI
set -euo pipefail

registry-generate --check                     # the registry is the source of truth; also writes registry/registry.json
archetypectl resolve --dry-run > resolution.json
./ci/stacks-json.sh > stacks.json             # id, path, tags, after (architecture §14.4)
archetypectl enrich stacks.json               # adds consumes[] and after_ids[]
archetypectl cmdb check                       # the CMDB's declared half is current (cmdb-qa DI2)
yq -o=json '.metadata.name' environments/*/binding.yaml | jq -s '{environments: {names: .}}' > environments.json
jq -e '.environments.names | length > 0' environments.json >/dev/null || { echo "G1: no environment" >&2; exit 1; }   # every environment's name, from the only list there is (multi-environment DX8): public names and G3 read it
./ci/check-federation.sh                      # federation coordinates in one reviewed file (landing-zone-qa DZ12)

conftest verify --policy policy/              # the policies' own tests

ct() {                                        # conftest that refuses to pass having evaluated nothing (§14.4)
  local out
  out=$(conftest test --all-namespaces --policy policy/ --data registry/registry.json --data environments.json -o json "$@") \
    || { jq -r '.[] | .filename as $f | .failures[]? | "FAIL \($f): \(.msg)"' <<<"$out"; return 1; }
  jq -e '[.[] | .successes + (.failures // [] | length)] | add > 0' <<<"$out" >/dev/null \
    || { echo "G1: no rule evaluated for $*" >&2; return 1; }
}

ct resolution.json stacks.json
for m in archetypes/*/manifest.yaml; do ct "$m"; done
for b in environments/*/binding.yaml; do ct "$b"; done     # public names: public_id and dns_suffix (§13.3)

# Admission before apply (source-hydration DH6): the library's constraints over each environment's rendering.
# A rendered P2/P11/P12/P13 violation fails the PR instead of the apply.
rendered=0
for b in environments/*/binding.yaml; do
  env=$(basename "$(dirname "$b")")
  mapfile -t files < <(terramate list --tags "$env" | while read -r d; do find "$d/_rendered" -maxdepth 1 -name '*.yaml' 2>/dev/null; done)
  [ "${#files[@]}" -gt 0 ] || continue                     # an environment whose stacks deploy no chart
  rendered=$((rendered + ${#files[@]}))
  gator test $(printf -- '--filename=%s ' "${files[@]}")
done
[ "$rendered" -gt 0 ] || { echo "G1: no rendered manifest reached gator" >&2; exit 1; }
