import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archetypectl import hcl
from archetypectl.hcl import UNRESOLVED


class TokenizerTest(unittest.TestCase):
    def test_comments_and_blocks(self):
        body = hcl.parse(
            """
            # a hash comment
            // a slash comment
            /* a block
               comment */
            stack {
              id = "gcp-demos-gke"
            }
            """
        )
        self.assertEqual(len(body.blocks), 1)
        self.assertEqual(hcl.evaluate(body.blocks[0].body.attributes["id"]), "gcp-demos-gke")

    def test_single_line_block_with_two_attributes(self):
        # The contract files are written this way; an attribute reader that
        # stopped only at newlines would swallow 'value' into 'backend'.
        body = hcl.parse('output "x" { backend = "tofu"  value = module.y.z }')
        block = body.blocks[0]
        self.assertEqual(block.labels, ["x"])
        self.assertEqual(hcl.evaluate(block.body.attributes["backend"]), "tofu")
        self.assertEqual(block.body.attributes["value"].raw, "module.y.z")

    def test_heredoc(self):
        body = hcl.parse('a = <<-EOT\n  hello\nEOT\nb = 1\n')
        self.assertEqual(hcl.evaluate(body.attributes["a"]), "  hello\n")
        self.assertEqual(hcl.evaluate(body.attributes["b"]), 1)

    def test_escaped_quote_in_string(self):
        body = hcl.parse('a = "say \\"hi\\""')
        self.assertEqual(hcl.evaluate(body.attributes["a"]), 'say "hi"')

    def test_unterminated_string_is_an_error(self):
        with self.assertRaises(hcl.HCLError):
            hcl.parse('a = "oops\n')


class EvaluateTest(unittest.TestCase):
    def scope(self):
        return {"global": {"cloud": "gcp", "env": "demos", "platform": {"cluster_stack_id": "gcp-demos-gke"}}}

    def test_literal_kinds(self):
        body = hcl.parse('s = "x"\nn = 3\nf = 1.5\nt = true\nl = ["a", "b"]\no = { a = 1, b = "c" }\n')
        self.assertEqual(hcl.evaluate(body.attributes["s"]), "x")
        self.assertEqual(hcl.evaluate(body.attributes["n"]), 3)
        self.assertEqual(hcl.evaluate(body.attributes["f"]), 1.5)
        self.assertIs(hcl.evaluate(body.attributes["t"]), True)
        self.assertEqual(hcl.evaluate(body.attributes["l"]), ["a", "b"])
        self.assertEqual(hcl.evaluate(body.attributes["o"]), {"a": 1, "b": "c"})

    def test_global_reference(self):
        body = hcl.parse("a = global.platform.cluster_stack_id")
        self.assertEqual(hcl.evaluate(body.attributes["a"], self.scope()), "gcp-demos-gke")

    def test_interpolation(self):
        body = hcl.parse('a = "${global.cloud}-${global.env}-gke"')
        self.assertEqual(hcl.evaluate(body.attributes["a"], self.scope()), "gcp-demos-gke")

    def test_unknown_global_is_unresolved_not_empty(self):
        # The whole point: never invent a value for an expression we cannot read.
        body = hcl.parse('a = global.platform.missing\nb = "${global.nope}-gke"')
        self.assertIs(hcl.evaluate(body.attributes["a"], self.scope()), UNRESOLVED)
        self.assertIs(hcl.evaluate(body.attributes["b"], self.scope()), UNRESOLVED)

    def test_function_call_is_unresolved(self):
        body = hcl.parse('a = tm_try(global.x, "fallback")')
        self.assertIs(hcl.evaluate(body.attributes["a"], self.scope()), UNRESOLVED)

    def test_traversal_rejects_calls(self):
        body = hcl.parse("a = tm_upper(global.cloud)")
        self.assertIsNone(hcl.traversal(body.attributes["a"].tokens))


if __name__ == "__main__":
    unittest.main()
