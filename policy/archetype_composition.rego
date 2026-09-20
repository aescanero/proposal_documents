# G1 — structure and composition: archetype manifest rules.
#
# Input is a single archetype manifest.yaml (kind: Archetype).
# `data.registry.traits` is loaded from registry/traits.yaml via
# `conftest --data registry/` — the registry is the single source of
# truth for the trait vocabulary (see CLAUDE.md, "The registry is
# load-bearing"), so an unregistered trait is a policy violation, not
# a silent no-op.
package archetype.composition

import rego.v1

# Demo archetypes are leaves with a mandatory expiry.
deny contains msg if {
	input.metadata.kind == "demo"
	count(input.provides) > 0
	msg := "demo archetypes must not publish capabilities"
}

deny contains msg if {
	input.metadata.kind == "demo"
	not input.metadata.expiresOn
	msg := "demo archetypes must set metadata.expiresOn"
}

deny contains msg if {
	input.metadata.kind == "demo"
	time.parse_rfc3339_ns(sprintf("%sT00:00:00Z", [input.metadata.expiresOn])) < time.now_ns()
	msg := sprintf("expiresOn %q is in the past", [input.metadata.expiresOn])
}

# Traits must exist in the registry — a typo that matches nothing is worse than no check.
deny contains msg if {
	some p in input.provides
	some t in p.traits
	not t in data.registry.traits
	msg := sprintf("unregistered trait %q in provides", [t])
}
