# SonarQube Community en el entorno `qa` — Etapa 1: elementos y dependencias

| | |
|---|---|
| **Estado** | Propuesta · etapa 1 de N · revisión 6 (custodia de recovery keys) |
| **Alcance** | Qué elementos necesita SonarQube Community Build en un entorno `qa` completo, de qué depende cada uno y con qué herramienta open source se cubre |
| **Fuera de alcance** | Código (generadores, contratos, charts), integración detallada de cada pipeline, procedimiento de upgrade. Son etapas posteriores |
| **Especificación de referencia** | `docs/archetype-model.md` (AM §n), `docs/terramate-outputs-sharing-architecture.md` (§n), `docs/developer-guide.md` (DG §n), `docs/risk-register.md` |
| **Diagramas** | `diagrams/*.mmd` (fuente Mermaid) y `diagrams/*.svg` (renderizados). El SVG se regenera desde el `.mmd`; no se edita a mano |

Nada de este documento reabre decisiones de `CLAUDE.md`. Donde SonarQube choca con una de ellas (PSS `restricted`, OIDC en el Gateway, `database-platform`), se dice y se propone cómo encajar sin cambiarla.

---

## 0. Contexto confirmado

| Pregunta | Respuesta | Consecuencia principal |
|---|---|---|
| Cloud | **GCP** | GKE **Standard** (no Autopilot, §4.1); borde con NEG standalone + Global external Application LB; GCS, Cloud KMS, Cloud DNS, Certificate Manager, Artifact Registry |
| CI y código | **GitHub** / GitHub Actions | SonarQube se publica a internet detrás de Cloud Armor (D3); tokens de proyecto como secretos de repositorio (D9); en Community solo se analiza `main` (§4.11) |
| Entorno | **Nuevo** — no existe nada | SonarQube es el **primer consumidor** y arrastra el cierre completo de la plataforma: landing zone, entorno, GKE, Gatekeeper, secretos, monitorización, CNPG y Keycloak (§6). Lo gobierna la fase 0 del roadmap |
| Volumen | **200 proyectos**, ≈ 10 M líneas, ≈ 4 merges/día por proyecto | Sizing en §4.12. El cuello de botella no es la memoria sino la **cola del compute engine, de un solo worker** en Community |
| Identidad de personas | **Entra ID** | Keycloak como broker OIDC hacia Entra ID; grupos por *app roles* (§4.6) |
| Región | **`europe-west1`** (Bélgica) | Todo lo regional en la misma región: cluster, discos, buckets, key ring de KMS, Artifact Registry. GCP no tiene región en Irlanda |
| Entra ID | Lo gestiona el **equipo de identidad** | App registration, app roles y asignación de grupos son suyos; la plataforma solo consume el claim `roles` (§4.6) |
| Filtrado por IP | **No** en SonarQube | D3 cerrada: SonarQube público tras Cloud Armor sin listas de IP |
| Acceso del pipeline al cluster | La IP del runner se **abre en las redes autorizadas** de GKE al empezar y se **cierra** al terminar | Procedimiento aceptado; cuatro condiciones para que sea seguro (§4.13) |

Preguntas que siguen abiertas: §10.

---

## 1. Lo que SonarQube Community impone al diseño

| Hecho | Consecuencia en el diseño | Verificar |
|---|---|---|
| **Un solo nodo.** La alta disponibilidad es de Data Center Edition (comercial) | `replicas: 1`, StatefulSet. En `qa` se acepta; RTO ≈ reinicio (2–5 min) más reindexado si se pierde el PVC | — |
| **Un solo worker de compute engine.** Configurar más es de Enterprise Edition (comercial) | Todos los análisis de los 200 proyectos pasan por una cola FIFO. Es el límite de capacidad real (§4.12) | Límite de workers por edición en la versión fijada |
| **Tres JVM en un contenedor**: web, compute engine y search (Elasticsearch embebido) | El límite de memoria cubre tres heaps, tres non-heap y el mmap de ES. Es DG §8.3 multiplicado por tres | Heaps por defecto de la versión fijada |
| **Elasticsearch exige `vm.max_map_count ≥ 524288`** en el host | El chart lo resuelve con un init container **privilegiado**, incompatible con PSS `restricted` y Gatekeeper. Se resuelve **a nivel de nodo** (§4.1) | Que GKE admita el sysctl en el node pool (V1) |
| **Base de datos externa obligatoria.** PostgreSQL soportado | Dependencia de `database-platform` (CloudNativePG) | Rango de versiones PostgreSQL soportado |
| **El único estado real es PostgreSQL.** Los índices de ES se reconstruyen desde la BD | Backup solo de PostgreSQL y de la clave de cifrado | Tiempo de reindexado con 200 proyectos |
| **Sin análisis de ramas ni decoración de PR** en Community | Solo `main`. Un análisis lanzado desde una PR **sobrescribe la historia de `main`** (§4.11) | — |
| **Autenticación integrada: local, SAML, LDAP, GitHub, GitLab.** OIDC genérico solo con plugin de terceros | Keycloak se integra por **SAML** (§4.6) | SAML y sincronización de grupos en Community (V3) |
| **Métricas Prometheus en `/api/monitoring/metrics`**, protegidas por passcode | Scrape con `X-Sonar-Passcode` desde un Secret | — |
| **Logs a stdout** en la imagen de contenedor | Recogida por DaemonSet | — |
| **Plugins desde el update center** por defecto | Plugins horneados en la imagen; egress a internet denegado | — |

---

## 2. Dónde encaja en el modelo de arquetipos

| Pregunta | Respuesta | Razón |
|---|---|---|
| ¿Arquetipo o componente? | **Arquetipo `sonarqube`**, `kind: catalog`, **capa 5** | No despliega un operador ni impone contrato multi-tenant (AM §5.4). Lo consumen pipelines por HTTP, no stacks por outputs sharing; no publica `provides` |
| ¿Modelo de entorno? | `qa` **dedicado** (§12.1) | Una instancia de SonarQube por entorno |
| ¿Instancia y stack IDs? | `sonarqube-main` → `gcp-qa-sonarqube-main-<stack>` | Convención `<cloud>-<env>-<capability>[-<instance>]` |
| ¿Runtime? | **`gke`** (Standard) | ES necesita disco persistente de baja latencia y sysctl de nodo. Cloud Run no da ninguno; Autopilot no da el segundo |

---

## 3. Inventario de elementos

### 3.1 Vista de contexto

![Contexto](diagrams/01-contexto.svg)

Fuente: [`diagrams/01-contexto.mmd`](diagrams/01-contexto.mmd)

### 3.2 Cierre de dependencias por capas

![Capas y dependencias](diagrams/02-capas-dependencias.svg)

Fuente: [`diagrams/02-capas-dependencias.mmd`](diagrams/02-capas-dependencias.mmd)

### 3.3 Tabla de elementos

Todo se construye de cero. **Registro** indica si la capability existe en `registry/capabilities.yaml`.

| Capa | Capability | Implementación en GCP | Licencia | Por qué la necesita SonarQube | Registro |
|---|---|---|---|---|---|
| 0 | `dns-zone` | Cloud DNS, zona delegada `qa.acme.com` | cloud | Registro wildcard `*.qa.acme.com` | ✓ |
| 0 | `cidr-pool` | Ledger del modelo (AM §9) | — | Una `/17` del bloque permanente `10.2.0.0/15` | ✓ |
| 0 | `cert` | Certificate Manager, certificado **wildcard** `*.qa.acme.com` con DNS authorization | cloud | TLS público en el borde | ✓ |
| 0 | `waf` | Cloud Armor | cloud | Única protección de red posible con runners alojados por GitHub (D3) | ✓ |
| 0 | `edge-ip` | IP global reservada | cloud | Destino del wildcard | ✓ |
| 0 | *(KMS)* | Cloud KMS, key ring `qa` en `europe-west1` | cloud | Estado de OpenTofu, secretos de etcd, auto-unseal de OpenBao, firma de imágenes (§4.14) | ✗ — deliberado, §4.14 |
| 0 | *(registro)* | Artifact Registry: repo remoto de Docker Hub + repo estándar | cloud | Imagen propia con plugins, pull por digest | ✗ — mismo criterio que KMS |
| 0 | *(identidad CI)* | Workload Identity Federation para GitHub Actions (§11.2) | cloud | Despliegue de la plataforma sin claves | — |
| 1 | `network` | VPC / subredes de `qa`, Cloud NAT, **Private Google Access** | cloud | Nodos, pods, acceso a GCS sin internet | ✓ |
| 1 | `env-edge` | Backend service + URL map + proxy + forwarding rule | cloud | Entrada hacia el NEG del Gateway | ✓ |
| 1b | `cloud-observability` | Cloud Logging **reducido** a auditoría y plano de control de GKE | cloud | No lo consume SonarQube; auditoría | ✓ |
| 2 | `cluster` | **GKE Standard** regional, node pools `general` y `sonar` | cloud | Donde corre; `sonar` aporta el sysctl | ✓ (+ trait) |
| 2b | `policy` | **OPA Gatekeeper** | Apache-2.0 | PSS `restricted`, etiquetas, registros permitidos | ✓ |
| 3 | `ingress` | **Envoy Gateway** (`gateway-envoy-gke`) | Apache-2.0 | `HTTPRoute`, políticas de tráfico | ✓ |
| 3 | `certs` | **cert-manager** con **CA interna** (`ClusterIssuer` CA) | Apache-2.0 | TLS GLB→Envoy y de OpenBao. Sin ACME: el certificado público lo da Certificate Manager | ✓ |
| 3 | `dns` | **No se enlaza** | — | El wildcard de `env-edge` lo cubre; external-dns no aporta nada con un Gateway y una IP por entorno (igual que `demos`, AM §7) | ✓ sin uso |
| 3 | `secrets` | **OpenBao** (Raft ×3, auto-unseal Cloud KMS) + **External Secrets Operator** | MPL-2.0 / Apache-2.0 | Credenciales, passcode, clave de cifrado, SAML | ✓ |
| 3 | `monitoring` | **kube-prometheus-stack**, **Grafana**, **Loki** (sobre GCS), **Fluent Bit**, **Blackbox exporter** | Apache-2.0 / AGPL-3.0 | Métricas, logs, alertas, sonda externa | ✓ (+ trait) |
| 4 | `object-store` | Buckets GCS por propósito | cloud | Backups CNPG, chunks de Loki, snapshots de OpenBao | ✓ |
| 4 | `database-platform` | **CloudNativePG** | Apache-2.0 | SonarQube y Keycloak crean su propio `Cluster` | ✓ (+ trait) |
| 4 | `oidc-idp` | **Keycloak**, realm `qa` | Apache-2.0 | Personas vía **SAML** | ✓ (+ trait) |
| 5 | — | **SonarQube Community Build**, chart oficial `sonarqube/sonarqube` | LGPL-3.0 | La aplicación | — |
| CI | — | **GitHub Actions** + `SonarSource/sonarqube-scan-action`, **Trivy**, **cosign** | — / Apache-2.0 | Análisis; build, escaneo y firma de la imagen propia | — |

Herramientas de plataforma sin cambios: Terramate, OpenTofu, conftest, Checkov.

**Qué es cloud y qué es OSS.** Todo lo que corre en el cluster es open source. Lo que queda en GCP es lo que no se puede o no conviene operar uno mismo: borde (LB, Cloud Armor, certificado público), KMS, almacenamiento de objetos y registro. Sustituir GCS o Artifact Registry por equivalentes OSS en el propio cluster crearía dependencias circulares (un backup dentro del cluster que protege no es un backup) y más superficie que operar. Se descarta Harbor por el mismo motivo, y MinIO además porque su edición comunitaria dejó de distribuir binarios e imágenes en 2025.

**Licencias.** Grafana y Loki son AGPL-3.0: sin impacto para uso interno sin modificar; que lo confirme quien gestione licencias.

---

## 4. Dependencias por dominio

### 4.1 Runtime: GKE Standard y node pool `sonar`

| Elemento | Propuesta | Motivo |
|---|---|---|
| Cluster | GKE Standard **regional**, plano de control privado, Workload Identity, release channel `STABLE`, `deletion_protection: true` (§12.6) | Línea base de §5.7 |
| Pods por nodo | 64 (default de plataforma) | No aplica la pregunta abierta de Autopilot |
| Node pool `sonar` | 1 nodo **n2-standard-8** (8 vCPU, 32 GB) en **una zona**, taint `dedicated=sonar:NoSchedule` | Aísla sysctl y presión de memoria. Zona única porque el PVC es zonal |
| Sysctl | `node_config.linux_node_config.sysctls = { "vm.max_map_count" = "524288" }` | Elimina el init container privilegiado |
| `fs.file-max` | Sin acción: el kernel lo dimensiona con la RAM y en 32 GB supera 131072 de sobra | Verificar en V1 |
| StorageClass | `hyperdisk-balanced`, `WaitForFirstConsumer`, `allowVolumeExpansion: true` | IOPS configurables sin sobredimensionar disco |
| Acceso del pipeline al plano de control | Endpoint público del plano de control con **redes autorizadas vacías por defecto**; la IP del runner se abre y cierra por job | Decisión del equipo (§4.13); cubre R18 |

**Por qué no Autopilot.** No permite configurar sysctl de nodo ni contenedores privilegiados. Se propone el trait **`sysctl-max-map-count`** en `cluster`: `gke` lo tiene, `gke-autopilot` no, y un binding equivocado falla en resolución en vez de en el primer arranque con `max virtual memory areas vm.max_map_count [65530] is too low`.

**Plan B** si V1 falla: `SONAR_SEARCH_JAVAADDITIONALOPTS=-Dnode.store.allow_mmap=false`, a costa de rendimiento de ES. Con 200 proyectos habría que medirlo antes de aceptarlo.

**Zona única.** Si cae la zona, SonarQube queda caído hasta que vuelva. Para `qa` se acepta. La alternativa es `hyperdisk-balanced-high-availability` (réplica síncrona entre dos zonas) con el node pool en esas dos zonas: RTO de minutos ante caída de zona, a costa del doble de coste de disco.

### 4.2 Política de admisión (capa 2b)

`qa`: `enforcementAction: deny`, `failurePolicy: Ignore` (§13.7).

![Pod de SonarQube](diagrams/08-pod-sonarqube.svg)

| Requisito PSS `restricted` / Gatekeeper | Ajuste en el chart |
|---|---|
| Sin contenedores privilegiados | `initSysctl.enabled: false` |
| Sin ejecución como root | `initFs.enabled: false`; permisos vía `fsGroup` |
| `runAsNonRoot`, `seccompProfile: RuntimeDefault`, `drop: [ALL]`, `allowPrivilegeEscalation: false` | `securityContext` y `containerSecurityContext` explícitos |
| Etiquetas obligatorias (`registry/labels.yaml`) | Emitidas por el generador en namespace y workload |
| `readOnlyRootFilesystem` (si hay constraint) | `emptyDir` en `temp` y `logs`; verificar qué más escribe (V2) |
| Imágenes solo de registros permitidos | `europe-docker.pkg.dev/<proyecto>/…` por digest |

Si SonarQube no puede correr con raíz de solo lectura, la salida es una **exención por nombre** para `sonarqube/sonarqube-0`, revisada en PR — nunca relajar el constraint para todo `qa`.

### 4.3 Secretos

![Flujo de secretos](diagrams/04-secretos.svg)

| Secreto | Ruta en OpenBao | Consumidor | Notas |
|---|---|---|---|
| Usuario y password JDBC | `qa/sonarqube/db` | CNPG (`bootstrap.initdb.secret`) y SonarQube | Un único origen para ambos lados |
| Monitoring passcode | `qa/sonarqube/passcode` | SonarQube y `PodMonitor` | Mismo namespace que el `PodMonitor` |
| Password admin | `qa/sonarqube/admin` | Job del chart | Break-glass tras activar SAML |
| Clave de cifrado de settings | `qa/sonarqube/secret-key` | `sonar.secretKeyPath` | Si se pierde, los settings cifrados son irrecuperables: entra en DR |
| Material SAML | `qa/sonarqube/saml` | Certificado del IdP; clave del SP si se firman peticiones | — |
| Tokens de análisis | **Secretos de repositorio en GitHub** (D9) | GitHub Actions | No en OpenBao: exigiría publicar OpenBao a internet para los runners alojados |

- **ESO como interfaz, OpenBao como backend.** Cambiar a Secret Manager es cambiar el `SecretStore`, no el arquetipo.
- **Auto-unseal con Cloud KMS**, clave `openbao-unseal` de capa 0 (§4.14); la cuenta de servicio de OpenBao tiene `cryptoKeyEncrypterDecrypter` solo sobre esa clave.
- **`SecretStore` por namespace**, rol de Kubernetes auth ligado a `ns=sonarqube, sa=eso-sonarqube` exacto (espíritu de R15).
- **Workloads a OpenBao por Kubernetes auth**, no por OIDC de Keycloak: evita el ciclo de §6.
- **Por outputs sharing solo viajan rutas**, nunca valores (§11.6, R8).

### 4.4 Datos: PostgreSQL con CloudNativePG

`database-platform` sin enlazar es la decisión de `demos`. En `qa` se propone **enlazarlo** a CloudNativePG, con una instancia **propia** por consumidor:

| Opción | Qué crea SonarQube | Recomendación |
|---|---|---|
| A. `Database` + `Role` en un `Cluster` compartido | BD lógica | No: SonarQube es intensivo en BD; vecino ruidoso en ambos sentidos |
| **B. `Cluster` CNPG propio en `sonarqube`** | Instancia dedicada, operador compartido | **Sí** — bus común, datos separados, como Kafka |
| C. Cloud SQL (`data` condicional) | Servicio gestionado | Solo si se abandona el requisito OSS para datos |

Requiere que `postgres-operator` autorice `Cluster` y `ScheduledBackup` en `tenant_resources` (AM §10.4). Keycloak usa el mismo patrón: es el segundo `Cluster` del entorno.

Backups a GCS con **Workload Identity**: IAM `roles/storage.objectAdmin` sobre el bucket para el principal exacto `principal://iam.googleapis.com/projects/<n>/locations/global/workloadIdentityPools/<proyecto>.svc.id.goog/subject/ns/sonarqube/sa/sonarqube-db`. Sin clave JSON; sin comodín.

### 4.5 Publicación

| Elemento | Propuesta |
|---|---|
| Hostname | `sonar.qa.acme.com` — **claim** en el ledger aunque el DNS sea wildcard: la unicidad del nombre sigue siendo escasa |
| DNS | Registro wildcard `*.qa.acme.com` → IP global, creado una vez por `gcp-qa-edge` |
| TLS público | Certificate Manager, wildcard, en el GLB |
| TLS interno | GLB → Envoy por HTTPS con certificado de la CA interna de cert-manager |
| Gateway | Uno por entorno, `allowedRoutes.namespaces.from: Selector` (§10.6); NEG standalone `eg-qa-neg` (§10.2, R20) |
| Timeout del backend service | **120 s** (por defecto 30 s): la subida del informe de un proyecto grande los supera |
| Envoy | `BackendTrafficPolicy` con timeout ≥ 120 s; `ClientTrafficPolicy` con límite de cuerpo ≥ 100 MiB |
| Firewall VPC | Rangos de health check del GLB (`35.191.0.0/16`, `130.211.0.0/22`) hacia los pods de Envoy — selector `cidr:` legítimo (AM §6.3) |

Recursos Gateway API empaquetados en el chart y desplegados con `helm_release`, nunca `kubernetes_manifest` (R24).

### 4.6 Autenticación y autorización

![Autenticación](diagrams/05-autenticacion.svg)

La plataforma prevé OIDC en el Gateway con `SecurityPolicy`. **No sirve para SonarQube**: la misma ruta la usan personas y GitHub Actions, y el scanner envía `Authorization: Bearer <token de SonarQube>` a `/api/*`. Una `SecurityPolicy` OIDC lo redirigiría a Keycloak y todos los análisis fallarían.

| Quién | Mecanismo | Dónde se valida |
|---|---|---|
| Personas | **SAML 2.0** contra Keycloak (realm `qa`, cliente `sonarqube`) | SonarQube |
| GitHub Actions | **Token de análisis de proyecto** (D9) | SonarQube |
| Break-glass | Cuenta local `admin` | SonarQube |
| Anónimos | Prohibidos: `sonar.forceAuthentication=true` | SonarQube |

`HTTPRoute` de SonarQube **sin `SecurityPolicy` OIDC**, igual que la de Keycloak. SAML es front-channel: SonarQube no necesita red hacia Keycloak.

**Identidades en Entra ID.** Keycloak no es fuente de verdad de usuarios: hace de **broker** hacia Entra ID (identity provider OpenID Connect en el realm `qa`) y emite SAML hacia SonarQube. MFA y acceso condicional se aplican en Entra ID, antes de llegar a Keycloak.

| Tema | Propuesta | Por qué |
|---|---|---|
| Registro en Entra ID | Una *app registration* `keycloak-qa`, redirect URI `https://sso.qa.acme.com/realms/qa/broker/entra/endpoint` | Un solo punto de confianza con Entra para todas las aplicaciones de `qa` |
| Credencial de Keycloak ante Entra | **Certificado** (client assertion firmada), no client secret | Los client secrets de Entra caducan (≤ 24 meses) y suelen caducar en producción sin aviso. Clave privada en OpenBao |
| Grupos | **App roles** en la app registration (`sonar-administrators`, `sonar-users`, `team-<x>`), asignados a grupos de Entra | El claim `groups` de Entra trae **GUIDs**, no nombres, y con más de 200 grupos se sustituye por un *overage* que exige llamar a Graph. El claim `roles` trae nombres estables y solo los de esta aplicación |
| Mapeo en Keycloak | Mapper *claim to group* por cada rol → grupo de Keycloak; sincronización `force` en cada login | Un cambio de pertenencia en Entra se refleja en el siguiente login |
| Hacia SonarQube | SAML con atributo `groups` = grupos de Keycloak | Sin cambios respecto al diseño anterior |
| Red | Keycloak necesita **egress** a `login.microsoftonline.com` (intercambio de código back-channel) vía Cloud NAT | SonarQube sigue sin necesitar red hacia Keycloak ni Entra |

Se mantiene Keycloak como intermediario (D4) aunque SonarQube podría hacer SAML directo contra Entra ID: Grafana, OpenBao y las aplicaciones futuras de `qa` usan el mismo realm, y la `SecurityPolicy` OIDC de Envoy para el resto de aplicaciones se diseñó contra Keycloak. El coste es que Keycloak queda en el camino crítico de login.

**Baja de usuarios.** Community no tiene SCIM (es de Enterprise). Deshabilitar a alguien en Entra ID impide su login, pero su usuario de SonarQube y **sus tokens personales siguen activos**. Mitigación: prohibir tokens personales en CI (solo tokens de proyecto, D9) y un job de reconciliación diario que desactive en SonarQube los usuarios cuyo login ya no exista o esté deshabilitado en Entra ID (Graph API + Web API de SonarQube).

| Grupo | Permisos en SonarQube |
|---|---|
| `sonar-administrators` | Administración global |
| `sonar-users` | Navegar |
| `team-<x>` | Plantilla de permisos por prefijo de clave de proyecto `<x>_*` |

Cada grupo de SonarQube corresponde a un app role de Entra ID; alta de un equipo = app role nuevo + grupo de Entra asignado + plantilla de permisos.

Con 200 proyectos, los permisos **solo** por plantillas: un proyecto nuevo nace con los de su equipo.

### 4.7 Observabilidad

![Observabilidad](diagrams/06-observabilidad.svg)

| Señal | Recogida | Alertas propuestas |
|---|---|---|
| Disponibilidad externa | Blackbox → `https://sonar.qa.acme.com/api/system/status` (pasa por GLB, Cloud Armor y Gateway) | ≠ `UP` durante 5 min |
| **Cola del compute engine** | `PodMonitor` sobre `/api/monitoring/metrics` | Pendientes > 20 durante 15 min; tarea más antigua > 10 min. **La alerta clave con 200 proyectos** |
| Tareas CE fallidas | Idem | Tasa de fallos > 5 % en 1 h |
| JVM | Idem | Heap > 90 % sostenido |
| Contenedor | kube-state-metrics | `OOMKilled` (exit 137, DG §8.3); memoria > 90 % |
| Disco | kubelet | PVC de ES > 80 % (ES pasa a solo lectura por encima de su watermark); PVC de BD > 80 % |
| PostgreSQL | Exporter CNPG | Retraso de réplica; conexiones > 80 %; último backup correcto > 26 h |
| Logs | Fluent Bit → Loki (GCS) | Tasa de `ERROR` |
| Certificados | cert-manager | CA interna o certificado de Envoy < 14 días |

`PodMonitor` y `PrometheusRule` van en el chart del arquetipo (CRD en plan, R24); de ahí el trait **`prometheus-operator-crds`**. Grafana entra por OIDC con Keycloak, sin ciclo.

### 4.8 Red

![Red](diagrams/07-red.svg)

`NetworkPolicy` default-deny de entrada y salida en `sonarqube`:

| Origen | Destino | Puerto |
|---|---|---|
| Envoy | SonarQube | 9000 |
| Prometheus | SonarQube / CNPG | 9000 / 9187 |
| SonarQube | CNPG | 5432 |
| CNPG | CNPG | 5432 (replicación) |
| Operador CNPG | CNPG | 8000 |
| CNPG | `storage.googleapis.com` vía Private Google Access | 443 |
| Todos | kube-dns | 53 |
| SonarQube | Internet | **Denegado**; `sonar.updatecenter.activate=false` |

GKE aplica `NetworkPolicy` con Dataplane V2; el egress a las APIs de Google se expresa por FQDN (`FQDNNetworkPolicy`) o por los rangos de Private Google Access — verificar cuál soporta la versión.

### 4.9 Backup y recuperación

| Qué | Cómo | Dónde | Retención |
|---|---|---|---|
| PostgreSQL | CNPG barman-cloud: base diaria + WAL continuo (PITR) | `gs://acme-qa-backups-db` | 14 días (§12.6) |
| OpenBao (incluye clave de cifrado de SonarQube) | Snapshot Raft programado | `gs://acme-qa-backups-bao` | 14 días |
| Índices de ES | No se respaldan | — | Reindexado |
| Configuración | Git | — | — |

Buckets con versionado de objetos y retention policy, en la región del cluster. Velero no hace falta: todo el estado está en PostgreSQL, OpenBao o Git.

Restauración ensayada una vez antes de dar el entorno por bueno (V5).

### 4.10 Cadena de suministro de la imagen

| Paso | Herramienta |
|---|---|
| Imagen `FROM sonarqube:<versión>-community` + plugins en `extensions/plugins` | GitHub Actions en el repo del arquetipo |
| Escaneo | Trivy, bloqueante en `CRITICAL` con fix |
| Firma | cosign con clave en Cloud KMS (evita publicar en el log público de Rekor) |
| Registro | Artifact Registry; base desde el repo remoto de Docker Hub (evita límites de pull) |
| Despliegue | Por digest (DG: la imagen se promueve, no se reconstruye) |

### 4.11 Integración con GitHub Actions

![Flujo de CI](diagrams/09-ci-github.svg)

| Regla | Motivo |
|---|---|
| **Analizar solo en `push` a `main`**, nunca en `pull_request` | Community no tiene ramas: un análisis desde una PR **se registra como `main`** y contamina su historia y el quality gate. Error silencioso; se impone con una regla de conftest/actionlint sobre los workflows |
| `concurrency: { group: sonar-${{ github.repository }}, cancel-in-progress: true }` | Dos merges seguidos: solo se analiza el último. Alivia la cola |
| `sonar.qualitygate.wait=true` con `timeout` 300 s | El job falla si el gate falla; con la cola llena el job espera y consume minutos: vigilar |
| Clave de proyecto `<org>_<repo>` | Plantillas de permisos por prefijo |
| Workflow reutilizable en un repo central | 200 copias de un workflow divergen; uno reutilizable se cambia una vez |
| Onboarding automatizado | Crear proyecto + token de proyecto con caducidad + secreto `SONAR_TOKEN` en el repo, por API de SonarQube y de GitHub (D9) |

Los runners alojados por GitHub salen desde rangos enormes y cambiantes: filtrar por IP en Cloud Armor no es útil. Cloud Armor aporta reglas OWASP (con exclusiones en `/api/ce/submit`, cuyo multipart dispara falsos positivos — verificar) y rate limit por IP; la autenticación la hace SonarQube.

### 4.12 Dimensionamiento para 200 proyectos

Estimación confirmada: mediana de 50 k líneas por proyecto, ≈ 10 M líneas en total, ≈ 4 merges a `main` por proyecto y día.

| Recurso | Valor inicial | Base |
|---|---|---|
| Node pool `sonar` | 1 × n2-standard-8 (8 vCPU, 32 GB) | Contenedor de 12 GiB + page cache para ES |
| Pod SonarQube | request 4 vCPU / 12 GiB, limit 12 GiB, **sin límite de CPU** | Con `limits.cpu` bajo, las JVM eligen SerialGC y el CE se ralentiza (DG §8.3) |
| Heaps | web `-Xmx2g`, CE `-Xmx3g`, search `-Xmx3g` | Σ 8 GiB + ≈ 1,5 GiB non-heap + margen = 12 GiB. **Nunca** heap = límite |
| PVC de ES | 50 GiB `hyperdisk-balanced`, 3000 IOPS | Expandible |
| PostgreSQL | 2 instancias (primaria + réplica), 2 vCPU / 8 GiB, 100 GiB, `max_connections` 200 | Pool de SonarQube ≈ 60 por proceso |
| GCS backups | ≈ 2–3× el tamaño de la BD con 14 días de WAL | — |

**La cola del compute engine es el límite.** 200 proyectos × 4 análisis/día = 800 tareas diarias. Con 20–60 s por tarea son **4,5–13 h de trabajo en serie**, concentradas en la jornada. En la parte alta, la cola crece en horas punta y los jobs de GitHub esperan al quality gate. Palancas, en orden:

1. Solo `main` y `cancel-in-progress` (ya incluidos).
2. CPU suficiente para el CE: la tarea es mayoritariamente monohilo; más núcleos no la aceleran, frecuencia sí (valorar c3 frente a n2 en V4).
3. Monorepos grandes fuera de horas punta.
4. Si la alerta de cola salta de forma sostenida: Enterprise Edition (varios workers, comercial) o separar en dos instancias por grupo de equipos.

V4 mide el tiempo real por tarea con proyectos representativos antes de fijar nada.

### 4.13 Acceso del pipeline al plano de control de GKE

Procedimiento decidido: el endpoint del plano de control es público pero con **redes autorizadas vacías** por defecto; cada job de GitHub Actions que necesita la API de Kubernetes añade la IP de su runner, ejecuta y la retira. Cubre R18 sin runners self-hosted.

![Acceso del runner](diagrams/10-acceso-runner.svg)

Funciona, con cuatro condiciones. Sin ellas falla de formas poco evidentes:

| # | Problema | Condición |
|---|---|---|
| 1 | **Carrera entre jobs.** La lista de redes autorizadas se actualiza **reemplazándola entera**: dos jobs simultáneos leen, añaden su IP y escriben, y el segundo borra la del primero, que pierde el acceso a mitad de un `apply` | Serializar: `concurrency: { group: gke-qa-api, cancel-in-progress: false }` en **todos** los workflows que abren la IP. Un job espera al anterior |
| 2 | **IP huérfana.** Un runner que muere o un job cancelado a destiempo no ejecuta el paso de cierre | Cierre en un paso `if: always()` **y** un reconciliador programado (cada 15 min) que retira toda entrada con más de 60 min. Cada entrada lleva `display_name = gha-<run_id>-<epoch>` para poder caducarla |
| 3 | **Deriva con OpenTofu.** Si `gcp-qa-gke` gestiona `master_authorized_networks_config`, un `apply` de ese stack revierte la IP del propio runner a mitad de ejecución, y cada `plan` muestra diferencias | `lifecycle { ignore_changes = [master_authorized_networks_config] }` en el cluster: la lista la gestiona solo el procedimiento; la línea base (vacía) se fija en la creación |
| 4 | **Escalada de privilegios.** Abrir la IP requiere `container.clusters.update`, que permite cambiar **cualquier** ajuste del cluster. La identidad de *preview* (PR, cualquier rama, §11.2) también la necesita, porque el plan de los proveedores `helm`/`kubernetes` consulta la API | **No dar `clusters.update` a las identidades del pipeline.** Un servicio intermedio mínimo (Cloud Run function) con esa permisión expone solo `open(ip)` / `close(ip)`, valida que la IP sea una /32, fija la caducidad y registra quién la pidió. El pipeline lo invoca con su identidad OIDC de GitHub |

Aun así, abrir la IP no autentica a nadie: la API sigue exigiendo IAM. Las redes autorizadas son una segunda barrera, no la primera. Y la IP de un runner alojado es compartida con otros clientes de GitHub durante la ventana abierta, aunque sin credenciales de IAM no obtienen nada.

La alternativa que haría innecesario todo lo anterior es el **endpoint DNS del plano de control** de GKE, controlado solo por IAM y sin listas de IP. Queda anotada por si el reconciliador o el servicio intermedio resultan más costosos de operar de lo previsto.

### 4.14 Claves de Cloud KMS

**Qué dice la documentación.** KMS aparece como requisito en cuatro sitios, pero **no como capability** ni con dueño asignado:

| Referencia | Qué exige |
|---|---|
| Arquitectura §5.7 (línea base GKE) | Cifrado de secretos de Kubernetes en etcd (*application-layer secrets encryption*) con una clave de Cloud KMS propia |
| Arquitectura §11.5, R17, checklist de fase 0 | Cifrado del estado de OpenTofu (bloque `encryption`, `key_provider "gcp_kms"`), **recomendado**, con **una clave por entorno**, no por stack: el consumidor de outputs sharing necesita la clave del productor. Si el bucket de estado usa CMEK, además `cryptoKeyDecrypter` |
| Arquitectura §11.6 | El material de clave nunca cruza outputs sharing; se comparte el nombre del recurso |
| Arquitectura §11.3 (AWS) | SCP que deniega `kms:ScheduleKeyDeletion` sobre las claves de estado. **No tiene equivalente escrito para GCP** |

Lo que la documentación **no** dice: qué stack crea las claves, en qué capa, con qué rotación y cómo se protegen de la destrucción en GCP. Es un hueco, y aparece al construir el primer entorno.

**Propuesta: key ring por entorno en capa 0.**

| Clave | Tipo | Consumidor | Rol IAM, sobre esa clave solamente | Rotación |
|---|---|---|---|---|
| `tofu-state` | Simétrica | Todas las identidades de pipeline de `qa` (`tf-plan-qa@`, `tf-apply-qa@`, `tf-destroy-qa@`) | `cryptoKeyEncrypterDecrypter` — también la de *plan*: el bloque `plan { }` **cifra** el fichero de plan | 90 días automática |
| `gke-secrets` | Simétrica | Agente de servicio de GKE (`service-<n>@container-engine-robot`) | `cryptoKeyEncrypterDecrypter` | 90 días |
| `openbao-unseal` | Simétrica | SA de OpenBao vía Workload Identity | `cryptoKeyEncrypterDecrypter` | 90 días |
| `cosign` | Asimétrica de firma (EC P-256) | Identidad del build de imágenes | `signerVerifier` | Manual, con solapamiento |
| *(opcional)* `gcs-cmek` | Simétrica | Agente de servicio de Cloud Storage | `cryptoKeyEncrypterDecrypter` | 90 días |

**Por qué capa 0 y no capa 1.** La clave de estado debe existir **antes** del primer stack cifrado de `qa`, que es el propio `gcp-qa-network`. Si la creara el stack de entorno, su estado se cifraría con una clave que él mismo crea. La landing zone ya es el singleton que se arranca a mano; su propia clave de estado es la única que se crea fuera del pipeline (bootstrap documentado, una vez).

**Por qué no es una capability.** Los nombres son deterministas (`projects/<p>/locations/europe-west1/keyRings/qa/cryptoKeys/<propósito>`): por el árbol de platform-overview §4, son **globals**, sin permisos de lectura de estado ni aristas de outputs sharing. Una capability solo tendría sentido si hubiera varios proveedores entre los que elegir (Cloud HSM, EKM). Si aparece ese requisito, se añade entonces, con traits como `hsm`. El mismo razonamiento vale para Artifact Registry.

**Restricciones de GCP a tener en cuenta:**

| Restricción | Consecuencia |
|---|---|
| La clave de etcd debe estar en la **misma ubicación que el cluster** | Key ring regional en `europe-west1`, no `global` ni `europe` |
| La clave CMEK de un bucket debe coincidir con la ubicación del bucket | Buckets regionales en `europe-west1` |
| **Un key ring y una clave no se pueden borrar** en Cloud KMS, solo sus versiones | Nombres definitivos desde el principio; un error de nombre queda para siempre |
| Destruir una versión es programado (por defecto 30 días) | Es la ventana de rescate. Org policy `constraints/cloudkms.minimumDestroyScheduledDuration` para imponer un mínimo |

**Protección frente a destrucción** — el equivalente GCP que falta de la SCP de AWS:

- Ninguna identidad de pipeline tiene `cloudkms.admin` ni `cryptoKeyVersions.destroy`. Solo el stack de landing zone, con su identidad de destroy separada (§11.4).
- `lifecycle { prevent_destroy = true }` en las claves.
- Perder `tofu-state` deja el estado ilegible; perder `openbao-unseal` deja OpenBao sellado para siempre y con él todos los secretos, incluida la clave de cifrado de SonarQube. Las dos son irrecuperables: son el activo más crítico del entorno.

**Recuperación de OpenBao: recovery keys en Secret Manager.** Con auto-unseal, OpenBao genera en su inicialización *recovery keys* por Shamir. No desellan (eso lo hace la clave KMS); sirven para **generar un token raíz** y para re-keying. Quien reúna el umbral es raíz de OpenBao: lee todos los secretos de `qa`, cambia políticas y **puede desactivar la auditoría**.

Guardarlas en Secret Manager es razonable: con auto-unseal, si se pierde GCP (proyecto o clave KMS), OpenBao está perdido tenga uno las recovery keys donde las tenga. Lo que importa es **quién puede reunir el umbral**.

**Decisión del equipo:** custodio el **equipo SRE**, las claves se quedan en Secret Manager y **el pipeline accede por WIF**.

Tal cual, el Shamir no aporta nada: tanto el grupo SRE como la identidad del pipeline llegan a todos los fragmentos. Eso es aceptable si se dice explícitamente y se compensa con otros controles. Lo que no es aceptable es que el acceso del pipeline sea de **lectura** con la identidad de despliegue de cada día, porque entonces cualquier merge a `main` que llegue a ejecutarse con esa identidad puede hacerse raíz de OpenBao sin dejar rastro en OpenBao.

| Condición | Motivo |
|---|---|
| El pipeline accede solo para **escribir** (`secretmanager.secretVersionAdder`), no para leer | La inicialización automatizada necesita **guardar** los fragmentos, no leerlos. Nada del ciclo normal de despliegue necesita raíz de OpenBao |
| Si hay un caso real de **lectura** desde pipeline (recuperación automatizada), se hace con una identidad WIF **separada**, `bao-breakglass-qa@`, ligada a un workflow propio y a un GitHub Environment con revisores obligatorios | Nunca `tf-plan-qa@` (se ejecuta desde cualquier rama) ni `tf-apply-qa@` (se ejecuta en cada merge) |
| SRE sin acceso permanente: `secretAccessor` concedido **just-in-time** con **Privileged Access Manager** de GCP, con justificación, duración máxima de 1 h y **aprobación de otro miembro de SRE** | Recupera la regla de dos personas que el Shamir pierde al tener un único custodio |
| Un único secreto `openbao-qa-recovery` con los fragmentos (umbral 3 de 5 se mantiene en OpenBao) | Separar en cinco secretos no aporta nada con un solo custodio; simplifica la operación |
| En el **proyecto de landing zone / seguridad**, no en el de `qa` | Quien administra `qa` no llega a los fragmentos |
| *Data Access audit logs* en Secret Manager y **alerta por cada lectura**, dirigida a SRE y a seguridad | La lectura es excepcional; si la hace el pipeline, lo ve alguien que no es el pipeline |
| Replicación **user-managed** en `europe-west1` | Región y residencia en la UE |
| Tras cualquier uso: re-keying (`bao operator rekey -target=recovery`) y nueva versión del secreto | Un fragmento leído se considera expuesto |

Esto introduce Secret Manager en la plataforma, pero solo para material de **arranque y emergencia** (break-glass). Los secretos de aplicación siguen en OpenBao; la frontera queda escrita para que Secret Manager no se convierta en un segundo almacén de secretos por comodidad.

---

## 5. Especificidades de GCP que afectan a SonarQube

| Tema | Decisión | Referencia |
|---|---|---|
| NEG fuera del estado de Terraform | Declarado como `data`, nombrado explícitamente | §10.2, R20 |
| Shared VPC o VPCs separadas | Sigue abierta en `CLAUDE.md` (nº 2); el backend del GLB debe estar en la misma VPC que el NEG | R23 |
| Cuenta de servicio de nodos | Dedicada, con `artifactregistry.reader`, logging y monitoring writer | §5.7 |
| Workload Identity | Principal exacto por namespace y KSA | R15 |
| Pipeline de plataforma | WIF de GitHub con `attribute_condition` sobre repo y environment exactos | §11.2, R12 |
| Acceso a la API de GKE | Redes autorizadas abiertas por job a través del servicio intermedio | §4.13, R18 |
| Región | `europe-west1` | Contexto (§0) |
| KMS | Key ring `qa` regional en capa 0, sin capability, protegido frente a destrucción | §4.14 |
| Org policies | Sin claves de SA, región confinada, sin IPs públicas en nodos | §11.7 |

---

## 6. Orden de despliegue y ciclos

Como el entorno es nuevo, el despliegue de SonarQube es el despliegue de la plataforma entera. Tres fases, cada una aplicada por etiquetas con mocks OFF (§4.11):

![Orden de despliegue](diagrams/03-orden-despliegue.svg)

| Fase | Stacks | Bloqueada por |
|---|---|---|
| **0** | Repositorio desechable, verificaciones de `CLAUDE.md` | Nada. Hay que hacerla primero |
| **A** | Landing zone, red, GKE | Fase 0; decisión Shared VPC |
| **B** | Gatekeeper, cert-manager, monitorización, OpenBao + ESO, buckets, CNPG, Keycloak, Gateway, borde | A |
| **C** | Los 8 stacks de `gcp-qa-sonarqube-main` | B; V1–V3 |

Aristas nuevas que introduce SonarQube (cada una con su `after`, R2):

| Consumidor | Productor | Qué cruza | Tipo |
|---|---|---|---|
| `…-iam` | `gcp-qa-gke` | `workload_identity_pool` | outputs sharing |
| `…-iam` | `gcp-qa-objects` | Nombre del bucket de backups | global (determinista) |
| `…-secrets` | `gcp-qa-secrets` | Mount kv y rol de Kubernetes auth | global |
| `…-data-tenant` | `gcp-qa-postgres-operator` | Versión del operador | outputs sharing |
| `…-frontdoor` | `gcp-qa-gateway` | Nombre y namespace del `Gateway` | global |
| `…-sso` | `gcp-qa-keycloak` | Realm, URL de metadatos SAML | outputs sharing |
| `…-observability` | `gcp-qa-monitoring` | Selector de reglas | global |

Ciclos y cómo se rompen:

| Ciclo | Ruptura |
|---|---|
| Keycloak ↔ Gateway (R22) | Resuelto en la plataforma; SonarQube tampoco lleva `SecurityPolicy` |
| Keycloak → secretos → OpenBao → login OIDC → Keycloak | Workloads por Kubernetes auth; el login OIDC de personas a OpenBao se añade después |
| OpenBao TLS → cert-manager | No es ciclo: cert-manager usa su CA propia, sin secretos de OpenBao |
| OpenBao → KMS | KMS está en capa 0 |
| Estado cifrado de `gcp-qa-network` → clave `tofu-state` | La clave la crea la landing zone, no el entorno (§4.14) |
| SonarQube SAML ↔ Keycloak | No existe: front-channel |
| Gateway → NEG → `env-edge` (capa 1) | La arista ascendente de §10: `gcp-qa-edge` se aplica tras `gcp-qa-gateway` |

---

## 7. Borradores ilustrativos

No son ficheros del repositorio; muestran la forma de la etapa 2.

```yaml
# archetypes/sonarqube/manifest.yaml — borrador
apiVersion: archetype/v1
kind: Archetype
metadata:
  name: sonarqube
  version: 0.1.0
  layer: 5
  kind: catalog
  description: SonarQube Community Build, single node, SAML contra oidc-idp
  owners: [team-platform]

runtimes: [gke, eks, aks]                     # no gke-autopilot: le falta el trait

requires:
  - capability: cluster
    version: "^2.0.0"
    traits: [sysctl-max-map-count]            # NUEVO
  - capability: policy
    version: "^1.0.0"
  - capability: ingress
    version: ">=3.0.0 <4.0.0"
    traits: [gateway-api, http-route]
  - capability: secrets
    version: "^2.0.0"
  - capability: oidc-idp
    version: "^4.0.0"
    traits: [saml-idp]                        # NUEVO
  - capability: database-platform
    version: "^1.0.0"
    traits: [cnpg]                            # NUEVO
  - capability: object-store
    version: "^1.0.0"
  - capability: monitoring
    version: "^1.5.0"
    traits: [prometheus-operator-crds]        # NUEVO

stacks:
  - name: iam
  - name: secrets
    after: [iam]
  - name: data-tenant
    after: [iam, secrets]
    creates_tenant_resources: [database-platform]
  - name: firewall
    after: [data-tenant]
  - name: app
    after: [secrets, firewall]
  - name: sso
    after: [app]
    creates_tenant_resources: [oidc-idp]
  - name: frontdoor
    after: [app]
  - name: observability
    after: [app]

claims:
  - kind: hostname
    pool: "{{ environment.dns_zone }}"
    value: "sonar.{{ environment.dns_suffix }}"

firewall:
  - name: gateway-to-sonar
    from: zone:pods
    to: self
    ports: [9000]

capacity:
  cpu_millicores: 8000                        # 4000 SonarQube + 2 × 2000 PostgreSQL
  memory_mib: 28672                           # 12 GiB + 2 × 8 GiB
  pvc_gib: 250                                # 50 ES + 2 × 100 PostgreSQL
  ingress_routes: 1
  workload_identities: 2                      # ESO→OpenBao, CNPG→GCS
```

```yaml
# environments/qa/binding.yaml — borrador
apiVersion: archetype/v1
kind: EnvironmentBinding
metadata: { name: qa, model: dedicated, cloud: gcp, region: europe-west1 }
bindings:
  network:             { archetype: environment,          stack_id: gcp-qa-network }
  cluster:             { archetype: gke,                  stack_id: gcp-qa-gke }
  cloud-observability: { archetype: cloud-monitoring-gcp, stack_id: gcp-qa-cloudmon }
  policy:              { archetype: policy-gatekeeper,    stack_id: gcp-qa-policy }
  ingress:             { archetype: gateway-envoy-gke,    stack_id: gcp-qa-gateway }
  certs:               { archetype: cert-manager,         stack_id: gcp-qa-certs }
  secrets:             { archetype: secrets-openbao,      stack_id: gcp-qa-secrets }
  monitoring:          { archetype: monitoring-oss,       stack_id: gcp-qa-monitoring }
  object-store:        { archetype: object-store-gcs,     stack_id: gcp-qa-objects }
  database-platform:   { archetype: postgres-operator,    stack_id: gcp-qa-postgres-operator }  # SÍ en qa
  oidc-idp:            { archetype: keycloak,             stack_id: gcp-qa-keycloak }
  # dns: sin enlazar — wildcard en env-edge
network:
  dns_zone: qa-acme-com
  dns_suffix: qa.acme.com
cluster:
  max_pods_per_node: 64
policy:
  gatekeeper_enforcement: deny
  gatekeeper_failure_policy: Ignore
```

### Cambios propuestos al registro (no aplicados)

Se aplicarán en `registry/*.yaml` (nunca en `schemas/`, R34) al aprobar esta etapa:

| Fichero | Alta | Motivo |
|---|---|---|
| `traits.yaml` · compute | `sysctl-max-map-count` | Sysctl de nodo sin pods privilegiados |
| `traits.yaml` · identity | `saml-idp` | El `oidc-idp` también sirve SAML 2.0 |
| `traits.yaml` · data | `cnpg` | `database-platform` es CloudNativePG y admite `Cluster` como tenant resource |
| `traits.yaml` · observability | `prometheus-operator-crds` | Existen `PodMonitor` / `PrometheusRule` |
| `capabilities.yaml` | *(ninguna)* | KMS y registro se resuelven con globals deterministas de la landing zone (§4.14) |

---

## 8. Decisiones

| # | Decisión | Estado | Recomendación | Alternativa |
|---|---|---|---|---|
| D1 | Backend de secretos | Propuesta | OpenBao + ESO | ESO + Secret Manager |
| D2 | PostgreSQL | Propuesta | `Cluster` CNPG propio | Cloud SQL |
| D3 | Exposición | **Cerrada** | Pública tras GLB + Cloud Armor, sin filtrado por IP; auth en SonarQube | — |
| D4 | Autenticación de personas | **Cerrada en la fuente** (Entra ID); propuesta en el camino | SAML desde Keycloak, que hace broker OIDC hacia Entra ID; grupos por app roles | SAML directo SonarQube ↔ Entra ID: menos piezas, pero rompe la uniformidad del realm `qa` |
| D5 | Runtime | **Cerrada** | GKE Standard | — (Autopilot sin sysctl) |
| D6 | Ramas / PR | Propuesta | Solo `main` | Plugin comunitario de ramas (acoplado a versión); Developer Edition |
| D7 | Logs | Propuesta | Fluent Bit → Loki | Grafana Alloy |
| D8 | Registro de imágenes | **Cerrada** | Artifact Registry | Harbor |
| D9 | Tokens de CI | Propuesta | Token de proyecto por repo, con caducidad, creado por onboarding automatizado | Un token global de análisis como secreto de organización: más simple, pero una fuga da acceso a los 200 proyectos |
| D10 | DNS del entorno | Propuesta | Wildcard + certificado wildcard; `dns` sin enlazar | external-dns por hostname |
| D11 | Acceso del pipeline a GKE | **Cerrada** | Apertura temporal de la IP del runner, con las condiciones de §4.13 | Endpoint DNS del plano de control |
| D12 | Grupos de Entra ID | Propuesta | App roles | Claim `groups` (GUIDs y overage) |

---

## 9. Riesgos nuevos

Propuestos para `docs/risk-register.md`; se numerarán al incorporarse.

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| **Cola del CE saturada** con 200 proyectos | Media-alta | Media — CI lento, jobs esperando el gate | Solo `main`, `cancel-in-progress`, alerta de cola, V4; salida comercial documentada |
| **Análisis lanzado desde una PR** contamina `main` | Alta sin control | Media — historia y gate de `main` incorrectos, en silencio | Workflow reutilizable solo con `push` a `main`; política sobre los workflows |
| **Init container privilegiado del chart** activo | Alta | Media | Valores del arquetipo; sysctl de nodo; trait en resolución |
| **OOMKill silencioso** por heaps que suman más que el límite | Alta sin cálculo | Alta — exit 137 sin log | Heaps explícitos; límite = Σ heaps + margen; alerta |
| **`SecurityPolicy` OIDC añadida a la ruta** por homogeneidad | Media | Alta — todos los análisis fallan | Assertion en el generador; documentado junto a la excepción de Keycloak |
| **Timeout de 30 s del backend service** del GLB | Alta en proyectos grandes | Media — análisis fallan con 502 intermitente | 120 s en `env-edge`; V6 |
| **Pérdida de `sonar-secret.txt`** | Baja | Alta | En OpenBao con snapshot a GCS; en la prueba de DR |
| **Token global filtrado** desde un repo | Media si se elige | Alta | Tokens de proyecto (D9) |
| **Upgrade con migración de BD sin retorno** | Media | Alta | Backup CNPG verificado antes; rollback = restaurar BD + imagen anterior (DG §6) |
| **Caída de la zona** del PVC | Baja | Media | Aceptado en `qa`; disco HA como opción (§4.1) |
| **Carrera en redes autorizadas**: un job borra la IP de otro | Alta sin serializar | Media — `apply` cortado a medias | Grupo de `concurrency` único para la API de GKE (§4.13) |
| **IP de runner olvidada abierta** | Media | Baja — IAM sigue protegiendo | `if: always()` + reconciliador con caducidad de 60 min |
| **`container.clusters.update` en la identidad de preview** | Alta si se hace por la vía directa | Crítico — cualquier PR puede reconfigurar el cluster | Servicio intermedio con permiso mínimo (§4.13) |
| **Usuario dado de baja en Entra ID conserva tokens** en SonarQube | Media | Media | Reconciliación diaria; sin tokens personales en CI |
| **Destrucción de `tofu-state` u `openbao-unseal`** | Baja | Crítico — estado ilegible o todos los secretos perdidos | Sin permisos de destroy en pipelines, `prevent_destroy`, org policy de duración mínima (§4.14) |
| **Caducidad de la credencial de Keycloak en Entra ID** | Media | Alta — nadie puede entrar | Certificado en vez de secreto; alerta 30 días antes de la caducidad, dirigida al equipo de identidad |
| **Raíz de OpenBao alcanzable desde el pipeline** (recovery keys legibles por WIF) | Media si la identidad de despliegue lee | Crítico — todos los secretos de `qa`, auditoría desactivable | Pipeline solo escribe; lectura solo con identidad break-glass aprobada; SRE vía PAM con aprobación; alerta por lectura (§4.14) |

---

## 10. Qué verificar y qué sigue abierto

| # | Verificación | Resultado que la cierra |
|---|---|---|
| V1 | `vm.max_map_count` en `linux_node_config.sysctls` de GKE | Nodo con el valor y SonarQube arrancando sin `initSysctl` |
| V2 | SonarQube con PSS `restricted` y Gatekeeper en `deny` | Pod admitido sin exenciones |
| V3 | SAML en Community con sincronización de grupos | Usuario de Keycloak con su grupo aplicado |
| V4 | Tiempo por tarea del CE con 5–10 proyectos representativos; memoria real de las tres JVM | Capacidad de cola y límites justificados con datos |
| V5 | Restauración CNPG desde GCS a un `Cluster` nuevo | SonarQube arrancando contra la BD restaurada |
| V6 | Análisis grande a través de GLB + Cloud Armor + Gateway | Sin 413, 502 ni bloqueo de WAF |
| V7 | Apertura/cierre de IP con dos workflows simultáneos y un job cancelado | Ningún job pierde acceso a mitad; el reconciliador retira la entrada huérfana |
| V8 | Login Entra ID → Keycloak → SonarQube con app roles | Usuario con su grupo `team-<x>` aplicado; baja en Entra reflejada tras la reconciliación |

Preguntas abiertas:

- **Q10.** Acuerdo con el equipo de identidad, **estimado** a falta de confirmar: app role de equipo en ≤ 2 días laborables; renovación del certificado de Keycloak en la app registration a cargo de identidad, disparada por la alerta de 30 días de la plataforma. El alta de un equipo en SonarQube hereda ese plazo.
- **Q11.** ¿El pipeline necesita **leer** las recovery keys (recuperación automatizada) o solo **escribirlas** en la inicialización? Decide si hace falta la identidad `bao-breakglass-qa@`.
- De `CLAUDE.md`, sigue abierta la nº 2 (Shared VPC), que bloquea la fase A.

---

## 11. Siguiente etapa

Etapa 2: manifiesto real de `sonarqube`, alta de traits en `registry/`, `binding.yaml` de `qa`, valores del chart, contratos de outputs sharing de §6 y el workflow reutilizable de GitHub Actions. La fase 0 y V1–V3 van antes; si V1 falla, cambian §4.1 y el plan B pasa a ser el camino principal.
