# Registro de riesgos

**Complementa a `terramate-outputs-sharing-architecture.md`, `archetype-model.md` y `platform-overview.md`**

| | |
|---|---|
| **Alcance** | Todos los modos de fallo identificados en generación, resolución, identidad, borde, políticas y multi-tenancy |
| **Referencias de sección** | `§n` se refiere al documento de arquitectura salvo que lleve el prefijo `AM §n` (modelo de arquetipos) |
| **Identificadores** | R1–R69. R28 está **retirado** (duplicado de R26), y R38 y R39 se retiran con el endpoint DNS del plano de control (`landing-zone-qa` DZ4); los números retirados no se reutilizan |
| **Cadencia de revisión** | En cada fase del roadmap, y siempre que cambie la versión fijada de una herramienta |

Los riesgos se agrupan por dominio, no por orden numérico, porque así es como se revisan. Los números R son identificadores estables y no deben reutilizarse si un riesgo se retira.

---

## Cómo leer esto

| Columna | Significado |
|---|---|
| **Probabilidad** | Probabilidad de que el fallo ocurra **si la mitigación no está en marcha** |
| **Impacto** | Gravedad cuando ocurre |
| **Mitigación** | El control, y la sección que lo especifica |

Un riesgo cuya mitigación es una puerta de CI solo está mitigado cuando esa puerta es **bloqueante**. Varios de abajo llevan la etiqueta "Alta sin X" precisamente porque el estado por defecto es desprotegido.

---


## 1. Outputs sharing y generación

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | **Outputs Sharing es experimental** y su semántica de bloque puede cambiar | Media | Alta — afecta a todo fichero de contrato | Fijar la versión de Terramate en `mise.toml`; mantener los contratos centralizados en `imports/contracts/` para que un cambio incompatible sea una edición acotada; suscribirse a las notas de versión de Terramate; validar cada actualización en una rama de prueba antes de desplegarla |
| R2 | **Falta `after` en un stack consumidor** | Alta sin lint | Alta — se aplican valores incorrectos | El lint de §14.4, hecho bloqueante |
| R3 | **Mocks que se filtran a un despliegue** | Media | Alta | Scripts separados de `preview` y `deploy`; prefijo `mock-` en todos los mocks; grep posterior al apply que busque `mock-` en las salidas |
| R4 | **Mocks con el tipo equivocado** | Alta | Media — el plan pasa, el apply falla | Checklist de revisión de código; listas de mocks como listas, base64 como base64 válido |
| R9 | **Código generado editado a mano** | Media | Media | Puerta G0 + `CODEOWNERS` en `stacks/**/_*.tf` que exige aprobación del equipo de plataforma |
| R17 | **Clave de cifrado de estado por stack, bloqueando outputs sharing** | Media al desplegar | Media — el consumidor no puede descifrar el estado del productor | Una clave de cifrado de estado por **entorno**, no por stack (§11.5) |

## 2. Identidad, acceso y secretos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R8 | **Secreto filtrado a través de `TF_VAR_*`** | Baja si se sigue la política | Crítico | Nunca compartir *valores* de secretos; solo referencias. Añadir una política Checkov o un grep bloqueante que falle cuando el valor de un bloque `output` coincida con patrones de secreto conocidos |
| R12 | **Política de confianza OIDC con un `sub` comodín** (`repo:org/repo:*`) | Alta si no se revisa | Crítico — cualquier PR de rama o fork puede asumir el rol de apply | `StringEquals` sobre el `repo:ORG/REPO:environment:ENV` exacto; en GCP, `attribute_condition` que fija `assertion.repository` y `repository_owner_id`; revisar ambos en un PR de bootstrap dedicado (§11.2, §11.3) |
| R15 | **Binding de identidad de workload escrito con comodín** (`POOL[*/*]`, `system:serviceaccount:*:*`) | Media | Crítico — todos los pods del cluster obtienen el rol | Generar el binding desde `global.platform.namespace`; política Checkov que rechace `*` en condiciones de confianza (§11.8) |
| R16 | **Permission boundary omitido en un rol IAM creado por un tenant** | Media | Alta — el stack del tenant puede escalar | La plataforma publica `task_role_boundary_arn`; una assertion bloquea la generación sin él (§11.7) |
| R19 | **Cuenta de servicio por defecto usada como identidad de workload** (SA de cómputo de GCP, rol compartido de ECS) | Media | Alta — el workload corre con Editor del proyecto | Identidad dedicada por workload, forzada por una política Checkov (§7.4, §5.7) |
| R25 | **`kube_config` de AKS acaba en el estado como credencial** | Segura si se usa | Alta | `local_account_disabled = true` más autenticación Entra; nunca exponer `kube_config` como salida compartida (§9.5) |
| R39 | *Retirado — con el endpoint DNS ninguna identidad del pipeline necesita `container.clusters.update` (`landing-zone-qa` DZ4). El número no se reutiliza.* | — | — | — |
| R40 | **Valores de secreto guardados en el estado de OpenTofu** (`random_password` + versión del secreto) | Alta por defecto | Alta — el estado cifrado se convierte en un segundo almacén de secretos legible por cualquier identidad que pueda leer el estado | Recursos `ephemeral` y atributos write-only (`secret_data_wo`); verificar el soporte en las versiones fijadas de OpenTofu y del proveedor en la fase 0 |
| R41 | **Destrucción de la clave de cifrado de estado del entorno** — GCP no tiene un equivalente escrito de la SCP de AWS en §11.3 | Baja | Crítico — el estado del entorno queda ilegible, de forma irrecuperable | Sin permiso de destrucción de KMS en identidades de pipeline; `prevent_destroy`; política de organización `constraints/cloudkms.minimumDestroyScheduledDuration`; key ring creado en la capa 0 (`proposals/sonarqube-qa`, sección 4.14) |
| R42 | **Caduca la credencial de federación del IdP** (la credencial de Keycloak en el app registration del IdP superior) | Media | Alta — nadie puede iniciar sesión en nada tras el realm | Credencial de certificado en vez de client secret; alerta 30 días antes de la caducidad, dirigida al equipo dueño del app registration |
| R43 | **Un usuario dado de baja conserva tokens de la aplicación** cuando la aplicación no tiene SCIM | Media | Media — el acceso continúa tras deshabilitar la cuenta superior | Job de reconciliación diario contra el directorio superior; sin tokens personales en CI |
| R54 | **Identidad de Workload Identity compartida en el proyecto non-prod**: un pool por proyecto de GCP, así que el mismo namespace y KSA en dos clusters no productivos son una sola identidad de GCP | Alta si los KSA no llevan prefijo | Alta — un entorno no productivo lee los secretos, buckets y bases de datos de otro | Todo KSA con IAM de GCP se llama `<env>-<nombre>`; Gatekeeper P12 rechaza el prefijo de otro entorno; G1 comprueba cada `member` de IAM. Residual: un cluster-admin de un entorno no productivo puede saltarse la admisión — aceptado solo para no producción; `prod` nunca comparte proyecto (`CLAUDE.md`) |
| R60 | **Un grant de proyecto donde bastaba uno de recurso**: en el proyecto non-prod compartido, un rol sobre el proyecto alcanza a todos sus entornos | Media | Alta — una identidad de un entorno lee o escribe recursos de otro | Grants por recurso sobre claves, repositorios, zonas y SAs; la landing zone crea las SAs que reciben grants entre proyectos; regla de G3 sobre el IAM de la landing zone (`landing-zone-qa` §6.3, §11.1) |
| R61 | **Estado legible por concesiones a nivel de proyecto cuando la capa 0 adopta un proyecto existente**: identidades que ya tienen `owner`, `editor` o `storage.admin` sobre el proyecto leen y escriben todos los objetos de estado | Alta en un proyecto adoptado | Crítico — el estado de todos los entornos, el de la landing zone incluido, legible y modificable fuera del pipeline | Reducidas a nivel de recurso antes de que el bootstrap guarde estado; estado por prefijo y claves por clave; auditoría DATA_READ sobre `storage.googleapis.com` (`landing-zone-qa` §1.5, RZ6) |
| R63 | **La cota de administración de IAM desacompasada de los roles que protege**: la identidad de apply de la landing zone administra el IAM de proyecto acotada a una lista de roles; un rol añadido sin actualizar la cota, o un rol privilegiado colado en la lista | Media | Alto — un 403 (seguro) en el primer caso; un camino de escalada en el segundo | Una sola lista `global.identities` que leen quien concede y la cota; las validaciones del módulo rechazan `owner`, `editor`, administración de IAM y roles de creación de tokens en la lista concedible; el cambio del bootstrap lo revisa seguridad (`landing-zone-qa` DZ13, RZ8) |

## 3. Redes y planificación de direcciones

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R7 | **Faltan permisos de lectura de estado entre cuentas** | Alta en la primera configuración | Media — CI falla de forma ruidosa | Documentar las concesiones necesarias por entorno; probarlo en el PoC antes de escalar |
| R18 | **Plano de control privado inalcanzable desde runners alojados por GitHub** | Alta en clusters privados | Media — pipeline bloqueado tarde en el despliegue | Decidir entre runners self-hosted o una concesión de red autorizada en la fase 0 (§11.9); en GCP, el endpoint DNS del plano de control con solo IAM elimina el problema sin runners self-hosted (`landing-zone-qa` DZ4) |
| R23 | **La no transitividad del peering de VPC en GCP bloquea el LB del hub → NEG del spoke** | Alta si el hub-and-spoke usa VPC separadas | Alta — el diseño de borde no funciona | Shared VPC con una /17 por entorno, Network Connectivity Center, o un LB por spoke. Decidir en la fase 0 |
| R26 | **Rango secundario de pods dimensionado para pocos nodos** — inmutable tras crear el cluster. El disparador original era una /18 a 110 pods por nodo (64 nodos) | Alta sin la comprobación | Alta — el cluster no puede crecer; solo se arregla reconstruyéndolo | Valor por defecto de la plataforma de 64 pods por nodo (`/25` por nodo, 128 nodos en una `/18`); el resolver rechaza `max_nodes × bloque > rango` (AM §9.4); `/16` para producción; Azure CNI Overlay elimina la restricción (§9.2) |
| R27 | **El pool del entorno se fragmenta en /17 inutilizables** | Media en 12 meses | Media — una /16 deja de poder asignarse | Asignación por pares que prefiere bloques que no dividen tiradas libres más grandes; aislar la supernet efímera (AM §8.5) |
| R38 | *Retirado — el endpoint DNS del plano de control elimina las redes autorizadas que describía (`landing-zone-qa` DZ4). El número no se reutiliza.* | — | — | — |
| R68 | **Un recurso fuera de la región o la jurisdicción de su entorno** | Media con varias regiones | Alto — datos fuera de su territorio; latencia y coste entre regiones | `gcp.resourceLocations` en la carpeta de cada jurisdicción; un proyecto no productivo y un bucket de estado por jurisdicción; G1 `environment.placement`; G3 `terraform.own_location` (§13.4; `multi-environment` DX4, DX5) |
| R66 | **El egress de la VPC denegado por defecto bloquea un flujo legítimo**: un puerto distinto de 443, o falta el permiso para el propio rango del entorno | Media con cada arquetipo nuevo | Alto si es el permiso interno — nada falla en el apply, y todos los webhooks de admisión expiran (con `failurePolicy: Fail`, bloqueo); Medio en otro caso | Regla de denegación con logs; la lista de permisos (443, el rango del entorno, el VIP privado) escrita antes del cluster; otros puertos por arquetipo en `egress_extra`, revisados; la lista verificada antes de instalar Gatekeeper (`network-qa` §2, VW6) |

## 4. Borde e ingress

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R20 | **El NEG de GCP no está en el estado de Terraform** | Segura | Media — la afirmación de "todo en IaC" es falsa | Referenciarlo por su URL determinista (nunca un `resource`, nunca una fuente `data` que hace fallar la preview), dividido en tres stacks con `after` comprobado por una regla G1 con nombre; registrar la ausencia de `iac-owned-edge` en el manifiesto del arquetipo en vez de ocultarla (§10.2) |
| R21 | **`TargetGroupBinding` deja que un tenant redirija el tráfico de otro** | Media en EKS compartido | Crítico | RBAC de Kubernetes que deniega el CRD a los namespaces de aplicación; solo el arquetipo `gateway` los crea; IAM del controlador acotado a target groups concretos (§10.3) |
| R22 | **Ciclo de arranque Keycloak ↔ Gateway** | Alta en el primer arranque en frío | Alta — el entorno no arranca | El `HTTPRoute` de Keycloak no lleva `SecurityPolicy`; el descubrimiento OIDC pasa por el Service interno del cluster; documentado como invariante (§10.7) |
| R24 | **`kubernetes_manifest` rompe las previsualizaciones de PR** | Alta si se usa | Media | Empaquetar los recursos personalizados de Gateway API en el chart Helm del arquetipo; desplegar con `helm_release` (§10.5) |
| R44 | **`SecurityPolicy` OIDC aplicada a una ruta que también sirve a clientes máquina** con sus propios tokens portador | Media, por homogeneidad | Alta — todo cliente de la API es redirigido al IdP y falla | Assertion en el generador para arquetipos que se autentican a sí mismos; documentado junto a la excepción de Keycloak (R22) |
| R45 | **Timeout por defecto de 30 s del backend service en el LB de Application externo de GCP** | Alta en subidas grandes | Media — 502 intermitente | Timeout fijado explícitamente en el stack de borde; `BackendTrafficPolicy` de Envoy a juego |

## 5. Multi-tenancy y entornos compartidos

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R5 | **Plataforma compartida destruida al desmontar una instancia** | Baja con salvaguardas, catastrófica sin ellas | Crítico | Etiqueta `protected` + comprobación del selector de destrucción + recuento de referencias en la CMDB por aristas, no por nombre (§12.4); R56 |
| R6 | **Renombrar una salida del productor rompe a N consumidores** | Media | Alta en plataformas compartidas | Tratar las salidas como un contrato versionado; añadir salidas nuevas junto a las viejas, deprecar en dos versiones; una regla G1 hace fallar el PR cuando una salida consumida falta en su productor y nombra al consumidor (§13.3, `terramate.contracts`); el grafo de relaciones de la CMDB dice a quién afecta |
| R11 | **Reconstruir el cluster invalida todo binding IRSA/WI en una plataforma compartida** | Baja | Alta | Tratar la sustitución del cluster como un evento de flota; mantener la lista de consumidores en la CMDB; ensayarlo en un entorno efímero |
| R13 | **Rol de ejecución de tarea compartido en un cluster ECS multi-tenant** | Alta por defecto | Alta — exposición de secretos entre tenants | Rol de ejecución por instancia, acotado a los ARN de secretos de esa instancia (§8.4) |
| R14 | **Servicio de Cloud Run desplegado con `ingress = ALL`** | Media | Alta — evita Cloud Armor, el WAF y los logs de acceso | Valor por defecto en globals + assertion + política de organización `constraints/run.allowedIngress` (§7.2) |
| R29 | **Bus Kafka compartido saturado por un tenant** | Media en `demos` | Alta — afecta a todos los tenants | Cuotas de productor/consumidor por `KafkaUser`, no solo ResourceQuota; presupuesto de `kafka_partitions` forzado en el PR (AM §10.3) |
| R30 | **Un tenant escribe topics de Kafka sin prefijo** | Alta sin política de admisión | Media — colisión silenciosa entre demos | Prefijo obligatorio `{{ instance }}-` forzado por el proveedor; ACL derivadas por el arquetipo `kafka`, nunca escritas a mano |
| R31 | **Los arquetipos demo se acumulan más allá de su utilidad** | Segura | Media — fuga de rangos, identidades y cuotas | `expiresOn` obligatorio para `kind: demo`; un job programado abre un PR de destrucción; nunca destrucción automática |
| R32 | **Cada demo aprovisiona su propia base de datos gestionada** | Segura en `demos`, por diseño | Media — un entorno de demos compartido deja de ser barato | Aceptado: los dos proveedores de `database-platform` dan a cada consumidor su propia instancia (`CLAUDE.md`, aislamiento antes que coste). Acotado por la capacity `managed_db_instances` del binding (25 en `demos`); un `Cluster` de CNPG cuesta menos que una instancia de Cloud SQL donde un cliente elige `postgres-operator` |
| R67 | **Nombres de entorno o de región que son prefijo de otros, o un entorno extraído del id de un stack**: `sandbox` y `sandbox-eu`, `europe-west1` y `europe-west10`; `split(id, "-")[1]` sobre `gcp-sandbox-eu-edge` | Media en cuanto hay varios entornos; segura para una regla que analiza ids en cuanto un nombre lleva `-` | Alto — las KSA, zonas DNS y permisos condicionados de un entorno alcanzan los del otro; una regla de ubicación deja pasar otra región; una regla de G1 bloquea cambios correctos o deja pasar una arista que falta | Nombres de entorno libres de prefijo (G1 `environment.names`); separador en toda comparación de prefijo; el entorno leído de `global.env` o de un tag, nunca de un id; reglas probadas con fixtures de un segundo entorno cuyo nombre lleva `-` (§13.3; `multi-environment` DX3) |
| R65 | **Un recurso de red o DNS de un entorno enlazado al de otro** en el proyecto non-prod compartido: una zona privada visible para otra VPC, una regla de firewall o una ruta sobre ella, un registro en sus zonas | Baja por error, posible a propósito | Alto — las APIs de Google o los nombres internos de otro entorno respondidos con direcciones que eligió este; su tráfico abierto o desviado; con escritura en su zona pública, certificados para sus nombres | G3 `terraform.own_network` (§13.4); `dns.admin` sobre el proyecto solo condicionado al prefijo de zona del entorno; prefijo de estado por entorno; revisión. Nunca llega a `prod` (`network-qa` DW8) |

## 6. Políticas y validación

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R33 | **Webhook de Gatekeeper caído con `failurePolicy: Fail`** | Baja | Crítico — el cluster rechaza toda admisión, incluida la propia recuperación de Gatekeeper | `exemptNamespaces` para `kube-system` y el namespace de Gatekeeper; ≥3 réplicas con un PDB; `Ignore` en todas partes salvo producción (§13.7) |
| R34 | **Divergencia del registro entre JSON Schema, los datos de conftest y los valores de Gatekeeper** | Alta sin una puerta | Alta — despliegues legítimos bloqueados en admisión, el peor sitio para descubrirlo | Una única fuente `registry/*.yaml`; los tres artefactos generados; puerta `registry-generate --check` (§13.8) |
| R35 | **Se adopta un add-on de política gestionado y luego hacen falta templates personalizados** | Media | Alta — el add-on de Azure es mutuamente excluyente con Gatekeeper autogestionado y restringe los templates personalizados | Gatekeeper autogestionado en las tres clouds; el trait `custom-templates` convierte la limitación en un error de resolución en vez de un descubrimiento (§13.5) |
| R36 | **Una regla Rego se escribe pero nunca se dispara** | Alta sin tests | Media — falsa confianza | `conftest verify` sobre `policy/*_test.rego` en el mismo job que la puerta (§13.3) |
| R37 | **Se asume que los runtimes serverless tienen la misma cobertura de políticas** | Media | Media — un control que se creía universal está ausente en Cloud Run y Fargate | Hueco de paridad declarado explícitamente (§13); ahí la política del plano de control cloud sustituye a la admisión |
| R46 | **El chart Helm de origen trae un init container privilegiado o como root** (sysctl, chown) | Alta | Media — el pod se rechaza bajo PSS `restricted`, o presión para eximir todo un namespace | Desactivarlo en los valores del arquetipo; trasladar el requisito al nodo (un trait como `sysctl-max-map-count`); exención por nombre solo como último recurso |
| R59 | **Una política singleton del proyecto escrita por un entorno**: Binary Authorization es una política por proyecto, y un stack `gke` que la escribe borra las reglas de los otros clusters no productivos | Alta si cada entorno la escribe | Alta — reglas de admisión de otros entornos borradas, sin error | Solo la escribe la landing zone, una regla por cluster a partir de los bindings, `ALWAYS_DENY` por defecto; una regla de G3 cuenta las reglas (`landing-zone-qa` §8) |

## 7. Proceso y herramientas

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R10 | **Comparativas de proveedores exageradas** | — | Media — elección de herramienta equivocada | Buena parte del material de Terramate frente a Terragrunt en circulación lo publica el propio Terramate. Validar uno mismo, en el PoC, las afirmaciones sobre detección de cambios y outputs sharing antes de comprometer a la organización |
| R28 | *Retirado — duplicado de R26, fusionado ahí. El número no se reutiliza.* | — | — | — |
| R55 | **El sync de la CMDB escribe en `main`**: un job con bypass de la protección de `main`, y un commit que vuelve a disparar `deploy` | Alta si la mitad observada se escribe en `main` | Media — un job que puede empujar a `main` sin revisión; un bucle de despliegue que solo contiene un `paths-ignore` | Mitad observada en su propia rama `cmdb-observed`, escrita solo por el workflow reutilizable `cmdb-sync`; el ruleset de `main` no tiene bypass (AM §11.1, §14.2) |
| R56 | **Aristas de la CMDB vacías en silencio**: el extractor no evalúa un `from_stack_id` y el stack parece no tener consumidores | Media hasta verificar el extractor con la versión fijada de Terramate | Crítico — la guarda de destroy cuenta 0 y deja ir una plataforma con consumidores (R5) | `archetypectl cmdb check` falla cuando un stack tiene bloques `input` y ningún `consumes` evaluado; un único extractor compartido con la regla de R2 de G1, así que fallan juntos (§12.4) |
| R57 | **Un valor secreto llega a la CMDB**: una salida que lo lleva no está marcada `sensitive` y acaba en la mitad observada y en el modelo de lectura | Media | Alta — un secreto en un fichero que cualquier lector del repositorio puede descargar | La regla de nombres de secreto de G1 (§13.3); el colector descarta las salidas `sensitive`; el modelo de lectura es un asset de release privado, nunca unas Pages públicas (AM §11.2) |
| R58 | **Arranque de la landing zone irrepetible**: nadie recuerda cómo se arrancó la organización cuando hay que reconstruirla | Media | Alta — la plataforma no se puede recrear desde el repositorio | El bootstrap es un stack del repositorio con un runbook, aplicado una vez a mano y gestionado después con estado remoto (`landing-zone-qa` §1) |
| R62 | **Un nombre ya ocupado en un proyecto compartido**: el plan dice `create` porque el recurso no está en nuestro estado, y la API responde `409` treinta recursos después | Media en un proyecto compartido o adoptado | Alto — la landing zone o un entorno aplicados a medias | Una comprobación previa de cada nombre antes del primer `apply`; nombres que llevan el repositorio o el entorno; nunca `import` de un recurso que no creamos (`landing-zone-qa` §1.3, RZ7) |
| R69 | **Un default de chart o módulo igual al valor de un entorno real**: un override que falta funciona en ese entorno y solo se ve en el siguiente | Alta sin la regla | Medio — el segundo entorno crea recursos con los nombres del primero, o choca con ellos | Defaults neutros o ausentes; el generador pasa siempre el valor; la derivación introducida con aceptación por diff vacío y comprobada con fixtures de un segundo entorno (`multi-environment` DX2, DX7) |
| R64 | **Redes autorizadas huérfanas** en la variante de acceso al plano de control que abre un `/32` por job: un runner que muere antes de su limpieza deja autorizada en el API server una IP del pool compartido del proveedor | Media donde se usa la variante | Medio — IAM y RBAC siguen protegiendo el endpoint; la barrera de red no | Retirada programada de entradas `gha-*` antiguas; alerta ante cambios en las redes autorizadas fuera del pipeline; un tope de entradas; el diseño por defecto (endpoint DNS, solo IAM) o un runner propio en la VPC lo evitan (`landing-zone-qa` §3.2, DZ16) |

---

## 8. Aplicaciones — SonarQube en `qa`

Específico de `docs/proposals/sonarqube-qa/`. Se mantiene aquí para que la fase de revisión lo trate junto con el resto.

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R47 | **Cola del compute engine saturada** — Community tiene un solo worker para ~800 análisis al día | Media-alta | Media — jobs de CI esperando el quality gate | Analizar solo `main`; `cancel-in-progress`; alerta de cola; medido en V4; Enterprise Edition como salida documentada |
| R48 | **Un análisis lanzado desde una pull request se registra como `main`** | Alta sin un control | Media — historia y gate de `main` incorrectos en silencio | Workflow reutilizable disparado solo en push a `main`; política sobre los ficheros de workflow |
| R49 | **OOMKill de las tres JVM** cuyos heaps más el non-heap superan el límite del contenedor | Alta sin el cálculo | Alta — exit 137, nada en el log | Heaps explícitos; límite = Σ heaps + margen; alerta de `OOMKilled` (guía del desarrollador §8.3) |
| R50 | **Pérdida de la clave de cifrado de settings** (`sonar-secret.txt`) | Baja | Alta — settings cifrados irrecuperables | Secret Manager con `prevent_destroy` y destrucción diferida de versiones |
| R51 | **Token global de análisis filtrado** desde uno de 200 repositorios | Media si se elige | Alta — expone todos los proyectos | Tokens por proyecto con caducidad, creados por el onboarding automatizado |
| R52 | **Un upgrade ejecuta una migración de base de datos irreversible** | Media | Alta | Backup de CNPG verificado antes de cada upgrade; el rollback es restaurar + la imagen anterior (guía del desarrollador §6) |
| R53 | **La pérdida de la zona deja varado el volumen persistente zonal** | Baja | Media — caída hasta que vuelve la zona | Aceptado para `qa`; disco regional (HA) como opción |

---

## Los cinco primeros a atajar

Ordenados por (probabilidad × impacto) con la mitigación aún sin implantar:

| Puesto | Riesgo | Por qué encabeza la lista |
|---|---|---|
| 1 | **R2** — falta `after` en un stack consumidor | Silencioso. Un orden sin resolver aplica un valor obsoleto o incorrecto sin ningún error. La puerta de política G1 debe ser bloqueante desde el primer día |
| 2 | **R12** — `sub` comodín en una política de confianza OIDC | Una línea de YAML permite que cualquier PR de rama o fork asuma el rol de apply. La configuración incorrecta de OIDC en AWS más común en informes públicos de incidentes |
| 3 | **R26** — rango de pods dimensionado para pocos nodos | Inmutable tras crear el cluster. Se descubre cuando el cluster deja de escalar, y solo se arregla reconstruyéndolo |
| 4 | **R34** — divergencia del registro | Falla en admisión, el peor sitio para diagnosticarlo, y solo después de que el generador y el `Constraint` ya hayan divergido |
| 5 | **R5** — plataforma compartida destruida al desmontar una instancia | Baja probabilidad con salvaguardas, catastrófica sin ellas. Un selector de etiqueta equivocado tumba a todos los tenants |

---

## Lista de revisión

En cada fase, confirmar para cada riesgo dentro de alcance:

- [ ] La mitigación está **implementada**, no solo documentada
- [ ] Donde la mitigación es una puerta de CI, es **bloqueante**, no solo informativa
- [ ] Donde la mitigación es una assertion, un test demuestra que se dispara
- [ ] La calificación de probabilidad sigue reflejando la realidad tras los cambios de la fase
- [ ] Ningún riesgo se ha retirado reutilizando su número R para otra cosa
