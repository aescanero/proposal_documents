# Platform

Multi-cloud infrastructure platform: **Terramate CLI + OpenTofu**, with an archetype
packaging model for composing applications onto it.

GCP, AWS and Azure at parity; designed so a fourth cloud touches only layers 0–2.

## Start here

| Read | For |
|---|---|
| [`docs/platform-overview.md`](docs/platform-overview.md) | Diagram-led map of everything. **Start here** |
| [`docs/archetype-model.md`](docs/archetype-model.md) | What may be composed with what — manifests, capabilities, traits, pools, CMDB, resolution |
| [`docs/terramate-outputs-sharing-architecture.md`](docs/terramate-outputs-sharing-architecture.md) | How it is generated and applied — generators, outputs sharing, IAM, policy, CI/CD, five runtime guides |
| [`docs/developer-guide.md`](docs/developer-guide.md) | For application developers — branching, versioning, build, rollback, and the three languages |
| [`docs/risk-register.md`](docs/risk-register.md) | 37 risks by domain, reviewed at each phase gate |
| [`CLAUDE.md`](CLAUDE.md) | Decision log: what is settled, what is open, and the traps |

The two halves meet at `binding.tm.hcl`: the resolver writes globals, the generators
consume them.

## Layout

| Path | Contents |
|---|---|
| `docs/` | Reference documents — the specification |
| `registry/` | **Source of truth** for capabilities, traits, zones, labels |
| `schemas/` | JSON Schema — **generated** from `registry/`, never hand-edited |
| `policy/` | Rego for conftest, plus `*_test.rego` |
| `tools/archetypectl/` | The platform CLI. So far only `enrich`, which feeds the G1 gate |

## Status

Documentation complete. The only code is `tools/archetypectl` (roadmap phase 2c.2);
**nothing is deployed**.

Next step is Phase 0 of the roadmap (architecture document §16): confirm the Terramate
assumptions in a throwaway repository before writing any generators. It is an
afternoon's work and it gates everything else.

## Validating

```bash
check-jsonschema --schemafile schemas/archetype-manifest.schema.json archetypes/*/manifest.yaml
check-jsonschema --schemafile schemas/environment-binding.schema.json environments/*/binding.yaml
check-jsonschema --schemafile schemas/pool-ledger.schema.json cmdb-data/pools/*.json

terramate list --json > stacks.json
tools/archetypectl/bin/archetypectl enrich stacks.json   # adds consumes[] and after_ids[]

conftest verify --policy policy/
conftest test --policy policy/ --data registry/ resolution.json stacks.json

python3 -m unittest discover -s tools/archetypectl/tests -t tools/archetypectl
```
