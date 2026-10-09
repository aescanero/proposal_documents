#!/usr/bin/env bash
# Destination: ci/hydrate.sh — renders every helm_release into _rendered/ (source-hydration DH2–DH5)
# Each stack that deploys charts carries _releases.json, written by `terramate generate`:
#   [{"name": "cert-manager", "namespace": "cert-manager", "chart": "oci://…/charts/cert-manager",
#     "version": "v1.16.2", "values": "_values-cert-manager.yaml"}]
# Per release it writes, next to the stack:
#   _rendered/<name>.yaml         what `helm get manifest` will return, minus the CRDs
#   _rendered/<name>.hooks.yaml   hooks: `helm template` renders them, `helm get manifest` does not
#   _rendered/<name>.crds.sha256  one line per CRD: name and digest (CRDs are ~97 % of the bytes)
set -euo pipefail

mapfile -t release_files < <(git ls-files -co --exclude-standard '*/_releases.json')
[ "${#release_files[@]}" -gt 0 ] || { echo "hydrate: no _releases.json: nothing would be rendered" >&2; exit 1; }

for rf in "${release_files[@]}"; do
  dir=$(dirname "$rf")
  out="$dir/_rendered"
  mkdir -p "$out"
  find "$out" -maxdepth 1 -type f -name '*' -delete         # a release removed from the stack leaves nothing behind
  jq -c '.[]' "$rf" | while read -r rel; do
    name=$(jq -r .name <<<"$rel"); ns=$(jq -r .namespace <<<"$rel")
    chart=$(jq -r .chart <<<"$rel"); version=$(jq -r .version <<<"$rel"); values=$(jq -r .values <<<"$rel")
    [[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "hydrate: bad release name '$name' in $rf" >&2; exit 1; }
    helm template "$name" "$chart" --version "$version" --namespace "$ns" \
      --values "$dir/$values" --include-crds --kube-version "${KUBE_VERSION:?pinned in .mise.toml}" \
      | python3 -I "$(dirname "$0")/split-rendered.py" "$out" "$name"
  done
done
