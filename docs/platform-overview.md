# Platform Overview — Read This First

Visual map of the two reference documents. Nothing here is normative; every diagram points at the section that specifies it.

| Document | Answers |
|---|---|
| `archetype-model.md` | *What may be composed with what?* Manifests, capabilities, traits, pools, CMDB, resolution |
| `terramate-outputs-sharing-architecture.md` | *How is it generated and applied?* Generators, outputs sharing, IAM, policy, CI/CD, per-cloud guides |
| `risk-register.md` | *What can go wrong, and is the control actually in place?* 37 risks by domain, reviewed at each phase gate |

---

## 1. The two halves, and the seam between them

```mermaid
flowchart LR
    subgraph R["archetype-model.md — RESOLVE"]
        direction TB
        M["manifest.yaml<br/>requires / provides / traits"]
        B["binding.yaml<br/>which provider per capability"]
        L["pool ledgers<br/>CIDR, hostnames"]
        RES["archetypectl resolve"]
        M --> RES
        B --> RES
        L --> RES
    end

    subgraph G["terramate-outputs-sharing-architecture.md — GENERATE"]
        direction TB
        GEN["terramate generate"]
        TF["_main.tf, _backend.tf<br/>_sharing_generated.tf"]
        RUN["terramate run --enable-sharing"]
        GEN --> TF --> RUN
    end

    RES -->|"binding.tm.hcl<br/>(globals)"| GEN
    RUN -->|"stack + resource inventory"| CMDB[("CMDB in Git")]
    CMDB -.->|"utilisation, claims"| RES
```

**The seam is `binding.tm.hcl`.** The resolver writes globals; the generators consume them. Neither half knows the other's internals.

---

## 2. End-to-end flow of a pull request

```mermaid
flowchart TD
    PR([Pull request opened]) --> SCH["Schema validation<br/>manifests, bindings, ledgers"]
    SCH --> RESOLVE["archetypectl resolve<br/>17 steps — fails closed"]
    RESOLVE -->|"binding.tm.hcl<br/>ledger writes"| G0["G0 · terramate generate --check<br/>generated code is current"]
    G0 --> G1["G1 · conftest<br/>structure, composition, input↔after"]
    G1 --> G2["G2 · Checkov on generated HCL"]
    G2 --> PLAN["terramate script run --changed tofu preview<br/>sharing ON · mocks ON"]
    PLAN --> G3["G3 · Checkov + conftest on plan.json"]
    G3 --> CMT["PR comment · closure, claims, capacity, plan"]

    CMT --> REV{Approved?}
    REV -->|no| END1([Closed — claims released])
    REV -->|yes| ENV["GitHub Environment<br/>required reviewers"]
    ENV --> APPLY["tofu deploy<br/>sharing ON · mocks OFF"]
    APPLY --> SYNC["CMDB sync"]

    style RESOLVE fill:#e8f0fe
    style APPLY fill:#fce8e6
```

Two things this makes visible: the resolver runs **before** generation because it produces generation's input, and `mock_on_fail` is true in preview and false in deploy — separate named scripts so it cannot be got wrong.

Specified in: architecture §13, §14, companion §12.

---

## 3. Archetype layers

```mermaid
flowchart BT
    L0["<b>Layer 0 · landing-zone</b><br/>hub · dns-zone · cert · waf · cidr-pool · edge-ip"]
    L1["<b>Layer 1 · environment</b><br/>prod / qa / dev / demos / ephemeral-*<br/>claims a /17 · provides network, env-edge, psa-range"]
    L1B["<b>Layer 1b · cloud-monitoring</b><br/>cloud-observability"]
    L2["<b>Layer 2 · runtime</b><br/>gke · gke-autopilot · eks · aks · cloudrun · fargate<br/>claims node subnet + pod range"]
    L2B["<b>Layer 2b · policy</b><br/>policy-gatekeeper — Kubernetes runtimes only"]
    L3["<b>Layer 3 · platform services</b><br/>gateway · monitoring · certs · dns · secrets · mesh"]
    L4["<b>Layer 4 · middleware</b><br/>kafka · keycloak · postgres-operator · redis"]
    L5["<b>Layer 5 · applications</b><br/>webapp-3tier · event-driven · demo-*"]

    L0 --> L1
    L1 --> L1B
    L1 --> L2
    L2 --> L2B
    L2B --> L3
    L3 --> L4
    L4 --> L5
    L3 -.->|"edge attachment handle<br/>the one upward edge"| L1

    style L1B fill:#f5f5f5
    style L2B fill:#fff4e5
    style L5 fill:#e8f5e9
```

The dotted edge is the exception worth remembering: the `gateway` archetype at layer 3 publishes the NEG name / target group ARN / AGFC frontend that the environment's edge stack at layer 1 consumes.

Specified in: companion §3.

---

## 4. Where a fact comes from — globals or outputs sharing

```mermaid
flowchart TD
    Q{"Is the value known<br/>before any apply?"}
    Q -->|yes| G["<b>Globals</b><br/>compile time · zero permissions"]
    Q -->|no| S{"Is it a credential,<br/>secret or token?"}
    S -->|yes| N["<b>Neither</b><br/>share a reference;<br/>fetch via data source"]
    S -->|no| C{"Would sharing it<br/>create a cycle?"}
    C -->|yes| D["<b>Promote to a global</b><br/>deterministic name<br/>breaks the cycle"]
    C -->|no| O["<b>Outputs sharing</b><br/>runtime · needs producer<br/>state read permission"]

    style G fill:#e8f5e9
    style N fill:#fce8e6
    style O fill:#e8f0fe
```

Every outputs-sharing edge is a runtime coupling, a CI permission requirement and a failure mode. Every global is a compile-time constant. Prefer globals.

Specified in: architecture §4.6, §11.5, §11.6.

---

## 5. How a shared value actually travels

```mermaid
sequenceDiagram
    participant TG as terramate generate
    participant P as Producer stack
    participant C as Consumer stack
    participant TF as tofu (consumer)

    TG->>P: output block → _sharing_generated.tf (output)
    TG->>C: input block → _sharing_generated.tf (variable)
    Note over TG: committed to git

    C->>P: cd producer && tofu output -json
    P-->>C: JSON
    Note over C: evaluate outputs.NAME.value
    C->>TF: TF_VAR_NAME=resolved
    TF->>TF: plan / apply
```

The third arrow is the one that costs permissions: the consumer's CI job needs **read access to the producer's state backend**, and its encryption key if state encryption is enabled.

Specified in: architecture §3.3, §11.5.

---

## 6. Hierarchical pools and purpose zones

```mermaid
flowchart TD
    G["<b>10.0.0.0/8</b> · global pool<br/>published by landing-zone"]
    G --> HUB["10.0.0.0/17 · hub<br/><i>fixed reservation</i>"]
    G --> HUBDR["10.0.128.0/17 · hub DR<br/><i>fixed reservation</i>"]
    G --> PERM["10.2.0.0/15 · permanent environments"]
    G --> EPH["10.16.0.0/12 · ephemeral"]

    PERM --> ENV["<b>10.4.0.0/17</b> · demos<br/>environment pool"]

    ENV --> Z1["zone <b>infra</b> · /20<br/>node subnets, endpoints"]
    ENV --> Z2["zone <b>data</b> · /20<br/>PSA, DB subnets"]
    ENV --> Z3["zone <b>edge</b> · /20<br/>services, egress"]
    ENV --> Z4["zone <b>growth</b> · /20<br/><i>never allocatable</i>"]
    ENV --> Z5["zone <b>pods</b> · /18<br/>pod ranges only"]

    Z1 -.-> C1["claim: nodes /23<br/>owner gcp-demos-gke"]
    Z5 -.-> C2["claim: pods /18<br/>owner gcp-demos-gke"]
    Z2 -.-> C3["claim: db-subnet /24<br/>owner demos-alpha"]

    style HUB fill:#f5f5f5
    style HUBDR fill:#f5f5f5
    style Z4 fill:#f5f5f5
```

The hub is a **fixed reservation, not a claim** — the landing zone publishes the pool and needs addresses itself, so a claim would create a bootstrap cycle.

Specified in: companion §9.

---

## 7. Claim, capacity, or neither

```mermaid
flowchart TD
    A{"Finite, indivisible,<br/>unique in a scope?"}
    A -->|yes| CL["<b>CLAIM</b> · ledger + reservation<br/>CIDR · hostname · static IP"]
    A -->|no| B{"Divisible quantity<br/>with a known total?"}
    B -->|yes| CA["<b>CAPACITY</b> · budget, no ledger<br/>kafka_partitions · db_connections<br/>workload_identities · managed_db_instances"]
    B -->|no| C{"Derivable from<br/>instance identity?"}
    C -->|yes| DE["<b>NEITHER</b> · deterministic global<br/>namespace · log group · role name<br/>Kafka topic prefix"]
    C -->|no| RE["Re-examine — it is<br/>probably one of the above"]

    style CL fill:#e8f0fe
    style CA fill:#fff4e5
    style DE fill:#e8f5e9
```

Allocation is idempotent on the triple **`(pool, owner, purpose)`**, so five retries of a failed deployment do not burn five pod ranges.

Specified in: companion §8.

---

## 8. Resolution — the 17 steps, grouped

```mermaid
flowchart TD
    subgraph LOAD["Load"]
        S1["1 · manifests + components + binding"]
        S2["2 · category rules for kind: demo"]
    end
    subgraph GRAPH["Graph"]
        S3["3 · transitive closure, cycle detection"]
        S4["4 · bind capability → single provider"]
    end
    subgraph VAL["Validate"]
        S5["5 · versions"]
        S6["6 · traits"]
        S7["7 · runtime"]
        S8["8 · conflicts"]
        S9["9 · evaluate stack conditions"]
        S10["10 · output contract"]
        S11["11 · tenant resources"]
    end
    subgraph ALLOC["Allocate"]
        S12["12 · claims, hierarchical, idempotent"]
        S13["13 · firewall selectors"]
        S14["14 · capacity budgets"]
        S15["15 · provider constraints"]
    end
    subgraph EMIT["Emit"]
        S16["16 · topological order"]
        S17["17 · resolution.json + binding.tm.hcl"]
    end

    LOAD --> GRAPH --> VAL --> ALLOC --> EMIT

    style ALLOC fill:#fff4e5
```

Step 4 is a **lookup, not a search** — exactly one provider per capability per environment — which is why resolution is linear rather than NP-complete. The engineering effort belongs in the diagnostics, not the algorithm.

Specified in: companion §12, §13.

---

## 9. The shape every runtime guide follows

```mermaid
flowchart LR
    N["<b>network</b><br/>VPC/VNet, subnets, NAT"]
    R["<b>runtime</b><br/>cluster or serverless<br/><i>consumer + producer</i>"]
    S["<b>platform services</b><br/>gateway, certs, dns"]
    D["<b>data</b><br/>per instance"]
    A["<b>app</b><br/>per instance"]

    N --> R --> S --> A
    N --> D --> A
```

All five guides — GKE, EKS, Cloud Run, ECS Fargate, AKS — are this graph. What differs is *which facts cross each edge*:

```mermaid
flowchart TD
    subgraph NET["network produces"]
        G1["GKE: network_self_link, subnet_self_link,<br/>pods_range_name, services_range_name"]
        A1["EKS/Fargate: vpc_id, private_subnet_ids (list)"]
        Z1["AKS: vnet_id, node_subnet_id"]
    end
    subgraph CLU["runtime produces"]
        G2["GKE: cluster_endpoint (no scheme), cluster_ca,<br/><b>workload_identity_pool</b>"]
        A2["EKS: cluster_endpoint (WITH https://), cluster_ca,<br/><b>oidc_provider_arn + oidc_provider_url</b>"]
        Z2["AKS: cluster_endpoint, cluster_ca,<br/><b>oidc_issuer_url</b>"]
        F2["Fargate: cluster_arn, alb_listener_arn,<br/><b>task_role_boundary_arn</b>"]
        C2["Cloud Run: artifact_registry_repo,<br/>cloud_armor_policy_id"]
    end
    NET --> CLU
```

Two asymmetries that cause copy-paste bugs: GKE returns an endpoint **without** a scheme and EKS returns one **with** `https://`; and AWS needs two OIDC facts where GCP and Azure need one.

**Never shared, on any cloud:** the auth token. Fetched locally by each consumer via `google_client_config`, `aws_eks_cluster_auth` or the Azure equivalent.

Specified in: architecture §5–§9, §6.8.

---

## 10. Edge attachment — the least portable element

```mermaid
flowchart TD
    subgraph GCP["Google Cloud"]
        GT["Terraform owns:<br/>backend service, health check,<br/>URL map, proxy, forwarding rule"]
        GN["NEG controller creates the NEG"]
        GT -.->|"data lookup by name"| GN
        GNOTE["<b>NOT in Terraform state</b><br/>no iac-owned-edge trait"]
        GN --- GNOTE
    end
    subgraph AWS["AWS"]
        AT["Terraform owns:<br/><b>target group</b>, listener, rules"]
        AC["Controller registers pod IPs<br/>via TargetGroupBinding CR"]
        AT --> AC
        ANOTE["<b>In Terraform state</b><br/>iac-owned-edge ✓"]
        AT --- ANOTE
    end
    subgraph AZ["Azure"]
        ZT["Terraform owns:<br/><b>AGFC + Frontend + Association</b>"]
        ZC["Controller binds via<br/>Gateway annotation"]
        ZT --> ZC
        ZNOTE["<b>In Terraform state</b><br/>iac-owned-edge ✓"]
        ZT --- ZNOTE
    end

    style GNOTE fill:#fce8e6
    style ANOTE fill:#e8f5e9
    style ZNOTE fill:#e8f5e9
```

GCP is the weakest of the three for full IaC ownership. That gap is recorded as the absence of the `iac-owned-edge` trait rather than hidden, so a future compliance requirement fails at validation rather than at audit.

Specified in: architecture §10, companion §4.3.

---

## 11. Why Gateway API removes the fan-in problem

```mermaid
flowchart LR
    subgraph OLD["URL-map edge — fan-in"]
        direction TB
        E1["edge stack"]
        T1["tenant A"] --> E1
        T2["tenant B"] --> E1
        T3["tenant C"] --> E1
        N1["edge must know every tenant;<br/>runs AFTER all of them"]
    end
    subgraph NEW["Gateway API — no fan-in"]
        direction TB
        GW["Gateway<br/>allowedRoutes: Selector"]
        R1["HTTPRoute A"] -->|parentRefs| GW
        R2["HTTPRoute B"] -->|parentRefs| GW
        R3["HTTPRoute C"] -->|parentRefs| GW
        N2["edge knows nothing;<br/>routes attach themselves"]
    end
    OLD -.->|"adopt Gateway API"| NEW

    style OLD fill:#fce8e6
    style NEW fill:#e8f5e9
```

Adopting Gateway API removes three things: the URL map generated from a tenant list, the listener-priority ledger, and the edge-routing stack that had to run last. What survives as a claim is the **hostname** — only one tenant can own `alpha.demos.acme.com`.

Specified in: architecture §10.6.

---

## 12. Isolation boundaries by runtime

```mermaid
flowchart TD
    subgraph K8S["Kubernetes runtimes — boundary is the NAMESPACE"]
        GKE["GKE<br/>WI: POOL[ns/ksa]"]
        EKS["EKS<br/>IRSA: sub=system:serviceaccount:ns:sa"]
        AKS["AKS<br/>FIC: subject=system:serviceaccount:ns:sa"]
    end
    subgraph SRV["Serverless runtimes — boundary is the SERVICE / TASK"]
        CR["Cloud Run<br/>per-service runtime SA<br/>per-service gVisor sandbox"]
        FG["ECS Fargate<br/>task role + per-instance execution role<br/>per-task micro-VM"]
    end
    K8S -->|"shared kernel on shared nodes"| RISK["higher exposure for<br/>semi-trusted workloads"]
    SRV -->|"per-workload isolation"| SAFE["stronger default for<br/>shared demo environments"]

    style RISK fill:#fff4e5
    style SAFE fill:#e8f5e9
```

A wildcard in any of those three trust conditions (`POOL[*/*]`, `system:serviceaccount:*:*`) silently grants every pod in the cluster the identity. That is risk R15.

Specified in: architecture §11.8, §12.3.

---

## 12b. Three enforcement points

```mermaid
flowchart LR
    CI["<b>1 · CI</b><br/>conftest + Checkov<br/><i>every runtime</i>"]
    CP["<b>2 · Cloud control plane</b><br/>Org Policy · SCP · Azure Policy<br/><i>every runtime · not evadable</i>"]
    AD["<b>3 · Cluster admission</b><br/>Gatekeeper, layer 2b<br/><i>Kubernetes runtimes ONLY</i>"]
    CI --> CP --> AD --> DONE([enforced])
    style AD fill:#fff4e5
```

The third point does not exist on Cloud Run, ECS Fargate or Container Apps — the `policy` capability lives only where `cluster` does. Runtime parity is not achievable here, and the gap is written down rather than assumed away.

The resolver **computes**; OPA **asserts**. They must not implement the same rule twice: the resolver owns closure, allocation and ordering; OPA validates that what the resolver and generators produced is legal.

```mermaid
flowchart TD
    REG["<b>registry/*.yaml</b><br/>capabilities · traits · zones · labels"]
    REG -->|generate| S["schemas/*.schema.json<br/>enum blocks"]
    REG -->|generate| D["registry/*.json<br/>conftest --data"]
    REG -->|generate| V["Gatekeeper chart values<br/>ConstraintTemplate params"]
    S --> CK["check-jsonschema"]
    D --> CF["conftest"]
    V --> GK["Gatekeeper"]
    style REG fill:#e8f0fe
```

One source, three generated artefacts, a `registry-generate --check` gate. Without it they diverge — and the failure mode is a label the generator stopped emitting while the admission `Constraint` still demands it, which blocks legitimate deployments at the worst possible moment.

Specified in: architecture §13, companion §4.5.

---

## 13. Three layers of guard rails

```mermaid
flowchart TD
    ORG["<b>Org Policies (GCP) · SCPs (AWS) · Azure Policy</b><br/>region confinement · no SA keys · no public IPs · no IAM users<br/><i>the pipeline cannot disable these</i>"]
    PB["<b>Permission boundaries</b><br/>published by the platform stack, attached by assertion<br/><i>a tenant cannot escape these</i>"]
    RP["<b>Least-privilege role policies</b><br/>per environment · per phase · per workload<br/><i>reviewed in the pull request</i>"]
    ORG --> PB --> RP

    style ORG fill:#fce8e6
    style PB fill:#fff4e5
    style RP fill:#e8f5e9
```

Specified in: architecture §11.7.

---

## 14. Tenant resources on a shared operator

```mermaid
flowchart LR
    subgraph KNS["kafka namespace"]
        KC["Kafka cluster<br/>Strimzi, KRaft"]
        TA["alpha-orders<br/>alpha-events"]
        TB["beta-orders"]
        UA["alpha-app<br/>+ ACLs + quotas"]
        UB["beta-app<br/>+ ACLs + quotas"]
    end
    subgraph ANS["demo-alpha namespace"]
        AM["messaging stack<br/>creates_tenant_resources: [event-bus]"]
    end
    subgraph BNS["demo-beta namespace"]
        BM["messaging stack"]
    end
    AM -->|"KafkaTopic, KafkaUser<br/>prefix alpha-"| TA
    AM --> UA
    BM -->|"prefix beta-"| TB
    BM --> UB
    KC -.->|"derives ACLs from prefix"| UA
    KC -.->|"derives ACLs from prefix"| UB
```

Three rules make this safe: mandatory `{{ instance }}-` prefix, ACLs **derived by the provider** rather than written by each application, and `KafkaUser` throughput quotas — because ResourceQuota does not limit bytes per second.

Specified in: companion §10.

---

## 15. Catalog, demo and component

```mermaid
flowchart TD
    subgraph CAT["kind: catalog — platform team"]
        C1["keycloak@4.1.0"]
        C2["kafka@2.0.0"]
        C3["webapp-3tier@2.3.0"]
        CN["years · many instances<br/>strict semver · may publish capabilities"]
    end
    subgraph COMP["components — reusable stack templates"]
        P1["component/neo4j"]
        P2["component/mongodb"]
        P3["component/postgres"]
        P4["component/redis"]
    end
    subgraph DEMO["kind: demo — project office"]
        D1["demo-acme-graph@0.1.0<br/>expiresOn required"]
        DN["weeks · one instance · leaf only<br/>may NOT publish capabilities"]
    end
    COMP -->|"stacks[].use"| D1
    COMP -->|"stacks[].use"| C3
    CAT -->|"requires capabilities"| D1

    style DEMO fill:#e8f5e9
    style COMP fill:#e8f0fe
```

The component catalog is what makes the demo category viable: the project office writes one bespoke stack and a values file, not infrastructure. Twenty minutes instead of a day.

Specified in: companion §5.

---

## 16. Reading order

```mermaid
flowchart LR
    S["Start here"] --> O["This overview"]
    O --> A1["archetype-model §3 layers<br/>§4 capabilities and traits"]
    A1 --> A2["companion §5 anatomy<br/>§6 manifest"]
    A2 --> B1["architecture §3 architecture<br/>§4 element reference"]
    B1 --> B2["pick ONE guide<br/>§5 GKE or §6 EKS"]
    B2 --> C1["architecture §11 identity<br/>§12 environments"]
    C1 --> C2["companion §8 §9 pools<br/>§12 resolution"]
    C2 --> D1["architecture §13 policy<br/>§14 CI/CD"]
    D1 --> D2["risk-register.md<br/>top five first"]
```

Read one runtime guide, not five. They are the same graph with different facts on the edges; §6.8 tabulates the differences.
