#!/usr/bin/env bash
# Destino: ci/stacks-json.sh — id, ruta, tags y after de cada stack, como un único array JSON
# Terramate 0.17 no tiene `list --json`, y `experimental eval` no expone `after`: se lee `debug show metadata`
set -euo pipefail
terramate debug show metadata | jq -Rn '
  reduce (inputs | select(test("^\\s+terramate\\.stack\\."))
          | capture("^\\s+terramate\\.stack\\.(?<k>[a-z_.]+)=(?<v>.*)$")) as $m
    ([]; if $m.k == "id" then . + [{}] else . end | .[-1][$m.k] = ($m.v | fromjson))
  | map({id, path: .["path.relative"], tags, after})
  | if length == 0 then error("stacks-json: no stack parsed") else . end'
