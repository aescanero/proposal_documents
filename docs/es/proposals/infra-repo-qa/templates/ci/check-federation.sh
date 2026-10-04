#!/usr/bin/env bash
# Destino: ci/check-federation.sh — G1: las coordenadas de la federación viven en un fichero revisado (landing-zone-qa DZ12)
set -euo pipefail
fail=0

# 1. Nada lee coordenadas de identidad de variables: serían editables sin revisión
if grep -rnE 'vars\.GCP_' .github/; then
  echo "::error::read ci/federation.env through .github/actions/setup, never vars.GCP_*"; fail=1
fi

# 2. Cada clave existe y tiene la forma correcta
# shellcheck source=/dev/null
source ci/federation.env
for k in GCP_LZ_PROJECT GCP_LZ_PROJECT_NUMBER GCP_WIF_POOL GCP_WIF_PROVIDER_ID; do
  [ -n "${!k:-}" ] || { echo "::error::ci/federation.env: $k is missing"; fail=1; }
done
[[ "${GCP_LZ_PROJECT_NUMBER:-}" =~ ^[0-9]{6,}$ ]] || { echo "::error::GCP_LZ_PROJECT_NUMBER is not a project number"; fail=1; }
[[ "${GCP_LZ_PROJECT_NUMBER:-}" =~ ^0+$ ]] && echo "::notice::GCP_LZ_PROJECT_NUMBER is still the placeholder: plans fail to authenticate until the bootstrap runs"

# 3. El fichero nombra el pool y el proveedor que crea el bootstrap
for v in "$GCP_WIF_POOL" "$GCP_WIF_PROVIDER_ID"; do
  grep -rqF "\"$v\"" stacks/landing-zone/gcp/bootstrap modules/gcp-lz-bootstrap 2>/dev/null \
    || { echo "::error::$v is not what the bootstrap creates"; fail=1; }
done

exit "$fail"
