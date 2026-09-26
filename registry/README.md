# Registry

**Source of truth** for the controlled vocabularies. Nothing else may define them.

| File | Defines |
|---|---|
| `capabilities.yaml` | Capability names. Exactly one provider per capability per environment |
| `traits.yaml` | Trait vocabulary. An unregistered trait is a resolution error |
| `zones.yaml` | Purpose zones inside an environment pool |
| `labels.yaml` | Mandatory labels per resource type — emitted by the generator, validated by Gatekeeper |

Generated from here (by `registry-generate`, roadmap phase 2c.1, not yet written):

| Artefact | Consumer |
|---|---|
| `enum` blocks in `../schemas/*.schema.json` | `check-jsonschema` |
| `registry/*.json` bundle (git-ignored) | `conftest --data` |
| Gatekeeper chart `values.yaml` | `ConstraintTemplate` parameters |

To add a term: edit the YAML here, then regenerate. Until the generator exists, the matching `enum` in `schemas/` is updated **in the same commit, mechanically, to equal the YAML** — never on its own. See `CLAUDE.md`, "The registry is load-bearing", and risk R34.
