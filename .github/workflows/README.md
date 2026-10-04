# Workflows

*[Español](README.es.md)*

| Workflow | Jobs | Blocking today |
|---|---|---|
| `validate.yml` | **Schemas and registry**: JSON Schema and registry YAML are well-formed; `registry-generate --check` once it exists, and until then `.github/scripts/check-registry-enums.py` (schema enums equal the registry); manifests, components, bindings and ledgers validated against `schemas/`; a directory that exists and matches no file fails, because an empty glob validates nothing | Yes, for what exists |
| | **Policy**: `conftest verify` over `policy/*_test.rego` | Skipped until `policy/` exists (roadmap phase 2c.3) |

The platform pipelines (`preview`, `deploy`, `drift`, `destroy`) are specified in the architecture document §14 and are not written yet.
