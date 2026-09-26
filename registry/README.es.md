# Registry

*[English](README.md)*

**Fuente de verdad** para los vocabularios controlados. Nada más puede definirlos.

| Archivo | Define |
|---|---|
| `capabilities.yaml` | Nombres de capabilities. Exactamente un proveedor por capability por environment |
| `traits.yaml` | Vocabulario de traits. Un trait no registrado es un error de resolución |
| `zones.yaml` | Zonas de propósito dentro de un pool de environment |
| `labels.yaml` | Labels obligatorias por tipo de recurso — emitidas por el generador, validadas por Gatekeeper |

Generado a partir de aquí (por `registry-generate`, roadmap fase 2c.1, aún no escrito):

| Artefacto | Consumidor |
|---|---|
| bloques `enum` en `../schemas/*.schema.json` | `check-jsonschema` |
| bundle `registry/*.json` (ignorado por git) | `conftest --data` |
| `values.yaml` del chart de Gatekeeper | parámetros de `ConstraintTemplate` |

Para añadir un término: editar el YAML de aquí, luego regenerar. Hasta que exista el generador, el `enum` correspondiente en `schemas/` se actualiza **en el mismo commit, mecánicamente, para igualar el YAML** — nunca por su cuenta. Ver `CLAUDE.md`, "The registry is load-bearing", y el riesgo R34.
