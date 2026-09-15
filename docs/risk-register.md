# Risk Register

**Companion to `terramate-outputs-sharing-architecture.md`, `archetype-model.md` and `platform-overview.md`**

| | |
|---|---|
| **Scope** | Every identified failure mode across generation, resolution, identity, edge, policy and multi-tenancy |
| **Section references** | `§n` refers to the architecture document unless prefixed `AM §n` (archetype model) |
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

## 3. Networking and address planning

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R7 | **Cross-account state read permissions missing** | High at first setup | Medium — CI fails loudly | Document the required grants per environment; test in the PoC before scaling out |
| R18 | **Private control plane unreachable from GitHub-hosted runners** | High on private clusters | Medium — pipeline blocked late in rollout | Decide self-hosted runners vs authorized-network allowance in Phase 0 (§11.9) |
| R23 | **GCP VPC peering non-transitivity blocks hub LB → spoke NEG** | High if hub-and-spoke uses separate VPCs | High — the edge design does not work | Shared VPC with a /17 per environment, Network Connectivity Center, or an LB per spoke. Decide in Phase 0 |
| R26 | **Pod CIDR sized for 64 nodes** (a /18 with 110 pods per node) | High | High — cluster cannot grow, and the range is immutable | Lower `max-pods-per-node`, or allocate a /16 to production; Azure CNI Overlay removes the constraint (§9.2) |
| R27 | **Environment pool fragments into unusable /17s** | Medium over 12 months | Medium — a /16 becomes unallocatable | Buddy allocation preferring blocks that do not split larger free runs; isolate the ephemeral supernet (companion document §8.5) |

## 4. Edge and ingress

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R20 | **GCP NEG is not in Terraform state** | Certain | Medium — "all in IaC" claim is false | Declare as `data`, name explicitly, split into three stacks with `after`; record the absence of `iac-owned-edge` in the archetype manifest rather than hiding it (§10.2) |
| R21 | **`TargetGroupBinding` lets a tenant redirect another tenant's traffic** | Medium on shared EKS | Critical | Kubernetes RBAC denying the CRD to application namespaces; only the `gateway` archetype creates them; controller IAM scoped to specific target groups (§10.3) |
| R22 | **Keycloak ↔ Gateway bootstrap cycle** | High on first cold start | High — environment does not start | Keycloak's `HTTPRoute` carries no `SecurityPolicy`; OIDC discovery via in-cluster Service; documented as an invariant (§10.7) |
| R24 | **`kubernetes_manifest` breaks PR previews** | High if used | Medium | Package Gateway API custom resources in the archetype's Helm chart; deploy via `helm_release` (§10.5) |

## 5. Multi-tenancy and shared environments

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R5 | **Shared platform destroyed by an instance teardown** | Low with guards, catastrophic without | Critical | `protected` tag + destroy-selector check + CMDB reference count (§14.4) |
| R6 | **Producer output rename breaks N consumers** | Medium | High on shared platforms | Treat outputs as a versioned contract; add new outputs alongside old, deprecate over two releases; the CMDB relationship graph tells you who is affected |
| R11 | **Cluster rebuild invalidates every IRSA/WI binding on a shared platform** | Low | High | Treat cluster replacement as a fleet event; maintain the consumer list in the CMDB; rehearse in an ephemeral environment |
| R13 | **Shared task execution role on a multi-tenant ECS cluster** | High by default | High — cross-tenant secret exposure | Per-instance execution role scoped to that instance's secret ARNs (§8.4) |
| R14 | **Cloud Run service deployed with `ingress = ALL`** | Medium | High — bypasses Cloud Armor, WAF and access logs | Globals default + assertion + org policy `constraints/run.allowedIngress` (§7.2) |
| R29 | **Shared Kafka bus saturated by one tenant** | Medium on `demos` | High — affects every tenant | `KafkaUser` producer/consumer quotas, not just ResourceQuota; `kafka_partitions` budget enforced at PR time (companion §10.3) |
| R30 | **Tenant writes unprefixed Kafka topics** | High without admission policy | Medium — silent collision between demos | Mandatory `{{ instance }}-` prefix enforced by the provider; ACLs derived by the `kafka` archetype, never hand-written |
| R31 | **Demo archetypes accumulate past their usefulness** | Certain | Medium — ranges, identities and quotas leak | `expiresOn` mandatory for `kind: demo`; scheduled job opens a destroy PR; never automatic destruction |
| R32 | **Each demo provisions its own managed database** | High if `database-platform` is unbound | Medium — a shared demo environment stops being cheap | Bind `database-platform` in shared environments; conditional `data` / `data-tenant` stacks in one manifest (companion §5.5) |

## 6. Policy and validation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R33 | **Gatekeeper webhook down with `failurePolicy: Fail`** | Low | Critical — cluster rejects all admission, including Gatekeeper's own recovery | `exemptNamespaces` for `kube-system` and the Gatekeeper namespace; ≥3 replicas with a PDB; `Ignore` everywhere except production (§13.7) |
| R34 | **Registry drift between JSON Schema, conftest data and Gatekeeper values** | High without a gate | High — legitimate deployments blocked at admission, the worst place to find out | Single `registry/*.yaml` source; all three artefacts generated; `registry-generate --check` gate (§13.8) |
| R35 | **Managed policy add-on adopted, then custom templates needed** | Medium | High — the Azure add-on is mutually exclusive with self-managed Gatekeeper and restricts custom templates | Self-managed Gatekeeper on all three clouds; the `custom-templates` trait makes the limitation a resolution error rather than a discovery (§13.5) |
| R36 | **Rego rule written but never fires** | High without tests | Medium — false confidence | `conftest verify` on `policy/*_test.rego` in the same job as the gate (§13.3) |
| R37 | **Serverless runtimes assumed to have the same policy coverage** | Medium | Medium — a control believed universal is absent on Cloud Run and Fargate | Parity gap stated explicitly (§13); cloud control-plane policy substitutes for admission there |

## 7. Process and tooling

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R10 | **Vendor-sourced comparisons overstated** | — | Medium — wrong tool choice | Much of the Terramate-vs-Terragrunt material in circulation is published by Terramate. Validate the change-detection and outputs-sharing claims yourself in the PoC before committing the organisation |
| R28 | **Pod secondary range sized for too few nodes** | High without the check | High — immutable; requires cluster rebuild | Platform default of 64 pods per node (`/25` per node, 128 nodes in a `/18`); resolver rejects `max_nodes × block > range` (companion §9.4) |

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
