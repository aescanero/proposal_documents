# Glosario

Términos técnicos y definiciones extraídos de `platform-overview.md`, `archetype-model.md`, `terramate-outputs-sharing-architecture.md`, `developer-guide.md` y `risk-register.md`. Las propuestas de `proposals/` no están cubiertas. Organizado por el área de la plataforma a la que pertenece cada término, siguiendo el orden de lectura de `platform-overview.md` §16. Las definiciones se toman de los documentos fuente, o los siguen de cerca — este fichero no añade ninguna decisión nueva.

---

## 1. Resolve — conceptos centrales (`archetype-model.md`)

| Término | Definición |
|---|---|
| **Arquetipo** | Una unidad que despliega un operador o servicio compartido que otros consumen e impone un contrato multi-tenant — O, en el sentido general de empaquetado, la unidad de composición de la plataforma: un conjunto de stacks de Terramate con un manifiesto que declara qué requiere, qué provee, con qué entra en conflicto, qué posee y qué reclama. |
| **Componente** | Una instancia dedicada dentro de un arquetipo que lo usa, sin contrato con nadie más; una plantilla de stack parametrizada y reutilizable (chart, claims, reglas de firewall, integración de secretos ya resuelta) que se selecciona y configura con valores en vez de escribirse desde cero. La misma tecnología puede ser arquetipo y componente a la vez (`postgres-operator` frente a `component/postgres`) — no es una inconsistencia. |
| **Capability** | Un nombre virtual (p. ej. `cluster`, `ingress`, `oidc-idp`, `database-platform`) del que depende una aplicación en vez de depender de un arquetipo concreto. Exactamente un proveedor satisface una capability por entorno, decidido por el binding del entorno, de modo que los manifiestos de aplicación no necesitan cambiar cuando cambia la implementación. |
| **Proveedor** (de una capability) | La instancia de arquetipo concreta y desplegada que satisface una capability en un entorno. A diferencia de apt/rpm, los proveedores son instancias desplegadas concretas, no builds de paquete intercambiables. |
| **Trait** | Una etiqueta de vocabulario controlado que expresa una propiedad que las restricciones de versión no pueden expresar ("este agente de monitorización no puede correr en Autopilot"), convirtiendo un fallo en tiempo de ejecución en un fallo de validación en tiempo de resolución. Un trait no registrado es un error de resolución. |
| **Manifiesto** (`manifest.yaml`) | Un fichero por arquetipo (`component.yaml` para un componente) que declara metadata, `requires`/`provides`/`conflicts`, runtimes, stacks, claims, firewall, capacity y providers. Lo leen tanto el resolver como Terramate (`tm_yamldecode(tm_file(...))`). |
| **Resolver** (`archetypectl resolve`) | Calcula el cierre transitivo, valida versiones/traits, asigna claims desde pools jerárquicos y emite un plan ordenado antes de generar ningún código. Se ejecuta antes de `terramate generate`, falla de forma cerrada y nunca retrocede — exactamente un proveedor por capability por entorno hace que la resolución sea lineal, no NP-completa. |
| **Ledger** (`PoolLedger`) | Un fichero JSON committeado en Git que registra cada asignación de recursos (zonas, claims activos y en cuarentena); la fuente de verdad de lo que está ocupado. Un conflicto de merge sobre el fichero del ledger es el bloqueo de control de concurrencia. |
| **Catálogo de componentes** | El conjunto de plantillas de componentes reutilizables que hace que componer un arquetipo nuevo sea selección, no autoría de infraestructura — "veinte minutos en vez de un día." |
| **CMDB** (base de datos de gestión de configuración) | Un sistema de registro derivado, de tres niveles, construido a partir de ficheros de Git (nivel 0), un modelo de lectura publicado (nivel 1) y un modelo analítico DuckDB (nivel 2), con una base de datos de grafos opcional (nivel 3). Una CMDB de inventario, no de gestión de cambios. Ver §5 más abajo. |
| **Binding / binding de entorno** (`binding.yaml`) | Nombra qué instancia concreta de arquetipo satisface cada capability en un entorno dado, más los ajustes de red/cluster/capacity/policy; lo bastante pequeño para revisarlo entero y validado por esquema como cualquier manifiesto. |
| **`binding.tm.hcl`** | El fichero de globals de Terramate generado que es **la costura** entre la mitad Resolve y la mitad Generate del sistema. El resolver lo escribe; los generadores lo consumen; ninguno conoce los internos del otro. Nunca se edita a mano. |
| **Resolución** | El algoritmo de 17 pasos (Cargar → Grafo → Validar → Asignar → Emitir) que valida una composición propuesta y asigna recursos antes de generar código. Ver §6 más abajo. |
| **`resolution.json`** | La salida emitida de la resolución: cierre, proveedores enlazados, stacks, claims, tenant resources, uso de capacity, orden de aplicación, `skipped_stacks` y avisos. |
| **Claim** | Un recurso finito e indivisible, único dentro de un ámbito, reservado a través del ledger (CIDR, hostname, IP estática). La asignación debe ser idempotente, con clave `(pool, owner, purpose)`. |
| **Capacity** | Una cantidad divisible con un total conocido, controlada como un presupuesto **sin** ledger (`kafka_partitions`, `db_connections`, `workload_identities`, `managed_db_instances`). Se hace cumplir sumando el consumo de los tenants activos contra un presupuesto de entorno. |
| **Determinista (global)** | Un valor derivable sin colisión a partir de la identidad de la instancia más una convención (namespace, log group, nombre de rol IAM, prefijo de topic de Kafka); no se registra en ningún ledger porque hacerlo "añade contención para nada." |
| **Idempotencia (resolución)** | Una repetición de la resolución (p. ej. tras un apply fallido) no debe consumir recursos nuevos; se logra mediante la clave `(pool, owner, purpose)`, que devuelve la asignación existente en vez de asignar de nuevo. Cinco reintentos de un despliegue fallido no deben quemar cinco rangos de pods. |
| **Cuarentena** | Un estado de enfriamiento por el que pasa un claim liberado antes de volver a estar disponible (7 días para rangos CIDR, 0 para hostnames), porque rutas, peerings, reglas de firewall y cachés de DNS sobreviven a un `tofu destroy`. |
| **Cierre transitivo** | El conjunto completo de capabilities/arquetipos que arrastra una aplicación una vez se siguen las dependencias de cada dependencia — p. ej. una aplicación que declara 6 capabilities puede resolver a 15 arquetipos. |
| **Kind** | El discriminador de tipo de manifiesto/documento: `kind: Archetype`, `kind: Component`, `kind: EnvironmentBinding`, `kind: PoolLedger`; también `metadata.kind`, que distingue arquetipos `catalog` de `demo`. |
| **`kind: catalog`** | Escrito por el equipo de plataforma, de vida larga (años), muchas instancias, semver estricto, puede publicar `provides`, puede apuntar a las capas 0–3, revisión completa. |
| **`kind: demo`** | Escrito por la oficina de proyecto (revisión ligera), de vida corta (semanas), una instancia, versionado `0.x` sin garantías, solo hoja (no puede publicar `provides`), restringido a la capa 5, requiere `expiresOn`, revisión más ligera (solo esquema + política + presupuesto). |
| **Pool** | Un depósito jerárquico y acotado de un recurso finito (espacio de direcciones, hostnames) del que se asignan claims — p. ej. el pool global `/8` en la capa 0, subdividido en pools de entorno en la capa 1, y luego en zonas de propósito. |
| **Entorno** | Una instancia de arquetipo de capa 1 (`prod`, `qa`, `dev`, `demos`, `ephemeral-*`) que reclama una `/17` (o `/16` para `prod`) del pool global y provee `network`, `env-edge`, `cidr-pool`, `psa-range` a lo que aloja. |
| **Entorno `demos`** | Un entorno compartido (no efímero por demo) — Kafka como bus común justifica compartirlo — donde `database-platform` se deja deliberadamente **sin enlazar** para que cada tenant de demo obtenga su propia instancia de base de datos gestionada dedicada. El aislamiento, no el coste, es el criterio. |
| **Instancia** | Un despliegue concreto de un arquetipo (p. ej. `demos-alpha`), identificado en la CMDB por versiones, claims, stacks y caducidad. |
| **Patrón consumidor/productor (tenant resource)** | Un arquetipo consumidor escribe objetos (p. ej. `KafkaTopic`) directamente en el namespace de un arquetipo productor/proveedor, en vez de limitarse a leer sus salidas; declarado en ambos lados vía `creates_tenant_resources` y `tenant_resources`. |

---

## 2. Capas de arquetipos

| Capa | Nombre | Provee / reclama |
|---|---|---|
| **0** | landing-zone | Singleton por cuenta cloud. Posee hub, dns-zone, cert, waf, cidr-pool, edge-ip. Ciclo de vida: años. |
| **1** | environment | Uno por entorno. Reclama una `/17`/`/16`; provee `network`, `env-edge`, `cidr-pool`, `psa-range`. |
| **1b** | cloud-monitoring | Paralela a la capa 2, ligada al *entorno* (no a un cluster) porque la monitorización nativa de la cloud tiene alcance de entorno; provee `cloud-observability`. Precedente citado para la capa 2b. |
| **2** | runtime | Un runtime por entorno (`gke`, `gke-autopilot`, `eks`, `aks`, `cloudrun`, `fargate`); reclama subred de nodos + rango de pods; provee `cluster` o `serverless-runtime`. |
| **2b** | policy | `policy-gatekeeper`, uno por cluster de Kubernetes. Debe preceder a todo lo que gobierna (control de admisión), incluida la capa 3, así que se sitúa entre las capas 2 y 3. Solo runtimes de Kubernetes; provee `policy`. |
| **3** | platform services | gateway, monitoring, cert-manager, external-dns, secrets, mesh — uno por capability por entorno. |
| **4** | middleware | kafka, keycloak, postgres-operator, redis-operator — uno por capability por entorno. |
| **5** | applications | webapp-3tier, event-driven, demo-* — muchas por entorno, ciclo de vida de días, propiedad de los equipos de aplicación / oficina de proyecto. |
| **Handle de adjunto de borde** | La única arista ascendente en un grafo de dependencias por lo demás estrictamente descendente: el arquetipo `gateway` de la capa 3 publica un nombre de NEG / ARN de target group / frontend de AGFC que consume el stack de borde de la capa 1. |

---

## 3. Gramática del manifiesto (analogía de paquete tomada de apt/rpm)

| Campo | Análogo | Definición |
|---|---|---|
| **`requires`** | `Depends:` | Declara una dependencia de capability; el fallo es un error de resolución que nombra la cadena completa de quien la requiere. |
| **`requires[].traits`** | — | Traits requeridos en el proveedor enlazado; el fallo nombra el trait que falta. |
| **`requires[].optional`** | `Recommends:` | El fallo es solo un aviso; dirige la selección de stacks por `condition:`. |
| **`provides`** | `Provides:` | Declara qué capability (versión, traits, salidas, `tenant_resources`) satisface el arquetipo. Pertenece al arquetipo como conjunto, no a un stack interno. |
| **`conflicts`** | `Conflicts:` | Declara capabilities/arquetipos incompatibles; el fallo es un error de resolución. |
| **`runtimes`** | `Architecture:` | Qué runtimes soporta el arquetipo; falla si el runtime del entorno está ausente. |
| **`stacks[]`** | — | Los stacks internos de Terramate que posee un arquetipo; cada uno se convierte en un stack de Terramate bajo el directorio de la instancia. `after` se convierte en `stack.after`. |
| **`stacks[].use`** | — | Referencia a un componente del catálogo para expandirlo como stack; un componente desconocido es un error. |
| **`stacks[].condition`** | — | Una expresión booleana (p. ej. `resolved(database-platform)`) evaluada tras la resolución para decidir qué stacks se generan realmente. |
| **`claims[]`** | — | Declara recursos finitos que reserva el arquetipo/stack; el fallo es un fallo de asignación (pool agotado o valor ya tomado). |
| **`firewall[]`** | — | Declara reglas de red usando selectores (ver §7); falla si un selector referencia un propósito no reclamado. |
| **`capacity{}`** | — | Declara consumo de recurso divisible contra un presupuesto compartido; el fallo es presupuesto excedido entre los tenants activos. |
| **`providers[]`** | `Build-Depends:` | Declara las fuentes de proveedor de OpenTofu requeridas y sus restricciones de versión; el fallo es una intersección de restricciones vacía en todo el cierre. |
| **`creates_tenant_resources`** | — | Declarado en un stack consumidor, listando en qué capabilities proveedoras escribe tenant resources (p. ej. `event-bus`); debe coincidir con los tipos `tenant_resources` que autoriza el proveedor. |
| **`tenant_resources`** | — | Declarado en la entrada `provides` de un proveedor: qué tipos de objetos creados por tenants autoriza (p. ej. `KafkaTopic`, `KafkaUser`), con `namePrefix` y `maxCount`. |
| **Capability virtual** | — | Un nombre de capability del que depende una aplicación de forma abstracta (p. ej. `cluster`), satisfecho por el arquetipo que nombre el binding del entorno. |
| **Versión de capability** | — | Versiona el **contrato de salidas** de la capability, no su implementación. MAJOR = salida eliminada/renombrada/con tipo cambiado, o un tipo de `tenant_resources` eliminado; MINOR = salida o trait añadido; PATCH = solo implementación, contrato idéntico byte a byte. |

---

## 4. Redes y pools de direcciones

| Término | Definición |
|---|---|
| **Bloque CIDR** | Un rango de direcciones reclamado como recurso; p. ej. el CIDR del entorno, la subred de nodos, el rango de pods, la subred de base de datos/rango PSA, la subred de egress serverless. |
| **Rango PSA (Private Services Access)** | Un rango de direcciones específico de GCP, por VPC (no por arquetipo), para servicios gestionados, reclamado una sola vez por el arquetipo de entorno en la capa 1. Un claim de base de datos dentro de él no es en sí mismo un claim CIDR. |
| **Zona de propósito** | Una subdivisión con nombre del pool de direcciones de un entorno (`infra`, `data`, `edge`, `growth`, `pods`), cada una reclamable solo para los propósitos declarados; da a las reglas de firewall una superficie de destino estable para los casos que genuinamente necesitan un CIDR en vez de un selector de workload. |
| **Zona `growth`** | Una zona reservada, nunca asignable, guardada para expansión futura dentro del pool de un entorno. |
| **Zona `pods`** | Una zona de propósito `/18` usada solo para rangos de pods. |
| **Rango de pods** | El rango IP secundario asignado a los pods de un cluster de Kubernetes, dimensionado a partir de `max_pods_per_node`. **Inmutable tras crear el cluster** (riesgo R26). |
| **Subred de nodos** | El rango IP asignado a los nodos del cluster; el dimensionamiento se deriva como `max_nodes × 4`, con un suelo de `/24`. |
| **`max_pods_per_node`** | Valor por defecto de la plataforma **64** (asume nodos con ≥32 GB de RAM), dando un bloque `/25` por nodo y 128 nodos en una mitad de pods `/18`. Inmutable tras crear el cluster. Si es configurable en GKE Autopilot es una pregunta abierta. |
| **Overlay-pods** (trait) | Marca un runtime (p. ej. AKS con Azure CNI Overlay) cuyos pods no consumen direcciones reales de VNet/red, así que su claim de rango de pods es cero — importa para la planificación de capacidad. |
| **Perfil de claim** | La forma, por runtime, de qué recursos de red reclama un runtime (p. ej. GKE reclama subred de nodos + rango de pods; EKS solo reclama subredes de nodos, consumiendo direcciones reales de VPC por pod). |
| **IP estática de borde** | Un claim con alcance de cuenta/proyecto para una dirección IP pública fija, reclamado en la capa 0. |
| **Hostname (claim)** | Un claim de nombre DNS, con alcance en la zona DNS de un entorno; cuarentena de cero días. |
| **Clave de asignación** | La tripleta **`(pool, owner, purpose)`** usada para hacer idempotente la asignación de claims — una solicitud repetida para la misma tripleta devuelve la asignación existente. |
| **First-fit** | La estrategia de asignación determinista: los bloques candidatos del tamaño solicitado se consideran en orden ascendente y se elige el primero que encaja, garantizando reproducibilidad tras un rebase. |
| **`max_claim_fraction`** | Una política de pool que limita qué fracción de una zona puede consumir un solo claim, evitando que un arquetipo agote el espacio de direcciones de un entorno. |
| **Asignación por pares (buddy)** | Estrategia de asignación que prefiere bloques que preservan tiradas libres más grandes, mitigando la fragmentación del pool con el tiempo (riesgo R27). |
| **El tráfico este-oeste se resuelve por DNS** | Decisión asentada: las direcciones no necesitan ser reproducibles entre reconstrucciones; lo que se requiere es una asignación idempotente. Las reglas de firewall deben preferir selectores de workload (etiquetas de red, referencias a security groups) sobre CIDR. |

---

## 5. CMDB (base de datos de gestión de configuración)

| Nivel | Definición |
|---|---|
| **Nivel 0** | Ficheros en bruto en Git (`cmdb-data/`): manifiestos resueltos, entornos, instancias, un fichero por stack, ficheros de aristas (`depends-on.json`, `provides.json`, `tenant-resources.json`), ledgers de pools y un `index.json`. El sistema de registro. |
| **Nivel 1** | Un modelo de lectura publicado: `index.json` más una proyección JSON-LD servida vía GitHub Pages / contenido crudo / Contents API / asset de release. |
| **Nivel 2** | Un modelo analítico: DuckDB sobre Parquet particionado, publicado como asset de release no committeado, consultado en el navegador vía DuckDB-WASM con peticiones HTTP range. |
| **Nivel 3** | Una base de datos de grafos opcional (KuzuDB u Oxigraph), justificada solo cuando las consultas necesitan recorridos de longitud variable y tipo de arista mixto (p. ej. alcanzabilidad multi-salto de identidad/secreto) — no debe construirse de forma especulativa. |
| **Arista (CMDB)** | Una relación extraída estáticamente antes del despliegue: aristas de dependencia (de `input.from_stack_id`), aristas de capability (de `provides`), aristas de tenant resource (de `creates_tenant_resources`). |
| **Workflow de drift** | El proceso que mantiene los ficheros de la CMDB alineados con el último apply exitoso; sin él la CMDB "miente con confianza." |
| **DuckDB / DuckDB-WASM** | La base de datos analítica embebida usada para el modelo de nivel 2 de la CMDB, consultable en el navegador vía WASM. |
| **graphology / networkx** | Librerías de grafos sugeridas para cargar en memoria la proyección JSON-LD de nivel 1 y hacer consultas de grafo a escala moderada (<~100 000 nodos). |
| **KuzuDB** | Una base de datos de grafo de propiedades embebida candidata (Cypher, WASM) para un modelo de grafo de CMDB de nivel 3. |
| **Oxigraph** | Una base de datos de grafo RDF/SPARQL embebida candidata (Rust, WASM) para un modelo de grafo de CMDB de nivel 3. |

---

## 6. Algoritmo de resolución (`archetypectl resolve`) — los 17 pasos

| Grupo de pasos | Pasos | Qué ocurre |
|---|---|---|
| **Cargar** | 1–2 | Cargar manifiestos, componentes y binding; expandir `stacks[].use`; imponer las reglas de categoría de `kind: demo`. |
| **Grafo** | 3–4 | Calcular el cierre transitivo con detección de ciclos; enlazar cada capability a su único proveedor (una búsqueda directa, no una búsqueda combinatoria — por qué la resolución es lineal y no NP-completa). |
| **Validar** | 5–11 | Versiones, traits, soporte de runtime, conflictos, evaluación de `stacks[].condition`, verificación del contrato de salidas, autorización de tenant resources. |
| **Asignar** | 12–15 | Claims (jerárquicos, idempotentes), selectores de firewall, presupuestos de capacity, restricciones de versión de providers. |
| **Emitir** | 16–17 | Orden topológico; escribir `resolution.json` + `binding.tm.hcl` + escrituras del ledger + comentario en el PR. |

| Término | Definición |
|---|---|
| **`archetypectl`** | La CLI (planeada) que ejecuta la resolución (`archetypectl resolve --instance demos-alpha`) y, según la guía del desarrollador, monta el andamiaje de aplicaciones nuevas (`archetypectl new-app`, todavía aplazado). |
| **`--dry-run`** | Un modo de resolución que ejecuta todos los pasos salvo las escrituras del ledger, de modo que un PR de solo validación no consume direcciones. |
| **Falla de forma cerrada** | Principio de diseño: los errores de resolución bloquean el PR en vez de continuar con un estado no resuelto o ambiguo. |
| **"Quién lo requirió, y qué cambiar"** | La regla declarada para todo mensaje de error de resolución: nombrar la cadena de quien lo requiere y el remedio, no solo el fallo. |
| **"No hay solución instalable"** | Formulación de diagnóstico para un conflicto de versión sin resolución posible, porque un entorno mantiene exactamente una instancia de una capability. |
| **`skipped_stacks`** | Un campo de `resolution.json` que registra qué stacks condicionales no se generaron y por qué. |
| **`expiresOn`** | Campo obligatorio en arquetipos `kind: demo`; un job programado lista las instancias caducadas y abre un PR de destrucción aprobado por humano — la destrucción nunca es automática. |

---

## 7. Selectores de firewall

| Selector | Significado |
|---|---|
| **`purpose:<name>`** | Un rango que este mismo arquetipo reclamó con ese propósito. |
| **`zone:<name>`** | Una zona de propósito del pool del entorno — una superficie de destino estable. |
| **`cidr:<literal>`** | Un rango fijo (p. ej. rangos de health check, CIDR del plano de control); se usa solo cuando genuinamente hace falta. |
| **`self`** | El selector de workload propio del stack (etiqueta de red, security group, etiqueta de NetworkPolicy); preferido sobre CIDR para tráfico este-oeste. |

---

## 8. Kafka / tenant resources multi-tenant

| Término | Definición |
|---|---|
| **Kafka (arquetipo, no componente)** | Kafka despliega un operador e impone un contrato multi-tenant — bus común, datos de tenant separados — que es lo que lo convierte en arquetipo en vez de componente. |
| **Event-bus** | La capability que provee el arquetipo `kafka`, que representa el bus Kafka común multi-tenant. |
| **Strimzi** | El operador de Kubernetes usado para ejecutar Kafka. |
| **KRaft** | El modo de consenso de Kafka basado en Raft (sin ZooKeeper); un trait con nombre usado por el stack de cluster del arquetipo `kafka`. |
| **`KafkaTopic` / `KafkaUser`** | Recursos personalizados (tenant resources) que un arquetipo *consumidor* crea dentro del namespace del proveedor Kafka, en vez de que el proveedor los cree; deben llevar el prefijo de tenant obligatorio. |
| **ACL (Access Control List)** | Regla de autorización a nivel de Kafka; derivada automáticamente por el arquetipo `kafka` a partir del prefijo `KafkaUser` de cada tenant — nunca escrita a mano — para garantizar el aislamiento. |
| **Prefijo de nombre obligatorio** (`{{ instance }}-`) | Todos los topics/usuarios de Kafka de un tenant deben llevar este prefijo, forzado por política de admisión, evitando colisiones silenciosas entre tenants. |
| **Cuotas de Kafka** | Límites por `KafkaUser` (tasa de bytes de productor/consumidor, porcentaje de peticiones) necesarios porque `ResourceQuota` de Kubernetes no limita el throughput de Kafka. |
| **`kafka_partitions`** | Una clave de capacity; el techo real de un cluster Kafka (se agota antes que CPU/almacenamiento). El presupuesto de 4000 usado para `demos` es un valor provisional pendiente de medirse contra el número de brokers previsto (pregunta abierta). |
| **`kafka_topics` / `kafka_storage_gib` / `kafka_throughput_mibs`** | Claves de capacity adicionales de Kafka que gobiernan la carga de reconciliación del operador, el almacenamiento retención×throughput y el throughput agregado de productores. |

---

## 9. Generate — conceptos centrales de Terramate y OpenTofu

| Término | Definición |
|---|---|
| **Terramate CLI** | La herramienta de orquestación open source, solo CLI, sobre la que se construye la plataforma; resuelve la composición "stacks dentro de stacks" mediante stacks planos más generación de código, en vez de bloques de stack anidados. Elegida sobre Terraform Stacks (solo HCP, no está en la CLI OSS ni en OpenTofu) y sobre Terragrunt (detección de cambios a escala, ejecución de binario nativo, el código generado es `.tf` real que Checkov puede escanear directamente). |
| **OpenTofu** | El fork open source de Terraform usado como motor de ejecución de IaC; `tofu` es el binario invocado en todo el sistema. Decidido desde el principio, frente a Terraform. |
| **Terraform Stacks** | El modelo de bloques `component`/`stack`/`deployment` de HashiCorp; una funcionalidad exclusiva de plataforma alojada (HCP Terraform / Terraform Enterprise 2.0+), no disponible en Terraform OSS ni en OpenTofu — fuera de alcance aquí. |
| **Módulo** | Un módulo reutilizable de OpenTofu (recursos, variables, salidas, restricciones de provider) sin backend propio; vive bajo `modules/` o en un registro. |
| **Stack** (Terramate) | Un directorio que contiene `stack.tm.hcl`, una configuración de backend y su propio fichero de estado — la unidad más pequeña que orquesta Terramate. |
| **Platform** (agrupación de stacks) | Un conjunto de stacks (red + cluster + servicios de plataforma) que provee las bases compartidas para una cloud y un entorno; produce salidas consumidas por las instancias de arquetipo. |
| **Instancia de arquetipo** (lado generate) | Un despliegue concreto de una plantilla de arquetipo, enlazado a una plataforma y un entorno; consume salidas vía `binding.tm.hcl`. |
| **Stack productor** | Un stack que declara bloques `output`, haciendo disponibles hechos de tiempo de ejecución a otros stacks. |
| **Stack consumidor** | Un stack que declara bloques `input`, extrayendo hechos de tiempo de ejecución de un stack productor. |
| **Entorno dedicado** | Una plataforma que sirve exactamente a una instancia de arquetipo. |
| **Entorno compartido** | Una plataforma que sirve a muchas instancias de arquetipo a la vez (típico para demos). |
| **Globals** | La capa de datos en tiempo de compilación de Terramate, heredada hacia abajo por el árbol de directorios y sobreescribible en cualquier nivel; usada para valores conocidos antes del apply. Regla general: globals para todo lo conocido antes del apply, outputs sharing solo para valores que se conocen después del apply. |
| **Outputs Sharing** (`sharing_backend`/`output`/`input`) | El mecanismo **experimental** de Terramate para pasar hechos de tiempo de ejecución (IDs de VPC, endpoints de cluster, ARN de OIDC) entre stacks que no pueden conocerse en tiempo de generación. Requiere `experiments = ["outputs-sharing"]`. Aceptado pese a ser experimental (riesgo R1); los contratos se centralizan en `imports/contracts/` para que un cambio incompatible sea una edición acotada. |
| **`sharing_backend`** | El bloque de nivel raíz que nombra el transporte para outputs sharing: `type` (la palabra clave desnuda, sin comillas, `terraform`), `filename` (por convención `_sharing_generated.tf`), y `command` (p. ej. `["tofu","output","-json"]`, ejecutado dentro del directorio del stack productor, debe emitir JSON). Se define una sola vez en la raíz del repo. |
| **Bloque `output`** | Declara el contrato de un productor: un valor con nombre ligado a un `backend`, evaluado en el código OpenTofu generado, con `description`/`sensitive` opcionales. Renombrar la etiqueta es un cambio incompatible para todo consumidor. |
| **Bloque `input`** | Declara el contrato de un consumidor: genera una `variable "<etiqueta>"`, referenciando a un productor vía `from_stack_id`, evaluando una expresión sobre `outputs.*`, con un `mock` opcional usado solo bajo `--mock-on-fail`. |
| **`from_stack_id`** | El atributo del bloque `input` que nombra el ID del stack productor. **Acepta una expresión, no solo un literal** — esto es "una suposición tomada como decisión de diseño": todo el modelo de late binding depende de ello, permitiendo que un contrato escrito a mano referencie `global.platform.cluster_stack_id` y sirva a toda instancia enlazada. Si resulta ser solo literal, el resolver debe generar un fichero de contrato por instancia en su lugar — más maquinaria, no un rediseño. |
| **`mock` (atributo de input)** | Un valor de respaldo usado solo bajo `--mock-on-fail`, esencial para las previsualizaciones de PR donde la salida real del productor todavía no existe. Debe coincidir exactamente con el tipo del valor real — un tipo distinto pasa la validación en el plan y falla en el apply. Convención: prefijar cada mock con `mock-`. |
| **`mock_on_fail`** | Controla si una lectura fallida de outputs sharing recurre al mock. **Debe ser `true` en preview y `false` en deploy** — se mantiene en bloques `script` con nombre separados para que no se pueda confundir. |
| **Bloque `stack`** | Declara la identidad del stack (`id`, `name`, `tags`) y el orden (`after`/`before`). `stack.id` debe ser globalmente único, estable y derivable por un humano (escrito a mano en los ficheros de binding): `<cloud>-<env>-<capability>[-<instance>]`. |
| **`stack.after` / orden de ejecución** | Declaración explícita de dependencia que usa Terramate para ordenar las ejecuciones. **Outputs sharing no crea por sí solo orden de ejecución** — todo `input` necesita un `after` a juego, o un consumidor puede ejecutarse antes que su productor sin avisar y resolver un valor obsoleto sin ningún error (riesgo R2, el riesgo principal). |
| **`generate_hcl`** | La primitiva de generación de código de Terramate — "la capa base." Un generador por capability, usando una expresión `condition` sobre globals (o un `stack_filter`) para decidir qué stacks reciben qué HCL emitido. Los ficheros generados llevan el prefijo `_`. |
| **Versionado de generadores** | Los generadores viven bajo `imports/generators/v1/`, etc., condicionados por `condition = global.generators.version == "v1"`, de modo que un cambio incompatible se publica como `v2/` y migra entorno por entorno cambiando un global. |
| **Bloque `script`** (`terramate script`) | Nombra un workflow de varios pasos (init/plan/apply) invocable de forma idéntica desde un portátil o desde CI; las flags de sharing (`enable_sharing`, `mock_on_fail`) se fijan aquí por comando. Scripts `preview`/`deploy` separados evitan que se intercambie el comportamiento de los mocks. |
| **Bloque `assert`** | Falla `terramate generate` cuando se viola un invariante, imponiendo reglas arquitectónicas (p. ej. los clusters de producción deben tener protección de borrado) en vez de limitarse a documentarlas. |
| **`terramate generate`** | Ejecuta todos los generadores y escribe los ficheros generados. **`terramate generate --check`** es la puerta **G0**: garantiza que nadie ha editado a mano un fichero generado, ya que el siguiente `generate` revertiría la corrección en silencio. |
| **`terramate run`** | Orquesta las invocaciones reales de `tofu` a través de los stacks (p. ej. `terramate run --tags <cloud>:<env>:network --enable-sharing -- tofu apply`). Admite `--changed` para ejecuciones incrementales y selección por `--tags` como mecanismo de orden de respaldo cuando el `stack.after` derivado de globals no se resuelve (lo cual falla **en silencio** — probarlo deliberadamente). |
| **`--enable-sharing`** | La flag de `terramate run` que activa la resolución de outputs sharing para esa invocación. |
| **`--mock-on-fail`** | Recurre al `mock` declarado del input tras una lectura fallida de outputs sharing; nunca debe aparecer en una ruta de deploy real. |
| **`terramate.tm.hcl`** | Configuración de raíz del repositorio: fija `required_version`, declara `experiments` (necesario para desbloquear `sharing_backend`/`input`/`output`), fija los valores por defecto de `config.git` para la detección de cambios, y `config.run.env`. |
| **`imports/`** | Convención de directorio que solo contiene configuración importable (mixins, generadores, contratos, scripts) — nunca stacks reales. Terramate nunca debe orquestar nada bajo él. |
| **`imports/mixins/`** | Fragmentos generadores de backend y provider por cloud (`backend_gcp.tm.hcl`, `provider_gcp.tm.hcl`) más la inyección de etiquetas comunes. |
| **`imports/generators/v1/`** | Un generador por capability (`gen_network.tm.hcl`, `gen_cluster.tm.hcl`, ...) — "la capa base." |
| **`imports/contracts/`** | Definiciones de contrato de output/input por capability (`contract_network_gcp.tm.hcl`, `contract_cluster_gke.tm.hcl`), centralizando el contrato de sharing para revisarlo en un solo sitio. |
| **`imports/scripts/`** | Definiciones de bloques `script` con nombre (`tofu.tm.hcl` define `preview`/`deploy`). |
| **Convención de nombres de ficheros generados** | Los ficheros generados se committean a git y llevan el prefijo `_` (`_main.tf`, `_sharing_generated.tf`, `_providers.tf`, `_backend.tf`), se ordenan juntos, y están cubiertos por `CODEOWNERS`. |
| **`_sharing_generated.tf`** | El nombre de fichero por defecto que contiene los bloques `variable`/`output` derivados, producidos a partir de las declaraciones `input`/`output`. |
| **`tm_cidrsubnet`** | Una función de evaluación de globals de Terramate que calcula rangos CIDR de subred/pods/servicios a partir de un CIDR padre en tiempo de generación — en tiempo de compilación, revisable en los diffs. |
| **`tm_dynamic`** | Una construcción de `generate_hcl` (análoga al `dynamic` de Terraform) que itera una lista en tiempo de compilación (p. ej. `global.tenants`) para emitir bloques repetidos. |
| **`tm_contains` / `tm_can` / `tm_regex`** | Funciones auxiliares de Terramate usadas en expresiones `assert`: pertenencia a una lista, captura de errores de evaluación, validación por regex. |
| **`terramate debug show globals`** | Inspecciona los globals totalmente resueltos de un stack. |
| **`terramate experimental run-graph`** | Inspecciona el orden de ejecución calculado entre stacks. |
| **`config.tm.hcl`** | Fichero por nivel de directorio (capa de cloud, capa de entorno) que declara `globals` heredados por todo lo que hay debajo. |
| **Apply escalonado (primer despliegue)** | El orden manual requerido para el primerísimo apply de un entorno completamente nuevo — red → cluster → servicios de plataforma → instancia — porque el bloque provider de un consumidor no puede alcanzar un recurso que todavía no existe. Después de eso, `terramate run --changed` gestiona todo el grafo en una sola pasada. |

---

## 10. Trampas (transversales — léase antes de escribir código)

| Trampa | Por qué importa |
|---|---|
| **Outputs sharing no crea orden de ejecución** | Todo `input` necesita un `after` a juego; un orden sin resolver aplica un valor obsoleto **sin ningún error** (riesgo R2, el principal; la puerta **G1** existe específicamente para atraparlo). |
| **`mock_on_fail` verdadero en preview / falso en deploy** | Hay que usar bloques `script` con nombre separados, o un despliegue puede recurrir a un mock en silencio y aplicar disparates. |
| **Los mocks deben tener el tipo correcto** | Un campo base64 simulado como `"mock"` rompe `base64decode()`; un campo de lista simulado como cadena pasa la validación local y explota en el apply. Prefijar cada mock con `mock-`. |
| **Nunca compartir secretos por outputs sharing** | Los valores acaban en variables de entorno `TF_VAR_*`, que se filtran a logs y árboles de procesos. Compartir referencias (ID de secreto, ARN, nombre de clave); los consumidores los obtienen bajo su propia identidad. Los tokens de autenticación (`google_client_config`, `aws_eks_cluster_auth`) siempre se obtienen localmente, nunca se comparten. |
| **El endpoint de GKE no tiene esquema; el de EKS incluye `https://`** | Bug clásico de copiar y pegar entre guías por cloud. |
| **El nombrado determinista rompe ciclos de dependencia** | El ciclo de etiquetado de subredes de EKS (la red necesita el nombre del cluster, el cluster necesita las subredes) se resuelve promoviendo `cluster_name` a global. Este es el remedio general siempre que outputs sharing parece necesitar un ciclo. |
| **Outputs sharing modela 1 a N, no N a 1** | Los bloques `input` no pueden generarse desde una lista dinámica (fan-in). Gateway API elimina el problema de fan-in por completo — la razón por la que es el diseño objetivo, con el enfoque de URL map solo como respaldo. |
| **Evitar `kubernetes_manifest` para CR de Gateway API / Gatekeeper** | Requiere que el CRD y el API server sean alcanzables **en tiempo de plan**, rompiendo las previsualizaciones de PR. Empaquetar los CR en el chart Helm propio del arquetipo, desplegar con `helm_release`. |
| **El ciclo de arranque Keycloak ↔ Gateway** | El `HTTPRoute` propio de Keycloak no debe llevar **ninguna** `SecurityPolicy`, y el descubrimiento OIDC del Gateway debe resolverse a través del Service interno del cluster, no del hostname público. Sin ambas cosas, un entorno en frío no arranca y la causa no es obvia. |
| **`failurePolicy: Fail` puede dejarte fuera del cluster** | Gatekeeper rechazaría su propia recuperación. Mitigado con `exemptNamespaces` para `kube-system`/el propio namespace de Gatekeeper, ≥3 réplicas con un PDB, y `Ignore` en todas partes salvo producción. |
| **ECS: nunca compartir el rol de ejecución de tarea entre tenants** | Un rol de ejecución compartido puede leer los secretos de todos los tenants. Usar un rol por instancia aunque duplique permisos de ECR/logs. |
| **`TargetGroupBinding` de AWS puede referenciar cualquier target group de la cuenta** | En un cluster compartido, un tenant podría redirigir el tráfico de otro. Solo el arquetipo `gateway` los crea; RBAC deniega el CRD a los namespaces de aplicación. |
| **Políticas de confianza OIDC: `StringEquals` sobre el `sub` exacto, nunca `StringLike` con comodín** | La configuración incorrecta de OIDC en AWS más común (riesgo R12). |
| **Los rangos secundarios de pods son inmutables** | Dimensionarlos para pocos nodos significa reconstruir el cluster (riesgo R26). |

---

## 11. Guías de runtime por cloud

### 11.1 Forma común

Las cinco guías de runtime (GKE, EKS, Cloud Run, ECS Fargate, AKS) siguen el mismo grafo — `network → runtime (consumidor+productor) → servicios de plataforma → datos / app` — difiriendo solo en *qué hechos cruzan cada arista*.

| Término | Definición |
|---|---|
| **`workload_identity_pool`** (GKE) | El espacio de identidad de GCP por proyecto (`<project>.svc.id.goog`) que enlaza cuentas de servicio de Kubernetes con cuentas de servicio de Google; una salida del cluster. |
| **Workload Identity (GKE)** | El mecanismo de GCP que enlaza una SA de Kubernetes con una SA de Google a través del workload identity pool; debe activarse a nivel de cluster y por node pool, o los pods recaen en compartir la SA del nodo. El binding nunca debe usar un comodín (`POOL[*/*]`) — riesgo R15. |
| **`oidc_provider_arn` / `oidc_provider_url`** (EKS) | Los dos hechos OIDC que debe emitir el stack de cluster de EKS para poder escribir políticas de confianza IRSA — AWS necesita dos hechos donde GCP/Azure necesitan solo uno. |
| **IRSA (IAM Roles for Service Accounts)** | El mecanismo de EKS que enlaza una SA de Kubernetes con un rol IAM a través de federación OIDC y una política de confianza acotada por `sub`/`aud`. Descrito como "el caso de uso canónico de outputs sharing en AWS", ya que la política de confianza no puede escribirse sin el ARN/URL OIDC que produce el apply del stack de cluster. |
| **Proveedor OIDC (EKS)** | El proveedor de identidad OIDC por cluster, compartido por toda instancia de arquetipo en ese cluster — reconstruir el cluster invalida todo rol IRSA de la flota (riesgo R11). |
| **EKS Pod Identity** | Alternativa más reciente de AWS a IRSA, que asocia pods con roles IAM a través de la API de EKS en vez de un documento de confianza OIDC; si se adopta, el stack de cluster emite `pod_identity_agent_ready` en vez de los dos hechos OIDC. |
| **EKS Access Entries (modo de autenticación por API)** | Mecanismo moderno, auditado por IAM, para el acceso al cluster, que sustituye al `ConfigMap` `aws-auth` heredado (sin rastro de auditoría, se corrompe con escrituras concurrentes). Propiedad exclusiva del stack `eks`. |
| **`oidc_issuer_url`** (AKS) | La salida del cluster de AKS que nombra al emisor OIDC del que depende toda credencial de identidad de workload federada. |
| **`azurerm_federated_identity_credential`** | Enlaza una identidad gestionada asignada por el usuario con un `subject` OIDC acotado a namespace y cuenta de servicio concretos — nunca un comodín. |
| **UAMI (User-Assigned Managed Identity)** | Una identidad de Azure creada por workload, usada en vez de la identidad asignada por el sistema del cluster o la identidad del kubelet, de modo que un workload nunca hereda privilegios del pipeline o del nodo. |
| **Identidad del kubelet** | La identidad a nivel de nodo de AKS, acotada solo a pull de ACR; nunca debe reutilizarse como identidad de workload ya que es alcanzable desde el nodo. |
| **`local_account_disabled`** | Ajuste de AKS que elimina el kubeconfig estático de admin, forzando Entra ID + RBAC de Azure para el acceso al cluster — evita que `kube_config` se convierta en una credencial desnuda en el estado (riesgo R25). |
| **Grupo de recursos de nodo** (AKS) | Un segundo resource group que AKS crea y gestiona automáticamente junto al cluster; no debe gestionarse con Terraform, o el reconciliador del cluster peleará con el plan. |
| **Azure CNI Overlay** | El modo de red de pods por defecto de AKS: los pods obtienen direcciones de un CIDR overlay privado, no enrutable, en vez de IPs de VNet, eliminando la presión sobre las IPs de la VNet. |
| **Azure CNI (tradicional)** | Modo de AKS en el que cada pod obtiene una IP de VNet enrutable; se usa solo cuando los pods deben ser directamente alcanzables desde fuera del cluster. |
| **Azure CNI Powered by Cilium** | Modo de AKS que combina direccionamiento overlay con un dataplane eBPF, elegido cuando se necesita NetworkPolicy con el rendimiento de eBPF. |
| **AGFC (Application Gateway for Containers)** | La implementación de Gateway API de Azure; utilizable en modalidad BYO (traer el propio), aprovisionada en Terraform. Es en sí misma un gateway L7, así que poner Envoy Gateway detrás es un doble salto redundante. |
| **Secrets Store CSI driver** | El mecanismo de AKS para montar secretos de Key Vault en pods vía workload identity, de modo que los Secrets de Kubernetes nunca son la fuente de verdad. |
| **`artifact_registry_repo` / `cloud_armor_policy_id`** (Cloud Run) | Salidas del stack de red que consume un stack de runtime de Cloud Run. |
| **Agente de servicio de Cloud Run** | La identidad gestionada por GCP (`service-<número-de-proyecto>@serverless-robot-prod.iam.gserviceaccount.com`) que realmente hace pull de las imágenes de contenedor para un servicio de Cloud Run — distinta de la SA de runtime propia del servicio. Conceder permisos de pull a la SA de runtime en su lugar es "un fallo clásico del primer despliegue." |
| **Direct VPC egress** | El mecanismo preferido (más reciente) para que Cloud Run alcance recursos privados de VPC sin un conector gestionado; requiere una subred `/24` dedicada como mínimo. |
| **Conector Serverless VPC Access** | El mecanismo heredado para el acceso a VPC de Cloud Run, usando un recurso/CIDR de conector fijo. |
| **Binary Authorization** | Control basado en atestaciones que exige que las imágenes de contenedor lleven atestaciones verificadas antes del despliegue (GKE y Cloud Run). |
| **Ocultación de metadata (GKE)** | Desactivar los endpoints de metadata heredados de GCE (`metadata.disable-legacy-endpoints = true`) para que los pods no puedan leer directamente el token de la SA del nodo, lo que anularía Workload Identity. |
| **Nodos Shielded de GKE** | Nodos de GKE con arranque seguro y monitorización de integridad activados — parte de la línea base de seguridad de GKE. |
| **gVisor** | El sandbox a nivel de kernel por servicio de Cloud Run, que hace que una plataforma Cloud Run compartida sea materialmente más segura que un node pool de GKE compartido para workloads de demo semi-confiables. |
| **Cloud Armor** | El servicio de WAF/política de seguridad de borde de GCP — evitado si el `ingress` de un servicio de Cloud Run es `ALL` o su invoker es `allUsers` sin un balanceador delante (riesgo R14, "el ajuste de Cloud Run mal configurado más común con diferencia"). |
| **`cluster_arn` / `alb_listener_arn` / `task_role_boundary_arn`** (Fargate) | Salidas del stack de runtime que necesita un stack consumidor de Fargate. |
| **Rol de ejecución de tarea** (ECS) | El rol IAM usado antes de que arranque el contenedor: hace pull de la imagen desde ECR, crea log streams, lee los secretos de la definición de tarea. No alcanzable desde dentro del contenedor. |
| **Rol de tarea** (ECS) | El rol IAM que asume el código de la aplicación durante toda su vida, alcanzable a través del endpoint de metadata de la tarea. Siempre debe ser distinto del rol de ejecución — la regla cardinal de ECS de la plataforma. |
| **Rol de ejecución por instancia** | En un cluster ECS compartido, un rol de ejecución dedicado acotado a los secretos propios de una instancia — compartirlo dejaría que el rol que arranca las tareas del tenant A lea los secretos del tenant B (riesgo R13). |
| **Permission boundary (ECS)** | Adjunto tanto al rol de ejecución como al de tarea, publicado por la plataforma, evitando la escalada de privilegios desde el propio stack de un tenant — "la piedra angular de la multi-tenancy" para ECS. |
| **Protección frente a confused deputy** | Condiciones de política de confianza (`aws:SourceArn` + `aws:SourceAccount`) que fijan la asunción de rol a una cuenta y cluster concretos, bloqueando la asunción entre cuentas vía el service principal de ECS. |
| **Bloque `secrets` frente a `environment`** (definición de tarea ECS) | Los valores sensibles deben ir en `secrets` (resueltos por el rol de ejecución al arrancar, nunca aparecen en `DescribeTaskDefinition`), nunca en `environment` en claro. |
| **ECS Exec** (`enable_execute_command`) | Shell interactiva dentro de una tarea de Fargate en ejecución; desactivada por defecto y bloqueada por assertion en producción. |
| **`readonlyRootFilesystem`** | Ajuste de contenedor que bloquea la mayoría de las herramientas de post-explotación al impedir escrituras en el sistema de ficheros raíz. |
| **Aislamiento por micro-VM de Fargate** | Cada tarea de Fargate obtiene su propia micro-VM — aislamiento de cómputo por tarea más fuerte que la exposición de kernel compartido de un node pool de EKS compartido. |
| **Asignación de prioridad de listener** | Un espacio de nombres compartido y finito de prioridades de regla de listener de ALB, asignado en rangos por tenant (`config.tm.hcl`, p. ej. `alpha = 100–199`) para que PR concurrentes no colisionen. |
| **Perfiles de EKS Fargate** | Una opción de cómputo (no una plataforma separada) que selecciona workloads por namespace/etiquetas, usando un rol de ejecución de pod de Fargate en vez del rol de nodo; no soportado: DaemonSets, contenedores privilegiados, red del host. |
| **VPC endpoints (AWS)** | Endpoints de interfaz/gateway (ECR API/DKR, S3, CloudWatch Logs, Secrets Manager/SSM, STS, SSM Messages) que permiten a las tareas de Fargate en subredes privadas alcanzar servicios de AWS sin una NAT gateway — "la línea base de buenas prácticas" frente a NAT. |
| **Envelope encryption (secretos de EKS)** | Cifrar los secretos de Kubernetes (etcd en reposo) bajo una clave KMS gestionada por el cliente — parte de la línea base de seguridad de EKS. |
| **Límite de saltos de IMDS / IMDSv2** (EKS) | Restringir el servicio de metadata de instancia EC2 a un límite de saltos de 1 y exigir IMDSv2, evitando que un pod comprometido alcance las credenciales del instance profile del nodo. |

### 11.2 Fronteras de aislamiento

| Familia de runtime | Frontera |
|---|---|
| **Runtimes de Kubernetes** (GKE, EKS, AKS) | El **namespace** — kernel compartido en nodos compartidos, mayor exposición para workloads semi-confiables. |
| **Runtimes serverless** (Cloud Run, ECS Fargate) | El **servicio / la tarea** — aislamiento por workload, un valor por defecto más fuerte para entornos de demo compartidos. |
| **Autopilot / EKS Auto Mode / AKS Automatic** | Modos de Kubernetes gestionado en las tres clouds que restringen los workloads privilegiados de forma distinta; modelados como traits en vez de código con casos especiales. |
| **`workload_identities`** | Clave de capacity normalizada que cubre las cuentas de servicio de GCP, los roles IAM de AWS y las identidades gestionadas de Azure bajo una sola clave presupuestada. |

---

## 12. Adjunto de borde y Gateway API

| Término | Definición |
|---|---|
| **Trait `iac-owned-edge`** | Se gana cuando el mecanismo de adjunto del balanceador de carga está completamente creado y rastreado en el estado de Terraform — cierto para `TargetGroupBinding` de AWS y AGFC de Azure, **falso** para el NEG standalone gestionado por el controlador de GCP (el hueco se registra en vez de ocultarse). |
| **NEG standalone (Network Endpoint Group)** | El mecanismo de GCP que expone pods a un balanceador de carga; creado por el controlador de NEG de GKE (no por Terraform) y referenciado como fuente `data`. Los NEG son zonales, así que `minReplicas` debe ser ≥ el número de zonas. |
| **`TargetGroupBinding`** | Un CRD de Kubernetes de AWS que enlaza un Service con un target group de ALB/NLB aprovisionado enteramente en Terraform. Nunca se combina con `aws_lb_target_group_attachment`. En un cluster compartido puede referenciar **cualquier** target group de la cuenta, así que solo el arquetipo `gateway` puede crearlo (riesgo R21). |
| **Envoy Gateway** | La implementación de referencia de Gateway API elegida para ingress; OIDC nativo vía `SecurityPolicy`. Su Service de cara al borde lo genera el controlador (vía `EnvoyProxy`), no se escribe a mano. |
| **`EnvoyProxy`** | Recurso personalizado que configura el Service de proxy generado por el controlador (tipo, anotaciones de cloud, número de réplicas, topology spread); admite `mergeGateways` para compartir una sola flota de proxies entre varios Gateways. |
| **`GatewayClass`** | El recurso de Gateway API que referencia una configuración de `EnvoyProxy`; desplegado vía `helm_release`, nunca `kubernetes_manifest`. |
| **`HTTPRoute`** | Un recurso de Gateway API en el namespace de la aplicación, adjuntado a un Gateway vía `parentRefs` — invierte la dependencia de enrutamiento para que el borde ya no necesite conocer a sus tenants. |
| **`parentRefs`** | El campo de `HTTPRoute` que nombra el/los Gateway(s) al que se adjunta. |
| **`allowedRoutes`** | El campo del lado del Gateway (`namespaces.from: Selector`) que controla qué namespaces/rutas pueden adjuntarse — sustituye a una lista de fan-in de tenants. |
| **`SecurityPolicy`** | Un CR de Envoy Gateway que proporciona autenticación OIDC nativa en el gateway. El `HTTPRoute` propio de Keycloak no debe llevar ninguna, para evitar el ciclo de arranque. |
| **Un Gateway por entorno** | El patrón obligatorio — no uno por tenant — ya que cada Gateway genera su propio Deployment/Service/NEG de Envoy. |
| **Fail-open frente a fail-closed (fallo del IdP)** | La decisión explícita de si el Gateway sigue sirviendo (fail-open) o deja de autenticar todo (fail-closed) si Keycloak está caído. Aceptable fallar en `demos`; producción necesita Keycloak en alta disponibilidad más una decisión explícita. |

---

## 13. Identidad, IAM y línea base de seguridad

| Término | Definición |
|---|---|
| **Federación OIDC (identidad de pipeline)** | Nunca se guardan credenciales cloud de larga vida (claves JSON de SA, claves de acceso IAM) en CI; el pipeline se autentica por intercambio de tokens OIDC. |
| **Identidad de plan frente a identidad de apply** | Plan es de solo lectura y alcanzable desde cualquier rama/PR; apply es de solo escritura y alcanzable solo desde un GitHub Environment protegido con revisores obligatorios. |
| **Workload Identity Federation (GCP, pipeline)** | `google_iam_workload_identity_pool`/`_provider` que permite a GitHub Actions asumir una SA de GCP vía OIDC, acotado por un `attribute_condition`. |
| **`attribute_condition`** | La condición WIF de GCP requerida que restringe qué repositorio de GitHub puede suplantar al pool; omitirla deja que cualquier repositorio de GitHub del mundo lo suplante. |
| **Claim `attribute.environment`** | Un claim OIDC de GitHub presente solo cuando un job de workflow declara `environment:`; enlazar la SA de apply a él hace que el rol de apply sea inalcanzable sin pasar por la puerta de aprobación del environment. |
| **`aws_iam_openid_connect_provider`** | El recurso de AWS que registra el emisor OIDC de GitHub para `AssumeRoleWithWebIdentity`, emparejado con `sts.amazonaws.com` como audiencia. |
| **Condiciones `sub` / `aud` (política de confianza OIDC de AWS)** | `sub` debe usar `StringEquals` sobre la cadena `repo:ORG/REPO:environment:ENV` exacta (nunca `StringLike` con comodín — riesgo R12); `aud` siempre debe estar presente para rechazar tokens emitidos para otras audiencias. |
| **Permission boundary (pipeline)** | Un límite IAM sobre el rol de apply del pipeline que le niega la capacidad de crear principales IAM más poderosos que él mismo. |
| **`max_session_duration`** | El límite de 1 hora en la sesión de un rol de pipeline asumido, limitando la exposición ante un token de sesión filtrado. |
| **Nombrado de sesión** (`gha-<run_id>-<run_attempt>`) | Ata cada evento de CloudTrail/log de auditoría a una ejecución y commit concretos de GitHub Actions. |
| **Matriz de segregación de roles** | Asigna los jobs de preview/deploy/drift/destroy a identidades distintas de GCP/AWS y a puertas de environment de GitHub; destroy tiene su propia identidad y grupo de aprobadores ya que puede tumbar a todos los tenants en una plataforma compartida. |
| **`-lock=false` (plan)** | Permite que `tofu plan` se ejecute sin adquirir el bloqueo de estado — lo que permite una identidad de plan genuinamente de solo lectura. |
| **Permisos del backend de estado (outputs sharing)** | Un stack consumidor necesita acceso de lectura (y descifrado, si se usa cifrado de estado) al estado del productor — el bloqueador más común en la primera semana de adopción, ya que `tofu output -json` se ejecuta dentro del propio directorio del productor. |
| **Cifrado de estado de OpenTofu** (bloque `encryption`) | Cifrado de estado/plan en el lado del cliente; un consumidor entonces también necesita la clave de cifrado del productor, así que las claves deben acotarse una por entorno, no por stack. |
| **Qué nunca cruza la frontera de sharing** | Outputs sharing se resuelve en variables de entorno `TF_VAR_*` (visibles en volcados de fallo, entornos de subprocesos, logs de CI, salida de `ps`); los secretos nunca deben compartirse así — solo referencias, obtenidas localmente bajo la identidad propia del consumidor. |
| **Salvaguardas por encima del pipeline** | Defensa en profundidad de tres capas: Org Policies/SCP/Azure Policy (el pipeline no puede desactivarlas) → permission boundaries (un tenant no puede escapar de ellas) → políticas de rol de mínimo privilegio (revisadas por PR). |
| **El namespace como frontera de tenancy** | En GKE/EKS, dado que la identidad de workload tiene alcance de namespace, el namespace mismo es la frontera de aislamiento multi-tenant y nunca debe compartirse entre instancias. |

---

## 14. Gestión de entornos

| Término | Definición |
|---|---|
| **Modelos Dedicado / Compartido / Híbrido** | Topologías plataforma-a-instancia: Dedicado (1:1, aislamiento = cuenta/proyecto cloud), Compartido (1:N, aislamiento = namespace + IAM), Híbrido (red compartida, clusters dedicados por grupo de instancias). |
| **`global.platform.model`** | La flag global (`"dedicated"` o `"shared"`) que condiciona la salida del generador — p. ej. las salvaguardas de tenancy solo se emiten cuando es `"shared"`. |
| **Salvaguardas de tenancy (modelo compartido)** | Recursos por instancia generados solo para instancias de modelo compartido: un `kubernetes_namespace` dedicado con `pod-security.kubernetes.io/enforce: restricted`, un `kubernetes_resource_quota`, un `kubernetes_limit_range`, una `kubernetes_network_policy` default-deny. |
| **`global.quota`** | Objeto de globals requerido (cpu, memoria, pods, loadbalancers) que las instancias de modelo compartido deben definir, forzado por assertion. |
| **Destroy acotado por etiqueta** | La destrucción obligatoria en entornos compartidos (`terramate run --tags instance:<name> --reverse ...`) — nunca un selector basado en ruta/`--changed`, que podría arrastrar stacks de plataforma. |
| **Etiqueta `protected`** | Marca los stacks de plataforma para que CI se niegue a destruirlos fuera de un workflow de break-glass. |
| **Recuento de referencias (destrucción de plataforma)** | Contar las instancias que todavía están enlazadas a una plataforma compartida antes de permitir destruir la propia plataforma. |
| **Entorno efímero** (`ephemeral-*`) | Una plataforma de vida corta (p. ej. `ephemeral/conf-2026-q3`) creada copiando `demos/` y cambiando tres globals (`env`, `project_id`, `vpc_cidr`); la caducidad se gestiona con un PR de destrucción aprobado por humano, nunca automático. |
| **Promoción de entorno (diff de globals)** | Mover la configuración de `demos` → `dev` → `qa` → `prod` es puramente un cambio en los valores de globals de `config.tm.hcl` (número de nodos, canal de release, protección de borrado, retención de backups) — generadores y contratos idénticos en todas partes. |
| **Integración de CMDB (Terramate)** | `terramate list --json` (inventario lógico, previo al apply) y `terramate run --changed -- tofu show -json` (inventario físico, posterior al apply) como fuentes de datos de la CMDB — mejor que parsear los ficheros de estado directamente. |

---

## 15. Políticas, Gatekeeper y puertas de CI/CD

| Término | Definición |
|---|---|
| **Tres puntos de aplicación** | CI (conftest + Checkov, todo runtime) → plano de control cloud (Org Policy/SCP/Azure Policy, todo runtime, no evadible) → admisión de cluster (Gatekeeper, **solo runtimes de Kubernetes**). Ninguno sustituye a los demás. |
| **Hueco de paridad de runtime** | Cloud Run y ECS Fargate no tienen capa de admisión de Kubernetes, así que la capability `policy` existe solo donde existe `cluster`; los runtimes serverless sustituyen con controles del plano de control cloud más burdos pero no evadibles (riesgo R37). |
| **División de trabajo entre el resolver y OPA** | El resolver **calcula** (cierre, asignación, orden, escrituras del ledger); OPA **verifica** (comprobaciones de invariante sin estado sobre lo que produjeron el resolver/generadores) — OPA nunca vuelve a resolver nada, dando defensa en profundidad frente a errores del resolver. |
| **G0 — integridad de generación** | `terramate generate && git diff --exit-code` en cada PR; siempre bloqueante. Evita que una edición a mano de `_main.tf` se revierta en silencio. |
| **G1 — estructura y composición** | `conftest test --policy policy/ --data registry/ ...` en cada PR; siempre bloqueante. Impone el invariante de orden `input`↔`after` (R2), convenciones de nombrado de stacks, etiquetado de instancias, la regla de no exportar secretos. |
| **G2 — escaneo estático de seguridad** | `checkov -d . --framework terraform` en cada PR; bloqueante en HIGH/CRITICAL. Ve la *llamada* al módulo. |
| **G3 — escaneo del plan** | `checkov -f plan.json --framework terraform_plan` + `conftest --namespace terraform`, ejecutado antes del apply; bloqueante en HIGH/CRITICAL. Ve el *resultado* del módulo, atrapando configuraciones incorrectas solo alcanzables con una combinación concreta de globals. |
| **Checkov** | Escáner de seguridad de IaC estático/de plan; la "biblioteca estándar" de comprobaciones conocidas de configuración incorrecta cloud, complementario a OPA/Rego (que codifica reglas específicas de la plataforma que Checkov no puede expresar). Configuración en `.checkov/gcp.yaml`, `.checkov/aws.yaml`. |
| **conftest** | Herramienta de política CLI sin estado que consume `registry/*.json` como `--data`; elegida para las comprobaciones de política en CI en vez de correr un servidor OPA. |
| **check-jsonschema** | Herramienta CLI que valida manifiestos, ficheros de componente, bindings de entorno y ledgers de pool contra JSON Schemas antes de que se ejecute la resolución. |
| **`conftest verify`** | Ejecuta los tests unitarios propios de las políticas Rego (`policy/*_test.rego`) para que una regla que nunca se dispara no dé una falsa confianza (riesgo R36). |
| **`archetypectl enrich`** | Herramienta a medida que escanea cada stack en busca de declaraciones `from_stack_id`/`after`, emitiendo los campos `consumes[]` y `after_ids[]`, ya que `terramate list --json` no expone por sí mismo los bloques `input` — se mantiene pequeña e independiente para que el Rego siga siendo portable y testeable contra fixtures. |
| **`skip-check` (Checkov)** | Directiva de configuración por cloud que suprime una comprobación concreta (p. ej. `CKV_GCP_69` para un endpoint de cluster de demo intencionadamente público); toda supresión requiere un comentario que nombre el motivo/alcance y no debe filtrarse a la configuración de producción. |
| **Gatekeeper autogestionado** | El modelo de despliegue elegido en las tres clouds en vez de add-ons gestionados, porque las alternativas gestionadas son mutuamente excluyentes con una instalación autogestionada (AKS rechaza su add-on si Gatekeeper v3 está presente), restringen los templates personalizados, y supondrían tres comportamientos distintos que depurar. |
| **Gatekeeper, no Kyverno** | Elegido porque el equipo ya escribe Rego para conftest — un solo lenguaje de política. Las reglas **no** son literalmente reutilizables entre ambos, solo el lenguaje y las librerías auxiliares, porque la entrada de Gatekeeper es un `AdmissionReview`, no `resolution.json`. |
| **`ConstraintTemplate`** | El tipo de CR de Gatekeeper que envuelve una política Rego para aplicarla en la admisión. |
| **Trait `custom-templates`** | Declarado por un arquetipo que necesita sus propios `ConstraintTemplate`s; hace que el resolver rechace un binding de política gestionada que carezca de este trait (p. ej. el add-on gestionado de Azure). |
| **Sin mutación de Gatekeeper** | El generador emite las etiquetas; Gatekeeper solo las valida. Un escritor, un validador — la mutación haría los cambios invisibles en los diffs de Terraform y partiría la propiedad de la lista de etiquetas. |
| **`enforcementAction`** | Ajuste de constraint de Gatekeeper (`warn` para efímero/demos, `deny` para dev/qa/prod); las reglas nuevas siempre empiezan en `dryrun` antes de promocionarse. |
| **`failurePolicy`** | Ajuste del webhook de Gatekeeper (`Ignore` en todas partes salvo producción, `Fail` en producción) que controla el comportamiento cuando el webhook es inalcanzable. |
| **`exemptNamespaces`** | Configuración de Gatekeeper que excluye `kube-system` y el namespace de Gatekeeper de la aplicación, para que `failurePolicy: Fail` no pueda bloquear la propia recuperación de la plataforma. |
| **Capa 2b (policy)** | La ubicación arquitectónica del control de admisión — entre el cluster (capa 2) y los servicios de plataforma (capa 3) — porque la admisión debe preceder a todo lo que gobierna. |
| **El registro único** (`registry/{capabilities,traits,zones,labels}.yaml`) | La única fuente de verdad de la que se generan los bloques `enum` de JSON Schema, el paquete JSON de `conftest --data`, y el `values.yaml` del chart de Gatekeeper. **Nunca editar a mano un `enum` en `schemas/`** — eso es un bug (riesgo R34). |
| **`registry-generate`** | La herramienta (todavía no escrita) que genera los enums de esquema, el paquete de datos de conftest y los valores del chart de Gatekeeper a partir de `registry/*.yaml`; protegida en CI por `registry-generate --check`, análoga a `terramate generate --check`. Primera tarea de la fase 2c del roadmap. |

---

## 16. Workflows de CI/CD

| Término | Definición |
|---|---|
| **Workflow de preview** | El pipeline de PR: G0 → escaneo estático de Checkov → autenticación OIDC cloud → `terramate script run --changed tofu preview` (sharing y mocks activados) → escaneo del plan con Checkov → comentario en el PR con los stacks cambiados. |
| **`fetch-depth: 0`** | Ajuste de checkout requerido para que la detección de cambios de Terramate (compara contra `main`) tenga el historial de git completo; un clon superficial informa en silencio de cero stacks cambiados. |
| **Workflow de despliegue** | El pipeline de merge a main, protegido por un `environment: production` de GitHub (revisores obligatorios), que ejecuta `terramate script run --changed tofu deploy` con los mocks desactivados, y luego un script de sincronización de la CMDB. |
| **Workflow de drift** | Un job programado que ejecuta `tofu plan -detailed-exitcode -lock=false` por selector de cloud para detectar drift de configuración sin aplicar. |
| **Entradas de construcción de la puerta de política** | La cadena que produce las entradas de evaluación de conftest: `registry-generate --check` → `archetypectl resolve --dry-run > resolution.json` → `terramate list --json > stacks.json` → `archetypectl enrich stacks.json`. |
| **`mise`** | Gestor de fijación de versiones de herramientas (`mise.toml`, `jdx/mise-action`) que fija las versiones de Terramate, OpenTofu y Checkov de forma consistente entre las máquinas de los desarrolladores y CI. |

---

## 17. Fases del roadmap

| Fase | Foco |
|---|---|
| **Fase 0** | Validar suposiciones — un pico de una semana en un repositorio desechable que confirma: `from_stack_id` resuelve un global heredado y acepta interpolación; `stack.after` resuelve rutas derivadas de globals o recurre a filtros de etiqueta (y falla en silencio si no — probarlo deliberadamente); el comportamiento de `--mock-on-fail`; lecturas de estado entre proyectos/cuentas con roles OIDC; alcanzabilidad del plano de control privado desde el tipo de runner elegido. **Es el trabajo de una tarde y condiciona todo lo demás.** |
| **Fase 0b** | Esqueleto del resolver — validación por JSON Schema, pasos de resolución 1–8 (sin escrituras del ledger), demostrando que un `binding.tm.hcl` generado por el resolver hace funcionar `terramate generate` sin cambios. |
| **Fase 1** | Una cloud, una plataforma compartida — configuración raíz, `sharing_backend`, mixins, `gen_network`/`gen_cluster`, primera plataforma de demos, workflows de preview/deploy con G0/G1, una instancia de arquetipo. |
| **Fase 2** | Segunda cloud — segundo conjunto de mixin/generador que demuestra que los ficheros de contrato son agnósticos de cloud; añade el escaneo de plan G2 y permission boundaries. |
| **Fase 2a** | Paridad de Azure — arquetipos de landing-zone/environment/AKS, la decisión CNI Overlay frente a tradicional (tomada antes del primer cluster, ya que es inmutable), la elección de borde (AGFC BYO o Envoy Gateway detrás de un LB interno, no ambos), y una prueba de aceptación de que un manifiesto de app de capa 5 se despliega en Azure sin editar. |
| **Fase 2b** | Runtimes serverless — ramas de generador para Cloud Run y ECS Fargate tras un switch `global.platform.runtime`, reutilizando los stacks de red/datos existentes. |
| **Fase 2c** | Capa de políticas — en subfases: registro → `archetypectl enrich` → G1 informativo → G1 bloqueante → tests de política → Gatekeeper en la capa 2b (primero en efímero, dryrun, promoción gradual). |
| **Fase 3** | Multi-tenancy — segunda/tercera instancia de plataforma compartida, generación de namespace/quota/NetworkPolicy, salvaguardas de destrucción. |
| **Fase 4** | Entornos dedicados y CMDB — plataformas `prod` dedicadas por cloud, la matriz de globals de promoción, sincronización de los niveles 1–2 de la CMDB, workflow de drift. |
| **Fase 5** | Endurecimiento — ensayo de migración de generadores `v2`, runbooks de break-glass, proceso de deprecación de contratos. |

---

## 18. Guía del desarrollador — modelo de repositorio y manifiesto

| Término | Definición |
|---|---|
| **Monorepo por aplicación** | Un repositorio contiene todos los servicios de una aplicación, así que un cambio de contrato entre servicios es una versión, un PR, una ejecución de CI. |
| **Stack** (sentido de la guía del desarrollador) | Uno por servicio dentro de una aplicación; `stacks[].after` da el orden de despliegue. |
| **`hasFrontend`** | Un predicado `condition:` verdadero cuando hay un bloque `frontend` en el manifiesto; una aplicación sin UI no genera stack `web` ni reclama hostname. |
| **`libs/`** | Directorio de código compartido; cualquier servicio que lo liste en `build.deps` se reconstruye cuando cambia — una librería demasiado gruesa dispara reconstrucciones innecesarias. |
| **`archetype-manifest.schema.json`** | El JSON Schema del manifiesto, `additionalProperties: false`, generado desde `registry/`; extender el manifiesto (p. ej. añadir `language: java17`) exige extender antes este esquema. |
| **Las especificaciones de build y deploy extienden `manifest.yaml`** | Decisión asentada: un `build.yaml`/`deploy.yaml` paralelo es un tercer sitio donde declarar la misma dependencia, y diverge. |
| **Detección de cambios** | `git diff --name-only <merge-base>..<head>` mapeado sobre `build.context`/`build.deps` para decidir qué servicios se reconstruyen; una ruta sin correspondencia reconstruye todo (a prueba de fallos). |
| **Bloque capacity** | Sección del manifiesto (cpu, memoria, conexiones de BD, rutas de ingress, identidades de workload) tratada como un consumo de presupuesto contra el entorno compartido; el resolver suma el consumo de todos los tenants y falla el PR si se excede el total. |
| **Revisión de plataforma para aumentos de capacity en entornos compartidos** | Decisión asentada: subir `capacity` en un entorno compartido necesita revisión del equipo de plataforma (solo el resolver ve el consumo de todos los tenants); un entorno dedicado no necesita ninguna. |

---

## 19. Ramas, entornos y GitFlow

| Rama | Despliega en | Notas |
|---|---|---|
| **`feature/*`** | Nada (solo previsualización de PR) | Previsualización de PR completa: build, tests, escaneo de imagen, `archetypectl resolve --dry-run`, `tofu preview` con mocks. Nada se aplica salvo que se solicite explícitamente un entorno `ephemeral-*`. |
| **`develop`** | `dev`, automáticamente al hacer merge | Tag de imagen `2.5.0-dev.<n>.g<sha>`. |
| **`release/x.y`** | `qa`, automáticamente | Tag de imagen `2.5.0-rc.<n>`. |
| **`main`** | `prod`, solo con un tag `vX.Y.Z` | Aprobación manual vía un GitHub Environment `production` con revisores obligatorios; la imagen se **promueve** (se retagea), nunca se reconstruye. |
| **`hotfix/*`** | `qa` y luego `prod` | Ruta rápida desde `main`, saltándose `develop`/release pero no `qa`, ni el escaneo de imagen, ni la aprobación de producción. Debe hacerse merge de vuelta a `main` **y** `develop` (y cualquier `release/x.y` abierta); una puerta de CI bloquea el merge a `main` hasta que exista el PR de merge de vuelta a `develop`. |

| Término | Definición |
|---|---|
| **GitFlow** | El modelo de ramas usado; la rama por sí sola decide el entorno de despliegue — no hay un botón "desplegar esta rama a prod". |
| **Entorno `ephemeral-*`** | Un entorno temporal por solicitud, reclamado contra la supernet efímera; se destruye al cerrar el PR. |
| **Puerta de promoción** | Se niega a desplegar en `prod` un digest sin un despliegue exitoso registrado en `qa` — hace que "promovido, no reconstruido" sea exigible. |

---

## 20. Versionado y release

| Término | Definición |
|---|---|
| **`metadata.version`** | La única versión del arquetipo, a nivel de toda la aplicación (no por servicio); generada a partir del tag de Git y committeada para que el manifiesto sea legible por Terramate; nunca escrita a mano. |
| **`archetypectl version --check`** | Puerta de CI que recalcula la versión a partir de la referencia de Git y falla si `metadata.version` difiere del tag. |
| **Una versión por aplicación, no por servicio** | Decisión asentada: un esquema por servicio hace que "qué corría junto el martes" no tenga respuesta y elimina el objetivo del rollback. |
| **Conflicto semver/tag OCI** | `+` es legal en semver pero ilegal en el conjunto de caracteres del tag de imagen OCI (`[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}`); el pipeline sustituye `+` por `.` al derivar el tag de imagen. |
| **Reglas de subida de versión** | **MAJOR** — endpoint eliminado/cambiado, cambio de contrato de capability provista, o cualquier migración irreversible (aunque el diff sea de una línea). **MINOR** — adiciones retrocompatibles, migraciones en fase de expand, servicios nuevos, rangos de `requires` ampliados. **PATCH** — corrección de bugs, subidas de dependencias, cambios de capacity/recursos sin cambio de contrato. Sin release para cambios solo de docs/tests/CI. |
| **Migración irreversible** | Un cambio de esquema (`DROP COLUMN`, `DROP TABLE`, una adición de `NOT NULL`, un cambio de tipo que estrecha) que elimina permanentemente la capacidad de ejecutar una versión anterior de la aplicación contra la base de datos; siempre es una subida MAJOR, sin importar el tamaño del diff. |
| **Regla de re-tagging** | Todo servicio de la aplicación lleva el tag de versión de la aplicación tras cada release, se haya reconstruido o no — ninguna aplicación tiene nunca servicios con tags no coincidentes. |
| **`release.lock.json`** | Lockfile generado por el pipeline que mapea cada servicio a su digest de imagen desplegado, committeado junto a cada tag de release; un servicio no reconstruido copia su digest del lockfile del release anterior. |
| **Promoción de imagen** | Retagear una imagen en el registro (`docker buildx imagetools create`) en vez de reconstruirla — 200–500 ms, cero bytes transferidos, el digest (y la firma cosign, SBOM, procedencia) se preservan. |
| **Digest frente a tag** | El digest es la identidad inmutable de una imagen y lo que se despliega; el tag es un alias mutable, de cara al humano. "Desplegar por digest, nunca por tag" es una decisión asentada. |
| **El frontend es nginx en el cluster, no bucket + CDN** | Decisión asentada: mismo Gateway, hostname, certificado, `HTTPRoute`, `SecurityPolicy` y observabilidad que todo lo demás. Un bucket necesita una segunda ruta de borde y un segundo modelo de identidad. |

---

## 21. Rollback

| Mecanismo | Definición |
|---|---|
| **Redesplegar un digest de imagen anterior** | El rollback principal y barato: un cambio de imagen de contenedor más un rolling update, 30–90 s, reversible, radio de impacto limitado al servicio. Requiere que el código antiguo todavía pueda correr contra el esquema actual de la base de datos. |
| **`helm rollback`** | Restaura el manifiesto de release de Helm anterior (más que solo la imagen), 1–5 min. Los hooks se vuelven a ejecutar (problemático para migraciones), los CRD no se revierten, y los cambios en campos inmutables pueden fallar a mitad del rollback, dejando un tercer estado inconsistente. |
| **`tofu apply` de un commit anterior** | Revertir el código de infraestructura y volver a aplicar — **no** es reversible y puede destruir recursos (revertir un commit que "añadió un recurso" planea un `destroy`; revertir un cambio `ForceNew` planea destruir-y-luego-crear). Nunca usarlo como respuesta a un incidente; en su lugar, "avanzar" (roll forward). |
| **Atributo `ForceNew`** | Un atributo de recurso cuyo cambio fuerza la sustitución del recurso (destruir y luego crear) en vez de una actualización in situ. |
| **Campos inmutables** | Campos (p. ej. el `Deployment.spec.selector` de Kubernetes, el tamaño de una PVC) que no pueden cambiarse/revertirse in situ — intentar revertirlos con `helm rollback` falla a mitad de camino. |
| **"Revertir un merge no deshace una migración"** | La trampa clave del rollback: revertir código vía Git deja la base de datos en el esquema nuevo, así que el código revertido (antiguo) corre entonces contra un esquema que no espera — una release rota se convierte en una release rota más una ruta de rollback rota. Alguien lo intentará de todos modos. |
| **Una migración no tiene rollback en absoluto** | La razón declarada por la que existe expand-contract, y por qué las migraciones se separan del despliegue. |

---

## 22. Migraciones y expand-contract

| Término | Definición |
|---|---|
| **Migraciones como stack separado** | Las migraciones corren como su propio stack (`phase: pre-deploy`) con su propia aprobación de producción — nunca dentro del entrypoint de la aplicación, un `initContainer`, o un hook `pre-upgrade` de Helm (cada uno compite con varias réplicas o se vuelve a ejecutar en un rollback). |
| **Expand-contract** | Divide todo cambio de esquema entre releases de modo que, en todo momento, tanto el código actualmente desplegado como el del release anterior funcionen contra el esquema actual. **N (expand)**: añadir columna/tabla/índice anulable, el código escribe en ambos / lee el antiguo — seguro para rollback. **N+1 (migrate)**: el código lee el nuevo, todavía escribe en ambos — seguro para rollback. **N+2 (contract)**: eliminar la columna antigua, el código lee/escribe solo el nuevo — **no** es seguro para rollback, el punto de subida MAJOR. |
| **Regla de tiempos de la fase contract** | Contract nunca debe ir en el mismo release que el código que dejó de escribir en la columna antigua — como mínimo un release completo de margen, y no antes de que haya pasado la ventana de rollback de producción de 14 días de N+1. |
| **Backfill en lotes** | El backfill de datos durante una migración de expand debe hacerse en lotes por clave primaria, con commits acotados, reanudables e idempotentes, ya que un único `UPDATE` grande mantiene un bloqueo y puede ser matado a mitad de transacción por el timeout de un job. |
| **Alembic** | La herramienta de migración de Python usada. Reglas: revisar a mano toda migración autogenerada (se le escapan los valores por defecto del servidor, los renombrados de constraint, algunos cambios de tipo, y puede emitir `DROP`s no deseados); mantener exactamente una cabeza de migración (`alembic heads` en CI); que exista `down_revision`/`downgrade()` no significa que un rollback sea seguro para los datos; tomar un bloqueo de aviso de PostgreSQL (`pg_advisory_lock`) al empezar la migración para protegerse de reintentos duplicados. |

---

## 23. Java / JVM

| Término | Definición |
|---|---|
| **Lockfile (Java)** | El `gradle.lockfile` de Gradle (vía `dependencyLocking`) o `verification-metadata.xml`, o el `lockfile.json` de Maven (vía `maven-lockfile`) / reglas de `maven-enforcer` (`banDynamicVersions`, `requireReleaseDeps`) — garantiza builds reproducibles para que se sostenga la promesa del digest en la detección de cambios. |
| **`startupProbe`** | Debe usarse en vez de `livenessProbe.initialDelaySeconds` para servicios de arranque lento (Spring Boot, 20–45 s); solo tras pasarlo empieza el liveness probe, evitando un `CrashLoopBackOff` falso. |
| **`livenessProbe` / `readinessProbe`** | Sondas de salud estándar de Kubernetes; ajustadas a 10/3/2 y 5/2 respectivamente para Java, activas solo tras pasar el `startupProbe`. |
| **`-XX:MaxRAMPercentage` / `-XX:InitialRAMPercentage`** | Flags de la JVM que fijan el tamaño del heap como un porcentaje del límite de memoria del contenedor (75.0–80.0 recomendado) en vez de un `-Xmx` fijo, así el heap escala con el límite de memoria del pod dejando sitio para el non-heap. |
| **Memoria non-heap** | Memoria de la JVM fuera del heap: metaspace (128–256 MiB), code cache (64–240 MiB), pilas de hilos (1 MiB cada una), direct byte buffers, estructuras del GC — no es opcional, no se cuenta en `-Xmx`. |
| **OOMKill** | Contenedor matado por el kernel (`SIGKILL`, código de salida 137, `OOMKilled` en `kubectl describe pod`) sin nada registrado por la aplicación — el kernel no da al proceso ninguna oportunidad de escribir nada antes de matarlo. |
| **Bug de memoria del host en cgroups v2** | En versiones de JDK anteriores a 8u372, 11.0.16 o 15, `UseContainerSupport` puede recaer en silencio en dimensionar el heap de la JVM a partir de la memoria del *host* en vez del límite del contenedor/cgroup, causando un heap sobredimensionado que solo falla cuando crece. |
| **`MaxRAMPercentage` por defecto (25%)** | Sin una flag explícita, una JVM moderna fija el heap por defecto al 25% del límite del contenedor, desperdiciando la mayor parte de la memoria asignada hasta que se acumula presión de GC. |
| **`-Xmx` fijado al límite completo** | Una corrección intuitiva pero equivocada: un heap máximo igual a todo el límite de memoria no deja nada para los 250–400 MiB de non-heap, así que el RSS supera el límite bajo carga. |
| **Selección de SerialGC bajo `limits.cpu: 1`** | La ergonomía de la JVM elige el SerialGC monohilo cuando ve menos de 2 CPU (o por debajo de ~1792 MB), causando pausas stop-the-world largas; mitigado fijando explícitamente `-XX:+UseG1GC`. |
| **`requests.memory == limits.memory` (JVM)** | Requerido porque la JVM se dimensiona a partir del límite; una request más baja permite al scheduler sobresuscribir el nodo, arriesgando el desalojo bajo presión de memoria. |
| **Tres rutas distintas de OOMKill** | Todas con salida 137 y nada en el log de la aplicación: (1) una JVM anterior a 8u372/11.0.16 en un nodo cgroups v2 que lee la memoria del host; (2) el valor por defecto del 25% sin flag; (3) `-Xmx` fijado a todo el límite sin dejar nada para el non-heap. |

---

## 24. Python

| Término | Definición |
|---|---|
| **`uv.lock`** | Lockfile obligatorio committeado para las dependencias de Python; `uv lock --check` falla CI si está desactualizado, y la imagen instala vía `uv sync --frozen --no-dev`, instalando exactamente lo que especifica el lock sin volver a resolver. |
| **Imagen multi-stage (Python)** | Etapa de build (`uv` + toolchain del compilador) separada de una etapa de runtime ligera; reduce el tamaño de la imagen de ~1,1 GB a ~180 MB y elimina el toolchain del compilador (y sus CVE) de la imagen enviada. |
| **`UV_COMPILE_BYTECODE`** | Flag de build que precompila ficheros `.pyc` en tiempo de build, recortando latencia de la primera petición de cada worker. |

---

## 25. Frontend Node / React

| Término | Definición |
|---|---|
| **`nginxinc/nginx-unprivileged`** | Una variante de imagen nginx que corre como uid 101, escuchando en el puerto 8080 (no root/puerto 80) — requerida porque el nginx de serie no puede satisfacer PSS `restricted` (`runAsNonRoot`, sin binding a puertos privilegiados, `readOnlyRootFilesystem`). Usar el nginx de serie hace que el pod sea rechazado en la admisión. |
| **PSS `restricted`** | El Pod Security Standard de Kubernetes forzado vía la etiqueta de namespace `pod-security.kubernetes.io/enforce`; requiere `runAsNonRoot: true`, capabilities eliminadas (sin `NET_BIND_SERVICE` para puertos <1024), etc. |
| **`readOnlyRootFilesystem`** | Requiere que las rutas escribibles (`/var/run`, `/var/cache/nginx`, `/tmp` de nginx) se monten como volúmenes `emptyDir` en vez de escribirse en el sistema de ficheros del contenedor. |
| **`env.js` (configuración en tiempo de ejecución)** | El patrón correcto: un script de entrypoint del contenedor escribe valores de `window.__ENV__` en `env.js` al arrancar el contenedor, a partir de variables de entorno tomadas de globals resueltos — produciendo **una sola imagen** utilizable en todos los entornos. |
| **`VITE_API_URL` (env en tiempo de build, antipatrón)** | Incrustar una URL en el bundle en el momento de `npm run build` vía `import.meta.env` de Vite — produce una imagen (y digest) distinta por entorno y rompe la promoción de imagen, ya que el artefacto probado en `qa` diferiría del desplegado en `prod`. |
| **Cache-Control (asimétrico)** | `index.html` y `/config/env.js` (sin hash, específicos del entorno) reciben `no-store, must-revalidate`; los ficheros con hash bajo `/assets/` reciben `public, max-age=31536000, immutable`. Invertir esto hace que un deploy parezca fallar en silencio o sirva chunks rotos. |
| **`try_files $uri /index.html`** | Directiva de nginx que sirve `index.html` como fallback para que las rutas del lado del cliente (React Router) funcionen al recargar/enlace directo — debe acotarse para que no se aplique dentro de `/assets/`, donde un fichero ausente debería dar 404 (`try_files $uri =404;`) en vez de producir un error de parseo de módulo `Unexpected token '<'`. |
| **`npm ci` frente a `npm install`** | `npm ci` falla el build si el lockfile está desincronizado con `package.json`; `npm install` reescribiría el lockfile en silencio, rompiendo la reproducibilidad. |
| **Los cuatro detalles del frontend en el primer despliegue** | `nginxinc/nginx-unprivileged` frente a PSS `restricted`/`readOnlyRootFilesystem` (bloquea sin más); `env.js` en tiempo de ejecución frente a `VITE_API_URL` en tiempo de build (bloquea sin más, mata la promoción); `Cache-Control` asimétrico; `try_files $uri /index.html`. Los dos últimos se despliegan con éxito y están rotos de todos modos — el modo de fallo peor. |

---

## 26. Registro de riesgos (`risk-register.md`) — 53 riesgos por dominio (52 activos)

Cada riesgo tiene un número R estable y nunca reutilizado, una probabilidad, un impacto y una mitigación ligada a una sección del documento.

| ID | Riesgo |
|---|---|
| **R1** | Outputs Sharing es experimental — la semántica de bloque de Terramate puede cambiar. Mitigado fijando la versión de Terramate y centralizando los contratos en `imports/contracts/`. |
| **R2** | Falta `after` en un stack consumidor — un orden de dependencia sin resolver aplica en silencio un valor de salida compartida obsoleto/incorrecto, sin ningún error. **Riesgo mejor clasificado.** Mitigado por la política bloqueante G1 de conftest. |
| **R3** | Los mocks se filtran a un despliegue. Mitigado con scripts separados de preview/deploy, la convención del prefijo `mock-`, y un grep posterior al apply que busque `mock-` en las salidas. |
| **R4** | Los mocks con el tipo equivocado pasan la validación en preview pero fallan en el apply. Mitigado con una checklist de revisión de código y mocks con el tipo correcto. |
| **R5** | Una plataforma compartida destruida por el desmontaje de una instancia a través de un selector de destroy equivocado, tumbando a todos los tenants. Puesto 5 de los principales riesgos. Mitigado con una etiqueta `protected`, una comprobación del selector de destroy, y un recuento de referencias en la CMDB. |
| **R6** | Renombrar una salida del productor rompe a N consumidores. Mitigado tratando las salidas como un contrato versionado (añadir la nueva junto a la vieja, deprecar en dos releases) y usando el grafo de relaciones de la CMDB para encontrar a los consumidores afectados. |
| **R7** | Faltan permisos de lectura de estado entre cuentas en la primera configuración, causando fallos ruidosos de CI. Mitigado documentando las concesiones necesarias y probándolo en el PoC. |
| **R8** | Secreto filtrado a través de `TF_VAR_*` por compartir valores en vez de referencias. Mitigado no compartiendo nunca valores de secreto, más una puerta de política/grep para patrones de secreto en las salidas. |
| **R9** | Código generado editado a mano, revertido en silencio por el siguiente `terramate generate`. Mitigado por la puerta G0 más `CODEOWNERS` que exige aprobación del equipo de plataforma en los ficheros generados. |
| **R10** | Las comparativas de Terramate frente a Terragrunt de origen de proveedor están exageradas (a menudo publicadas por el propio Terramate). Mitigado validando de forma independiente las afirmaciones de detección de cambios y outputs sharing en el PoC. |
| **R11** | Reconstruir el cluster invalida todo binding IRSA/WI en una plataforma compartida. Mitigado tratando la sustitución del cluster como un evento de flota, una lista de consumidores en la CMDB, y ensayándolo en un entorno efímero. |
| **R12** | Un `sub` comodín en una política de confianza OIDC permite que cualquier PR de rama o fork asuma el rol de apply cloud — la configuración incorrecta de OIDC en AWS más común. Puesto 2 de los principales riesgos. Mitigado con `StringEquals` sobre el `repo:ORG/REPO:environment:ENV` exacto. |
| **R13** | Un rol de ejecución de tarea compartido en un cluster ECS multi-tenant puede leer los secretos de todos los tenants. Mitigado con un rol de ejecución por instancia. |
| **R14** | Un servicio de Cloud Run desplegado con `ingress = ALL` evita Cloud Armor, el WAF y los logs de acceso. Mitigado con un global seguro por defecto, una assertion, y la política de organización de GCP `constraints/run.allowedIngress`. |
| **R15** | Un binding de identidad de workload escrito con comodín (`POOL[*/*]`, `system:serviceaccount:*:*`) concede el rol a todos los pods del cluster. Mitigado generando los bindings desde `global.platform.namespace` y una política Checkov que rechaza los comodines. |
| **R16** | Omitir el permission boundary en un rol IAM creado por un tenant permite la escalada de privilegios. Mitigado con la plataforma publicando `task_role_boundary_arn` y una assertion que bloquea la generación sin él. |
| **R17** | Una clave de cifrado de estado acotada por stack bloquea outputs sharing (los consumidores no pueden descifrar el estado del productor). Mitigado con una clave de cifrado de estado por entorno, no por stack. |
| **R18** | Plano de control privado inalcanzable desde runners alojados por GitHub. Resuelto decidiendo entre runners self-hosted o una concesión de red autorizada en la fase 0. |
| **R19** | Usar la cuenta de servicio por defecto como identidad de workload arriesga permisos amplios (p. ej. Editor del proyecto). Mitigado con una identidad dedicada por workload, forzada por política. |
| **R20** | El NEG de GCP no está en el estado de Terraform, haciendo falsa la afirmación de "todo en IaC". Mitigado declarándolo como fuente `data`, nombrándolo explícitamente, y registrando el hueco en el manifiesto del arquetipo. |
| **R21** | `TargetGroupBinding` deja que un tenant redirija el tráfico de otro en EKS compartido. Mitigado con RBAC que deniega el CRD a los namespaces de aplicación y restringe la creación al arquetipo `gateway`. |
| **R22** | El ciclo de arranque Keycloak ↔ Gateway puede provocar un interbloqueo en el primer arranque en frío. Mitigado con el `HTTPRoute` de Keycloak sin llevar `SecurityPolicy` y el descubrimiento OIDC resolviéndose vía el Service interno del cluster. |
| **R23** | La no transitividad del peering de VPC en GCP bloquea el LB del hub → NEG del spoke si el hub-and-spoke usa VPC separadas. Resuelto con Shared VPC, Network Connectivity Center, o un balanceador por spoke — decidido en la fase 0. |
| **R24** | `kubernetes_manifest` rompe las previsualizaciones de PR (requiere que el CRD/API server sean alcanzables en tiempo de plan). Mitigado empaquetando los CR en el chart Helm del arquetipo y desplegando vía `helm_release`. |
| **R25** | El `kube_config` de AKS acaba en el estado como credencial. Mitigado con `local_account_disabled = true` más autenticación Entra (Azure AD). |
| **R26** | Rango secundario de pods dimensionado para pocos nodos — inmutable tras crear el cluster, así que el cluster no puede crecer sin una reconstrucción completa. Puesto 3 de los principales riesgos. Mitigado con el valor por defecto de 64 pods por nodo, una comprobación del resolver que rechaza `max_nodes × bloque > rango`, una /16 para producción, o Azure CNI Overlay. |
| **R27** | El pool del entorno se fragmenta en /17 inutilizables con el tiempo. Mitigado con asignación por pares que prefiere bloques que preservan tiradas libres más grandes, y aislando la supernet efímera. |
| **R28** | *Retirado* — duplicado de R26, fusionado ahí. El número no se reutiliza. |
| **R29** | Bus Kafka compartido saturado por un tenant en `demos`. Mitigado con cuotas de productor/consumidor por `KafkaUser` y un presupuesto de `kafka_partitions` forzado en el PR. |
| **R30** | Un tenant escribe topics de Kafka sin prefijo, arriesgando colisiones de nombre. Mitigado con un prefijo obligatorio `{{ instance }}-` y ACL derivadas por el arquetipo `kafka`, nunca escritas a mano. |
| **R31** | Los arquetipos demo se acumulan más allá de su utilidad. Mitigado con un `expiresOn` obligatorio y un job programado que abre un PR de destrucción (aprobado por humano). |
| **R32** | Cada demo aprovisiona su propia base de datos gestionada si `database-platform` no está enlazado, socavando la eficiencia de coste. Mitigado enlazando `database-platform` en entornos compartidos con stacks `data`/`data-tenant` condicionales (salvo deliberadamente en `demos` — ver §1). |
| **R33** | El webhook de Gatekeeper caído con `failurePolicy: Fail` rechaza toda admisión del cluster, incluida la propia recuperación de Gatekeeper. Mitigado con `exemptNamespaces`, ≥3 réplicas con un PDB, y una política de fallo `Ignore` en todas partes salvo producción. |
| **R34** | La divergencia del registro entre JSON Schema, los datos de conftest y los valores de Gatekeeper bloquea despliegues legítimos en la admisión — el peor sitio para descubrirlo. Puesto 4 de los principales riesgos. Mitigado tratando el registro como fuente única y una puerta bloqueante `registry-generate --check`. |
| **R35** | Se adopta un add-on de política gestionado y luego hacen falta templates personalizados, pero ambos son mutuamente excluyentes. Mitigado estandarizando en Gatekeeper autogestionado en las tres clouds, con un trait `custom-templates`. |
| **R36** | Una regla Rego se escribe pero nunca se dispara, produciendo falsa confianza. Mitigado ejecutando `conftest verify` sobre `policy/*_test.rego` en el mismo job de CI que la puerta. |
| **R37** | Se asume que los runtimes serverless tienen la misma cobertura de políticas que los runtimes de Kubernetes, pero ahí no existe la capa de admisión. Mitigado declarando explícitamente el hueco de paridad de cobertura, con la política del plano de control cloud sustituyendo al control de admisión. |
| **R38** | Las redes autorizadas de GKE se editan por cada job de CI: jobs concurrentes se sobrescriben la entrada y un runner muerto deja su IP abierta. Mitigado con un único grupo de `concurrency`, un paso de cierre `if: always()` y un reconciliador que caduca entradas obsoletas. |
| **R39** | `container.clusters.update` concedido a una identidad de pipeline para abrir la IP del runner — permite que cualquier PR reconfigure el cluster. Mitigado con un servicio intermedio mínimo que solo abre y cierra una /32. |
| **R40** | Valores de secreto guardados en el estado de OpenTofu, convirtiendo el estado en un segundo almacén de secretos. Mitigado con recursos ephemeral y atributos write-only. |
| **R41** | Destrucción de la clave de cifrado de estado del entorno; GCP carece de un equivalente escrito de la SCP de AWS. Mitigado sin permiso de destrucción para pipelines, `prevent_destroy` y una duración mínima programada de destrucción. |
| **R42** | Caduca la credencial de federación del IdP (Keycloak en el IdP superior) y nadie puede iniciar sesión. Mitigado con una credencial de certificado y una alerta de caducidad al equipo propietario. |
| **R43** | Un usuario dado de baja conserva tokens de la aplicación cuando no hay SCIM. Mitigado con reconciliación diaria y sin tokens personales en CI. |
| **R44** | `SecurityPolicy` OIDC aplicada a una ruta que también sirve a clientes máquina con tokens portador. Mitigado con una assertion del generador para arquetipos que se autentican a sí mismos. |
| **R45** | El timeout por defecto de 30 s del LB de Application externo de GCP causa 502 intermitente en subidas grandes. Mitigado con un timeout explícito en el stack de borde. |
| **R46** | El chart Helm de origen trae un init container privilegiado o como root. Mitigado desactivándolo y trasladando el requisito al nodo, expresado como un trait. |
| **R47–R53** | SonarQube en `qa`: saturación de la cola del compute engine, un análisis de pull request registrado como `main`, OOMKill multi-JVM, pérdida de la clave de cifrado de settings, token global de análisis filtrado, migración de upgrade irreversible, pérdida del volumen zonal. Ver `risk-register.md` §8. |

**Los cinco principales riesgos** (ordenados por probabilidad × impacto, mitigación aún no implantada): 1) R2 (falta `after`), 2) R12 (`sub` comodín OIDC), 3) R26 (rango de pods dimensionado para pocos nodos), 4) R34 (divergencia del registro), 5) R5 (plataforma compartida destruida al desmontar una instancia).

---

## 27. Preguntas todavía abiertas (aún sin zanjar — ver `CLAUDE.md`)

| # | Pregunta |
|---|---|
| 1 | ¿Es `max_pods_per_node` configurable en GKE Autopilot? El valor por defecto de 64 lo asume. |
| 2 | ¿Shared VPC o VPC separadas en GCP? La no transitividad del peering más la regla del backend en la misma VPC pueden forzar Shared VPC (riesgo R23). **Zanjado para `qa`: VPC separada.** Abierto para `demos` y cualquier entorno cuyo borde se sitúe en el hub. |
| 3 | Techo de particiones de Kafka sobre el número de brokers previsto — el presupuesto de 4000 en el binding de `demos` es un valor provisional. |
| 4 | ¿Dónde corre la resolución — una CLI en el repo, o un workflow reutilizable? Determina si la oficina de proyecto puede validar una demo localmente. |
| 5 | ¿Cuánto Rego se comparte genuinamente entre conftest y los `ConstraintTemplate`s — medirlo antes de planificar una única base de código de políticas. |
| 6 | Preguntas abiertas de la guía del desarrollador: herramienta de andamiaje frente a repositorio plantilla, dónde se calcula la subida de versión, entornos efímeros opt-in o automáticos. |
