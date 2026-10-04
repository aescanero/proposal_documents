#!/usr/bin/env bash
# Destination: ci/check-federation.sh — G1: the federation coordinates live in one reviewed file (landing-zone-qa DZ12)
set -euo pipefail
fail=0

# 1. Nothing reads identity coordinates from variables: they would be editable without review
if grep -rnE 'vars\.GCP_' .github/; then
  echo "::error::read ci/federation.env through .github/actions/setup, never vars.GCP_*"; fail=1
fi

# 2. Every key is present and well formed
# shellcheck source=/dev/null
source ci/federation.env
for k in GCP_LZ_PROJECT GCP_LZ_PROJECT_NUMBER GCP_WIF_POOL GCP_WIF_PROVIDER_ID; do
  [ -n "${!k:-}" ] || { echo "::error::ci/federation.env: $k is missing"; fail=1; }
done
[[ "${GCP_LZ_PROJECT_NUMBER:-}" =~ ^[0-9]{6,}$ ]] || { echo "::error::GCP_LZ_PROJECT_NUMBER is not a project number"; fail=1; }
[[ "${GCP_LZ_PROJECT_NUMBER:-}" =~ ^0+$ ]] && echo "::notice::GCP_LZ_PROJECT_NUMBER is still the placeholder: plans fail to authenticate until the bootstrap runs"

# 3. The file names the pool and provider the bootstrap creates
for v in "$GCP_WIF_POOL" "$GCP_WIF_PROVIDER_ID"; do
  grep -rqF "\"$v\"" stacks/landing-zone/gcp/bootstrap modules/gcp-lz-bootstrap 2>/dev/null \
    || { echo "::error::$v is not what the bootstrap creates"; fail=1; }
done

exit "$fail"
