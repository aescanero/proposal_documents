#!/usr/bin/env bash
# Destination: ci/stacks-json.sh — id, path, tags and after of every stack, as one JSON array
# Terramate 0.17 has no `list --json`, and `experimental eval` does not expose `after`: parse `debug show metadata`
set -euo pipefail
terramate debug show metadata | jq -Rn '
  reduce (inputs | select(test("^\\s+terramate\\.stack\\."))
          | capture("^\\s+terramate\\.stack\\.(?<k>[a-z_.]+)=(?<v>.*)$")) as $m
    ([]; if $m.k == "id" then . + [{}] else . end | .[-1][$m.k] = ($m.v | fromjson))
  | map({id, path: .["path.relative"], tags, after})
  | if length == 0 then error("stacks-json: no stack parsed") else . end'
