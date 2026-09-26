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
| `risk-register.md` | 53 risks by domain (52 active), reviewed at each phase gate |
| `glossary.md` | Every technical term in the documents above, with its definition |
| `proposals/sonarqube-qa/` | Design proposal, in two stages: elements and dependencies, then the layer-5 `sonarqube` archetype and its implementation plan |

The two halves meet at `binding.tm.hcl`: the resolver writes globals, the generators
consume them.

## Layout

| Path | Contents |
|---|---|
| `docs/` | Reference documents — the specification |
| `registry/` | **Source of truth** for capabilities, traits, zones, labels |
| `schemas/` | JSON Schema — **generated** from `registry/`, never hand-edited |
| `.github/workflows/` | `validate.yml`: schema and registry well-formedness, manifest validation, policy tests |

Planned, not yet present: `policy/` (Rego for conftest, plus `*_test.rego`), `archetypes/`, `components/`, `environments/`, `cmdb-data/`, and the Terramate tree listed in `CLAUDE.md`. The validation commands below skip what does not exist yet.

## Status

Documentation complete. **Nothing built yet.**

Next step is Phase 0 of the roadmap (architecture document §16): confirm the Terramate
assumptions in a throwaway repository before writing any generators. It is an
afternoon's work and it gates everything else.

## Validating

```bash
check-jsonschema --schemafile schemas/archetype-manifest.schema.json archetypes/*/manifest.yaml
check-jsonschema --schemafile schemas/environment-binding.schema.json environments/*/binding.yaml
check-jsonschema --schemafile schemas/pool-ledger.schema.json cmdb-data/pools/*.json

conftest verify --policy policy/
conftest test --policy policy/ --data registry/ resolution.json stacks.json
```
