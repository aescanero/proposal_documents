#!/usr/bin/env bash
# Destino: ci/changed-envs.sh
# Para cada entorno: ¿hay stacks cambiados desde su último deploy con éxito?
# Escribe en $GITHUB_OUTPUT: lz=<objeto|vacío>, nonprod=<lista>, prod=<objeto|vacío>
set -euo pipefail

marker() {   # commit del último deploy con éxito del entorno, o vacío
  git show "origin/cmdb-observed:cmdb-data/observed/deployed/$1.json" 2>/dev/null | jq -r .sha || true
}

lz=""; prod=""; nonprod="[]"
for env in landing-zone $(ls environments); do
  base="$(marker "$env")"
  if [ -z "$base" ]; then
    echo "::warning::$env no tiene marcador de deploy: su primer despliegue es first-deploy (arquitectura §4.11)"
    continue
  fi
  if ! git merge-base --is-ancestor "$base" HEAD; then
    echo "::error::el marcador de $env ($base) no está en la historia de main"
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
