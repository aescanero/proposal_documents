# Phase 0 PoC — results

Validates the assumptions listed in `CLAUDE.md` → "Where to start", against a
pinned toolchain. Every transcript below is real output from `./run-poc.sh`,
not a reconstruction.

| | |
|---|---|
| **Terramate** | `0.16.0` |
| **OpenTofu** | `v1.10.6` |
| **Date** | 2026-09-16 |
| **Harness** | `./run-poc.sh` (see [Why a harness](#why-a-harness-and-not-just-terramate-generate)) |

---

## Scorecard

| # | Assumption | Verdict |
|---|---|---|
| A1 | `from_stack_id` resolves a global **inherited from a parent directory** | ☑ **Confirmed** |
| A2 | `from_stack_id` accepts **interpolation** (`"${global.env}-producer"`) | ☑ **Confirmed** |
| A3 | `stack.after` accepts a globals-derived path | ☒ **Refuted — but it fails LOUDLY, not silently** |
| A3b | Tag filters work as the ordering fallback | ☑ **Confirmed** |
| A4 | `--mock-on-fail` behaves as documented when the producer has no state | ☑ **Confirmed** |
| A5 | End-to-end: real values flow producer → consumer once applied | ☑ **Confirmed** |
| A6 | Cross-project / cross-account state reads with OIDC roles | ☐ **Not tested** — needs cloud credentials |
| A7 | Private control plane reachable from the chosen runner | ☐ **Not tested** — needs cloud infrastructure |

**Net effect on the architecture: the late-binding model works.** A1 and A2 are
the two that the whole `imports/contracts/` design rests on, and both hold. A3
does not hold, but its failure mode is the opposite of what was feared, and the
documented fallback works — so the cost is a one-line convention change, not a
redesign.

---

## What the PoC contains

Three stacks and three fixtures, deliberately provider-free — locals and
outputs only, so `tofu init` needs no network and no credentials and the
Terramate answers are not contaminated by cloud setup.

```
poc/
  terramate.tm.hcl                  root config: required_version, experiments, sharing_backend
  globals.tm.hcl                    PARENT globals: env, producer_id, producer_path
  stacks/
    producer/                       id poc-producer, tags [poc, producer]
    consumer-inherited/             A1 — from_stack_id = global.producer_id
    consumer-interpolated/          A2 — from_stack_id = "${global.env}-producer"
  cases/                            fixtures probed one at a time, see A3
    after-global-expr/              after = [global.producer_path]
    after-global-interp/            after = ["${global.producer_path}"]
    no-after/                       an input with no ordering at all
```

The producer shares three values chosen to exercise the mock type-correctness
trap: a plain string, a base64 string, and a list.

---

## A1 — inherited global in `from_stack_id` ☑

`global.producer_id` is defined **only** in `/globals.tm.hcl`, never in the stack
directory. `stacks/consumer-inherited/contract.tm.hcl`:

```hcl
input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = global.producer_id
  value         = outputs.cluster_endpoint.value
  mock          = "https://mock-endpoint.example.invalid"
}
```

`terramate generate`:

```
Code generation report

Successes:

- /stacks/consumer-inherited
	[+] _main.tf
	[+] _observed.tf
	[+] _sharing_generated.tf

- /stacks/consumer-interpolated
	[+] _main.tf
	[+] _observed.tf
	[+] _sharing_generated.tf

- /stacks/producer
	[+] _main.tf
	[+] _sharing_generated.tf
```

Generation alone does not prove binding — the generated file is only variable
declarations:

```hcl
// stacks/consumer-inherited/_sharing_generated.tf
// TERRAMATE: GENERATED AUTOMATICALLY DO NOT EDIT

variable "cluster_endpoint" {
  type = any
}
variable "cluster_ca_data" {
  type = any
}
variable "pod_ranges" {
  type = any
}
```

The binding is proven by A5 below, where the real producer value arrives.

---

## A2 — interpolation in `from_stack_id` ☑

```hcl
input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = "${global.env}-producer"   # global.env = "poc"
  value         = outputs.cluster_endpoint.value
  mock          = "https://mock-endpoint.example.invalid"
}
```

Generates and resolves identically to A1. To prove the string is genuinely
rendered rather than ignored, the PoC was re-run with the id pointed at a
non-existent producer (`"${global.env}-does-not-exist"`):

```
Error: one or more commands failed
> Stack /stacks/consumer-interpolated needs output from stack ID "poc-does-not-exist" but it cannot be found
```

The error names **`poc-does-not-exist`**, so `global.env` was interpolated. A2
holds.

> **Bonus finding.** `--mock-on-fail` does **not** mask a missing producer
> *stack* — the error above was produced *with* `--mock-on-fail` set. Mocks
> cover a missing output *value*, not a broken `from_stack_id`. A typo in a
> contract is therefore caught in PR preview, not at deploy. That is better
> than assumed and worth relying on.

---

## A3 — `stack.after` with a globals-derived path ☒

**This is the one that changes a decision, so it is reported in full.**

`CLAUDE.md` predicts: *"it fails **silently** — an unresolved expression leaves
the ordering empty rather than raising an error."* That prediction is **wrong
for 0.16.0**. Globals are not in scope in the `stack` block at all, and
Terramate aborts the entire configuration load:

```
----- A3 probe: cases/after-global-expr
Error: unable to parse configuration
> …/stacks/_probe/stack.tm.hcl:14,12-18: terramate schema error: … failed to evaluate "after" attribute: eval expression: There is no variable named "global"

----- A3 probe: cases/after-global-interp
Error: unable to parse configuration
> …/stacks/_probe/stack.tm.hcl:12,15-21: terramate schema error: … failed to evaluate "after" attribute: eval expression: There is no variable named "global"
```

Interpolation does not help either — note the second probe. This is a hard stop
on **every** command (`list`, `generate`, `run`, `run-graph`), not just the one
stack.

### What works instead

Measured with `terramate experimental run-graph`, not by absence of an error:

| Form | Edge created? |
|---|---|
| `after = [global.producer_path]` | **parse error** |
| `after = ["${global.producer_path}"]` | **parse error** |
| `after = ["/stacks/producer"]` | ☑ yes |
| `after = ["../producer"]` | ☑ yes |
| `after = ["tag:producer"]` | ☑ yes |

The PoC stacks use the literal path (`consumer-inherited`) and the tag filter
(`consumer-interpolated`). Both produce edges:

```
digraph  {
	n1[label="PoC consumer — inherited global in from_stack_id"];
	n3[label="PoC consumer — interpolated from_stack_id + tag ordering"];
	n2[label="PoC producer"];
	n2->n1;
	n2->n3;
}
```

```
----- A3 baseline — terramate list --run-order (the definitive ordering)
stacks/producer
stacks/consumer-inherited
stacks/consumer-interpolated
```

```
----- A3 baseline — order actually used by terramate run
…/stacks/producer
…/stacks/consumer-inherited
…/stacks/consumer-interpolated
```

### The silent failure is real — it is just a different one

Since a globals-derived `after` cannot parse, the ordering hazard is not an
unresolved expression. It is an `after` that was simply **forgotten**.
`cases/no-after/` is a stack with a valid `input` reading from the producer and
no ordering at all. Terramate accepts it without complaint:

```
# run-graph: look for an edge into 'A3 probe — input with no after'. There is none.
digraph  {
	n1[label="A3 probe — input with no after"];
	n2[label="PoC consumer — inherited global in from_stack_id"];
	n4[label="PoC consumer — interpolated from_stack_id + tag ordering"];
	n3[label="PoC producer"];
	n3->n2;
	n3->n4;
}
# run-order: the probe may be scheduled before the producer it reads from.
stacks/_probe
stacks/producer
stacks/consumer-inherited
stacks/consumer-interpolated
# and generate is perfectly happy with it:
Code generation report

Successes:

- /stacks/_probe
	[+] _sharing_generated.tf

generate exit=0
```

**`stacks/_probe` is scheduled first — before the producer whose output it
reads — and nothing anywhere reports a problem.** That is risk R2, reproduced,
and it is exactly why the G1 conftest policy has to exist.

### Consequences

1. **The resolver must emit literal `after` values.** It cannot reference
   globals there. Since the resolver already writes `binding.tm.hcl`, it can
   equally write a literal path or tag into `stack.tm.hcl` — this is a codegen
   change, not a design change.
2. **Prefer `tag:` over paths.** Tags survive a stack being moved on disk;
   literal paths do not. `docs/…-architecture.md` §4.5 already prefers tags.
3. **R2 stays the top risk, and G1 is still mandatory.** The good news is only
   that an *unresolvable expression* can no longer be the cause.
4. **Amend `CLAUDE.md`.** The trap text ("Globals in `stack.after` remain an
   open question, and it fails silently") is now measured and wrong in its
   detail. Suggested replacement is in [Documentation corrections](#documentation-corrections).

---

## A4 — `--mock-on-fail` with no producer state ☑

The producer is deliberately never applied before this step, so
`tofu output -json` in the producer directory cannot succeed.

### A4a — preview path: `--enable-sharing --mock-on-fail`

```
Changes to Outputs:
  + observed_ca_decoded  = "mock-ca-bundle"
  + observed_endpoint    = "https://mock-endpoint.example.invalid"
  + observed_first_range = "10.255.0.0/24"
  + observed_range_count = 1

Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
exit=0
```

```json
// stacks/consumer-inherited — tofu output -json
{
  "observed_ca_decoded":  { "type": "string", "value": "mock-ca-bundle" },
  "observed_endpoint":    { "type": "string", "value": "https://mock-endpoint.example.invalid" },
  "observed_first_range": { "type": "string", "value": "10.255.0.0/24" },
  "observed_range_count": { "type": "number", "value": 1 }
}
```

Mocks are substituted, the apply succeeds, and `base64decode()` on the mocked CA
works — so the mock was type-correct.

### A4b — deploy path: `--enable-sharing`, no `--mock-on-fail`

Same state (producer still unapplied). Must fail, and does:

```
terramate: Entering stack in /stacks/consumer-inherited
Error: one or more commands failed
> eval expression: evaluating input value: This object does not have an attribute named "cluster_endpoint".
exit=1
```

This is the behaviour the two-named-`script`-blocks rule depends on. Confirmed.

### A4c — mocks are NOT type-checked, and the G0 gate cannot catch a bad one

`CLAUDE.md` warns that a wrong-typed mock "type-checks locally and explodes on
apply". Measured, and it is worse than that — a bad mock does not change any
generated file, so `terramate generate` has nothing to report:

**base64 field mocked as `"mock"`:**

```
-- terramate generate:
Nothing to do, generated code is up to date
generate exit=0
-- tofu apply with --mock-on-fail:
Error: Error in function call
  on _main.tf line 7, in locals:
   7:   decoded_ca  = base64decode(var.cluster_ca_data)
    │ while calling base64decode(str)
    │ var.cluster_ca_data is "mock"
```

**list field mocked as a string:**

```
Changes to Outputs:
  + observed_range_count = 13
…
Error: Invalid index
  on _main.tf line 8, in locals:
   8:   first_range = var.pod_ranges[0]
    │ var.pod_ranges is "10.255.0.0/24"
This value does not have any indices.
```

> **Read `observed_range_count = 13` carefully.** `length()` on the mocked
> string returned the *string length* and succeeded. Only the `[0]` index
> failed. A list mocked as a string can therefore flow through arithmetic,
> `count`, or a capacity check producing a plausible wrong number rather than
> an error. Mock type-correctness cannot be left to "the plan will catch it".

Since `terramate generate --detailed-exit-code` returns 0 for a bad mock, **the
G0 gate cannot cover this.** A conftest rule over `input` blocks is the only
place to catch it — recommend extending G1 to assert that every `mock` matches
the declared shape of its capability contract.

---

## A5 — end-to-end, real values ☑

Producer applied first, then consumers with no mocks in play:

```
# producer
Outputs:
cluster_ca_data = "cG9jLWNsdXN0ZXItY2EtYnVuZGxl"
cluster_endpoint = "https://poc-producer.example.invalid"
pod_ranges = [
  "10.10.0.0/24",
  "10.10.1.0/24",
]
```

```json
// stacks/consumer-inherited     (A1: bare inherited global)
{
  "observed_ca_decoded":  { "type": "string", "value": "poc-cluster-ca-bundle" },
  "observed_endpoint":    { "type": "string", "value": "https://poc-producer.example.invalid" },
  "observed_first_range": { "type": "string", "value": "10.10.0.0/24" },
  "observed_range_count": { "type": "number", "value": 2 }
}

// stacks/consumer-interpolated  (A2: "${global.env}-producer")
{
  "observed_endpoint":    { "type": "string", "value": "https://poc-producer.example.invalid" },
  "observed_first_range": { "type": "string", "value": "10.10.0.0/24" },
  "observed_range_count": { "type": "number", "value": 2 }
}
```

No `mock-` prefix anywhere, `range_count` is 2 not 1, and the decoded CA is the
producer's. **Both binding styles reached the same producer with real data.**
A1, A2 and A5 all hold.

---

## Not tested

| | Why |
|---|---|
| **A6** cross-project / cross-account state reads with OIDC roles | Needs real cloud accounts and an OIDC trust setup. Unblocked only by a cloud sandbox; this PoC uses local state on purpose. |
| **A7** private control plane reachable from the runner | Needs a real cluster and runner networking. |

Both remain open against `CLAUDE.md` → "Where to start". They are the remaining
Phase 0 work and neither is affected by the findings above.

---

## Documentation corrections

Measured discrepancies between the docs and Terramate 0.16.0. None is fatal;
all should be fixed before anyone builds on them.

| Where | Says | Actually |
|---|---|---|
| `CLAUDE.md` traps; `docs/…-architecture.md` §4.4 note | Globals in `stack.after` "fails **silently**" | Hard parse error, `There is no variable named "global"`. The silent failure is a **missing** `after`, not an unresolved one. |
| `CLAUDE.md:164`, `docs/platform-overview.md:51` | The G0 gate is `terramate generate --check` | **No such flag** — `Error: unknown flag --check`. Use `terramate generate --detailed-exit-code` (0 = up to date, 2 = drift, 1 = error). Note this says nothing about `registry-generate --check`, which is a tool this project has yet to write and may define as it likes. |
| `docs/…-architecture.md` §4.3 | `output.description` is "Emitted into the generated `output` block" | Not emitted. The generated block is `output "cluster_endpoint" { value = local.endpoint }` only. Descriptions survive as contract documentation in `imports/contracts/`, but do not reach `tofu output`. |
| — | — | `terramate experimental run-graph` labels nodes with `stack.name`, not `stack.id`. Use `terramate list --run-order` when you need ids. |

Suggested replacement for the `CLAUDE.md` trap paragraph:

> **Globals do not resolve in `stack.after` — it is a parse error, not a silent
> one** (measured, Terramate 0.16.0). The resolver must write literal values;
> prefer `after = ["tag:<capability>"]` over a path so a stack can move. The
> silent failure that remains is a *forgotten* `after`: a consumer with an
> `input` and no ordering generates cleanly and can be scheduled before its
> producer, with no error at any stage. That is R2, and G1 is what catches it.

---

## Why a harness and not just `terramate generate`

Terramate derives its project root from the **git root**, and `required_version`
and `config.experiments` may only be declared there:

```
terramate schema error: attribute terramate.required_version can only be
declared at the project root directory
Warning: root config found outside root dir: …/poc
```

So `poc/` cannot be run in place inside `proposal_documents`. `run-poc.sh`
copies the tree (sources only — no generated files, no state) to a scratch
directory outside any git repository, where `poc/` itself becomes the project
root.

This is worth knowing beyond the PoC: **a Terramate project is one git
repository with one root config.** Vendoring a second Terramate project into a
subdirectory of an existing one does not work, which constrains how the real
repository can be laid out.

### Reproducing

```bash
cd poc
./run-poc.sh                 # or: ./run-poc.sh /path/to/workdir
```

Requires `terramate` and `tofu` on `PATH`. No cloud credentials, no network
beyond the two binaries. Runs in a few seconds.
