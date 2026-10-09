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

Plus `platform-overview.md` (diagram-led map, read first), `risk-register.md` (73 risks by domain, 70 active), `glossary.md` (every term, defined) and `developer-guide.md` (the application developer's half — branching, versioning, build, rollback). Each of these lives in **two languages**: `docs/en/<file>.md` and `docs/es/<file>.md`. Below, a bare `docs/<file>.md` reference means "that file, in whichever language you are reading" — both copies say the same thing, so the path is language-neutral by design.

**This repository is the normative design specification, and stays so.** It is not frozen, and no deployment repository replaces it. A deployment repository (`disasterproject/infra`, `infra-repo-qa`) implements what is written here and carries a byte-identical copy of `registry/` and `schemas/` pinned to a commit of this one (DR4); it never edits that copy. What implementing the design teaches — a measured tool behaviour, a gate that did not run, a constraint of a real organisation — comes back here as a design change, in both languages, stated as a fact about the design rather than as a report of where it was found.

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
- **File names are identifiers, and stay in English in both copies.** That includes diagram files: `docs/es/…/diagrams/02-request-path.mmd` and `docs/en/…/diagrams/02-request-path.mmd`, never a Spanish name in the English tree or the other way round. The rule applies to every new file; the diagrams named before it keep their names until they are renamed together, in both languages, with their links.
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
| **`prod` in its own account/project/subscription; non-production environments share one; hub and landing zone in their own** | `prod` shares nothing: its project is its isolation boundary (architecture §12.1). Non-production environments (`dev`, `qa`, `demos`, `sandbox`, `ephemeral-*`) share a **non-prod project** (`disasterproject-nonprod` on GCP); when a project's limits are reached, a second non-prod project is added, never a mixed one. Inside it each environment keeps **its own VPC**, its own cluster, its own Cloud SQL instances and its own edge (IP, Cloud Armor, certificate, which must share a project with their load balancer); every resource name carries the environment prefix, and **billing is split by labels**. KMS, the image registry and CI federation stay in the landing zone, granted across projects. Cross-environment isolation inside the non-prod project rests on naming, admission control and review, not on the project boundary — accepted for non-production only (see the next row and risk R54) |
| **Workload Identity principals carry the environment prefix** | On GKE the Workload Identity pool is **one per project** (`PROJECT.svc.id.goog`) and the principal is `ns/<namespace>/sa/<ksa>`, with no cluster in it: the same namespace and KSA in two clusters of one project are **the same GCP identity**. Every KSA that receives GCP IAM is therefore named `<env>-<name>` (`qa-eso-sonarqube`, `qa-keycloak-config`, `qa-sonarqube`); namespaces keep their names. Gatekeeper rejects, in each cluster, a ServiceAccount whose name starts with another environment's prefix (rule P12), and G1 rejects an IAM `member` whose KSA does not carry the prefix of the environment that owns the resource. A cluster-admin of one non-prod environment can still bypass admission and impersonate another: that residual risk is why `prod` never shares a project |
| **Each environment is a VPC/VNet**, a `/17` (or `/16` for production) from `10.0.0.0/8` | |
| **Environments: `prod`, `qa`, `dev`, `demos`, `sandbox`, `ephemeral-*`** | Normalised naming. Older drafts used `shared-demo`/`pre`/`prd` — those names are dead. Every name except `prod` lives in the shared non-prod project of its jurisdiction. Names are **prefix-free** — no `<a>-` is a prefix of `<b>-` (`sandbox` and `sandbox-eu` cannot coexist) — because `<env>-` is the boundary for KSAs, DNS zones and resources in a shared project (`multi-environment` DX3) |
| **An environment is its binding; region and jurisdiction are attributes of it** | Environments are not copies: composition, providers, versions, size, region and jurisdiction vary; generators, contracts, conventions and rules do not. `environments/<env>/binding.yaml` is the only file written by hand; names that are not claims are derived. `metadata.jurisdiction` (the territory the data stays in) selects the folder with its `gcp.resourceLocations`, the non-production project and the state bucket; `metadata.region` is one of its regions and places the environment's resources and key ring. Image registries are regional, one per region of the bindings. Jurisdictions are listed once, in `global.lz.jurisdictions` (`multi-environment` DX1, DX4, DX6) |
| **`demos` is a shared environment** | Not ephemeral-per-demo. Kafka as a common bus argues for it |
| **Data is NOT shared in `demos`** | `database-platform` is bound to `postgres-cloudsql`, the managed provider, so each demo gets its own managed instance. Ten demos get ten managed instances. Isolation, not cost, is the criterion. It used to be left unbound for the same effect; the global-provider model made it an explicit binding |
| **Managed services first; the strategy stays agnostic** | Where a managed service is equivalent, it is the default provider; the operator-based alternative is kept and supported, because some clients will want one and some the other. On GCP, production PostgreSQL is Cloud SQL, and `qa` mirrors production |
| **A capability's provider is global per environment** | One provider per capability per environment, chosen in the binding (AM §2) — resolution stays a lookup. No per-consumer selection: it breaks environment parity and doubles the operations. A temporary per-instance override for migrating between providers is described, not built (`postgres-cloudsql` proposal) |
| **`database-platform` has two maintained providers** | `postgres-cloudsql` (default, managed) and `postgres-operator` (CloudNativePG). A consumer carries both paths, `data` and `data-tenant`, selected by the provider's trait (`cloudsql` or `cnpg`). Either way each consumer gets its own instance: data are never shared |
| **64 pods per node** (platform default) | Assumes ≥32 GB nodes. Gives `/25` per node, 128 nodes in a `/18` pod half. **Immutable after cluster creation** |
| **Two node pools per cluster: `system` and `apps`** | `system` (tainted with GKE's `components.gke.io/gke-managed-components`) runs layers 2b and 3 and GKE's components; `apps` (untainted, carrying the `vm.max_map_count` sysctl) runs layers 4 and 5. The generator adds the `system` selector and toleration to platform charts; applications set nothing. Gatekeeper P11 lets only `system`'s owners tolerate its taint. A third pool (Kafka's page cache, GPUs) is an exception backed by data, not a starting point; the one documented is `gvisor` (GKE Sandbox, 0–1 nodes) for third-party code that needs privileges, A.I.G's agent (`appsec-qa` DA8, Gatekeeper P13). Replaces the per-archetype pools (`sonar`, `kafka`) of earlier revisions (`gke-qa` §5, DN11) |
| **Layer 2b for policy** | Admission control must precede everything it governs, including layer 3 services. Cluster-scoped, not a named service. Precedent: layer 1b for cloud monitoring |
| **No Gatekeeper mutation** | The generator emits labels; Gatekeeper validates them. One writer, one validator. Mutation would make changes invisible in Terraform diffs and split ownership of the label list |
| **East-west traffic resolves by DNS** | So addresses need not be reproducible across rebuilds. What IS required is **idempotency**: allocation key is `(pool, owner, purpose)` |
| **Firewall rules are written by whoever claims the range** | Prefer workload selectors (network tags, security group references) over CIDR for east-west |
| **A runtime creates its own subnets** | Node subnets, pod ranges and control-plane subnets are the runtime's claims (AM §9.5), so its archetype creates them in a first `*-subnets` stack. `network` publishes the VPC/VNet, egress and routing, and knows no runtime. Claim owner = creator = firewall writer; rebuilding a cluster never touches the network; the EKS subnet-tagging cycle cannot arise. Applied to all five runtime guides: GKE, EKS, Cloud Run, ECS Fargate and AKS (architecture §5.2, §6.2, §7.2, §8.2, §9.2); on the serverless runtimes the claim is the egress subnet or the task subnets, found through `global.platform.runtime_subnet_stack_id` |
| **The CMDB has two halves, split by who writes them** | The **declared** half (stacks, edges, claims) is generated by `archetypectl cmdb` in the pull request, checked like G0, and lives on `main`, so the reviewer sees a new edge or claim in the diff. The **observed** half (`lastApply`, `resourceCount`, non-sensitive outputs, drift) is written after apply by the reusable `cmdb-sync` workflow to the `cmdb-observed` branch — never to `main`, which would need a protection bypass and would re-trigger `deploy` (R55). The read model is a private release asset (`cmdb-latest`): public Pages would publish the environment's map. The destroy guard counts CMDB **edges**, never stack names (AM §11, architecture §12.4, §14.2; `cmdb-qa` proposal) |
| **The edge depends only downward; the load balancer → Envoy leg is HTTP** | Public TLS terminates at the load balancer with the layer-1 certificate (Certificate Manager, validated by DNS authorization in the environment's own delegated zone). A certificate for the backend leg from `cert-manager` (layer 3) was an upward dependency the load balancer did not even validate. The NEG name stays the only upward edge (AM §3). If the leg must ever be authenticated, the root is a platform CA in layer 1, never the internal CA (architecture §10.2; `edge-qa` DL9, `envoy-gateway-qa` DG14) |
| **Public names never carry the environment name** | Whatever is visible without credentials — public zone and hostnames, the wildcard that lands in Certificate Transparency logs, globally unique bucket names, the Keycloak realm name in OIDC/SAML URLs — uses the environment's `network.public_id`: 7 random lowercase letters from the landing zone, never a hash of the name. As a **subdomain** (`sonar.<public_id>.disasterproject.com`), not a hyphen: the wildcard stays per environment, the delegated zone stays the environment's, cookies do not cross environments. Internal names (labels, KSA prefixes, stack IDs, namespaces, `qa.internal`) keep the environment name: hiding them protects nothing and breaks billing and operations. Checked in G1 over each binding and in G3 over the plan, from one word list (architecture §13.3–§13.4); the realm by an `assert` in `keycloak` (AM §7; `edge-qa` DL10) |
| **Pipeline access to GKE through the control plane DNS endpoint** | IAM only (`container.clusters.connect` per cluster, then RBAC); the public IP endpoint is disabled. The earlier procedure — opening the runner IP in authorised networks through a Cloud Run intermediary — was unreachable under the `run.allowedIngress` org policy and rested on four fragile conditions; R38 and R39 are retired. The network barrier is gone, so access by principals outside the list is alerted in layer 1b (`landing-zone-qa` DZ4, `gke-qa` §2.2). Where an organisation forbids any internet-reachable Kubernetes endpoint, the documented **variant** is a `/32` per job with four mandatory controls and risk R64 — a variant, never the default (`landing-zone-qa` §3.2, DZ16) |
| **The landing zone owns project singletons and cross-project identities** | A resource that exists once per project (the Binary Authorization policy) is written only by the landing zone, one rule per cluster, `ALWAYS_DENY` by default — otherwise each environment's `apply` erases the others' rules (R59). SAs that receive cross-project grants (a runtime's node SA) are created by the landing zone, so layer 0 never waits on layer 2 (R60). Pipeline identities live in the landing zone project with per-prefix state access (architecture §11.2; `landing-zone-qa` DZ5, DZ6) |
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
   **Settled for `qa`: separate VPC.** `qa` has its own VPC inside the shared non-prod project, so its edge load balancer lives in its own VPC next to the Envoy NEG and nothing routes through the hub; R23 does not arise. Still open for `demos` and any environment whose edge would sit in the hub. See `proposals/sonarqube-qa/README.md` §4.15.
3. **Kafka partition ceiling** on the intended broker count. The 4000 budget in the `demos` binding is a placeholder.
4. **Where does resolution run** — a CLI in the repo, or a reusable workflow? Determines whether the project office can validate a demo locally. *Proposed* in `infra-repo-qa` DR3: a CLI from a separate `platform-tools` repository, pinned with `mise`, run by `ci/g1.sh` both locally and in CI.
5. **How much Rego is genuinely shared** between conftest and `ConstraintTemplate`s. Measure before planning a single policy codebase.
6. **Developer guide open questions** — scaffolding tool vs template repository, where the version bump is computed, ephemeral environments opt-in or automatic. Listed in `developer-guide.md` §13.

---

## Traps — read these before writing code

These are the failure modes that have already been identified. Do not rediscover them.

**Outputs sharing does not create execution order.** Every `input` block needs a matching `after` in `stack.tm.hcl`. An unresolved ordering applies a stale value with **no error**. This is risk R2, the top risk, and the G1 conftest policy exists specifically to catch it. The rule wants the **producer itself** in `after`: running after a stack that runs after the producer is correct today and fails G1 on purpose, because it holds only until someone reorders the stack in between (architecture §13.3).

**Globals do not resolve in `stack.after` — it is a parse error, not a silent one** (measured, Terramate 0.16.0 and 0.17.3, `poc/RESULTS.md`). The resolver must write literal values; prefer `after = ["tag:<capability>"]` over a path so a stack can move. The silent failure that remains is a *forgotten* `after`: a consumer with an `input` and no ordering generates cleanly and can be scheduled before its producer, with no error at any stage. That is R2, and G1 is what catches it.

**Terramate tags cannot contain `:`** (measured, 0.16.0 and 0.17.3: only lowercase letters, digits, `.`, `_`, `-`, `/`). In a filter, `:` means AND and `,` means OR, and two `--tags` flags are OR. So instance and archetype tags are `instance/<id>` and `archetype/<name>`, and `--tags gcp:qa:network` selects stacks carrying all three tags. A tag written `instance:alpha` fails the whole configuration load.

**`terramate list` has no `--json`** (0.16.0, 0.17.3): it prints paths. And `terramate experimental eval` exposes `terramate.stack.id`, `tags` and `path` but **not `after`** (measured, 0.17.3) — an inventory built on it cannot feed the R2 rule at all. The inventory comes from `terramate debug show metadata`, which carries `after`, parsed by `ci/stacks-json.sh`; it refuses to return an empty array (architecture §14.4, `poc/RESULTS.md` A8).

**`script` blocks are still experimental on 0.17.3.** `experiments = ["outputs-sharing", "scripts"]`: without `"scripts"`, one `script` block fails the load of the **whole** configuration, and every `terramate` command exits 1 (`poc/RESULTS.md` A8a).

**`output.value` is copied verbatim into the generated code.** Terramate interpolates neither `global.*` nor `"${global.x}"` there: `value = global.project_id` lands in the `.tf` as an invalid reference, and so does a `var.*` no `input` declares. A contract publishes `module.*`, `resource.*`, `data.*` or a `local` the generator emits (architecture §4.3, `poc/RESULTS.md` A8d).

**The G0 flag is `terramate generate --detailed-exit-code`** (0 = up to date, 2 = drift, 1 = error). `--check` does not exist in Terramate and fails with `unknown flag`. A wrong-typed mock changes no generated file, so G0 cannot catch it; G1 checks mock shape against the contract.

**`mock_on_fail` must be true in preview and false in deploy.** Separate named `script` blocks so it cannot be got wrong. A deployment that silently falls back to a mock applies nonsense.

**Mocks must be type-correct.** A base64 field mocked as `"mock"` breaks `base64decode()`. A list field mocked as a string type-checks locally and explodes on apply. Prefix every mock with `mock-`, or, where the provider fixes the format, carry `mock` inside it (`vpc-mock…`, `projects/mock-project/…`) — and a base64 mock decodes to a `mock-` value too (`bW9jay1jYQ==`, `mock-ca`), so a mocked CA that reaches a deploy log is recognisable. The G1 rule `terramate.mocks` checks all three shapes (architecture §13.3).

**`--mock-on-fail` covers `input` blocks, never `data` sources.** A `data` source that reads something another stack creates fails the preview whenever that thing does not exist yet, and no flag saves it. Reference by a deterministic name or URL instead — the NEG is referenced by its URL, built from `neg_name` (architecture §10.2). An `after` with no `input` behind it is checked by nobody, so the one such edge, the upward one, has a named G1 rule (§13.3).

**A gate that cannot run is worse than an absent one, because it reports success.** Measured: `conftest test` without `--all-namespaces` evaluates only `package main` and passes with `0 tests`; `--data registry/` leaves `data.registry` empty, so an unknown trait passes; `--namespace terraform` matches no `package terraform.public_names`; a `shopt -s nullglob` loop over a glob that matches nothing validates nothing and exits 0. Every gate proves it evaluated something: G1 and G3 fail on zero rules, `stacks-json.sh` on zero stacks, `validate.yml` on an existing directory that matches no file (architecture §14.4, `poc/RESULTS.md` A8). The same holds for a step a gate depends on: a deploy marker tied to the whole job never moves while the observer that follows the apply is broken, so it is tied to the apply step.

**In a shared project, the plan says `create` and the API says `409`.** A resource that already exists under our name is not in our state, so nothing before the apply sees it, and the apply stops thirty resources in. A preflight checks every name first; names carry the repository or the environment (`gh-disasterproject-infra`); a resource we did not create is never imported (`landing-zone-qa` §1.3, R62).

**A plan identity is reachable from any pull request, so it never holds `roles/viewer`.** `tf-plan-<env>@` gets an enumerated read list, never a secret's payload and never a decrypter beyond its own state key; `roles/viewer` reads every service's configuration on behalf of code nobody has reviewed yet (`landing-zone-qa` DZ14). The state condition carries a listing half (`objectListPrefix` starts with `<env>/`), or the first plan cannot list its own prefix.

**The identity that grants roles is bounded by role.** Only the landing zone's apply identity administers project IAM, through `modifiedGrantsByRole.hasOnly([...])` generated from the same `global.identities` list it grants from — never an unbounded `folderAdmin` or `projectIamAdmin`, which is an escalation path (DZ13, R63). Federation coordinates are committed in `ci/federation.env`, not repository variables; G1 fails on `vars.GCP_*` (DZ12).

**The bootstrap's plaintext fallback lives only in `TF_ENCRYPTION`, and `enforced = true` comes after the migration** (measured, OpenTofu 1.10.6, `poc/RESULTS.md` A9). `enforced = true` forbids even an injected fallback and the environment cannot relax it, so committing it in step 1 makes the migration impossible; committing a fallback in the code leaves a plaintext path open until someone removes it.

**Never share secrets through outputs sharing.** Values land in `TF_VAR_*` environment variables, which leak into logs and process trees. Share references — a secret ID, an ARN, a key name — and let the consumer read it under its own identity. Auth tokens are fetched locally per consumer (`google_client_config`, `aws_eks_cluster_auth`), never shared.

**GKE endpoint has no scheme; EKS endpoint includes `https://`.** Classic copy-paste bug between guides.

**Never parse the environment out of a stack id, and never compare a prefix without its separator.** `<cloud>-<env>-<capability>` is ambiguous once a name contains `-`: `split(id, "-")[1]` turned `gcp-sandbox-eu-edge` into `sandbox` and the upward-edge rule failed two correct environments (measured, conftest 0.70.1). Read the environment from `global.env` or a tag; pair stacks by what precedes their suffix. `europe-west1` is a prefix of `europe-west10`, `sandbox` of `sandbox-eu`: compare `<region>-`, `<env>-` (`multi-environment` DX3, R67).

**An environment is emitted, never copied, and no list of environments is kept by hand.** Copying another environment's `stack.tm.hcl` files and rewriting `qa` into the new name over- and under-matches (`qa.internal`, prefixes inside values) and drifts with every later change; the resolver emits the tree from binding and manifests. Workflow inputs are text validated against `environments/`, counts are derived, and the public-name words include every binding's name — with a hand-kept word list, a public name carrying another environment's name passed G1 and G3. Each stack's state key is `<env>/<stack id>`, never its path, so moving a directory is not a state move (`multi-environment` DX1, DX8, R70).

**GitHub creates a missing Environment on the fly, unprotected.** A job that names an Environment that does not exist gets one with no reviewers and no branch policy, and its token carries `environment: <env>`. An identity bound to `attribute.environment/<env>` alone is then impersonable from any branch in the window between federating it and an administrator creating the Environment. Apply and destroy identities are bound to `attribute.env_ref/<env>@refs/heads/main`; Environments are created before the binding merges; a manual workflow validates the environment in a job without `environment:` and never interpolates it into a script (`multi-environment` DX9, R71).

**KMS key rings and keys are never deleted.** Their location is decided before the first `apply`: an environment's ring follows its cluster's region (`gke-secrets` must be in the cluster's location), and a ring created in the wrong region stays there for good (`multi-environment` DX4).

**No chart or module default is a real environment's value.** A default of `envoy-qa` works on `qa` with the override missing, and the second environment silently creates an `envoy-qa`. Defaults are neutral (`envoy`, `gateway`) or absent; the generator always passes the derived value (`multi-environment` DX2, R69).

**Deterministic naming breaks dependency cycles.** The EKS subnet-tagging cycle (network needs the cluster name, cluster needs the subnets) arose while the network owned the cluster's subnets; with the runtime owning them it cannot arise, and `cluster_name` stays a global so the runtime's stacks agree on it. When outputs sharing appears to need a cycle, a deterministic global is still the remedy.

**Outputs sharing models 1-to-N, not N-to-1.** `input` blocks cannot be generated from a dynamic list. Gateway API removes the fan-in problem entirely, which is why it is the target design and the URL-map remedy is only a fallback.

**Avoid `kubernetes_manifest`** for Gateway API and Gatekeeper custom resources. It requires the CRD to exist and the API server reachable **at plan time**, which breaks PR previews. Package CRs in the archetype's own Helm chart and deploy with `helm_release`.

**`helm_release` renders the chart at apply, so a chart bump reviewed as one line is a manifest nobody saw.** Review `_rendered/`, never the version number: `ci/hydrate.sh` writes `helm template` of every release next to its stack, G0 fails if it is stale, `gator` evaluates it in G1, and the deploy compares `helm get manifest` with it after apply. Three measured details (Helm 3.19.0): `--skip-crds` does not drop CRDs a chart renders from `templates/` — split by `kind`; CRDs are ~97 % of a render — keep a digest; hooks are in `helm template` but not in `helm get manifest` — keep them apart. A chart value from outputs sharing is rendered as `late:<input>`, never a mock; a `Secret` with a value in a render fails it (`source-hydration` DH2–DH7, R72, R73).

**The Keycloak ↔ Gateway bootstrap cycle.** Keycloak's own `HTTPRoute` carries **no** `SecurityPolicy`, and the Gateway's OIDC discovery resolves through the in-cluster Service, not the public hostname. Without both, a cold environment does not start and the cause is not obvious.

**VPC egress is denied by default, and the environment's own range is egress too.** Without an allow for the `/17`, nothing fails at apply: the cluster is created, and the first admission webhook times out — with `failurePolicy: Fail`, the lock-out below. The allows are 443, the `/17` and the private VIP; a peering-based control plane outside the `/17` needs 443 and 8132 (konnectivity), written by GKE; any other port is an `egress_extra` entry of the archetype that needs it (`network-qa` DW6, R66).

**In the shared project, IAM does not keep a network resource on its own VPC.** `compute.networkAdmin` reaches every VPC, and a private zone bound to another environment's VPC answers its Google APIs. The G3 rule `terraform.own_network` does; `dns.admin` on the project is only ever conditioned on the zone prefix, because the public zones live there too (`network-qa` DW8, R65).

**`failurePolicy: Fail` can lock you out of the cluster** — Gatekeeper rejects its own recovery. `exemptNamespaces` for `kube-system` and the Gatekeeper namespace, ≥3 replicas with a PDB, `Ignore` everywhere except production.

**ECS: never share the task execution role between tenants.** A shared execution role can read every tenant's secrets. Per-instance, even though it duplicates ECR and logs permissions.

**AWS `TargetGroupBinding` can reference any target group in the account.** On a shared cluster, a tenant could redirect another's traffic. Only the `gateway` archetype creates them; RBAC denies the CRD to application namespaces.

**OIDC trust policies: `StringEquals` on the exact `sub`, never `StringLike` with a wildcard.** The most common AWS OIDC misconfiguration. Risk R12.

**Pod secondary ranges are immutable.** Sizing them for too few nodes means rebuilding the cluster. Risk R26.
**One Workload Identity pool per GCP project.** Two clusters in the shared non-prod project that both run `sonarqube/eso-sonarqube` get the same GCP identity, and each can read the other's secrets. Prefix every KSA that holds GCP IAM with the environment (`qa-eso-sonarqube`), and build it only from `global.ksa_prefix` — G1 rejects a literal KSA name in a generator; prefixing the ESO controller's namespace isolates nothing, because the controller has no GCP identity and reads with each consumer's KSA.

---

## Repository layout

```
docs/en/, docs/es/      reference documents, in English and Spanish (CLAUDE.md, "Bilingual documentation")
docs/en/proposals/, docs/es/proposals/   design proposals for concrete deployments (not normative)
schemas/                JSON Schema, GENERATED from registry/
registry/               SOURCE OF TRUTH for capabilities, traits, zones, labels
.github/workflows/
```

Planned, not yet present — they belong to the deployment repository `disasterproject/infra`, not to this one (layout, branches and workflow templates in `proposals/infra-repo-qa/`; there is **no branch per environment**, DR2):

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
cmdb-data/              level 0 CMDB, declared half, one file per stack (observed half: branch cmdb-observed)
```

---

## The registry is load-bearing

`registry/*.yaml` is the **single source of truth** for capabilities, traits, zone names and mandatory labels, and it is written **here**: a deployment repository carries a byte-identical copy of `registry/` and `schemas/` pinned in `spec.lock.json`, checked both ways by `ci/spec-sync.sh`, and never edits it (`infra-repo-qa` DR4). Three artefacts are generated from it:

| Generated | Consumer |
|---|---|
| `enum` blocks in `schemas/*.schema.json` | `check-jsonschema` |
| `registry/registry.json` bundle (top-level key `registry`) | `conftest --data` |
| Gatekeeper chart `values.yaml` | `ConstraintTemplate` parameters |

**Never hand-edit an `enum` in `schemas/`.** That is a bug. The failure mode of drift is nasty: a label the generator stopped emitting while the admission `Constraint` still demands it blocks legitimate deployments at admission. Risk R34.

The generator (`registry-generate`) is **not yet written**. It is the first task of roadmap phase 2c. Until it exists, `.github/scripts/check-registry-enums.py` — blocking in `validate.yml` — compares capabilities, traits and allocatable zones with the schema enums: a notice in its place would be a gate that cannot run.

---

## Conventions

| Thing | Pattern | Example |
|---|---|---|
| Stack ID | `<cloud>-<env>-<capability>[-<instance>]` | `gcp-demos-gke`, `aws-prod-eks` |
| Public names | `<app>.<public_id>.<domain>`; buckets `disasterproject-<public_id>-<purpose>` | `sonar.tqbvzkr.disasterproject.com` (`public_id` is an example) |
| Stack tags | cloud, env, capability, `platform`\|`archetype/<name>`, `instance/<id>`, `producer`\|`consumer`, `protected` | |
| Generated files | `_<purpose>.tf` | `_main.tf`, `_sharing_generated.tf` |
| Rendered charts | `_releases.json`, `_values-<release>.yaml` (generated); `_rendered/<release>.yaml`, `.hooks.yaml`, `.crds.sha256` (`ci/hydrate.sh`) | `_rendered/cert-manager.yaml` |
| Generators | `imports/generators/v<N>/gen_<capability>.tm.hcl` | |
| Contracts | `imports/contracts/contract_<capability>[_<stack>][_<cloud>].tm.hcl` — `<stack>` for an internal stack of a multi-stack archetype | `contract_run_subnet_gcp.tm.hcl` |
| Mocks | prefixed `mock-` | `mock-endpoint.example.invalid` |

Generated code **is committed to git**, prefixed with `_`, and covered by `CODEOWNERS`. The `terramate generate --detailed-exit-code` gate (G0) exists because of this: without it, someone hand-edits a `_main.tf`, the scan passes, and the next generate silently reverts the fix. G0 also re-runs `ci/hydrate.sh` and fails on any change under `_rendered/`.

---

## Where to start

Roadmap is in `terramate-outputs-sharing-architecture.md` §16. Current position: **Phase 0 local PoC done (`poc/`); nothing deployed; documentation complete**. This repository holds documentation and proposals only; the deployment repository it describes is laid out in `docs/en/proposals/infra-repo-qa/`.

**Phase 0 results** (Terramate 0.16.0, OpenTofu 1.10.6, measured 2026-09-16; re-run 2026-09-28 on 0.16.0 and on 0.17.3, the pinned version, with identical output — `poc/RESULTS.md`):

| Assumption | Result |
|---|---|
| `from_stack_id` resolves a global **inherited from a parent directory** | Confirmed |
| `from_stack_id` accepts **interpolation** (`"${global.env}-gke"`) | Confirmed |
| `stack.after` accepts a globals-derived path | **Refuted, loudly** — parse error. Tag filters and literal paths work; the resolver writes literals |
| `--mock-on-fail` behaves as documented when the producer has no state | Confirmed; it does not mask a missing producer stack |
| Cross-project state reads work with the OIDC roles | Not tested — first `qa` deployment, `landing-zone-qa` VZ1–VZ3 |
| The control plane is reachable from the runner | Not tested — now the DNS endpoint with IAM only, `landing-zone-qa` VZ5 |
| Plaintext bootstrap state migrates with the fallback only in `TF_ENCRYPTION` (2026-10-04, OpenTofu 1.10.6) | **Confirmed**; `enforced = true` cannot be committed until after the migration (`poc/RESULTS.md` A9) |
| The gate tooling evaluates what it claims (2026-10-04, 0.17.3, conftest 0.70.1) | **Refuted** as previously written — `scripts` experiment required, no `after` in `experimental eval`, `output.value` verbatim, conftest namespaces and data. Fixed in the architecture and the templates (`poc/RESULTS.md` A8) |

Two side findings: a Terramate project is **one git repository with one root config** (it cannot be nested in another), and `output.description` is not emitted into the generated block.

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
