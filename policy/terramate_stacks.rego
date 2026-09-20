# G1 — structure and composition: stack-level invariants.
#
# The first rule replaces the shell lint that used to guard the
# input<->after ordering invariant. That invariant is risk R2, ranked
# #1 in risk-register.md: outputs sharing does not create execution
# order, so a consumer stack missing 'after' can silently apply a
# stale or missing value with no error.
#
# Input is `stacks.json` (`terramate list --json`) enriched with
# `consumes[]` and `after_ids[]` by `archetypectl enrich` — see
# docs/terramate-outputs-sharing-architecture.md §13.3 and §14.4.
package terramate.stacks

import rego.v1

# Every stack consuming an output must declare the producer in 'after'.
deny contains msg if {
	some stack in input.stacks
	some dep in stack.consumes
	not dep.from_stack_id in stack.after_ids
	msg := sprintf(
		"stack %q consumes output %q from %q but does not declare it in 'after'",
		[stack.id, dep.output, dep.from_stack_id])
}

# Stack IDs follow the naming convention: <cloud>-<env>-<capability>[-<instance>].
deny contains msg if {
	some s in input.stacks
	not regex.match(`^[a-z0-9]+-[a-z0-9-]+-[a-z0-9-]+$`, s.id)
	msg := sprintf("stack id %q does not follow <cloud>-<env>-<capability>", [s.id])
}

# Application stacks carry an instance tag, so tag-scoped destroy is safe.
deny contains msg if {
	some s in input.stacks
	s.capability == "app"
	count({t | some t in s.tags; startswith(t, "instance:")}) == 0
	msg := sprintf("application stack %q has no instance: tag", [s.id])
}
