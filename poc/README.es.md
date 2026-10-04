# `poc/` — validación de la fase 0

El experimento desechable de dos stacks del que `CLAUDE.md` → "Where to start"
hace depender todo lo demás. Responde, contra un Terramate fijado, si el modelo
de *late binding* de `docs/es/terramate-outputs-sharing-architecture.md`
funciona de verdad.

**Lee [`RESULTS.es.md`](RESULTS.es.md) para las respuestas.** Titular: las dos
suposiciones en las que descansa el diseño de `imports/contracts/` se cumplen;
`stack.after` con un global no funciona y falla de forma ruidosa, no silenciosa,
lo que es un cambio de convención y no un rediseño.

## Ejecución

```bash
cd poc
./run-poc.sh                 # or: ./run-poc.sh /path/to/workdir
```

Necesita `terramate` y `tofu` en el `PATH`. Sin credenciales de nube y sin red:
los stacks no usan proveedores a propósito, así que `tofu init` funciona sin
conexión y las respuestas de Terramate no se contaminan con la configuración de
la nube. Tarda segundos.

`run-poc.sh` copia el árbol a un directorio temporal **fuera** de cualquier
repositorio git antes de ejecutar. No es casual: Terramate toma la raíz del
proyecto de la raíz de git y rechaza `required_version` / `config.experiments`
en cualquier otro sitio, así que esta PoC no puede ejecutarse en su sitio dentro
de `proposal_documents`. Ver RESULTS.es.md → "Por qué un arnés".

## Estructura

| Ruta | Propósito |
|---|---|
| `terramate.tm.hcl` | Configuración raíz — `required_version`, `experiments`, `sharing_backend` |
| `globals.tm.hcl` | Los globals del **directorio padre**. Es el objeto de la suposición A1: ningún stack los redefine |
| `stacks/producer/` | `poc-producer`. Comparte una cadena, una cadena base64 y una lista |
| `stacks/consumer-inherited/` | A1 — `from_stack_id = global.producer_id`, ordenado por ruta literal |
| `stacks/consumer-interpolated/` | A2 — `from_stack_id = "${global.env}-producer"`, ordenado por `tag:producer` |
| `cases/` | Fixtures que el arnés prueba de uno en uno, ver abajo |
| `gates/run-encryption.sh` | A9 — migrar un estado en claro a un backend cifrado con el fallback solo en `TF_ENCRYPTION`; qué permite `enforced = true`. Necesita `tofu` |
| `gates/run-gates.sh` | A8 — las herramientas detrás de las puertas: el experimento `scripts`, el inventario de stacks, los namespaces y datos de conftest. Construye sus propios fixtures; necesita `terramate`, `conftest` y `jq` |

## Por qué `cases/` no es `stacks/`

`cases/after-global-expr/` y `cases/after-global-interp/` **no se pueden
analizar**, y un solo stack que no se analiza aborta la carga de configuración
entera de Terramate: todos los comandos, no solo ese stack. Dejarlos en
`stacks/` bloquearía toda la PoC. Llevan el sufijo `.fixture`, se copian de uno
en uno a un directorio de stack temporal, se miden y se eliminan.

`cases/no-after/` se analiza sin problemas. Se mantiene fuera de `stacks/` por
otra razón: es la demostración del riesgo R2 — un consumidor con un `input` y
sin orden, que Terramate programa **antes** que su productor sin informar de
nada. Mantenerlo activo haría engañoso el run-graph de referencia.

## Estado

Las suposiciones A1–A5 están respondidas (medidas el 2026-09-16, repetidas el
2026-09-28 con el mismo resultado). A6 (lecturas de estado entre proyectos con
OIDC) y A7 (plano de control alcanzable desde el runner, ahora por el endpoint
DNS) necesitan un proyecto en la nube y se comprueban en el primer despliegue de
`qa` (`landing-zone-qa` VZ1–VZ5).

Este directorio es **evidencia**, guardada en el repositorio de documentación
porque los documentos de referencia la citan. No es la semilla del repositorio
de despliegue; ver `docs/es/proposals/infra-repo-qa/`.

*[English](README.md) · resultados: [English](RESULTS.md), [Español](RESULTS.es.md)*
