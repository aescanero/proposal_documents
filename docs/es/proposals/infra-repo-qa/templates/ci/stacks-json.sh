#!/usr/bin/env bash
# Destino: ci/stacks-json.sh — id, ruta, tags y after de cada stack, como un único array JSON
# Terramate 0.17 no tiene `list --json`: se evalúan los metadatos de cada stack
set -euo pipefail
terramate run --quiet -- terramate experimental eval \
  'tm_jsonencode({id = terramate.stack.id, path = terramate.stack.path.relative, tags = terramate.stack.tags, after = terramate.stack.after})' \
  | jq -s .
