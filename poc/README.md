# `poc/` — Phase 0 validation

The throwaway two-stack experiment that `CLAUDE.md` → "Where to start" gates
everything else on. It answers, against a pinned Terramate, whether the
late-binding model in `docs/terramate-outputs-sharing-architecture.md` actually
works.

**Read [`RESULTS.md`](RESULTS.md) for the answers.** Headline: the two
assumptions the `imports/contracts/` design rests on both hold; `stack.after`
with a global does not work and fails loudly rather than silently, which is a
convention change rather than a redesign.

## Running it

```bash
cd poc
./run-poc.sh                 # or: ./run-poc.sh /path/to/workdir
```

Needs `terramate` and `tofu` on `PATH`. No cloud credentials and no network:
the stacks are provider-free on purpose, so `tofu init` is offline and the
Terramate answers are not contaminated by cloud setup. Runs in seconds.

`run-poc.sh` copies the tree to a scratch directory **outside** any git
repository before running. That is not incidental — Terramate takes its project
root from the git root and rejects `required_version` / `config.experiments`
anywhere else, so this PoC cannot execute in place inside `proposal_documents`.
See RESULTS.md → "Why a harness".

## Layout

| Path | Purpose |
|---|---|
| `terramate.tm.hcl` | Root config — `required_version`, `experiments`, `sharing_backend` |
| `globals.tm.hcl` | The **parent-directory** globals. The point of assumption A1: no stack redefines these |
| `stacks/producer/` | `poc-producer`. Shares a string, a base64 string and a list |
| `stacks/consumer-inherited/` | A1 — `from_stack_id = global.producer_id`, ordered by literal path |
| `stacks/consumer-interpolated/` | A2 — `from_stack_id = "${global.env}-producer"`, ordered by `tag:producer` |
| `cases/` | Fixtures probed one at a time by the harness, see below |

## Why `cases/` is not `stacks/`

`cases/after-global-expr/` and `cases/after-global-interp/` **do not parse**, and
one unparseable stack aborts Terramate's entire configuration load — every
command, not just that stack. Leaving them under `stacks/` would block the whole
PoC. They are suffixed `.fixture`, copied into a scratch stack directory one at
a time, measured, and removed.

`cases/no-after/` parses fine. It is kept out of `stacks/` for a different
reason: it is the demonstration of risk R2 — a consumer with an `input` and no
ordering, which Terramate schedules **before** its producer without reporting
anything. Keeping it live would make the baseline run-graph misleading.

## Status

Assumptions A1–A5 are answered. A6 (cross-account state reads over OIDC) and A7
(private control plane reachable from the runner) still need a cloud sandbox and
are the remaining Phase 0 work.
