# Fixtures for policy/terramate_stacks.rego. A rule that never fires
# gives false confidence (risk R36) — every deny rule below has one
# fixture that must be denied and one that must pass clean.
package terramate.stacks

import rego.v1

# --- input <-> after ordering invariant (risk R2, top of the register) ---

test_consumer_without_after_is_denied if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-app",
		"capability": "app",
		"tags": ["instance:demos-alpha"],
		"consumes": [{"output": "cluster_endpoint", "from_stack_id": "aws-demos-eks"}],
		"after_ids": [],
	}]}

	count(violations) == 1
	`stack "aws-demos-app" consumes output "cluster_endpoint" from "aws-demos-eks" but does not declare it in 'after'` in violations
}

test_consumer_with_after_is_allowed if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-app",
		"capability": "app",
		"tags": ["instance:demos-alpha"],
		"consumes": [{"output": "cluster_endpoint", "from_stack_id": "aws-demos-eks"}],
		"after_ids": ["aws-demos-eks"],
	}]}

	count(violations) == 0
}

# --- stack id naming convention ---

test_malformed_stack_id_is_denied if {
	violations := deny with input as {"stacks": [{
		"id": "AWS_demos_eks",
		"capability": "cluster",
		"tags": [],
		"consumes": [],
		"after_ids": [],
	}]}

	count(violations) == 1
	`stack id "AWS_demos_eks" does not follow <cloud>-<env>-<capability>` in violations
}

test_wellformed_stack_id_is_allowed if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-eks",
		"capability": "cluster",
		"tags": [],
		"consumes": [],
		"after_ids": [],
	}]}

	count(violations) == 0
}

# --- instance: tag on application stacks ---

test_app_stack_without_instance_tag_is_denied if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-app",
		"capability": "app",
		"tags": ["env:demos"],
		"consumes": [],
		"after_ids": [],
	}]}

	count(violations) == 1
	`application stack "aws-demos-app" has no instance: tag` in violations
}

test_app_stack_with_instance_tag_is_allowed if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-app",
		"capability": "app",
		"tags": ["instance:demos-alpha"],
		"consumes": [],
		"after_ids": [],
	}]}

	count(violations) == 0
}
