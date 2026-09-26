# Workflows

*[Español](README.es.md)*

| Workflow | Jobs | Blocking today |
|---|---|---|
| `validate.yml` | **Schemas and registry**: JSON Schema and registry YAML are well-formed; `registry-generate --check` once it exists; manifests, components, bindings and ledgers validated against `schemas/` | Yes, for what exists |
| | **Policy**: `conftest verify` over `policy/*_test.rego` | Skipped until `policy/` exists (roadmap phase 2c.3) |

The platform pipelines (`preview`, `deploy`, `drift`, `destroy`) are specified in the architecture document §14 and are not written yet.
