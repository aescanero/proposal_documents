#!/usr/bin/env bash
# Destino: ci/g1.sh — la puerta G1 (arquitectura §14.4), igual en local y en CI
set -euo pipefail

registry-generate --check                     # el registro es la fuente de verdad
archetypectl resolve --dry-run > resolution.json
./ci/stacks-json.sh > stacks.json           # Terramate 0.16 no tiene list --json
archetypectl enrich stacks.json               # añade consumes[] y after_ids[]
archetypectl cmdb check                       # la mitad declarada de la CMDB está al día (cmdb-qa DI2)

conftest verify --policy policy/              # los tests de las propias políticas
conftest test --policy policy/ --data registry/ resolution.json stacks.json
for m in archetypes/*/manifest.yaml; do
  conftest test --policy policy/ --data registry/ "$m"
done
for b in environments/*/binding.yaml; do      # nombres públicos: public_id y dns_suffix (§13.3)
  conftest test --policy policy/ --data registry/ "$b"
done
