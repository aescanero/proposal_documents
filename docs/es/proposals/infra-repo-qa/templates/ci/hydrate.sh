#!/usr/bin/env bash
# Destino: ci/hydrate.sh — renderiza cada helm_release en _rendered/ (source-hydration DH2–DH5)
# Cada stack que despliega charts lleva _releases.json, escrito por `terramate generate`:
#   [{"name": "cert-manager", "namespace": "cert-manager", "chart": "oci://…/charts/cert-manager",
#     "version": "v1.16.2", "values": "_values-cert-manager.yaml"}]
# Por cada release escribe, junto al stack:
#   _rendered/<name>.yaml         lo que devolverá `helm get manifest`, sin los CRD
#   _rendered/<name>.hooks.yaml   hooks: `helm template` los renderiza, `helm get manifest` no
#   _rendered/<name>.crds.sha256  una línea por CRD: nombre y digest (los CRD son ~97 % de los bytes)
set -euo pipefail

mapfile -t release_files < <(git ls-files -co --exclude-standard '*/_releases.json')
[ "${#release_files[@]}" -gt 0 ] || { echo "hydrate: no hay _releases.json: no se renderizaría nada" >&2; exit 1; }

for rf in "${release_files[@]}"; do
  dir=$(dirname "$rf")
  out="$dir/_rendered"
  mkdir -p "$out"
  find "$out" -maxdepth 1 -type f -name '*' -delete         # un release que sale del stack no deja nada atrás
  jq -c '.[]' "$rf" | while read -r rel; do
    name=$(jq -r .name <<<"$rel"); ns=$(jq -r .namespace <<<"$rel")
    chart=$(jq -r .chart <<<"$rel"); version=$(jq -r .version <<<"$rel"); values=$(jq -r .values <<<"$rel")
    [[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "hydrate: nombre de release no válido '$name' en $rf" >&2; exit 1; }
    helm template "$name" "$chart" --version "$version" --namespace "$ns" \
      --values "$dir/$values" --include-crds --kube-version "${KUBE_VERSION:?fijada en .mise.toml}" \
      | python3 -I "$(dirname "$0")/split-rendered.py" "$out" "$name"
  done
done
