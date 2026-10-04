#!/usr/bin/env bash
# Destination: ci/fetch-observed.sh — fetch the cmdb-observed branch, if there is one
# A new repository has none until cmdb-sync's first run: that means "no environment has a
# deploy marker", not an error. Any other failure of the remote (network, auth) is an error.
set -euo pipefail
rc=0; git ls-remote --exit-code --heads origin cmdb-observed >/dev/null || rc=$?
case $rc in
  0) git fetch origin cmdb-observed ;;
  2) echo "::notice::no cmdb-observed branch yet: no environment has a deploy marker" ;;
  *) exit "$rc" ;;
esac
