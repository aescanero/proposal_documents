#!/usr/bin/env bash
# Destino: ci/g1.sh — la puerta G1 (arquitectura §14.4), igual en local y en CI
set -euo pipefail

registry-generate --check                     # el registro es la fuente de verdad; escribe también registry/registry.json
archetypectl resolve --dry-run > resolution.json
./ci/stacks-json.sh > stacks.json             # id, ruta, tags, after (arquitectura §14.4)
archetypectl enrich stacks.json               # añade consumes[] y after_ids[]
archetypectl cmdb check                       # la mitad declarada de la CMDB está al día (cmdb-qa DI2)
yq -o=json '.metadata.name' environments/*/binding.yaml | jq -s '{environments: {names: .}}' > environments.json
jq -e '.environments.names | length > 0' environments.json >/dev/null || { echo "G1: no environment" >&2; exit 1; }   # el nombre de cada entorno, de la única lista que hay (multi-environment DX8): lo leen los nombres públicos y G3
./ci/check-federation.sh                      # coordenadas de la federación en un fichero revisado (landing-zone-qa DZ12)

conftest verify --policy policy/              # los tests de las propias políticas

ct() {                                        # conftest que se niega a pasar sin haber evaluado nada (§14.4)
  local out
  out=$(conftest test --all-namespaces --policy policy/ --data registry/registry.json --data environments.json -o json "$@") \
    || { jq -r '.[] | .filename as $f | .failures[]? | "FAIL \($f): \(.msg)"' <<<"$out"; return 1; }
  jq -e '[.[] | .successes + (.failures // [] | length)] | add > 0' <<<"$out" >/dev/null \
    || { echo "G1: no rule evaluated for $*" >&2; return 1; }
}

ct resolution.json stacks.json
for m in archetypes/*/manifest.yaml; do ct "$m"; done
for b in environments/*/binding.yaml; do ct "$b"; done     # nombres públicos: public_id y dns_suffix (§13.3)

# Admisión antes del apply (source-hydration DH6): los constraints de library sobre lo renderizado de cada entorno.
# Una violación de P2/P11/P12/P13 en lo renderizado falla el PR en vez del apply.
rendered=0
for b in environments/*/binding.yaml; do
  env=$(basename "$(dirname "$b")")
  mapfile -t files < <(terramate list --tags "$env" | while read -r d; do find "$d/_rendered" -maxdepth 1 -name '*.yaml' 2>/dev/null; done)
  [ "${#files[@]}" -gt 0 ] || continue                     # un entorno cuyos stacks no despliegan ningún chart
  rendered=$((rendered + ${#files[@]}))
  gator test $(printf -- '--filename=%s ' "${files[@]}")
done
[ "$rendered" -gt 0 ] || { echo "G1: ningún manifiesto renderizado llegó a gator" >&2; exit 1; }
