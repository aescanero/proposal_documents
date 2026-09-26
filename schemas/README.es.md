# Schemas

*[English](README.md)*

JSON Schema (draft 2020-12) para los archivos que lee el resolver.

| Schema | Valida |
|---|---|
| `archetype-manifest.schema.json` | `archetypes/*/manifest.yaml` |
| `component.schema.json` | `components/*/component.yaml` |
| `environment-binding.schema.json` | `environments/*/binding.yaml` |
| `pool-ledger.schema.json` | `cmdb-data/pools/*.json` |
| `cmdb-stack.schema.json` | `cmdb-data/stacks/*.json` |

La estructura está escrita a mano. Los bloques `enum` marcados *"Generated from registry/…"* **no lo están**: vienen de `../registry/`. Editar uno de esos a mano es un bug (riesgo R34).

Brecha conocida: los bloques de build y deploy de `developer-guide.md` §2 (`frontend`, `stacks[].build`, `stacks[].deploy`) todavía no están en el schema del manifest, y `additionalProperties: false` los rechaza. Llegarán con `registry/languages.yaml`.
