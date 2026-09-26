# CLAUDE.md

*[Español](CLAUDE.es.md)*

Context for Claude Code working in this repository. Read this before touching anything.

This file is the **decision log**. It records what was settled and why, so you do not re-litigate choices or guess at rationale. The reference documents in `docs/` are the specification; this file tells you which parts are settled, which are still open, and what the traps are.

---

## What this repository is

A multi-cloud infrastructure platform built on **Terramate CLI + OpenTofu**, with an archetype packaging model layered on top. Two halves:

| Half | Document | Answers |
|---|---|---|
| **Resolve** | `archetype-model.md` | What may be composed with what — manifests, capabilities, traits, pools, CMDB, resolution |
| **Generate** | `terramate-outputs-sharing-architecture.md` | How it is generated and applied — generators, outputs sharing, IAM, policy, CI/CD, per-cloud guides |

Plus `platform-overview.md` (diagram-led map, read first), `risk-register.md` (53 risks by domain, 52 active), `glossary.md` (every term, defined) and `developer-guide.md` (the application developer's half — branching, versioning, build, rollback). Each of these lives in **two languages**: `docs/en/<file>.md` and `docs/es/<file>.md`. Below, a bare `docs/<file>.md` reference means "that file, in whichever language you are reading" — both copies say the same thing, so the path is language-neutral by design.

**The seam between the halves is `binding.tm.hcl`.** The resolver writes globals; the generators consume them. Neither knows the other's internals.

---

## Bilingual documentation

Every document under `docs/` exists in **English** (`docs/en/`) and **Spanish** (`docs/es/`), as full, independently readable copies — not a machine-translated shadow of one "real" version. Structure, headings, tables, code blocks and section numbers match exactly between the two, so a section reference (`§9.4`, `AM §5.1`) resolves the same way in either language. What differs is only the prose.

| Kind of document | Written first in | Then translated into |
|---|---|---|
| Reference documents (`docs/en/*.md`, `docs/es/*.md` at the top level: `platform-overview.md`, `archetype-model.md`, `terramate-outputs-sharing-architecture.md`, `developer-guide.md`, `risk-register.md`, `glossary.md`) | **English** | Spanish |
| Design proposals (`docs/en/proposals/`, `docs/es/proposals/`) | **Spanish** | English |
| This file, the root `README.md`, and the small `registry/`, `schemas/`, `.github/workflows/` READMEs | **English** | Spanish (a `<name>.es.md` sibling, or a bilingual single file where the content is short enough — see the existing files for the pattern) |

Rules that follow from "kept in sync", not just "translated once":

- **A change to a reference document changes both copies in the same commit or the same pull request.** A PR that edits `docs/en/risk-register.md` without touching `docs/es/risk-register.md` is incomplete, not a follow-up for later — the two are one document with two renderings, and letting them drift is exactly the kind of silent divergence this repository's other gates (registry vs. schema, generator vs. Gatekeeper) exist to prevent.
- **Diagrams are part of the document, not an attachment.** A Mermaid source or a hand-built SVG with labels in one language needs its own rendered copy with labels in the other — never a screenshot of the other language's diagram relabelled, and never one language's diagram left to stand for both. `docs/es/proposals/sonarqube-qa/diagrams/20-bloques-presentacion.py` is the pattern for a hand-built SVG: the generator script travels with the language it renders.
- **Identifiers stay in English in both copies.** Capability names, trait names, stack IDs, HCL/YAML keys, `kind:` values, environment names — anything that is also a literal string somewhere in the registry, a schema, or generated code — is not translated, in either language. Only prose, table descriptions and comments are. This is why translating code blocks verbatim (not transliterating them) is correct, not an oversight.
- **A new document is not done until both languages exist.** Adding only `docs/en/foo.md` (or only the Spanish proposal) and deferring the other copy to "a follow-up" is the failure mode this section exists to name and forbid.

---

## Settled decisions — do not reopen without a reason

### Tooling

| Decision | Rationale |
|---|---|
| **Terramate CLI, not Terraform Stacks** | Stacks is HCP-only. Not in the OSS CLI, not in OpenTofu at all |
| **Terramate over Terragrunt** | Change detection at scale, native binary execution rather than a wrapper, generated code is real `.tf` that Checkov can scan without plan indirection |
| **OpenTofu, not Terraform** | Decided at the outset |
| **Outputs Sharing** (`sharing_backend`/`input`/`output`) | Accepted despite being **experimental**. Risk R1. Contracts are centralised in `imports/contracts/` so a breaking change is a bounded edit |
| **Gatekeeper, not Kyverno** | The team already writes Rego for conftest, so one policy language. Note: rules are **not** literally reusable between them — shared language and helper libraries only, because Gatekeeper's input is an `AdmissionReview`, not `resolution.json` |
| **Self-managed Gatekeeper on all three clouds** | Managed add-ons are mutually exclusive with it (AKS refuses the Azure Policy add-on if Gatekeeper v3 is present) and restrict custom templates. One version, one behaviour everywhere |
| **Envoy Gateway** for ingress | Gateway API reference implementation; native OIDC via `SecurityPolicy` |
| **conftest** for CI policy, not a server | Stateless, no OPA server to run |

### Architecture

| Decision | Rationale |
|---|---|
| **`from_stack_id` accepts an expression** | **This is an assumption taken as a design decision.** The entire late-binding model depends on it: one hand-written contract file per capability, referencing `global.platform.cluster_stack_id`. If it turns out to be literal-only, the resolver must generate a contract file per instance — more machinery, noisier PRs, but not a redesign |
| **One account/project/subscription per environment; hub and landing zone in their own** | The environment is the isolation boundary of the dedicated model (architecture §12.1), and cross-project state reads are already designed for (§11.5). On GCP the edge IP, Cloud Armor policy and certificate must share a project with the load balancer, so they are provided by the **environment**, not the landing zone. KMS, the image registry and CI federation stay in the landing zone, granted across projects. Settled with `qa` (`disasterproject-qa`) |
| **Each environment is a VPC/VNet**, a `/17` (or `/16` for production) from `10.0.0.0/8` | |
| **Environments: `prod`, `qa`, `dev`, `demos`, `ephemeral-*`** | Normalised naming. Older drafts used `shared-demo`/`pre`/`prd` — those names are dead |
| **`demos` is a shared environment** | Not ephemeral-per-demo. Kafka as a common bus argues for it |
| **Data is NOT shared in `demos`** | `database-platform` is deliberately **unbound** there. Ten demos get ten managed instances. Isolation, not cost, is the criterion |
| **64 pods per node** (platform default) | Assumes ≥32 GB nodes. Gives `/25` per node, 128 nodes in a `/18` pod half. **Immutable after cluster creation** |
| **Layer 2b for policy** | Admission control must precede everything it governs, including layer 3 services. Cluster-scoped, not a named service. Precedent: layer 1b for cloud monitoring |
| **No Gatekeeper mutation** | The generator emits labels; Gatekeeper validates them. One writer, one validator. Mutation would make changes invisible in Terraform diffs and split ownership of the label list |
| **East-west traffic resolves by DNS** | So addresses need not be reproducible across rebuilds. What IS required is **idempotency**: allocation key is `(pool, owner, purpose)` |
| **Firewall rules are written by whoever claims the range** | Prefer workload selectors (network tags, security group references) over CIDR for east-west |
| **Kafka is an archetype, not a component** | It deploys an operator and imposes a multi-tenant contract. Common bus, separated data |
| **Neo4j, MongoDB are components** | Dedicated instances with no contract to anyone else |

### Rule for archetype vs component

> **Archetype** — deploys an operator or shared service that others consume, and imposes a multi-tenant contract.
> **Component** — a dedicated instance inside the archetype that uses it, with no contract to anyone else.

The same technology can be both. `postgres-operator` (archetype, provides `database-platform`) versus `component/postgres` (dedicated instance). That is not an inconsistency.

---

## Still open — ask before assuming

1. **Is `max_pods_per_node` settable on Autopilot?** The default of 64 assumes it is.
2. **Shared VPC or separate VPCs on GCP?** Peering non-transitivity plus the same-VPC backend rule may force Shared VPC. Address plan unchanged either way. Risk R23.
   **Settled for `qa`: separate VPC.** `qa` is dedicated, so its edge load balancer lives in its own VPC next to the Envoy NEG and nothing routes through the hub; R23 does not arise. Still open for `demos` and any environment whose edge would sit in the hub. See `proposals/sonarqube-qa/README.md` §4.15.
3. **Kafka partition ceiling** on the intended broker count. The 4000 budget in the `demos` binding is a placeholder.
4. **Where does resolution run** — a CLI in the repo, or a reusable workflow? Determines whether the project office can validate a demo locally.
5. **How much Rego is genuinely shared** between conftest and `ConstraintTemplate`s. Measure before planning a single policy codebase.
6. **Developer guide open questions** — scaffolding tool vs template repository, where the version bump is computed, ephemeral environments opt-in or automatic. Listed in `developer-guide.md` §13.

---

## Traps — read these before writing code

These are the failure modes that have already been identified. Do not rediscover them.

**Outputs sharing does not create execution order.** Every `input` block needs a matching `after` in `stack.tm.hcl`. An unresolved ordering applies a stale value with **no error**. This is risk R2, the top risk, and the G1 conftest policy exists specifically to catch it.

**`mock_on_fail` must be true in preview and false in deploy.** Separate named `script` blocks so it cannot be got wrong. A deployment that silently falls back to a mock applies nonsense.

**Mocks must be type-correct.** A base64 field mocked as `"mock"` breaks `base64decode()`. A list field mocked as a string type-checks locally and explodes on apply. Prefix every mock with `mock-`.

**Never share secrets through outputs sharing.** Values land in `TF_VAR_*` environment variables, which leak into logs and process trees. Share references — a secret ID, an ARN, a key name — and let the consumer read it under its own identity. Auth tokens are fetched locally per consumer (`google_client_config`, `aws_eks_cluster_auth`), never shared.

**GKE endpoint has no scheme; EKS endpoint includes `https://`.** Classic copy-paste bug between guides.

**Deterministic naming breaks dependency cycles.** The EKS subnet-tagging cycle (network needs the cluster name, cluster needs the subnets) is solved by promoting `cluster_name` to a global. When outputs sharing appears to need a cycle, this is the remedy.

**Outputs sharing models 1-to-N, not N-to-1.** `input` blocks cannot be generated from a dynamic list. Gateway API removes the fan-in problem entirely, which is why it is the target design and the URL-map remedy is only a fallback.

**Avoid `kubernetes_manifest`** for Gateway API and Gatekeeper custom resources. It requires the CRD to exist and the API server reachable **at plan time**, which breaks PR previews. Package CRs in the archetype's own Helm chart and deploy with `helm_release`.

**The Keycloak ↔ Gateway bootstrap cycle.** Keycloak's own `HTTPRoute` carries **no** `SecurityPolicy`, and the Gateway's OIDC discovery resolves through the in-cluster Service, not the public hostname. Without both, a cold environment does not start and the cause is not obvious.

**`failurePolicy: Fail` can lock you out of the cluster** — Gatekeeper rejects its own recovery. `exemptNamespaces` for `kube-system` and the Gatekeeper namespace, ≥3 replicas with a PDB, `Ignore` everywhere except production.

**ECS: never share the task execution role between tenants.** A shared execution role can read every tenant's secrets. Per-instance, even though it duplicates ECR and logs permissions.

**AWS `TargetGroupBinding` can reference any target group in the account.** On a shared cluster, a tenant could redirect another's traffic. Only the `gateway` archetype creates them; RBAC denies the CRD to application namespaces.

**OIDC trust policies: `StringEquals` on the exact `sub`, never `StringLike` with a wildcard.** The most common AWS OIDC misconfiguration. Risk R12.

**Pod secondary ranges are immutable.** Sizing them for too few nodes means rebuilding the cluster. Risk R26.

---

## Repository layout

```
docs/en/, docs/es/      reference documents, in English and Spanish (CLAUDE.md, "Bilingual documentation")
docs/en/proposals/, docs/es/proposals/   design proposals for concrete deployments (not normative)
schemas/                JSON Schema, GENERATED from registry/
registry/               SOURCE OF TRUTH for capabilities, traits, zones, labels
.github/workflows/
```

Planned, not yet present:

```
policy/                 Rego for conftest, plus *_test.rego
modules/                OpenTofu modules
imports/mixins/         backend and provider generators per cloud
imports/generators/v1/  one generator per capability — "the base layer"
imports/contracts/      output/input contracts per capability
imports/scripts/        terramate script blocks
stacks/platforms/       layer 0-3 per cloud and environment
stacks/archetypes/      layer 4-5, with instances/
components/             reusable stack templates
cmdb-data/              level 0 CMDB, one file per stack
```

---

## The registry is load-bearing

`registry/*.yaml` is the **single source of truth** for capabilities, traits, zone names and mandatory labels. Three artefacts are generated from it:

| Generated | Consumer |
|---|---|
| `enum` blocks in `schemas/*.schema.json` | `check-jsonschema` |
| `registry/*.json` bundle | `conftest --data` |
| Gatekeeper chart `values.yaml` | `ConstraintTemplate` parameters |

**Never hand-edit an `enum` in `schemas/`.** That is a bug. The failure mode of drift is nasty: a label the generator stopped emitting while the admission `Constraint` still demands it blocks legitimate deployments at admission. Risk R34.

The generator (`registry-generate`) is **not yet written**. It is the first task of roadmap phase 2c.

---

## Conventions

| Thing | Pattern | Example |
|---|---|---|
| Stack ID | `<cloud>-<env>-<capability>[-<instance>]` | `gcp-demos-gke`, `aws-prod-eks` |
| Stack tags | cloud, env, capability, `platform`\|`archetype:<name>`, `instance:<id>`, `producer`\|`consumer`, `protected` | |
| Generated files | `_<purpose>.tf` | `_main.tf`, `_sharing_generated.tf` |
| Generators | `imports/generators/v<N>/gen_<capability>.tm.hcl` | |
| Contracts | `imports/contracts/contract_<capability>[_<cloud>].tm.hcl` | |
| Mocks | prefixed `mock-` | `mock-endpoint.example.invalid` |

Generated code **is committed to git**, prefixed with `_`, and covered by `CODEOWNERS`. The `terramate generate --check` gate (G0) exists because of this: without it, someone hand-edits a `_main.tf`, the scan passes, and the next generate silently reverts the fix.

---

## Where to start

Roadmap is in `terramate-outputs-sharing-architecture.md` §16. Current position: **nothing built yet; documentation complete**.

**Phase 0 first.** Build a throwaway repository with two stacks and confirm, against a pinned Terramate version:

- `from_stack_id` resolves a global **inherited from a parent directory**, not only one defined in the stack
- `from_stack_id` accepts **interpolation** (`"${global.env}-gke"`), not only a bare reference
- `stack.after` accepts a globals-derived path, **or** tag filters work as a fallback — this one **fails silently**, so test it deliberately
- `--mock-on-fail` behaves as documented when the producer has no state
- Cross-project / cross-account state reads work with the OIDC roles
- A private control plane is reachable from the chosen runner type

These are an afternoon's work and they gate everything else.

---

## The developer guide

Written: `developer-guide.md`. Java, Python and Node/React; GitFlow; `archetypectl new-app` scaffolding still deferred.

Settled there, do not reopen:

| Decision | Rationale |
|---|---|
| **Monorepo per application** | One version, one PR, one CI run for a change crossing two services |
| **One version per application, not per service** | Otherwise "what was running together on Tuesday" has no answer and a rollback has no target. The version is the Git tag; `metadata.version` is generated and a CI gate fails a hand edit |
| **Image promoted between environments, never rebuilt** | A rebuild is a different digest, so "prod runs what qa tested" becomes uncheckable. Promotion is a registry-side re-tag — 200–500 ms, zero bytes, digest and signatures intact. Deploy by digest; the tag is an alias |
| **Every service carries the release tag, rebuilt or not** | Otherwise a release leaves unmodified services on an old tag and the application has three versions at once. `release.lock.json` records service → digest |
| **Frontend is nginx in the cluster, not bucket + CDN** | Same Gateway, hostname, certificate, `HTTPRoute`, `SecurityPolicy` and observability. A bucket needs a second edge path and a second identity model |
| **Platform review to raise `capacity` in a shared environment** | The resolver is the only thing that sees every tenant's draw |
| **Build and deploy specs extend `manifest.yaml`** | A parallel `build.yaml`/`deploy.yaml` is a third place to declare the same dependency, and it drifts. Note `additionalProperties: false` — the schema must be extended from `registry/`, never by hand |

**Rollback is the part that hurts, and the guide says so in §6.** Only redeploying a previous image digest is cheap. A Helm rollback re-runs hooks and cannot revert immutable fields. A `tofu apply` of an earlier commit plans `destroy` for anything the reverted commit added. A migration has no rollback at all — hence expand-contract and migrations separated from deployment. **Reverting a merge does not undo a migration**, and someone will try.

**JVM memory has concrete numbers in §8.3, not a footnote.** Three distinct OOMKill paths, all exit 137 with nothing in the application log: a pre-8u372/11.0.16 JVM on a cgroups v2 node reading the *host's* memory; the 25% default with no flag; and `-Xmx` set to the whole limit leaving nothing for the 250–400 MiB of non-heap.

**The frontend has four details, all found on the first deployment, two of which block it outright** (§10): `nginxinc/nginx-unprivileged` against PSS `restricted` and `readOnlyRootFilesystem`; runtime `env.js` instead of a build-time `VITE_API_URL`, which would produce one image per environment and kill promotion; asymmetric `Cache-Control`; and `try_files $uri /index.html`. The last two deploy successfully and are broken anyway — the worse failure mode.

---

## Working style

The documents are written plainly and densely: tables over prose, concrete numbers over hedging, and the rationale for a decision recorded alongside it. Keep that. When something is uncertain, say so and say what would settle it — several sections end with a "verify in the PoC" note, and those are load-bearing, not filler.

Push back on ideas that will not work. Several decisions in this file exist because an earlier proposal was wrong and got corrected.
