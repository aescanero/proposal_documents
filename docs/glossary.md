# Glossary

Technical terms and definitions drawn from `platform-overview.md`, `archetype-model.md`, `terramate-outputs-sharing-architecture.md`, `developer-guide.md` and `risk-register.md`. Proposals under `proposals/` are not covered. Organised by the area of the platform each term belongs to, matching the reading order in `platform-overview.md` §16. Definitions are taken from, or closely follow, the source documents — this file adds no new decisions.

---

## 1. Resolve — core concepts (`archetype-model.md`)

| Term | Definition |
|---|---|
| **Archetype** | A unit that deploys an operator or shared service that others consume and imposes a multi-tenant contract — OR, in the general packaging sense, the platform's unit of composition: a set of Terramate stacks with a manifest declaring what it requires, provides, conflicts with, owns and claims. |
| **Component** | A dedicated instance inside an archetype that uses it, with no contract to anyone else; a parameterised, reusable stack template (chart, claims, firewall rules, secret integration already solved) selected and configured with values rather than authored from scratch. The same technology can be both an archetype and a component (`postgres-operator` vs `component/postgres`) — not an inconsistency. |
| **Capability** | A virtual name (e.g. `cluster`, `ingress`, `oidc-idp`, `database-platform`) that an application depends on instead of a concrete archetype. Exactly one provider satisfies a capability per environment, decided by the environment binding, so application manifests need not change when the implementation changes. |
| **Provider** (of a capability) | The concrete deployed archetype instance that satisfies a capability in an environment. Unlike apt/rpm, providers are concrete deployed instances, not interchangeable package builds. |
| **Trait** | A controlled-vocabulary tag expressing a property version constraints cannot ("this monitoring agent cannot run on Autopilot"), turning a would-be runtime failure into a validation failure at resolution time. An unregistered trait is a resolution error. |
| **Manifest** (`manifest.yaml`) | One file per archetype (`component.yaml` for a component) declaring metadata, `requires`/`provides`/`conflicts`, runtimes, stacks, claims, firewall, capacity and providers. Read by both the resolver and Terramate (`tm_yamldecode(tm_file(...))`). |
| **Resolver** (`archetypectl resolve`) | Computes the transitive closure, validates versions/traits, allocates claims from hierarchical pools, and emits an ordered plan before any code is generated. Runs before `terramate generate`, fails closed, and never backtracks — exactly one provider per capability per environment makes resolution linear, not NP-complete. |
| **Ledger** (`PoolLedger`) | A Git-committed JSON file recording every resource allocation (zones, active and quarantined claims); the source of truth for what is occupied. A merge conflict on the ledger file is the concurrency-control lock. |
| **Component catalog** | The set of reusable component templates that lets composing a new archetype be selection, not infrastructure authorship — "twenty minutes instead of a day." |
| **CMDB** (Configuration Management Database) | A derived, three-level system of record built from Git files (level 0), a published read model (level 1) and an analytical DuckDB model (level 2), with an optional graph database (level 3). An inventory CMDB, not a change-management one. See §5 below. |
| **Binding / environment binding** (`binding.yaml`) | Names which concrete archetype instance satisfies each capability in a given environment, plus network/cluster/capacity/policy settings; small enough to review in full and schema-validated like any manifest. |
| **`binding.tm.hcl`** | The generated Terramate globals file that is **the seam** between the Resolve half and the Generate half of the system. The resolver writes it; the generators consume it; neither knows the other's internals. Never hand-edited. |
| **Resolution** | The 17-step algorithm (Load → Graph → Validate → Allocate → Emit) that validates a proposed composition and allocates resources before code generation. See §6 below. |
| **`resolution.json`** | The emitted output of resolution: closure, bound providers, stacks, claims, tenant resources, capacity usage, apply order, `skipped_stacks` and warnings. |
| **Claim** | A finite, indivisible resource unique within a scope, reserved via the ledger (CIDR, hostname, static IP). Allocation must be idempotent, keyed on `(pool, owner, purpose)`. |
| **Capacity** | A divisible quantity with a known total, tracked as a budget with **no** ledger (`kafka_partitions`, `db_connections`, `workload_identities`, `managed_db_instances`). Enforced by summing active tenants' usage against an environment budget. |
| **Deterministic (global)** | A value derivable without collision from instance identity plus convention (namespace, log group, IAM role name, Kafka topic prefix); not tracked in any ledger because tracking it "adds contention for nothing." |
| **Idempotency (resolution)** | A re-run of resolution (e.g. after a failed apply) must not consume new resources; achieved via the `(pool, owner, purpose)` key returning the existing allocation rather than allocating anew. Five retries of a failed deployment must not burn five pod ranges. |
| **Quarantine** | A cooldown state a released claim passes through before becoming available again (7 days for CIDR ranges, 0 for hostnames), because routes, peerings, firewall rules and DNS caches outlive a `tofu destroy`. |
| **Transitive closure** | The full set of capabilities/archetypes an application pulls in once every dependency's dependencies are followed — e.g. an application declaring 6 capabilities can resolve to 15 archetypes. |
| **Kind** | The manifest/document-type discriminator: `kind: Archetype`, `kind: Component`, `kind: EnvironmentBinding`, `kind: PoolLedger`; also `metadata.kind` distinguishing `catalog` vs `demo` archetypes. |
| **`kind: catalog`** | Platform-team-authored, long-lived (years), many instances, strict semver, may publish `provides`, may target layers 0–3, full review gate. |
| **`kind: demo`** | Project-office-authored (light review), short-lived (weeks), one instance, `0.x` versioning with no guarantees, leaf-only (cannot publish `provides`), restricted to layer 5, requires `expiresOn`, lighter review gate (schema + policy + budget only). |
| **Pool** | A hierarchical, scoped reservoir of a finite resource (address space, hostnames) from which claims are allocated — e.g. the global `/8` pool at layer 0, subdivided into environment pools at layer 1, then purpose zones. |
| **Environment** | A layer-1 archetype instance (`prod`, `qa`, `dev`, `demos`, `ephemeral-*`) that claims a `/17` (or `/16` for `prod`) from the global pool and provides `network`, `env-edge`, `cidr-pool`, `psa-range` to what it hosts. |
| **`demos` environment** | A shared (not ephemeral-per-demo) environment — Kafka as a common bus argues for sharing — where `database-platform` is deliberately left **unbound** so each demo tenant gets its own dedicated managed database instance. Isolation, not cost, is the criterion. |
| **Instance** | A concrete deployment of an archetype (e.g. `demos-alpha`), identified in the CMDB by versions, claims, stacks and expiry. |
| **Consumer / Producer (tenant-resource pattern)** | A consumer archetype writes objects (e.g. `KafkaTopic`) directly into a producer/provider archetype's namespace, rather than merely reading its outputs; declared on both sides via `creates_tenant_resources` and `tenant_resources`. |

---

## 2. Archetype layers

| Layer | Name | Provides / claims |
|---|---|---|
| **0** | landing-zone | Singleton per cloud account. Owns hub, dns-zone, cert, waf, cidr-pool, edge-ip. Lifecycle: years. |
| **1** | environment | One per environment. Claims a `/17`/`/16`; provides `network`, `env-edge`, `cidr-pool`, `psa-range`. |
| **1b** | cloud-monitoring | Parallel to layer 2, attached to the *environment* (not a cluster) because cloud-native monitoring is environment-scoped; provides `cloud-observability`. Precedent cited for layer 2b. |
| **2** | runtime | One runtime per environment (`gke`, `gke-autopilot`, `eks`, `aks`, `cloudrun`, `fargate`); claims node subnet + pod range; provides `cluster` or `serverless-runtime`. |
| **2b** | policy | `policy-gatekeeper`, one per Kubernetes cluster. Must precede everything it governs (admission control), including layer 3, so it sits between layers 2 and 3. Kubernetes runtimes only; provides `policy`. |
| **3** | platform services | gateway, monitoring, cert-manager, external-dns, secrets, mesh — one per capability per environment. |
| **4** | middleware | kafka, keycloak, postgres-operator, redis-operator — one per capability per environment. |
| **5** | applications | webapp-3tier, event-driven, demo-* — many per environment, days-scale lifecycle, owned by application teams / project office. |
| **Edge attachment handle** | The one upward edge in an otherwise strictly downward dependency graph: layer 3's `gateway` archetype publishes a NEG name / target group ARN / AGFC frontend that layer 1's edge stack consumes. |

---

## 3. Manifest grammar (package-analogy borrowed from apt/rpm)

| Field | Analogue | Definition |
|---|---|---|
| **`requires`** | `Depends:` | Declares a capability dependency; failure is a resolution error naming the full requirer chain. |
| **`requires[].traits`** | — | Required traits on the bound provider; failure names the missing trait. |
| **`requires[].optional`** | `Recommends:` | Failure is a warning only; drives `condition:` stack selection. |
| **`provides`** | `Provides:` | Declares which capability (version, traits, outputs, `tenant_resources`) the archetype satisfies. Belongs to the archetype as a whole, not to one internal stack. |
| **`conflicts`** | `Conflicts:` | Declares incompatible capabilities/archetypes; failure is a resolution error. |
| **`runtimes`** | `Architecture:` | Which runtimes the archetype supports; failure if the environment's runtime is absent. |
| **`stacks[]`** | — | The internal Terramate stacks an archetype owns; each becomes one Terramate stack under the instance directory. `after` becomes `stack.after`. |
| **`stacks[].use`** | — | References a component from the catalog to expand into a stack; unknown component is an error. |
| **`stacks[].condition`** | — | A boolean expression (e.g. `resolved(database-platform)`) evaluated post-resolution to decide which stacks are actually generated. |
| **`claims[]`** | — | Declares finite resources the archetype/stack reserves; failure is an allocation failure (pool exhausted or value taken). |
| **`firewall[]`** | — | Declares network rules using selectors (see §7); failure if a selector references an unclaimed purpose. |
| **`capacity{}`** | — | Declares divisible-resource draw against a shared budget; failure is budget exceeded across active tenants. |
| **`providers[]`** | `Build-Depends:` | Declares required OpenTofu provider sources and version constraints; failure is empty constraint intersection across the closure. |
| **`creates_tenant_resources`** | — | Declared on a consumer stack, listing which provider capabilities it writes tenant resources into (e.g. `event-bus`); must match the provider's authorised `tenant_resources` kinds. |
| **`tenant_resources`** | — | Declared on a provider's `provides` entry: which kinds of tenant-created objects it authorises (e.g. `KafkaTopic`, `KafkaUser`), with `namePrefix` and `maxCount`. |
| **Virtual capability** | — | A capability name an application depends on abstractly (e.g. `cluster`), satisfied by whichever archetype the environment binding names. |
| **Capability version** | — | Versions the capability's **outputs contract**, not its implementation. MAJOR = output removed/renamed/type-changed or a `tenant_resources` kind removed; MINOR = output or trait added; PATCH = implementation-only, contract byte-identical. |

---

## 4. Networking and address pools

| Term | Definition |
|---|---|
| **CIDR block** | An address range claimed as a resource; e.g. environment CIDR, node subnet, pod range, database subnet/PSA range, serverless egress subnet. |
| **PSA (Private Services Access) range** | A GCP-specific, per-VPC (not per-archetype) address range for managed services, claimed once by the environment archetype at layer 1. A database claim within it is not itself a CIDR claim. |
| **Purpose zone** | A named subdivision of an environment's address pool (`infra`, `data`, `edge`, `growth`, `pods`), each claimable only for declared purposes; gives firewall rules a stable destination surface for the cases that genuinely need a CIDR rather than a workload selector. |
| **Zone `growth`** | A reserved, never-allocatable zone held for future expansion within an environment pool. |
| **Zone `pods`** | A `/18` purpose zone used only for pod ranges. |
| **Pod range** | The secondary IP range allocated to pods on a Kubernetes cluster, sized from `max_pods_per_node`. **Immutable after cluster creation** (risk R26). |
| **Node subnet** | The IP range allocated to cluster nodes; sizing derived as `max_nodes × 4`, floored at `/24`. |
| **`max_pods_per_node`** | Platform default **64** (assumes ≥32 GB RAM nodes), giving a `/25` block per node and 128 nodes in a `/18` pod half. Immutable after cluster creation. Whether it is settable on GKE Autopilot is an open question. |
| **Overlay-pods** (trait) | Marks a runtime (e.g. AKS with Azure CNI Overlay) whose pods do not consume VNet/real network addresses, so its pod-range claim is zero — matters for capacity planning. |
| **Claim profile** | The per-runtime shape of what network resources a runtime claims (e.g. GKE claims node subnet + pod range; EKS claims node subnets only, consuming real VPC addresses per pod). |
| **Static edge IP** | An account/project-scoped claim for a fixed public IP address, claimed at layer 0. |
| **Hostname (claim)** | A DNS name claim, scoped to an environment's DNS zone; zero-day quarantine cooldown. |
| **Allocation key** | The triple **`(pool, owner, purpose)`** used to make claim allocation idempotent — a repeat request for the same triple returns the existing allocation. |
| **First-fit** | The deterministic allocation strategy: candidate blocks of the requested size are considered in ascending order and the first that fits is chosen, ensuring reproducibility after a rebase. |
| **`max_claim_fraction`** | A pool policy limiting how large a fraction of a zone a single claim may consume, preventing one archetype from exhausting an environment's address space. |
| **Buddy allocation** | Allocation strategy preferring blocks that preserve larger free runs, mitigating pool fragmentation over time (risk R27). |
| **East-west traffic resolves by DNS** | Settled decision: addresses need not be reproducible across rebuilds; what is required is idempotent allocation. Firewall rules should prefer workload selectors (network tags, security-group references) over CIDR. |

---

## 5. CMDB (Configuration Management Database)

| Level | Definition |
|---|---|
| **Level 0** | Raw files in Git (`cmdb-data/`): resolved manifests, environments, instances, one file per stack, edge files (`depends-on.json`, `provides.json`, `tenant-resources.json`), pool ledgers, and an `index.json`. The system of record. |
| **Level 1** | A published read model: `index.json` plus a JSON-LD projection served via GitHub Pages / raw content / Contents API / release asset. |
| **Level 2** | An analytical model: DuckDB over partitioned Parquet, published as a non-committed release asset, queried in-browser via DuckDB-WASM with HTTP range requests. |
| **Level 3** | An optional graph database (KuzuDB or Oxigraph), justified only once queries need variable-length, mixed-edge-type traversal (e.g. multi-hop identity/secret reachability) — not to be built speculatively. |
| **Edge (CMDB)** | A relationship extracted statically before deployment: dependency edges (from `input.from_stack_id`), capability edges (from `provides`), tenant-resource edges (from `creates_tenant_resources`). |
| **Drift workflow** | The process that keeps CMDB files matching the last successful apply; without it the CMDB "lies with confidence." |
| **DuckDB / DuckDB-WASM** | The embedded analytical database used for the CMDB level-2 model, queryable in-browser via WASM. |
| **graphology / networkx** | Graph libraries suggested for loading the level-1 JSON-LD projection into memory for graph queries at moderate scale (<~100k nodes). |
| **KuzuDB** | A candidate embedded property-graph database (Cypher, WASM) for a level-3 CMDB graph model. |
| **Oxigraph** | A candidate embedded RDF/SPARQL graph database (Rust, WASM) for a level-3 CMDB graph model. |

---

## 6. Resolution algorithm (`archetypectl resolve`) — the 17 steps

| Step group | Steps | What happens |
|---|---|---|
| **Load** | 1–2 | Load manifests, components and binding; expand `stacks[].use`; enforce `kind: demo` category rules. |
| **Graph** | 3–4 | Compute transitive closure with cycle detection; bind each capability to its single provider (a lookup, not a search — why resolution is linear rather than NP-complete). |
| **Validate** | 5–11 | Versions, traits, runtime support, conflicts, `stacks[].condition` evaluation, output-contract verification, tenant-resource authorisation. |
| **Allocate** | 12–15 | Claims (hierarchical, idempotent), firewall selectors, capacity budgets, provider version constraints. |
| **Emit** | 16–17 | Topological ordering; write `resolution.json` + `binding.tm.hcl` + ledger writes + PR comment. |

| Term | Definition |
|---|---|
| **`archetypectl`** | The (planned) CLI that runs resolution (`archetypectl resolve --instance demos-alpha`) and, per the developer guide, scaffolds new applications (`archetypectl new-app`, still deferred). |
| **`--dry-run`** | A resolution mode performing every step except ledger writes, so a validation-only PR consumes no addresses. |
| **Fails closed** | Design principle: resolution errors block the PR rather than proceeding with unresolved/ambiguous state. |
| **"Who required what, and what to change"** | The stated rule for every resolution error message: name the requirer chain and the remedy, not just the failure. |
| **No installable solution** | Diagnostic phrasing for a version conflict with no resolution, because an environment holds exactly one instance of a capability. |
| **`skipped_stacks`** | A `resolution.json` field recording which conditional stacks were not generated and why. |
| **`expiresOn`** | Required field on `kind: demo` archetypes; a scheduled job lists instances past expiry and opens a human-approved destroy PR — destruction is never automatic. |

---

## 7. Firewall selectors

| Selector | Meaning |
|---|---|
| **`purpose:<name>`** | A range this archetype itself claimed with that purpose. |
| **`zone:<name>`** | A purpose zone of the environment pool — a stable destination surface. |
| **`cidr:<literal>`** | A fixed range (e.g. health-check ranges, control-plane CIDR); used only when genuinely needed. |
| **`self`** | The stack's own workload selector (network tag, security group, NetworkPolicy label); preferred over CIDR for east-west traffic. |

---

## 8. Kafka / multi-tenant tenant resources

| Term | Definition |
|---|---|
| **Kafka (archetype, not component)** | Kafka deploys an operator and imposes a multi-tenant contract — common bus, separated tenant data — which is what makes it an archetype rather than a component. |
| **Event-bus** | The capability provided by the `kafka` archetype, representing the common multi-tenant Kafka bus. |
| **Strimzi** | The Kubernetes operator used to run Kafka. |
| **KRaft** | Kafka's Raft-based consensus mode (no ZooKeeper); a named trait used by the `kafka` archetype's cluster stack. |
| **`KafkaTopic` / `KafkaUser`** | Custom resources (tenant resources) a *consuming* archetype creates inside the Kafka provider's namespace, rather than the provider creating them; must carry the mandatory tenant prefix. |
| **ACL (Access Control List)** | Kafka-level authorisation rule; derived automatically by the `kafka` archetype from each tenant's `KafkaUser` prefix — never hand-written — to guarantee isolation. |
| **Mandatory name prefix** (`{{ instance }}-`) | Every tenant's Kafka topics/users must carry this prefix, enforced by admission policy, preventing silent collisions between tenants. |
| **Kafka quotas** | Per-`KafkaUser` limits (producer/consumer byte rate, request percentage) needed because Kubernetes `ResourceQuota` does not limit Kafka throughput. |
| **`kafka_partitions`** | A capacity key; the real ceiling of a Kafka cluster (exhausts before CPU/storage). The 4000 budget used for `demos` is a placeholder pending measurement against the intended broker count (open question). |
| **`kafka_topics` / `kafka_storage_gib` / `kafka_throughput_mibs`** | Additional Kafka capacity keys governing operator reconciliation load, retention×throughput storage, and aggregate producer throughput. |

---

## 9. Generate — Terramate & OpenTofu core concepts

| Term | Definition |
|---|---|
| **Terramate CLI** | The open-source, CLI-only orchestration tool the platform is built on; solves "stacks within stacks" composition via flat stacks plus code generation rather than nested stack blocks. Chosen over Terraform Stacks (HCP-only, not in OSS CLI or OpenTofu) and over Terragrunt (change detection at scale, native binary execution, generated code is real `.tf` Checkov can scan directly). |
| **OpenTofu** | The open-source Terraform fork used as the IaC execution engine; `tofu` is the binary invoked throughout. Decided at the outset over Terraform. |
| **Terraform Stacks** | HashiCorp's `component`/`stack`/`deployment` block model; a hosted-platform-only feature (HCP Terraform / Terraform Enterprise 2.0+), unavailable in OSS Terraform or OpenTofu — out of scope here. |
| **Module** | A reusable OpenTofu module (resources, variables, outputs, provider constraints) with no backend of its own; lives under `modules/` or a registry. |
| **Stack** (Terramate) | A directory containing `stack.tm.hcl`, a backend configuration and its own state file — the smallest unit Terramate orchestrates. |
| **Platform** (stack grouping) | A set of stacks (network + cluster + platform services) providing shared foundations for a cloud and environment; produces outputs consumed by archetype instances. |
| **Archetype instance** (generate-side) | A concrete deployment of an archetype template, bound to one platform and one environment; consumes outputs via `binding.tm.hcl`. |
| **Producer stack** | A stack that declares `output` blocks, making runtime facts available to other stacks. |
| **Consumer stack** | A stack that declares `input` blocks, pulling runtime facts from a producer stack. |
| **Dedicated environment** | A platform serving exactly one archetype instance. |
| **Shared environment** | A platform serving many archetype instances simultaneously (typical for demos). |
| **Globals** | Terramate's compile-time data layer, inherited down the directory tree and overridable at any level; used for values known before apply. Rule of thumb: globals for anything known before apply, outputs sharing only for values knowable after apply. |
| **Outputs Sharing** (`sharing_backend`/`output`/`input`) | Terramate's **experimental** mechanism for passing runtime facts (VPC IDs, cluster endpoints, OIDC ARNs) between stacks that cannot be known at generate time. Requires `experiments = ["outputs-sharing"]`. Accepted despite being experimental (risk R1); contracts centralised in `imports/contracts/` so a breaking change is a bounded edit. |
| **`sharing_backend`** | The root-level block naming the transport for outputs sharing: `type` (the bare, unquoted keyword `terraform`), `filename` (conventionally `_sharing_generated.tf`), and `command` (e.g. `["tofu","output","-json"]`, run inside the producer stack directory, must output JSON). Defined once at repo root. |
| **`output` block** | Declares a producer's contract: a named value tied to a `backend`, evaluated in generated OpenTofu code, with optional `description`/`sensitive`. Renaming the label is a breaking change for every consumer. |
| **`input` block** | Declares a consumer's contract: generates a `variable "<label>"`, referencing a producer via `from_stack_id`, evaluating an expression over `outputs.*`, with an optional `mock` used only under `--mock-on-fail`. |
| **`from_stack_id`** | The `input`-block attribute naming the producer stack's ID. **Accepts an expression, not just a literal** — this is "an assumption taken as a design decision": the entire late-binding model depends on it, letting one hand-written contract reference `global.platform.cluster_stack_id` and serve every bound instance. If it turns out to be literal-only, the resolver must generate a contract file per instance instead — more machinery, not a redesign. |
| **`mock` (input attribute)** | A fallback value used only under `--mock-on-fail`, essential for PR previews where the real producer output doesn't exist yet. Must match the real value's type exactly — a mismatch type-checks in plan and fails on apply. Convention: prefix every mock with `mock-`. |
| **`mock_on_fail`** | Controls whether a failed outputs-sharing read falls back to the mock. **Must be `true` in preview and `false` in deploy** — kept in separate named `script` blocks so it cannot be got wrong. |
| **`stack` block** | Declares stack identity (`id`, `name`, `tags`) and ordering (`after`/`before`). `stack.id` must be globally unique, stable, and human-derivable (hand-typed into binding files): `<cloud>-<env>-<capability>[-<instance>]`. |
| **`stack.after` / execution ordering** | Explicit dependency declaration Terramate uses to order runs. **Outputs sharing does not itself create execution order** — every `input` needs a matching `after`, or a consumer can silently run before its producer and resolve a stale value with no error (risk R2, the top risk). |
| **`generate_hcl`** | The Terramate code-generation primitive — "the base layer." One generator per capability, using a `condition` expression over globals (or a `stack_filter`) to decide which stacks receive which emitted HCL. Generated files are prefixed `_`. |
| **Generator versioning** | Generators live under `imports/generators/v1/` etc., gated by `condition = global.generators.version == "v1"`, so a breaking change ships as `v2/` and migrates environment-by-environment by flipping a global. |
| **`script` block** (`terramate script`) | Names a multi-step workflow (init/plan/apply) invokable identically from a laptop or CI; sharing flags (`enable_sharing`, `mock_on_fail`) are set per command here. Separate `preview`/`deploy` scripts prevent mock behaviour from being swapped. |
| **`assert` block** | Fails `terramate generate` when an invariant is violated, enforcing architectural rules (e.g. production clusters must have deletion protection) rather than merely documenting them. |
| **`terramate generate`** | Runs all generators and writes generated files. **`terramate generate --check`** is gate **G0**: ensures nobody hand-edited a generated file, since the next `generate` would silently revert the fix. |
| **`terramate run`** | Orchestrates actual `tofu` invocations across stacks (e.g. `terramate run --tags <cloud>:<env>:network --enable-sharing -- tofu apply`). Supports `--changed` for incremental runs and tag-based `--tags` selection as a fallback ordering mechanism when globals-derived `stack.after` fails to resolve (which fails **silently** — test this deliberately). |
| **`--enable-sharing`** | The `terramate run` flag activating outputs-sharing resolution for that invocation. |
| **`--mock-on-fail`** | Falls back to the input's declared `mock` on a failed outputs-sharing read; must never appear in a real deploy path. |
| **`terramate.tm.hcl`** | Repository-root config: pins `required_version`, declares `experiments` (required to unlock `sharing_backend`/`input`/`output`), sets `config.git` defaults for change detection, and `config.run.env`. |
| **`imports/`** | Directory convention holding only importable configuration (mixins, generators, contracts, scripts) — never actual stacks. Terramate must never orchestrate anything under it. |
| **`imports/mixins/`** | Per-cloud backend and provider generator fragments (`backend_gcp.tm.hcl`, `provider_gcp.tm.hcl`) plus common label injection. |
| **`imports/generators/v1/`** | One generator per capability (`gen_network.tm.hcl`, `gen_cluster.tm.hcl`, ...) — "the base layer." |
| **`imports/contracts/`** | Output/input contract definitions per capability (`contract_network_gcp.tm.hcl`, `contract_cluster_gke.tm.hcl`), centralising the sharing contract for review in one place. |
| **`imports/scripts/`** | Named `script` block definitions (`tofu.tm.hcl` defining `preview`/`deploy`). |
| **Generated file naming convention** | Generated files are committed to git and prefixed `_` (`_main.tf`, `_sharing_generated.tf`, `_providers.tf`, `_backend.tf`), sort together, and are covered by `CODEOWNERS`. |
| **`_sharing_generated.tf`** | The default filename holding derived `variable`/`output` blocks produced from `input`/`output` declarations. |
| **`tm_cidrsubnet`** | A Terramate global-evaluation function computing subnet/pod/service CIDR ranges from a parent CIDR at generate time — compile-time, reviewable in diffs. |
| **`tm_dynamic`** | A `generate_hcl` construct (Terraform's `dynamic`, analogously) iterating a compile-time list (e.g. `global.tenants`) to emit repeated blocks. |
| **`tm_contains` / `tm_can` / `tm_regex`** | Terramate helper functions used in `assert` expressions: list membership, catching evaluation errors, regex validation. |
| **`terramate debug show globals`** | Inspects a stack's fully resolved globals. |
| **`terramate experimental run-graph`** | Inspects the computed execution order between stacks. |
| **`config.tm.hcl`** | Per-directory-level file (cloud layer, environment layer) declaring `globals` inherited by everything beneath it. |
| **Staged apply (first deployment)** | The required manual ordering for a brand-new environment's very first apply — network → cluster → platform-services → instance — because a consumer's provider block cannot reach a resource that doesn't exist yet. After that, `terramate run --changed` handles the whole graph in one pass. |

---

## 10. Traps (cross-cutting — read before writing code)

| Trap | Why it matters |
|---|---|
| **Outputs sharing does not create execution order** | Every `input` needs a matching `after`; an unresolved ordering applies a stale value with **no error** (risk R2, top risk; gate **G1** exists specifically to catch it). |
| **`mock_on_fail` true-in-preview / false-in-deploy** | Must use separate named `script` blocks, or a deployment can silently fall back to a mock and apply nonsense. |
| **Mocks must be type-correct** | A base64 field mocked as `"mock"` breaks `base64decode()`; a list field mocked as a string type-checks locally and explodes on apply. Prefix every mock with `mock-`. |
| **Never share secrets through outputs sharing** | Values land in `TF_VAR_*` environment variables, which leak into logs and process trees. Share references (secret ID, ARN, key name); consumers fetch under their own identity. Auth tokens (`google_client_config`, `aws_eks_cluster_auth`) are always fetched locally, never shared. |
| **GKE endpoint has no scheme; EKS endpoint includes `https://`** | Classic copy-paste bug between per-cloud guides. |
| **Deterministic naming breaks dependency cycles** | The EKS subnet-tagging cycle (network needs the cluster name, cluster needs the subnets) is solved by promoting `cluster_name` to a global. This is the general remedy whenever outputs sharing appears to need a cycle. |
| **Outputs sharing models 1-to-N, not N-to-1** | `input` blocks cannot be generated from a dynamic list (fan-in). Gateway API removes the fan-in problem entirely — the reason it is the target design, with the URL-map approach only a fallback. |
| **Avoid `kubernetes_manifest` for Gateway API / Gatekeeper CRs** | Requires the CRD and API server reachable **at plan time**, breaking PR previews. Package CRs in the archetype's own Helm chart, deploy with `helm_release`. |
| **The Keycloak ↔ Gateway bootstrap cycle** | Keycloak's own `HTTPRoute` must carry **no** `SecurityPolicy`, and the Gateway's OIDC discovery must resolve through the in-cluster Service, not the public hostname. Without both, a cold environment does not start and the cause is not obvious. |
| **`failurePolicy: Fail` can lock you out of the cluster** | Gatekeeper would reject its own recovery. Mitigated by `exemptNamespaces` for `kube-system`/Gatekeeper's own namespace, ≥3 replicas with a PDB, and `Ignore` everywhere except production. |
| **ECS: never share the task execution role between tenants** | A shared execution role can read every tenant's secrets. Use a per-instance role even though it duplicates ECR/logs permissions. |
| **AWS `TargetGroupBinding` can reference any target group in the account** | On a shared cluster, a tenant could redirect another's traffic. Only the `gateway` archetype creates them; RBAC denies the CRD to application namespaces. |
| **OIDC trust policies: `StringEquals` on the exact `sub`, never `StringLike` with a wildcard** | The most common AWS OIDC misconfiguration (risk R12). |
| **Pod secondary ranges are immutable** | Sizing them for too few nodes means rebuilding the cluster (risk R26). |

---

## 11. Per-cloud runtime guides

### 11.1 Common shape

All five runtime guides (GKE, EKS, Cloud Run, ECS Fargate, AKS) follow the same graph — `network → runtime (consumer+producer) → platform services → data / app` — differing only in *which facts cross each edge*.

| Term | Definition |
|---|---|
| **`workload_identity_pool`** (GKE) | GCP's per-project identity namespace (`<project>.svc.id.goog`) binding Kubernetes service accounts to Google service accounts; a cluster output. |
| **Workload Identity (GKE)** | GCP's mechanism binding a Kubernetes SA to a Google SA via the workload identity pool; must be enabled cluster-wide and per node pool, or pods fall back to sharing the node SA. Binding must never use a wildcard (`POOL[*/*]`) — risk R15. |
| **`oidc_provider_arn` / `oidc_provider_url`** (EKS) | The two OIDC facts an EKS cluster stack must output for IRSA trust policies to be written — AWS needs two facts where GCP/Azure need only one. |
| **IRSA (IAM Roles for Service Accounts)** | EKS's mechanism binding a Kubernetes SA to an IAM role via OIDC federation and a trust policy scoped by `sub`/`aud`. Described as "the canonical outputs-sharing use case on AWS," since the trust policy cannot be written without the OIDC ARN/URL the cluster stack's apply produces. |
| **OIDC provider (EKS)** | The per-cluster OIDC identity provider shared by every archetype instance on that cluster — a cluster rebuild invalidates every IRSA role fleet-wide (risk R11). |
| **EKS Pod Identity** | Newer AWS alternative to IRSA, associating pods with IAM roles via the EKS API instead of an OIDC trust document; if adopted, the cluster stack outputs `pod_identity_agent_ready` instead of the two OIDC facts. |
| **EKS Access Entries (API auth mode)** | Modern, IAM-audited mechanism for cluster access, replacing the legacy `aws-auth` ConfigMap (no audit trail, corrupts under concurrent writes). Owned solely by the `eks` stack. |
| **`oidc_issuer_url`** (AKS) | The AKS cluster output naming the OIDC issuer every federated workload-identity credential depends on. |
| **`azurerm_federated_identity_credential`** | Binds a user-assigned managed identity to a specific, namespace-and-service-account-scoped OIDC `subject` — never a wildcard. |
| **UAMI (User-Assigned Managed Identity)** | An Azure identity created per workload, used instead of the cluster's system-assigned identity or the kubelet identity, so a workload never inherits pipeline or node privilege. |
| **Kubelet identity** | The AKS node-level identity, scoped to ACR pull only; must never be reused as a workload identity since it is reachable from the node. |
| **`local_account_disabled`** | AKS setting removing the static admin kubeconfig, forcing Entra ID + Azure RBAC for cluster access — prevents `kube_config` from becoming a bare credential in state (risk R25). |
| **Node resource group** (AKS) | A second resource group AKS creates and manages automatically alongside the cluster; must not be Terraform-managed, or the cluster reconciler fights the plan. |
| **Azure CNI Overlay** | AKS's default pod-networking mode: pods get addresses from a private, non-routable overlay CIDR rather than VNet IPs, removing VNet IP pressure. |
| **Azure CNI (traditional)** | AKS mode where every pod gets a routable VNet IP; used only when pods must be directly reachable from outside the cluster. |
| **Azure CNI Powered by Cilium** | AKS mode combining overlay addressing with an eBPF dataplane, chosen when NetworkPolicy is needed at eBPF performance. |
| **AGFC (Application Gateway for Containers)** | Azure's Gateway API implementation; usable BYO (bring-your-own), provisioned in Terraform. Itself an L7 gateway, so placing Envoy Gateway behind it is a redundant double hop. |
| **Secrets Store CSI driver** | AKS's mechanism for mounting Key Vault secrets into pods via workload identity, so Kubernetes Secrets are never the source of truth. |
| **`artifact_registry_repo` / `cloud_armor_policy_id`** (Cloud Run) | Network-stack outputs a Cloud Run runtime stack consumes. |
| **Cloud Run service agent** | The GCP-managed identity (`service-<project-number>@serverless-robot-prod.iam.gserviceaccount.com`) that actually pulls container images for a Cloud Run service — distinct from the service's own runtime SA. Granting pull permissions to the runtime SA instead is "a classic first-deployment failure." |
| **Direct VPC egress** | The preferred (newer) mechanism for Cloud Run to reach VPC-private resources without a managed connector; requires a dedicated `/24` subnet minimum. |
| **Serverless VPC Access connector** | The legacy mechanism for Cloud Run VPC access, using a fixed connector resource/CIDR. |
| **Binary Authorization** | Attestation-based control requiring container images to carry verified attestations before deployment (GKE and Cloud Run). |
| **Metadata concealment (GKE)** | Disabling legacy GCE metadata endpoints (`metadata.disable-legacy-endpoints = true`) so pods cannot read the node SA's token directly, which would defeat Workload Identity. |
| **Shielded GKE nodes** | GKE nodes with secure boot and integrity monitoring enabled — part of the GKE security baseline. |
| **gVisor** | Cloud Run's per-service kernel-level sandbox, making a shared Cloud Run platform materially safer than a shared GKE node pool for semi-trusted demo workloads. |
| **Cloud Armor** | GCP's edge WAF/security-policy service — bypassed if a Cloud Run service's `ingress` is `ALL` or its invoker is `allUsers` with no load balancer in front (risk R14, "the single most commonly misconfigured Cloud Run setting"). |
| **`cluster_arn` / `alb_listener_arn` / `task_role_boundary_arn`** (Fargate) | Runtime-stack outputs a Fargate consumer stack needs. |
| **Task execution role** (ECS) | The IAM role used before the container starts: pulls the image from ECR, creates log streams, reads task-definition secrets. Not reachable from inside the container. |
| **Task role** (ECS) | The IAM role the application code assumes for its whole life, reachable via the task metadata endpoint. Must always be distinct from the execution role — the platform's cardinal ECS rule. |
| **Per-instance execution role** | On a shared ECS cluster, a dedicated execution role scoped to one instance's own secrets — sharing it would let the role starting tenant A's tasks read tenant B's secrets (risk R13). |
| **Permissions boundary (ECS)** | Attached to both execution and task roles, published by the platform, preventing privilege escalation from a tenant's own stack — "the multi-tenancy keystone" for ECS. |
| **Confused deputy protection** | Trust-policy conditions (`aws:SourceArn` + `aws:SourceAccount`) pinning role assumption to a specific account and cluster, blocking cross-account assumption via the ECS service principal. |
| **`secrets` block vs `environment`** (ECS task definition) | Sensitive values must go in `secrets` (resolved by the execution role at start, never appearing in `DescribeTaskDefinition`), never in plaintext `environment`. |
| **ECS Exec** (`enable_execute_command`) | Interactive shell into a running Fargate task; disabled by default and blocked by assertion in production. |
| **`readonlyRootFilesystem`** | Container setting blocking most post-exploitation tooling by preventing writes to the root filesystem. |
| **Fargate micro-VM isolation** | Each Fargate task gets its own micro-VM — per-task compute isolation stronger than a shared EKS node pool's shared-kernel exposure. |
| **Listener priority allocation** | A shared, finite namespace of ALB listener-rule priorities, allocated in ranges per tenant (`config.tm.hcl`, e.g. `alpha = 100–199`) so concurrent PRs cannot collide. |
| **EKS Fargate profiles** | A compute option (not a separate platform) selecting workloads by namespace/labels, using a Fargate pod execution role instead of the node role; unsupported: DaemonSets, privileged containers, host networking. |
| **VPC endpoints (AWS)** | Interface/Gateway endpoints (ECR API/DKR, S3, CloudWatch Logs, Secrets Manager/SSM, STS, SSM Messages) letting Fargate tasks in private subnets reach AWS services without a NAT gateway — "the best-practice baseline" over NAT. |
| **Envelope encryption (EKS secrets)** | Encrypting Kubernetes secrets (etcd at rest) under a customer-managed KMS key — part of the EKS security baseline. |
| **IMDS hop limit / IMDSv2** (EKS) | Restricting the EC2 instance metadata service to hop limit 1 and requiring IMDSv2, preventing a compromised pod from reaching the node's instance-profile credentials. |

### 11.2 Isolation boundaries

| Runtime family | Boundary |
|---|---|
| **Kubernetes runtimes** (GKE, EKS, AKS) | The **namespace** — shared kernel on shared nodes, higher exposure for semi-trusted workloads. |
| **Serverless runtimes** (Cloud Run, ECS Fargate) | The **service / task** — per-workload isolation, a stronger default for shared demo environments. |
| **Autopilot / EKS Auto Mode / AKS Automatic** | Managed Kubernetes modes across the three clouds that restrict privileged workloads differently; modelled as traits rather than special-cased code. |
| **`workload_identities`** | Normalised capacity key covering GCP service accounts, AWS IAM roles and Azure managed identities under one budgeted key. |

---

## 12. Edge attachment and Gateway API

| Term | Definition |
|---|---|
| **`iac-owned-edge` trait** | Earned when the load-balancer attachment mechanism is fully created and tracked in Terraform state — true for AWS `TargetGroupBinding` and Azure AGFC, **false** for GCP's controller-managed standalone NEG (the gap is recorded rather than hidden). |
| **Standalone NEG (Network Endpoint Group)** | GCP's mechanism exposing pods to a load balancer; created by the GKE NEG controller (not Terraform) and referenced as a `data` source. NEGs are zonal, so `minReplicas` must be ≥ the number of zones. |
| **`TargetGroupBinding`** | An AWS Kubernetes CRD binding a Service to an ALB/NLB target group provisioned entirely in Terraform. Never paired with `aws_lb_target_group_attachment`. On a shared cluster it can reference **any** target group in the account, so only the `gateway` archetype may create it (risk R21). |
| **Envoy Gateway** | The chosen Gateway API reference implementation for ingress; native OIDC via `SecurityPolicy`. Its edge-facing Service is generated by the controller (via `EnvoyProxy`), not hand-written. |
| **`EnvoyProxy`** | Custom resource configuring the controller's generated proxy Service (type, cloud annotations, replica count, topology spread); supports `mergeGateways` to share one proxy fleet across multiple Gateways. |
| **`GatewayClass`** | The Gateway API resource referencing an `EnvoyProxy` configuration; deployed via `helm_release`, never `kubernetes_manifest`. |
| **`HTTPRoute`** | A Gateway API resource in the application's namespace, attaching to a Gateway via `parentRefs` — inverts the routing dependency so the edge no longer needs to know its tenants. |
| **`parentRefs`** | The `HTTPRoute` field naming the Gateway(s) it attaches to. |
| **`allowedRoutes`** | The Gateway-side field (`namespaces.from: Selector`) controlling which namespaces/routes may attach — replaces a fan-in list of tenants. |
| **`SecurityPolicy`** | An Envoy Gateway CR providing native OIDC authentication at the gateway. Keycloak's own `HTTPRoute` must carry none, to avoid the bootstrap cycle. |
| **One Gateway per environment** | The mandated pattern — not one per tenant — since each Gateway spawns its own Envoy Deployment/Service/NEG. |
| **Fail-open vs fail-closed (IdP failure)** | The explicit decision of whether the Gateway keeps serving (fail-open) or stops authenticating everything (fail-closed) if Keycloak is down. Acceptable to fail in `demos`; production needs Keycloak HA plus an explicit choice. |

---

## 13. Identity, IAM and security baseline

| Term | Definition |
|---|---|
| **OIDC federation (pipeline identity)** | No long-lived cloud credentials (SA JSON keys, IAM access keys) are ever stored in CI; the pipeline authenticates via OIDC token exchange. |
| **Plan identity vs apply identity** | Plan is read-only and reachable from any branch/PR; apply is write-only and reachable only from a protected GitHub Environment with required reviewers. |
| **Workload Identity Federation (GCP, pipeline)** | `google_iam_workload_identity_pool`/`_provider` letting GitHub Actions assume a GCP SA via OIDC, gated by an `attribute_condition`. |
| **`attribute_condition`** | The required GCP WIF condition restricting which GitHub repository can impersonate the pool; omitting it lets any GitHub repository in the world impersonate it. |
| **`attribute.environment` claim** | A GitHub OIDC claim present only when a workflow job declares `environment:`; binding the apply SA to it makes the apply role unreachable without the environment approval gate. |
| **`aws_iam_openid_connect_provider`** | The AWS resource registering GitHub's OIDC issuer for `AssumeRoleWithWebIdentity`, paired with `sts.amazonaws.com` as audience. |
| **`sub` / `aud` conditions (AWS OIDC trust policy)** | `sub` must use `StringEquals` on the exact `repo:ORG/REPO:environment:ENV` string (never `StringLike` with a wildcard — risk R12); `aud` must always be present to reject tokens minted for other audiences. |
| **Permission boundary (pipeline)** | An IAM boundary on the pipeline's apply role denying it the ability to create IAM principals more powerful than itself. |
| **`max_session_duration`** | The 1-hour cap on an assumed pipeline role's session, limiting exposure from a leaked session token. |
| **Session naming** (`gha-<run_id>-<run_attempt>`) | Ties every CloudTrail/audit-log event back to a specific GitHub Actions run and commit. |
| **Role segregation matrix** | Maps preview/deploy/drift/destroy jobs to distinct GCP/AWS identities and GitHub environment gates; destroy gets its own identity and approver group since it can take down every tenant on a shared platform. |
| **`-lock=false` (plan)** | Lets `tofu plan` run without acquiring the state lock — what allows a genuinely read-only plan identity. |
| **State backend permissions (outputs sharing)** | A consumer stack needs read (and decrypt, if state encryption is used) access to the producer's state — the most common first-week adoption blocker, since `tofu output -json` runs inside the producer's own directory. |
| **OpenTofu state encryption** (`encryption` block) | Client-side state/plan encryption; a consumer then needs the producer's encryption key too, so keys should be scoped one per environment, not per stack. |
| **What never crosses the sharing boundary** | Outputs sharing resolves into `TF_VAR_*` environment variables (visible in crash dumps, subprocess environments, CI logs, `ps` output); secrets must never be shared this way — only references, fetched locally under the consumer's own identity. |
| **Guard rails above the pipeline** | Three-layer defence in depth: Org Policies/SCPs/Azure Policy (cannot be disabled by the pipeline) → permission boundaries (cannot be escaped by a tenant) → least-privilege role policies (reviewed per PR). |
| **Namespace as tenancy boundary** | On GKE/EKS, since workload identity is scoped by namespace, the namespace itself is the multi-tenant isolation boundary and must never be shared between instances. |

---

## 14. Environment management

| Term | Definition |
|---|---|
| **Dedicated / Shared / Hybrid models** | Platform-to-instance topologies: Dedicated (1:1, isolation = cloud account/project), Shared (1:N, isolation = namespace + IAM), Hybrid (shared network, dedicated clusters per instance group). |
| **`global.platform.model`** | The global flag (`"dedicated"` or `"shared"`) conditioning generator output — e.g. tenancy guard rails only emitted when `"shared"`. |
| **Tenancy guard rails (shared model)** | Per-instance resources generated only for shared-model instances: a dedicated `kubernetes_namespace` with `pod-security.kubernetes.io/enforce: restricted`, a `kubernetes_resource_quota`, a `kubernetes_limit_range`, a default-deny `kubernetes_network_policy`. |
| **`global.quota`** | Required globals object (cpu, memory, pods, loadbalancers) shared-model instances must define, enforced by assertion. |
| **Tag-scoped destroy** | The mandated shared-environment teardown (`terramate run --tags instance:<name> --reverse ...`) — never a path/`--changed`-based selector, which could sweep in platform stacks. |
| **`protected` tag** | Marks platform stacks so CI refuses to destroy them outside a break-glass workflow. |
| **Reference counting (platform destroy)** | Counting instances still bound to a shared platform before allowing the platform itself to be destroyed. |
| **Ephemeral environment** (`ephemeral-*`) | A short-lived platform (e.g. `ephemeral/conf-2026-q3`) created by copying `demos/` and changing three globals (`env`, `project_id`, `vpc_cidr`); expiry handled via a human-approved destroy PR, never automatic. |
| **Environment promotion (globals diff)** | Moving config from `demos` → `dev` → `qa` → `prod` is purely a change in `config.tm.hcl` globals values (node counts, release channel, deletion protection, backup retention) — identical generators and contracts everywhere. |
| **CMDB integration (Terramate)** | `terramate list --json` (logical, pre-apply inventory) and `terramate run --changed -- tofu show -json` (physical, post-apply inventory) as CMDB data sources — better than parsing state files directly. |

---

## 15. Policy, Gatekeeper and CI/CD gates

| Term | Definition |
|---|---|
| **Three enforcement points** | CI (conftest + Checkov, every runtime) → cloud control plane (Org Policy/SCP/Azure Policy, every runtime, not evadable) → cluster admission (Gatekeeper, **Kubernetes runtimes only**). None subsumes the others. |
| **Runtime parity gap** | Cloud Run and ECS Fargate have no Kubernetes admission layer, so the `policy` capability exists only where `cluster` does; serverless runtimes substitute coarser but non-evadable cloud control-plane controls (risk R37). |
| **Resolver vs OPA division of labour** | The resolver **computes** (closure, allocation, ordering, ledger writes); OPA **asserts** (stateless invariant checks on what the resolver/generators produced) — OPA never re-resolves anything, giving defence in depth against resolver bugs. |
| **G0 — generation integrity** | `terramate generate && git diff --exit-code` on every PR; always blocking. Prevents a hand-edit to `_main.tf` being silently reverted. |
| **G1 — structure and composition** | `conftest test --policy policy/ --data registry/ ...` on every PR; always blocking. Enforces the `input`↔`after` ordering invariant (R2), stack-naming conventions, instance tagging, no-secret-output rule. |
| **G2 — static security scan** | `checkov -d . --framework terraform` on every PR; blocking on HIGH/CRITICAL. Sees the module *call*. |
| **G3 — plan scan** | `checkov -f plan.json --framework terraform_plan` + `conftest --namespace terraform`, run before apply; blocking on HIGH/CRITICAL. Sees the module *result*, catching misconfigurations reachable only with a particular globals combination. |
| **Checkov** | Static/plan IaC security scanner; the "standard library" of known cloud misconfiguration checks, complementary to OPA/Rego (which encodes platform-specific rules Checkov cannot express). Config in `.checkov/gcp.yaml`, `.checkov/aws.yaml`. |
| **conftest** | Stateless CLI policy tool consuming `registry/*.json` as `--data`; chosen for CI policy checks instead of running an OPA server. |
| **check-jsonschema** | CLI tool validating manifests, component files, environment bindings and pool ledgers against JSON Schemas before resolution runs. |
| **`conftest verify`** | Runs the Rego policies' own unit tests (`policy/*_test.rego`) so a rule that never fires does not give false confidence (risk R36). |
| **`archetypectl enrich`** | Custom tool scanning each stack for `from_stack_id`/`after` declarations, emitting `consumes[]` and `after_ids[]` fields, since `terramate list --json` does not itself expose `input` blocks — kept small and standalone so the Rego stays portable and testable against fixtures. |
| **`skip-check` (Checkov)** | Per-cloud config directive suppressing a specific check (e.g. `CKV_GCP_69` for an intentionally public demo cluster endpoint); every suppression requires a comment naming the reason/scope and must not leak into production config. |
| **Self-managed Gatekeeper** | The chosen deployment model on all three clouds instead of managed add-ons, because managed alternatives are mutually exclusive with a self-managed install (AKS refuses its add-on if Gatekeeper v3 is present), restrict custom templates, and would mean three different behaviours to debug. |
| **Gatekeeper, not Kyverno** | Chosen because the team already writes Rego for conftest — one policy language. Rules are **not** literally reusable between them, only the language and helper libraries, because Gatekeeper's input is an `AdmissionReview`, not `resolution.json`. |
| **`ConstraintTemplate`** | The Gatekeeper CR type wrapping a Rego policy for admission enforcement. |
| **`custom-templates` trait** | Declared by an archetype needing its own `ConstraintTemplate`s; causes the resolver to reject a managed-policy binding that lacks this trait (e.g. Azure's managed add-on). |
| **No Gatekeeper mutation** | The generator emits labels; Gatekeeper only validates them. One writer, one validator — mutation would make changes invisible in Terraform diffs and split ownership of the label list. |
| **`enforcementAction`** | Gatekeeper constraint setting (`warn` for ephemeral/demos, `deny` for dev/qa/prod); new rules always start in `dryrun` before promotion. |
| **`failurePolicy`** | Gatekeeper webhook setting (`Ignore` everywhere except production, `Fail` in production) controlling behaviour when the webhook is unreachable. |
| **`exemptNamespaces`** | Gatekeeper config excluding `kube-system` and the Gatekeeper namespace from enforcement, so `failurePolicy: Fail` cannot lock out the platform's own recovery. |
| **Layer 2b (policy)** | Admission control's architectural placement — between the cluster (layer 2) and platform services (layer 3) — because admission must precede everything it governs. |
| **The single registry** (`registry/{capabilities,traits,zones,labels}.yaml`) | The sole source of truth from which the JSON Schema `enum` blocks, the `conftest --data` JSON bundle, and the Gatekeeper chart's `values.yaml` are all generated. **Never hand-edit an `enum` in `schemas/`** — that is a bug (risk R34). |
| **`registry-generate`** | The (not-yet-written) tool generating schema enums, conftest data bundle and Gatekeeper chart values from `registry/*.yaml`; guarded in CI by `registry-generate --check`, analogous to `terramate generate --check`. Roadmap phase 2c's first task. |

---

## 16. CI/CD workflows

| Term | Definition |
|---|---|
| **Preview workflow** | The PR pipeline: G0 → Checkov static scan → cloud OIDC auth → `terramate script run --changed tofu preview` (sharing + mocks on) → Checkov plan scan → PR comment with changed stacks. |
| **`fetch-depth: 0`** | Required checkout setting so Terramate's change detection (compares against `main`) has full git history; a shallow clone silently reports zero changed stacks. |
| **Deployment workflow** | The merge-to-main pipeline, gated by a GitHub `environment: production` (required reviewers), running `terramate script run --changed tofu deploy` with mocks off, then a CMDB sync script. |
| **Drift workflow** | A scheduled job running `tofu plan -detailed-exitcode -lock=false` per cloud selector to detect configuration drift without applying. |
| **Policy gate build inputs** | The chain producing conftest's evaluation inputs: `registry-generate --check` → `archetypectl resolve --dry-run > resolution.json` → `terramate list --json > stacks.json` → `archetypectl enrich stacks.json`. |
| **`mise`** | Tool-version pinning manager (`mise.toml`, `jdx/mise-action`) pinning Terramate, OpenTofu and Checkov versions consistently across developer machines and CI. |

---

## 17. Roadmap phases

| Phase | Focus |
|---|---|
| **Phase 0** | Validate assumptions — a one-week throwaway-repo spike confirming: `from_stack_id` resolves an inherited global and accepts interpolation; `stack.after` resolves globals-derived paths or falls back to tag filters (and fails silently if not — test deliberately); `--mock-on-fail` behaviour; cross-project/account state reads with OIDC roles; private control-plane reachability from the chosen runner type. **These are an afternoon's work and gate everything else.** |
| **Phase 0b** | Resolver skeleton — JSON Schema validation, resolution steps 1–8 (no ledger writes), proving a resolver-generated `binding.tm.hcl` drives `terramate generate` unchanged. |
| **Phase 1** | One cloud, one shared platform — root config, `sharing_backend`, mixins, `gen_network`/`gen_cluster`, first demos platform, preview/deploy workflows with G0/G1, one archetype instance. |
| **Phase 2** | Second cloud — second mixin/generator set proving contract files are cloud-agnostic; adds G2 plan scanning and permission boundaries. |
| **Phase 2a** | Azure parity — landing-zone/environment/AKS archetypes, the CNI Overlay-vs-traditional decision (made before first cluster, since immutable), edge choice (AGFC BYO or Envoy Gateway behind an internal LB, not both), and an acceptance test that a layer-5 app manifest deploys to Azure unedited. |
| **Phase 2b** | Serverless runtimes — Cloud Run and ECS Fargate generator branches behind a `global.platform.runtime` switch, reusing existing network/data stacks. |
| **Phase 2c** | Policy layer — sub-phased: registry → `archetypectl enrich` → G1 advisory → G1 blocking → policy tests → Gatekeeper at layer 2b (ephemeral-first, dryrun, gradual promotion). |
| **Phase 3** | Multi-tenancy — second/third shared-platform instances, namespace/quota/NetworkPolicy generation, destroy guard rails. |
| **Phase 4** | Dedicated environments and CMDB — per-cloud dedicated `prod` platforms, the promotion globals matrix, CMDB levels 1–2 sync, drift workflow. |
| **Phase 5** | Hardening — generator `v2` migration rehearsal, break-glass runbooks, contract deprecation process. |

---

## 18. Developer guide — repository and manifest model

| Term | Definition |
|---|---|
| **Monorepo per application** | One repository holds every service of one application, so a cross-service contract change is one version, one PR, one CI run. |
| **Stack** (developer-guide sense) | One per service within an application; `stacks[].after` gives deployment ordering. |
| **`hasFrontend`** | A `condition:` predicate true when a `frontend` block is present in the manifest; an application with no UI generates no `web` stack and claims no hostname. |
| **`libs/`** | Shared code directory; any service listing it in `build.deps` rebuilds whenever it changes — an overly coarse library triggers unnecessary rebuilds. |
| **`archetype-manifest.schema.json`** | The manifest's JSON Schema, `additionalProperties: false`, generated from `registry/`; extending the manifest (e.g. adding `language: java17`) requires extending this schema first. |
| **Build and deploy specs extend `manifest.yaml`** | Settled decision: a parallel `build.yaml`/`deploy.yaml` is a third place to declare the same dependency and it drifts. |
| **Change detection** | `git diff --name-only <merge-base>..<head>` mapped onto `build.context`/`build.deps` to decide which services rebuild; an unmatched path rebuilds everything (fail-safe). |
| **capacity block** | Manifest section (cpu, memory, db connections, ingress routes, workload identities) treated as a budget draw against the shared environment; the resolver sums all tenants' draws and fails the PR if the total is exceeded. |
| **Platform review for capacity increases in shared environments** | Settled decision: raising `capacity` in a shared environment needs platform-team review (the resolver alone sees every tenant's draw); a dedicated environment needs none. |

---

## 19. Branches, environments and GitFlow

| Branch | Deploys to | Notes |
|---|---|---|
| **`feature/*`** | Nothing (PR preview only) | Full PR preview: build, tests, image scan, `archetypectl resolve --dry-run`, `tofu preview` with mocks. Nothing applied unless an `ephemeral-*` environment is explicitly requested. |
| **`develop`** | `dev`, automatically on merge | Image tag `2.5.0-dev.<n>.g<sha>`. |
| **`release/x.y`** | `qa`, automatically | Image tag `2.5.0-rc.<n>`. |
| **`main`** | `prod`, only on a `vX.Y.Z` tag | Manual approval via a GitHub Environment `production` with required reviewers; the image is **promoted** (re-tagged), never rebuilt. |
| **`hotfix/*`** | `qa` then `prod` | Fast path from `main`, skipping `develop`/release but not `qa`, the image scan, or production approval. Must merge back to `main` **and** `develop` (and any open `release/x.y`); a CI gate blocks the merge to `main` until the back-merge PR to `develop` exists. |

| Term | Definition |
|---|---|
| **GitFlow** | The branching model used; the branch alone decides the deployment environment — there is no "deploy this branch to prod" button. |
| **`ephemeral-*` environment** | A per-request, temporary environment claimed against the ephemeral supernet; destroyed on PR close. |
| **Promotion gate** | Refuses to deploy to `prod` a digest with no recorded successful `qa` deployment — makes "promoted, not rebuilt" enforceable. |

---

## 20. Versioning and release

| Term | Definition |
|---|---|
| **`metadata.version`** | The archetype's single application-wide version (not per-service); generated from the Git tag and committed so the manifest is Terramate-readable; never hand-authored. |
| **`archetypectl version --check`** | CI gate recomputing the version from the Git ref and failing if `metadata.version` differs from the tag. |
| **One version per application, not per service** | Settled decision: a per-service scheme makes "what was running together on Tuesday" unanswerable and removes rollback's target. |
| **Semver/OCI tag conflict** | `+` is legal in semver but illegal in the OCI image tag charset (`[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}`); the pipeline replaces `+` with `.` when deriving the image tag. |
| **Version bump rules** | **MAJOR** — removed/changed endpoint, provided-capability contract change, or any irreversible migration (even a one-line diff). **MINOR** — backward-compatible additions, expand-phase migrations, new services, widened `requires` ranges. **PATCH** — bug fixes, dependency bumps, capacity/resource changes with no contract change. No release for docs/tests/CI-only changes. |
| **Irreversible migration** | A schema change (`DROP COLUMN`, `DROP TABLE`, a `NOT NULL` addition, a narrowing type change) that permanently removes the ability to run an earlier application version against the database; always a MAJOR bump regardless of diff size. |
| **Re-tagging rule** | Every service in the application carries the application's version tag after every release, whether or not it was rebuilt — no application ever has services on mismatched tags. |
| **`release.lock.json`** | Pipeline-generated lockfile mapping each service to its deployed image digest, committed alongside every release tag; a service not rebuilt copies its digest from the previous release's lockfile. |
| **Image promotion** | Re-tagging an image at the registry (`docker buildx imagetools create`) rather than rebuilding — 200–500 ms, zero bytes transferred, digest (and cosign signature, SBOM, provenance) preserved. |
| **Digest vs tag** | The digest is the immutable identity of an image and what gets deployed; the tag is a mutable, human-facing alias. "Deploy by digest, never by tag" is a settled decision. |
| **Frontend is nginx in the cluster, not bucket + CDN** | Settled decision: same Gateway, hostname, certificate, `HTTPRoute`, `SecurityPolicy` and observability as everything else. A bucket needs a second edge path and identity model. |

---

## 21. Rollback

| Mechanism | Definition |
|---|---|
| **Redeploy a previous image digest** | The primary, cheap rollback: a container image change plus rolling update, 30–90 s, reversible, blast radius limited to the service. Requires that the older code can still run against the current database schema. |
| **`helm rollback`** | Restores the previous Helm release manifest (more than just the image), 1–5 min. Hooks re-run (problematic for migrations), CRDs are not rolled back, and changes to immutable fields can fail mid-rollback, leaving a third, inconsistent state. |
| **`tofu apply` of an earlier commit** | Reverting infrastructure code and reapplying — **not** reversible and can destroy resources (reverting an "added a resource" commit plans a `destroy`; reverting a `ForceNew` change plans destroy-then-create). Never use as incident response; "roll forward" instead. |
| **`ForceNew` attribute** | A resource attribute whose change forces resource replacement (destroy then create) rather than an in-place update. |
| **Immutable fields** | Fields (e.g. a Kubernetes `Deployment.spec.selector`, a PVC size) that cannot be changed/reverted in place — attempting to roll them back via `helm rollback` fails partway through. |
| **"Reverting a merge does not undo a migration"** | Key rollback trap: reverting code via Git leaves the database on the new schema, so the reverted (old) code then runs against a schema it doesn't expect — one broken release becomes a broken release plus a broken rollback path. Someone will try it anyway. |
| **A migration has no rollback at all** | The stated reason expand-contract exists, and why migrations are separated from deployment. |

---

## 22. Migrations and expand-contract

| Term | Definition |
|---|---|
| **Migrations as a separate stack** | Migrations run as their own stack (`phase: pre-deploy`) with their own production approval — never inside the application entrypoint, an `initContainer`, or a Helm `pre-upgrade` hook (each races multiple replicas or re-runs on rollback). |
| **Expand-contract** | Splits every schema change across releases so that, at every point, both the currently deployed code and the previous release's code work against the current schema. **N (expand)**: add nullable column/table/index, code writes both / reads old — rollback-safe. **N+1 (migrate)**: code reads new, still writes both — rollback-safe. **N+2 (contract)**: drop old column, code reads/writes new only — **not** rollback-safe, the MAJOR bump point. |
| **Contract phase timing rule** | Contract must never be in the same release as the code that stopped writing the old column — at minimum one full release gap, and not before the 14-day production rollback window on N+1 has passed. |
| **Backfill in batches** | Data backfill during an expand migration must be batched by primary key with bounded, resumable, idempotent commits, since one large `UPDATE` holds a lock and can be killed mid-transaction by a job timeout. |
| **Alembic** | The Python migration tool used. Rules: review every autogenerated migration by hand (it misses server defaults, constraint renames, some type changes, and may emit unwanted `DROP`s); keep exactly one migration head (`alembic heads` in CI); a `down_revision`/`downgrade()` existing does not mean a rollback is data-safe; take a PostgreSQL advisory lock (`pg_advisory_lock`) at migration start to guard against duplicate retries. |

---

## 23. Java / JVM

| Term | Definition |
|---|---|
| **Lockfile (Java)** | Gradle's `gradle.lockfile` (via `dependencyLocking`) or `verification-metadata.xml`, or Maven's `lockfile.json` (via `maven-lockfile`) / `maven-enforcer` rules (`banDynamicVersions`, `requireReleaseDeps`) — ensures reproducible builds so the digest promise in change detection holds. |
| **`startupProbe`** | Must be used instead of `livenessProbe.initialDelaySeconds` for slow-starting services (Spring Boot, 20–45 s); only after it passes does the liveness probe begin, avoiding a false `CrashLoopBackOff`. |
| **`livenessProbe` / `readinessProbe`** | Standard Kubernetes health probes; tuned to 10/3/2 and 5/2 respectively for Java, active only after `startupProbe` passes. |
| **`-XX:MaxRAMPercentage` / `-XX:InitialRAMPercentage`** | JVM flags setting heap size as a percentage of the container memory limit (75.0–80.0 recommended) instead of a fixed `-Xmx`, so heap scales with the pod's memory limit while leaving room for non-heap. |
| **Non-heap memory** | JVM memory outside the heap: metaspace (128–256 MiB), code cache (64–240 MiB), thread stacks (1 MiB each), direct byte buffers, GC structures — not optional, not counted in `-Xmx`. |
| **OOMKill** | Container killed by the kernel (`SIGKILL`, exit code 137, `OOMKilled` in `kubectl describe pod`) with nothing logged by the application — the kernel gives the process no chance to write anything before killing it. |
| **cgroups v2 host-memory bug** | On JDK versions before 8u372, 11.0.16 or 15, `UseContainerSupport` can silently fall back to sizing the JVM heap from the *host's* memory rather than the container/cgroup limit, causing an oversized heap that fails only once it grows. |
| **Default `MaxRAMPercentage` (25%)** | Without an explicit flag, a modern JVM defaults heap to 25% of the container limit, wasting most of the allocated memory until GC pressure builds. |
| **`-Xmx` set to the full limit** | An intuitive but wrong fix: max heap equal to the entire memory limit leaves nothing for the 250–400 MiB of non-heap, so RSS exceeds the limit under load. |
| **SerialGC selection under `limits.cpu: 1`** | JVM ergonomics select the single-threaded SerialGC when it sees fewer than 2 CPUs (or under ~1792 MB), causing long stop-the-world pauses; mitigated by explicitly setting `-XX:+UseG1GC`. |
| **`requests.memory == limits.memory` (JVM)** | Required because the JVM sizes itself from the limit; a lower request lets the scheduler oversubscribe the node, risking eviction under memory pressure. |
| **Three distinct OOMKill paths** | All exit 137 with nothing in the application log: (1) a pre-8u372/11.0.16 JVM on a cgroups v2 node reading the host's memory; (2) the 25% default with no flag; (3) `-Xmx` set to the whole limit leaving nothing for non-heap. |

---

## 24. Python

| Term | Definition |
|---|---|
| **`uv.lock`** | Mandatory committed lockfile for Python dependencies; `uv lock --check` fails CI if stale, and the image installs via `uv sync --frozen --no-dev`, installing exactly what the lock specifies without re-resolving. |
| **Multi-stage image (Python)** | Build stage (`uv` + compiler toolchain) separate from a slim runtime stage; reduces image size from ~1.1 GB to ~180 MB and removes the compiler toolchain (and its CVEs) from the shipped image. |
| **`UV_COMPILE_BYTECODE`** | Build flag pre-compiling `.pyc` files at build time, shaving latency off each worker's first request. |

---

## 25. Node / React frontend

| Term | Definition |
|---|---|
| **`nginxinc/nginx-unprivileged`** | An nginx image variant running as uid 101, listening on port 8080 (not root/port 80) — required because stock nginx cannot satisfy PSS `restricted` (`runAsNonRoot`, no privileged-port binding, `readOnlyRootFilesystem`). Using stock nginx gets the pod rejected at admission. |
| **PSS `restricted`** | Kubernetes Pod Security Standard enforced via the `pod-security.kubernetes.io/enforce` namespace label; requires `runAsNonRoot: true`, dropped capabilities (no `NET_BIND_SERVICE` for ports <1024), etc. |
| **`readOnlyRootFilesystem`** | Requires writable paths (nginx's `/var/run`, `/var/cache/nginx`, `/tmp`) to be mounted as `emptyDir` volumes instead of written to the container filesystem. |
| **`env.js` (runtime config)** | The correct pattern: a container-entrypoint script writes `window.__ENV__` values into `env.js` at container startup, from environment variables sourced from resolved globals — producing **one image** usable across all environments. |
| **`VITE_API_URL` (build-time env, anti-pattern)** | Baking a URL into the bundle at `npm run build` time via Vite's `import.meta.env` — produces a different image (and digest) per environment and breaks image promotion, since the artifact tested in `qa` would differ from the one deployed to `prod`. |
| **Cache-Control (asymmetric)** | `index.html` and `/config/env.js` (unhashed, environment-specific) get `no-store, must-revalidate`; hashed files under `/assets/` get `public, max-age=31536000, immutable`. Getting this backward makes a deploy silently appear to fail or serve broken chunk loads. |
| **`try_files $uri /index.html`** | nginx directive serving `index.html` as a fallback so client-side (React Router) routes work on reload/direct link — must be scoped so it doesn't apply inside `/assets/`, where a missing file should 404 (`try_files $uri =404;`) instead of producing an `Unexpected token '<'` module-parse error. |
| **`npm ci` vs `npm install`** | `npm ci` fails the build if the lockfile is out of sync with `package.json`; `npm install` would silently rewrite the lockfile, breaking reproducibility. |
| **The frontend's four first-deployment details** | `nginxinc/nginx-unprivileged` against PSS `restricted`/`readOnlyRootFilesystem` (blocks outright); runtime `env.js` vs. build-time `VITE_API_URL` (blocks outright, kills promotion); asymmetric `Cache-Control`; `try_files $uri /index.html`. The last two deploy successfully and are broken anyway — the worse failure mode. |

---

## 26. Risk register (`risk-register.md`) — 53 risks by domain (52 active)

Each risk has a stable, never-reused R-number, a likelihood, an impact, and a mitigation tied to a document section.

| ID | Risk |
|---|---|
| **R1** | Outputs Sharing is experimental — Terramate's block semantics may change. Mitigated by pinning the Terramate version and centralising contracts in `imports/contracts/`. |
| **R2** | Missing `after` on a consumer stack — an unresolved dependency ordering silently applies a stale/wrong shared-output value with no error. **Top-ranked risk.** Mitigated by the blocking G1 conftest policy. |
| **R3** | Mocks leak into a deployment. Mitigated by separate preview/deploy scripts, the `mock-` prefix convention, and a post-apply grep for `mock-` in outputs. |
| **R4** | Type-mismatched mocks type-check in preview but fail at apply. Mitigated by code-review checklist and correctly-typed mocks. |
| **R5** | A shared platform destroyed by an instance teardown via a wrong destroy-selector, taking down every tenant. Ranked #5 of top risks. Mitigated by a `protected` tag, a destroy-selector check, and a CMDB reference count. |
| **R6** | Producer output rename breaks N consumers. Mitigated by treating outputs as a versioned contract (add new alongside old, deprecate over two releases) and using the CMDB relationship graph to find affected consumers. |
| **R7** | Cross-account state read permissions missing at first setup, causing loud CI failures. Mitigated by documenting required grants and testing in the PoC. |
| **R8** | Secret leaked through `TF_VAR_*` by sharing values instead of references. Mitigated by never sharing secret values, plus a policy/grep gate for secret patterns in outputs. |
| **R9** | Generated code edited by hand, silently reverted by the next `terramate generate`. Mitigated by the G0 gate plus `CODEOWNERS` requiring platform-team approval on generated files. |
| **R10** | Vendor-sourced Terramate-vs-Terragrunt comparisons are overstated (often published by Terramate itself). Mitigated by independently validating change-detection and outputs-sharing claims in the PoC. |
| **R11** | Cluster rebuild invalidates every IRSA/WI binding on a shared platform. Mitigated by treating cluster replacement as a fleet event, a CMDB consumer list, and rehearsing in an ephemeral environment. |
| **R12** | Wildcard `sub` in an OIDC trust policy lets any branch or fork PR assume the cloud apply role — the most common AWS OIDC misconfiguration. Ranked #2 of top risks. Mitigated by `StringEquals` on the exact `repo:ORG/REPO:environment:ENV`. |
| **R13** | Shared task execution role on a multi-tenant ECS cluster can read every tenant's secrets. Mitigated by a per-instance execution role. |
| **R14** | Cloud Run service deployed with `ingress = ALL` bypasses Cloud Armor, WAF, and access logs. Mitigated by a secure-by-default global, an assertion, and GCP org policy `constraints/run.allowedIngress`. |
| **R15** | Workload identity binding written with a wildcard (`POOL[*/*]`, `system:serviceaccount:*:*`) grants the role to every pod in the cluster. Mitigated by generating bindings from `global.platform.namespace` and a Checkov policy rejecting wildcards. |
| **R16** | Permission boundary omitted from a tenant-created IAM role allows privilege escalation. Mitigated by the platform publishing `task_role_boundary_arn` and an assertion blocking generation without it. |
| **R17** | State encryption key scoped per stack blocks outputs sharing (consumers can't decrypt producer state). Mitigated by one state-encryption key per environment, not per stack. |
| **R18** | Private control plane unreachable from GitHub-hosted runners. Resolved by deciding self-hosted runners vs. authorised-network allowance in Phase 0. |
| **R19** | Default service account used as workload identity risks broad (e.g. project Editor) permissions. Mitigated by a dedicated identity per workload, enforced by policy. |
| **R20** | GCP NEG is not in Terraform state, making an "all in IaC" claim false. Mitigated by declaring it as a `data` source, naming it explicitly, and recording the gap in the archetype manifest. |
| **R21** | `TargetGroupBinding` lets a tenant redirect another tenant's traffic on shared EKS. Mitigated by RBAC denying the CRD to application namespaces and restricting creation to the `gateway` archetype. |
| **R22** | Keycloak ↔ Gateway bootstrap cycle can deadlock on first cold start. Mitigated by Keycloak's `HTTPRoute` carrying no `SecurityPolicy` and OIDC discovery resolving via the in-cluster Service. |
| **R23** | GCP VPC peering non-transitivity blocks hub LB → spoke NEG if hub-and-spoke uses separate VPCs. Resolved by Shared VPC, Network Connectivity Center, or a load balancer per spoke — decided in Phase 0. |
| **R24** | `kubernetes_manifest` breaks PR previews (requires CRD/API server reachable at plan time). Mitigated by packaging CRs in the archetype's Helm chart and deploying via `helm_release`. |
| **R25** | AKS `kube_config` lands in state as a credential. Mitigated by `local_account_disabled = true` plus Entra (Azure AD) auth. |
| **R26** | Pod secondary range sized for too few nodes — immutable after cluster creation, so the cluster cannot grow without a full rebuild. Ranked #3 of top risks. Mitigated by the 64-pods-per-node default, a resolver check rejecting `max_nodes × block > range`, a /16 for production, or Azure CNI Overlay. |
| **R27** | Environment pool fragments into unusable /17s over time. Mitigated by buddy allocation preferring blocks that preserve larger free runs, and isolating the ephemeral supernet. |
| **R28** | *Retired* — duplicate of R26, merged there. The number is not reused. |
| **R29** | Shared Kafka bus saturated by one tenant on `demos`. Mitigated by `KafkaUser` producer/consumer quotas and a `kafka_partitions` budget enforced at PR time. |
| **R30** | Tenant writes unprefixed Kafka topics, risking name collisions. Mitigated by a mandatory `{{ instance }}-` prefix and ACLs derived by the `kafka` archetype, never hand-written. |
| **R31** | Demo archetypes accumulate past their usefulness. Mitigated by a mandatory `expiresOn` and a scheduled job opening a (human-approved) destroy PR. |
| **R32** | Each demo provisions its own managed database if `database-platform` is unbound, undermining cost efficiency. Mitigated by binding `database-platform` in shared environments with conditional `data`/`data-tenant` stacks (except deliberately in `demos` — see §1). |
| **R33** | Gatekeeper webhook down with `failurePolicy: Fail` rejects all cluster admission, including Gatekeeper's own recovery. Mitigated by `exemptNamespaces`, ≥3 replicas with a PDB, and `Ignore` failure policy everywhere except production. |
| **R34** | Registry drift between JSON Schema, conftest data and Gatekeeper values blocks legitimate deployments at admission — the worst place to discover it. Ranked #4 of top risks. Mitigated by treating the registry as the single source and a blocking `registry-generate --check` gate. |
| **R35** | A managed policy add-on is adopted, then custom templates are needed, but the two are mutually exclusive. Mitigated by standardising on self-managed Gatekeeper on all three clouds, with a `custom-templates` trait. |
| **R36** | A Rego rule is written but never fires, producing false confidence. Mitigated by running `conftest verify` on `policy/*_test.rego` in the same CI job as the gate. |
| **R37** | Serverless runtimes are assumed to have the same policy coverage as Kubernetes runtimes, but the admission layer doesn't exist there. Mitigated by explicitly stating the coverage parity gap, with cloud control-plane policy substituting for admission control. |
| **R38** | GKE authorized networks edited per CI job: concurrent jobs overwrite each other's entry and a dead runner leaves its IP open. Mitigated by one `concurrency` group, an `if: always()` close step and a reconciler expiring stale entries. |
| **R39** | `container.clusters.update` granted to a pipeline identity to open the runner IP — lets any PR reconfigure the cluster. Mitigated by a minimal intermediate service that only opens and closes a /32. |
| **R40** | Secret values stored in OpenTofu state, making the state a second secret store. Mitigated by ephemeral resources and write-only attributes. |
| **R41** | Environment state-encryption key destroyed; GCP lacks a written equivalent of the AWS SCP. Mitigated by no destroy permission for pipelines, `prevent_destroy` and a minimum destroy-scheduled duration. |
| **R42** | IdP federation credential (Keycloak in the upstream IdP) expires and nobody can log in. Mitigated by a certificate credential and an expiry alert to the owning team. |
| **R43** | Offboarded user keeps application tokens where there is no SCIM. Mitigated by daily reconciliation and no personal tokens in CI. |
| **R44** | OIDC `SecurityPolicy` applied to a route that also serves machine clients with bearer tokens. Mitigated by a generator assertion for self-authenticating archetypes. |
| **R45** | Default 30 s backend timeout on the GCP external Application LB causes intermittent 502 on large uploads. Mitigated by an explicit timeout in the edge stack. |
| **R46** | Upstream Helm chart ships a privileged or root init container. Mitigated by disabling it and moving the requirement to the node, expressed as a trait. |
| **R47–R53** | SonarQube on `qa`: compute engine queue saturation, pull-request analysis recorded as `main`, multi-JVM OOMKill, loss of the settings encryption key, leaked global analysis token, irreversible upgrade migration, zonal volume loss. See `risk-register.md` §8. |

**Top five risks** (ranked by likelihood × impact, mitigation not yet in place): 1) R2 (missing `after`), 2) R12 (wildcard OIDC `sub`), 3) R26 (pod range sized for too few nodes), 4) R34 (registry drift), 5) R5 (shared platform destroyed by instance teardown).

---

## 27. Still-open questions (not yet settled — see `CLAUDE.md`)

| # | Question |
|---|---|
| 1 | Is `max_pods_per_node` settable on GKE Autopilot? The default of 64 assumes it is. |
| 2 | Shared VPC or separate VPCs on GCP? Peering non-transitivity plus the same-VPC backend rule may force Shared VPC (risk R23). **Settled for `qa`: separate VPC.** Open for `demos` and any environment whose edge sits in the hub. |
| 3 | Kafka partition ceiling on the intended broker count — the 4000 budget in the `demos` binding is a placeholder. |
| 4 | Where does resolution run — a CLI in the repo, or a reusable workflow? Determines whether the project office can validate a demo locally. |
| 5 | How much Rego is genuinely shared between conftest and `ConstraintTemplate`s — measure before planning a single policy codebase. |
| 6 | Developer-guide open questions: scaffolding tool vs. template repository, where the version bump is computed, ephemeral environments opt-in or automatic. |
