# SonarQube Community en el entorno `qa` — Etapa 1: elementos y dependencias

| | |
|---|---|
| **Estado** | Propuesta · etapa 1 de N |
| **Alcance** | Qué elementos necesita SonarQube Community Build en un entorno `qa` completo, de qué depende cada uno y con qué herramienta open source se cubre |
| **Fuera de alcance** | Código (generadores, contratos, charts), sizing definitivo, integración con pipelines de aplicaciones, procedimiento de upgrade. Son etapas posteriores |
| **Especificación de referencia** | `docs/archetype-model.md` (AM §n), `docs/terramate-outputs-sharing-architecture.md` (§n), `docs/risk-register.md` |
| **Diagramas** | `diagrams/*.mmd` (fuente Mermaid) y `diagrams/*.svg` (renderizados). El SVG se regenera desde el `.mmd`; no se edita a mano |

Nada de este documento reabre decisiones de `CLAUDE.md`. Donde SonarQube choca con una de ellas (PSS `restricted`, OIDC en el Gateway, `database-platform`), se dice y se propone cómo encajar sin cambiarla.

---

## 1. Lo que SonarQube Community impone al diseño

Hechos del producto que condicionan todo lo demás. Cada uno se marca con lo que hay que verificar contra la versión que se fije.

| Hecho | Consecuencia en el diseño | Verificar |
|---|---|---|
| **Un solo nodo.** La alta disponibilidad es de Data Center Edition (comercial) | `replicas: 1`, StatefulSet. En `qa` se acepta; el RTO lo marca el reinicio (≈2–5 min) más el reindexado si se pierde el PVC | — |
| **Tres JVM en un contenedor**: web, compute engine y search (Elasticsearch embebido) | El límite de memoria del contenedor debe cubrir **tres heaps más tres non-heap más el mmap de ES**. Es el caso de developer-guide §8.3 multiplicado por tres | Heaps por defecto de la versión fijada |
| **Elasticsearch exige `vm.max_map_count ≥ 524288` y `fs.file-max ≥ 131072`** en el host | El chart lo resuelve con un init container **privilegiado** (`initSysctl`), incompatible con PSS `restricted` y Gatekeeper. Debe resolverse **a nivel de nodo** (§4.1) | Soporte del sysctl en el node pool de cada cloud |
| **Base de datos externa obligatoria** fuera de evaluación. PostgreSQL soportado | Dependencia de `database-platform` (CloudNativePG) | Rango de versiones PostgreSQL soportado |
| **El único estado real es PostgreSQL.** Los índices de ES se reconstruyen desde la BD | Backup solo de PostgreSQL. El PVC de datos no necesita backup; perderlo cuesta un reindexado, no datos | Tiempo de reindexado con el volumen de `qa` |
| **Sin análisis de ramas ni decoración de PR** en Community | Solo rama principal por proyecto. Decisión D6 | — |
| **Autenticación integrada: local, SAML, LDAP, GitHub, GitLab**. OIDC genérico solo con plugin de terceros | Keycloak se integra por **SAML**, no por OIDC (§4.6) | SAML disponible en Community en la versión fijada |
| **Métricas Prometheus en `/api/monitoring/metrics`**, protegidas por passcode o token de sistema | Scrape con cabecera `X-Sonar-Passcode` desde un Secret (§4.7) | — |
| **Logs a stdout** en la imagen de contenedor | Recogida estándar por DaemonSet; sin sidecar | Formato JSON configurable |
| **Plugins desde el update center** por defecto (salida a internet) | Plugins **horneados en la imagen**; egress a internet denegado (§4.8, §4.10) | — |

---

## 2. Dónde encaja en el modelo de arquetipos

| Pregunta | Respuesta | Razón |
|---|---|---|
| ¿Arquetipo o componente? | **Arquetipo `sonarqube`**, `kind: catalog`, **capa 5** | No despliega un operador ni impone contrato multi-tenant a otros arquetipos (AM §5.4). Lo consumen pipelines por HTTP, no stacks por outputs sharing, así que no publica `provides` |
| ¿Modelo de entorno? | `qa` es **dedicado** (§12.1) | Tabla §12.1: `qa` → dedicated. Una instancia de SonarQube por entorno |
| ¿Instancia? | `sonarqube-main` | Stack IDs `<cloud>-qa-sonarqube-main-<stack>` según la convención |
| ¿Runtime? | **Kubernetes** (`gke`, `eks`, `aks`). **No** Cloud Run / Fargate / Container Apps | ES necesita disco persistente con baja latencia y sysctl de host; los runtimes serverless no dan ninguno de los dos |
| ¿Cloud? | **Abierto.** Todo lo de capa 3 hacia arriba es igual en las tres; las diferencias quedan en capas 0–2 y se tabulan en §5 | AM §14.1 |

---

## 3. Inventario de elementos

### 3.1 Vista de contexto

![Contexto](diagrams/01-contexto.svg)

Fuente: [`diagrams/01-contexto.mmd`](diagrams/01-contexto.mmd)

### 3.2 Cierre de dependencias por capas

![Capas y dependencias](diagrams/02-capas-dependencias.svg)

Fuente: [`diagrams/02-capas-dependencias.mmd`](diagrams/02-capas-dependencias.mmd)

### 3.3 Tabla de elementos

Todo lo que SonarQube necesita para funcionar en `qa`, con la herramienta open source propuesta. La columna **Registro** indica si la capability ya existe en `registry/capabilities.yaml`.

| Capa | Capability | Herramienta propuesta | Licencia | Por qué la necesita SonarQube | Registro |
|---|---|---|---|---|---|
| 0 | `dns-zone` | Zona delegada `qa.acme.com` en el DNS cloud | — (cloud) | Hostname `sonar.qa.acme.com`; desafío DNS-01 de cert-manager | ✓ |
| 0 | `cidr-pool` | Ledger del modelo (AM §9) | — | La `/17` de `qa` | ✓ |
| 0 | *(KMS)* | KMS cloud | — (cloud) | Auto-unseal de OpenBao. Única dependencia cloud del plano de secretos | ✗ no es capability — ver §7 |
| 1 | `network` | Arquetipo `environment` | — | VPC/VNet, subredes, NAT, egress controlado | ✓ |
| 1 | `env-edge` | LB cloud del entorno | — (cloud) | Entrada L4/L7 hacia el Gateway | ✓ |
| 1b | `cloud-observability` | Nativo cloud, **reducido** a logs de auditoría | — | No lo consume SonarQube; se mantiene para auditoría del plano de control. La observabilidad de workloads es OSS (capa 3) | ✓ |
| 2 | `cluster` | GKE Standard / EKS / AKS con **node pool dedicado `sonar`** | — | Donde corre; el node pool aporta el sysctl | ✓ (+ trait nuevo) |
| 2b | `policy` | **OPA Gatekeeper** | Apache-2.0 | Admite o rechaza el pod de SonarQube; fuerza PSS `restricted` y etiquetas obligatorias | ✓ |
| 3 | `ingress` | **Envoy Gateway** (Gateway API) | Apache-2.0 | Publicación HTTPS, `HTTPRoute` | ✓ |
| 3 | `certs` | **cert-manager** + ACME (Let's Encrypt) o CA interna | Apache-2.0 | Certificado TLS del listener | ✓ |
| 3 | `dns` | **external-dns** | Apache-2.0 | Registro A/CNAME de `sonar.qa.acme.com` | ✓ |
| 3 | `secrets` | **OpenBao** (fuente de verdad) + **External Secrets Operator** (entrega) | MPL-2.0 / Apache-2.0 | Credenciales de BD, passcode, admin, clave de cifrado, material SAML | ✓ |
| 3 | `monitoring` | **Prometheus Operator** (kube-prometheus-stack), **Alertmanager**, **Grafana**, **Loki**, **Fluent Bit**, **Blackbox exporter** | Apache-2.0 / AGPL-3.0 (Grafana, Loki) | Métricas, logs, alertas, sonda externa | ✓ |
| 4 | `oidc-idp` | **Keycloak**, realm `qa` | Apache-2.0 | Identidad de personas vía **SAML**; grupos → permisos | ✓ (+ trait nuevo) |
| 4 | `database-platform` | **CloudNativePG** | Apache-2.0 | Operador de PostgreSQL; SonarQube crea su propio `Cluster` | ✓ |
| 4 | `object-store` | Bucket cloud (GCS / S3 / Blob) | — (cloud) | Destino de WAL y base backups de CNPG. Fuera del cluster a propósito (§4.9) | ✓ |
| 5 | — | **SonarQube Community Build**, chart oficial `sonarqube/sonarqube` | LGPL-3.0 | La aplicación | — |
| — | *(registro de imágenes)* | **Harbor** como proxy-cache + réplica, o el registro cloud | Apache-2.0 | Imagen propia con plugins horneados, firmada y escaneada | ✗ ver §7 |
| — | *(runners CI)* | **actions-runner-controller** (ARC) self-hosted | Apache-2.0 | Solo si SonarQube no se publica a internet (D3) | ✗ fuera del modelo |
| — | *(escaneo)* | **Trivy** + **cosign** | Apache-2.0 | Escaneo y firma de la imagen propia | — |

Herramientas de la plataforma que no cambian: Terramate, OpenTofu, conftest, Checkov (`CLAUDE.md`).

**Nota de licencias.** Grafana y Loki son AGPL-3.0: sin impacto para uso interno sin modificar, pero conviene que lo valide quien gestione licencias. Se descarta MinIO como object store en cluster: desde 2025 su edición comunitaria dejó de distribuir binarios e imágenes, y en cualquier caso un backup dentro del cluster que protege no es un backup.

---

## 4. Dependencias por dominio

### 4.1 Runtime: cluster y node pool

| Elemento | Propuesta | Motivo |
|---|---|---|
| Node pool dedicado `sonar` | 1–2 nodos, ≥ 4 vCPU / 16 GiB, taint `dedicated=sonar:NoSchedule` | Aísla el sysctl y la presión de memoria de ES del resto de `qa` |
| `vm.max_map_count=524288`, `fs.file-max=131072` | **Configuración de nodo** del node pool, gestionada por el stack de cluster | Elimina el init container privilegiado; PSS `restricted` se mantiene sin excepción |
| StorageClass | SSD, `WaitForFirstConsumer`, `allowVolumeExpansion: true` | Latencia de ES; el PVC debe nacer en la zona del nodo |
| PVC de datos | 30 GiB inicial, expandible | Índices de ES; reconstruibles |

Cómo se fija el sysctl en cada cloud:

| Cloud | Mecanismo | Estado |
|---|---|---|
| GKE Standard | `node_config.linux_node_config.sysctls` | **Verificar** que la versión de GKE admite `vm.max_map_count` en la lista permitida |
| GKE Autopilot | Sin control de nodo | **Probablemente inviable** sin el init privilegiado → trait ausente, falla la resolución (ver abajo). Liga con la pregunta abierta nº1 de `CLAUDE.md` |
| EKS | Launch template (`user_data`) o settings de Bottlerocket | Soportado |
| AKS | `linux_os_config.sysctl_config.vm_max_map_count` | Soportado |

Esto es exactamente para lo que existen los traits: se propone el trait **`sysctl-max-map-count`** en la capability `cluster`. El arquetipo `sonarqube` lo exige; un `qa` enlazado a Autopilot falla en resolución con un diagnóstico claro, no en el primer arranque con `max virtual memory areas vm.max_map_count [65530] is too low`.

**Plan B**, solo si el sysctl no se puede fijar: `SONAR_SEARCH_JAVAADDITIONALOPTS=-Dnode.store.allow_mmap=false`. Evita el requisito a costa de rendimiento de ES. Aceptable en `qa`, a medir.

### 4.2 Política de admisión (capa 2b)

`qa` usa `enforcementAction: deny`, `failurePolicy: Ignore` (§13.7). Lo que implica para el chart:

![Pod de SonarQube](diagrams/08-pod-sonarqube.svg)

| Requisito PSS `restricted` / Gatekeeper | Ajuste en el chart |
|---|---|
| Sin contenedores privilegiados | `initSysctl.enabled: false` (lo cubre el nodo, §4.1) |
| Sin ejecución como root | `initFs.enabled: false`; permisos del volumen vía `fsGroup` |
| `runAsNonRoot`, `seccompProfile: RuntimeDefault`, `capabilities.drop: [ALL]`, `allowPrivilegeEscalation: false` | `securityContext` y `containerSecurityContext` explícitos |
| Etiquetas obligatorias (`registry/labels.yaml`) | Emitidas por el generador en namespace y workload: `archetype`, `instance`, `app.kubernetes.io/*`, `pod-security.kubernetes.io/enforce: restricted` |
| `readOnlyRootFilesystem` (si hay constraint) | `emptyDir` en `/opt/sonarqube/temp` y `/opt/sonarqube/logs`; **verificar** qué más escribe la versión fijada |
| Imágenes solo de registros permitidos | Imagen propia en el registro interno (§4.10) |

Si la verificación muestra que SonarQube no puede correr con raíz de solo lectura, la salida es una **exención por nombre** del constraint para `sonarqube/sonarqube-0`, registrada en el binding y revisada en PR — nunca relajar el constraint para todo `qa`.

### 4.3 Secretos

![Flujo de secretos](diagrams/04-secretos.svg)

| Secreto | Ruta en OpenBao | Consumidor | Notas |
|---|---|---|---|
| Usuario y password JDBC | `qa/sonarqube/db` | CNPG (`bootstrap.initdb.secret`) y SonarQube (`SONAR_JDBC_*`) | Un único origen para ambos lados; CNPG no genera la suya |
| Monitoring passcode | `qa/sonarqube/passcode` | SonarQube (`SONAR_WEB_SYSTEMPASSCODE`) y `PodMonitor` | El `PodMonitor` debe estar en el mismo namespace que el Secret |
| Password admin inicial | `qa/sonarqube/admin` | Job del chart que cambia `admin/admin` | Tras SAML, la cuenta local `admin` queda como break-glass |
| Clave de cifrado de settings | `qa/sonarqube/secret-key` | `sonar.secretKeyPath` montado | Si se pierde, los settings cifrados de la BD son irrecuperables: **incluirla en el plan de DR** |
| Material SAML | `qa/sonarqube/saml` | Certificado del IdP; clave y certificado del SP si se firman las peticiones | El certificado del IdP es público; la clave del SP no |
| Tokens de análisis de CI | No en OpenBao de `qa` | Secretos del sistema de CI, uno por proyecto | Tokens de proyecto con caducidad; nunca un token global |

Decisiones en este dominio:

- **ESO siempre como interfaz**; el backend es intercambiable. OpenBao es la opción 100 % OSS; Secret Manager / Secrets Manager / Key Vault (AM §14.2) entran cambiando el `SecretStore`, sin tocar el arquetipo.
- **`SecretStore` por namespace, no `ClusterSecretStore`.** El rol de OpenBao queda ligado a `ns=sonarqube, sa=eso-sonarqube` con `StringEquals` literal. El equivalente en Kubernetes auth de la regla R15: nada de comodines.
- **Autenticación de workloads a OpenBao por Kubernetes auth**, no por OIDC de Keycloak. Si no, aparece el ciclo Keycloak → secretos → OpenBao → login → Keycloak (§6).
- **Por outputs sharing solo viajan rutas** (`qa/sonarqube/db`), nunca valores (§11.6, R8).

### 4.4 Datos: PostgreSQL con CloudNativePG

`CLAUDE.md` deja `database-platform` **sin enlazar en `demos`** por aislamiento. En `qa` se propone **enlazarlo** a `postgres-operator` (CloudNativePG): `qa` es un entorno dedicado de cargas de confianza, y un operador compartido evita un Cloud SQL / RDS por aplicación sin perder aislamiento, porque:

| Opción | Qué crea SonarQube | Aislamiento | Recomendación |
|---|---|---|---|
| A. `Database` + `Role` en un `Cluster` CNPG compartido | Una BD lógica | Proceso PostgreSQL compartido con otras apps | No: SonarQube es intensivo en BD y un vecino ruidoso afecta a ambos |
| **B. `Cluster` CNPG propio en el namespace `sonarqube`** | Instancia PostgreSQL dedicada gestionada por el operador compartido | Proceso, almacenamiento y backups propios | **Sí**: operador compartido, datos separados — la misma idea que Kafka (bus común, datos separados) |
| C. Servicio gestionado cloud (`data` condicional) | Cloud SQL / RDS / Flexible Server | Máximo | Solo si se abandona el requisito de OSS |

La opción B requiere que `postgres-operator` autorice el tipo `Cluster` (y `ScheduledBackup`) en `tenant_resources` además de `Database` y `Role` (AM §10.4). Es un cambio del manifiesto de `postgres-operator`, no del modelo.

Parámetros de partida: 2 instancias (primaria + réplica síncrona) en nodos distintos, 20 GiB, PostgreSQL en la versión mayor más alta que soporte la versión fijada de SonarQube, `backup_retention_days: 14` (§12.6, columna `qa`).

### 4.5 Publicación

| Elemento | Propuesta |
|---|---|
| Hostname | `sonar.qa.acme.com` — **claim** de hostname en el ledger (AM §8.1) |
| DNS | external-dns crea el registro desde el `HTTPRoute` |
| TLS | cert-manager, `Certificate` en el listener HTTPS del Gateway del entorno. DNS-01 contra la zona de capa 0 con identidad de workload, sin claves |
| Gateway | **Uno por entorno**, `allowedRoutes.namespaces.from: Selector` (§10.6). SonarQube solo aporta su `HTTPRoute` |
| Borde cloud | El `env-edge` de capa 1 (NEG / target group / AGFC según cloud, §10) |
| Tamaño de subida | `ClientTrafficPolicy` con límite de cuerpo ≥ 50 MiB: los informes del scanner de proyectos grandes superan los límites por defecto |
| Timeouts | `BackendTrafficPolicy` con timeout de petición ≥ 60 s para `/api/ce/submit` |
| WAF | El `waf` de capa 0 si la exposición es pública (D3) |

Recursos Gateway API empaquetados en el chart del arquetipo y desplegados con `helm_release`, **nunca `kubernetes_manifest`** (R24).

### 4.6 Autenticación y autorización

![Autenticación](diagrams/05-autenticacion.svg)

El choque con el diseño existente: la plataforma prevé OIDC en el Gateway mediante `SecurityPolicy`. **No sirve para SonarQube**, porque la misma ruta la usan personas y máquinas: el scanner envía `Authorization: Bearer <token de SonarQube>` a `/api/*`, y una `SecurityPolicy` OIDC en la ruta lo redirigiría a Keycloak. Partir la ruta por paths (UI con OIDC, `/api` sin él) duplica la autenticación y deja la API igualmente expuesta.

| Quién | Mecanismo | Dónde se valida |
|---|---|---|
| Personas | **SAML 2.0** SP-initiated contra Keycloak (realm `qa`, cliente `sonarqube`) | SonarQube |
| Pipelines | **Token de análisis de proyecto** de SonarQube | SonarQube |
| Break-glass | Cuenta local `admin`, password en OpenBao | SonarQube |
| Anónimos | Prohibidos: `sonar.forceAuthentication=true` | SonarQube |

Propuesta: `HTTPRoute` de SonarQube **sin `SecurityPolicy` OIDC**, igual que la de Keycloak; la autenticación es responsabilidad de la aplicación. Controles que sí se aplican en el Gateway: rate limit local y, si D3 lo decide, lista de IPs de origen.

Una ventaja de SAML: el intercambio es **front-channel** (vía navegador). SonarQube no necesita conectividad de red con Keycloak; basta con el certificado del IdP. Sin dependencia de arranque entre ambos.

Autorización:

| Grupo en Keycloak | Grupo en SonarQube | Permisos |
|---|---|---|
| `sonar-administrators` | `sonar-administrators` | Administración global |
| `sonar-users` | `sonar-users` | Navegar y ver proyectos |
| `team-<x>` | `team-<x>` | Plantilla de permisos por prefijo de clave de proyecto `<x>-*` |

Sincronización de grupos por el atributo `groups` de la aserción SAML. Los permisos por proyecto se definen con **plantillas de permisos**, no a mano, para que un proyecto nuevo nazca con los permisos de su equipo.

### 4.7 Observabilidad

![Observabilidad](diagrams/06-observabilidad.svg)

| Señal | Origen | Recogida | Alertas propuestas |
|---|---|---|---|
| Salud | `/api/system/health` (requiere passcode), `/api/system/status` (público) | Blackbox exporter desde fuera del namespace a través del Gateway | Status ≠ `UP` durante 5 min |
| Métricas de aplicación | `/api/monitoring/metrics` | `PodMonitor` con passcode desde Secret | Cola del compute engine creciendo durante 30 min; tareas fallidas; ES en rojo |
| JVM | Métricas JVM del mismo endpoint | Idem | Heap > 90 % sostenido; tiempo de GC |
| Contenedor | cAdvisor / kube-state-metrics | kube-prometheus-stack | Reinicios con `OOMKilled` (exit 137, §8.3); memoria > 90 % del límite |
| Disco | kubelet volume stats | kube-prometheus-stack | PVC de datos > 80 % (ES pasa a solo lectura por encima de su watermark) |
| PostgreSQL | Exporter de CNPG `:9187` | `PodMonitor` de CNPG | Retraso de réplica; conexiones cerca del máximo; último backup correcto > 26 h |
| Logs | stdout de los tres procesos | Fluent Bit → Loki | Tasa de `ERROR` |
| Certificado | cert-manager | kube-prometheus-stack | Caducidad < 14 días |

Grafana usa login OIDC con Keycloak: no hay problema de ciclo, porque Grafana está detrás del Gateway como cualquier aplicación y Keycloak no depende de ella.

El `PodMonitor` y la `PrometheusRule` se empaquetan en el chart del arquetipo (el CRD debe existir en plan; R24). Por eso `sonarqube` exige `monitoring` con un trait que asegure los CRD de Prometheus Operator — se propone **`prometheus-operator-crds`**.

### 4.8 Red

![Red](diagrams/07-red.svg)

`NetworkPolicy` **default-deny de entrada y de salida** en `sonarqube`, más permisos explícitos:

| Origen | Destino | Puerto | Motivo |
|---|---|---|---|
| Envoy (ns `envoy-gateway-system`) | SonarQube | 9000 | Tráfico de usuarios y CI |
| Prometheus (ns `monitoring`) | SonarQube | 9000 | Métricas |
| Prometheus | Pods CNPG | 9187 | Métricas de PostgreSQL |
| SonarQube | Pods CNPG | 5432 | JDBC |
| Pods CNPG | Pods CNPG | 5432 | Replicación |
| Operador CNPG (ns `cnpg-system`) | Pods CNPG | 8000 | Estado de instancias |
| Pods CNPG | Bucket de backups | 443 | WAL y base backups — private endpoint si la cloud lo permite |
| Todos | CoreDNS | 53 | Resolución |
| SonarQube | Internet | — | **Denegado.** Plugins en la imagen; `sonar.updatecenter.activate=false` |

Selectores de workload, no CIDR, conforme a AM §6.3. SonarQube no necesita hablar con Keycloak (SAML front-channel).

### 4.9 Backup y recuperación

| Qué | Cómo | Dónde | Retención |
|---|---|---|---|
| PostgreSQL | CNPG barman-cloud: base backup diario + archivo continuo de WAL (PITR) | Bucket cloud del entorno, acceso por identidad de workload, sin claves | 14 días |
| Clave de cifrado de settings | En OpenBao, que a su vez hace snapshot Raft | Bucket separado | Igual que OpenBao |
| Índices de ES | **No se respaldan** | — | Reconstrucción al arrancar |
| Configuración | En Git (valores del chart, manifiesto) | Repositorio | — |

Velero no es necesario: todo el estado está en PostgreSQL, OpenBao o Git. Añadirlo sería un segundo mecanismo que respalda lo mismo.

Prueba de restauración: CNPG puede crear un `Cluster` nuevo en recuperación desde el bucket. Debe ensayarse una vez antes de dar el entorno por bueno; un backup nunca restaurado es una hipótesis.

### 4.10 Cadena de suministro de la imagen

| Paso | Herramienta |
|---|---|
| Imagen propia `FROM sonarqube:<versión>-community` + plugins en `extensions/plugins` | Build del repositorio del arquetipo |
| Escaneo | Trivy, bloqueante en `CRITICAL` con fix disponible |
| Firma | cosign; la verificación en admisión es una mejora posterior |
| Registro | Harbor (proxy-cache de Docker Hub + proyecto interno) o el registro cloud |
| Despliegue | **Por digest**, no por tag (developer-guide: la imagen se promueve, no se reconstruye) |

---

## 5. Diferencias por cloud (solo capas 0–2)

| Elemento | GCP | AWS | Azure |
|---|---|---|---|
| Runtime | GKE **Standard** (no Autopilot, §4.1) | EKS | AKS |
| Sysctl de nodo | `linux_node_config.sysctls` — verificar | Launch template / Bottlerocket | `linux_os_config` |
| StorageClass SSD | `pd-ssd` / `hyperdisk-balanced` | `gp3` | `managed-csi-premium` |
| Bucket de backups | GCS + Workload Identity | S3 + IRSA (`StringEquals` exacto, R12) | Blob + Workload Identity |
| Auto-unseal OpenBao | Cloud KMS | AWS KMS | Key Vault |
| DNS-01 cert-manager / external-dns | Cloud DNS + WI | Route 53 + IRSA | Azure DNS + WI |
| Borde | NEG standalone (sin `iac-owned-edge`, R20) | Target group + `TargetGroupBinding` | AGFC |

Nada por encima de capa 2 cambia entre columnas. Esa es la prueba de aceptación de AM §14.3 aplicada a este caso.

---

## 6. Orden de despliegue y ciclos

![Orden de despliegue](diagrams/03-orden-despliegue.svg)

Cada flecha entre stacks que cruce outputs sharing necesita su `after` (R2). Las aristas nuevas que introduce SonarQube:

| Consumidor (stack) | Productor | Qué cruza | Tipo |
|---|---|---|---|
| `sonarqube-main-iam` | `qa-cluster` | Pool / proveedor OIDC de identidad de workload | outputs sharing |
| `sonarqube-main-secrets` | `qa-secrets` | Nombre del mount kv y del rol de Kubernetes auth | global (determinista) |
| `sonarqube-main-data-tenant` | `qa-postgres-operator` | Versión del operador, nombre del bucket de backups | outputs sharing |
| `sonarqube-main-frontdoor` | `qa-gateway` | Nombre y namespace del `Gateway` | global (determinista) |
| `sonarqube-main-sso` | `qa-keycloak` | Nombre del realm, URL de metadatos SAML | outputs sharing |
| `sonarqube-main-observability` | `qa-monitoring` | Selector de reglas de Prometheus | global |

Siguiendo el árbol de decisión de platform-overview §4, todo lo derivable de la identidad (namespace, nombre del Gateway, ruta kv) es global; outputs sharing solo para lo que no se conoce antes de un apply.

Ciclos identificados y cómo se rompen:

| Ciclo | Ruptura |
|---|---|
| Keycloak ↔ Gateway (R22) | Ya resuelto en la plataforma. SonarQube no lo agrava: su ruta tampoco lleva `SecurityPolicy` |
| Keycloak → secretos → OpenBao → login OIDC → Keycloak | Workloads se autentican en OpenBao por **Kubernetes auth**. El login OIDC de personas a OpenBao se añade después y no es camino de arranque |
| OpenBao → auto-unseal → KMS | No es un ciclo: KMS es de capa 0 |
| Keycloak → PostgreSQL (CNPG) → secretos | Orden lineal: secretos → operador → Keycloak |
| SonarQube SAML ↔ Keycloak | No existe: SAML es front-channel. El stack `sso` va después de `app` solo para registrar el cliente con la URL definitiva |

---

## 7. Borradores ilustrativos

No son ficheros del repositorio; muestran cómo quedaría la etapa 2.

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

runtimes: [gke, eks, aks]                     # no gke-autopilot: falta el trait

requires:
  - capability: cluster
    version: "^2.0.0"
    traits: [sysctl-max-map-count]            # NUEVO
  - capability: policy
    version: "^1.0.0"
  - capability: ingress
    version: ">=3.0.0 <4.0.0"
    traits: [gateway-api, http-route]
  - capability: certs
    version: "^1.0.0"
  - capability: dns
    version: "^1.0.0"
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
    creates_tenant_resources: [oidc-idp]      # KeycloakClient
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
  cpu_millicores: 4000
  memory_mib: 10240                           # SonarQube 6 GiB + 2 × PostgreSQL 2 GiB
  pvc_gib: 70                                 # 30 ES + 2 × 20 PostgreSQL
  ingress_routes: 1
  workload_identities: 2                      # ESO→OpenBao, CNPG→bucket
```

```yaml
# environments/qa/binding.yaml — borrador, solo las capabilities que SonarQube cierra
metadata: { name: qa, model: dedicated, cloud: <por decidir> }
bindings:
  network:           { archetype: environment,        stack_id: <cloud>-qa-network }
  cluster:           { archetype: <gke|eks|aks>,      stack_id: <cloud>-qa-cluster }
  policy:            { archetype: policy-gatekeeper,  stack_id: <cloud>-qa-policy }
  ingress:           { archetype: gateway-envoy-<rt>, stack_id: <cloud>-qa-gateway }
  certs:             { archetype: cert-manager,       stack_id: <cloud>-qa-certs }
  dns:               { archetype: external-dns,       stack_id: <cloud>-qa-dns }
  secrets:           { archetype: secrets-openbao,    stack_id: <cloud>-qa-secrets }
  monitoring:        { archetype: monitoring-oss,     stack_id: <cloud>-qa-monitoring }
  oidc-idp:          { archetype: keycloak,           stack_id: <cloud>-qa-keycloak }
  database-platform: { archetype: postgres-operator,  stack_id: <cloud>-qa-postgres-operator }  # SÍ enlazado en qa
  object-store:      { archetype: object-store-<cloud>, stack_id: <cloud>-qa-objects }
policy:
  gatekeeper_enforcement: deny
  gatekeeper_failure_policy: Ignore
```

### Cambios propuestos al registro (no aplicados)

Se aplicarán en `registry/*.yaml` (nunca en `schemas/`, R34) cuando se apruebe esta etapa:

| Fichero | Alta | Motivo |
|---|---|---|
| `traits.yaml` · compute | `sysctl-max-map-count` | El runtime permite fijar el sysctl a nivel de nodo sin pods privilegiados |
| `traits.yaml` · identity | `saml-idp` | El `oidc-idp` también sirve SAML 2.0 |
| `traits.yaml` · data | `cnpg` | El `database-platform` es CloudNativePG y admite `Cluster` como tenant resource |
| `traits.yaml` · observability | `prometheus-operator-crds` | Existen los CRD `PodMonitor` / `PrometheusRule` |
| `capabilities.yaml` | *(ninguna)* | KMS y registro de imágenes se modelan dentro de `landing-zone` de momento; decidir si merecen capability (Q5) |

---

## 8. Decisiones propuestas

| # | Decisión | Recomendación | Alternativa | Qué la zanja |
|---|---|---|---|---|
| D1 | Backend de secretos | **OpenBao + ESO** | ESO + gestor cloud | Coste operativo de OpenBao (unseal, Raft, upgrades) frente al requisito de OSS |
| D2 | PostgreSQL | **`Cluster` CNPG propio** (opción B, §4.4) | BD lógica en cluster compartido; servicio gestionado | — |
| D3 | Exposición | **Solo red interna** + runners self-hosted (ARC) si hay acceso corporativo a la red de `qa`; si no, pública con WAF y rate limit | Pública con lista de IPs de GitHub (rangos enormes, poco útil) | Dónde corren los runners (liga con R18) |
| D4 | Autenticación de personas | **SAML contra Keycloak** | Plugin OIDC de terceros; `SecurityPolicy` OIDC en el Gateway | — (el Gateway rompe el scanner, §4.6) |
| D5 | Runtime en GCP | **GKE Standard** | Autopilot con `allow_mmap=false` | Verificación del sysctl (§4.1) |
| D6 | Análisis de ramas / PR | **Solo rama principal** (Community) | Plugin comunitario de branches (acoplado a cada versión, bloquea upgrades); Developer Edition (comercial) | Si los equipos necesitan quality gate en PR |
| D7 | Logs | **Fluent Bit → Loki** | Grafana Alloy (unifica logs y métricas) | Si la plataforma quiere un único agente |

---

## 9. Riesgos nuevos

Propuestos para `docs/risk-register.md`; se numerarán al incorporarse.

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| **Init container privilegiado del chart** activo por defecto; Gatekeeper lo rechaza y el pod no arranca, o alguien pide una exención global | Alta | Media | `initSysctl`/`initFs` desactivados en los valores del arquetipo; sysctl de nodo; trait en resolución |
| **OOMKill silencioso**: tres heaps que suman más que el límite | Alta sin cálculo | Alta — exit 137 sin log | Heaps explícitos por proceso; límite = Σ heaps + ≥ 1,5 GiB; alerta de `OOMKilled` |
| **Pérdida de `sonar-secret.txt`** | Baja | Alta — settings cifrados irrecuperables | En OpenBao, con snapshot Raft; incluida en la prueba de DR |
| **`SecurityPolicy` OIDC añadida a la ruta** por homogeneidad con otras apps | Media | Alta — todos los análisis de CI fallan | Assertion en el generador: `sonarqube` no lleva `SecurityPolicy`; documentado junto a la excepción de Keycloak |
| **Upgrade de SonarQube con migración de BD sin retorno** | Media | Alta | Backup CNPG verificado antes de cada upgrade; rollback = restaurar BD + imagen anterior (developer-guide §6). Se detalla en una etapa posterior |
| **PVC de ES lleno** → índices en solo lectura | Media | Media | Alerta al 80 %; `allowVolumeExpansion` |
| **Tokens de análisis globales** filtrados desde CI | Media | Media | Solo tokens de proyecto, con caducidad |

---

## 10. Qué verificar antes de la etapa 2

| # | Verificación | Resultado que la cierra |
|---|---|---|
| V1 | `vm.max_map_count` configurable en el node pool de la cloud elegida | Nodo con el valor aplicado y SonarQube arrancando sin `initSysctl` |
| V2 | SonarQube con PSS `restricted` y, si aplica, `readOnlyRootFilesystem` | Pod admitido por Gatekeeper en `deny` sin exenciones |
| V3 | SAML disponible en Community en la versión fijada, con sincronización de grupos | Login de un usuario de Keycloak con su grupo aplicado |
| V4 | Consumo real de memoria de los tres procesos con el volumen de proyectos de `qa` | Límite de memoria justificado con datos, no con la tabla por defecto |
| V5 | Restauración de CNPG desde el bucket a un `Cluster` nuevo | SonarQube arrancando contra la BD restaurada y reindexando |
| V6 | Scanner contra `/api/ce/submit` a través del Gateway con un informe grande | Sin 413 ni timeout |

Preguntas abiertas:

- **Q1.** ¿Qué cloud tiene `qa`? Condiciona solo capas 0–2 y la tabla de §5.
- **Q2.** ¿Dónde corren los runners que analizan? Decide D3.
- **Q3.** ¿Cuántos proyectos y líneas de código se esperan? Dimensiona CPU, memoria, PVC y BD.
- **Q4.** ¿`qa` ya tiene, o tendrá, Keycloak y CNPG por otras aplicaciones? Si SonarQube es el primer consumidor, arrastra su despliegue completo.
- **Q5.** ¿KMS y registro de imágenes merecen capability propia en el registro, o se quedan como parte de `landing-zone`?

---

## 11. Siguiente etapa

Etapa 2, cuando esta se apruebe: manifiesto real de `sonarqube`, alta de traits en `registry/`, `binding.yaml` de `qa`, valores del chart y contratos de outputs sharing de las aristas de §6. Las verificaciones V1–V3 van antes; si V1 falla en la cloud elegida, cambia D5 y parte de §4.1.
