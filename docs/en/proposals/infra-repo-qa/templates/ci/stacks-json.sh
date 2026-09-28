#!/usr/bin/env bash
# Destination: ci/stacks-json.sh — id, path, tags and after of every stack, as one JSON array
# Terramate 0.17 has no `list --json`: each stack's metadata is evaluated instead
set -euo pipefail
terramate run --quiet -- terramate experimental eval \
  'tm_jsonencode({id = terramate.stack.id, path = terramate.stack.path.relative, tags = terramate.stack.tags, after = terramate.stack.after})' \
  | jq -s .
