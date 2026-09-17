"""The output contract with the G1 policy.

The rule in terramate-outputs-sharing-architecture.md §13.3 is:

    deny contains msg if {
        some stack in input.stacks
        some dep in stack.consumes
        not dep.from_stack_id in stack.after_ids
        ...
    }

conftest is not a dependency of this package, so the rule is re-stated here in
Python and run over the enriched fixture. If a field is renamed or a value
changes shape, this test fails before the gate silently stops firing (R36).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_enrich import enrich_fixture


def deny_ordering(document):
    return sorted(
        "stack %r consumes output %r from %r but does not declare it in 'after'"
        % (stack["id"], dep["output"], dep["from_stack_id"])
        for stack in document["stacks"]
        for dep in stack["consumes"]
        if dep["from_stack_id"] not in stack["after_ids"]
    )


class G1ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _stacks, cls.document = enrich_fixture()

    def test_the_documented_rule_reads_every_field_it_needs(self):
        for stack in self.document["stacks"]:
            self.assertIsInstance(stack["id"], str)
            self.assertIsInstance(stack["after_ids"], list)
            for dep in stack["consumes"]:
                self.assertEqual(set(dep) >= {"from_stack_id", "output"}, True)

    def test_the_rule_denies_exactly_the_two_known_bad_pairs(self):
        denials = deny_ordering(self.document)
        self.assertEqual(
            denials,
            [
                "stack 'gcp-demos-edge' consumes output 'backend_service_id' from None "
                "but does not declare it in 'after'",
                "stack 'gcp-demos-services' consumes output 'cluster_ca' from "
                "'gcp-demos-gke' but does not declare it in 'after'",
                "stack 'gcp-demos-services' consumes output 'cluster_endpoint' from "
                "'gcp-demos-gke' but does not declare it in 'after'",
            ],
        )

    def test_correct_stacks_produce_no_denial(self):
        # An enricher that failed to follow imports would report no consumes at
        # all and this test would still pass — hence test_the_rule_denies_*.
        denials = deny_ordering(
            {"stacks": [s for s in self.document["stacks"] if s["id"] in ("gcp-demos-gke", "aws-demos-eks", "gcp-demos-alpha-app")]}
        )
        self.assertEqual(denials, [])

    def test_the_fixture_is_valid_json_for_conftest(self):
        json.dumps(self.document)


if __name__ == "__main__":
    unittest.main()
