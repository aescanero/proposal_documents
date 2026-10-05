# Risk Register

**Companion to `terramate-outputs-sharing-architecture.md`, `archetype-model.md` and `platform-overview.md`**

| | |
|---|---|
| **Scope** | Every identified failure mode across generation, resolution, identity, edge, policy and multi-tenancy |
| **Section references** | `§n` refers to the architecture document unless prefixed `AM §n` (archetype model) |
| **Identifiers** | R1–R71. R28 is **retired** (duplicate of R26), and R38 and R39 are retired with the control plane DNS endpoint (`landing-zone-qa` DZ4); retired numbers are not reused |
| **Review cadence** | At each roadmap phase gate, and whenever a pinned tool version changes |

Risks are grouped by domain rather than numbered order, because that is how they are reviewed. The original R-numbers are stable identifiers and must not be reused if a risk is retired.

---

## How to read this

| Column | Meaning |
|---|---|
| **Likelihood** | Probability the failure occurs **if the mitigation is not in place** |
| **Impact** | Severity when it does occur |
| **Mitigation** | The control, and the section that specifies it |

A risk whose mitigation is a CI gate is only mitigated once that gate is **blocking**. Several below are marked "High without X" precisely because the default state is unprotected.

---


## 1. Outputs sharing and generation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Outputs Sharing is experimental** and its block semantics may change | Medium | High — every contract file affected | Pin the Terramate version in `mise.toml`; keep contracts centralised in `imports/contracts/` so a breaking change is a bounded edit; subscribe to Terramate release notes; validate on upgrade in a scratch branch before rolling out |
| R2 | **Missing `after` on a consumer stack** | High without lint | High — wrong values applied | The lint in §14.4, made blocking |
| R3 | **Mocks leak into a deployment** | Medium | High | Separate `preview` and `deploy` scripts; prefix all mocks with `mock-`; add a post-apply grep for `mock-` in outputs |
| R4 | **Type-mismatched mocks** | High | Medium — plan passes, apply fails | Code review checklist; mock lists as lists, base64 as valid base64 |
| R9 | **Generated code edited by hand** | Medium | Medium | G0 gate + `CODEOWNERS` on `stacks/**/_*.tf` requiring platform-team approval |
| R17 | **State encryption key scoped per stack, blocking outputs sharing** | Medium at rollout | Medium — consumers cannot decrypt producer state | One state-encryption key per **environment**, not per stack (§11.5) |

## 2. Identity, access and secrets

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R8 | **Secret leaked through `TF_VAR_*`** | Low if policy followed | Critical | Never share secret *values*; share references only. Add a Checkov custom policy or a grep gate that fails when an `output` block value matches known secret patterns |
| R12 | **OIDC trust policy uses a wildcard `sub`** (`repo:org/repo:*`) | High if unreviewed | Critical — any branch or fork PR can assume the apply role | `StringEquals` on the exact `repo:ORG/REPO:environment:ENV`; GCP `attribute_condition` pinning `assertion.repository` and `repository_owner_id`; review both in a dedicated bootstrap PR (§11.2, §11.3) |
| R15 | **Workload identity binding written with a wildcard** (`POOL[*/*]`, `system:serviceaccount:*:*`) | Medium | Critical — every pod in the cluster gains the role | Generate the binding from `global.platform.namespace`; Checkov custom policy rejecting `*` in trust conditions (§11.8) |
| R16 | **Permission boundary omitted from a tenant-created IAM role** | Medium | High — tenant stack can escalate | Platform publishes `task_role_boundary_arn`; assertion blocks generation without it (§11.7) |
| R19 | **Default service account used as workload identity** (GCP compute SA, ECS shared role) | Medium | High — workload runs with project Editor | Dedicated identity per workload, enforced by Checkov custom policy (§7.4, §5.7) |
| R25 | **AKS `kube_config` lands in state as a credential** | Certain if used | High | `local_account_disabled = true` plus Entra auth; never expose `kube_config` as a shared output (§9.5) |
| R39 | *Retired — with the DNS endpoint no pipeline identity needs `container.clusters.update` (`landing-zone-qa` DZ4). Number not reused.* | — | — | — |
| R40 | **Secret values stored in OpenTofu state** (`random_password` + secret version) | High by default | High — the encrypted state becomes a second secret store readable by every identity that can read state | Ephemeral resources and write-only attributes (`secret_data_wo`); verify support in the pinned OpenTofu and provider versions in Phase 0 |
| R41 | **Environment state-encryption key destroyed** — GCP has no written equivalent of the AWS SCP in §11.3 | Low | Critical — the environment's state is unreadable, irrecoverably | No KMS destroy permission on pipeline identities; `prevent_destroy`; org policy `constraints/cloudkms.minimumDestroyScheduledDuration`; key ring created at layer 0 (`proposals/sonarqube-qa`, section 4.14) |
| R42 | **IdP federation credential expires** (Keycloak's credential in the upstream IdP app registration) | Medium | High — nobody can log in to anything behind the realm | Certificate credential instead of client secret; alert 30 days before expiry routed to the team that owns the app registration |
| R43 | **Offboarded user keeps application tokens** where the application has no SCIM | Medium | Medium — access continues after the upstream account is disabled | Daily reconciliation job against the upstream directory; no personal tokens in CI |
| R54 | **Workload Identity sameness in the shared non-prod project**: one pool per GCP project, so the same namespace and KSA in two non-prod clusters are one GCP identity | High unless KSAs are prefixed | High — one non-prod environment reads another's secrets, buckets and databases | Every KSA with GCP IAM named `<env>-<name>`; Gatekeeper P12 rejects another environment's prefix; G1 checks every IAM `member`. Residual: a cluster-admin of one non-prod environment can bypass admission — accepted for non-prod only; `prod` never shares a project (`CLAUDE.md`) |
| R60 | **A project-level grant where a resource-level one would do**: in the shared non-prod project, a role on the project reaches every environment in it | Medium | High — an environment identity reads or writes another environment's resources | Grants on keys, repositories, zones and SAs per resource; the landing zone creates the SAs that receive cross-project grants; a G3 rule on landing zone IAM (`landing-zone-qa` §6.3, §11.1) |
| R71 | **An environment identity federated before its protected GitHub Environment exists, or bound to the Environment without the branch**: GitHub creates on the fly, with no protection, an Environment a job names and that does not exist | Medium at each onboarding | Critical — `tf-apply-<env>@` or `tf-destroy-<env>@` impersonable from a workflow on any branch by anyone with write access | Apply and destroy identities bound to `attribute.env_ref/<env>@refs/heads/main`; Environments created before the binding merges; manual workflows validate the environment in a job without `environment:` and check the Environment's protection through the API (§11.2; `multi-environment` DX9) |
| R61 | **State readable through project-level grants when layer 0 adopts an existing project**: identities that already hold `owner`, `editor` or `storage.admin` on the project read and write every state object | High in an adopted project | Critical — every environment's state, the landing zone's included, readable and writable outside the pipeline | Narrowed to resource level before the bootstrap stores state; state per prefix and keys per key; DATA_READ audit on `storage.googleapis.com` (`landing-zone-qa` §1.5, RZ6) |
| R63 | **The IAM-administration bound out of step with the roles it guards**: the landing zone's apply identity administers project IAM bounded to a role list; a role added without updating the bound, or a privileged role slipped into the list | Medium | High — a 403 (safe) in the first case; an escalation path in the second | One `global.identities` list read by the grantor and by the bound; module validations refuse `owner`, `editor`, IAM administration and token-creator roles in the grantable list; the bootstrap change is reviewed by security (`landing-zone-qa` DZ13, RZ8) |

## 3. Networking and address planning

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R7 | **Cross-account state read permissions missing** | High at first setup | Medium — CI fails loudly | Document the required grants per environment; test in the PoC before scaling out |
| R18 | **Private control plane unreachable from GitHub-hosted runners** | High on private clusters | Medium — pipeline blocked late in rollout | Decide self-hosted runners vs authorized-network allowance in Phase 0 (§11.9); on GCP, the control plane DNS endpoint with IAM only removes the problem without self-hosted runners (`landing-zone-qa` DZ4) |
| R23 | **GCP VPC peering non-transitivity blocks hub LB → spoke NEG** | High if hub-and-spoke uses separate VPCs | High — the edge design does not work | Shared VPC with a /17 per environment, Network Connectivity Center, or an LB per spoke. Decide in Phase 0 |
| R26 | **Pod secondary range sized for too few nodes** — immutable after cluster creation. The original trigger was a /18 at 110 pods per node (64 nodes) | High without the check | High — cluster cannot grow; fixed only by rebuilding it | Platform default of 64 pods per node (`/25` per node, 128 nodes in a `/18`); resolver rejects `max_nodes × block > range` (AM §9.4); `/16` for production; Azure CNI Overlay removes the constraint (§9.2) |
| R27 | **Environment pool fragments into unusable /17s** | Medium over 12 months | Medium — a /16 becomes unallocatable | Buddy allocation preferring blocks that do not split larger free runs; isolate the ephemeral supernet (AM §8.5) |
| R38 | *Retired — the control plane DNS endpoint removes the authorized networks it described (`landing-zone-qa` DZ4). Number not reused.* | — | — | — |
| R68 | **A resource outside its environment's region or jurisdiction** | Medium with several regions | High — data outside its territory; cross-region latency and cost | `gcp.resourceLocations` on each jurisdiction's folder; a non-production project and a state bucket per jurisdiction; G1 `environment.placement`; G3 `terraform.own_location` (§13.4; `multi-environment` DX4, DX5) |
| R66 | **VPC egress denied by default blocks a legitimate flow**: a port other than 443, or the allow for the environment's own range missing | Medium with each new archetype | High if it is the internal allow — nothing fails at apply, and every admission webhook times out (with `failurePolicy: Fail`, lock-out); Medium otherwise | Logged deny rule; the allow list (443, the environment's range, the private VIP) written before the cluster; other ports per archetype in `egress_extra`, reviewed; the list verified before Gatekeeper is installed (`network-qa` §2, VW6) |

## 4. Edge and ingress

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R20 | **GCP NEG is not in Terraform state** | Certain | Medium — "all in IaC" claim is false | Reference it by its deterministic URL (never a `resource`, never a `data` source that fails the preview), split into three stacks with `after` checked by a named G1 rule; record the absence of `iac-owned-edge` in the archetype manifest rather than hiding it (§10.2) |
| R21 | **`TargetGroupBinding` lets a tenant redirect another tenant's traffic** | Medium on shared EKS | Critical | Kubernetes RBAC denying the CRD to application namespaces; only the `gateway` archetype creates them; controller IAM scoped to specific target groups (§10.3) |
| R22 | **Keycloak ↔ Gateway bootstrap cycle** | High on first cold start | High — environment does not start | Keycloak's `HTTPRoute` carries no `SecurityPolicy`; OIDC discovery via in-cluster Service; documented as an invariant (§10.7) |
| R24 | **`kubernetes_manifest` breaks PR previews** | High if used | Medium | Package Gateway API custom resources in the archetype's Helm chart; deploy via `helm_release` (§10.5) |
| R44 | **OIDC `SecurityPolicy` applied to a route that also serves machine clients** with their own bearer tokens | Medium, by homogeneity | High — every API client is redirected to the IdP and fails | Assertion in the generator for archetypes that authenticate themselves; documented next to the Keycloak exception (R22) |
| R45 | **Default 30 s backend-service timeout on the GCP external Application LB** | High for large uploads | Medium — intermittent 502 | Timeout set explicitly in the edge stack; matching Envoy `BackendTrafficPolicy` |

## 5. Multi-tenancy and shared environments

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R5 | **Shared platform destroyed by an instance teardown** | Low with guards, catastrophic without | Critical | `protected` tag + destroy-selector check + CMDB reference count by edges, not by name (§12.4); R56 |
| R6 | **Producer output rename breaks N consumers** | Medium | High on shared platforms | Treat outputs as a versioned contract; add new outputs alongside old, deprecate over two releases; a G1 rule fails the PR when a consumed output is missing from its producer and names the consumer (§13.3, `terramate.contracts`); the CMDB relationship graph tells you who is affected |
| R11 | **Cluster rebuild invalidates every IRSA/WI binding on a shared platform** | Low | High | Treat cluster replacement as a fleet event; maintain the consumer list in the CMDB; rehearse in an ephemeral environment |
| R13 | **Shared task execution role on a multi-tenant ECS cluster** | High by default | High — cross-tenant secret exposure | Per-instance execution role scoped to that instance's secret ARNs (§8.4) |
| R14 | **Cloud Run service deployed with `ingress = ALL`** | Medium | High — bypasses Cloud Armor, WAF and access logs | Globals default + assertion + org policy `constraints/run.allowedIngress` (§7.2) |
| R29 | **Shared Kafka bus saturated by one tenant** | Medium on `demos` | High — affects every tenant | `KafkaUser` producer/consumer quotas, not just ResourceQuota; `kafka_partitions` budget enforced at PR time (AM §10.3) |
| R30 | **Tenant writes unprefixed Kafka topics** | High without admission policy | Medium — silent collision between demos | Mandatory `{{ instance }}-` prefix enforced by the provider; ACLs derived by the `kafka` archetype, never hand-written |
| R31 | **Demo archetypes accumulate past their usefulness** | Certain | Medium — ranges, identities and quotas leak | `expiresOn` mandatory for `kind: demo`; scheduled job opens a destroy PR; never automatic destruction |
| R32 | **Each demo provisions its own managed database** | Certain in `demos`, by design | Medium — a shared demo environment stops being cheap | Accepted: both `database-platform` providers give each consumer its own instance (`CLAUDE.md`, isolation over cost). Bounded by the `managed_db_instances` capacity in the binding (25 in `demos`); a CNPG `Cluster` costs less than a Cloud SQL instance where a client chooses `postgres-operator` |
| R67 | **Environment or region names that are a prefix of others, or an environment parsed out of a stack id**: `sandbox` and `sandbox-eu`, `europe-west1` and `europe-west10`; `split(id, "-")[1]` on `gcp-sandbox-eu-edge` | Medium as soon as there are several environments; certain for a rule that parses ids once a name contains `-` | High — one environment's KSAs, DNS zones and conditioned grants reach the other's; a location rule lets another region through; a G1 rule blocks correct changes or lets a missing edge through | Prefix-free environment names (G1 `environment.names`); a separator in every prefix comparison; the environment read from `global.env` or a tag, never from an id; rules fixture-tested with a second environment whose name contains `-` (§13.3; `multi-environment` DX3) |
| R65 | **One environment's network or DNS resource bound to another's** in the shared non-prod project: a private zone visible to another VPC, a firewall rule or route on it, a record in its zones | Low by mistake, possible by intent | High — another environment's Google APIs or internal names answered by addresses this one chose; its traffic opened or redirected; with record write on its public zone, certificates for its names | G3 `terraform.own_network` (§13.4); `dns.admin` on the project only conditioned on the environment's zone prefix; per-environment state prefix; review. Never reaches `prod` (`network-qa` DW8) |

## 6. Policy and validation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R33 | **Gatekeeper webhook down with `failurePolicy: Fail`** | Low | Critical — cluster rejects all admission, including Gatekeeper's own recovery | `exemptNamespaces` for `kube-system` and the Gatekeeper namespace; ≥3 replicas with a PDB; `Ignore` everywhere except production (§13.7) |
| R34 | **Registry drift between JSON Schema, conftest data and Gatekeeper values** | High without a gate | High — legitimate deployments blocked at admission, the worst place to find out | Single `registry/*.yaml` source; all three artefacts generated; `registry-generate --check` gate (§13.8) |
| R35 | **Managed policy add-on adopted, then custom templates needed** | Medium | High — the Azure add-on is mutually exclusive with self-managed Gatekeeper and restricts custom templates | Self-managed Gatekeeper on all three clouds; the `custom-templates` trait makes the limitation a resolution error rather than a discovery (§13.5) |
| R36 | **Rego rule written but never fires** | High without tests | Medium — false confidence | `conftest verify` on `policy/*_test.rego` in the same job as the gate (§13.3) |
| R37 | **Serverless runtimes assumed to have the same policy coverage** | Medium | Medium — a control believed universal is absent on Cloud Run and Fargate | Parity gap stated explicitly (§13); cloud control-plane policy substitutes for admission there |
| R46 | **Upstream Helm chart ships a privileged or root init container** (sysctl, chown) | High | Medium — pod rejected under PSS `restricted`, or pressure to exempt a whole namespace | Disable in the archetype's values; move the requirement to the node (a trait such as `sysctl-max-map-count`); name-scoped exemption only as a last resort |
| R59 | **A project-singleton policy written by an environment**: Binary Authorization is one policy per project, and a `gke` stack that writes it erases the other non-prod clusters' rules | High if each environment writes it | High — admission rules of other environments gone, with no error | Only the landing zone writes it, one rule per cluster from the bindings, `ALWAYS_DENY` by default; a G3 rule counts the rules (`landing-zone-qa` §8) |

## 7. Process and tooling

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R10 | **Vendor-sourced comparisons overstated** | — | Medium — wrong tool choice | Much of the Terramate-vs-Terragrunt material in circulation is published by Terramate. Validate the change-detection and outputs-sharing claims yourself in the PoC before committing the organisation |
| R28 | *Retired — duplicate of R26, merged there. Number not reused.* | — | — | — |
| R55 | **The CMDB sync writes to `main`**: a job with a bypass of `main`'s protection, and a commit that triggers `deploy` again | High if the observed half is committed to `main` | Medium — a job that can push to `main` without review; a deploy loop held back only by a `paths-ignore` | Observed half on its own `cmdb-observed` branch, written only by the reusable `cmdb-sync` workflow; `main`'s ruleset has no bypass (AM §11.1, §14.2) |
| R56 | **CMDB edges silently empty**: the extractor does not evaluate a `from_stack_id`, the stack appears to have no consumers | Medium until the extractor is verified against the pinned Terramate version | Critical — the destroy guard counts 0 and lets a platform with consumers go (R5) | `archetypectl cmdb check` fails when a stack has `input` blocks and no evaluated `consumes`; one extractor shared with the R2 rule of G1, so both fail together (§12.4) |
| R57 | **A secret value reaches the CMDB**: an output carrying one is not marked `sensitive` and ends up in the observed half and the read model | Medium | High — a secret in a file every repository reader can fetch | The G1 secret-name rule (§13.3); the collector drops `sensitive` outputs; the read model is a private release asset, never public Pages (AM §11.2) |
| R58 | **An unrepeatable landing zone bootstrap**: nobody remembers how the organisation was started when it has to be rebuilt | Medium | High — the platform cannot be recreated from the repository | The bootstrap is a stack in the repository with a runbook, applied once by hand and then managed with remote state (`landing-zone-qa` §1) |
| R62 | **A name already taken in a shared project**: the plan says `create` because the resource is not in our state, and the API answers `409` thirty resources later | Medium in a shared or adopted project | High — the landing zone or an environment half applied | A preflight that checks every name before the first `apply`; names that carry the repository or the environment; never `import` a resource we did not create (`landing-zone-qa` §1.3, RZ7) |
| R70 | **An environment created by copying another's stacks, or a list of environments kept by hand** (workflow options, counts, forbidden public-name words) | High at the second environment | Medium — copies that drift from their original; a public name carrying another environment's name that passes; a workflow that does not offer the new environment | Stack tree emitted by the resolver from binding and manifests; every list derived from `environments/*/`; public-name words include every binding's name in G1 and G3 (§12.8, §13.3–§13.4; `multi-environment` DX1, DX8) |
| R69 | **A chart or module default equal to a real environment's value**: a missing override works in that environment and shows only in the next | High without the rule | Medium — the second environment creates resources with the first one's names, or collides with them | Neutral or absent defaults; the generator always passes the value; the derivation introduced with an empty-diff acceptance and checked with fixtures of a second environment (`multi-environment` DX2, DX7) |
| R64 | **Orphan authorised networks** in the control-plane variant that opens a `/32` per job: a runner that dies before its cleanup leaves an IP from the provider's shared pool authorised on the API server | Medium where the variant is used | Medium — IAM and RBAC still guard the endpoint; the network barrier does not | Scheduled removal of stale `gha-*` entries; alert on authorised-network changes outside the pipeline; a cap on entries; the default (DNS endpoint, IAM only) or a self-hosted runner in the VPC avoids it (`landing-zone-qa` §3.2, DZ16) |

---

## 8. Applications — SonarQube on `qa`

Specific to `docs/proposals/sonarqube-qa/`. Kept here so the phase gate reviews them with the rest.

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R47 | **Compute engine queue saturated** — Community has one worker for ~800 analyses a day | Medium-high | Medium — CI jobs wait on the quality gate | Analyse `main` only; `cancel-in-progress`; queue alert; measured in V4; Enterprise Edition as the documented exit |
| R48 | **Analysis run from a pull request is recorded as `main`** | High without a control | Medium — `main` history and gate silently wrong | Reusable workflow triggered only on push to `main`; policy over workflow files |
| R49 | **OOMKill from three JVMs** whose heaps plus non-heap exceed the container limit | High without the calculation | High — exit 137, nothing in the log | Explicit heaps; limit = Σ heaps + margin; `OOMKilled` alert (developer guide §8.3) |
| R50 | **Loss of the settings encryption key** (`sonar-secret.txt`) | Low | High — encrypted settings unrecoverable | Secret Manager with `prevent_destroy` and delayed version destruction |
| R51 | **Global analysis token leaked** from one of 200 repositories | Medium if chosen | High — every project exposed | Per-project tokens with expiry, created by automated onboarding |
| R52 | **Upgrade runs an irreversible database migration** | Medium | High | Verified CNPG backup before every upgrade; rollback is restore + previous image (developer guide §6) |
| R53 | **Zone loss strands the zonal persistent volume** | Low | Medium — outage until the zone returns | Accepted for `qa`; regional (HA) disk as the option |

---

## Top five to act on first

Ranked by (likelihood × impact) with the mitigation not yet in place:

| Rank | Risk | Why it leads |
|---|---|---|
| 1 | **R2** — missing `after` on a consumer stack | Silent. An unresolved ordering applies a stale or wrong value with no error. The G1 policy gate must be blocking from day one |
| 2 | **R12** — wildcard `sub` in an OIDC trust policy | One line of YAML lets any branch or fork PR assume the apply role. The most common AWS OIDC misconfiguration in public incident reports |
| 3 | **R26** — pod range sized for too few nodes | Immutable after cluster creation. Discovered when the cluster stops scaling, fixed only by rebuilding it |
| 4 | **R34** — registry drift | Fails at admission, the worst place to diagnose it, and only after the generator and the `Constraint` have already diverged |
| 5 | **R5** — shared platform destroyed by an instance teardown | Low probability with guards, catastrophic without. One wrong tag selector takes down every tenant |

---

## Review checklist

At each phase gate, confirm for every risk in scope:

- [ ] The mitigation is **implemented**, not merely documented
- [ ] Where the mitigation is a CI gate, it is **blocking** rather than advisory
- [ ] Where the mitigation is an assertion, a test proves it fires
- [ ] The likelihood rating still reflects reality after the phase's changes
- [ ] No risk was retired by reusing its R-number for something else
