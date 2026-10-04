# PoC de la fase 0 — resultados

Valida las suposiciones enumeradas en `CLAUDE.md` → "Where to start", contra una
cadena de herramientas fijada. Cada transcripción de abajo es salida real de
`./run-poc.sh`, no una reconstrucción.

*[English](RESULTS.md)*

| | |
|---|---|
| **Terramate** | `0.16.0`; repetida con `0.17.3` (2026-09-28) con salida idéntica |
| **OpenTofu** | `v1.10.6` |
| **Fecha** | 2026-09-16 (repetida el 2026-09-28, misma cadena, mismos resultados) |
| **conftest** | `0.70.1` (OPA `1.20.2`), solo A8 |
| **Sondas de puertas** | `./gates/run-gates.sh`, 2026-10-04, Terramate `0.17.3` |
| **Arnés** | `./run-poc.sh` (ver [Por qué un arnés](#por-qué-un-arnés-y-no-solo-terramate-generate)) |

---

## Resumen

| # | Suposición | Veredicto |
|---|---|---|
| A1 | `from_stack_id` resuelve un global **heredado de un directorio padre** | ☑ **Confirmada** |
| A2 | `from_stack_id` acepta **interpolación** (`"${global.env}-producer"`) | ☑ **Confirmada** |
| A3 | `stack.after` acepta una ruta derivada de globals | ☒ **Refutada — pero falla de forma RUIDOSA, no silenciosa** |
| A3b | Los filtros por tag funcionan como alternativa de orden | ☑ **Confirmada** |
| A4 | `--mock-on-fail` se comporta como está documentado cuando el productor no tiene estado | ☑ **Confirmada** |
| A5 | De extremo a extremo: los valores reales fluyen productor → consumidor una vez aplicados | ☑ **Confirmada** |
| A6 | Lecturas de estado entre proyectos / cuentas con roles OIDC | ☐ **No probada** — necesita credenciales de nube |
| A7 | Plano de control privado alcanzable desde el runner elegido | ☐ **No probada** — ya superada: el pipeline llega a GKE por el endpoint DNS del plano de control (solo IAM, sin camino de red), así que lo que queda es la comprobación VZ5 de `landing-zone-qa` |
| A8a | Un bloque `script` carga sin el experimento `scripts` (0.17.3) | ☒ **Refutada, ruidosamente** — falla la carga de toda la configuración |
| A8b | `terramate experimental eval` expone `terramate.stack.after` | ☒ **Refutada** — solo `id`, `tags`, `path` |
| A8c | `terramate debug show metadata` lleva `after` | ☑ **Confirmada** — el inventario de stacks se construye con él |
| A8d | Un global en `output.value` se resuelve al generar | ☒ **Refutada** — se copia literalmente: `value = global.project_id` llega al `.tf`, donde no es válido |
| A8e–h | Los comandos conftest de G1 y G3 evalúan las políticas | ☒ **Refutada** — cero reglas sin `--all-namespaces` o con un `--namespace` inexacto; `data.registry` vacío con `--data registry/` |

**Efecto neto sobre la arquitectura: el modelo de *late binding* funciona.** A1
y A2 son las dos en las que descansa todo el diseño de `imports/contracts/`, y
ambas se cumplen. A3 no se cumple, pero su modo de fallo es el contrario del que
se temía, y la alternativa documentada funciona — así que el coste es un cambio
de convención de una línea, no un rediseño.

---

## Qué contiene la PoC

Tres stacks y tres fixtures, deliberadamente sin proveedores — solo locals y
outputs, así que `tofu init` no necesita red ni credenciales y las respuestas de
Terramate no se contaminan con la configuración de la nube.

```
poc/
  terramate.tm.hcl                  root config: required_version, experiments, sharing_backend
  globals.tm.hcl                    PARENT globals: env, producer_id, producer_path
  stacks/
    producer/                       id poc-producer, tags [poc, producer]
    consumer-inherited/             A1 — from_stack_id = global.producer_id
    consumer-interpolated/          A2 — from_stack_id = "${global.env}-producer"
  cases/                            fixtures probed one at a time, see A3
    after-global-expr/              after = [global.producer_path]
    after-global-interp/            after = ["${global.producer_path}"]
    no-after/                       an input with no ordering at all
  gates/run-gates.sh                A8 — builds its own fixtures: scripts experiment, inventory, conftest flags
```

El productor comparte tres valores elegidos para ejercitar la trampa de la
corrección de tipos de los mocks: una cadena simple, una cadena base64 y una
lista.

---

## A1 — global heredado en `from_stack_id` ☑

`global.producer_id` se define **solo** en `/globals.tm.hcl`, nunca en el
directorio del stack. `stacks/consumer-inherited/contract.tm.hcl`:

```hcl
input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = global.producer_id
  value         = outputs.cluster_endpoint.value
  mock          = "https://mock-endpoint.example.invalid"
}
```

`terramate generate`:

```
Code generation report

Successes:

- /stacks/consumer-inherited
	[+] _main.tf
	[+] _observed.tf
	[+] _sharing_generated.tf

- /stacks/consumer-interpolated
	[+] _main.tf
	[+] _observed.tf
	[+] _sharing_generated.tf

- /stacks/producer
	[+] _main.tf
	[+] _sharing_generated.tf
```

Generar no prueba por sí solo el enlace — el fichero generado son solo
declaraciones de variables:

```hcl
// stacks/consumer-inherited/_sharing_generated.tf
// TERRAMATE: GENERATED AUTOMATICALLY DO NOT EDIT

variable "cluster_endpoint" {
  type = any
}
variable "cluster_ca_data" {
  type = any
}
variable "pod_ranges" {
  type = any
}
```

El enlace lo prueba A5, más abajo, donde llega el valor real del productor.

---

## A2 — interpolación en `from_stack_id` ☑

```hcl
input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = "${global.env}-producer"   # global.env = "poc"
  value         = outputs.cluster_endpoint.value
  mock          = "https://mock-endpoint.example.invalid"
}
```

Genera y resuelve igual que A1. Para probar que la cadena se renderiza de verdad
y no se ignora, la PoC se repitió con el id apuntando a un productor
inexistente (`"${global.env}-does-not-exist"`):

```
Error: one or more commands failed
> Stack /stacks/consumer-interpolated needs output from stack ID "poc-does-not-exist" but it cannot be found
```

El error nombra **`poc-does-not-exist`**, así que `global.env` se interpoló. A2
se cumple.

> **Hallazgo adicional.** `--mock-on-fail` **no** enmascara un *stack*
> productor inexistente — el error de arriba se produjo *con* `--mock-on-fail`
> activo. Los mocks cubren un *valor* de output ausente, no un `from_stack_id`
> roto. Un error tipográfico en un contrato se detecta, por tanto, en la
> previsualización del PR, no en el despliegue. Es mejor de lo supuesto y
> merece la pena apoyarse en ello.

---

## A3 — `stack.after` con una ruta derivada de globals ☒

**Esta es la que cambia una decisión, así que se informa completa.**

`CLAUDE.md` predecía: *"falla **en silencio** — una expresión no resuelta deja
el orden vacío en lugar de dar un error."* Esa predicción es **incorrecta para
0.16.0**. Los globals no están en el ámbito del bloque `stack` en absoluto, y
Terramate aborta la carga de configuración entera:

```
----- A3 probe: cases/after-global-expr
Error: unable to parse configuration
> …/stacks/_probe/stack.tm.hcl:14,12-18: terramate schema error: … failed to evaluate "after" attribute: eval expression: There is no variable named "global"

----- A3 probe: cases/after-global-interp
Error: unable to parse configuration
> …/stacks/_probe/stack.tm.hcl:12,15-21: terramate schema error: … failed to evaluate "after" attribute: eval expression: There is no variable named "global"
```

La interpolación tampoco ayuda — ver la segunda prueba. Es una parada total de
**todos** los comandos (`list`, `generate`, `run`, `run-graph`), no solo de ese
stack.

### Qué funciona en su lugar

Medido con `terramate experimental run-graph`, no por ausencia de error:

| Forma | ¿Crea arista? |
|---|---|
| `after = [global.producer_path]` | **error de análisis** |
| `after = ["${global.producer_path}"]` | **error de análisis** |
| `after = ["/stacks/producer"]` | ☑ sí |
| `after = ["../producer"]` | ☑ sí |
| `after = ["tag:producer"]` | ☑ sí |

Los stacks de la PoC usan la ruta literal (`consumer-inherited`) y el filtro por
tag (`consumer-interpolated`). Ambos producen aristas:

```
digraph  {
	n1[label="PoC consumer — inherited global in from_stack_id"];
	n3[label="PoC consumer — interpolated from_stack_id + tag ordering"];
	n2[label="PoC producer"];
	n2->n1;
	n2->n3;
}
```

```
----- A3 baseline — terramate list --run-order (the definitive ordering)
stacks/producer
stacks/consumer-inherited
stacks/consumer-interpolated
```

```
----- A3 baseline — order actually used by terramate run
…/stacks/producer
…/stacks/consumer-inherited
…/stacks/consumer-interpolated
```

### El fallo silencioso es real — solo que es otro

Como un `after` derivado de globals no se puede analizar, el peligro de orden no
es una expresión no resuelta. Es un `after` que simplemente se **olvidó**.
`cases/no-after/` es un stack con un `input` válido que lee del productor y sin
ningún orden. Terramate lo acepta sin quejarse:

```
# run-graph: look for an edge into 'A3 probe — input with no after'. There is none.
digraph  {
	n1[label="A3 probe — input with no after"];
	n2[label="PoC consumer — inherited global in from_stack_id"];
	n4[label="PoC consumer — interpolated from_stack_id + tag ordering"];
	n3[label="PoC producer"];
	n3->n2;
	n3->n4;
}
# run-order: the probe may be scheduled before the producer it reads from.
stacks/_probe
stacks/producer
stacks/consumer-inherited
stacks/consumer-interpolated
# and generate is perfectly happy with it:
Code generation report

Successes:

- /stacks/_probe
	[+] _sharing_generated.tf

generate exit=0
```

**`stacks/_probe` se programa primero — antes del productor cuyo output lee — y
nada en ningún sitio informa de un problema.** Es el riesgo R2, reproducido, y
es exactamente por lo que tiene que existir la política conftest G1.

### Consecuencias

1. **El resolutor debe emitir valores `after` literales.** No puede referenciar
   globals ahí. Como el resolutor ya escribe `binding.tm.hcl`, igualmente puede
   escribir una ruta o tag literal en `stack.tm.hcl` — es un cambio de
   generación de código, no de diseño.
2. **Preferir `tag:` sobre rutas.** Los tags sobreviven a que un stack se mueva
   en disco; las rutas literales no. `docs/…-architecture.md` §4.5 ya prefiere
   tags.
3. **R2 sigue siendo el riesgo principal, y G1 sigue siendo obligatorio.** La
   buena noticia es solo que una *expresión no resoluble* ya no puede ser la
   causa.
4. **Corregir `CLAUDE.md`.** El texto de la trampa ("Globals in `stack.after`
   remain an open question, and it fails silently") está ahora medido y es
   incorrecto en su detalle. El reemplazo sugerido está en
   [Correcciones a la documentación](#correcciones-a-la-documentación).

---

## A4 — `--mock-on-fail` sin estado del productor ☑

El productor no se aplica deliberadamente antes de este paso, así que
`tofu output -json` en el directorio del productor no puede tener éxito.

### A4a — camino de previsualización: `--enable-sharing --mock-on-fail`

```
Changes to Outputs:
  + observed_ca_decoded  = "mock-ca-bundle"
  + observed_endpoint    = "https://mock-endpoint.example.invalid"
  + observed_first_range = "10.255.0.0/24"
  + observed_range_count = 1

Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
exit=0
```

```json
// stacks/consumer-inherited — tofu output -json
{
  "observed_ca_decoded":  { "type": "string", "value": "mock-ca-bundle" },
  "observed_endpoint":    { "type": "string", "value": "https://mock-endpoint.example.invalid" },
  "observed_first_range": { "type": "string", "value": "10.255.0.0/24" },
  "observed_range_count": { "type": "number", "value": 1 }
}
```

Los mocks se sustituyen, el apply tiene éxito y `base64decode()` sobre la CA
simulada funciona — así que el mock tenía el tipo correcto.

### A4b — camino de despliegue: `--enable-sharing`, sin `--mock-on-fail`

Mismo estado (el productor sigue sin aplicar). Debe fallar, y falla:

```
terramate: Entering stack in /stacks/consumer-inherited
Error: one or more commands failed
> eval expression: evaluating input value: This object does not have an attribute named "cluster_endpoint".
exit=1
```

Es el comportamiento del que depende la regla de los dos bloques `script` con
nombre. Confirmado.

### A4c — los mocks NO se comprueban por tipo, y la puerta G0 no puede detectar uno malo

`CLAUDE.md` advierte que un mock de tipo incorrecto "pasa la comprobación de
tipos en local y explota en el apply". Medido, y es peor — un mock malo no
cambia ningún fichero generado, así que `terramate generate` no tiene nada que
informar:

**campo base64 simulado como `"mock"`:**

```
-- terramate generate:
Nothing to do, generated code is up to date
generate exit=0
-- tofu apply with --mock-on-fail:
Error: Error in function call
  on _main.tf line 7, in locals:
   7:   decoded_ca  = base64decode(var.cluster_ca_data)
    │ while calling base64decode(str)
    │ var.cluster_ca_data is "mock"
```

**campo lista simulado como cadena:**

```
Changes to Outputs:
  + observed_range_count = 13
…
Error: Invalid index
  on _main.tf line 8, in locals:
   8:   first_range = var.pod_ranges[0]
    │ var.pod_ranges is "10.255.0.0/24"
This value does not have any indices.
```

> **Lee `observed_range_count = 13` con atención.** `length()` sobre la cadena
> simulada devolvió la *longitud de la cadena* y tuvo éxito. Solo falló el
> índice `[0]`. Una lista simulada como cadena puede, por tanto, pasar por
> aritmética, `count` o una comprobación de capacidad produciendo un número
> erróneo pero plausible en lugar de un error. La corrección de tipos de los
> mocks no se puede dejar a "el plan lo detectará".

Como `terramate generate --detailed-exit-code` devuelve 0 con un mock malo,
**la puerta G0 no puede cubrir esto.** Una regla conftest sobre los bloques
`input` es el único sitio donde detectarlo — se recomienda ampliar G1 para que
compruebe que cada `mock` coincide con la forma declarada en el contrato de su
capacidad.

---

## A5 — de extremo a extremo, valores reales ☑

Primero se aplica el productor, luego los consumidores, sin mocks en juego:

```
# producer
Outputs:
cluster_ca_data = "cG9jLWNsdXN0ZXItY2EtYnVuZGxl"
cluster_endpoint = "https://poc-producer.example.invalid"
pod_ranges = [
  "10.10.0.0/24",
  "10.10.1.0/24",
]
```

```json
// stacks/consumer-inherited     (A1: bare inherited global)
{
  "observed_ca_decoded":  { "type": "string", "value": "poc-cluster-ca-bundle" },
  "observed_endpoint":    { "type": "string", "value": "https://poc-producer.example.invalid" },
  "observed_first_range": { "type": "string", "value": "10.10.0.0/24" },
  "observed_range_count": { "type": "number", "value": 2 }
}

// stacks/consumer-interpolated  (A2: "${global.env}-producer")
{
  "observed_endpoint":    { "type": "string", "value": "https://poc-producer.example.invalid" },
  "observed_first_range": { "type": "string", "value": "10.10.0.0/24" },
  "observed_range_count": { "type": "number", "value": 2 }
}
```

Ningún prefijo `mock-` en ningún sitio, `range_count` es 2 y no 1, y la CA
decodificada es la del productor. **Los dos estilos de enlace llegaron al mismo
productor con datos reales.** A1, A2 y A5 se cumplen.

---

## A8 — las herramientas detrás de las puertas ☒

Cinco comportamientos de los que dependen las puertas, los contratos y el inventario de stacks,
probados contra las versiones fijadas con `./gates/run-gates.sh`. Cada uno, tal
como estaba escrito, o no cargaba la configuración, o generaba código inválido, o
**pasaba sin haber evaluado nada**.

```
========== A8a — a script block without the "scripts" experiment ==========
----- terramate list
Error: unable to parse configuration
> <work>/tm/b/stack.tm.hcl:6,1-16: terramate schema error: loading from <work>/tm/b: unrecognized block "script" (script is an experimental feature, it must be enabled before usage with `terramate.config.experiments = ["scripts"]`)
[exit 1]
----- same, with experiments = ["outputs-sharing", "scripts"]
script ran
[exit 0]

========== A8b — experimental eval: is terramate.stack.after exposed? ==========
Error: <cmdline>:1,64-70: eval expression: eval "tm_jsonencode({id = terramate.stack.id, after = terramate.stack.after})": This object does not have an attribute named "after".
[exit 1]

========== A8c — debug show metadata carries after ==========
stack "/b":
	terramate.stack.id="b"
	terramate.stack.tags=["gcp","qa"]
	terramate.stack.after=["tag:gcp:qa:network","/a"]
[exit 0]

========== A8d — output.value is copied verbatim into the generated code ==========
// TERRAMATE: GENERATED AUTOMATICALLY DO NOT EDIT

output "project_id" {
  value = global.project_id
}

========== A8e — G1 without --all-namespaces ==========
0 tests, 0 passed, 0 warnings, 0 failures, 0 exceptions
[exit 0]

========== A8f — --all-namespaces, but --data registry/ (YAML at the root of data) ==========
2 tests, 2 passed, 0 warnings, 0 failures, 0 exceptions
[exit 0]

========== A8g — --all-namespaces and the bundle with top-level key registry ==========
FAIL - manifest.json - archetype.composition - unknown trait bogus
2 tests, 1 passed, 0 warnings, 1 failure, 0 exceptions
[exit 1]

========== A8h — G3: --namespace terraform vs the exact package ==========
----- --namespace terraform
0 tests, 0 passed, 0 warnings, 0 failures, 0 exceptions
[exit 0]
----- --namespace terraform.public_names
FAIL - plan.json - terraform.public_names - environment name in a public name
[exit 1]
```

| Sonda | Consecuencia | Aplicada en |
|---|---|---|
| A8a | `experiments` debe listar `"scripts"` además de `"outputs-sharing"`. Sin él ningún comando `terramate` carga la configuración | Arquitectura §4.1; `infra-repo-qa` `terramate.tm.hcl` |
| A8b–c | `ci/stacks-json.sh` lee `debug show metadata`; con `experimental eval` el inventario no tiene `after` y la regla de R2 no puede ejecutarse | Arquitectura §14.4; `infra-repo-qa` `ci/stacks-json.sh` |
| A8d | El `value` de un contrato solo puede referenciar lo que el código generado declara — `module.*`, `resource.*`, `data.*`, `local.*`, y `var.*` solo para una variable que crea un `input`. No `global.*`, no un `var.*` que nadie declara | Arquitectura §4.3, §5.2 |
| A8e | G1 ejecuta `conftest test --all-namespaces`: las políticas viven en `terramate.*`, `archetype.*`, `environment.*`, nunca en `main` | Arquitectura §13, §14.4; `ci/g1.sh` |
| A8f–g | `--data registry/registry.json`, un paquete con la clave de primer nivel `registry`; `--data registry/` pone cada fichero en la raíz de `data` y un rasgo desconocido pasa | Ídem; `registry/README.es.md` |
| A8h | G3 nombra cada paquete exactamente: `--namespace terraform` no coincide con `terraform.public_names` | Arquitectura §13.4 |
| todas | Toda puerta conftest falla cuando evaluó cero reglas (`ct` en `ci/g1.sh`) | Arquitectura §14.4 |

---

## No probado

| | Por qué |
|---|---|
| **A6** lecturas de estado entre proyectos / cuentas con roles OIDC | Necesita cuentas de nube reales y una relación de confianza OIDC. Solo la desbloquea un entorno de nube; esta PoC usa estado local a propósito. |
| **A7** plano de control privado alcanzable desde el runner | Necesita un clúster real. La pregunta ha cambiado: con el endpoint DNS (`landing-zone-qa` DZ4) no hay camino de red del runner que probar, solo IAM — ver VZ5 en esa propuesta. |

Ambas siguen abiertas frente a `CLAUDE.md` → "Where to start". Son el trabajo
restante de la fase 0, ninguna se ve afectada por los hallazgos anteriores, y
ambas se comprueban en el primer despliegue de `qa` (`landing-zone-qa`
VZ1–VZ5).

---

## Correcciones a la documentación

Discrepancias medidas entre los documentos y Terramate 0.16.0. Ninguna es fatal;
todas deben corregirse antes de que nadie construya sobre ellas.

| Dónde | Dice | En realidad |
|---|---|---|
| Trampas de `CLAUDE.md`; nota de `docs/…-architecture.md` §4.4 | Los globals en `stack.after` "fallan **en silencio**" | Error de análisis rotundo, `There is no variable named "global"`. El fallo silencioso es un `after` **ausente**, no uno sin resolver. |
| `CLAUDE.md:164`, `docs/platform-overview.md:51` | La puerta G0 es `terramate generate --check` | **No existe esa opción** — `Error: unknown flag --check`. Usar `terramate generate --detailed-exit-code` (0 = al día, 2 = deriva, 1 = error). Esto no dice nada de `registry-generate --check`, que es una herramienta que este proyecto aún tiene que escribir y puede definir como quiera. |
| `docs/…-architecture.md` §4.3 | `output.description` se "emite en el bloque `output` generado" | No se emite. El bloque generado es solo `output "cluster_endpoint" { value = local.endpoint }`. Las descripciones sobreviven como documentación del contrato en `imports/contracts/`, pero no llegan a `tofu output`. |
| — | — | `terramate experimental run-graph` etiqueta los nodos con `stack.name`, no con `stack.id`. Usar `terramate list --run-order` cuando se necesiten ids. |

Las cuatro se aplicaron a `CLAUDE.md` y a los documentos de referencia, en los
dos idiomas, el 2026-09-28.

Reemplazo sugerido para el párrafo de la trampa en `CLAUDE.md`:

> **Los globals no se resuelven en `stack.after` — es un error de análisis, no
> uno silencioso** (medido, Terramate 0.16.0). El resolutor debe escribir
> valores literales; preferir `after = ["tag:<capability>"]` a una ruta para que
> un stack pueda moverse. El fallo silencioso que queda es un `after`
> *olvidado*: un consumidor con un `input` y sin orden se genera limpiamente y
> puede programarse antes que su productor, sin error en ninguna fase. Eso es
> R2, y G1 es lo que lo detecta.

---

## Por qué un arnés y no solo `terramate generate`

Terramate obtiene la raíz del proyecto de la **raíz de git**, y
`required_version` y `config.experiments` solo pueden declararse ahí:

```
terramate schema error: attribute terramate.required_version can only be
declared at the project root directory
Warning: root config found outside root dir: …/poc
```

Así que `poc/` no puede ejecutarse en su sitio dentro de `proposal_documents`.
`run-poc.sh` copia el árbol (solo fuentes — ni ficheros generados ni estado) a
un directorio temporal fuera de cualquier repositorio git, donde `poc/` pasa a
ser la raíz del proyecto.

Esto importa más allá de la PoC: **un proyecto Terramate es un repositorio git
con una configuración raíz.** Incluir un segundo proyecto Terramate en un
subdirectorio de uno existente no funciona, lo que condiciona cómo puede
organizarse el repositorio real.

### Reproducción

```bash
cd poc
./run-poc.sh                 # or: ./run-poc.sh /path/to/workdir
```

Requiere `terramate` y `tofu` en el `PATH`. Sin credenciales de nube, sin más red
que los dos binarios. Tarda unos segundos.
