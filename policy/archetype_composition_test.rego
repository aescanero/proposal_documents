# Fixtures for policy/archetype_composition.rego.
package archetype.composition

import rego.v1

# A demo archetype with every rule already satisfied: no provides, an
# expiry far enough in the future to stay valid. Reused as the "pass"
# fixture for the rules not under test in a given case.
valid_demo := {
	"metadata": {"kind": "demo", "expiresOn": "2099-12-31"},
	"provides": [],
}

# --- demo archetypes must not publish capabilities ---

test_demo_with_provides_is_denied if {
	fixture := {
		"metadata": {"kind": "demo", "expiresOn": "2099-12-31"},
		"provides": [{"capability": "database-platform", "traits": []}],
	}
	violations := deny with input as fixture

	count(violations) == 1
	"demo archetypes must not publish capabilities" in violations
}

test_demo_without_provides_is_allowed if {
	violations := deny with input as valid_demo
	count(violations) == 0
}

# --- demo archetypes must set metadata.expiresOn ---

test_demo_without_expiry_is_denied if {
	fixture := {"metadata": {"kind": "demo"}, "provides": []}
	violations := deny with input as fixture

	count(violations) == 1
	"demo archetypes must set metadata.expiresOn" in violations
}

test_demo_with_expiry_is_allowed if {
	violations := deny with input as valid_demo
	count(violations) == 0
}

# --- expiresOn must not be in the past ---

test_demo_with_past_expiry_is_denied if {
	fixture := {
		"metadata": {"kind": "demo", "expiresOn": "2000-01-01"},
		"provides": [],
	}
	violations := deny with input as fixture

	count(violations) == 1
	`expiresOn "2000-01-01" is in the past` in violations
}

test_demo_with_future_expiry_is_allowed if {
	violations := deny with input as valid_demo
	count(violations) == 0
}

# --- traits referenced in 'provides' must exist in the registry ---

test_unregistered_trait_is_denied if {
	fixture := {
		"metadata": {"kind": "catalog"},
		"provides": [{"capability": "database-platform", "traits": ["not-a-real-trait"]}],
	}
	violations := deny with input as fixture
		with data.registry.traits as ["managed-nodes", "irsa"]

	count(violations) == 1
	`unregistered trait "not-a-real-trait" in provides` in violations
}

test_registered_trait_is_allowed if {
	fixture := {
		"metadata": {"kind": "catalog"},
		"provides": [{"capability": "database-platform", "traits": ["irsa"]}],
	}
	violations := deny with input as fixture
		with data.registry.traits as ["managed-nodes", "irsa"]

	count(violations) == 0
}
