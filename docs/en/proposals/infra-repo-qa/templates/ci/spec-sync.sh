#!/usr/bin/env bash
# Destination: ci/spec-sync.sh — registry/ and schemas/ are a pinned, byte-identical copy of the specification
# The specification (aescanero/proposal_documents) is the normative origin; infra never edits the copy.
#   --check                    the copies match spec.lock.json, and nothing outside it was added (a hand edit)
#   --upstream <clone>         spec.lock.json matches the pinned commit of the origin (a lock edited by hand)
#   --update <clone> <commit>  copy both directories at <commit> and rewrite the lock; the pull request shows the diff
set -euo pipefail
LOCK=spec.lock.json
sums() { git ls-files -co --exclude-standard registry schemas | sort | while read -r f; do
           printf '%s\t%s\n' "$f" "$(sha256sum < "$f" | cut -d' ' -f1)"; done; }

case "${1:-}" in
  --check)
    diff <(jq -r '.files | to_entries[] | "\(.key)\t\(.value)"' "$LOCK" | sort) <(sums) \
      || { echo "::error::registry/ or schemas/ differ from spec.lock.json: edit the specification, then raise the pin"; exit 1; } ;;
  --upstream)
    commit=$(jq -r .commit "$LOCK")
    jq -r '.files | to_entries[] | "\(.key) \(.value)"' "$LOCK" | while read -r path sum; do
      [ "$(git -C "$2" show "$commit:$path" | sha256sum | cut -d' ' -f1)" = "$sum" ] \
        || { echo "::error::$path differs from the pinned commit $commit"; exit 1; }
    done ;;
  --update)
    git rm -rq --ignore-unmatch registry schemas
    git -C "$2" archive "$3" registry schemas | tar -x
    sums | jq -Rn --arg repo aescanero/proposal_documents --arg commit "$(git -C "$2" rev-parse "$3")" \
      '{spec_repo: $repo, commit: $commit, files: ([inputs | split("\t") | {(.[0]): .[1]}] | add)}' > "$LOCK" ;;
  *) echo "usage: $0 --check | --upstream <clone> | --update <clone> <commit>" >&2; exit 2 ;;
esac
