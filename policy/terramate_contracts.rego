# G1 — structure and composition: outputs-sharing contract rules.
#
# Never share secrets through outputs sharing: shared values land in
# TF_VAR_* environment variables, which leak into logs and process
# trees (see CLAUDE.md, "Traps"). Producers must share a reference —
# a secret ID, an ARN, a key name — never the value itself.
package terramate.contracts

import rego.v1

secret_fragments := {"password", "private_key", "token", "credential", "secret_value"}

reference_suffixes := {"_id", "_arn", "_name", "_uri"}

# An output block must never export a secret value — only a reference.
deny contains msg if {
	some s in input.stacks
	some o in s.produces
	some frag in secret_fragments
	contains(o, frag)
	every suffix in reference_suffixes { not endswith(o, suffix) }
	msg := sprintf("stack %q exports %q — share a reference, not a value", [s.id, o])
}
