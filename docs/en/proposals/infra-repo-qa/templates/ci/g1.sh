#!/usr/bin/env bash
# Destination: ci/g1.sh — the G1 gate (architecture §14.4), the same locally and in CI
set -euo pipefail

registry-generate --check                     # the registry is the source of truth
archetypectl resolve --dry-run > resolution.json
./ci/stacks-json.sh > stacks.json           # Terramate 0.16 has no list --json
archetypectl enrich stacks.json               # adds consumes[] and after_ids[]
archetypectl cmdb check                       # the CMDB's declared half is current (cmdb-qa DI2)

conftest verify --policy policy/              # the policies' own tests
conftest test --policy policy/ --data registry/ resolution.json stacks.json
for m in archetypes/*/manifest.yaml; do
  conftest test --policy policy/ --data registry/ "$m"
done
for b in environments/*/binding.yaml; do      # public names: public_id and dns_suffix (§13.3)
  conftest test --policy policy/ --data registry/ "$b"
done
