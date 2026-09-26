# Workflows

*[English](README.md)*

| Workflow | Jobs | ¿Bloqueante hoy? |
|---|---|---|
| `validate.yml` | **Schemas y registry**: el JSON Schema y el YAML del registry están bien formados; `registry-generate --check` una vez que exista; manifiestos, components, bindings y ledgers validados contra `schemas/` | Sí, para lo que existe |
| | **Policy**: `conftest verify` sobre `policy/*_test.rego` | Omitido hasta que exista `policy/` (roadmap fase 2c.3) |

Los pipelines de la plataforma (`preview`, `deploy`, `drift`, `destroy`) están especificados en el documento de arquitectura §14 y todavía no están escritos.
