# Kafka en `qa` — arquetipo `kafka` (capa 4), proveedor de `event-bus`

| | |
|---|---|
| **Estado** | Propuesta · revisión 1 |
| **Alcance** | El arquetipo de capa 4 `kafka` en `qa`: operador, topología KRaft, almacenamiento y zonas, autenticación mTLS con la CA interna, el contrato multi-tenant (topics, usuarios, ACLs y cuotas), capacidad, red, acceso desde fuera del cluster, observabilidad, stacks, políticas, ejecución y plan |
| **Por qué ahora** | AM §10 define Kafka como el bus común con datos separados, pero solo como ejemplo en `demos`. `qa` no lo tiene enlazado. Con la CA interna (cert-manager DT10) y el patrón B de exposición L4 (Envoy Gateway §4.4) ya decididos, se puede fijar cómo se autentica un cliente y cómo sale el bus del cluster |
| **Especificación de referencia** | `archetype-model.md` (AM §n), `terramate-outputs-sharing-architecture.md` (§n), `risk-register.md` |
| **Diagramas** | `diagrams/*.mmd` (fuente Mermaid) y `diagrams/*.svg` (renderizados). El SVG se regenera desde el `.mmd`; no se edita a mano. `diagrams/06-bloques-presentacion.svg` (1920×1080, para presentaciones) se genera con `06-bloques-presentacion.py`, no con Mermaid |
| **Identificadores propios** | Decisiones `DB1…`, riesgos candidatos `RB1…`, verificaciones `VB1…`, preguntas `Q-B1…`. Los riesgos reciben número `R54+` en `risk-register.md` si se adopta, detrás de los de las propuestas anteriores |

Nada de este documento reabre decisiones de `CLAUDE.md`: Kafka es un arquetipo, no un componente; bus común y datos separados; prefijo obligatorio, ACLs derivadas y cuotas de `KafkaUser` (AM §10.2, R29, R30).

![Arquetipo kafka en bloques](diagrams/06-bloques-presentacion.svg)

Fuente: [`diagrams/06-bloques-presentacion.py`](diagrams/06-bloques-presentacion.py) — vista de presentación; el detalle está en §2–§10.

---

## 0. Contexto

| Pregunta | Respuesta | Consecuencia |
|---|---|---|
| Qué es | Arquetipo `kafka`, `kind: catalog`, **capa 4**, provee **`event-bus` 2.1.0** | El binding de `qa` gana `event-bus: { archetype: kafka, version: 2.1.0, stack_id: gcp-qa-kafka }` (§12) |
| Entorno | `qa` (dedicado). El contrato es el mismo que en `demos`; §11 recoge lo que cambia allí | En `qa` también conviven varias aplicaciones: el contrato multi-tenant aplica igual |
| Stacks | 4: `iam`, `operator`, `cluster`, `policy` en `stacks/archetypes/kafka/` | El operador y el cluster tienen ciclos de vida distintos (§8.2) |
| Componentes | Strimzi (Cluster Operator, Entity Operator con Topic y User Operator), Kafka en modo KRaft, Kafka Exporter, Cruise Control | Todo Apache-2.0 |
| Clientes | Aplicaciones del cluster por **mTLS con la CA interna**; de fuera, solo con una excepción de patrón B | §3, §6 |
| Qué **no** hace | Schema registry, Kafka Connect, MirrorMaker, Kafka Bridge como servicio de tenants | §7.1 |

![Contexto](diagrams/01-contexto.svg)

Fuente: [`diagrams/01-contexto.mmd`](diagrams/01-contexto.mmd)

---

## 1. El operador

| Opción | Veredicto |
|---|---|
| **Strimzi** | **Sí**. Es el operador que ya fijan AM §10 y los traits `strimzi` y `kraft`. CNCF, Apache-2.0, y `KafkaTopic` y `KafkaUser` son justo los tenant resources del contrato |
| Kafka gestionado (Confluent Cloud, Managed Service for Apache Kafka de Google) | No en este arquetipo. Sería otro proveedor de `event-bus`, con otro contrato: las ACLs y cuotas no serían CRDs en el cluster |

| Ajuste | Valor | Motivo |
|---|---|---|
| Ámbito del operador | `watchNamespaces: [kafka]` | Solo ve su namespace. Un `Kafka` creado en otro namespace no existe para él |
| CRDs | `helm.sh/resource-policy: keep` | Borrar el CRD `KafkaTopic` borra todos los `KafkaTopic`, y el Topic Operator borra los topics en Kafka (RB2) |
| Versión | La última de Strimzi que soporte la versión de Kafka elegida y de Kubernetes de `qa` **(verificar, VB10)** | Strimzi publica cada versión con un rango de Kafka soportado |

---

## 2. El cluster

![Topología](diagrams/05-topologia.svg)

Fuente: [`diagrams/05-topologia.mmd`](diagrams/05-topologia.mmd)

### 2.1 Topología

| Ajuste | `qa` | Motivo |
|---|---|---|
| Modo | **KRaft**, sin ZooKeeper | Trait `kraft`; ZooKeeper ya no existe en Kafka 4 |
| `KafkaNodePool` | Uno, `dual`, **3 nodos con los roles `controller` y `broker`** | En `qa` basta: quórum de 3 y 3 réplicas. En `prod` y `demos`, pools separados de controladores y brokers (§11) |
| Zonas | Un nodo por zona de `europe-west1`; `rack.topologyKey: topology.kubernetes.io/zone` | Kafka reparte las réplicas de cada partición en zonas distintas: perder una zona no pierde datos |
| Node pool de GKE | **`kafka`**: 3 × `n2-standard-4` (4 vCPU, 16 GB), uno por zona, taint `dedicated=kafka:NoSchedule` | Kafka vive de la caché de páginas del sistema: compartir nodo con otras cargas la vacía. Requisito nuevo a E1 §4.1 (§12) |
| Recursos por nodo Kafka | Petición 2 CPU / 8 GiB; límite de memoria 12 GiB; heap `-Xms4g -Xmx4g` | Heap fijo y pequeño; el resto de la memoria es caché de páginas. Nunca `-Xmx` igual al límite (DG §8.3) |

### 2.2 Almacenamiento

| Ajuste | Valor | Motivo |
|---|---|---|
| Tipo | `jbod` con un volumen `persistent-claim` por nodo, 200 GiB | Punto de partida; lo fija `kafka_storage_gib` (§5) |
| StorageClass | La de E1 §4.1, `WaitForFirstConsumer`, `allowVolumeExpansion: true` | El disco se crea en la zona del pod |
| `deleteClaim` | `false` | Borrar el `Kafka` no borra los datos |
| Tiered storage | No | Trait `tiered-storage` no ofrecido |

### 2.3 Valores por defecto del broker

| Parámetro | Valor | Motivo |
|---|---|---|
| `default.replication.factor` | 3 | Una réplica por zona |
| `min.insync.replicas` | 2 | Con `acks=all`, una zona caída no para la escritura |
| `auto.create.topics.enable` | `false` | Todo topic es un `KafkaTopic` con prefijo; si no, un cliente crea `events` y se salta el contrato (R30) |
| `unclean.leader.election.enable` | `false` | Perder mensajes nunca es la salida por defecto |
| `offsets.topic.replication.factor`, `transaction.state.log.replication.factor` | 3 | Idem para los topics internos |
| `transaction.state.log.min.isr` | 2 | |

---

## 3. Autenticación: mTLS con la CA interna

![Autenticación mTLS](diagrams/03-autenticacion.svg)

Fuente: [`diagrams/03-autenticacion.mmd`](diagrams/03-autenticacion.mmd)

La plataforma usa una sola CA para todo el TLS y el mTLS dentro del cluster (cert-manager DT10). Kafka se alinea con ella.

| Tramo | CA | Motivo |
|---|---|---|
| Cliente → broker (listener `tls`) | **`internal-ca`**: certificado del listener emitido por cert-manager y montado con `brokerCertChainAndKey` | Los clientes ya confían en `internal-ca-bundle`, que está en todos los namespaces (E2 §5.1) |
| Certificado del cliente | **`internal-ca`**: el consumidor lo pide en **su** namespace; la clave nunca sale de él | Sin contraseñas que repartir: nada que pase por Secret Manager ni por ESO |
| Broker ↔ broker y controlador | CA de cluster de **Strimzi** | Tráfico que no sale del namespace `kafka`; Strimzi la gestiona y la renueva. Sustituirla no aporta nada y complica cada rotación |

### 3.1 Identidad del cliente

| Pieza | Valor | Por qué |
|---|---|---|
| `Certificate` del cliente | En el namespace del consumidor, `issuerRef: internal-ca`, `usages: [client auth]`, `dnsNames: [<instancia>-<propósito>.<namespace>.svc]`, `commonName` igual a ese nombre | approver-policy (`namespace-services`) solo emite nombres del propio namespace y exige `commonName` = primer `dnsName` (cert-manager §3): la identidad es veraz por construcción |
| `KafkaUser` | Nombre = ese `commonName`; `authentication.type: tls-external` | Strimzi no emite el certificado; Kafka autentica por el `CN` **(verificar el formato del principal, VB2)** |
| Prefijo de instancia | El nombre empieza por `<instancia>-` | Cumple la regla de AM §10.2 sin excepciones |
| Namespace de origen | El sufijo `.<namespace>.svc` | Dice de qué namespace viene el cliente, y approver-policy impide falsificarlo |

Ejemplo en `qa` para una aplicación `orders`: `orders-events.orders.svc`. En `demos`, instancia `alpha`: `alpha-orders.demo-alpha.svc`.

**Confianza no es autorización** (cert-manager RT7). Cualquier namespace puede obtener un certificado de cliente de `internal-ca`. Kafka lo autentica, pero **no** le da permisos: sin un `KafkaUser` con su nombre exacto, el principal no tiene ACLs y `authorization: simple` lo deniega todo.

### 3.2 La condición: CA de clientes sin clave privada

Para `tls-external`, Strimzi debe confiar en `internal-ca` como CA de clientes (`clientsCa.generateCertificateAuthority: false`). La clave privada de `internal-ca` **no sale nunca** del namespace `cert-manager`, así que a Strimzi solo se le da el certificado.

| Resultado de VB1 | Diseño |
|---|---|
| Strimzi acepta una CA de clientes sin clave cuando todos los usuarios son `tls-external` | **mTLS** como aquí se describe (DB3) |
| Strimzi exige la clave | **SCRAM-SHA-512 sobre TLS**. La contraseña es del consumidor: secreto `qa-<instancia>-kafka` en Secret Manager, con `secretAccessor` para el KSA `eso-kafka` concedido por el consumidor (el mismo patrón que Keycloak §6.5). ESO la materializa en `kafka` para el `KafkaUser` (`password.valueFrom`) y en el namespace del consumidor para la aplicación. El arquetipo pasa a requerir `secrets` con el trait `eso` |

Nunca se copia la clave de `internal-ca` a otro namespace para satisfacer a Strimzi: la CA firmaría cualquier cosa desde allí.

---

## 4. El contrato multi-tenant

![Tenant resources](diagrams/02-tenencia.svg)

Fuente: [`diagrams/02-tenencia.mmd`](diagrams/02-tenencia.mmd)

El consumidor crea sus `KafkaTopic` y `KafkaUser` **en el namespace `kafka`**, desde su stack `messaging` (`creates_tenant_resources: [event-bus]`, AM §10.1). Lo que puede escribir está acotado.

### 4.1 Topics

| Campo | Regla | Motivo |
|---|---|---|
| `metadata.name` | `<instancia>-<nombre>` | R30 |
| `spec.topicName` | **Ausente** o igual a `metadata.name` | Si no, un `KafkaTopic` llamado `alpha-x` con `topicName: beta-orders` gestionaría el topic de otro tenant, y podría borrarlo (RB1) |
| `partitions` | ≤ 12 | Cuenta contra `kafka_partitions` (§5) |
| `replicas` | Exactamente 3 | Una por zona |
| `config` | Lista blanca: `retention.ms` ≤ 7 días, `retention.bytes` **obligatorio** y ≤ 5 GiB por partición, `cleanup.policy` (`delete` o `compact`), `max.message.bytes` ≤ 1 MiB, `compression.type` | Un topic sin `retention.bytes` puede llenar el disco del broker y parar el bus de todos (RB5) |
| Prohibido en `config` | `min.insync.replicas` distinto de 2, `unclean.leader.election.enable` | Durabilidad no negociable por tenant |

### 4.2 Usuarios, ACLs y cuotas

| Campo | Regla | Motivo |
|---|---|---|
| `metadata.name` | `<instancia>-<propósito>.<namespace>.svc`, igual al `CN` del certificado | §3.1 |
| `authentication` | `tls-external` (o `scram-sha-512` si VB1 falla) | §3.2 |
| `authorization.acls` | **Generadas** por el generador `gen_messaging`, nunca escritas por el tenant | AM §10.2 |
| `quotas` | Obligatorias | R29 |

ACLs generadas para la instancia `alpha`:

```yaml
authorization:
  type: simple
  acls:
    - resource: { type: topic, name: "alpha-", patternType: prefix }
      operations: [Read, Write, Describe]
    - resource: { type: group, name: "alpha-", patternType: prefix }
      operations: [Read]
    - resource: { type: transactionalId, name: "alpha-", patternType: prefix }   # solo si declara transacciones
      operations: [Write, Describe]
```

| Cuota por `KafkaUser` | Por defecto | Motivo |
|---|---|---|
| `producerByteRate` | 1 MiB/s | Un bucle de producción no satura el bus (R29) |
| `consumerByteRate` | 2 MiB/s | |
| `requestPercentage` | 25 | Tiempo de CPU del broker |
| `controllerMutationRate` | 1 | Crear o borrar particiones en ráfaga carga al controlador |

Subir una cuota es una PR con revisión de plataforma: suma contra `kafka_throughput_mibs` (§5), igual que subir `capacity` en un entorno compartido.

### 4.3 Lo que un tenant no puede crear

| Kind | Motivo |
|---|---|
| `Kafka`, `KafkaNodePool` | El cluster es del arquetipo |
| `KafkaConnect`, `KafkaConnector`, `KafkaMirrorMaker2` | Ejecutan código y credenciales de terceros dentro del namespace `kafka`. Si una aplicación necesita Connect, despliega su propio `KafkaConnect` como componente en su namespace, contra el bus y con su propio `KafkaUser` |
| `KafkaBridge` | La opción HTTP (Envoy Gateway §4.4) la despliega el consumidor en su namespace, con su usuario |
| `KafkaRebalance` | Cruise Control es de la plataforma |

Todos se deniegan con Gatekeeper fuera de lo que despliega el propio arquetipo (§9.2). AM §13 ya muestra el error de resolución para `KafkaConnector`.

---

## 5. Capacidad

| Clave | `qa` | Cómo se cuenta |
|---|---|---|
| `kafka_topics` | 200 | Número de `KafkaTopic` |
| `kafka_partitions` | **1000** | Particiones líder. Con réplica 3 son 3000 réplicas en 3 brokers: 1000 por broker |
| `kafka_storage_gib` | 450 (3 × 200 GiB × 75 %) | Σ `partitions × replicas × retention.bytes`: lo calcula el resolver; por encima, la PR falla |
| `kafka_throughput_mibs` | 60 | Σ `producerByteRate` de todos los `KafkaUser` |

**El techo de particiones (pregunta abierta nº 3 de `CLAUDE.md`).** El 1000 de `qa` es un punto de partida prudente, no una medida. VB7 lo mide: 3 brokers, con particiones crecientes, midiendo el tiempo de conmutación del controlador, la latencia p99 de producción y el tiempo de arranque de un broker. El número que salga fija el budget de `qa` y sustituye al 4000 provisional de `demos`.

En `qa` los budgets no se aplican (modelo dedicado, E1 §0), pero se calculan y se publican: son la medida que falta para `demos`.

---

## 6. Red y acceso desde fuera

![Red](diagrams/04-red.svg)

Fuente: [`diagrams/04-red.mmd`](diagrams/04-red.mmd)

### 6.1 Listeners

| Listener | Puerto | Tipo | Autenticación | Quién |
|---|---|---|---|---|
| `tls` | 9093 | `internal` | mTLS (`tls-external`) | Aplicaciones del cluster |
| `external` | 9094 y uno por broker | `nodeport` | mTLS | **Desactivado.** Se activa con una excepción de patrón B (Envoy Gateway §4.4) |
| Replicación y controlador | 9090, 9091 | Internos de Strimzi | mTLS con la CA de Strimzi | Solo entre pods de `kafka` |

Sin listener en claro (9092). Sin listener `loadbalancer`: sería el patrón A, prohibido.

### 6.2 `NetworkPolicy`

| Origen | Destino | Puerto | Nota |
|---|---|---|---|
| Namespaces con `kafka.disasterproject.com/client: "true"` | Brokers | 9093 | `networkPolicyPeers` del listener; Strimzi genera la política. La etiqueta la pone `gen_tenant_namespace` si el manifiesto requiere `event-bus` (§12) |
| Operador y Entity Operator | Brokers y controladores | 9091, 9093 | Generadas por Strimzi |
| Brokers ↔ brokers ↔ controladores | | 9090, 9091 | Generadas por Strimzi |
| Prometheus | Brokers, Kafka Exporter, Cruise Control | 9404 y métricas | |
| Cruise Control | Brokers | 9091 | |
| Todos | Internet | **Denegado** | |

### 6.3 Clientes de fuera del cluster: patrón B

Si un productor o consumidor externo lo justifica (Envoy Gateway §4.4, fila Kafka), el listener `external` se activa así:

| Pieza | Valor | Motivo |
|---|---|---|
| Tipo de listener | `nodeport`, con `nodePort` **fijo** para el bootstrap y para cada broker (`overrides`) | Reglas de firewall y balanceador deterministas |
| `externalTrafficPolicy` | `Local` | Sin salto extra entre nodos y con la IP de origen intacta. El health check TCP del balanceador sobre el `nodePort` solo da por sano el nodo que tiene el broker |
| Balanceador | Uno passthrough en `gcp-qa-edge`: una IP, un puerto para el bootstrap y uno por broker | Cada cliente habla con cada broker por su dirección anunciada |
| `advertisedHost` y `advertisedPort` | La IP (o nombre) del balanceador y el puerto de cada broker | Si se anuncia la IP del nodo, el cliente externo no llega |
| Autenticación | mTLS | La misma que dentro |

**El certificado del listener externo es la pregunta abierta Q-B1.** Con el patrón B el TLS termina en el broker, así que el broker presenta el certificado. Un cliente externo espera un nombre público. La CA interna no firma nombres públicos (cert-manager DT10), y el certificado de Certificate Manager no se puede exportar a un pod. Hay dos salidas, y no es una decisión de Kafka sino de toda excepción de patrón B con TLS:

| Opción | Cómo | Coste |
|---|---|---|
| **A. `ClusterIssuer` ACME público** (Let's Encrypt con DNS-01 contra la zona `qa.disasterproject.com`) | Solo para los nombres de una `exposures` aprobada; approver-policy lo limita a esos nombres | cert-manager necesita egress a la CA pública y permiso de escritura en Cloud DNS; revisa "sin ACME" de cert-manager §1 |
| B. CA privada para contrapartes (Certificate Authority Service) | La contraparte instala nuestra CA | Otra CA que operar y repartir fuera de banda |

Recomendación: **A**, porque la contraparte no tiene que confiar en nada nuestro. Mientras Q-B1 no se decida, el listener `external` no se activa.

---

## 7. El contrato `event-bus` 2.1.0

### 7.1 Salidas y traits

| Salida | Valor en `qa` | Uso |
|---|---|---|
| `bootstrap_servers` | `qa-kafka-kafka-bootstrap.kafka.svc:9093` | Configuración del cliente |
| `namespace` | `kafka` | Tenant resources |
| `cluster_name` | `qa-kafka` | Etiqueta `strimzi.io/cluster` de `KafkaTopic` y `KafkaUser` |
| `client_auth` | `tls-external` | Forma del `KafkaUser` y del `Certificate` del cliente (§3.1) |
| `ca_bundle_configmap` | `internal-ca-bundle` | Truststore del cliente: ya está en su namespace |
| `client_namespace_label` | `kafka.disasterproject.com/client: "true"` | Para la `NetworkPolicy` del listener |
| `cluster_ca_secret` | Obsoleta; se elimina en 3.0.0 | Los clientes ya no confían en la CA de Strimzi |

Las cuatro últimas son nuevas o cambian de uso sin romper a quien consume `^2.0.0`: MINOR, **2.1.0**.

| Trait | ¿Lo ofrece? | Motivo |
|---|---|---|
| `strimzi`, `kraft`, `acl-authz` | Sí | — |
| `tls-mtls` | Sí | §3 |
| `schema-registry` | **No** | No hay registry en esta versión. AM §10.1 lo lista en su ejemplo; un consumidor que lo exija falla en resolución, que es lo correcto (Q-B2) |
| `tiered-storage` | No | §2.2 |

### 7.2 Lo que escribe un consumidor

En su stack `messaging` (el generador rellena ACLs, cuotas y etiquetas):

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: orders-events                       # <instancia>-<nombre>
  namespace: kafka
  labels: { strimzi.io/cluster: qa-kafka }
spec:
  partitions: 6
  replicas: 3
  config: { retention.ms: 604800000, retention.bytes: 1073741824, cleanup.policy: delete }
---
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaUser
metadata:
  name: orders-events.orders.svc            # = CN del certificado
  namespace: kafka
  labels: { strimzi.io/cluster: qa-kafka }
spec:
  authentication: { type: tls-external }
  # authorization y quotas: las genera gen_messaging (§4.2)
```

Y en su propio namespace:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata: { name: kafka-client, namespace: orders }
spec:
  secretName: kafka-client
  issuerRef: { kind: ClusterIssuer, name: internal-ca }
  commonName: orders-events.orders.svc
  dnsNames: [orders-events.orders.svc]
  usages: [client auth]
  duration: 2160h
  renewBefore: 720h
  privateKey: { algorithm: ECDSA, size: 256, rotationPolicy: Always }
```

El cliente usa `ssl.keystore.type=PEM` con el `Secret` `kafka-client` y `ssl.truststore.type=PEM` con `internal-ca-bundle`. Un cliente que lee el keystore solo al arrancar necesita reiniciarse al renovar: hay un mes de margen (cert-manager §5.1).

---

## 8. El arquetipo

### 8.1 Manifiesto

```yaml
# archetypes/kafka/manifest.yaml
apiVersion: archetype/v1
kind: Archetype

metadata:
  name: kafka
  version: 2.1.0
  layer: 4
  kind: catalog
  description: Bus Kafka común con datos separados; Strimzi, KRaft, mTLS con la CA interna
  owners: [team-platform]

runtimes: [gke, eks, aks]

requires:
  - capability: cluster
    version: "^2.0.0"
  - capability: policy
    version: "^1.0.0"
    traits: [gatekeeper]
  - capability: certs
    version: "^1.1.0"
    traits: [cert-manager]
  - capability: monitoring
    version: "^1.5.0"
    traits: [prometheus-operator-crds]

provides:
  - capability: event-bus
    version: 2.1.0
    traits: [strimzi, kraft, acl-authz, tls-mtls]
    outputs:
      - { name: bootstrap_servers,      from: cluster }
      - { name: namespace,              from: iam }
      - { name: cluster_name,           from: cluster }
      - { name: client_auth,            from: cluster }
      - { name: ca_bundle_configmap,    from: cluster }
      - { name: client_namespace_label, from: cluster }
      - { name: cluster_ca_secret,      from: cluster }    # obsoleta; se elimina en 3.0.0
    tenant_resources:
      - kind: KafkaTopic
        namePrefix: "{{ instance }}-"
        maxCount: 20
      - kind: KafkaUser
        namePrefix: "{{ instance }}-"
        maxCount: 3

stacks:
  - name: iam
  - name: operator
    after: [iam]
  - name: cluster
    after: [operator]
  - name: policy
    after: [cluster]

capacity:
  cpu_millicores: 7200
  memory_mib: 27648
  pods: 8
  workload_identities: 0
```

`runtimes: [gke, eks, aks]`: nada es de GCP salvo la StorageClass (AM §14.2: `event-bus` es Strimzi en las tres nubes). **Sin `ingress`**: Kafka no habla HTTP. **Sin `secrets`** mientras VB1 confirme mTLS; con SCRAM, `secrets` con el trait `eso` (§3.2).

**Sin claim de subred.** El ejemplo de AM §10.1 reclama una `/26` en la zona `data` con propósito `kafka-storage-subnet`. Kafka en Kubernetes guarda sus datos en volúmenes persistentes, no en una subred, y sus pods usan el rango de pods del cluster. Se propone quitarlo de AM (§12).

### 8.2 Los stacks

| Stack | Contenido | Entradas por sharing |
|---|---|---|
| `iam` | Namespace `kafka` (`gen_tenant_namespace`, PSS `restricted`) | `cluster_*` |
| `operator` | `helm_release` de Strimzi con `watchNamespaces: [kafka]` y CRDs con `keep` | `cluster_*` |
| `cluster` | `Kafka`, `KafkaNodePool`, `Certificate` del listener (`internal-ca`), Kafka Exporter, Cruise Control, `PodMonitor` y `PrometheusRule`; `prevent_destroy` sobre el `helm_release` | `cluster_*` |
| `policy` | `ConstraintTemplate` y `Constraint` de los kinds de Strimzi (§9.2); los valores por defecto de cuotas y topics que usa `gen_messaging` | `cluster_*` |

**Por qué `operator` y `cluster` separados.** Un upgrade de Strimzi no debe planificar cambios sobre el cluster de Kafka, que tiene datos. Destruir el cluster exige un PR explícito que quite `prevent_destroy` (el mismo razonamiento que cert-manager §8.2 y Envoy Gateway §8.2).

### 8.3 El lado del consumidor

| Pieza | Dónde |
|---|---|
| `requires: event-bus ^2.1.0` con `traits: [acl-authz, tls-mtls]` | Manifiesto del consumidor |
| Stack `messaging` con `creates_tenant_resources: [event-bus]` y `after` a `gcp-qa-kafka-cluster` | Generado por `gen_messaging` |
| `Certificate` del cliente | Stack `messaging`, en el namespace del consumidor |
| Etiqueta `kafka.disasterproject.com/client` | `gen_tenant_namespace` (§12) |

---

## 9. Políticas

### 9.1 `assert` en generación

```hcl
assert {
  assertion = global.kafka_values.config["min.insync.replicas"] == 2 && global.kafka_values.config["default.replication.factor"] == 3
  message   = "event-bus: réplica 3 e ISR mínimo 2 — una zona caída no para la escritura"
}
assert {
  assertion = !global.kafka_values.config["auto.create.topics.enable"]
  message   = "event-bus: sin creación automática de topics — todo topic es un KafkaTopic con prefijo (R30)"
}
assert {
  assertion = alltrue([for l in global.kafka_values.listeners : l.tls && l.type != "loadbalancer"])
  message   = "event-bus: ningún listener en claro ni de tipo loadbalancer (patrón A prohibido)"
}
assert {
  assertion = global.kafka_values.crds.keep && global.kafka_values.watchNamespaces == ["kafka"]
  message   = "event-bus: CRDs con keep y operador limitado a su namespace (RB2)"
}
```

### 9.2 Gatekeeper y conftest

| Regla | Dónde | Qué comprueba |
|---|---|---|
| **Nueva:** forma del `KafkaTopic` | Gatekeeper | §4.1: prefijo = etiqueta de instancia; `spec.topicName` ausente o igual al nombre; límites de particiones, réplicas y `config` |
| **Nueva:** forma del `KafkaUser` | Gatekeeper | §4.2: nombre `<instancia>-*.<namespace>.svc`; `tls-external`; ACLs iguales a las derivadas del prefijo; cuotas presentes |
| **Nueva:** kinds reservados | Gatekeeper | §4.3 |
| **Nueva:** tenant resources | G1 | El stack `messaging` declara `creates_tenant_resources: [event-bus]`; prefijo de su instancia; `maxCount` |
| **Nueva:** capacidad | G1 | Particiones, almacenamiento y cuotas sumadas contra los budgets (§5) |
| **Nueva:** certificado y usuario | G1 | El `commonName` del `Certificate` del cliente es igual al nombre de un `KafkaUser` de la misma instancia |
| **Nueva:** `after` | G1 (existente, R2) | `messaging` tiene `after` a `gcp-qa-kafka-cluster` |

Todos los stacks de `qa` se aplican con la misma identidad de pipeline, así que el control de fondo sobre qué instancia escribe qué es G1 contra el ledger; Gatekeeper comprueba la forma (el mismo reparto que Keycloak §6.4).

---

## 10. Observabilidad

Kafka es capa 4 y requiere `monitoring`: declara sus propias reglas, a diferencia de las capacidades de capa 3.

| Alerta | Señal | Umbral |
|---|---|---|
| Particiones sin réplicas suficientes | `kafka_server_replicamanager_underreplicatedpartitions` | > 0 durante 5 min |
| Particiones fuera de línea | `kafka_controller_kafkacontroller_offlinepartitionscount` | > 0 |
| Controlador activo | Suma de `activecontrollercount` | ≠ 1 durante 1 min |
| Disco | `kubelet_volume_stats_used_bytes` del PVC | > 80 % |
| Retraso de consumo | `kafka_consumergroup_lag` de Kafka Exporter, **por instancia** | Umbral declarado por el consumidor; la alerta va al equipo de la instancia (monitorización §5.2) |
| Cuotas | Tiempo de throttling por usuario | Sostenido > 0: el tenant está en su límite |
| Certificados | cert-manager §6 | Listener y clientes < 14 días |
| Budget | Particiones usadas / `kafka_partitions` | > 80 % |

Nombres de métricas según la configuración del exportador JMX de Strimzi **(verificar, VB10)**.

---

## 11. `demos` y `prod`

| Tema | `qa` | `demos` | `prod` |
|---|---|---|---|
| Nodos | 3 duales | 3 controladores + 3 brokers | 3 controladores + ≥ 3 brokers |
| Budgets | Calculados, no aplicados | **Aplicados** en la PR (AM §8) | Aplicados |
| Cuotas | Por defecto de §4.2 | Más bajas: muchos tenants pequeños | Por aplicación |
| GKE | Standard con node pool `kafka` | Autopilot: sin node pool dedicado; clase de cómputo con disco y memoria suficientes **(verificar Strimzi en Autopilot, VB11)** | Standard |
| Techo de particiones | Mide VB7 | El número de VB7 sustituye al 4000 provisional | Idem |

---

## 12. Cambios a otros documentos

| Documento | Cambio | Estado |
|---|---|---|
| Binding de `qa` (E1 §7) | `event-bus: { archetype: kafka, version: 2.1.0, stack_id: gcp-qa-kafka }`; budgets de §5 | Propuesto |
| E1 §4.1 | Node pool `kafka`: 3 × `n2-standard-4`, uno por zona, taint `dedicated=kafka:NoSchedule` | Propuesto |
| `gen_tenant_namespace` (E2 §5.1) | Etiqueta `kafka.disasterproject.com/client: "true"` si el manifiesto requiere `event-bus` | Propuesto |
| AM §10.1 | Quitar el claim `kafka-storage-subnet`; `KafkaUser` nombrado como el `CN` del certificado del cliente; `schema-registry` fuera de los traits de ejemplo; contrato 2.1.0 con las salidas de §7.1 | Propuesto |
| cert-manager §1 | Si se elige la opción A de Q-B1, `ClusterIssuer` ACME acotado a las `exposures` aprobadas | Pendiente de Q-B1 |
| Envoy Gateway §4.4 | Fila Kafka: ya remite a §6.3 | Sin cambio |

---

## 13. Decisiones

| # | Decisión | Estado | Recomendación | Alternativa |
|---|---|---|---|---|
| DB1 | Operador | Consecuencia de AM §10 | Strimzi, limitado al namespace `kafka` | Kafka gestionado (otro proveedor) |
| DB2 | Topología en `qa` | Propuesta | KRaft, 3 nodos duales, uno por zona, node pool `kafka` | Controladores y brokers separados (en `demos` y `prod`) |
| DB3 | Autenticación | Propuesta, pendiente de VB1 | mTLS `tls-external` con `internal-ca`; certificado pedido por el consumidor en su namespace | SCRAM-SHA-512 con contraseña del consumidor vía Secret Manager y ESO |
| DB4 | CAs | Propuesta | `internal-ca` para todo lo que ven los clientes; CA de Strimzi solo entre brokers y controladores | CA de Strimzi repartida a los clientes |
| DB5 | Nombre del usuario | Propuesta | `<instancia>-<propósito>.<namespace>.svc` = `CN` | Nombre libre con prefijo |
| DB6 | ACLs y cuotas | Consecuencia de AM §10.2 | Generadas; Gatekeeper exige que coincidan | Escritas por el tenant |
| DB7 | Límites de topic | Propuesta | ≤ 12 particiones, réplica 3, `retention.bytes` obligatorio, ≤ 7 días | Sin límites por topic |
| DB8 | Acceso externo | Propuesta | Patrón B con `nodePort` fijo por broker, desactivado hasta Q-B1 | `loadbalancer` de Strimzi (patrón A) |
| DB9 | Budget inicial de particiones en `qa` | Propuesta | 1000, hasta que VB7 mida | 4000 como en `demos` |
| DB10 | Servicios extra | Propuesta | Kafka Exporter y Cruise Control de plataforma; sin registry, Connect ni Bridge compartidos | Ofrecerlos como servicio |

---

## 14. Riesgos candidatos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| RB1 | **`spec.topicName` apunta al topic de otro tenant** y lo gestiona o lo borra | Media sin regla | Alta — pérdida de datos de otro tenant | Gatekeeper (§9.2); VB4 |
| RB2 | **Borrado de los CRDs de Strimzi** borra todos los topics | Baja | Alta — el bus entero | CRDs con `keep`, assert, VB9 |
| RB3 | **CA de clientes**: Strimzi exige la clave de `internal-ca` | Media | Media — cambia el diseño a SCRAM | VB1 antes de la fase 1; plan B de §3.2 |
| RB4 | **Tenant ruidoso** | Media | Alta en `demos` | Cuotas obligatorias (R29) |
| RB5 | **Disco lleno** por un topic sin límite | Media sin `retention.bytes` | Alta — el broker se para y con él todos | `retention.bytes` obligatorio, budget de almacenamiento, alerta al 80 % |
| RB6 | **Renovación del certificado del listener** reinicia los brokers | Media | Baja con RF 3 e ISR 2 | Rolling de Strimzi; VB3 |
| RB7 | **Zona caída** | Baja | Media | Réplica 3 por zona, ISR 2; VB6 |
| RB8 | **Techo de particiones** alcanzado antes de lo previsto | Media | Media — no se pueden crear topics | Budget de 1000 hasta medir (VB7) |

---

## 15. Verificaciones

| # | Verificación | Resultado que la cierra |
|---|---|---|
| VB1 | Strimzi con `clientsCa.generateCertificateAuthority: false` y solo el certificado de `internal-ca` (sin clave), todos los usuarios `tls-external` | El cluster reconcilia y un cliente con certificado de `internal-ca` se autentica. Si no, SCRAM (§3.2) |
| VB2 | Principal de un usuario `tls-external` | Las ACLs de §4.2 se aplican al principal que Kafka deriva del `CN` |
| VB3 | Listener con `brokerCertChainAndKey` desde el `Secret` de cert-manager | Renovación forzada: rolling de brokers sin errores de cliente con `acks=all` |
| VB4 | `KafkaTopic` con `topicName` ajeno; `KafkaUser` con ACLs no derivadas | Ambos denegados en admisión |
| VB5 | Cuotas | Un productor a 10 veces su cuota queda limitado; la latencia p99 de los demás no cambia |
| VB6 | Zona caída (cordon y drenado de una zona) | Cero particiones fuera de línea; los productores con `acks=all` siguen |
| VB7 | Techo de particiones con 3 brokers | Número publicado con tiempo de conmutación del controlador, latencia p99 y arranque de broker; fija el budget |
| VB8 | Listener `external` con patrón B y `externalTrafficPolicy: Local` | IP de origen intacta; el cliente llega a cada broker por su dirección anunciada |
| VB9 | Desinstalar el operador en un entorno efímero | Topics, usuarios y datos siguen existiendo |
| VB10 | Versión de Strimzi y Kafka; nombres de métricas | Alertas de §10 con series reales |
| VB11 | Strimzi en GKE Autopilot (`demos`) | Brokers con su PVC zonal y reparto por zona |
| VB12 | PSS `restricted` con los pods de Strimzi | Admitidos sin exención |

---

## 16. Preguntas abiertas

| # | Pregunta | Recomendación |
|---|---|---|
| Q-B1 | Certificado de un listener expuesto por patrón B con nombre público | `ClusterIssuer` ACME con DNS-01, acotado a las `exposures` aprobadas (§6.3) |
| Q-B2 | ¿Hace falta schema registry? | No hasta que una aplicación lo pida; entonces Apicurio Registry como arquetipo aparte, con su propio contrato |

---

## 17. Plan de implementación

| Fase | Contenido | Criterio de salida | Estimación |
|---|---|---|---|
| **0 · Prerrequisitos** | Node pool `kafka`; binding de `qa`; **VB1**, VB10, VB12 | Autenticación decidida (mTLS o SCRAM) | 1 día |
| **1 · Esqueleto** | Manifiesto, charts, asserts, reglas G1 y constraints, `gen_messaging` | `archetypectl resolve --dry-run`, `terramate generate --check`, G1 y preview con mocks en verde | 2 días |
| **2 · Operador y cluster** | `iam`, `operator`, `cluster`, `policy` | Cluster `Ready`; **VB2**, **VB3**, **VB4**, **VB9** | 2 días |
| **3 · Pruebas de carga** | Aplicación de prueba con dos instancias | **VB5**, **VB6**, **VB7** | 2 días |
| **4 · Acceso externo** | Solo cuando haya una excepción aprobada y Q-B1 decidida | **VB8** | Con la excepción |

Siete días para una persona. VB1 va primero: decide si el arquetipo necesita `secrets`.
