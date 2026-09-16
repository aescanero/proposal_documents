"""Tests for tools/registry-generate.

A gate that cannot fail is not a gate (risk R36), so the two properties the gate
rests on are tested directly: that `--check` detects drift and writes nothing,
and that regeneration touches the two enum arrays in the schema and nothing else.

    python -m unittest discover -s tools -t tools
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The tool has no .py extension — it is a command, not a module.
_spec = importlib.util.spec_from_loader(
    "registry_generate",
    importlib.machinery.SourceFileLoader("registry_generate", str(REPO_ROOT / "tools" / "registry-generate")),
)
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class SandboxTest(unittest.TestCase):
    """Each test runs against a throwaway copy of registry/ and schemas/."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(REPO_ROOT / "registry", self.root / "registry")
        shutil.copytree(REPO_ROOT / "schemas", self.root / "schemas")
        self.schema = self.root / "schemas" / "archetype-manifest.schema.json"

    def run_tool(self, *args: str) -> int:
        # The tool's diagnostics are deliberate; they are just noise in a test log.
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return rg.main(["--root", str(self.root), "-q", *args])

    def generate(self) -> None:
        self.assertEqual(self.run_tool(), 0)

    def enums(self) -> tuple[list[str], list[str]]:
        defs = json.loads(self.schema.read_text(encoding="utf-8"))["$defs"]
        return defs["capability"]["enum"], defs["trait"]["enum"]


class TestGeneration(SandboxTest):
    def test_enums_are_the_registry_sorted(self) -> None:
        self.generate()
        registry = rg.read_registry(self.root / "registry")
        capabilities, traits = self.enums()
        self.assertEqual(capabilities, sorted(yaml_list(self.root, "capabilities.yaml", "capabilities")))
        self.assertEqual(traits, sorted(yaml_list(self.root, "traits.yaml", "traits")))
        self.assertEqual(capabilities, registry["capabilities"])
        self.assertEqual(traits, registry["traits"])

    def test_schema_stays_valid_json_and_keeps_everything_else(self) -> None:
        before = self.schema.read_text(encoding="utf-8")
        self.generate()
        after = self.schema.read_text(encoding="utf-8")
        # The committed schema is already current, so a no-op regeneration must
        # not rewrite a single byte — not the key order, not the — escapes,
        # not the absent trailing newline.
        self.assertEqual(before, after)
        json.loads(after)

    def test_only_the_enum_arrays_are_touched(self) -> None:
        original = self.schema.read_text(encoding="utf-8")
        tampered = original.replace(
            '"title": "Archetype Manifest"', '"title": "Archetype Manifest EDITED"'
        ).replace('        "waf"\n      ],', '        "waf",\n        "invented"\n      ],', 1)
        self.schema.write_text(tampered, encoding="utf-8")

        self.generate()
        result = self.schema.read_text(encoding="utf-8")

        capabilities, _ = self.enums()
        self.assertNotIn("invented", capabilities)          # the enum was restored
        self.assertIn('"Archetype Manifest EDITED"', result)  # the rest was not
        self.assertEqual(
            result, original.replace('"Archetype Manifest"', '"Archetype Manifest EDITED"')
        )

    def test_bundle_and_values_are_parseable_and_agree(self) -> None:
        self.generate()
        bundle = json.loads((self.root / "registry" / "registry.json").read_text(encoding="utf-8"))
        values = rg.yaml.safe_load(
            (self.root / "charts" / "policy-gatekeeper" / "values.registry.yaml").read_text(
                encoding="utf-8"
            )
        )["registry"]

        capabilities, traits = self.enums()
        for name, expected in (("capabilities", capabilities), ("traits", traits)):
            self.assertEqual(bundle[name], expected, name)
            self.assertEqual(values[name], expected, name)

        # Policies address the bundle as data.registry.<key> (§13.3).
        self.assertEqual(bundle["zone_names"], [z["name"] for z in bundle["zones"]])
        self.assertEqual(values["zones"], bundle["zone_names"])
        self.assertEqual(values["labels"], bundle["labels"])
        # purposes is normalised, so Rego need not test for the key.
        self.assertEqual([z for z in bundle["zones"] if z["name"] == "growth"][0]["purposes"], [])
        # Every label target carries both buckets, optional possibly empty.
        for target, buckets in bundle["labels"].items():
            self.assertEqual(sorted(buckets), ["optional", "required"], target)


class TestCheck(SandboxTest):
    def test_check_passes_when_current(self) -> None:
        self.generate()
        self.assertEqual(self.run_tool("--check"), 0)

    def test_check_detects_a_hand_edited_enum(self) -> None:
        self.generate()
        self.schema.write_text(
            self.schema.read_text(encoding="utf-8").replace(
                '        "waf"\n      ],', '        "waf",\n        "invented"\n      ],', 1
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.run_tool("--check"), 1)

    def test_check_detects_a_new_capability_in_the_source(self) -> None:
        self.generate()
        capabilities = self.root / "registry" / "capabilities.yaml"
        capabilities.write_text(
            capabilities.read_text(encoding="utf-8") + "  - probe\n", encoding="utf-8"
        )
        self.assertEqual(self.run_tool("--check"), 1)

    def test_check_fails_when_an_artefact_is_missing(self) -> None:
        self.assertEqual(self.run_tool("--check"), 1)  # nothing generated yet

    def test_check_writes_nothing(self) -> None:
        self.generate()
        capabilities = self.root / "registry" / "capabilities.yaml"
        capabilities.write_text(
            capabilities.read_text(encoding="utf-8") + "  - probe\n", encoding="utf-8"
        )
        before = snapshot(self.root)
        self.assertEqual(self.run_tool("--check"), 1)
        self.assertEqual(snapshot(self.root), before)


class TestSourceValidation(SandboxTest):
    """A bad source is exit 2, distinct from drift's exit 1."""

    def append(self, name: str, text: str) -> None:
        path = self.root / "registry" / name
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_duplicate_entry(self) -> None:
        self.append("traits.yaml", "  - gpu\n")
        self.assertEqual(self.run_tool("--check"), 2)

    def test_non_slug_entry(self) -> None:
        self.append("traits.yaml", "  - Bad_Trait\n")
        self.assertEqual(self.run_tool("--check"), 2)

    def test_malformed_yaml(self) -> None:
        self.append("traits.yaml", "  - [unclosed\n")
        self.assertEqual(self.run_tool("--check"), 2)

    def test_zone_without_a_fraction(self) -> None:
        self.append("zones.yaml", "\n  - name: rogue\n    allocatable: true\n    purposes: [nodes]\n")
        self.assertEqual(self.run_tool("--check"), 2)

    def test_allocatable_zone_without_purposes(self) -> None:
        self.append("zones.yaml", "\n  - name: rogue\n    fraction: /20\n    allocatable: true\n")
        self.assertEqual(self.run_tool("--check"), 2)

    def test_label_in_both_buckets(self) -> None:
        self.append("labels.yaml", "    optional:\n      - archetype\n")
        self.assertEqual(self.run_tool("--check"), 2)

    def test_missing_source_file(self) -> None:
        (self.root / "registry" / "zones.yaml").unlink()
        self.assertEqual(self.run_tool("--check"), 2)


class TestScanner(unittest.TestCase):
    """The JSON scanner is what keeps the rest of the schema intact."""

    SAMPLE = (
        '{\n  "a": {"nested": [1, 2, {"x": "}"}], "enum": ["one"]},\n'
        '  "b": "escaped \\" brace }",\n  "c": [true, null, -1.5e3]\n}'
    )

    def test_finds_a_nested_value(self) -> None:
        start, end = rg.find_span(self.SAMPLE, ["a", "enum"])
        self.assertEqual(self.SAMPLE[start:end], '["one"]')

    def test_is_not_fooled_by_braces_inside_strings(self) -> None:
        start, end = rg.find_span(self.SAMPLE, ["b"])
        self.assertEqual(json.loads(self.SAMPLE[start:end]), 'escaped " brace }')
        start, end = rg.find_span(self.SAMPLE, ["c"])
        self.assertEqual(json.loads(self.SAMPLE[start:end]), [True, None, -1500.0])

    def test_unknown_key_is_a_source_error(self) -> None:
        with self.assertRaises(rg.SourceError):
            rg.find_span(self.SAMPLE, ["a", "missing"])

    def test_render_enum_follows_the_surrounding_indentation(self) -> None:
        text = '{\n    "enum": ["old"]\n}'
        start, _ = rg.find_span(text, ["enum"])
        self.assertEqual(rg._render_enum(["x", "y"], text, start), '[\n      "x",\n      "y"\n    ]')
        self.assertEqual(rg._render_enum([], text, start), "[]")


class TestCommittedArtefacts(unittest.TestCase):
    def test_the_repository_is_current(self) -> None:
        """What the CI gate asserts, asserted here too."""
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rg.main(["--check", "-q"]), 0)


def yaml_list(root: Path, filename: str, key: str) -> list[str]:
    return rg.yaml.safe_load((root / "registry" / filename).read_text(encoding="utf-8"))[key]


if __name__ == "__main__":
    unittest.main()
