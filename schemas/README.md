# Schemas

JSON Schema (draft 2020-12) for the files the resolver reads.

| Schema | Validates |
|---|---|
| `archetype-manifest.schema.json` | `archetypes/*/manifest.yaml` |
| `component.schema.json` | `components/*/component.yaml` |
| `environment-binding.schema.json` | `environments/*/binding.yaml` |
| `pool-ledger.schema.json` | `cmdb-data/pools/*.json` |
| `cmdb-stack.schema.json` | `cmdb-data/stacks/*.json` |

The structure is written by hand. The `enum` blocks marked *"Generated from registry/…"* are **not**: they come from `../registry/`. A hand edit of one of those is a bug (risk R34).

Known gap: the build and deploy blocks of `developer-guide.md` §2 (`frontend`, `stacks[].build`, `stacks[].deploy`) are not in the manifest schema yet, and `additionalProperties: false` rejects them. They arrive with `registry/languages.yaml`.
