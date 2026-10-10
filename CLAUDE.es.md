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

Además `platform-overview.md` (mapa guiado por diagramas, léelo primero), `risk-register.md` (73 riesgos por dominio, 70 activos), `glossary.md` (cada término, definido) y `developer-guide.md` (la mitad del desarrollador de aplicaciones — branching, versionado, build, rollback). Cada uno de estos vive en **dos idiomas**: `docs/en/<archivo>.md` y `docs/es/<archivo>.md`. Más abajo, una referencia simple a `docs/<archivo>.md` significa "ese archivo, en el idioma que estés leyendo" — ambas copias dicen lo mismo, así que la ruta es neutral respecto al idioma por diseño.

**Este repositorio es la especificación de diseño normativa, y lo sigue siendo.** No está congelado, y ningún repositorio de despliegue lo sustituye. Un repositorio de despliegue (`disasterproject/infra`, `infra-repo-qa`) implementa lo que aquí se escribe y lleva una copia idéntica byte a byte de `registry/` y `schemas/` fijada a un commit de este (DR4); nunca edita esa copia. Lo que enseña implementar el diseño — un comportamiento medido de una herramienta, una puerta que no se ejecutaba, una restricción de una organización real — vuelve aquí como un cambio de diseño, en los dos idiomas, expresado como un hecho sobre el diseño y no como el informe de dónde se encontró.

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
- **Los nombres de fichero son identificadores, y van en inglés en las dos copias.** Eso incluye los ficheros de diagramas: `docs/es/…/diagrams/02-request-path.mmd` y `docs/en/…/diagrams/02-request-path.mmd`, nunca un nombre en español en el árbol inglés ni al revés. La regla se aplica a todo fichero nuevo; los diagramas nombrados antes conservan su nombre hasta que se renombren juntos, en los dos idiomas, con sus enlaces.
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
| **`prod` en su propia cuenta/proyecto/suscripción; los entornos no productivos comparten uno; el hub y la landing zone en el suyo** | `prod` no comparte nada: su proyecto es su límite de aislamiento (architecture §12.1). Los entornos no productivos (`dev`, `qa`, `demos`, `sandbox`, `ephemeral-*`) comparten un **proyecto non-prod** (`disasterproject-nonprod` en GCP); cuando se alcanzan los límites de un proyecto se añade un segundo proyecto non-prod, nunca uno mixto. Dentro, cada entorno mantiene **su propia VPC**, su propio cluster, sus propias instancias de Cloud SQL y su propio borde (IP, Cloud Armor, certificado, que deben compartir proyecto con su load balancer); todo nombre de recurso lleva el prefijo del entorno, y **la facturación se reparte por etiquetas**. KMS, el registry de imágenes y la federación de CI permanecen en la landing zone, concedidos entre proyectos. El aislamiento entre entornos dentro del proyecto non-prod se apoya en el nombrado, el control de admisión y la revisión, no en el límite del proyecto — aceptado solo para no producción (ver la fila siguiente y el riesgo R54) |
| **Los principales de Workload Identity llevan el prefijo del entorno** | En GKE el pool de Workload Identity es **uno por proyecto** (`PROJECT.svc.id.goog`) y el principal es `ns/<namespace>/sa/<ksa>`, sin el cluster: el mismo namespace y KSA en dos clusters de un mismo proyecto son **la misma identidad de GCP**. Por eso todo KSA que recibe IAM de GCP se llama `<env>-<nombre>` (`qa-eso-sonarqube`, `qa-keycloak-config`, `qa-sonarqube`); los namespaces mantienen su nombre. Gatekeeper rechaza, en cada cluster, un ServiceAccount cuyo nombre empiece por el prefijo de otro entorno (regla P12), y G1 rechaza un `member` de IAM cuyo KSA no lleve el prefijo del entorno dueño del recurso. Un cluster-admin de un entorno no productivo aún puede saltarse la admisión y suplantar a otro: ese riesgo residual es la razón de que `prod` nunca comparta proyecto |
| **Cada environment es una VPC/VNet**, un `/17` (o `/16` para producción) de `10.0.0.0/8` | |
| **Environments: `prod`, `qa`, `dev`, `demos`, `sandbox`, `ephemeral-*`** | Nomenclatura normalizada. Borradores anteriores usaban `shared-demo`/`pre`/`prd` — esos nombres están muertos. Todos salvo `prod` viven en el proyecto non-prod compartido de su jurisdicción. Los nombres son **libres de prefijo** —ningún `<a>-` es prefijo de `<b>-` (`sandbox` y `sandbox-eu` no pueden coexistir)— porque `<env>-` es la frontera de KSA, zonas DNS y recursos en un proyecto compartido (`multi-environment` DX3) |
| **Un entorno es su binding; la región y la jurisdicción son atributos suyos** | Los entornos no son copias: varían composición, proveedores, versiones, tamaño, región y jurisdicción; no varían generadores, contratos, convenciones ni reglas. `environments/<env>/binding.yaml` es el único fichero escrito a mano; los nombres que no son claims se derivan. `metadata.jurisdiction` (el territorio del que no salen los datos) elige la carpeta con su `gcp.resourceLocations`, el proyecto no productivo y el bucket de estado; `metadata.region` es una de sus regiones y sitúa los recursos y el key ring del entorno. Los registros de imágenes son regionales, uno por región de los bindings. Las jurisdicciones se enumeran una vez, en `global.lz.jurisdictions` (`multi-environment` DX1, DX4, DX6) |
| **`demos` es un environment compartido** | No efímero por demo. Kafka como bus común argumenta a favor de ello |
| **Los datos NO se comparten en `demos`** | `database-platform` está enlazada a `postgres-cloudsql`, el proveedor gestionado, así que cada demo obtiene su propia instancia gestionada. Diez demos obtienen diez instancias gestionadas. Aislamiento, no coste, es el criterio. Antes se dejaba sin enlazar con el mismo efecto; el modelo de proveedor global lo convirtió en un binding explícito |
| **Servicios gestionados primero; la estrategia sigue siendo agnóstica** | Donde exista un servicio gestionado equivalente, es el proveedor por defecto; la alternativa basada en operador se mantiene y se soporta, porque unos clientes querrán una y otros la otra. En GCP, el PostgreSQL de producción es Cloud SQL, y `qa` refleja producción |
| **El proveedor de una capability es global por entorno** | Un proveedor por capability y entorno, elegido en el binding (AM §2): la resolución sigue siendo una búsqueda. Sin selección por consumidor: rompe la paridad entre entornos y duplica la operación. Una excepción temporal por instancia para migrar entre proveedores queda descrita, no construida (propuesta `postgres-cloudsql`) |
| **`database-platform` tiene dos proveedores mantenidos** | `postgres-cloudsql` (por defecto, gestionado) y `postgres-operator` (CloudNativePG). Un consumidor lleva los dos caminos, `data` y `data-tenant`, elegidos por el trait del proveedor (`cloudsql` o `cnpg`). En ambos casos cada consumidor tiene su propia instancia: los datos nunca se comparten |
| **64 pods por nodo** (valor por defecto de la plataforma) | Asume nodos ≥32 GB. Da un `/25` por nodo, 128 nodos en una mitad `/18` de pods. **Inmutable tras la creación del cluster** |
| **Dos node pools por cluster: `system` y `apps`** | `system` (con el taint de GKE `components.gke.io/gke-managed-components`) ejecuta las capas 2b y 3 y los componentes de GKE; `apps` (sin taint, con el sysctl `vm.max_map_count`) ejecuta las capas 4 y 5. El generador añade el selector y la tolerancia de `system` a los charts de plataforma; las aplicaciones no ponen nada. Gatekeeper P11 deja tolerar el taint de `system` solo a sus dueños. Un tercer pool (la caché de páginas de Kafka, GPUs) es una excepción respaldada por datos, no el punto de partida; el único documentado es `gvisor` (GKE Sandbox, 0–1 nodos) para código de terceros que necesita privilegios, el agente de A.I.G (`appsec-qa` DA8, Gatekeeper P13). Sustituye a los pools por arquetipo (`sonar`, `kafka`) de revisiones anteriores (`gke-qa` §5, DN11) |
| **Capa 2b para policy** | El control de admisión debe preceder a todo lo que gobierna, incluyendo los servicios de capa 3. Alcance de cluster, no un servicio nombrado. Precedente: capa 1b para monitorización de nube |
| **Sin mutación de Gatekeeper** | El generador emite labels; Gatekeeper las valida. Un escritor, un validador. La mutación haría los cambios invisibles en los diffs de Terraform y dividiría la propiedad de la lista de labels |
| **El tráfico este-oeste se resuelve por DNS** | Así las direcciones no necesitan ser reproducibles entre reconstrucciones. Lo que SÍ se requiere es **idempotencia**: la clave de asignación es `(pool, owner, purpose)` |
| **Las reglas de firewall las escribe quien reclama el rango** | Preferir selectores de carga de trabajo (network tags, referencias a security groups) sobre CIDR para este-oeste |
| **Un runtime crea sus propias subredes** | Las subredes de nodos, los rangos de pods y las subredes del plano de control son claims del runtime (AM §9.5), así que las crea su arquetipo en un primer stack `*-subnets`. `network` publica la VPC/VNet, la salida y el enrutamiento, y no conoce ningún runtime. Dueño del claim = creador = autor del firewall; reconstruir un cluster nunca toca la red; el ciclo de etiquetado de subredes de EKS no puede aparecer. Aplicado a las cinco guías de runtime: GKE, EKS, Cloud Run, ECS Fargate y AKS (arquitectura §5.2, §6.2, §7.2, §8.2, §9.2); en los runtimes serverless el claim es la subred de egress o las subredes de tareas, localizadas mediante `global.platform.runtime_subnet_stack_id` |
| **La CMDB tiene dos mitades, separadas por quién las escribe** | La mitad **declarada** (stacks, aristas, claims) la genera `archetypectl cmdb` en la pull request, se comprueba como G0 y vive en `main`, así que el revisor ve una arista o un claim nuevo en el diff. La mitad **observada** (`lastApply`, `resourceCount`, salidas no sensibles, drift) la escribe tras el apply el workflow reutilizable `cmdb-sync` en la rama `cmdb-observed` — nunca en `main`, que necesitaría un bypass de su protección y volvería a disparar `deploy` (R55). El modelo de lectura es un asset de release privado (`cmdb-latest`): unas Pages públicas publicarían el mapa del entorno. La guarda de destroy cuenta **aristas** de la CMDB, nunca nombres de stack (AM §11, arquitectura §12.4, §14.2; propuesta `cmdb-qa`) |
| **El borde solo depende hacia abajo; el tramo balanceador → Envoy es HTTP** | El TLS público termina en el balanceador con el certificado de la capa 1 (Certificate Manager, validado por DNS authorization en la zona delegada del propio entorno). Un certificado de `cert-manager` (capa 3) para el tramo hacia el backend era una dependencia hacia arriba que el balanceador ni siquiera validaba. El nombre del NEG sigue siendo la única arista hacia arriba (AM §3). Si algún día hay que autenticar el tramo, la raíz es una CA de plataforma en la capa 1, nunca la CA interna (arquitectura §10.2; `edge-qa` DL9, `envoy-gateway-qa` DG14) |
| **Los nombres públicos nunca llevan el nombre del entorno** | Todo lo visible sin credenciales —zona pública y hostnames, el wildcard que queda en los logs de Certificate Transparency, los nombres de bucket, que son globales, el nombre del realm de Keycloak en las URLs de OIDC/SAML— usa el `network.public_id` del entorno: 7 letras minúsculas aleatorias de la landing zone, nunca un hash del nombre. Como **subdominio** (`sonar.<public_id>.disasterproject.com`), no con guion: el wildcard sigue siendo por entorno, la zona delegada sigue siendo del entorno y las cookies no cruzan entornos. Los nombres internos (etiquetas, prefijos de KSA, IDs de stack, namespaces, `qa.internal`) conservan el nombre del entorno: ocultarlos no protege nada y rompe la facturación y la operación. Se comprueba en G1 sobre cada binding y en G3 sobre el plan, con una sola lista de palabras (arquitectura §13.3–§13.4); el realm, con un `assert` en `keycloak` (AM §7; `edge-qa` DL10) |
| **El pipeline llega a GKE por el endpoint DNS del plano de control** | Solo IAM (`container.clusters.connect` por cluster, después RBAC); el endpoint IP público, desactivado. El procedimiento anterior —abrir la IP del runner en las redes autorizadas mediante un intermediario en Cloud Run— era inalcanzable con la org policy `run.allowedIngress` y dependía de cuatro condiciones frágiles; R38 y R39 se retiran. Sin la barrera de red, los accesos de principales fuera de la lista se alertan en la capa 1b (`landing-zone-qa` DZ4, `gke-qa` §2.2). Donde una organización prohíbe cualquier endpoint de Kubernetes alcanzable desde internet, la **variante** documentada es un `/32` por job con cuatro controles obligatorios y el riesgo R64 — una variante, nunca el diseño por defecto (`landing-zone-qa` §3.2, DZ16) |
| **La landing zone es dueña de los singletons del proyecto y de las identidades entre proyectos** | Un recurso que existe una vez por proyecto (la política de Binary Authorization) lo escribe solo la landing zone, una regla por cluster, `ALWAYS_DENY` por defecto: si no, el `apply` de cada entorno borra las reglas de los demás (R59). Las SAs que reciben grants entre proyectos (la SA de nodos de un runtime) las crea la landing zone, para que la capa 0 nunca espere a la capa 2 (R60). Las identidades del pipeline viven en el proyecto de la landing zone, con acceso al estado por prefijo (arquitectura §11.2; `landing-zone-qa` DZ5, DZ6) |
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
   **Asentado para `qa`: VPC separada.** `qa` tiene su propia VPC dentro del proyecto non-prod compartido, así que su load balancer de edge vive en su propia VPC junto al NEG de Envoy y nada enruta a través del hub; R23 no se presenta. Todavía abierto para `demos` y cualquier environment cuyo edge fuera a residir en el hub. Ver `proposals/sonarqube-qa/README.md` §4.15.
3. **Techo de particiones de Kafka** para el número de brokers previsto. El presupuesto de 4000 en el binding de `demos` es un valor de relleno.
4. **Dónde corre la resolución** — ¿un CLI en el repositorio, o un workflow reutilizable? Determina si la oficina de proyecto puede validar una demo localmente. *Propuesto* en `infra-repo-qa` DR3: un CLI de un repositorio aparte, `platform-tools`, fijado con `mise` y ejecutado por `ci/g1.sh` igual en local que en CI.
5. **Cuánto Rego se comparte genuinamente** entre conftest y los `ConstraintTemplate`s. Medir antes de planear una única base de código de política.
6. **Preguntas abiertas de la guía del desarrollador** — herramienta de scaffolding vs. repositorio plantilla, dónde se calcula el incremento de versión, environments efímeros opt-in o automáticos. Listadas en `developer-guide.md` §13.

---

## Trampas — leer esto antes de escribir código

Estos son los modos de fallo que ya se han identificado. No los redescubras.

**Outputs sharing no crea orden de ejecución.** Cada bloque `input` necesita un `after` correspondiente en `stack.tm.hcl`. Un ordenamiento no resuelto aplica un valor obsoleto **sin ningún error**. Este es el riesgo R2, el riesgo principal, y la política conftest G1 existe específicamente para detectarlo. La regla exige al **productor mismo** en `after`: ejecutarse después de un stack que va después del productor es correcto hoy y falla G1 a propósito, porque solo se sostiene hasta que alguien reordena el stack intermedio (arquitectura §13.3).

**Los globals no se resuelven en `stack.after` — es un error de análisis, no uno silencioso** (medido, Terramate 0.16.0 y 0.17.3, `poc/RESULTS.es.md`). El resolver debe escribir valores literales; preferir `after = ["tag:<capability>"]` a una ruta para que un stack pueda moverse. El fallo silencioso que queda es un `after` *olvidado*: un consumidor con un `input` y sin orden se genera limpiamente y puede programarse antes que su productor, sin error en ninguna fase. Eso es R2, y G1 es lo que lo detecta.

**Los tags de Terramate no pueden contener `:`** (medido, 0.16.0 y 0.17.3: solo minúsculas, dígitos, `.`, `_`, `-`, `/`). En un filtro, `:` significa AND y `,` significa OR, y dos opciones `--tags` son OR. Por eso los tags de instancia y de arquetipo son `instance/<id>` y `archetype/<name>`, y `--tags gcp:qa:network` selecciona los stacks que llevan los tres tags. Un tag escrito `instance:alpha` hace fallar la carga entera de la configuración.

**`terramate list` no tiene `--json`** (0.16.0, 0.17.3): imprime rutas. Y `terramate experimental eval` expone `terramate.stack.id`, `tags` y `path` pero **no `after`** (medido, 0.17.3) — un inventario construido sobre él no puede alimentar la regla de R2. El inventario sale de `terramate debug show metadata`, que sí lleva `after`, leído por `ci/stacks-json.sh`; se niega a devolver un array vacío (arquitectura §14.4, `poc/RESULTS.es.md` A8).

**Los bloques `script` siguen siendo experimentales en 0.17.3.** `experiments = ["outputs-sharing", "scripts"]`: sin `"scripts"`, un solo bloque `script` hace fallar la carga de **toda** la configuración, y cualquier comando `terramate` sale con 1 (`poc/RESULTS.es.md` A8a).

**`output.value` se copia literalmente al código generado.** Terramate no interpola ahí ni `global.*` ni `"${global.x}"`: `value = global.project_id` llega al `.tf` como una referencia inválida, igual que un `var.*` que ningún `input` declara. Un contrato publica `module.*`, `resource.*`, `data.*` o un `local` que emite el generador (arquitectura §4.3, `poc/RESULTS.es.md` A8d).

**La opción de G0 es `terramate generate --detailed-exit-code`** (0 = al día, 2 = deriva, 1 = error). `--check` no existe en Terramate y falla con `unknown flag`. Un mock de tipo incorrecto no cambia ningún fichero generado, así que G0 no puede detectarlo; G1 comprueba la forma del mock contra el contrato.

**`mock_on_fail` debe ser true en preview y false en deploy.** Bloques `script` nombrados por separado para que no se pueda confundir. Un deployment que cae silenciosamente en un mock aplica un sinsentido.

**Los mocks deben tener el tipo correcto.** Un campo base64 mockeado como `"mock"` rompe `base64decode()`. Un campo lista mockeado como una cadena valida el tipo localmente y explota al aplicar. Prefijar cada mock con `mock-`, o, donde el proveedor fija el formato, llevar `mock` dentro (`vpc-mock…`, `projects/mock-project/…`) — y un mock base64 también se decodifica a un valor `mock-` (`bW9jay1jYQ==`, `mock-ca`), para que una CA mockeada que llegue a un log de deploy sea reconocible. La regla G1 `terramate.mocks` comprueba las tres formas (arquitectura §13.3).

**`--mock-on-fail` cubre bloques `input`, nunca fuentes `data`.** Una fuente `data` que lee algo que crea otro stack hace fallar la preview siempre que ese algo aún no exista, y ningún flag la salva. Referenciar por un nombre o una URL deterministas — el NEG se referencia por su URL, construida a partir de `neg_name` (arquitectura §10.2). Un `after` sin `input` detrás no lo comprueba nadie, así que la única arista así, la ascendente, tiene una regla G1 con nombre (§13.3).

**Una puerta que no puede ejecutarse es peor que una ausente, porque informa de éxito.** Medido: `conftest test` sin `--all-namespaces` solo evalúa `package main` y pasa con `0 tests`; `--data registry/` deja `data.registry` vacío, así que un rasgo desconocido pasa; `--namespace terraform` no coincide con ningún `package terraform.public_names`; un bucle con `shopt -s nullglob` sobre un glob que no encuentra nada no valida nada y sale con 0. Toda puerta demuestra que evaluó algo: G1 y G3 fallan con cero reglas, `stacks-json.sh` con cero stacks, `validate.yml` con un directorio existente que no contiene ningún fichero (arquitectura §14.4, `poc/RESULTS.es.md` A8). Lo mismo vale para un paso del que depende una puerta: un marcador de deploy atado al job entero nunca avanza mientras el observador que sigue al apply esté roto, así que se ata al paso de apply.

**En un proyecto compartido, el plan dice `create` y la API responde `409`.** Un recurso que ya existe con nuestro nombre no está en nuestro estado, así que nada antes del apply lo ve, y el apply se detiene treinta recursos después. Una comprobación previa revisa cada nombre antes; los nombres llevan el repositorio o el entorno (`gh-disasterproject-infra`); un recurso que no creamos nunca se importa (`landing-zone-qa` §1.3, R62).

**Una identidad de plan es alcanzable desde cualquier PR, así que nunca tiene `roles/viewer`.** `tf-plan-<env>@` recibe una lista de lectura enumerada, nunca el contenido de un secreto y nunca un descifrador más allá de su propia clave de estado; `roles/viewer` lee la configuración de todos los servicios en nombre de código que nadie ha revisado aún (`landing-zone-qa` DZ14). La condición del estado lleva una mitad de listado (`objectListPrefix` empieza por `<env>/`), o el primer plan no puede listar su propio prefijo.

**La identidad que concede roles está acotada por rol.** Solo la identidad de apply de la landing zone administra el IAM de proyecto, mediante `modifiedGrantsByRole.hasOnly([...])` generado de la misma lista `global.identities` de la que concede — nunca un `folderAdmin` o `projectIamAdmin` sin cota, que es un camino de escalada (DZ13, R63). Las coordenadas de la federación se commitean en `ci/federation.env`, no son variables de repositorio; G1 falla con `vars.GCP_*` (DZ12).

**El fallback en claro del bootstrap vive solo en `TF_ENCRYPTION`, y `enforced = true` llega después de la migración** (medido, OpenTofu 1.10.6, `poc/RESULTS.es.md` A9). `enforced = true` prohíbe incluso un fallback inyectado y el entorno no puede relajarlo, así que commitearlo en el paso 1 hace imposible la migración; commitear un fallback en el código deja abierto un camino en claro hasta que alguien lo quite.

**Nunca compartir secretos a través de outputs sharing.** Los valores aterrizan en variables de entorno `TF_VAR_*`, que se filtran en logs y árboles de procesos. Compartir referencias — un ID de secreto, un ARN, un nombre de clave — y dejar que el consumer lo lea bajo su propia identidad. Los tokens de autenticación se obtienen localmente por cada consumer (`google_client_config`, `aws_eks_cluster_auth`), nunca compartidos.

**El endpoint de GKE no tiene esquema; el de EKS incluye `https://`.** Bug clásico de copiar y pegar entre guías.

**Nunca extraigas el entorno del id de un stack, y nunca compares un prefijo sin su separador.** `<cloud>-<env>-<capability>` es ambiguo en cuanto un nombre lleva `-`: `split(id, "-")[1]` convertía `gcp-sandbox-eu-edge` en `sandbox` y la regla de la arista ascendente fallaba con dos entornos correctos (medido, conftest 0.70.1). Lee el entorno de `global.env` o de un tag; empareja stacks por lo que precede a su sufijo. `europe-west1` es prefijo de `europe-west10`, `sandbox` de `sandbox-eu`: compara `<region>-`, `<env>-` (`multi-environment` DX3, R67).

**Un entorno se emite, nunca se copia, y ninguna lista de entornos se mantiene a mano.** Copiar los `stack.tm.hcl` de otro entorno y reescribir `qa` por el nombre nuevo falla por exceso y por defecto (`qa.internal`, prefijos dentro de valores) y diverge con cada cambio posterior; el resolver emite el árbol desde binding y manifiestos. Las entradas de los workflows son texto validado contra `environments/`, los recuentos se derivan, y las palabras de nombres públicos incluyen el nombre de cada binding — con una lista de palabras a mano, un nombre público con el nombre de otro entorno pasaba G1 y G3. La clave del estado de cada stack es `<env>/<stack id>`, nunca su ruta, así que mover un directorio no es mover estado (`multi-environment` DX1, DX8, R70).

**GitHub crea al vuelo, sin protección, un Environment que no existe.** Un job que nombra un Environment inexistente obtiene uno sin revisores ni política de ramas, y su token lleva `environment: <env>`. Una identidad ligada solo a `attribute.environment/<env>` es entonces suplantable desde cualquier rama en la ventana entre federarla y que un administrador cree el Environment. Las identidades de apply y destroy se ligan a `attribute.env_ref/<env>@refs/heads/main`; los Environments se crean antes de fusionar el binding; un workflow manual valida el entorno en un job sin `environment:` y nunca lo interpola en un script (`multi-environment` DX9, R71).

**Los key rings y las claves de KMS no se borran nunca.** Su ubicación se decide antes del primer `apply`: el ring de un entorno sigue a la región de su cluster (`gke-secrets` debe estar en la ubicación del cluster), y un ring creado en la región equivocada se queda allí para siempre (`multi-environment` DX4).

**Ningún default de chart o módulo es el valor de un entorno real.** Un default `envoy-qa` funciona en `qa` aunque falte el override, y el segundo entorno crea en silencio un `envoy-qa`. Los defaults son neutros (`envoy`, `gateway`) o no existen; el generador pasa siempre el valor derivado (`multi-environment` DX2, R69).

**El nombrado determinista rompe ciclos de dependencia.** El ciclo de etiquetado de subredes de EKS (la red necesita el nombre del cluster, el cluster necesita las subredes) aparecía mientras la red era dueña de las subredes del cluster; con el runtime como dueño no puede aparecer, y `cluster_name` sigue siendo un global para que los stacks del runtime coincidan en él. Cuando outputs sharing parece necesitar un ciclo, un global determinista sigue siendo el remedio.

**Outputs sharing modela 1-a-N, no N-a-1.** Los bloques `input` no se pueden generar a partir de una lista dinámica. Gateway API elimina el problema del fan-in por completo, por lo que es el diseño objetivo y el remedio de URL-map es solo un fallback.

**Evitar `kubernetes_manifest`** para los custom resources de Gateway API y Gatekeeper. Requiere que el CRD exista y el API server sea alcanzable **en tiempo de plan**, lo cual rompe los previews de PR. Empaquetar los CRs en el propio chart de Helm del archetype y desplegar con `helm_release`.

**`helm_release` renderiza el chart en el apply, así que una subida de chart revisada como una línea es un manifiesto que nadie vio.** Revisa `_rendered/`, nunca el número de versión: `ci/hydrate.sh` escribe el `helm template` de cada release junto a su stack, G0 falla si está obsoleto, `gator` lo evalúa en G1, y el despliegue compara `helm get manifest` con él tras el apply. Tres detalles medidos (Helm 3.19.0): `--skip-crds` no quita las CRDs que un chart renderiza desde `templates/` — se separan por `kind`; las CRDs son ~97 % de un renderizado — se guarda un digest; los hooks están en `helm template` pero no en `helm get manifest` — se guardan aparte. Un valor de chart que viene de outputs sharing se renderiza como `late:<input>`, nunca un mock; un `Secret` con valor en un renderizado lo hace fallar (`source-hydration` DH2–DH7, R72, R73).

**El ciclo de arranque Keycloak ↔ Gateway.** El propio `HTTPRoute` de Keycloak **no** lleva `SecurityPolicy`, y el discovery de OIDC del Gateway se resuelve a través del Service dentro del cluster, no del hostname público. Sin ambos, un environment en frío no arranca y la causa no es obvia.

**El egress de la VPC se deniega por defecto, y el propio rango del entorno también es egress.** Sin un permiso para el `/17`, nada falla en el apply: el cluster se crea, y el primer webhook de admisión expira — con `failurePolicy: Fail`, el bloqueo de abajo. Los permisos son 443, el `/17` y el VIP privado; un plano de control con peering fuera del `/17` necesita 443 y 8132 (konnectivity), que escribe GKE; cualquier otro puerto es una entrada de `egress_extra` del arquetipo que lo necesita (`network-qa` DW6, R66).

**En el proyecto compartido, IAM no mantiene un recurso de red en su propia VPC.** `compute.networkAdmin` alcanza todas las VPC, y una zona privada enlazada a la VPC de otro entorno responde sus APIs de Google. Lo hace la regla G3 `terraform.own_network`; `dns.admin` sobre el proyecto va siempre condicionado al prefijo de zona, porque las zonas públicas también viven ahí (`network-qa` DW8, R65).

**`failurePolicy: Fail` puede dejarte fuera del cluster** — Gatekeeper rechaza su propia recuperación. `exemptNamespaces` para `kube-system` y el namespace de Gatekeeper, ≥3 réplicas con un PDB, `Ignore` en todas partes excepto producción.

**ECS: nunca compartir el task execution role entre tenants.** Un execution role compartido puede leer los secretos de cada tenant. Por instancia, aunque duplique permisos de ECR y logs.

**El `TargetGroupBinding` de AWS puede referenciar cualquier target group de la cuenta.** En un cluster compartido, un tenant podría redirigir el tráfico de otro. Solo el archetype `gateway` los crea; RBAC deniega el CRD a los namespaces de aplicación.

**Políticas de confianza OIDC: `StringEquals` sobre el `sub` exacto, nunca `StringLike` con un wildcard.** El error de configuración de OIDC más común en AWS. Riesgo R12.

**Los rangos secundarios de pods son inmutables.** Dimensionarlos para muy pocos nodos significa reconstruir el cluster. Riesgo R26.
**Un pool de Workload Identity por proyecto de GCP.** Dos clusters del proyecto non-prod compartido que ejecuten `sonarqube/eso-sonarqube` obtienen la misma identidad de GCP, y cada uno puede leer los secretos del otro. Pon el prefijo del entorno a todo KSA con IAM de GCP (`qa-eso-sonarqube`), y constrúyelo solo a partir de `global.ksa_prefix` — G1 rechaza un nombre de KSA literal en un generador; prefijar el namespace del controlador de ESO no aísla nada, porque el controlador no tiene identidad de GCP y lee con el KSA de cada consumidor.

---

## Estructura del repositorio

```
docs/en/, docs/es/      documentos de referencia, en inglés y español (CLAUDE.md, "Documentación bilingüe")
docs/en/proposals/, docs/es/proposals/   propuestas de diseño para deployments concretos (no normativas)
schemas/                JSON Schema, GENERADO a partir de registry/
registry/               FUENTE DE VERDAD para capabilities, traits, zones, labels
talks/                  presentaciones HTML de una hora, solo en inglés; no son especificación (talks/README.md)
.github/workflows/
```

Planeado, aún no presente — pertenece al repositorio de despliegue `disasterproject/infra`, no a este (estructura, ramas y plantillas de workflows en `proposals/infra-repo-qa/`; **no hay rama por entorno**, DR2):

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
cmdb-data/              CMDB de nivel 0, mitad declarada, un archivo por stack (mitad observada: rama cmdb-observed)
```

---

## El registry es estructural

`registry/*.yaml` es la **única fuente de verdad** para capabilities, traits, nombres de zone y labels obligatorias, y se escribe **aquí**: un repositorio de despliegue lleva una copia idéntica byte a byte de `registry/` y `schemas/` fijada en `spec.lock.json`, comprobada en los dos sentidos por `ci/spec-sync.sh`, y nunca la edita (`infra-repo-qa` DR4). Se generan tres artefactos a partir de él:

| Generado | Consumidor |
|---|---|
| bloques `enum` en `schemas/*.schema.json` | `check-jsonschema` |
| bundle `registry/registry.json` (clave de primer nivel `registry`) | `conftest --data` |
| `values.yaml` del chart de Gatekeeper | parámetros de `ConstraintTemplate` |

**Nunca editar a mano un `enum` en `schemas/`.** Eso es un bug. El modo de fallo de la divergencia es desagradable: una label que el generador dejó de emitir mientras el `Constraint` de admisión todavía la exige bloquea deployments legítimos en la admisión. Riesgo R34.

El generador (`registry-generate`) **todavía no está escrito**. Es la primera tarea de la fase 2c del roadmap. Hasta que exista, `.github/scripts/check-registry-enums.py` — bloqueante en `validate.yml` — compara capacidades, traits y zonas asignables con los enums de los schemas: un aviso en su lugar sería una puerta que no puede ejecutarse.

---

## Convenciones

| Cosa | Patrón | Ejemplo |
|---|---|---|
| ID de stack | `<cloud>-<env>-<capability>[-<instance>]` | `gcp-demos-gke`, `aws-prod-eks` |
| Nombres públicos | `<app>.<public_id>.<dominio>`; buckets `disasterproject-<public_id>-<propósito>` | `sonar.tqbvzkr.disasterproject.com` (`public_id` es un ejemplo) |
| Tags de stack | cloud, env, capability, `platform`\|`archetype/<name>`, `instance/<id>`, `producer`\|`consumer`, `protected` | |
| Archivos generados | `_<propósito>.tf` | `_main.tf`, `_sharing_generated.tf` |
| Charts renderizados | `_releases.json`, `_values-<release>.yaml` (generados); `_rendered/<release>.yaml`, `.hooks.yaml`, `.crds.sha256` (`ci/hydrate.sh`) | `_rendered/cert-manager.yaml` |
| Generadores | `imports/generators/v<N>/gen_<capability>.tm.hcl` | |
| Contratos | `imports/contracts/contract_<capability>[_<stack>][_<cloud>].tm.hcl` — `<stack>` para un stack interno de un arquetipo de varios stacks | `contract_run_subnet_gcp.tm.hcl` |
| Mocks | prefijados con `mock-` | `mock-endpoint.example.invalid` |

El código generado **se commitea a git**, prefijado con `_`, y cubierto por `CODEOWNERS`. La puerta `terramate generate --detailed-exit-code` (G0) existe por esto: sin ella, alguien edita a mano un `_main.tf`, el escaneo pasa, y el siguiente generate revierte silenciosamente el arreglo. G0 vuelve además a ejecutar `ci/hydrate.sh` y falla ante cualquier cambio bajo `_rendered/`.

---

## Por dónde empezar

El roadmap está en `terramate-outputs-sharing-architecture.md` §16. Posición actual: **PoC local de la fase 0 hecha (`poc/`); nada desplegado; documentación completa**. Este repositorio contiene solo documentación y propuestas; el repositorio de despliegue que describe se organiza en `docs/es/proposals/infra-repo-qa/`.

**Resultados de la fase 0** (Terramate 0.16.0, OpenTofu 1.10.6, medido el 2026-09-16; repetido el 2026-09-28 con 0.16.0 y con 0.17.3, la versión fijada, con salida idéntica — `poc/RESULTS.es.md`):

| Suposición | Resultado |
|---|---|
| `from_stack_id` resuelve un global **heredado de un directorio padre** | Confirmada |
| `from_stack_id` acepta **interpolación** (`"${global.env}-gke"`) | Confirmada |
| `stack.after` acepta una ruta derivada de globals | **Refutada, ruidosamente** — error de análisis. Los filtros por tag y las rutas literales funcionan; el resolver escribe literales |
| `--mock-on-fail` se comporta como está documentado cuando el producer no tiene state | Confirmada; no enmascara un stack productor inexistente |
| Las lecturas de state entre proyectos funcionan con los roles OIDC | No probada — primer despliegue de `qa`, `landing-zone-qa` VZ1–VZ3 |
| El control plane es alcanzable desde el runner | No probada — ahora el endpoint DNS solo con IAM, `landing-zone-qa` VZ5 |
| El estado en claro del bootstrap migra con el fallback solo en `TF_ENCRYPTION` (2026-10-04, OpenTofu 1.10.6) | **Confirmada**; `enforced = true` no puede commitearse hasta después de la migración (`poc/RESULTS.es.md` A9) |
| Las herramientas de las puertas evalúan lo que dicen (2026-10-04, 0.17.3, conftest 0.70.1) | **Refutada** tal como estaba escrito — experimento `scripts` obligatorio, sin `after` en `experimental eval`, `output.value` literal, namespaces y datos de conftest. Corregido en la arquitectura y las plantillas (`poc/RESULTS.es.md` A8) |

Dos hallazgos laterales: un proyecto Terramate es **un repositorio git con una configuración raíz** (no puede anidarse en otro), y `output.description` no se emite en el bloque generado.

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
