#!/usr/bin/env bash
# Destination: ci/changed-envs.sh
# For each environment: are there stacks changed since its last successful deploy?
# Writes to $GITHUB_OUTPUT: lz=<object|empty>, nonprod=<list>, prod=<object|empty>
set -euo pipefail

marker() {   # commit of the environment's last successful deploy, or empty
  git show "origin/cmdb-observed:cmdb-data/observed/deployed/$1.json" 2>/dev/null | jq -r .sha || true
}

lz=""; prod=""; nonprod="[]"
for env in landing-zone $(ls environments); do
  base="$(marker "$env")"
  if [ -z "$base" ]; then
    echo "::warning::$env has no deploy marker: its first deployment is first-deploy (architecture §4.11)"
    continue
  fi
  if ! git merge-base --is-ancestor "$base" HEAD; then
    echo "::error::the marker of $env ($base) is not in main's history"
    exit 1
  fi
  [ -n "$(terramate list --changed -B "$base" --tags "$env" --no-tags bootstrap)" ] || continue
  item="$(jq -cn --arg env "$env" --arg base "$base" '{env: $env, base: $base}')"
  case "$env" in
    landing-zone) lz="$item" ;;
    prod)         prod="$item" ;;
    *)            nonprod="$(jq -c --argjson i "$item" '. + [$i]' <<<"$nonprod")" ;;
  esac
done

{
  echo "lz=$lz"
  echo "nonprod=$nonprod"
  echo "prod=$prod"
} >> "$GITHUB_OUTPUT"
