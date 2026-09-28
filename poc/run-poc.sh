#!/usr/bin/env bash
#
# Phase 0 PoC harness — validates the assumptions listed in CLAUDE.md
# ("Where to start") against a pinned Terramate version.
#
# Terramate derives its project root from the git root, and `required_version`
# / `config.experiments` may only be declared there. Running this PoC in place
# inside proposal_documents therefore fails with
#   "attribute terramate.required_version can only be declared at the project
#    root directory"
# This script copies the tree to a scratch directory *outside* any git
# repository, where poc/ itself becomes the project root, and runs there.
#
# Usage:  ./run-poc.sh [workdir]
# Output: a transcript on stdout. RESULTS.md quotes it verbatim.

set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${1:-${TMPDIR:-/tmp}/tm-phase0-poc}"

hdr() { printf '\n========== %s ==========\n' "$*"; }
sub() { printf '\n----- %s\n' "$*"; }

rm -rf "$WORK"
mkdir -p "$WORK"
# Sources only — never carry generated files or state into a fresh run.
( cd "$SRC" && tar -cf - \
    --exclude='.terraform*' --exclude='*.tfstate*' --exclude='_*.tf' \
    terramate.tm.hcl globals.tm.hcl stacks cases ) | ( cd "$WORK" && tar -xf - )

cd "$WORK" || exit 1

hdr "versions"
terramate version 2>&1 | head -1
tofu version 2>&1 | head -1

hdr "A0 — stacks discovered"
terramate list

# ---------------------------------------------------------------------------
hdr "A1 + A2 — terramate generate"
terramate generate

sub "A1 — consumer-inherited: from_stack_id = global.producer_id (global from parent dir)"
cat stacks/consumer-inherited/_sharing_generated.tf

sub "A2 — consumer-interpolated: from_stack_id = \"\${global.env}-producer\""
cat stacks/consumer-interpolated/_sharing_generated.tf

sub "producer side of the contract"
cat stacks/producer/_sharing_generated.tf

sub "G0 gate — re-running generate must report no change"
# NOTE: `terramate generate --check` does NOT exist in this CLI. The gate is
# --detailed-exit-code: 0 = nothing changed, 2 = changes were generated.
terramate generate --detailed-exit-code --quiet
echo "exit=$?  (0 = up to date, 2 = drift, 1 = error)"

# ---------------------------------------------------------------------------
hdr "A3 — stack.after: does it accept a globals-derived value?"
# CLAUDE.md warns this "fails silently". Verify the ORDER, never the exit code.
# Each failing fixture is probed alone in a scratch stack dir, because one
# unparseable stack aborts the whole configuration load.

for case in after-global-expr after-global-interp; do
  sub "A3 probe: cases/$case"
  mkdir -p stacks/_probe
  cp "cases/$case/stack.tm.hcl.fixture" stacks/_probe/stack.tm.hcl
  terramate experimental run-graph 2>&1 | head -6
  rm -rf stacks/_probe
done

sub "A3 probe: cases/no-after — an input with NO after (the real silent failure)"
mkdir -p stacks/_probe
cp cases/no-after/stack.tm.hcl.fixture    stacks/_probe/stack.tm.hcl
cp cases/no-after/contract.tm.hcl.fixture stacks/_probe/contract.tm.hcl
echo "# run-graph: look for an edge into 'A3 probe — input with no after'. There is none."
terramate experimental run-graph 2>&1
echo "# run-order: the probe may be scheduled before the producer it reads from."
terramate list --run-order 2>&1
echo "# and generate is perfectly happy with it:"
terramate generate --quiet 2>&1
echo "generate exit=$?"
rm -rf stacks/_probe
terramate generate --quiet >/dev/null 2>&1

sub "A3 baseline — run-graph with the forms actually used by the PoC stacks"
# consumer-inherited    uses after = ["/stacks/producer"]  (literal path)
# consumer-interpolated uses after = ["tag:producer"]      (tag fallback)
terramate experimental run-graph

sub "A3 baseline — terramate list --run-order (the definitive ordering)"
terramate list --run-order

sub "A3 baseline — order actually used by terramate run"
terramate run --quiet -- pwd

# ---------------------------------------------------------------------------
hdr "A4 — --mock-on-fail when the producer has NO state"
# The producer is deliberately NOT applied yet, so `tofu output -json` in the
# producer directory cannot succeed. The consumer must fall back to its mocks.

sub "A4a — preview path: --enable-sharing --mock-on-fail (expect success, mock values)"
terramate run --tags consumer --enable-sharing --mock-on-fail -- \
  tofu init -input=false -no-color >/dev/null 2>&1
terramate run --tags consumer --enable-sharing --mock-on-fail -- \
  tofu apply -auto-approve -input=false -no-color 2>&1 | grep -Ev '^$' | tail -25
echo "exit=${PIPESTATUS[0]}"

sub "A4a — consumer outputs (expect mock- values)"
for d in stacks/consumer-inherited stacks/consumer-interpolated; do
  echo "# $d"
  ( cd "$d" && tofu output -json 2>&1 )
done

sub "A4b — deploy path: --enable-sharing WITHOUT --mock-on-fail, still no producer state (must FAIL)"
rm -rf stacks/consumer-*/terraform.tfstate* stacks/consumer-*/.terraform*
terramate run --tags consumer --enable-sharing -- \
  tofu init -input=false -no-color >/dev/null 2>&1
terramate run --tags consumer --enable-sharing -- \
  tofu apply -auto-approve -input=false -no-color 2>&1 | tail -10
echo "exit=${PIPESTATUS[0]}"

# ---------------------------------------------------------------------------
hdr "A5 — end-to-end: apply producer, then consumers with no mocks"
terramate run --tags producer --enable-sharing -- \
  tofu init -input=false -no-color >/dev/null 2>&1
terramate run --tags producer --enable-sharing -- \
  tofu apply -auto-approve -input=false -no-color 2>&1 | tail -12

rm -rf stacks/consumer-*/terraform.tfstate* stacks/consumer-*/.terraform*
terramate run --tags consumer --enable-sharing -- \
  tofu init -input=false -no-color >/dev/null 2>&1
terramate run --tags consumer --enable-sharing -- \
  tofu apply -auto-approve -input=false -no-color 2>&1 | grep -Ev '^$' | tail -25
echo "exit=${PIPESTATUS[0]}"

sub "A5 — consumer outputs (expect REAL producer values, no mock- prefix)"
for d in stacks/consumer-inherited stacks/consumer-interpolated; do
  echo "# $d"
  ( cd "$d" && tofu output -json 2>&1 )
done

hdr "done — workdir $WORK"
