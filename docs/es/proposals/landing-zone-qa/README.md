# Landing zone para `qa` — arquetipo `landing-zone-gcp` (capa 0)

| | |
|---|---|
| **Estado** | Propuesta · revisión 1 |
| **Alcance** | Lo que la capa 0 tiene que dar para que `qa` arranque: arranque de la propia landing zone, proyectos y carpetas, org policies, APIs del proyecto non-prod, claves de Cloud KMS, Artifact Registry, federación de GitHub Actions e identidades del pipeline, bucket de estado, DNS padre y zona delegada, identificador público, pool global de direcciones, Binary Authorization, presupuestos. `hub` y `prod` solo donde cambian algo |
| **Por qué ahora** | Todas las propuestas de `qa` le dejan requisitos (§0.1) y ninguna la describe. Es lo primero que se aplica y lo único que se arranca a mano |
| **Base** | E1 §4.13 (acceso al plano de control), §4.14 (KMS), §4.15 (VPC separada); arquitectura §11.2 (identidad del pipeline), §11.4 (segregación), §11.5 (estado); AM §3 (capas), §7 (binding), §9.2 (pool global). No se repite lo que ya está allí |
| **Especificación de referencia** | `archetype-model.md` (AM §n), `terramate-outputs-sharing-architecture.md` (§n), `risk-register.md` |
| **Diagramas** | `diagrams/*.mmd` (fuente Mermaid) y `diagrams/*.svg` (renderizados). El SVG se regenera desde el `.mmd`; no se edita a mano. `diagrams/06-bloques-presentacion.svg` (1920×1080, para presentaciones) se genera con `06-bloques-presentacion.py`, no con Mermaid |
| **Identificadores propios** | Decisiones `DZ1…`, riesgos candidatos `RZ1…`, verificaciones `VZ1…`. Los riesgos reciben número `R58+` en `risk-register.md` si se adoptan |

No reabre ninguna decisión de `CLAUDE.md`. Reúne lo que las propuestas anteriores dejaron "a la landing zone" y encuentra tres problemas que ninguna podía ver por separado:

1. **Binary Authorization es una política por proyecto** (§8). Si cada stack `gke` escribe su regla, el último `apply` borra las de los demás entornos no productivos: un fan-in N→1 (`CLAUDE.md`, trampa de outputs sharing) en forma de recurso único.
2. **Grants entre proyectos sobre identidades que aún no existen** (§6.3). La landing zone concede `artifactregistry.reader` a la SA de nodos de `qa` y `cryptoKeyEncrypterDecrypter` al agente de GKE; si esas identidades las crea la capa 2, la capa 0 tiene que esperar a la 2 para aplicar: una arista hacia arriba.
3. **La org policy `run.allowedIngress` choca con el servicio `access` de GKE** (§3.2). E1 §4.13 lo expone a los runners de GitHub por internet; la política que protege R14 lo deja inalcanzable.

![Landing zone en bloques](diagrams/06-bloques-presentacion.svg)

Fuente: [`diagrams/06-bloques-presentacion.py`](diagrams/06-bloques-presentacion.py) — vista de presentación; el detalle está en §1–§10.

---

## 0. Contexto

| Pregunta | Respuesta | Consecuencia |
|---|---|---|
| Qué es | Arquetipo `landing-zone-gcp`, `kind: catalog`, **capa 0**, instancia `disasterproject-gcp-lz` (el valor de `platform.landing_zone` en el binding de `qa`). Singleton por organización | Stacks `gcp-lz-*`; los aplica solo su propia identidad (§5.2) |
| Provee | `cidr-pool` (el `/8` y el ledger global, AM §9.2), `dns-zone` (la zona padre) y `hub` (fuera de alcance: `qa` no hace peering, E1 §4.15). `cert`, `waf` y `edge-ip` son de la capa 1 (AM §3) | Lo demás que da —claves, registro, federación, bucket de estado, identidades, proyectos— son **globals deterministas**, no capabilities: un solo proveedor posible, nombres conocidos sin leer estado (E1 §4.14) |
| Proyectos | `disasterproject-lz` (la propia landing zone), `disasterproject-nonprod` (`dev`, `qa`, `demos`, `sandbox`, `ephemeral-*`), `disasterproject-prod` | Los crea la landing zone; los entornos solo crean recursos dentro (`CLAUDE.md`) |
| Qué **no** hace | Nada dentro de la VPC de un entorno; ningún recurso con el nombre de un entorno fuera de lo que la capa 1 necesita para arrancar (claves, zona, identidades) | La capa 1 conserva su propiedad (`network-qa`, `edge-qa`) |

![Contexto](diagrams/01-contexto.svg)

Fuente: [`diagrams/01-contexto.mmd`](diagrams/01-contexto.mmd)

### 0.1 Lo que le pidieron las propuestas anteriores

| Origen | Requisito | Dónde se cumple |
|---|---|---|
| E1 §4.14 | Key ring `qa` con `tofu-state`, `gke-secrets`, `cosign`; protección frente a destrucción | §4 |
| `network-qa` §1, §2, §5, §9.2 | Proyecto non-prod con APIs habilitadas; `compute.skipDefaultNetworkCreation`; `compute.restrictVpcPeering` que admita `servicenetworking` | §2, §3 |
| `edge-qa` §1, DL2, DL10 | Zona pública del entorno creada aquí, delegada con `DS` y DNSSEC, `dns.admin` al entorno sobre esa zona; identificador público aleatorio | §7 |
| `gke-qa` §3 | `gke-secrets` para el agente de GKE del proyecto; `artifactregistry.reader` sobre el repositorio para la SA de nodos; Binary Authorization por cluster | §4, §6.3, §8 |
| Gatekeeper P2, `postgres-operator-qa`, variante Cloud SQL | Artifact Registry único, imágenes por digest, copia de imágenes de terceros (CNPG, Cloud SQL Auth Proxy) | §6 |
| Arquitectura §11.2, §11.4 | Federación de GitHub Actions; `tf-plan-qa@`, `tf-apply-qa@`, `tf-destroy-qa@` | §5 |
| `cmdb-qa` §7 | `cmdb-reader@` con `cloudasset.viewer` en el proyecto non-prod | §5.1 |
| `CLAUDE.md` | Facturación por etiquetas en el proyecto compartido | §9 |

---

## 1. Arranque de la propia landing zone

La landing zone es lo único que no puede desplegar el pipeline, porque crea el pipeline: su bucket de estado, su clave de estado y la federación con la que GitHub se autentica. Se arranca **una vez**, a mano, y después se gestiona como cualquier otro stack.

![Arranque](diagrams/02-arranque.svg)

Fuente: [`diagrams/02-arranque.mmd`](diagrams/02-arranque.mmd)

| Paso | Quién | Qué | Estado |
|---|---|---|---|
| 1 | Persona con `organizationAdmin` y `billing.admin`, desde su estación | Stack `gcp-lz-bootstrap`: proyecto `disasterproject-lz`, bucket `disasterproject-tfstate-gcp`, key ring `lz` con `tofu-state`, pool de federación `github-pool`, `tf-apply-lz@` y `tf-destroy-lz@` | **Local**, sin cifrar: aún no hay dónde guardarlo |
| 2 | La misma persona | `tofu init -migrate-state` al bucket, con cifrado por la clave `lz/tofu-state` | En el bucket, cifrado |
| 3 | La misma persona | Borra el fichero local y retira sus roles de organización; queda como *break-glass* (§5.3) | — |
| 4 | Pipeline, `tf-apply-lz@` | El resto de stacks `gcp-lz-*` (§2–§9) | En el bucket, cifrado |

El bootstrap no se vuelve a ejecutar. Un cambio en lo que crea (una API, un rol del propio pipeline) se hace por PR sobre el mismo stack, ya con estado remoto. El procedimiento del paso 1 vive como runbook en el repositorio, porque la próxima vez que haga falta será para reconstruir la organización y nadie lo recordará (RZ1).

---

## 2. Organización, carpetas y proyectos

| Carpeta | Proyecto | Contiene | Motivo |
|---|---|---|---|
| `platform` | `disasterproject-lz` | Bucket de estado, claves, Artifact Registry, federación, identidades del pipeline, zona padre `disasterproject.com` | Lo que comparten todos los entornos; una identidad de entorno no puede tocarlo |
| `nonprod` | `disasterproject-nonprod` | Los recursos de `dev`, `qa`, `demos`, `sandbox`, `ephemeral-*`, cada uno con su prefijo; las zonas públicas delegadas de cada entorno | `CLAUDE.md`: proyecto compartido, VPC por entorno |
| `prod` | `disasterproject-prod` | Solo `prod` | Límite de aislamiento de `prod` |

Las org policies se aplican por carpeta (§3), así que `nonprod` y `prod` pueden diferir sin repetir la lista.

**Cuando el proyecto non-prod llegue a un límite** (cuotas de CPU, de IPs, de SAs por proyecto), se añade `disasterproject-nonprod-2` en la misma carpeta y los entornos nuevos van allí; ninguno se reparte entre dos proyectos (`CLAUDE.md`). El binding del entorno ya lleva `platform.project_id`, así que moverlo es cambiar ese valor y reconstruir, no rediseñar.

### 2.1 APIs del proyecto non-prod

Las que lista `network-qa` §1.1, habilitadas por el stack `gcp-lz-projects` con `disable_on_destroy = false`. A esa lista se suma una pieza que `network-qa` no podía ver:

| Pieza | Motivo |
|---|---|
| `google_project_service_identity` para `container.googleapis.com`, `sqladmin.googleapis.com`, `secretmanager.googleapis.com` y `storage` | El agente de servicio de un producto se crea **la primera vez que se usa**, no al habilitar la API. La landing zone tiene que concederle roles sobre claves (§4) antes de que el entorno cree el primer cluster; sin forzar su creación, el grant falla con "service account does not exist" **(verificar, VZ2)** |

---

## 3. Org policies

### 3.1 Lista

| Política | Valor | Carpetas | Origen |
|---|---|---|---|
| `iam.disableServiceAccountKeyCreation` | Enforce | Todas | Arquitectura §11.2 |
| `iam.allowedPolicyMemberDomains` | El dominio de la organización | Todas | Arquitectura §11.2 |
| `compute.skipDefaultNetworkCreation` | Enforce | Todas | `network-qa` §2 |
| `compute.restrictVpcPeering` | Solo `projects/*/global/networks/servicenetworking` y los hubs | `nonprod`, `prod` | `network-qa` §5, RW4 |
| `compute.vmExternalIpAccess` | Denegar todo | `nonprod`, `prod` | Nodos sin IP externa (`gke-qa`) |
| `compute.requireShieldedVm` | Enforce | `nonprod`, `prod` | Arquitectura §11.2 |
| `sql.restrictPublicIp` | Enforce | `nonprod`, `prod` | Cloud SQL solo por PSA |
| `storage.publicAccessPrevention` | Enforce | Todas | Ningún bucket público, tampoco el de estado |
| `storage.uniformBucketLevelAccess` | Enforce | Todas | IAM de bucket con condiciones por prefijo (§5.1) |
| `gcp.resourceLocations` | `in:europe-west1-locations` (y `global` para lo que no es regional) | Todas | Residencia; además KMS y buckets deben coincidir con el cluster (E1 §4.14) |
| `cloudkms.minimumDestroyScheduledDuration` | 30 días | `platform` | Ventana de rescate de una versión de clave (E1 §4.14) |
| `run.allowedIngress` | `internal-and-cloud-load-balancing` | `nonprod`, `prod` | R14; ver §3.2 |

### 3.2 `run.allowedIngress` y el servicio `access` de GKE

E1 §4.13 decidió abrir las redes autorizadas del plano de control con un servicio intermedio en Cloud Run (`gke-qa`, stack `access`), llamado por los runners de GitHub **desde internet**. Con `run.allowedIngress` a `internal-and-cloud-load-balancing`, ese servicio no es alcanzable: la política no distingue un servicio de otro.

| Opción | Qué hace | Coste |
|---|---|---|
| **A. Endpoint DNS del plano de control** (recomendada) | GKE expone el API server en un nombre DNS controlado **solo por IAM**, sin listas de IP. Desaparecen el servicio `access`, el reconciliador de IPs huérfanas y la carrera entre jobs de E1 §4.13 | Reabre E1 §4.13, que ya dejaba esta alternativa anotada. Hay que verificar que el proveedor `kubernetes`/`helm` y `kubectl` funcionan contra ese endpoint desde un runner alojado **(VZ5)** |
| B. Excepción de la política en `nonprod` | `run.allowedIngress` admite también `all` en la carpeta | Cualquier servicio Cloud Run del proyecto puede publicarse sin balanceador ni Cloud Armor: R14 vuelve para todos |
| C. Balanceador delante de `access` | Un GLB con backend serverless | Un balanceador, un certificado y una política de Cloud Armor para una función que abre y cierra una IP |

**Recomendación (DZ4):** A. Resuelve el choque y además elimina la parte más frágil de E1 §4.13. Queda como decisión pendiente porque cambia una propuesta ya cerrada.

---

## 4. Claves de Cloud KMS

El diseño de E1 §4.14 se aplica tal cual; aquí queda dónde y quién.

| Pieza | Valor |
|---|---|
| Proyecto | `disasterproject-lz` |
| Key ring | Uno por entorno: `qa`, en `europe-west1` (la clave de etcd debe estar en la ubicación del cluster). Más `lz`, del bootstrap |
| Claves de `qa` | `tofu-state`, `gke-secrets`, `cosign` (E1 §4.14). Las opcionales `gcs-cmek` y `secrets-cmek` no se crean en `qa` |
| Grants | Sobre **cada clave**, nunca sobre el key ring ni el proyecto: `tofu-state` → `tf-plan-qa@`, `tf-apply-qa@`, `tf-destroy-qa@`; `gke-secrets` → agente de GKE de `disasterproject-nonprod`; `cosign` → identidad del build |
| Protección | `prevent_destroy`; ninguna identidad de entorno tiene `cloudkms.admin`; destrucción de versiones con 30 días mínimos (§3.1) |

**El agente de GKE es uno por proyecto** (`gke-qa` §3): el grant de `gke-secrets` de `qa` también lo recibe, en la práctica, cualquier cluster no productivo. La clave por entorno separa por convención, no por IAM: aceptado en no producción, como R54.

---

## 5. Federación e identidades del pipeline

### 5.1 Identidades

Todas en `disasterproject-lz`, no en el proyecto del entorno: así una identidad de `qa` no puede modificar su propia política IAM ni la de otra.

| Identidad | Principal que la usa (federación) | Permisos, en `disasterproject-nonprod` salvo indicación |
|---|---|---|
| `tf-plan-qa@` | `attribute.repository/disasterproject/infra` (cualquier rama) | `roles/viewer`; lectura del prefijo `qa/` del bucket de estado; `tofu-state` de `qa` |
| `tf-apply-qa@` | `attribute.environment/qa` (solo con el GitHub Environment `qa`) | Los roles de arquitectura §11.2; escritura en el prefijo `qa/`; `dns.admin` **sobre la zona de `qa`**; `tofu-state` de `qa` |
| `tf-destroy-qa@` | `attribute.environment/qa-destroy` (Environment con otro grupo de aprobadores) | Como `tf-apply-qa@`, más los `delete` que aquel no tiene (arquitectura §11.4) |
| `tf-apply-lz@`, `tf-destroy-lz@` | `attribute.environment/landing-zone` | Organización, carpetas, proyectos, KMS, Artifact Registry, zona padre. Solo la landing zone |
| `cmdb-reader@` | Job de reconciliación (`cmdb-qa` §7) | `cloudasset.viewer` en `disasterproject-nonprod` |
| `image-mirror@` | Workflow de copia de imágenes (§6.2) | `artifactregistry.writer` sobre el repositorio `third-party` |
| `image-build@` | Workflow de build | `artifactregistry.writer` sobre `apps`; `signerVerifier` sobre `cosign` |

**Bucket de estado.** `disasterproject-tfstate-gcp`, un prefijo por entorno (`qa/`, `dev/`…). Los permisos van con condición IAM sobre el prefijo: `resource.name.startsWith("projects/_/buckets/disasterproject-tfstate-gcp/objects/qa/")`. `tf-plan-qa@` puede leer el estado de productores de su propio entorno para outputs sharing; no el de otro entorno. Versionado activado y retención de 30 días para versiones anteriores: un `apply` que corrompe el estado se recupera desde la versión previa.

### 5.2 Quién aplica la landing zone

Solo `tf-apply-lz@`, desde un GitHub Environment `landing-zone` con revisores del equipo de plataforma y de seguridad. Ninguna identidad de entorno puede asumirla. Los stacks `gcp-lz-*` llevan las etiquetas `landing-zone` y `protected`; los workflows de entorno seleccionan por `--tags qa`, que no los incluye, y aunque los incluyeran, sin `tf-apply-lz@` no podrían aplicarlos.

### 5.3 Break-glass

Una cuenta de persona con `organizationAdmin`, sin uso diario, con alerta en cada inicio de sesión (capa 1b de la landing zone). Es la que ejecutó el bootstrap y la única que puede rehacerlo.

---

## 6. Artifact Registry

### 6.1 Repositorios

| Repositorio | Contenido | Quién escribe | Quién lee |
|---|---|---|---|
| `apps` | Imágenes de las aplicaciones, promovidas entre entornos por re-etiquetado (DG §5) | `image-build@` | SA de nodos de cada entorno |
| `third-party` | Copias por digest de imágenes de terceros: SonarQube, Keycloak, CNPG y su catálogo, Cloud SQL Auth Proxy, Envoy, Gatekeeper… | `image-mirror@` | SA de nodos de cada entorno |
| `charts` | Charts OCI propios de los arquetipos | `image-build@` | `tf-apply-<env>@` |

En `europe-docker.pkg.dev`, dentro del perímetro de la zona privada `pkg.dev` de cada VPC (`network-qa` §4). Gatekeeper P2 solo admite imágenes de estos repositorios y por digest.

### 6.2 Copia de imágenes de terceros

Un workflow programado lee una lista declarada en el repositorio (imagen, versión, digest esperado), copia con `crane copy` por digest y falla si el digest publicado no coincide con el declarado. Actualizar una versión es un PR que cambia la lista, revisado como cualquier otro. Las imágenes nunca se descargan de su registro de origen en tiempo de ejecución.

### 6.3 Grants a identidades que crean capas superiores

La landing zone concede `artifactregistry.reader` a la SA de nodos de `qa` y `cryptoKeyEncrypterDecrypter` al agente de GKE. Si la SA de nodos la crea el stack `gke` (capa 2), la capa 0 no puede aplicar ese grant hasta que exista: la landing zone dependería de la capa 2.

| Opción | Consecuencia |
|---|---|
| **A. La landing zone crea las SAs que reciben grants entre proyectos** (recomendada) | `gke-nodes-qa@disasterproject-nonprod` la crea `gcp-lz-identities`, con nombre determinista; el stack `gke` la usa como global, sin crearla. El agente de GKE existe desde §2.1. Ninguna arista hacia arriba |
| B. El stack `gke` concede el grant | La identidad de `qa` necesitaría `setIamPolicy` sobre un repositorio de la landing zone, y con él podría darse acceso a imágenes de otros entornos |
| C. Grant a nivel de proyecto (`artifactregistry.reader` sobre `disasterproject-lz`) | Cualquier SA con ese rol lee todos los repositorios, también los que no le corresponden |

**Recomendación (DZ5):** A. Cambia `gke-qa` §3: la SA de nodos pasa a ser un global de la landing zone.

---

## 7. DNS e identificador público

| Pieza | Diseño |
|---|---|
| Zona padre | `disasterproject.com`, en `disasterproject-lz`, con DNSSEC. La registra el registrador del dominio; el `DS` del registrador se actualiza a mano en cada cambio de claves (RL4) |
| Identificador público | `random_string` de 7 letras minúsculas (sin números ni mayúsculas), uno por entorno, generado por `gcp-lz-environments` (`edge-qa` DL10). Si contiene una palabra de entorno, G1 rechaza el binding y se regenera (`taint`) |
| Zona del entorno | `<public_id>.disasterproject.com`, creada en `disasterproject-nonprod` con DNSSEC y NSEC3; el recurso se llama `qa-public`. La landing zone escribe en la padre el `NS` y el `DS` de la hija (DL2) |
| Permiso | `roles/dns.admin` para `tf-apply-qa@` **sobre esa zona**, no sobre el proyecto |
| Cómo llega al binding | La landing zone publica `public_id`, `public_zone` y `dns_suffix` como outputs; el PR que da de alta el entorno los copia al binding (`network.public_id`, `dns_zone`, `dns_suffix`), y G1 comprueba el binding (arquitectura §13.3). Son globals deterministas a partir de ese momento: nadie los lee por outputs sharing |

**El identificador no rota** (`edge-qa` DL10). Un `destroy` o un `taint` accidental del `random_string` cambiaría todos los nombres públicos del entorno: `prevent_destroy` y `lifecycle { ignore_changes = all }` sobre él.

---

## 8. Binary Authorization

La política de Binary Authorization es **una por proyecto** (`google_binary_authorization_policy`), con reglas de admisión por cluster (`cluster_admission_rules`, clave `<ubicación>.<cluster>`). En el proyecto non-prod, los clusters de `dev`, `qa`, `demos`… comparten ese único recurso.

| Si la escribe… | Qué pasa |
|---|---|
| Cada stack `gke` (lo que sugiere `gke-qa` §3) | Cada `apply` reescribe la política entera con **su** regla: el último entorno borra las reglas de los demás. Sin error, y el cluster afectado pasa a la regla por defecto |
| **La landing zone** (recomendada, DZ6) | `gcp-lz-binauthz` genera una regla por cluster a partir de los bindings de los entornos del proyecto (los nombres de cluster son deterministas). Un entorno nuevo es un cambio en la landing zone, revisado |

La regla por defecto del proyecto es **denegar**: un cluster sin regla propia no arranca pods, que es un fallo visible en vez de uno silencioso. En `qa`: lista de admisión del repositorio `apps` y `third-party`, atestación en *dry-run* (`gke-qa` DN10).

---

## 9. Facturación y presupuestos

| Pieza | Diseño |
|---|---|
| Cuenta de facturación | Una, enlazada a los tres proyectos |
| Reparto | Por la etiqueta `environment` que llevan todos los recursos (`registry/labels.yaml`); la exportación a BigQuery de la facturación agrupa por ella |
| Presupuestos | Uno por entorno, con filtro por la etiqueta `environment` y por el proyecto; avisos al 50, 90 y 100 %. `qa` tiene su propio umbral aunque comparta proyecto |
| Recursos sin etiqueta | Informe semanal de gasto sin `environment` en el proyecto non-prod: es gasto que no se reparte y, a menudo, un huérfano (`cmdb-qa` §7) |

---

## 10. Pool global y alta de un entorno

| Pieza | Valor |
|---|---|
| Pool | `10.0.0.0/8`, ledger `cmdb-data/pools/environments.json` (AM §9.2) |
| `qa` | `10.4.128.0/17`, asignado por el PR que da de alta el entorno |
| Reservas | El rango del hub y el de la landing zone, fijos, no reclamados (AM §9.2: un claim crearía un ciclo de arranque) |

**Alta de un entorno no productivo** — lo que la landing zone hace, en un solo PR:

1. Asigna el `/17` en el ledger global.
2. Genera el identificador público y crea la zona delegada (§7).
3. Crea el key ring con sus claves (§4).
4. Crea las identidades del entorno y sus enlaces de federación (§5), y la SA de nodos (§6.3).
5. Añade la regla de Binary Authorization del cluster (§8) y el presupuesto (§9).
6. Publica los globals del entorno; el PR del binding los copia.

---

## 11. Políticas, ejecución, riesgos y verificaciones

### 11.1 `assert` y conftest

```hcl
assert {
  assertion = tm_alltrue([for e in global.lz.environments : e.project_id != "disasterproject-prod" || e.name == "prod"])
  message   = "landing-zone: solo prod vive en disasterproject-prod (CLAUDE.md)"
}
assert {
  assertion = tm_alltrue([for k in global.lz.kms_keys : k.location == "europe-west1"])
  message   = "landing-zone: claves en europe-west1 — la de etcd debe estar en la ubicación del cluster (E1 §4.14)"
}
```

| Regla nueva (conftest) | Qué comprueba |
|---|---|
| G3: IAM de la landing zone a nivel de recurso | Ningún `google_project_iam_member` concede a una identidad de entorno un rol sobre `disasterproject-lz`; los grants de claves, repositorios y zonas son por recurso |
| G3: Binary Authorization | El plan de `gcp-lz-binauthz` tiene una regla por cada cluster declarado en los bindings del proyecto, y la regla por defecto es `ALWAYS_DENY` |

### 11.2 Ejecución

| Qué | Cómo |
|---|---|
| Primer despliegue | Bootstrap a mano (§1); después `gcp-lz-org` → `gcp-lz-projects` → `gcp-lz-identities`, `gcp-lz-kms`, `gcp-lz-registry`, `gcp-lz-dns` → `gcp-lz-environments` → `gcp-lz-binauthz` |
| Cambios | Por PR, con el Environment `landing-zone`; el pipeline de un entorno nunca los selecciona |
| Destrucción | No se contempla fuera de un cierre de la organización. Claves, zona padre, bucket de estado y proyectos con `prevent_destroy` |

### 11.3 Riesgos candidatos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| RZ1 | **Bootstrap irrepetible**: nadie recuerda cómo se arrancó cuando hay que reconstruir | Media | Alta — la organización no se puede recrear desde el repositorio | Runbook en el repositorio; el stack de bootstrap sigue en el código y se aplica con estado remoto después |
| RZ2 | **Binary Authorization reescrita por un entorno** | Alta si cada `gke` la escribe | Alta — reglas de otros entornos borradas en silencio | La escribe solo la landing zone (§8); regla por defecto `ALWAYS_DENY` |
| RZ3 | **Grant de proyecto donde bastaba uno de recurso** | Media | Alta — una identidad de entorno lee o escribe recursos de otro | Regla de G3 (§11.1); SAs creadas por la landing zone (§6.3) |
| RZ4 | **Identificador público regenerado** por un `taint` o un `destroy` | Baja | Alta — todos los nombres públicos del entorno cambian | `prevent_destroy` e `ignore_changes` (§7) |
| RZ5 | **Pérdida de la clave de estado** | Baja | Crítico — estado ilegible, irrecuperable (E1 §4.14) | Sin `cloudkms.admin` fuera de la landing zone; 30 días mínimos para destruir una versión |

### 11.4 Verificaciones

| # | Verificación | Resultado que la cierra |
|---|---|---|
| VZ1 | Bootstrap y migración de estado | `gcp-lz-bootstrap` con estado en el bucket, cifrado; la persona que lo ejecutó sin roles de organización |
| VZ2 | Agentes de servicio forzados | El grant de `gke-secrets` se aplica antes del primer cluster, sin "service account does not exist" |
| VZ3 | Federación | `tf-apply-qa@` no es asumible desde un job sin `environment: qa`; `tf-plan-qa@` no lee el prefijo `dev/` del bucket |
| VZ4 | Binary Authorization compartida | Dos clusters no productivos con reglas distintas; un `apply` de la landing zone no altera la regla de ninguno; un cluster sin regla no admite pods |
| VZ5 | Endpoint DNS del plano de control (si se elige DZ4 A) | `helm`, `kubernetes` y `kubectl` funcionan desde un runner alojado con solo IAM; sin redes autorizadas |
| VZ6 | Org policies | `run.allowedIngress` rechaza un servicio con `ingress=all`; `compute.restrictVpcPeering` admite la conexión de PSA (= VW5) |

---

## 12. `prod` y `demos`

| Ajuste | `qa` | `prod` | `demos` |
|---|---|---|---|
| Proyecto | `disasterproject-nonprod` | `disasterproject-prod`, solo | `disasterproject-nonprod` |
| Key ring | `qa` | `prod`, con `secrets-cmek` y `gcs-cmek` | `demos` |
| Binary Authorization | Regla del cluster en la política compartida, atestación en *dry-run* | Política propia del proyecto, atestación **exigida** | Regla del cluster en la política compartida |
| Agente de GKE | Compartido con los no productivos | Propio | Compartido |
| Aprobadores del Environment | Plataforma | Plataforma y seguridad | Plataforma |

---

## 13. Cambios a otros documentos

| Documento | Cambio | Estado |
|---|---|---|
| Propuesta `gke-qa` §3 y §7 | La SA de nodos `gke-nodes-qa@` la crea la landing zone y llega como global (DZ5); la regla de Binary Authorization la escribe la landing zone (DZ6) | **Propuesto** |
| E1 §4.13 y propuesta `gke-qa` (stack `access`) | Endpoint DNS del plano de control en lugar del servicio `access` y de las redes autorizadas (DZ4) | **Propuesto** |
| `network-qa` §1.1 | Agentes de servicio forzados con `google_project_service_identity` | **Propuesto** |
| Arquitectura §11.2 | Identidades del pipeline en el proyecto de la landing zone; condición IAM por prefijo en el bucket de estado | **Propuesto** |
| `risk-register.md` | RZ1–RZ3 como R58–R60 | **Propuesto** |

---

## 14. Decisiones

| # | Decisión | Estado | Recomendación | Alternativa |
|---|---|---|---|---|
| DZ1 | Arranque | **Propuesta** | Stack de bootstrap aplicado una vez a mano, con estado migrado después; runbook en el repositorio | Consola; script fuera del repositorio |
| DZ2 | Proyectos | **Propuesta** | `lz`, `nonprod`, `prod` en tres carpetas; un `nonprod-2` al llegar a límites | Un proyecto por entorno |
| DZ3 | Identidades | **Propuesta** | En el proyecto de la landing zone; grants por recurso; estado con condición por prefijo | En el proyecto del entorno |
| DZ4 | Acceso al plano de control | **Propuesta** — reabre E1 §4.13 | Endpoint DNS, solo IAM | Excepción de `run.allowedIngress`; balanceador delante de `access` |
| DZ5 | SAs con grants entre proyectos | **Propuesta** | Las crea la landing zone | Las crea la capa 2 (arista hacia arriba) |
| DZ6 | Binary Authorization | **Propuesta** | Política del proyecto escrita solo por la landing zone; `ALWAYS_DENY` por defecto | Cada `gke` escribe su regla |
| DZ7 | Presupuestos | **Propuesta** | Por entorno, filtrados por la etiqueta `environment` | Uno por proyecto |

---

## 15. Plan de implementación

| Fase | Contenido | Criterio de salida | Estimación |
|---|---|---|---|
| **0 · Bootstrap** | §1; **VZ1** | Estado de la landing zone en el bucket, cifrado | 0,5 días |
| **1 · Organización** | Carpetas, proyectos, org policies, APIs y agentes; **VZ2**, **VZ6** | `plan` de `gcp-qa-network` sin errores de política ni de API | 1 día |
| **2 · Pipeline** | Federación, identidades, bucket con condiciones; **VZ3** | Un PR de `qa` hace `plan` con `tf-plan-qa@`; el `apply` solo desde el Environment | 1 día |
| **3 · Servicios compartidos** | KMS, Artifact Registry y copia de imágenes, DNS e identificador, Binary Authorization, presupuestos; **VZ4** | Alta de `qa` completa (§10) | 2 días |
| **4 · Acceso** | Si se aprueba DZ4 A: endpoint DNS; **VZ5** | `helm` y `kubectl` contra el cluster de `qa` desde un runner alojado | 0,5 días |

Cinco días para una persona. Es la fase 0 de E1 §6: bloquea todo lo demás.
