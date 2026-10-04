#!/usr/bin/env bash
#
# Gate tooling probes — what the G1/G3 commands and the stack inventory
# actually evaluate, against the pinned Terramate and conftest.
#
# Each probe builds its fixture in a scratch directory outside any git
# repository (Terramate takes its project root from the git root; see
# ../RESULTS.md, "Why a harness"). No cloud, no network, no tofu.
#
# Usage:  ./run-gates.sh [workdir]
# Output: a transcript on stdout. ../RESULTS.md, section A8, quotes it.

set -uo pipefail

WORK="${1:-${TMPDIR:-/tmp}/tm-gates-poc}"
hdr() { printf '\n========== %s ==========\n' "$*"; }
sub() { printf '\n----- %s\n' "$*"; }
rc()  { printf '[exit %s]\n' "$1"; }

rm -rf "$WORK"; mkdir -p "$WORK/tm" "$WORK/cf/policy" "$WORK/cf/registry"

hdr "versions"
terramate version 2>&1 | head -1
conftest --version 2>&1

# ---------------------------------------------------------------- Terramate
cd "$WORK/tm" || exit 1
git init -q .
mkdir -p a b
cat > terramate.tm.hcl <<'HCL'
terramate {
  required_version = "= 0.17.3"
  config { experiments = ["outputs-sharing"] }
}
HCL
printf 'stack {\n  id   = "a"\n  tags = ["gcp", "qa"]\n}\n' > a/stack.tm.hcl
cat > b/stack.tm.hcl <<'HCL'
stack {
  id    = "b"
  tags  = ["gcp", "qa"]
  after = ["tag:gcp:qa:network", "/a"]
}
script "deploy" {
  description = "probe"
  job { command = ["echo", "script ran"] }
}
HCL
git add -A && git -c user.email=poc@invalid -c user.name=poc commit -qm fixture

hdr "A8a — a script block without the \"scripts\" experiment"
sub "terramate list"
terramate list 2>&1; rc $?
sub "terramate script run deploy"
terramate script run --quiet deploy 2>&1; rc $?

sed -i 's/\["outputs-sharing"\]/["outputs-sharing", "scripts"]/' terramate.tm.hcl
git -c user.email=poc@invalid -c user.name=poc commit -qam scripts
sub "same, with experiments = [\"outputs-sharing\", \"scripts\"]"
terramate script run --quiet deploy 2>&1; rc $?

hdr "A8b — experimental eval: is terramate.stack.after exposed?"
terramate run --quiet -- terramate experimental eval \
  'tm_jsonencode({id = terramate.stack.id, after = terramate.stack.after})' 2>&1; rc $?
sub "without after"
terramate run --quiet -- terramate experimental eval \
  'tm_jsonencode({id = terramate.stack.id, tags = terramate.stack.tags})' 2>&1; rc $?

hdr "A8c — debug show metadata carries after"
terramate debug show metadata 2>&1 | grep -E '^stack|stack\.(id|tags|after)='; rc $?

hdr "A8d — output.value is copied verbatim into the generated code"
mkdir -p n
printf 'globals {\n  project_id = "mock-project"\n}\n' > n/globals.tm.hcl
cat >> terramate.tm.hcl <<'HCL'
sharing_backend "tofu" {
  type     = terraform
  command  = ["tofu", "output", "-json"]
  filename = "_sharing_generated.tf"
}
HCL
cat > n/stack.tm.hcl <<'HCL'
stack { id = "n" }
output "project_id" {
  backend = "tofu"
  value   = global.project_id
}
HCL
git add -A && git -c user.email=poc@invalid -c user.name=poc commit -qm output
terramate generate >/dev/null 2>&1; rc $?
cat n/_sharing_generated.tf

# ---------------------------------------------------------------- conftest
cd "$WORK/cf" || exit 1
cat > policy/composition.rego <<'REGO'
package archetype.composition
import rego.v1
deny contains msg if {
  some t in input.traits
  not t in data.registry.traits
  msg := sprintf("unknown trait %s", [t])
}
REGO
cat > policy/public_names.rego <<'REGO'
package terraform.public_names
import rego.v1
deny contains "environment name in a public name" if input.bad
REGO
printf 'traits:\n  - cloudsql\n  - cnpg\n' > registry/traits.yaml
echo '{"registry":{"traits":["cloudsql","cnpg"]}}' > registry/registry.json
echo '{"traits":["bogus"]}' > manifest.json
echo '{"bad":true}' > plan.json

hdr "A8e — G1 without --all-namespaces"
conftest test --no-color --policy policy/ --data registry/ manifest.json 2>&1; rc $?

hdr "A8f — --all-namespaces, but --data registry/ (YAML at the root of data)"
rm registry/registry.json
conftest test --no-color --all-namespaces --policy policy/ --data registry/ manifest.json 2>&1; rc $?
echo '{"registry":{"traits":["cloudsql","cnpg"]}}' > registry/registry.json

hdr "A8g — --all-namespaces and the bundle with top-level key registry"
conftest test --no-color --all-namespaces --policy policy/ --data registry/registry.json manifest.json 2>&1; rc $?

hdr "A8h — G3: --namespace terraform vs the exact package"
sub "--namespace terraform"
conftest test --no-color --policy policy/ --namespace terraform plan.json 2>&1; rc $?
sub "--namespace terraform.public_names"
conftest test --no-color --policy policy/ --namespace terraform.public_names plan.json 2>&1; rc $?
