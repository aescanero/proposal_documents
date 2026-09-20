# Fixtures for policy/terramate_contracts.rego.
package terramate.contracts

import rego.v1

test_secret_value_output_is_denied if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-rds",
		"produces": ["db_password", "cluster_endpoint"],
	}]}

	count(violations) == 1
	`stack "aws-demos-rds" exports "db_password" — share a reference, not a value` in violations
}

test_secret_reference_output_is_allowed if {
	violations := deny with input as {"stacks": [{
		"id": "aws-demos-rds",
		"produces": ["db_credential_arn", "cluster_endpoint"],
	}]}

	count(violations) == 0
}
