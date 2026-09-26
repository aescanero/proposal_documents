# CLAUDE.md

*[English](CLAUDE.md)*

Contexto para Claude Code trabajando en este repositorio. Léelo antes de tocar nada.

Este archivo es el **registro de decisiones**. Registra qué se asentó y por qué, para que no vuelvas a debatir elecciones ya hechas ni adivines la justificación. Los documentos de referencia en `docs/` son la especificación; este archivo te dice qué partes están asentadas, cuáles siguen abiertas, y cuáles son las trampas.

---

## Qué es este repositorio

Una plataforma de infraestructura multi-nube construida sobre **Terramate CLI + OpenTofu**, con un modelo de empaquetado por archetype por encima. Dos mitades:

| Mitad | Documento | Responde |
|---|---|---|
| **Resolve** | `archetype-model.md` | Qué se puede componer con qué — manifiestos, capabilities, traits, pools, CMDB, resolución |
| **Generate** | `terramate-outputs-sharing-architecture.md` | Cómo se genera y se aplica — generadores, outputs sharing, IAM, política, CI/CD, guías por nube |

Además `platform-overview.md` (mapa guiado por diagramas, léelo primero), `risk-register.md` (53 riesgos por dominio, 52 activos), `glossary.md` (cada término, definido) y `developer-guide.md` (la mitad del desarrollador de aplicaciones — branching, versionado, build, rollback). Cada uno de estos vive en **dos idiomas**: `docs/en/<archivo>.md` y `docs/es/<archivo>.md`. Más abajo, una referencia simple a `docs/<archivo>.md` significa "ese archivo, en el idioma que estés leyendo" — ambas copias dicen lo mismo, así que la ruta es neutral respecto al idioma por diseño.

**La costura entre las dos mitades es `binding.tm.hcl`.** El resolver escribe globals; los generadores los consumen. Ninguna de las dos conoce las internas de la otra.

---

## Documentación bilingüe

Cada documento bajo `docs/` existe en **inglés** (`docs/en/`) y **español** (`docs/es/`), como copias completas e independientemente legibles — no una sombra traducida automáticamente de una única versión "real". La estructura, encabezados, tablas, bloques de código y numeración de secciones coinciden exactamente entre ambas, así que una referencia de sección (`§9.4`, `AM §5.1`) se resuelve igual en cualquiera de los dos idiomas. Lo que difiere es solo la prosa.

| Tipo de documento | Se escribe primero en | Luego se traduce a |
|---|---|---|
| Documentos de referencia (`docs/en/*.md`, `docs/es/*.md` de nivel superior: `platform-overview.md`, `archetype-model.md`, `terramate-outputs-sharing-architecture.md`, `developer-guide.md`, `risk-register.md`, `glossary.md`) | **Inglés** | Español |
| Propuestas de diseño (`docs/en/proposals/`, `docs/es/proposals/`) | **Español** | Inglés |
| Este archivo, el `README.md` de la raíz, y los pequeños README de `registry/`, `schemas/`, `.github/workflows/` | **Inglés** | Español (un `<nombre>.es.md` hermano, o un único archivo bilingüe donde el contenido sea lo bastante corto — ver los archivos existentes para el patrón) |

Reglas que se derivan de "mantenerse sincronizados", no solo "traducido una vez":

- **Un cambio a un documento de referencia cambia ambas copias en el mismo commit o la misma pull request.** Una PR que edita `docs/en/risk-register.md` sin tocar `docs/es/risk-register.md` está incompleta, no es un seguimiento para después — las dos son un solo documento con dos representaciones, y dejar que diverjan es exactamente el tipo de divergencia silenciosa que las demás puertas de este repositorio (registry vs. schema, generador vs. Gatekeeper) existen para evitar.
- **Los diagramas son parte del documento, no un adjunto.** Una fuente Mermaid o un SVG hecho a mano con etiquetas en un idioma necesita su propia copia renderizada con etiquetas en el otro — nunca una captura de pantalla del diagrama del otro idioma reetiquetada, y nunca el diagrama de un idioma dejado para representar a ambos. `docs/es/proposals/sonarqube-qa/diagrams/20-bloques-presentacion.py` es el patrón para un SVG hecho a mano: el script generador viaja junto con el idioma que renderiza.
- **Los identificadores permanecen en inglés en ambas copias.** Nombres de capability, nombres de trait, IDs de stack, claves de HCL/YAML, valores `kind:`, nombres de environment — cualquier cosa que también sea una cadena literal en algún lugar del registry, un schema, o código generado — no se traduce, en ninguno de los dos idiomas. Solo se traducen la prosa, las descripciones de tabla y los comentarios. Por eso traducir los bloques de código literalmente (no transliterarlos) es correcto, no un descuido.
- **Un documento nuevo no está terminado hasta que existan ambos idiomas.** Añadir solo `docs/en/foo.md` (o solo la propuesta en español) y posponer la otra copia a "un seguimiento" es el modo de fallo que esta sección existe para nombrar y prohibir.

---

## Decisiones asentadas — no reabrir sin una razón

### Herramientas

| Decisión | Justificación |
|---|---|
| **Terramate CLI, no Terraform Stacks** | Stacks es solo de HCP. No está en el CLI OSS, ni en OpenTofu en absoluto |
| **Terramate sobre Terragrunt** | Detección de cambios a escala, ejecución de binario nativo en lugar de un wrapper, el código generado es `.tf` real que Checkov puede escanear sin indirección de plan |
| **OpenTofu, no Terraform** | Decidido desde el inicio |
| **Outputs Sharing** (`sharing_backend`/`input`/`output`) | Aceptado a pesar de ser **experimental**. Riesgo R1. Los contratos se centralizan en `imports/contracts/` para que un cambio disruptivo sea una edición acotada |
| **Gatekeeper, no Kyverno** | El equipo ya escribe Rego para conftest, así que un solo lenguaje de política. Nota: las reglas **no** son literalmente reutilizables entre ambos — solo lenguaje compartido y librerías auxiliares, porque el input de Gatekeeper es un `AdmissionReview`, no `resolution.json` |
| **Gatekeeper autogestionado en las tres nubes** | Los add-ons gestionados son mutuamente excluyentes con él (AKS rechaza el add-on de Azure Policy si Gatekeeper v3 está presente) y restringen las plantillas personalizadas. Una versión, un comportamiento en todas partes |
| **Envoy Gateway** para ingress | Implementación de referencia de Gateway API; OIDC nativo vía `SecurityPolicy` |
| **conftest** para política de CI, no un servidor | Sin estado, sin servidor OPA que ejecutar |

### Arquitectura

| Decisión | Justificación |
|---|---|
| **`from_stack_id` acepta una expresión** | **Esto es una suposición tomada como decisión de diseño.** Todo el modelo de late-binding depende de ello: un archivo de contrato escrito a mano por capability, referenciando `global.platform.cluster_stack_id`. Si resulta ser solo literal, el resolver debe generar un archivo de contrato por instancia — más maquinaria, PRs más ruidosas, pero no un rediseño |
| **Una cuenta/proyecto/suscripción por environment; el hub y la landing zone en la suya propia** | El environment es el límite de aislamiento del modelo dedicado (architecture §12.1), y las lecturas de state entre proyectos ya están diseñadas para esto (§11.5). En GCP la IP de edge, la política de Cloud Armor y el certificado deben compartir proyecto con el load balancer, así que los provee el **environment**, no la landing zone. KMS, el registry de imágenes y la federación de CI permanecen en la landing zone, concedidos entre proyectos. Asentado con `qa` (`disasterproject-qa`) |
| **Cada environment es una VPC/VNet**, un `/17` (o `/16` para producción) de `10.0.0.0/8` | |
| **Environments: `prod`, `qa`, `dev`, `demos`, `ephemeral-*`** | Nomenclatura normalizada. Borradores anteriores usaban `shared-demo`/`pre`/`prd` — esos nombres están muertos |
| **`demos` es un environment compartido** | No efímero por demo. Kafka como bus común argumenta a favor de ello |
| **Los datos NO se comparten en `demos`** | `database-platform` está deliberadamente **no vinculada** ahí. Diez demos obtienen diez instancias gestionadas. Aislamiento, no coste, es el criterio |
| **64 pods por nodo** (valor por defecto de la plataforma) | Asume nodos ≥32 GB. Da un `/25` por nodo, 128 nodos en una mitad `/18` de pods. **Inmutable tras la creación del cluster** |
| **Capa 2b para policy** | El control de admisión debe preceder a todo lo que gobierna, incluyendo los servicios de capa 3. Alcance de cluster, no un servicio nombrado. Precedente: capa 1b para monitorización de nube |
| **Sin mutación de Gatekeeper** | El generador emite labels; Gatekeeper las valida. Un escritor, un validador. La mutación haría los cambios invisibles en los diffs de Terraform y dividiría la propiedad de la lista de labels |
| **El tráfico este-oeste se resuelve por DNS** | Así las direcciones no necesitan ser reproducibles entre reconstrucciones. Lo que SÍ se requiere es **idempotencia**: la clave de asignación es `(pool, owner, purpose)` |
| **Las reglas de firewall las escribe quien reclama el rango** | Preferir selectores de carga de trabajo (network tags, referencias a security groups) sobre CIDR para este-oeste |
| **Kafka es un archetype, no un component** | Despliega un operador e impone un contrato multi-tenant. Bus común, datos separados |
| **Neo4j, MongoDB son components** | Instancias dedicadas sin contrato con nadie más |

### Regla para archetype vs component

> **Archetype** — despliega un operador o servicio compartido que otros consumen, e impone un contrato multi-tenant.
> **Component** — una instancia dedicada dentro del archetype que lo usa, sin contrato con nadie más.

La misma tecnología puede ser ambas cosas. `postgres-operator` (archetype, provee `database-platform`) frente a `component/postgres` (instancia dedicada). Eso no es una inconsistencia.

---

## Todavía abierto — preguntar antes de asumir

1. **¿Es `max_pods_per_node` configurable en Autopilot?** El valor por defecto de 64 asume que sí.
2. **¿VPC compartida o VPCs separadas en GCP?** La no transitividad del peering más la regla del backend en la misma VPC pueden forzar Shared VPC. El plan de direccionamiento no cambia en ningún caso. Riesgo R23.
   **Asentado para `qa`: VPC separada.** `qa` es dedicado, así que su load balancer de edge vive en su propia VPC junto al NEG de Envoy y nada enruta a través del hub; R23 no se presenta. Todavía abierto para `demos` y cualquier environment cuyo edge fuera a residir en el hub. Ver `proposals/sonarqube-qa/README.md` §4.15.
3. **Techo de particiones de Kafka** para el número de brokers previsto. El presupuesto de 4000 en el binding de `demos` es un valor de relleno.
4. **Dónde corre la resolución** — ¿un CLI en el repositorio, o un workflow reutilizable? Determina si la oficina de proyecto puede validar una demo localmente.
5. **Cuánto Rego se comparte genuinamente** entre conftest y los `ConstraintTemplate`s. Medir antes de planear una única base de código de política.
6. **Preguntas abiertas de la guía del desarrollador** — herramienta de scaffolding vs. repositorio plantilla, dónde se calcula el incremento de versión, environments efímeros opt-in o automáticos. Listadas en `developer-guide.md` §13.

---

## Trampas — leer esto antes de escribir código

Estos son los modos de fallo que ya se han identificado. No los redescubras.

**Outputs sharing no crea orden de ejecución.** Cada bloque `input` necesita un `after` correspondiente en `stack.tm.hcl`. Un ordenamiento no resuelto aplica un valor obsoleto **sin ningún error**. Este es el riesgo R2, el riesgo principal, y la política conftest G1 existe específicamente para detectarlo.

**`mock_on_fail` debe ser true en preview y false en deploy.** Bloques `script` nombrados por separado para que no se pueda confundir. Un deployment que cae silenciosamente en un mock aplica un sinsentido.

**Los mocks deben tener el tipo correcto.** Un campo base64 mockeado como `"mock"` rompe `base64decode()`. Un campo lista mockeado como una cadena valida el tipo localmente y explota al aplicar. Prefijar cada mock con `mock-`.

**Nunca compartir secretos a través de outputs sharing.** Los valores aterrizan en variables de entorno `TF_VAR_*`, que se filtran en logs y árboles de procesos. Compartir referencias — un ID de secreto, un ARN, un nombre de clave — y dejar que el consumer lo lea bajo su propia identidad. Los tokens de autenticación se obtienen localmente por cada consumer (`google_client_config`, `aws_eks_cluster_auth`), nunca compartidos.

**El endpoint de GKE no tiene esquema; el de EKS incluye `https://`.** Bug clásico de copiar y pegar entre guías.

**El nombrado determinista rompe ciclos de dependencia.** El ciclo de etiquetado de subredes de EKS (la red necesita el nombre del cluster, el cluster necesita las subredes) se resuelve promoviendo `cluster_name` a un global. Cuando outputs sharing parece necesitar un ciclo, este es el remedio.

**Outputs sharing modela 1-a-N, no N-a-1.** Los bloques `input` no se pueden generar a partir de una lista dinámica. Gateway API elimina el problema del fan-in por completo, por lo que es el diseño objetivo y el remedio de URL-map es solo un fallback.

**Evitar `kubernetes_manifest`** para los custom resources de Gateway API y Gatekeeper. Requiere que el CRD exista y el API server sea alcanzable **en tiempo de plan**, lo cual rompe los previews de PR. Empaquetar los CRs en el propio chart de Helm del archetype y desplegar con `helm_release`.

**El ciclo de arranque Keycloak ↔ Gateway.** El propio `HTTPRoute` de Keycloak **no** lleva `SecurityPolicy`, y el discovery de OIDC del Gateway se resuelve a través del Service dentro del cluster, no del hostname público. Sin ambos, un environment en frío no arranca y la causa no es obvia.

**`failurePolicy: Fail` puede dejarte fuera del cluster** — Gatekeeper rechaza su propia recuperación. `exemptNamespaces` para `kube-system` y el namespace de Gatekeeper, ≥3 réplicas con un PDB, `Ignore` en todas partes excepto producción.

**ECS: nunca compartir el task execution role entre tenants.** Un execution role compartido puede leer los secretos de cada tenant. Por instancia, aunque duplique permisos de ECR y logs.

**El `TargetGroupBinding` de AWS puede referenciar cualquier target group de la cuenta.** En un cluster compartido, un tenant podría redirigir el tráfico de otro. Solo el archetype `gateway` los crea; RBAC deniega el CRD a los namespaces de aplicación.

**Políticas de confianza OIDC: `StringEquals` sobre el `sub` exacto, nunca `StringLike` con un wildcard.** El error de configuración de OIDC más común en AWS. Riesgo R12.

**Los rangos secundarios de pods son inmutables.** Dimensionarlos para muy pocos nodos significa reconstruir el cluster. Riesgo R26.

---

## Estructura del repositorio

```
docs/en/, docs/es/      documentos de referencia, en inglés y español (CLAUDE.md, "Documentación bilingüe")
docs/en/proposals/, docs/es/proposals/   propuestas de diseño para deployments concretos (no normativas)
schemas/                JSON Schema, GENERADO a partir de registry/
registry/               FUENTE DE VERDAD para capabilities, traits, zones, labels
.github/workflows/
```

Planeado, aún no presente:

```
policy/                 Rego para conftest, más *_test.rego
modules/                módulos de OpenTofu
imports/mixins/         generadores de backend y provider por nube
imports/generators/v1/  un generador por capability — "la capa base"
imports/contracts/      contratos de output/input por capability
imports/scripts/        bloques script de terramate
stacks/platforms/       capas 0-3 por nube y environment
stacks/archetypes/      capas 4-5, con instances/
components/             plantillas de stack reutilizables
cmdb-data/              CMDB de nivel 0, un archivo por stack
```

---

## El registry es estructural

`registry/*.yaml` es la **única fuente de verdad** para capabilities, traits, nombres de zone y labels obligatorias. Se generan tres artefactos a partir de él:

| Generado | Consumidor |
|---|---|
| bloques `enum` en `schemas/*.schema.json` | `check-jsonschema` |
| bundle `registry/*.json` | `conftest --data` |
| `values.yaml` del chart de Gatekeeper | parámetros de `ConstraintTemplate` |

**Nunca editar a mano un `enum` en `schemas/`.** Eso es un bug. El modo de fallo de la divergencia es desagradable: una label que el generador dejó de emitir mientras el `Constraint` de admisión todavía la exige bloquea deployments legítimos en la admisión. Riesgo R34.

El generador (`registry-generate`) **todavía no está escrito**. Es la primera tarea de la fase 2c del roadmap.

---

## Convenciones

| Cosa | Patrón | Ejemplo |
|---|---|---|
| ID de stack | `<cloud>-<env>-<capability>[-<instance>]` | `gcp-demos-gke`, `aws-prod-eks` |
| Tags de stack | cloud, env, capability, `platform`\|`archetype:<name>`, `instance:<id>`, `producer`\|`consumer`, `protected` | |
| Archivos generados | `_<propósito>.tf` | `_main.tf`, `_sharing_generated.tf` |
| Generadores | `imports/generators/v<N>/gen_<capability>.tm.hcl` | |
| Contratos | `imports/contracts/contract_<capability>[_<cloud>].tm.hcl` | |
| Mocks | prefijados con `mock-` | `mock-endpoint.example.invalid` |

El código generado **se commitea a git**, prefijado con `_`, y cubierto por `CODEOWNERS`. La puerta `terramate generate --check` (G0) existe por esto: sin ella, alguien edita a mano un `_main.tf`, el escaneo pasa, y el siguiente generate revierte silenciosamente el arreglo.

---

## Por dónde empezar

El roadmap está en `terramate-outputs-sharing-architecture.md` §16. Posición actual: **nada construido todavía; documentación completa**.

**Fase 0 primero.** Construir un repositorio desechable con dos stacks y confirmar, contra una versión fijada de Terramate:

- `from_stack_id` resuelve un global **heredado de un directorio padre**, no solo uno definido en el stack
- `from_stack_id` acepta **interpolación** (`"${global.env}-gke"`), no solo una referencia simple
- `stack.after` acepta una ruta derivada de globals, **o** los filtros de tags funcionan como fallback — esto último **falla silenciosamente**, así que probarlo deliberadamente
- `--mock-on-fail` se comporta como está documentado cuando el producer no tiene state
- Las lecturas de state entre proyectos/cuentas funcionan con los roles OIDC
- Un control plane privado es alcanzable desde el tipo de runner elegido

Esto es el trabajo de una tarde y condiciona todo lo demás.

---

## La guía del desarrollador

Escrita: `developer-guide.md`. Java, Python y Node/React; GitFlow; el scaffolding de `archetypectl new-app` todavía diferido.

Asentado ahí, no reabrir:

| Decisión | Justificación |
|---|---|
| **Monorepo por aplicación** | Una versión, una PR, una ejecución de CI para un cambio que cruza dos servicios |
| **Una versión por aplicación, no por servicio** | De lo contrario "qué corría junto el martes" no tiene respuesta y un rollback no tiene objetivo. La versión es el tag de Git; `metadata.version` es generado y una puerta de CI falla ante una edición a mano |
| **La imagen se promueve entre environments, nunca se reconstruye** | Una reconstrucción es un digest distinto, así que "prod corre lo que qa probó" se vuelve incomprobable. La promoción es un re-etiquetado del lado del registry — 200–500 ms, cero bytes, digest y firmas intactos. Desplegar por digest; el tag es un alias |
| **Cada servicio lleva el tag del release, reconstruido o no** | De lo contrario un release deja servicios sin modificar en un tag antiguo y la aplicación tiene tres versiones a la vez. `release.lock.json` registra servicio → digest |
| **El frontend es nginx en el cluster, no bucket + CDN** | Mismo Gateway, hostname, certificado, `HTTPRoute`, `SecurityPolicy` y observabilidad. Un bucket necesita un segundo camino de edge y un segundo modelo de identidad |
| **Revisión de plataforma para incrementar `capacity` en un environment compartido** | El resolver es lo único que ve el cargo de cada tenant |
| **Las especificaciones de build y deploy extienden `manifest.yaml`** | Un `build.yaml`/`deploy.yaml` paralelo es un tercer lugar donde declarar la misma dependencia, y diverge. Nota `additionalProperties: false` — el schema debe extenderse desde `registry/`, nunca a mano |

**El rollback es la parte que duele, y la guía lo dice en §6.** Solo redesplegar un digest de imagen anterior es barato. Un rollback de Helm vuelve a ejecutar hooks y no puede revertir campos inmutables. Un `tofu apply` de un commit anterior planea `destroy` para todo lo que añadió el commit revertido. Una migración no tiene rollback en absoluto — de ahí expand-contract y las migraciones separadas del deployment. **Revertir un merge no deshace una migración**, y alguien lo intentará.

**La memoria de la JVM tiene números concretos en §8.3, no una nota al pie.** Tres caminos distintos de OOMKill, todos con exit 137 y nada en el log de la aplicación: una JVM anterior a 8u372/11.0.16 en un nodo cgroups v2 leyendo la memoria *del host*; el 25% por defecto sin flag; y `-Xmx` fijado al límite completo sin dejar nada para los 250–400 MiB de non-heap.

**El frontend tiene cuatro detalles, todos encontrados en el primer deployment, dos de los cuales lo bloquean directamente** (§10): `nginxinc/nginx-unprivileged` frente a PSS `restricted` y `readOnlyRootFilesystem`; `env.js` en runtime en lugar de un `VITE_API_URL` en tiempo de build, que produciría una imagen por environment y mataría la promoción; `Cache-Control` asimétrico; y `try_files $uri /index.html`. Los dos últimos se despliegan con éxito y están rotos de todas formas — el peor modo de fallo.

---

## Estilo de trabajo

Los documentos están escritos de forma simple y densa: tablas sobre prosa, números concretos sobre las evasivas, y la justificación de una decisión registrada junto a ella. Mantén eso. Cuando algo es incierto, dilo y di qué lo resolvería — varias secciones terminan con una nota de "verificar en el PoC", y esas son estructurales, no relleno.

Rebate ideas que no van a funcionar. Varias decisiones en este archivo existen porque una propuesta anterior estaba equivocada y fue corregida.
