#!/usr/bin/env bash
#
# State-encryption migration probe — how the landing zone's bootstrap moves its
# first, plaintext state into an encrypted backend, and what the committed
# configuration can say from day one.
#
# Two local backends stand in for "local state" and "the bucket"; a pbkdf2
# passphrase stands in for the KMS key. No cloud.
#
# Usage:  ./run-encryption.sh [workdir]
# Output: a transcript on stdout. ../RESULTS.md, section A9, quotes it.

set -uo pipefail

WORK="${1:-${TMPDIR:-/tmp}/tofu-encryption-poc}"
hdr() { printf '\n========== %s ==========\n' "$*"; }
rc()  { printf '[exit %s]\n' "$1"; }
state_of() { [ -f "$1" ] || { echo "$1: not written"; return; }
             grep -q '"encrypted_data"' "$1" && echo "$1: encrypted" || echo "$1: PLAINTEXT"; }
errors() { grep -E '^(Error|Warning): ' | sort -u | head -4; }

mkdir -p "$WORK" && cd "$WORK" || exit 1
export TF_CLI_ARGS="-no-color"

# The fallback the migration needs, never committed: method plus fallback, both in the env var
FALLBACK='
method "unencrypted" "migrate" {}
state {
  method = method.aes_gcm.env
  fallback {
    method = method.unencrypted.migrate
  }
}'

# A fresh workdir with a plaintext state in "local", then the backend switched to "bucket"
fresh() {   # fresh <enforced: true|false>
  rm -rf ./.terraform ./*.tf ./*.tfstate ./*.tfstate.backup
  printf 'resource "terraform_data" "bucket_stand_in" {\n  input = "mock-bucket"\n}\n' > main.tf
  printf 'terraform {\n  backend "local" { path = "local.tfstate" }\n}\n' > backend.tf
  tofu init -input=false >/dev/null && tofu apply -auto-approve -input=false >/dev/null || echo "setup failed"
  cat > backend.tf <<HCL
terraform {
  backend "local" { path = "bucket.tfstate" }
  encryption {
    key_provider "pbkdf2" "env" {
      passphrase = "mock-passphrase-of-32-characters!!"
    }
    method "aes_gcm" "env" {
      keys = key_provider.pbkdf2.env
    }
    state {
      method   = method.aes_gcm.env
      enforced = $1
    }
    plan {
      method   = method.aes_gcm.env
      enforced = $1
    }
  }
}
HCL
}

hdr "versions"
tofu version | head -1

hdr "A9a — migrate a plaintext state with no fallback anywhere"
fresh false
tofu init -input=false -migrate-state -force-copy 2>&1 | errors; rc "${PIPESTATUS[0]}"
state_of bucket.tfstate

hdr "A9b — fallback only in TF_ENCRYPTION, committed configuration without enforced"
fresh false
TF_ENCRYPTION="$FALLBACK" tofu init -input=false -migrate-state -force-copy 2>&1 | errors; rc "${PIPESTATUS[0]}"
state_of bucket.tfstate
echo "--- plan with the committed configuration alone (0 = no changes)"
tofu plan -input=false -detailed-exitcode >/dev/null 2>&1; rc $?

hdr "A9c — fallback only in TF_ENCRYPTION, committed configuration with enforced = true"
fresh true
TF_ENCRYPTION="$FALLBACK" tofu init -input=false -migrate-state -force-copy 2>&1 | errors; rc "${PIPESTATUS[0]}"
state_of bucket.tfstate

hdr "A9d — the same, and TF_ENCRYPTION also sets enforced = false for this one process"
fresh true
TF_ENCRYPTION="$FALLBACK
plan {
  method   = method.aes_gcm.env
  enforced = false
}" ; TF_ENCRYPTION="${TF_ENCRYPTION/state \{/state \{
  enforced = false}"
export TF_ENCRYPTION
tofu init -input=false -migrate-state -force-copy 2>&1 | errors; rc "${PIPESTATUS[0]}"
unset TF_ENCRYPTION
state_of bucket.tfstate

hdr "A9e — after a migration, the committed enforced = true configuration"
fresh false
TF_ENCRYPTION="$FALLBACK" tofu init -input=false -migrate-state -force-copy >/dev/null 2>&1
sed -i 's/enforced = false/enforced = true/' backend.tf
tofu init -input=false -reconfigure >/dev/null 2>&1
echo "--- plan (0 = no changes)"
tofu plan -input=false -detailed-exitcode >/dev/null 2>&1; rc $?
echo "--- an unencrypted method injected through TF_ENCRYPTION"
TF_ENCRYPTION='
method "unencrypted" "plain" {}
state {
  method = method.unencrypted.plain
}' tofu apply -auto-approve -input=false 2>&1 | errors; rc "${PIPESTATUS[0]}"
state_of bucket.tfstate
