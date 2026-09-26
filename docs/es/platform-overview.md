# Visión general de la plataforma — Leer esto primero

Mapa visual de los dos documentos de referencia. Nada aquí es normativo; cada diagrama apunta a la sección que lo especifica.

| Documento | Responde |
|---|---|
| `archetype-model.md` | *¿Qué se puede componer con qué?* Manifiestos, capabilities, traits, pools, CMDB, resolución |
| `terramate-outputs-sharing-architecture.md` | *¿Cómo se genera y se aplica?* Generadores, outputs sharing, IAM, política, CI/CD, guías por nube |
| `risk-register.md` | *¿Qué puede salir mal, y el control está realmente implementado?* 53 riesgos por dominio (52 activos), revisados en cada puerta de fase |

---

## 1. Las dos mitades, y la costura entre ellas

```mermaid
flowchart LR
    subgraph R["archetype-model.md — RESOLVE"]
        direction TB
        M["manifest.yaml<br/>requires / provides / traits"]
        B["binding.yaml<br/>qué proveedor por capability"]
        L["pool ledgers<br/>CIDR, hostnames"]
        RES["archetypectl resolve"]
        M --> RES
        B --> RES
        L --> RES
    end

    subgraph G["terramate-outputs-sharing-architecture.md — GENERATE"]
        direction TB
        GEN["terramate generate"]
        TF["_main.tf, _backend.tf<br/>_sharing_generated.tf"]
        RUN["terramate run --enable-sharing"]
        GEN --> TF --> RUN
    end

    RES -->|"binding.tm.hcl<br/>(globals)"| GEN
    RUN -->|"inventario de stacks y recursos"| CMDB[("CMDB en Git")]
    CMDB -.->|"utilización, claims"| RES
```

**La costura es `binding.tm.hcl`.** El resolver escribe globals; los generadores los consumen. Ninguna de las dos mitades conoce las internas de la otra.

---

## 2. Flujo completo de un pull request

```mermaid
flowchart TD
    PR([Pull request abierta]) --> SCH["Validación de esquema<br/>manifiestos, bindings, ledgers"]
    SCH --> RESOLVE["archetypectl resolve<br/>17 pasos — falla cerrado"]
    RESOLVE -->|"binding.tm.hcl<br/>escrituras de ledger"| G0["G0 · terramate generate --check<br/>el código generado está al día"]
    G0 --> G1["G1 · conftest<br/>estructura, composición, input↔after"]
    G1 --> G2["G2 · Checkov sobre el HCL generado"]
    G2 --> PLAN["terramate script run --changed tofu preview<br/>sharing ON · mocks ON"]
    PLAN --> G3["G3 · Checkov + conftest sobre plan.json"]
    G3 --> CMT["Comentario en la PR · closure, claims, capacity, plan"]

    CMT --> REV{¿Aprobado?}
    REV -->|no| END1([Cerrado — claims liberados])
    REV -->|sí| ENV["GitHub Environment<br/>revisores obligatorios"]
    ENV --> APPLY["tofu deploy<br/>sharing ON · mocks OFF"]
    APPLY --> SYNC["Sincronización de CMDB"]

    style RESOLVE fill:#e8f0fe
    style APPLY fill:#fce8e6
```

Dos cosas quedan visibles aquí: el resolver corre **antes** de la generación porque produce la entrada de esta, y `mock_on_fail` es true en preview y false en deploy — scripts nombrados por separado para que no se pueda confundir.

Especificado en: architecture §13, §14, companion §12.

---

## 3. Capas de archetype

```mermaid
flowchart BT
    L0["<b>Capa 0 · landing-zone</b><br/>hub · dns-zone · cert · waf · cidr-pool · edge-ip"]
    L1["<b>Capa 1 · environment</b><br/>prod / qa / dev / demos / ephemeral-*<br/>reclama un /17 · provee network, env-edge, psa-range"]
    L1B["<b>Capa 1b · cloud-monitoring</b><br/>cloud-observability"]
    L2["<b>Capa 2 · runtime</b><br/>gke · gke-autopilot · eks · aks · cloudrun · fargate<br/>reclama subred de nodos + rango de pods"]
    L2B["<b>Capa 2b · policy</b><br/>policy-gatekeeper — solo runtimes Kubernetes"]
    L3["<b>Capa 3 · platform services</b><br/>gateway · monitoring · certs · dns · secrets · mesh"]
    L4["<b>Capa 4 · middleware</b><br/>kafka · keycloak · postgres-operator · redis"]
    L5["<b>Capa 5 · applications</b><br/>webapp-3tier · event-driven · demo-*"]

    L0 --> L1
    L1 --> L1B
    L1 --> L2
    L2 --> L2B
    L2B --> L3
    L3 --> L4
    L4 --> L5
    L3 -.->|"handle de attachment del edge<br/>la única arista ascendente"| L1

    style L1B fill:#f5f5f5
    style L2B fill:#fff4e5
    style L5 fill:#e8f5e9
```

La arista punteada es la excepción que vale la pena recordar: el archetype `gateway` en la capa 3 publica el nombre del NEG / el ARN del target group / el frontend de AGFC que consume el stack de edge del environment en la capa 1.

Especificado en: companion §3.

---

## 4. De dónde viene un dato — globals o outputs sharing

```mermaid
flowchart TD
    Q{"¿Se conoce el valor<br/>antes de cualquier apply?"}
    Q -->|sí| G["<b>Globals</b><br/>tiempo de compilación · cero permisos"]
    Q -->|no| S{"¿Es una credencial,<br/>secreto o token?"}
    S -->|sí| N["<b>Ninguno de los dos</b><br/>compartir una referencia;<br/>obtener vía data source"]
    S -->|no| C{"¿Compartirlo<br/>crearía un ciclo?"}
    C -->|sí| D["<b>Promover a global</b><br/>nombre determinista<br/>rompe el ciclo"]
    C -->|no| O["<b>Outputs sharing</b><br/>runtime · necesita permiso<br/>de lectura del state del producer"]

    style G fill:#e8f5e9
    style N fill:#fce8e6
    style O fill:#e8f0fe
```

Cada arista de outputs sharing es un acoplamiento en runtime, un requisito de permiso en CI y un modo de fallo. Cada global es una constante en tiempo de compilación. Preferir globals.

Especificado en: architecture §4.6, §11.5, §11.6.

---

## 5. Cómo viaja realmente un valor compartido

```mermaid
sequenceDiagram
    participant TG as terramate generate
    participant P as Stack producer
    participant C as Stack consumer
    participant TF as tofu (consumer)

    TG->>P: bloque output → _sharing_generated.tf (output)
    TG->>C: bloque input → _sharing_generated.tf (variable)
    Note over TG: commiteado a git

    C->>P: cd producer && tofu output -json
    P-->>C: JSON
    Note over C: evalúa outputs.NAME.value
    C->>TF: TF_VAR_NAME=resuelto
    TF->>TF: plan / apply
```

La tercera flecha es la que cuesta permisos: el job de CI del consumer necesita **acceso de lectura al state backend del producer**, y a su clave de cifrado si el cifrado de state está habilitado.

Especificado en: architecture §3.3, §11.5.

---

## 6. Pools jerárquicos y zonas de propósito

```mermaid
flowchart TD
    G["<b>10.0.0.0/8</b> · pool global<br/>publicado por landing-zone"]
    G --> HUB["10.0.0.0/17 · hub<br/><i>reserva fija</i>"]
    G --> HUBDR["10.0.128.0/17 · hub DR<br/><i>reserva fija</i>"]
    G --> PERM["10.4.0.0/14 · environments permanentes"]
    G --> EPH["10.16.0.0/12 · efímeros"]

    PERM --> ENV["<b>10.4.0.0/17</b> · demos<br/>pool del environment"]

    ENV --> Z1["zona <b>infra</b> · /20<br/>subredes de nodos, endpoints"]
    ENV --> Z2["zona <b>data</b> · /20<br/>PSA, subredes de BD"]
    ENV --> Z3["zona <b>edge</b> · /20<br/>services, egress"]
    ENV --> Z4["zona <b>growth</b> · /20<br/><i>nunca asignable</i>"]
    ENV --> Z5["zona <b>pods</b> · /18<br/>solo rangos de pods"]

    Z1 -.-> C1["claim: nodes /23<br/>owner gcp-demos-gke"]
    Z5 -.-> C2["claim: pods /18<br/>owner gcp-demos-gke"]
    Z2 -.-> C3["claim: db-subnet /24<br/>owner demos-alpha"]

    style HUB fill:#f5f5f5
    style HUBDR fill:#f5f5f5
    style Z4 fill:#f5f5f5
```

El hub es una **reserva fija, no un claim** — la landing zone publica el pool y necesita direcciones para sí misma, así que un claim crearía un ciclo de arranque.

Especificado en: companion §9.

---

## 7. Claim, capacity, o ninguno

```mermaid
flowchart TD
    A{"¿Finito, indivisible,<br/>único en un scope?"}
    A -->|sí| CL["<b>CLAIM</b> · ledger + reserva<br/>CIDR · hostname · IP estática"]
    A -->|no| B{"¿Cantidad divisible<br/>con un total conocido?"}
    B -->|sí| CA["<b>CAPACITY</b> · presupuesto, sin ledger<br/>kafka_partitions · db_connections<br/>workload_identities · managed_db_instances"]
    B -->|no| C{"¿Derivable de la<br/>identidad de la instancia?"}
    C -->|sí| DE["<b>NINGUNO</b> · global determinista<br/>namespace · log group · nombre de rol<br/>prefijo de topic de Kafka"]
    C -->|no| RE["Reexaminar — probablemente<br/>es uno de los anteriores"]

    style CL fill:#e8f0fe
    style CA fill:#fff4e5
    style DE fill:#e8f5e9
```

La asignación es idempotente sobre la tripla **`(pool, owner, purpose)`**, así que cinco reintentos de un deployment fallido no queman cinco rangos de pods.

Especificado en: companion §8.

---

## 8. Resolución — los 17 pasos, agrupados

```mermaid
flowchart TD
    subgraph LOAD["Cargar"]
        S1["1 · manifiestos + components + binding"]
        S2["2 · reglas de categoría para kind: demo"]
    end
    subgraph GRAPH["Grafo"]
        S3["3 · clausura transitiva, detección de ciclos"]
        S4["4 · vincular capability → proveedor único"]
    end
    subgraph VAL["Validar"]
        S5["5 · versiones"]
        S6["6 · traits"]
        S7["7 · runtime"]
        S8["8 · conflictos"]
        S9["9 · evaluar condiciones de stack"]
        S10["10 · contrato de output"]
        S11["11 · recursos del tenant"]
    end
    subgraph ALLOC["Asignar"]
        S12["12 · claims, jerárquico, idempotente"]
        S13["13 · selectores de firewall"]
        S14["14 · presupuestos de capacity"]
        S15["15 · restricciones del proveedor"]
    end
    subgraph EMIT["Emitir"]
        S16["16 · orden topológico"]
        S17["17 · resolution.json + binding.tm.hcl"]
    end

    LOAD --> GRAPH --> VAL --> ALLOC --> EMIT

    style ALLOC fill:#fff4e5
```

El paso 4 es una **búsqueda indexada, no una búsqueda general** — exactamente un proveedor por capability por environment — por eso la resolución es lineal y no NP-completa. El esfuerzo de ingeniería pertenece al diagnóstico, no al algoritmo.

Especificado en: companion §12, §13.

---

## 9. La forma que sigue cada guía de runtime

```mermaid
flowchart LR
    N["<b>network</b><br/>VPC/VNet, subredes, NAT"]
    R["<b>runtime</b><br/>cluster o serverless<br/><i>consumer + producer</i>"]
    S["<b>platform services</b><br/>gateway, certs, dns"]
    D["<b>data</b><br/>por instancia"]
    A["<b>app</b><br/>por instancia"]

    N --> R --> S --> A
    N --> D --> A
```

Las cinco guías — GKE, EKS, Cloud Run, ECS Fargate, AKS — son este mismo grafo. Lo que cambia es *qué datos cruzan cada arista*:

```mermaid
flowchart TD
    subgraph NET["network produce"]
        G1["GKE: network_self_link, subnet_self_link,<br/>pods_range_name, services_range_name"]
        A1["EKS/Fargate: vpc_id, private_subnet_ids (lista)"]
        Z1["AKS: vnet_id, node_subnet_id"]
    end
    subgraph CLU["runtime produce"]
        G2["GKE: cluster_endpoint (sin esquema), cluster_ca,<br/><b>workload_identity_pool</b>"]
        A2["EKS: cluster_endpoint (CON https://), cluster_ca,<br/><b>oidc_provider_arn + oidc_provider_url</b>"]
        Z2["AKS: cluster_endpoint, cluster_ca,<br/><b>oidc_issuer_url</b>"]
        F2["Fargate: cluster_arn, alb_listener_arn,<br/><b>task_role_boundary_arn</b>"]
        C2["Cloud Run: artifact_registry_repo,<br/>cloud_armor_policy_id"]
    end
    NET --> CLU
```

Dos asimetrías que causan bugs de copiar y pegar: GKE devuelve un endpoint **sin** esquema y EKS devuelve uno **con** `https://`; y AWS necesita dos datos de OIDC donde GCP y Azure necesitan uno.

**Nunca compartido, en ninguna nube:** el token de autenticación. Se obtiene localmente en cada consumer vía `google_client_config`, `aws_eks_cluster_auth` o el equivalente de Azure.

Especificado en: architecture §5–§9, §6.8.

---

## 10. Attachment del edge — el elemento menos portable

```mermaid
flowchart TD
    subgraph GCP["Google Cloud"]
        GT["Terraform posee:<br/>backend service, health check,<br/>URL map, proxy, forwarding rule"]
        GN["El controlador de NEG crea el NEG"]
        GT -.->|"lookup por nombre"| GN
        GNOTE["<b>NO está en el state de Terraform</b><br/>sin trait iac-owned-edge"]
        GN --- GNOTE
    end
    subgraph AWS["AWS"]
        AT["Terraform posee:<br/><b>target group</b>, listener, reglas"]
        AC["El controlador registra IPs de pods<br/>vía CR TargetGroupBinding"]
        AT --> AC
        ANOTE["<b>Está en el state de Terraform</b><br/>iac-owned-edge ✓"]
        AT --- ANOTE
    end
    subgraph AZ["Azure"]
        ZT["Terraform posee:<br/><b>AGFC + Frontend + Association</b>"]
        ZC["El controlador vincula vía<br/>anotación de Gateway"]
        ZT --> ZC
        ZNOTE["<b>Está en el state de Terraform</b><br/>iac-owned-edge ✓"]
        ZT --- ZNOTE
    end

    style GNOTE fill:#fce8e6
    style ANOTE fill:#e8f5e9
    style ZNOTE fill:#e8f5e9
```

GCP es el más débil de los tres en cuanto a propiedad completa por IaC. Esa brecha se registra como la ausencia del trait `iac-owned-edge` en lugar de ocultarse, para que un futuro requisito de cumplimiento falle en la validación y no en la auditoría.

Especificado en: architecture §10, companion §4.3.

---

## 11. Por qué Gateway API elimina el problema del fan-in

```mermaid
flowchart LR
    subgraph OLD["Edge con URL-map — fan-in"]
        direction TB
        E1["stack de edge"]
        T1["tenant A"] --> E1
        T2["tenant B"] --> E1
        T3["tenant C"] --> E1
        N1["el edge debe conocer a cada tenant;<br/>corre DESPUÉS de todos ellos"]
    end
    subgraph NEW["Gateway API — sin fan-in"]
        direction TB
        GW["Gateway<br/>allowedRoutes: Selector"]
        R1["HTTPRoute A"] -->|parentRefs| GW
        R2["HTTPRoute B"] -->|parentRefs| GW
        R3["HTTPRoute C"] -->|parentRefs| GW
        N2["el edge no conoce nada;<br/>las rutas se autoadjuntan"]
    end
    OLD -.->|"adoptar Gateway API"| NEW

    style OLD fill:#fce8e6
    style NEW fill:#e8f5e9
```

Adoptar Gateway API elimina tres cosas: el URL map generado a partir de una lista de tenants, el ledger de prioridad de listeners, y el stack de edge-routing que tenía que correr al final. Lo que sobrevive como claim es el **hostname** — solo un tenant puede ser dueño de `alpha.demos.disasterproject.com`.

Especificado en: architecture §10.6.

---

## 12. Límites de aislamiento por runtime

```mermaid
flowchart TD
    subgraph K8S["Runtimes de Kubernetes — el límite es el NAMESPACE"]
        GKE["GKE<br/>WI: POOL[ns/ksa]"]
        EKS["EKS<br/>IRSA: sub=system:serviceaccount:ns:sa"]
        AKS["AKS<br/>FIC: subject=system:serviceaccount:ns:sa"]
    end
    subgraph SRV["Runtimes serverless — el límite es el SERVICE / TASK"]
        CR["Cloud Run<br/>SA de runtime por servicio<br/>sandbox gVisor por servicio"]
        FG["ECS Fargate<br/>task role + execution role por instancia<br/>micro-VM por task"]
    end
    K8S -->|"kernel compartido en nodos compartidos"| RISK["mayor exposición para<br/>cargas semi-confiables"]
    SRV -->|"aislamiento por carga de trabajo"| SAFE["valor por defecto más fuerte para<br/>environments de demo compartidos"]

    style RISK fill:#fff4e5
    style SAFE fill:#e8f5e9
```

Un wildcard en cualquiera de esas tres condiciones de confianza (`POOL[*/*]`, `system:serviceaccount:*:*`) otorga silenciosamente la identidad a cada pod del cluster. Ese es el riesgo R15.

Especificado en: architecture §11.8, §12.3.

---

## 12b. Tres puntos de aplicación

```mermaid
flowchart LR
    CI["<b>1 · CI</b><br/>conftest + Checkov<br/><i>todo runtime</i>"]
    CP["<b>2 · Plano de control de la nube</b><br/>Org Policy · SCP · Azure Policy<br/><i>todo runtime · no evadible</i>"]
    AD["<b>3 · Admisión del cluster</b><br/>Gatekeeper, capa 2b<br/><i>SOLO runtimes Kubernetes</i>"]
    CI --> CP --> AD --> DONE([aplicado])
    style AD fill:#fff4e5
```

El tercer punto no existe en Cloud Run, ECS Fargate ni Container Apps — la capability `policy` vive solo donde vive `cluster`. La paridad de runtime no es alcanzable aquí, y la brecha queda escrita en lugar de asumida como resuelta.

El resolver **computa**; OPA **afirma**. No deben implementar la misma regla dos veces: el resolver posee la clausura, la asignación y el ordenamiento; OPA valida que lo que el resolver y los generadores produjeron es legal.

```mermaid
flowchart TD
    REG["<b>registry/*.yaml</b><br/>capabilities · traits · zones · labels"]
    REG -->|genera| S["schemas/*.schema.json<br/>bloques enum"]
    REG -->|genera| D["registry/*.json<br/>conftest --data"]
    REG -->|genera| V["valores del chart de Gatekeeper<br/>parámetros de ConstraintTemplate"]
    S --> CK["check-jsonschema"]
    D --> CF["conftest"]
    V --> GK["Gatekeeper"]
    style REG fill:#e8f0fe
```

Una fuente, tres artefactos generados, una puerta `registry-generate --check`. Sin ella divergen — y el modo de fallo es una label que el generador dejó de emitir mientras el `Constraint` de admisión aún la exige, lo que bloquea deployments legítimos en el peor momento posible.

Especificado en: architecture §13, companion §4.4.

---

## 13. Tres capas de barandillas

```mermaid
flowchart TD
    ORG["<b>Org Policies (GCP) · SCPs (AWS) · Azure Policy</b><br/>confinamiento por región · sin claves de SA · sin IPs públicas · sin usuarios IAM<br/><i>el pipeline no puede desactivar esto</i>"]
    PB["<b>Permission boundaries</b><br/>publicadas por el stack de la plataforma, adjuntadas por aserción<br/><i>un tenant no puede escapar de esto</i>"]
    RP["<b>Políticas de rol de mínimo privilegio</b><br/>por environment · por fase · por carga de trabajo<br/><i>revisadas en la pull request</i>"]
    ORG --> PB --> RP

    style ORG fill:#fce8e6
    style PB fill:#fff4e5
    style RP fill:#e8f5e9
```

Especificado en: architecture §11.7.

---

## 14. Recursos de tenant en un operador compartido

```mermaid
flowchart LR
    subgraph KNS["namespace kafka"]
        KC["Cluster Kafka<br/>Strimzi, KRaft"]
        TA["alpha-orders<br/>alpha-events"]
        TB["beta-orders"]
        UA["alpha-app<br/>+ ACLs + quotas"]
        UB["beta-app<br/>+ ACLs + quotas"]
    end
    subgraph ANS["namespace demo-alpha"]
        AM["stack de mensajería<br/>creates_tenant_resources: [event-bus]"]
    end
    subgraph BNS["namespace demo-beta"]
        BM["stack de mensajería"]
    end
    AM -->|"KafkaTopic, KafkaUser<br/>prefijo alpha-"| TA
    AM --> UA
    BM -->|"prefijo beta-"| TB
    BM --> UB
    KC -.->|"deriva ACLs a partir del prefijo"| UA
    KC -.->|"deriva ACLs a partir del prefijo"| UB
```

Tres reglas hacen esto seguro: prefijo obligatorio `{{ instance }}-`, ACLs **derivadas por el proveedor** en lugar de escritas por cada aplicación, y quotas de throughput de `KafkaUser` — porque ResourceQuota no limita bytes por segundo.

Especificado en: companion §10.

---

## 15. Catalog, demo y component

```mermaid
flowchart TD
    subgraph CAT["kind: catalog — equipo de plataforma"]
        C1["keycloak@4.1.0"]
        C2["kafka@2.0.0"]
        C3["webapp-3tier@2.3.0"]
        CN["años · muchas instancias<br/>semver estricto · puede publicar capabilities"]
    end
    subgraph COMP["components — plantillas de stack reutilizables"]
        P1["component/neo4j"]
        P2["component/mongodb"]
        P3["component/postgres"]
        P4["component/redis"]
    end
    subgraph DEMO["kind: demo — oficina de proyecto"]
        D1["demo-disasterproject-graph@0.1.0<br/>expiresOn obligatorio"]
        DN["semanas · una instancia · solo hoja<br/>NO puede publicar capabilities"]
    end
    COMP -->|"stacks[].use"| D1
    COMP -->|"stacks[].use"| C3
    CAT -->|"requires capabilities"| D1

    style DEMO fill:#e8f5e9
    style COMP fill:#e8f0fe
```

El catálogo de components es lo que hace viable la categoría demo: la oficina de proyecto escribe un stack a medida y un archivo de values, no infraestructura. Veinte minutos en lugar de un día.

Especificado en: companion §5.

---

## 16. Orden de lectura

```mermaid
flowchart LR
    S["Empezar aquí"] --> O["Esta visión general"]
    O --> A1["archetype-model §3 capas<br/>§4 capabilities y traits"]
    A1 --> A2["companion §5 anatomía<br/>§6 manifest"]
    A2 --> B1["architecture §3 arquitectura<br/>§4 referencia de elementos"]
    B1 --> B2["elegir UNA guía<br/>§5 GKE o §6 EKS"]
    B2 --> C1["architecture §11 identidad<br/>§12 environments"]
    C1 --> C2["companion §8 §9 pools<br/>§12 resolución"]
    C2 --> D1["architecture §13 policy<br/>§14 CI/CD"]
    D1 --> D2["risk-register.md<br/>primero los cinco principales"]
```

Leer una guía de runtime, no cinco. Son el mismo grafo con datos distintos en las aristas; §6.8 tabula las diferencias.
