# Platform

Multi-cloud infrastructure platform: **Terramate CLI + OpenTofu**, with an archetype
packaging model for composing applications onto it.

GCP, AWS and Azure at parity; designed so a fourth cloud touches only layers 0–2.

## Start here

Documentation is **bilingual**: every document exists in English (`docs/en/`) and in Spanish (`docs/es/`), kept in sync. Pick your language:

| Read | For |
|---|---|
| [`docs/en/`](docs/en/) | Documentation in **English** |
| [`docs/es/`](docs/es/) | Documentación en **español** |
| [`CLAUDE.md`](CLAUDE.md) | Decision log: what is settled, what is open, and the traps. See "Bilingual documentation" for the rule on which language is authored first |

Inside each language folder:

| Read | For |
|---|---|
| `platform-overview.md` | Diagram-led map of everything. **Start here** |
| `archetype-model.md` | What may be composed with what — manifests, capabilities, traits, pools, CMDB, resolution |
| `terramate-outputs-sharing-architecture.md` | How it is generated and applied — generators, outputs sharing, IAM, policy, CI/CD, five runtime guides |
| `developer-guide.md` | For application developers — branching, versioning, build, rollback, and the three languages |
| `risk-register.md` | 62 risks by domain (59 active), reviewed at each phase gate |
| `glossary.md` | Every technical term in the documents above, with its definition |
| `proposals/sonarqube-qa/` | Design proposal, in two stages: elements and dependencies, then the layer-5 `sonarqube` archetype and its implementation plan |
| `proposals/sonarqube-qa-cloudsql/` | SonarQube's `qa` path with the default `database-platform` provider: its PostgreSQL on its own Cloud SQL instance, through the Auth Proxy sidecar |
| `proposals/keycloak-qa/` | The layer-4 `keycloak` archetype on `qa`: `oidc-idp` 4.2.0, Entra ID as upstream IdP, consumer clients as tenant resources, Cloud SQL data |
| `proposals/external-secrets-qa/` | The layer-3 `secrets-eso-gsm` archetype on `qa`: External Secrets Operator over Secret Manager, the `secrets` 2.0.0 contract and the `eso` trait |
| `proposals/monitoring-qa/` | The layer-3 `monitoring-oss` archetype on `qa` and its layer-1b counterpart: Prometheus, Alertmanager, Loki, Fluent Bit, Grafana, and who watches the watcher |
| `proposals/cert-manager-qa/` | The layer-3 `cert-manager` archetype on `qa`: in-cluster internal CA, approver-policy, trust-manager, the `certs` 1.1.0 contract and the `cert-manager` trait |
| `proposals/envoy-gateway-qa/` | The layer-3 `gateway-envoy-gke` archetype on `qa`: one Gateway behind the GLB via a standalone NEG, hostname ownership between tenants, timeouts, the `ingress` 3.2.0 contract and the `backend-tls` trait |
| `proposals/kafka-qa/` | The layer-4 `kafka` archetype on `qa`: Strimzi in KRaft mode, mTLS with the internal CA, the multi-tenant contract (prefixed topics, derived ACLs, quotas), capacity budgets and the `event-bus` 2.1.0 contract |
| `proposals/gatekeeper-qa/` | The layer-2b `policy-gatekeeper` archetype on `qa`: who owns each admission rule, the consolidated rule catalogue, PSA for Pod Security, exceptions by name derived from resolution, `gator` tests in CI and the `policy` 1.1.0 contract |
| `proposals/postgres-cloudsql-qa/` | The layer-4 `postgres-cloudsql` archetype, default `database-platform` provider: a global provider per environment, managed first, the `database-platform` 2.0.0 contract shared with CloudNativePG, and the provider matrix in CI |
| `proposals/postgres-operator-qa/` | The layer-4 `postgres-operator` archetype, the CloudNativePG alternative `database-platform` provider: one `Cluster` per consumer in its own namespace, a platform image catalog by digest, barman-cloud backups to a bucket per consumer, in-place operator upgrades; not bound in `qa` |
| `proposals/gke-qa/` | The layer-2 `gke` archetype on `qa`: regional GKE Standard with private nodes, address claims, node pools declared by the environment and restricted to their owners, the storage class, Dataplane V2 and the `cluster` 2.5.0 contract |
| `proposals/network-qa/` | The network part of the layer-1 `environment` archetype on `qa`: VPC, Cloud NAT with dynamic ports, Google APIs through private DNS zones and the private VIP, PSA, the `qa.internal` zone, and the `network` 3.0.0 contract |
| `proposals/edge-qa/` | The edge of the layer-1 `environment` archetype on `qa`: public zone and wildcard, Certificate Manager, Cloud Armor with preview-then-deny and SAML exclusions, the managed Global external Application LB to Envoy's NEG, L4 exceptions, and the `env-edge` 1.0.0 contract |
| `proposals/cmdb-qa/` | The `qa` CMDB, levels 0 and 1 of AM §11: the declared half generated and checked in the PR on `main`, the observed half on its own `cmdb-observed` branch, a private release asset as the read model, and the guards that use it — reference counting by edges before a destroy, broken contracts and blast radius in the PR |
| `proposals/infra-repo-qa/` | The deployment repository (`disasterproject/infra`): layout, trunk-based branches and why there is no `qa` branch, GitHub Environments per environment, rulesets and CODEOWNERS, and workflow templates — preview, deploy per environment, drift, destroy, CMDB sync, image mirroring |
| `proposals/appsec-qa/` | Software and AI life-cycle security on `qa`: SonarQube, Trivy, Checkov, OWASP ZAP, Nuclei and A.I.G consolidated in DefectDojo — where each tool runs, when it blocks, how results are imported, the `defectdojo`, `dast` and `aig` archetypes, and the applications' reusable `appsec.yml` workflow |
| `proposals/landing-zone-qa/` | Layer 0 for `qa`: the one-time bootstrap, folders and projects, org policies, KMS key rings per environment, Artifact Registry and image mirroring, GitHub federation and pipeline identities, the parent zone and the public identifier, and the shared Binary Authorization policy the landing zone must own |

The two halves meet at `binding.tm.hcl`: the resolver writes globals, the generators
consume them.

## Layout

| Path | Contents |
|---|---|
| `docs/` | Reference documents — the specification |
| `registry/` | **Source of truth** for capabilities, traits, zones, labels |
| `schemas/` | JSON Schema — **generated** from `registry/`, never hand-edited |
| `.github/workflows/` | `validate.yml`: schema and registry well-formedness, manifest validation, policy tests |
| `poc/` | Phase 0 evidence: the two-stack Terramate PoC and its measured results |

Planned, not yet present: `policy/` (Rego for conftest, plus `*_test.rego`), `archetypes/`, `components/`, `environments/`, `cmdb-data/`, and the Terramate tree listed in `CLAUDE.md`. The validation commands below skip what does not exist yet.

## Status

Documentation complete. **Nothing deployed yet.** This repository holds documentation
and proposals only; the deployment repository it describes — layout, branches,
GitHub Environments and workflow templates — is specified in
`docs/en/proposals/infra-repo-qa/`.

Phase 0 of the roadmap (architecture document §16) is done locally: `poc/` measured the
Terramate assumptions against a pinned version (`poc/RESULTS.md`). The late-binding model
holds; globals in `stack.after` are a parse error, so the resolver writes literal tags.
The cloud half of Phase 0 is checked in the first `qa` deployment.

## Validating

```bash
check-jsonschema --schemafile schemas/archetype-manifest.schema.json archetypes/*/manifest.yaml
check-jsonschema --schemafile schemas/environment-binding.schema.json environments/*/binding.yaml
check-jsonschema --schemafile schemas/pool-ledger.schema.json cmdb-data/pools/*.json

conftest verify --policy policy/
conftest test --policy policy/ --data registry/ resolution.json stacks.json
```
