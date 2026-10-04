#!/usr/bin/env bash
# Destino: ci/g1.sh — la puerta G1 (arquitectura §14.4), igual en local y en CI
set -euo pipefail

registry-generate --check                     # el registro es la fuente de verdad; escribe también registry/registry.json
archetypectl resolve --dry-run > resolution.json
./ci/stacks-json.sh > stacks.json             # id, ruta, tags, after (arquitectura §14.4)
archetypectl enrich stacks.json               # añade consumes[] y after_ids[]
archetypectl cmdb check                       # la mitad declarada de la CMDB está al día (cmdb-qa DI2)
./ci/check-federation.sh                      # coordenadas de la federación en un fichero revisado (landing-zone-qa DZ12)

conftest verify --policy policy/              # los tests de las propias políticas

ct() {                                        # conftest que se niega a pasar sin haber evaluado nada (§14.4)
  local out
  out=$(conftest test --all-namespaces --policy policy/ --data registry/registry.json -o json "$@") \
    || { jq -r '.[] | .filename as $f | .failures[]? | "FAIL \($f): \(.msg)"' <<<"$out"; return 1; }
  jq -e '[.[] | .successes + (.failures // [] | length)] | add > 0' <<<"$out" >/dev/null \
    || { echo "G1: no rule evaluated for $*" >&2; return 1; }
}

ct resolution.json stacks.json
for m in archetypes/*/manifest.yaml; do ct "$m"; done
for b in environments/*/binding.yaml; do ct "$b"; done     # nombres públicos: public_id y dns_suffix (§13.3)
