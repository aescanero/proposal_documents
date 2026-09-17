import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archetypectl import cli
from archetypectl.enrich import Index, enrich_document, normalise_inventory, resolve_after_entry

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "repo")
INVENTORY = os.path.join(FIXTURE, "terramate-list.json")


def enrich_fixture():
    with open(INVENTORY, encoding="utf-8") as handle:
        document = json.load(handle)
    result, _errors = enrich_document(document, FIXTURE)
    return {stack["id"]: stack for stack in result["stacks"]}, result


class InventoryTest(unittest.TestCase):
    def test_object_array_and_ndjson_shapes_agree(self):
        entry = {"id": "a", "dir": "/a", "tags": []}
        for document in ({"stacks": [entry]}, [entry], [{"stack": entry}]):
            stacks, _extras = normalise_inventory(document)
            self.assertEqual(stacks, [entry])

    def test_unknown_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            normalise_inventory({"items": []})

    def test_envelope_keys_are_preserved(self):
        result, _ = enrich_document({"stacks": [], "version": "0.10.0"}, FIXTURE)
        self.assertEqual(result["version"], "0.10.0")
        self.assertEqual(result["stacks"], [])


class AfterResolutionTest(unittest.TestCase):
    def setUp(self):
        self.index = Index(
            [
                {"id": "gcp-demos-network", "dir": "/stacks/platforms/gcp/demos/network", "tags": ["gcp", "network"]},
                {"id": "gcp-demos-gke", "dir": "/stacks/platforms/gcp/demos/gke", "tags": ["gcp", "cluster"]},
                {"id": "aws-demos-eks", "dir": "/stacks/platforms/aws/demos/eks", "tags": ["aws", "cluster"]},
            ]
        )

    def test_absolute_path(self):
        self.assertEqual(
            resolve_after_entry("/stacks/platforms/gcp/demos/network", "/stacks/platforms/gcp/demos/gke", self.index),
            ["gcp-demos-network"],
        )

    def test_relative_path(self):
        self.assertEqual(
            resolve_after_entry("../network", "/stacks/platforms/gcp/demos/gke", self.index),
            ["gcp-demos-network"],
        )

    def test_directory_covers_nested_stacks(self):
        self.assertEqual(
            sorted(resolve_after_entry("/stacks/platforms/gcp", "/stacks/platforms/aws/demos/eks", self.index)),
            ["gcp-demos-gke", "gcp-demos-network"],
        )

    def test_tag_filter_and_is_an_intersection(self):
        self.assertEqual(resolve_after_entry("tag:gcp:cluster", "/x", self.index), ["gcp-demos-gke"])

    def test_tag_filter_comma_is_a_union(self):
        self.assertEqual(
            resolve_after_entry("tag:network,cluster", "/x", self.index),
            ["aws-demos-eks", "gcp-demos-gke", "gcp-demos-network"],
        )

    def test_unknown_tag_is_unresolved(self):
        self.assertIsNone(resolve_after_entry("tag:nope", "/x", self.index))

    def test_a_bare_stack_id_does_not_resolve(self):
        # Terramate reads a bare string as a path. Accepting it as an ID here
        # would certify an ordering Terramate never established — risk R2.
        self.assertIsNone(
            resolve_after_entry("gcp-demos-network", "/stacks/platforms/gcp/demos/gke", self.index)
        )


class EnrichTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stacks, cls.result = enrich_fixture()

    def test_inputs_come_from_imported_contracts(self):
        # The input blocks live in imports/contracts/, never in the stack dir.
        gke = self.stacks["gcp-demos-gke"]
        self.assertEqual(
            [(c["name"], c["output"], c["from_stack_id"]) for c in gke["consumes"]],
            [
                ("network_self_link", "network_self_link", "gcp-demos-network"),
                ("subnet_self_link", "subnet_self_link", "gcp-demos-network"),
            ],
        )
        self.assertTrue(all(c["resolved"] for c in gke["consumes"]))

    def test_outputs_become_produces(self):
        self.assertEqual(
            self.stacks["gcp-demos-network"]["produces"],
            ["network_self_link", "subnet_self_link", "project_id"],
        )
        self.assertEqual(self.stacks["gcp-demos-gke"]["produces"], ["cluster_endpoint", "cluster_ca"])

    def test_declared_after_path_becomes_an_id(self):
        self.assertEqual(self.stacks["gcp-demos-gke"]["after_ids"], ["gcp-demos-network"])
        self.assertEqual(self.stacks["gcp-demos-gke"]["after_unresolved"], [])

    def test_relative_after_path(self):
        self.assertEqual(self.stacks["aws-demos-eks"]["after_ids"], ["aws-demos-network"])

    def test_tag_filter_after(self):
        self.assertEqual(self.stacks["gcp-demos-edge"]["after_ids"], ["gcp-demos-gke"])

    def test_the_r2_case_is_visible(self):
        # gcp-demos-services consumes two outputs of gcp-demos-gke and declares
        # no ordering. This is the pair G1 denies on.
        services = self.stacks["gcp-demos-services"]
        self.assertEqual([c["from_stack_id"] for c in services["consumes"]], ["gcp-demos-gke"] * 2)
        self.assertEqual(services["after_ids"], [])

    def test_inherited_globals_and_interpolation(self):
        # binding.tm.hcl is in the parent directory; from_stack_id is built by
        # interpolation rather than a bare reference.
        app = self.stacks["gcp-demos-alpha-app"]
        self.assertEqual([c["from_stack_id"] for c in app["consumes"]], ["gcp-demos-gke"])
        self.assertEqual(app["consumes"][0]["output"], "cluster_endpoint")
        self.assertEqual(app["after_ids"], ["gcp-demos-gke"])
        self.assertEqual(app["capability"], "app")

    def test_unresolvable_from_stack_id_is_reported_not_guessed(self):
        edge = self.stacks["gcp-demos-edge"]
        consume = edge["consumes"][0]
        self.assertIsNone(consume["from_stack_id"])
        self.assertFalse(consume["resolved"])
        self.assertIn("tm_try", consume["from_stack_id_expr"])
        self.assertEqual(self.result["enrich"]["unresolved_inputs"], 1)
        self.assertTrue(any("from_stack_id" in e for e in self.result["enrich"]["errors"]))

    def test_producer_only_stack_consumes_nothing(self):
        self.assertEqual(self.stacks["aws-demos-network"]["consumes"], [])
        self.assertEqual(self.stacks["aws-demos-network"]["after_ids"], [])

    def test_every_stack_carries_the_policy_fields(self):
        for stack in self.result["stacks"]:
            for field in ("consumes", "produces", "after_ids", "after_unresolved", "implicit_after_ids"):
                self.assertIn(field, stack, stack["id"])

    def test_output_is_deterministic(self):
        again, _ = enrich_fixture()
        self.assertEqual(json.dumps(self.stacks, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_missing_directory_is_an_error_not_a_pass(self):
        result, errors = enrich_document(
            {"stacks": [{"id": "ghost", "dir": "/stacks/nope", "tags": []}]}, FIXTURE
        )
        self.assertTrue(errors)
        self.assertEqual(result["stacks"][0]["consumes"], [])
        self.assertTrue(any("does not exist" in e for e in result["enrich"]["errors"]))


class CLITest(unittest.TestCase):
    def test_in_place_rewrite(self):
        workdir = tempfile.mkdtemp()
        try:
            target = os.path.join(workdir, "stacks-under-test.json")
            shutil.copyfile(INVENTORY, target)
            code = cli.main(["enrich", target, "--root", FIXTURE, "--quiet"])
            self.assertEqual(code, 0)
            with open(target, encoding="utf-8") as handle:
                document = json.load(handle)
            self.assertIn("consumes", document["stacks"][0])
        finally:
            shutil.rmtree(workdir)

    def test_strict_fails_on_an_unresolved_input(self):
        code = cli.main(["enrich", INVENTORY, "--root", FIXTURE, "-o", os.devnull, "--strict", "--quiet"])
        self.assertEqual(code, cli.EXIT_STRICT)

    def test_strict_passes_when_everything_resolves(self):
        workdir = tempfile.mkdtemp()
        try:
            source = os.path.join(workdir, "subset.json")
            with open(INVENTORY, encoding="utf-8") as handle:
                document = json.load(handle)
            document["stacks"] = [s for s in document["stacks"] if s["id"] != "gcp-demos-edge"]
            with open(source, "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            code = cli.main(["enrich", source, "--root", FIXTURE, "-o", os.devnull, "--strict", "--quiet"])
            self.assertEqual(code, 0)
        finally:
            shutil.rmtree(workdir)

    def test_bad_json_is_a_usage_error(self):
        workdir = tempfile.mkdtemp()
        try:
            source = os.path.join(workdir, "broken.json")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            self.assertEqual(
                cli.main(["enrich", source, "--root", FIXTURE, "--quiet"]), cli.EXIT_USAGE
            )
        finally:
            shutil.rmtree(workdir)


if __name__ == "__main__":
    unittest.main()
