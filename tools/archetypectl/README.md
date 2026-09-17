# archetypectl

Platform tooling for the archetype model. One subcommand so far: **`enrich`**,
roadmap phase 2c.2 of `docs/terramate-outputs-sharing-architecture.md` §16.

Stdlib-only Python ≥ 3.9. No dependencies, deliberately: it runs in the same CI
step as `terramate list` and installing a HCL library there buys nothing that a
few hundred lines of focused parsing does not.

---

## What `enrich` is for

`terramate list --json` gives the stack inventory. It does **not** expose
`input` blocks, and `stack.after` is a list of *directory paths or tag filters*
while the invariant to check is expressed in *stack IDs*. `enrich` closes both
gaps so the G1 policy is a comparison between two lists of IDs and nothing more.

```bash
terramate list --json > stacks.json
archetypectl enrich stacks.json           # adds consumes[], produces[], after_ids[]
conftest test --policy policy/ --data registry/ resolution.json stacks.json
```

**The extraction lives here and not in Rego on purpose.** HCL parsing, import
following and globals inheritance written in Rego would be unreadable and
untestable. Here they are ordinary code with fixtures, and what the policy
receives is flat JSON — portable, and testable against fixtures without a
repository or a Terramate binary.

---

## The invariant it exists to serve

Outputs sharing does **not** create execution order (architecture §4.5). Every
`input` block needs a matching `after`; an unresolved ordering applies a stale
value with **no error**. That is risk R2, the top risk in the register, and the
G1 rule that catches it reads exactly the fields this tool emits:

```rego
deny contains msg if {
    some stack in input.stacks
    some dep in stack.consumes
    not dep.from_stack_id in stack.after_ids
    msg := sprintf("stack %q consumes output %q from %q but does not declare it in 'after'",
                   [stack.id, dep.output, dep.from_stack_id])
}
```

`tests/test_g1_contract.py` re-states that rule in Python and runs it over the
fixture repository, so a renamed field fails a test rather than quietly
stopping the gate from firing (R36).

---

## Output

Each entry of `stacks[]` keeps every key `terramate list --json` produced and
gains:

| Field | Type | Meaning |
|---|---|---|
| `consumes[]` | object | One entry per `input` block reaching the stack |
| `consumes[].name` | string | The `input` label — the generated `var.<name>` |
| `consumes[].output` | string | The **producer's** output name, read from `value = outputs.<name>.value`; falls back to the label |
| `consumes[].from_stack_id` | string \| null | The producer's stack ID, or `null` when the expression could not be evaluated |
| `consumes[].from_stack_id_expr` | string | The raw expression, always — so an unresolved case is diagnosable |
| `consumes[].resolved` | bool | False when `from_stack_id` is `null` |
| `produces[]` | string[] | Labels of the stack's `output` blocks, in declaration order |
| `after_ids[]` | string[] | Stack IDs that `stack.after` resolves to, sorted |
| `after_unresolved[]` | string[] | `after` entries that mapped to no stack |
| `implicit_after_ids[]` | string[] | Ancestor stacks, which Terramate orders first by nesting. **Not** merged into `after_ids` — see below |
| `capability` | string | From `global.capability`, when it resolves and the inventory did not already carry it |

The envelope is always the object form `{"stacks": [...]}`, because the policy
reads `input.stacks`; a bare array or NDJSON input is normalised to it. Other
top-level keys are preserved. A top-level `enrich` object carries counts and
the errors, so a policy can also fail closed on a partial extraction.

> `produces[]`, `capability` and `implicit_after_ids[]` are beyond the two
> fields the subcommand was specified to emit. They come from the same scan of
> the same files, and without the first two the `terramate.contracts` and
> stack-tagging rules of §13.3 can never fire.

---

## What it reads, and why that is more than the stack directory

| Source | Why |
|---|---|
| `*.tm.hcl` / `*.tm` in the stack directory | `stack`, and any locally declared `input`/`output` |
| Every file those `import` | **Contracts are imported, not local.** The `input` blocks live in `imports/contracts/`. An enricher reading only the stack directory would find none, report every stack as consuming nothing, and pass every repository |
| `globals` from the project root down to the stack directory | `from_stack_id = global.platform.network_stack_id` resolves against inherited globals — including the `binding.tm.hcl` the resolver writes in the instance directory above the stack |

Expression forms handled for `from_stack_id`: a literal string, a traversal
(`global.platform.cluster_stack_id`), and interpolation
(`"${global.cloud}-${global.env}-gke"`) — the three variants §4.4 flags for
confirmation in the PoC.

`after` entry forms: a project-absolute path (`/stacks/platforms/gcp/demos/network`),
a relative path (`../network`), a directory containing stacks (all of them), and
Terramate's tag filters (`tag:gcp:cluster` is AND, `tag:network,cluster` is OR).

---

## It never guesses

An expression it cannot evaluate yields `from_stack_id: null` and an entry in
`enrich.errors` — not an empty string, not a plausible-looking ID. The G1 rule
then denies the stack anyway, because `null` is not in any `after_ids`. Fail
closed: a gate checking a value the tool invented is worse than no gate.

The same reasoning drives two smaller decisions:

- **A bare stack ID in `after` does not resolve.** Terramate reads a bare string
  as a path, so treating it as an ID would certify an ordering Terramate never
  established — precisely the silent failure R2 is about.
- **`implicit_after_ids` is a separate field.** Ancestor stacks really are
  ordered first, but folding them into `after_ids` would report an ordering the
  repository never declared. A policy may choose to accept them; the documented
  rule stays strict.

---

## Usage

```
archetypectl enrich [stacks.json] [-o OUT] [--root DIR] [--strict] [-q]
```

| Flag | Default | |
|---|---|---|
| `stacks` | `-` (stdin) | The `terramate list --json` output |
| `-o, --output` | rewrite the input file in place | `-` writes to stdout |
| `--root` | nearest `terramate.tm.hcl` or git root | Project root, for `/imports/...` and stack directories |
| `--strict` | off | Exit 2 if anything could not be extracted |
| `-q, --quiet` | off | Suppress the stderr summary |

| Exit | |
|---|---|
| 0 | Enriched; any problems are in `enrich.errors` and on stderr |
| 1 | Usage, unreadable input, input is not the expected JSON |
| 2 | `--strict` and the extraction was incomplete |

Advisory phase (2c.3) runs without `--strict`; turn it on with the blocking
gate (2c.4), once the false-positive rate has been measured.

---

## Running it and testing it

```bash
tools/archetypectl/bin/archetypectl enrich stacks.json      # no install needed
python3 -m unittest discover -s tools/archetypectl/tests -t tools/archetypectl
```

`tests/fixtures/repo/` is a miniature project — two clouds, an archetype
instance with an inherited `binding.tm.hcl`, contracts under `imports/` — that
covers, deliberately, both the passing and the failing case of each rule:

| Stack | Covers |
|---|---|
| `gcp-demos-network` | Producer only; `output` blocks become `produces[]` |
| `gcp-demos-gke` | Correct consumer: absolute-path `after`, globals in the stack |
| `gcp-demos-services` | **The R2 case** — consumes two outputs, declares no `after` |
| `gcp-demos-edge` | `from_stack_id` that cannot be evaluated; tag-filter `after` |
| `aws-demos-eks` | Relative-path `after`, same contract file on a second cloud |
| `gcp-demos-alpha-app` | Globals inherited from `binding.tm.hcl` one directory up; interpolated `from_stack_id` |

`tests/fixtures/.tmskip` keeps Terramate out of the fixture tree, so these never
appear in a real `terramate list`.

---

## Known limits

- **Globals precedence is an approximation.** Deeper directories win, and within
  a directory an imported file is weaker than the file that imported it. Terramate's
  own evaluation is lazy and richer; a global computed by `tm_*` functions,
  `tm_ternary` or a `let` resolves to nothing here and is reported as unresolved
  rather than guessed.
- **`generate_hcl` is not executed.** An `input` block emitted by a generator
  rather than written in a contract file is invisible. Contracts are hand-written
  by convention (§4.4), so this holds today; if that changes, run `enrich` after
  `terramate generate` and teach it to read the generated files.
- **The HCL reader is a subset**, not an implementation. It reads blocks, labels,
  attributes and literal expressions. A file it cannot parse is an entry in
  `enrich.errors`, never a silently empty result.
