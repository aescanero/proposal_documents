#!/usr/bin/env bash
# Destino: ci/fetch-observed.sh — trae la rama cmdb-observed, si existe
# Un repositorio nuevo no la tiene hasta la primera ejecución de cmdb-sync: eso significa
# "ningún entorno tiene marcador de deploy", no un error. Cualquier otro fallo del remoto
# (red, autenticación) sí es un error.
set -euo pipefail
rc=0; git ls-remote --exit-code --heads origin cmdb-observed >/dev/null || rc=$?
case $rc in
  0) git fetch origin cmdb-observed ;;
  2) echo "::notice::no cmdb-observed branch yet: no environment has a deploy marker" ;;
  *) exit "$rc" ;;
esac
