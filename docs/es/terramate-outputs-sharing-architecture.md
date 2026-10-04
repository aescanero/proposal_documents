# Arquetipos Terramate con Outputs Sharing

**Una arquitectura de referencia para infraestructura multi-cloud y multi-entorno usando Terramate CLI + OpenTofu**

| | |
|---|---|
| **Alcance** | Terramate CLI (OSS) + OpenTofu, sin HCP Terraform, sin Terraform Stacks |
| **Mecanismo central** | Terramate Outputs Sharing (`sharing_backend` / `output` / `input`) |
| **Clouds cubiertas** | Google Cloud, AWS y Azure a la par; extensible a una cuarta |
| **Audiencia** | Ingeniería de plataforma, arquitectura tecnológica |
| **Estado de la dependencia clave** | Outputs Sharing es una funcionalidad **experimental** de Terramate — ver [§15 Registro de riesgos](#15-risk-register) |

---

## Índice

1. [Por qué existe este documento](#1-why-this-document-exists)
2. [Conceptos centrales y vocabulario](#2-core-concepts-and-vocabulary)
3. [Arquitectura](#3-architecture)
4. [Referencia elemento por elemento](#4-element-by-element-reference)
5. [Guía A — Plataforma GKE y su cadena de dependencias](#5-guide-a--gke-platform-and-its-dependency-chain)
6. [Guía B — Plataforma EKS y su cadena de dependencias](#6-guide-b--eks-platform-and-its-dependency-chain)
7. [Guía C — Plataforma Cloud Run y su cadena de dependencias](#7-guide-c--cloud-run-platform-and-its-dependency-chain)
8. [Guía D — Plataforma ECS Fargate y su cadena de dependencias](#8-guide-d--ecs-fargate-platform-and-its-dependency-chain)
9. [Guía E — Plataforma AKS y su cadena de dependencias](#9-guide-e--aks-platform-and-its-dependency-chain)
10. [Adjunto de borde entre clouds](#10-edge-attachment-across-clouds)
11. [Identidad, acceso y línea base de seguridad](#11-identity-access-and-security-baseline)
12. [Gestión de entornos: dedicados y compartidos](#12-environment-management-dedicated-and-shared)
13. [Validación de políticas y seguridad](#13-policy-and-security-validation)
14. [CI/CD con GitHub Actions](#14-cicd-with-github-actions)
15. [Registro de riesgos](#15-risk-register) — registro completo en `risk-register.md`
16. [Hoja de ruta de adopción](#16-adoption-roadmap)
17. [Apéndice — chuleta de convenciones](#17-appendix--conventions-cheat-sheet)

> **Empieza por `platform-overview.md`** para un mapa del conjunto de documentos guiado por diagramas.
>
> **Los riesgos** viven en `risk-register.md`, agrupados por dominio y revisados en cada hito de fase.
>
> **Documento complementario.** `archetype-model.md` especifica el modelo de
> empaquetado de arquetipos — manifiestos, resolución de capability/trait,
> arquetipos multi-stack, el catálogo de componentes, pools jerárquicos de
> CIDR, recursos de tenant sobre operadores compartidos, la CMDB basada en
> Git, y el resolver que valida una composición y escribe `binding.tm.hcl`
> *antes* de que se ejecuten los generadores de este documento.

---

## 1. Por qué existe este documento

Terraform Stacks — el modelo de bloques `component` / `stack` / `deployment` publicado por HashiCorp — es una funcionalidad de la **plataforma alojada** (HCP Terraform y Terraform Enterprise 2.0+). No está disponible en el CLI de Terraform de código abierto, y no está disponible en absoluto en OpenTofu. El patrón por capas de "stacks dentro de stacks" que circula en la comunidad no puede, por tanto, ejecutarse sobre una cadena de herramientas solo-CLI.

Terramate resuelve la misma clase de problema con un modelo fundamentalmente distinto:

| Terraform Stacks (HCP) | Terramate (CLI) |
|---|---|
| Los stacks se componen anidando bloques `stack` | Los stacks son planos; **la abstracción vive en la generación de código** |
| Los inputs se pasan explícitamente entre capas de stack | Los datos fluyen mediante **globals** (tiempo de compilación) u **outputs sharing** (tiempo de ejecución) |
| Orquestación por la plataforma | Orquestación mediante `terramate run` en tu propia CI |
| Artefactos versionados y publicados en un registro | Generadores y módulos versionados en Git en un monorepo |

La consecuencia es que "una capa base de landing zone envuelta por una capa específica de cloud" **no** se convierte en stacks anidados. Se convierte en:

- **Generadores** (`generate_hcl`) que emiten el código Terraform/OpenTofu — la capa base.
- **Globals** sobrescritos a lo largo del árbol de directorios — las capas específicas de cloud y de entorno.
- **Outputs sharing** para pasar hechos de tiempo de ejecución (IDs de VPC, endpoints de cluster, ARNs de proveedor OIDC) entre stacks que no pueden conocerse en el momento de generar el código.

Este documento especifica esa arquitectura por completo.

---

## 2. Conceptos centrales y vocabulario

El vocabulario consistente importa aquí porque Terraform, Terragrunt y Terramate usan todos la palabra *stack* para cosas distintas.

| Término | Definición en esta arquitectura |
|---|---|
| **Módulo (Module)** | Un módulo OpenTofu reutilizable — recursos, variables, outputs, restricciones de proveedor. Sin backend. Vive en `modules/` o en un registro. |
| **Stack** | Un directorio que contiene un `stack.tm.hcl`, una configuración de backend y su propio fichero de estado. La unidad más pequeña que orquesta Terramate. |
| **Capability** | Un rol funcional que juega un stack: `network`, `cluster`, `data`, `platform-services`, `app`. Determina qué generador aplica. |
| **Platform** | Un conjunto de stacks que provee fundamentos compartidos para una cloud y un entorno: network + cluster + servicios de plataforma. Produce outputs. |
| **Archetype** | Una composición reutilizable y parametrizada de stacks de aplicación (p. ej. `webapp-3tier`). Una plantilla, no un despliegue. |
| **Archetype instance** | Un despliegue concreto de un arquetipo, ligado a una plataforma y un entorno. Consume outputs. |
| **Producer stack** | Un stack que declara bloques `output`. |
| **Consumer stack** | Un stack que declara bloques `input`. |
| **Binding** | El acto de apuntar una instancia de arquetipo a una plataforma específica, fijando los IDs de stack `global.platform.*`. |
| **Dedicated environment** | Una plataforma que sirve exactamente a una instancia de arquetipo. |
| **Shared environment** | Una plataforma que sirve a muchas instancias de arquetipo simultáneamente (típico en demos). |

### Cómo se localiza un stack

Todo stack se sitúa en la intersección de ejes independientes, y mantenerlos ortogonales es lo que hace que el modelo escale:

| Eje | Valores | Resuelto por |
|---|---|---|
| **Cloud** | gcp \| aws \| azure | globals + `condition` del generador — qué proveedor y backend se generan |
| **Environment** | prod \| qa \| dev \| demos \| ephemeral-* | posición del directorio + globals — dimensionamiento, proyecto/cuenta |
| **Capability** | network \| cluster \| platform-services \| data \| app | generadores + filtros de stack — qué módulo se invoca |
| **Archetype instance** | webapp-3tier/alpha, keycloak, … | subárbol de directorios — qué conjunto de stacks existe |

El eje de arquetipo lo especifica por completo el documento complementario: capabilities, traits, capas y la gramática del manifiesto que decide qué arquetipo puede satisfacer qué requisito. Este documento lo trata como dado y cubre la generación.

---

## 3. Arquitectura

### 3.1 Vista lógica

```mermaid
graph TD
    subgraph PL["Capa de plataforma — productores"]
        NET["network<br/>id: gcp-demos-network"]
        CLU["cluster<br/>id: gcp-demos-gke"]
        SVC["platform-services<br/>id: gcp-demos-services"]
    end

    subgraph AL["Capa de instancias de arquetipo — consumidores"]
        APPA["app: demo-alpha<br/>id: gcp-demos-alpha-app"]
        APPB["app: demo-beta<br/>id: gcp-demos-beta-app"]
        DATA["data: demo-alpha<br/>id: gcp-demos-alpha-data"]
    end

    NET -->|"network_self_link"| CLU
    CLU -->|"cluster_name<br/>cluster_endpoint<br/>cluster_ca"| SVC
    CLU -->|"cluster_name, endpoint, pool WI"| APPA
    CLU -->|"cluster_name, endpoint, pool WI"| APPB
    NET -->|"network_self_link<br/>private_service_range"| DATA
    DATA -->|"db_connection_name<br/>secret_id"| APPA
    SVC -->|"ingress_class<br/>dns_zone"| APPA
    SVC -->|"ingress_class<br/>dns_zone"| APPB
```

Dos propiedades de este grafo dirigen cada decisión de diseño posterior:

1. **La capa de plataforma es un publicador compartido.** Muchas instancias de arquetipo consumen de los mismos productores. Un cambio en un output de plataforma es un cambio disruptivo para cada consumidor.
2. **Las aristas son de tiempo de ejecución, no de tiempo de compilación.** Un `cluster_endpoint` no existe hasta que el cluster se aplica. Esto es exactamente lo que aborda outputs sharing y lo que los globals no pueden abordar.

### 3.2 Vista física — disposición del repositorio

```
repo/
├── terramate.tm.hcl                       # config raíz: experiments, sharing_backend, run env
├── mise.toml                              # versiones fijadas de terramate / tofu / checkov
├── .checkov/
│   ├── gcp.yaml
│   └── aws.yaml
│
├── modules/                               # módulos OpenTofu (o un registro remoto)
│   ├── gcp-network/
│   ├── gcp-gke/
│   ├── aws-network/
│   ├── aws-eks/
│   ├── app-workload/
│   └── ...
│
├── imports/                               # nunca contiene stacks; solo config importable
│   ├── mixins/
│   │   ├── backend_gcp.tm.hcl             # generate_hcl "_backend.tf" para GCS
│   │   ├── backend_aws.tm.hcl             # generate_hcl "_backend.tf" para S3
│   │   ├── provider_gcp.tm.hcl
│   │   ├── provider_aws.tm.hcl
│   │   └── labels.tm.hcl                  # labels/tags comunes inyectados en cada stack
│   │
│   ├── generators/v1/                     # "la capa base": un generador por capability
│   │   ├── gen_network.tm.hcl
│   │   ├── gen_cluster.tm.hcl
│   │   ├── gen_data.tm.hcl
│   │   ├── gen_platform_services.tm.hcl
│   │   └── gen_app.tm.hcl
│   │
│   └── contracts/                         # contratos output/input por capability
│       ├── contract_network_gcp.tm.hcl
│       ├── contract_network_aws.tm.hcl
│       ├── contract_cluster_gke.tm.hcl
│       ├── contract_cluster_eks.tm.hcl
│       └── contract_data.tm.hcl
│
├── archetypes/                            # el CATÁLOGO: un directorio por arquetipo, nunca por entorno
│   ├── webapp-3tier/manifest.yaml         # requires / provides / stacks / claims
│   └── event-driven/manifest.yaml
│
└── stacks/
    ├── platforms/
    │   ├── gcp/
    │   │   ├── config.tm.hcl              # globals: cloud = "gcp"
    │   │   ├── demos/               # entorno COMPARTIDO
    │   │   │   ├── config.tm.hcl          # globals: env, project_id, cidrs, sizing
    │   │   │   ├── network/     stack.tm.hcl
    │   │   │   ├── gke/         stack.tm.hcl
    │   │   │   └── services/    stack.tm.hcl
    │   │   └── prod/                       # entorno DEDICADO
    │   │       ├── config.tm.hcl
    │   │       ├── network/ gke/ services/
    │   └── aws/
    │       ├── config.tm.hcl              # globals: cloud = "aws"
    │       ├── demos/
    │       │   ├── config.tm.hcl
    │       │   ├── network/ eks/ services/
    │       └── prod/
    │           └── network/ eks/ services/
    │
    └── archetypes/
        ├── webapp-3tier/
        │   ├── archetype.tm.hcl           # globals comunes al arquetipo
        │   └── instances/
        │       ├── alpha/                 # ligada a gcp/demos
        │       │   ├── binding.tm.hcl     # ESCRITO POR EL RESOLVER
        │       │   ├── iam/       stack.tm.hcl
        │       │   ├── secrets/   stack.tm.hcl
        │       │   ├── data/      stack.tm.hcl
        │       │   ├── messaging/ stack.tm.hcl
        │       │   ├── firewall/  stack.tm.hcl
        │       │   ├── app/       stack.tm.hcl
        │       │   └── frontdoor/ stack.tm.hcl
        │       ├── beta/                  # ligada a la MISMA gcp/demos
        │       └── disasterproject-prod/             # ligada a aws/prod — dedicada
        └── event-driven/
            └── ...
```

Los directorios de stack de una instancia se **generan a partir de `stacks[]` del arquetipo**, y un stack cuya `condition` sea falsa no tiene directorio alguno. `binding.tm.hcl` es la salida del resolver, nunca editado a mano.

**Los manifiestos viven en la raíz, en `archetypes/<nombre>/`, no bajo `stacks/`.** Un manifiesto describe una *versión* de arquetipo, que varios entornos enlazan a la vez; dentro de uno de sus despliegues no tiene un sitio correcto en cuanto hay dos. `stacks/archetypes/<nombre>/` contiene solo `archetype.tm.hcl` y las instancias. Toda puerta que recorre `archetypes/*/manifest.yaml` (G1, la comprobación de esquema) depende de esta ruta, y un glob que no encuentra nada no valida nada — así que cada una falla también ante un resultado vacío (§14.4).

Tres reglas que hacen funcionar esta disposición:

- **`imports/` no contiene stacks.** Terramate nunca debe orquestar nada bajo este directorio. Solo contiene bloques `generate_hcl`, `globals` y de contrato que los stacks importan.
- **Un stack de plataforma nunca importa configuración de arquetipo, y viceversa.** El único acoplamiento es a través de outputs sharing.
- **Los ficheros generados se commitean en git** y llevan el prefijo `_` para que se ordenen juntos y sean fáciles de emparejar en `CODEOWNERS`.

### 3.3 Vista de flujo de datos — cómo viaja un valor

```mermaid
sequenceDiagram
    participant TG as terramate generate
    participant P as Stack productor
    participant C as Stack consumidor
    participant TF as tofu (consumidor)

    TG->>P: bloque output → _sharing_generated.tf (output)
    TG->>C: bloque input → _sharing_generated.tf (variable)
    Note over TG,C: ficheros generados commiteados en git

    Note over C: terramate run --enable-sharing
    C->>P: cd producer && tofu output -json
    P-->>C: JSON
    Note over C: evalúa outputs.NAME.value
    C->>TF: export TF_VAR_NAME=resuelto
    TF->>TF: plan / apply
```

La implicación crítica de la tercera flecha: **el job de CI que ejecuta un stack consumidor necesita acceso de lectura al backend de estado del stack productor.** En una topología multi-cuenta o multi-proyecto esto es un requisito de IAM concreto, cubierto en §11.5, y por guía en §5.6, §6.6, §7.7, §8.7 y §9.5.

---

## 4. Referencia elemento por elemento

### 4.1 `terramate.tm.hcl` — configuración raíz

```hcl
# /terramate.tm.hcl
terramate {
  # Fija una versión que hayas verificado. La semántica de bloques de
  # Outputs Sharing cambió en 0.10.9 (el campo `sensitive` perdió su valor por defecto).
  required_version = "= 0.17.3"     # la versión que midió poc/; mise.toml fija la misma

  config {
    # Outputs Sharing y los scripts son experimentales y deben activarse explícitamente.
    experiments = ["outputs-sharing", "scripts"]

    git {
      default_branch = "main"
      default_remote = "origin"
    }

    run {
      env {
        TF_PLUGIN_CACHE_DIR = "${terramate.root.path.fs.absolute}/.tofu-plugin-cache"
        TF_IN_AUTOMATION    = "1"
      }
    }
  }
}
```

| Elemento | Propósito | Notas |
|---|---|---|
| `required_version` | Protege contra la deriva del CLI entre los portátiles de los desarrolladores y la CI | Fíjala; no uses `latest` en CI |
| `experiments` | `outputs-sharing` habilita `sharing_backend`, `input`, `output`; `scripts` habilita los bloques `script` de §14 | Sin ellos los bloques son errores de parseo, y un solo bloque no reconocido hace fallar la carga de **toda** la configuración: cualquier comando `terramate`, `run` y `script run` incluidos, sale con 1 (medido, 0.17.3) |
| `config.git` | Línea base para la detección de cambios | `--changed` compara contra `default_branch` |
| `config.run.env` | Entorno inyectado en cada `terramate run` | Buen lugar para la caché de plugins; una caché compartida reduce materialmente el tiempo de CI cuando tienes docenas de stacks |

### 4.2 `sharing_backend` — el transporte

```hcl
# /terramate.tm.hcl (mismo fichero o un .tm.hcl hermano en la raíz)
sharing_backend "tofu" {
  type     = terraform                       # palabra clave, NO una cadena; funciona también para OpenTofu
  filename = "_sharing_generated.tf"
  command  = ["tofu", "output", "-json"]
}
```

| Atributo | Tipo | Significado |
|---|---|---|
| label (`"tofu"`) | string | Nombre referenciado por cada `input.backend` y `output.backend`. Usa un backend por motor de IaC, no por cloud. |
| `type` | keyword | Solo `terraform` está soportado hoy. Es una palabra clave desnuda — entrecomillarla es un error de sintaxis. |
| `filename` | string | El fichero que Terramate genera en cada stack, conteniendo los bloques `variable` / `output` derivados. |
| `command` | list(string) | Ejecutado **dentro del directorio del stack productor**; la salida estándar debe ser un objeto JSON. |

**Guía de diseño**

- Define el `sharing_backend` **una vez en la raíz del repositorio** para que sea visible a cada stack. Definirlo por cloud crea dos espacios de nombres que no pueden referenciarse entre sí, lo que rompe los arquetipos entre clouds.
- El `command` debe ser *barato y sin efectos secundarios*. `tofu output -json` requiere un directorio de trabajo inicializado; asegúrate de que tu CI ejecuta `tofu init` en los productores antes que en los consumidores, o envuelve el comando en un script que inicialice bajo demanda.
- Como es solo un comando que produce JSON, puedes sustituir más adelante una ruta más rápida (p. ej. leer un artefacto de outputs publicado en almacenamiento de objetos) sin cambiar ningún bloque `input`/`output`.

### 4.3 `output` — el contrato del productor

```hcl
# stacks/platforms/gcp/demos/network/outputs.tm.hcl
output "network_self_link" {
  backend     = "tofu"
  value       = module.network.network_self_link
  description = "Self link de la VPC compartida"
}

output "private_service_range" {
  backend = "tofu"
  value   = module.network.psa_range_name
}
```

| Atributo | Requerido | Significado |
|---|---|---|
| label | sí | Nombre del output. Es la **clave pública del contrato** — trata los renombrados como cambios disruptivos. |
| `backend` | sí | Debe coincidir con un label de `sharing_backend`. |
| `value` | sí | Expresión copiada **literalmente** al código OpenTofu generado y evaluada allí, así que puede referenciar `module.*`, `resource.*`, `data.*`, `local.*`. No `global.*`: Terramate no la interpola, y `global.project_id` llega al `.tf` como una referencia inválida (medido, 0.17.3, `poc/RESULTS.md` A8d). Tampoco un `var.*`, salvo que un `input` del mismo stack cree esa variable. Un valor que el stack conoce al generar lo emite el generador como `local` y se publica como `local.<nombre>` |
| `description` | no | Documenta el contrato en `imports/contracts/`. **No** se emite en el bloque `output` generado (medido, Terramate 0.16.0 y 0.17.3, `poc/RESULTS.es.md`), así que no llega a `tofu output`. Úsala igualmente — es donde un revisor lee qué significa la clave. |
| `sensitive` | no | Solo se emite cuando se fija. Ver la advertencia más abajo. |

> **Valores sensibles.** Outputs sharing resuelve valores en variables de entorno `TF_VAR_<name>` en el proceso del consumidor. Las variables de entorno son visibles para cualquier cosa en ese árbol de procesos y se filtran fácilmente a los logs de CI. **Nunca compartas secretos a través de outputs sharing.** Comparte *referencias* — un ID de secreto de Secret Manager, un nombre de parámetro SSM, un ARN de clave KMS — y deja que el stack consumidor lea el secreto mediante un data source bajo su propia identidad IAM.

**Dónde poner los bloques `output`.** Ponlos en `imports/contracts/` e impórtalos en el stack productor, no inline. Esto te da un único lugar donde revisar el contrato, y hace el contrato reutilizable en cada entorno que instancia la misma capability.

```hcl
# imports/contracts/contract_network_gcp.tm.hcl
# Importado por cada stack de network de GCP.
output "network_self_link"     { backend = "tofu"  value = module.network.network_self_link }
output "private_service_range" { backend = "tofu"  value = module.network.psa_range_name }
output "project_id"            { backend = "tofu"  value = module.network.project_id }
```

```hcl
# stacks/platforms/gcp/demos/network/stack.tm.hcl
stack {
  id   = "gcp-demos-network"
  name = "GCP demos — network"
  tags = ["gcp", "demos", "network", "platform", "producer"]
}

import { source = "/imports/contracts/contract_network_gcp.tm.hcl" }
import { source = "/imports/mixins/backend_gcp.tm.hcl" }
import { source = "/imports/mixins/provider_gcp.tm.hcl" }
import { source = "/imports/generators/v1/gen_network.tm.hcl" }
```

### 4.4 `input` — el contrato del consumidor

```hcl
# imports/contracts/contract_cluster_gke.tm.hcl — importado por los stacks de cluster GKE
input "network_self_link" {
  backend       = "tofu"
  from_stack_id = global.platform.network_stack_id
  value         = outputs.network_self_link.value
  mock          = "projects/mock-project/global/networks/mock-vpc"
}

input "subnet_self_link" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_subnet_stack_id   # el stack de subred del propio arquetipo gke (§5.2)
  value         = outputs.subnet_self_link.value
  mock          = "projects/mock-project/regions/europe-west1/subnetworks/mock-subnet"
}
```

| Atributo | Requerido | Significado |
|---|---|---|
| label | sí | Se convierte en una `variable "<label>"` generada en el consumidor. Referénciala como `var.<label>` en tu código generado. |
| `backend` | sí | Debe coincidir con un label de `sharing_backend`. |
| `from_stack_id` | sí | El **ID de stack** del productor. Es una expresión de cadena — y es la palanca más importante de esta arquitectura. |
| `value` | sí | Expresión sobre el espacio de nombres `outputs.*` construido a partir del JSON del productor. |
| `mock` | no | Valor de reserva usado solo cuando se pasa `--mock-on-fail`. Esencial para las previews de PR. |
| `sensitive` | no | Solo se emite cuando se fija. |

#### La palanca `from_stack_id`

Como `from_stack_id` acepta una expresión, puede pilotarse mediante un global:

```hcl
# stacks/archetypes/webapp-3tier/instances/alpha/binding.tm.hcl
globals "platform" {
  cloud              = "gcp"
  env                = "demos"
  network_stack_id   = "gcp-demos-network"
  cluster_stack_id   = "gcp-demos-gke"
  services_stack_id  = "gcp-demos-services"
  # Dónde viven las cargas de trabajo de esta instancia dentro de un cluster compartido:
  namespace          = "demo-alpha"
}
```

```hcl
# stacks/archetypes/webapp-3tier/instances/disasterproject-prod/binding.tm.hcl
globals "platform" {
  cloud              = "aws"
  env                = "prod"
  network_stack_id   = "aws-prod-network"
  cluster_stack_id   = "aws-prod-eks"
  services_stack_id  = "aws-prod-services"
  namespace          = "disasterproject"
}
```

Los bloques `input` del arquetipo se escriben **una sola vez**, en `imports/contracts/`, referenciando `global.platform.cluster_stack_id`. Ligar una instancia a una plataforma demo compartida o a una plataforma de producción dedicada es entonces un **fichero de cinco líneas**. Esto es lo que reemplaza la capa de "configuración del componente wrapper del stack" del patrón HCP Stacks — binding tardío mediante globals en lugar de anidamiento.

> **Decisión de diseño: `from_stack_id` es una expresión — medido.** Esta
> arquitectura se apoya en que `from_stack_id` resuelva globals, que es lo que
> permite que un único fichero de contrato por capability sirva a cada instancia.
> La PoC de la fase 0 (`poc/`, Terramate 0.16.0 y 0.17.3) confirmó las tres variantes que la
> forma básica no garantiza: globals **heredados** de un directorio padre;
> **interpolación** (`"${global.env}-gke"`); y el comportamiento de `mock` bajo
> `--mock-on-fail` cuando el productor no tiene estado. También mostró que
> `--mock-on-fail` **no** enmascara un `from_stack_id` que nombra un stack
> inexistente, así que un error tipográfico en un contrato falla en la preview.
>
> **Los globals no se resuelven en `stack.after`** — es un error de análisis que
> aborta todos los comandos de Terramate, no uno silencioso. El resolver escribe
> ahí valores literales, preferiblemente `after = ["tag:<capability>"]` (§4.5). El
> fallo silencioso que queda es un `after` *olvidado*: un consumidor con un
> `input` y sin orden se genera limpiamente y puede programarse antes que su
> productor. Ese es el riesgo R2; el lint de §14.4 lo detecta.

#### Los mocks no son opcionales

En cualquier repositorio donde un productor y un consumidor puedan cambiar en el mismo pull request, las previews de plan del consumidor fallarán — los nuevos outputs todavía no existen. Cada bloque `input` debería llevar un `mock` cuya **forma y tipo** coincidan con el valor real. Un mock del tipo equivocado produce un plan que tiene éxito localmente y falla al aplicar.

Convención: prefija cada mock con `mock-` para que un valor mockeado que aparezca en un log de *despliegue* sea reconocible de inmediato como un bug.

### 4.5 `stack` — identidad y ordenamiento

```hcl
stack {
  id    = "gcp-demos-gke"
  name  = "GCP demos — GKE cluster"
  tags  = ["gcp", "demos", "cluster", "gke", "platform", "producer"]
  after = ["/stacks/platforms/gcp/demos/network"]
}
```

> **Esta es la fuente más común de incidentes de producción en esta arquitectura.**
> Outputs sharing **no crea orden de ejecución**. Terramate ordena los stacks por
> anidamiento de directorios y solo por `before` / `after` explícitos. Un bloque
> `input` que referencia un productor se ejecutará alegremente antes que ese
> productor, resolverá contra un estado obsoleto (o fallará), y aplicará el valor
> equivocado.
>
> **Cada bloque `input` debe tener una entrada `after` correspondiente.** Refuérzalo
> con un lint del repositorio (§14.4).

Requisitos de `stack.id`:

- **Globalmente único** en todo el repositorio.
- **Estable.** Es la clave de cable del contrato de sharing. Renombrar un ID de stack rompe a cada consumidor ligado a él.
- **Derivable por humanos**, porque lo escribirás a mano en los ficheros de binding.

Convención: `<cloud>-<env>-<capability>[-<instance>]`

| Ejemplo | Significado |
|---|---|
| `gcp-demos-network` | Network compartida de la demo GCP |
| `aws-prod-eks` | Cluster EKS de producción en AWS |
| `gcp-demos-alpha-data` | Stack de datos de la instancia `alpha` en la plataforma demo compartida |

### 4.6 `globals` — la capa de tiempo de compilación

Los globals son el mecanismo que reemplaza la "capa wrapper específica de cloud" del patrón HCP. Se heredan a lo largo del árbol de directorios y pueden sobrescribirse en cualquier nivel.

```hcl
# stacks/platforms/gcp/config.tm.hcl                      ← capa de cloud
globals {
  cloud             = "gcp"
  state_bucket      = "disasterproject-tfstate-gcp"
  oidc_provider_var = "GOOGLE_WORKLOAD_IDENTITY_PROVIDER"
}
```

```hcl
# stacks/platforms/gcp/demos/config.tm.hcl          ← capa de entorno
globals {
  env        = "demos"
  project_id = "disasterproject-nonprod"
  region     = "europe-west1"
  vpc_cidr   = "10.4.0.0/17"             # reclamado del bloque permanente (AM §9.2)
}

globals "cluster" {
  min_nodes       = 1
  max_nodes       = 12
  machine_type    = "e2-standard-4"
  release_channel = "REGULAR"
  deletion_protection = false      # demo compartida: intencionadamente destruible
}

globals "policy" {
  # Las plataformas demo compartidas son multi-tenant; las cuotas son obligatorias.
  enforce_namespace_quota = true
  enforce_network_policy  = true
}
```

```hcl
# stacks/platforms/gcp/prod/config.tm.hcl                  ← capa de entorno (dedicada)
globals {
  env        = "prod"
  project_id = "disasterproject-prod"
  region     = "europe-west1"
  vpc_cidr   = "10.6.0.0/16"             # producción recibe una /16
}

globals "cluster" {
  min_nodes           = 3
  max_nodes           = 60
  machine_type        = "n2-standard-8"
  release_channel     = "STABLE"
  deletion_protection = true
}
```

**Regla general para elegir entre globals y outputs sharing:**

| El valor es... | Usa |
|---|---|
| Conocido antes del apply (CIDR, región, tipo de máquina, convención de nombres, un nombre de recurso determinista) | **Globals** |
| Solo conocible después del apply (ID generado, endpoint, certificado CA, ARN de proveedor OIDC) | **Outputs sharing** |
| Conocido antes del apply pero producido por el pipeline de otro equipo | **Globals**, poblados desde un fichero commiteado — no acoples pipelines innecesariamente |

Prefiere los globals siempre que sea posible. Cada arista de outputs sharing es un acoplamiento de tiempo de ejecución, un requisito de permiso de CI, y un modo de fallo. Cada global es una constante de tiempo de compilación.

### 4.7 `generate_hcl` — la capa base

Los generadores son donde vive la "landing zone generalizada". Un generador por capability, que selecciona el comportamiento a partir de globals.

```hcl
# imports/generators/v1/gen_cluster.tm.hcl
generate_hcl "_main.tf" {
  condition = global.capability == "cluster" && global.cloud == "gcp"

  content {
    module "gke" {
      source = "${terramate.stack.path.to_root}/modules/gcp-gke"

      project_id = global.project_id
      region     = global.region
      name       = "${global.env}-gke"

      # Valores de tiempo de compilación desde globals
      min_nodes       = global.cluster.min_nodes
      max_nodes       = global.cluster.max_nodes
      machine_type    = global.cluster.machine_type
      release_channel = global.cluster.release_channel

      # Valores de tiempo de ejecución que llegan vía outputs sharing como variables generadas
      network    = var.network_self_link
      subnetwork = var.subnet_self_link
      pods_range_name     = var.gke_pods_range_name
      services_range_name = var.gke_services_range_name

      labels = global.labels
    }
  }
}
```

| Atributo | Propósito |
|---|---|
| label | Nombre de fichero generado dentro de cada stack que coincide. Por convención se prefija con `_`. |
| `condition` | Expresión booleana sobre globals — la forma más limpia de ramificar por cloud y capability. |
| `stack_filter` | Selección basada en rutas (`project_paths`, `repository_paths`) cuando una condición resulta forzada. |
| `content` | El HCL a emitir. Las variables y funciones de Terramate se interpolan; todo lo demás pasa sin cambios. |

**Versionado de generadores.** Pon los generadores bajo `imports/generators/v1/` y protégelos con `condition = global.generators.version == "v1"`. Cuando necesites un cambio disruptivo, añade `v2/` al lado y migra los entornos uno a uno cambiando un global. Este es el equivalente en CLI a publicar una nueva versión de una configuración de componente de stack.

### 4.8 `script` — flujos de trabajo reutilizables

Los bloques `terramate script` te permiten nombrar un flujo de trabajo de varios pasos una sola vez e invocarlo de forma idéntica desde un portátil y desde CI. Fundamentalmente, los flags de sharing son expresables aquí.

```hcl
# /imports/scripts/tofu.tm.hcl (importado en la raíz)
script "tofu" "preview" {
  name        = "Plan changed stacks"
  description = "init, validate, plan con sharing y mocks"
  job {
    commands = [
      ["tofu", "init", "-lock-timeout=5m", "-input=false"],
      ["tofu", "validate"],
      ["tofu", "plan", "-out", "out.tfplan", "-lock=false", "-input=false", {
        enable_sharing = true
        mock_on_fail   = true
      }],
    ]
  }
}

script "tofu" "deploy" {
  name        = "Apply changed stacks"
  description = "init, plan, apply con sharing; mocks deshabilitados"
  job {
    commands = [
      ["tofu", "init", "-lock-timeout=5m", "-input=false"],
      ["tofu", "plan", "-out", "out.tfplan", "-input=false", {
        enable_sharing = true
      }],
      ["tofu", "apply", "-input=false", "-auto-approve", "-lock-timeout=5m", "out.tfplan"],
    ]
  }
}
```

> **`mock_on_fail` debe ser `true` para las previews y `false` para los despliegues.** Un despliegue que caiga silenciosamente a un valor mock aplicará un disparate. Mantener los dos caminos en scripts nombrados separados hace imposible equivocarse por accidente.

### 4.9 `assert` — barandillas en el momento de generar

Los bloques `assert` hacen fallar `terramate generate` cuando se viola un invariante. Úsalos para reforzar la arquitectura en lugar de solo documentarla.

```hcl
# imports/contracts/guards.tm.hcl
assert {
  assertion = global.platform.cloud == global.cloud
  message   = "La instancia de arquetipo está ligada a una plataforma ${global.platform.cloud} pero está en un árbol ${global.cloud}"
}

assert {
  assertion = global.env != "prod" || global.cluster.deletion_protection
  message   = "Los clusters de producción deben habilitar la protección contra borrado"
}

assert {
  assertion = !tm_contains(["demos"], global.env) || global.policy.enforce_namespace_quota
  message   = "Los entornos compartidos deben reforzar las cuotas de namespace"
}
```

### 4.10 Un arquetipo mapea a varios stacks

El documento complementario modela un arquetipo como un **conjunto de stacks con
ordenamiento interno** — Keycloak posee sus stacks de identidad, secretos, base de
datos, firewall, aplicación y front-door. Esto mapea directamente a las
primitivas de este documento:

| Modelo complementario | Este documento |
|---|---|
| `stacks[].name` | Un directorio con un `stack.tm.hcl` bajo la instancia |
| `stacks[].after` | `stack.after` |
| `stacks[].use: component/x` | Los generadores emiten el chart y los recursos del componente |
| `stacks[].condition` | Qué directorios de stack genera el resolver en absoluto |
| `provides[].outputs[].from` | A qué stack interno apunta el `from_stack_id` del consumidor |
| `claims[]` | Valores escritos en `binding.tm.hcl` como globals |

El resolver se ejecuta **antes** de `terramate generate` y produce el
`binding.tm.hcl` que consumen §4.4 y §4.6. Un stack cuya `condition` evalúa a
falso no se genera, así que su directorio no existe y Terramate nunca lo
orquesta.

El encapsulamiento importa aquí: `provides` pertenece al arquetipo, no a un
stack. Los consumidores referencian una capability; el resolver mapea cada
output al stack interno que lo produce. Reorganizar los stacks internos de un
arquetipo no es, por tanto, un cambio disruptivo, siempre que los nombres de
output se mantengan.

### 4.11 Primer despliegue de un entorno nuevo

**Paso 0 — antes de la secuencia, y no con la identidad del entorno.** Dos cosas preceden al primer apply de un entorno:

| | Qué | Quién lo aplica | Dónde se especifica |
|---|---|---|---|
| **0a** | **La landing zone existe.** El stack `gcp-lz-bootstrap` (bucket de estado, key ring `lz` con `tofu-state`, el pool de federación, `tf-plan-lz@`, `tf-apply-lz@`, `tf-destroy-lz@`) lo aplica **una vez por organización** una persona, con estado local, y su estado se migra al bucket; después el resto de la landing zone lo aplica el pipeline | Una persona con `organizationAdmin` y `billing.admin`, una vez; después el job `landing-zone` | `landing-zone-qa` §1 |
| **0b** | **El entorno se da de alta en la landing zone.** Una pull request añade `environments/<env>/binding.yaml`, del que la landing zone descubre el entorno (sin una segunda lista que mantener al paso): key ring de KMS y clave `tofu-state`, el prefijo de estado, `tf-plan-<env>@`, `tf-apply-<env>@`, `tf-destroy-<env>@` con sus vínculos de federación, la zona delegada y el `public_id`, el bloque de direcciones del pool global, la regla de Binary Authorization y la SA de nodos del runtime. De `metadata.jurisdiction` y `metadata.region` del binding deriva la carpeta y el proyecto, el bucket de estado y la ubicación del key ring (`multi-environment` DX6). La misma pull request añade `environments/<env>/binding.yaml`. Fuera del repositorio, un administrador crea los GitHub Environments `<env>` y `<env>-destroy` con sus revisores y su política de ramas — sin variables: la identidad se deriva del entorno (`landing-zone-qa` DZ12) | El job `landing-zone` (`tf-apply-lz@`); los GitHub Environments, un administrador del repositorio | `landing-zone-qa` §10; `infra-repo-qa` |

La identidad propia del entorno no puede hacer ninguna de las dos: no existe antes de 0b, y después no tiene ningún rol sobre la landing zone. Solo cuando ambas están hechas se ejecuta la secuencia de abajo — desde `first-deploy`, un workflow manual ligado al Environment `<env>`, que escribe el primer marcador de deploy del entorno (§14.2).

La misma secuencia aplica a cada cloud y runtime; solo cambian los selectores de tag.

```bash
terramate generate
git diff --exit-code                  # el código generado debe estar commiteado

# Apply escalonado — sharing habilitado, mocks DESACTIVADOS. Capas de plataforma primero.
terramate run --tags <cloud>:<env>:network  --enable-sharing -- tofu init -input=false
terramate run --tags <cloud>:<env>:network  --enable-sharing -- tofu apply -auto-approve
terramate run --tags <cloud>:<env>:cluster  --enable-sharing -- tofu init -input=false
terramate run --tags <cloud>:<env>:cluster  --enable-sharing -- tofu apply -auto-approve
terramate run --tags <cloud>:<env>:platform-services --enable-sharing -- tofu apply -auto-approve

# Una vez que la plataforma existe, una instancia se despliega en una sola ejecución ordenada.
terramate run --tags instance/<name> --enable-sharing -- tofu apply -auto-approve
```

El escalonamiento solo se requiere en un **primer** apply de un entorno nuevo, porque
el bloque provider de un consumidor no puede alcanzar un cluster que todavía no
existe. Después de eso, `terramate run --changed` resuelve todo el grafo en una
sola pasada.

### 4.12 Tabla resumen de elementos

| Elemento | Convención de fichero | Capa que implementa | Evaluado |
|---|---|---|---|
| `terramate` | `/terramate.tm.hcl` | Configuración del repositorio | generate + run |
| `sharing_backend` | `/terramate.tm.hcl` | Transporte para datos de tiempo de ejecución | generate + run |
| `globals` | `config.tm.hcl`, `binding.tm.hcl` | Capas de cloud / entorno / instancia | generate |
| `generate_hcl` | `imports/generators/vN/` | Capa base de landing zone | generate |
| `output` | `imports/contracts/` | Contrato del productor | generate + run |
| `input` | `imports/contracts/` | Contrato del consumidor, binding tardío | generate + run |
| `stack` | `<stack>/stack.tm.hcl` | Identidad, tags, ordenamiento | generate + run |
| `assert` | `imports/contracts/guards.tm.hcl` | Invariantes arquitectónicos | generate |
| `script` | `imports/scripts/` | Flujos de trabajo nombrados | run |

---

## 5. Guía A — Plataforma GKE y su cadena de dependencias

### 5.1 Grafo de dependencias

```mermaid
graph LR
    NET["<b>network</b><br/>gcp-ENV-network"] --> SUB["<b>gke-subnet</b><br/>gcp-ENV-gke-subnet"] --> GKE["<b>gke</b><br/>gcp-ENV-gke"]
    NET --> GKE
    GKE --> SVC["<b>services</b><br/>gcp-ENV-services"]
    NET --> DATA["<b>data</b><br/>gcp-ENV-INST-data"]
    GKE --> APP["<b>app</b><br/>gcp-ENV-INST-app"]
    SVC --> APP
    DATA --> APP
```

Cuatro niveles, aplicados en este orden; los stacks del mismo nivel se ejecutan en paralelo. Los dos stacks de `gke` son de un mismo arquetipo y se aplican seguidos.

| # | Stack | Capability | Produce | Consume |
|---|---|---|---|---|
| 1 | `gcp-ENV-network` | network | VPC, Cloud NAT, acceso privado a servicios | — |
| 2a | `gcp-ENV-gke-subnet` | cluster | Subred de nodos y sus dos rangos secundarios — los claims del runtime (AM §9.5) — con Private Google Access | network |
| 2b | `gcp-ENV-gke` | cluster | Cluster, node pools, pool de Workload Identity | network, gke-subnet |
| 3 | `gcp-ENV-services` | platform-services | Controlador de ingress, external-dns, cert-manager, namespaces | gke |
| 4a | `gcp-ENV-INST-data` | data | Cloud SQL, entradas de Secret Manager | network |
| 4b | `gcp-ENV-INST-app` | app | Workload, service account, bindings de IAM | gke, services, data |

### 5.2 Stack 1 — network (solo productor)

GKE en modo VPC-native requiere que existan **rangos IP secundarios para pods y servicios** en la subred antes de crear el cluster. **No** son de la red: el runtime reclama la subred de nodos y el rango de pods (AM §9.5), porque cada runtime tiene una forma distinta, así que los crea el arquetipo `gke` en su primer stack (§5.3). El contrato de la red lleva solo lo que comparten todos los runtimes. Dueño del claim, creador y autor de las reglas de firewall del rango son el mismo. Quitar esas salidas hizo del contrato de red la **3.0.0** —una versión mayor, porque rompe a quien las leía— y sus consumidores piden `^3.0.0` (propuesta `network-qa` §8.1).

```hcl
# imports/contracts/contract_network_gcp.tm.hcl
output "project_id"              { backend = "tofu"  value = module.network.project_id }   # no var.*: ningún stack la declara (§4.3)
output "region"                  { backend = "tofu"  value = module.network.region }
output "network_self_link"       { backend = "tofu"  value = module.network.network_self_link }
output "network_name"            { backend = "tofu"  value = module.network.network_name }
output "private_service_range"   { backend = "tofu"  value = module.network.psa_range_name }
```

```hcl
# stacks/platforms/gcp/demos/network/stack.tm.hcl
stack {
  id   = "gcp-demos-network"
  name = "GCP demos — network"
  tags = ["gcp", "demos", "network", "platform", "producer"]
}

globals { capability = "network" }

import { source = "/imports/mixins/backend_gcp.tm.hcl" }
import { source = "/imports/mixins/provider_gcp.tm.hcl" }
import { source = "/imports/generators/v1/gen_network.tm.hcl" }
import { source = "/imports/contracts/contract_network_gcp.tm.hcl" }
```

**Dimensionar los rangos es un asunto de globals, no de sharing.** Los rangos de pods deben dimensionarse para el número máximo de nodos multiplicado por pods-por-nodo; hacerlo mal requiere reconstruir el cluster. Calcúlalo de forma determinista:

```hcl
# stacks/platforms/gcp/demos/config.tm.hcl — los claims del arquetipo gke, tal como los asigna el ledger (AM §9.6)
globals {
  vpc_cidr           = "10.4.0.0/17"
  subnet_cidr        = tm_cidrsubnet(global.vpc_cidr, 3, 0)   # 10.4.0.0/20  — infra de zona
  pods_cidr          = tm_cidrsubnet(global.vpc_cidr, 1, 1)   # 10.4.64.0/18 — pods de zona
  services_cidr      = tm_cidrsubnet(global.vpc_cidr, 7, 32)  # 10.4.32.0/24 — borde de zona, como en el ledger de AM §9.6
}
```

### 5.3 Stack 2 — cluster GKE (consumidor y productor)

```hcl
# imports/contracts/contract_cluster_gke.tm.hcl

## ---- consume del stack de network ----
input "network_self_link" {
  backend       = "tofu"
  from_stack_id = global.platform.network_stack_id
  value         = outputs.network_self_link.value
  mock          = "projects/mock-project/global/networks/mock-vpc"
}

## ---- consume del stack de subred propio (gcp-demos-gke-subnet) ----
input "subnet_self_link" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_subnet_stack_id
  value         = outputs.subnet_self_link.value
  mock          = "projects/mock-project/regions/europe-west1/subnetworks/mock-subnet"
}
input "gke_pods_range_name" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_subnet_stack_id
  value         = outputs.gke_pods_range_name.value
  mock          = "mock-pods"
}
input "gke_services_range_name" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_subnet_stack_id
  value         = outputs.gke_services_range_name.value
  mock          = "mock-services"
}

## ---- produce para los stacks de services y app ----
output "cluster_name"     { backend = "tofu"  value = module.gke.name }
output "cluster_location" { backend = "tofu"  value = module.gke.location }
output "cluster_endpoint" { backend = "tofu"  value = module.gke.endpoint }
output "cluster_ca" {
  backend   = "tofu"
  value     = module.gke.ca_certificate
  sensitive = true
}
output "workload_identity_pool" {
  backend = "tofu"
  value   = module.gke.workload_identity_pool
}
output "node_service_account" { backend = "tofu"  value = module.gke.node_sa_email }
```

```hcl
# stacks/platforms/gcp/demos/gke/stack.tm.hcl
stack {
  id    = "gcp-demos-gke"
  name  = "GCP demos — GKE"
  tags  = ["gcp", "demos", "cluster", "gke", "platform", "producer", "consumer"]
  after = ["/stacks/platforms/gcp/demos/network", "/stacks/platforms/gcp/demos/gke-subnet"]   # OBLIGATORIO
}

globals {
  capability = "cluster"
}

globals "platform" {
  network_stack_id        = "gcp-demos-network"
  cluster_subnet_stack_id = "gcp-demos-gke-subnet"
}
```

Nótese que los *propios stacks de plataforma* usan la misma convención de binding `global.platform.*` que las instancias de arquetipo. Esto mantiene un único modelo mental y permite construir un segundo cluster sobre la misma network copiando un directorio y cambiando un global.

### 5.4 Stack 3 — servicios de plataforma (consumidor y productor)

Aquí es donde aparecen por primera vez los providers de Kubernetes y Helm, y contiene la advertencia específica de GKE más importante.

```hcl
# imports/generators/v1/gen_platform_services.tm.hcl
generate_hcl "_providers.tf" {
  condition = global.capability == "platform-services" && global.cloud == "gcp"

  content {
    # Token de corta duración obtenido en el momento del plan/apply. NUNCA compartido como output.
    data "google_client_config" "default" {}

    provider "kubernetes" {
      host                   = "https://${var.cluster_endpoint}"
      cluster_ca_certificate = base64decode(var.cluster_ca)
      token                  = data.google_client_config.default.access_token
    }

    provider "helm" {
      kubernetes {
        host                   = "https://${var.cluster_endpoint}"
        cluster_ca_certificate = base64decode(var.cluster_ca)
        token                  = data.google_client_config.default.access_token
      }
    }
  }
}
```

> **Nunca compartas credenciales como outputs.** El endpoint y el certificado CA son hechos estables y pertenecen al contrato de sharing. El token portador es una credencial de 60 minutos y debe obtenerlo cada consumidor mediante `google_client_config` bajo su propia identidad. Compartir un token a través de `TF_VAR_*` lo filtraría al entorno del proceso y, tarde o temprano, a un log de CI.

Contrato del stack de services:

```hcl
# imports/contracts/contract_services_gcp.tm.hcl
input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_stack_id
  value         = outputs.cluster_endpoint.value
  mock          = "mock-endpoint.example.invalid"
}
input "cluster_ca" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_stack_id
  value         = outputs.cluster_ca.value
  sensitive     = true
  mock          = "bW9jay1jYQ=="          # base64("mock-ca"): tipo correcto, y el valor decodificado conserva el prefijo mock-
}
input "workload_identity_pool" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_stack_id
  value         = outputs.workload_identity_pool.value
  mock          = "mock-project.svc.id.goog"
}

output "ingress_class"       { backend = "tofu"  value = "gce" }
output "dns_zone_name"       { backend = "tofu"  value = module.external_dns.zone_name }
output "cert_issuer_name"    { backend = "tofu"  value = module.cert_manager.cluster_issuer_name }
```

### 5.5 Stack 4 — instancia de arquetipo (consumidores)

El stack de aplicación es donde ocurre el binding de Workload Identity, y necesita hechos de tres productores a la vez.

```hcl
# imports/contracts/contract_app_gcp.tm.hcl
input "cluster_endpoint" {
  backend = "tofu"  from_stack_id = global.platform.cluster_stack_id
  value = outputs.cluster_endpoint.value  mock = "mock-endpoint.example.invalid"
}
input "cluster_ca" {
  backend = "tofu"  from_stack_id = global.platform.cluster_stack_id
  value = outputs.cluster_ca.value  sensitive = true  mock = "bW9jay1jYQ=="
}
input "workload_identity_pool" {
  backend = "tofu"  from_stack_id = global.platform.cluster_stack_id
  value = outputs.workload_identity_pool.value  mock = "mock-project.svc.id.goog"
}
input "ingress_class" {
  backend = "tofu"  from_stack_id = global.platform.services_stack_id
  value = outputs.ingress_class.value  mock = "mock-ingress"
}
input "db_connection_name" {
  backend = "tofu"  from_stack_id = global.platform.data_stack_id
  value = outputs.db_connection_name.value  mock = "mock:europe-west1:mock-db"
}
input "db_secret_id" {
  backend = "tofu"  from_stack_id = global.platform.data_stack_id
  value = outputs.db_secret_id.value  mock = "projects/mock/secrets/mock"
}
```

Binding de Workload Identity en el código generado:

```hcl
# imports/generators/v1/gen_app.tm.hcl (rama GCP, extracto)
generate_hcl "_workload_identity.tf" {
  condition = global.capability == "app" && global.platform.cloud == "gcp"

  content {
    resource "google_service_account" "app" {
      account_id = "${global.instance}-${global.app.name}"
      project    = global.project_id
    }

    resource "google_service_account_iam_member" "wi" {
      service_account_id = google_service_account.app.name
      role               = "roles/iam.workloadIdentityUser"
      member             = "serviceAccount:${var.workload_identity_pool}[${global.platform.namespace}/${global.app.name}]"
    }

    resource "kubernetes_service_account" "app" {
      metadata {
        name      = global.app.name
        namespace = global.platform.namespace
        annotations = {
          "iam.gke.io/gcp-service-account" = google_service_account.app.email
        }
      }
    }
  }
}
```

Nótese `global.platform.namespace` — esto es lo que permite que dos instancias de arquetipo coexistan en un cluster compartido. Cubierto completamente en §12.

### 5.6 Advertencias específicas de GKE

| Advertencia | Impacto | Mitigación |
|---|---|---|
| **Los rangos secundarios son inmutables** | Cambiar los CIDR de pods/servicios requiere recrear el cluster | Dimensiona generosamente en globals desde el primer día; calcula con `tm_cidrsubnet` para que sea revisable |
| **El provider de Kubernetes necesita un cluster vivo en el momento del plan** | `tofu plan` en el stack de services falla si el cluster todavía no se ha aplicado | Usa `--mock-on-fail` para las previews de PR; acepta que un primer despliegue de un entorno nuevo requiere un apply escalonado (network → cluster → services) |
| **`tofu output -json` en el stack de network requiere acceso de lectura al estado** | El job de CI que aplica el cluster debe leer el objeto de estado GCS del stack de network | Concede al job del cluster `roles/storage.objectViewer` sobre el prefijo de estado de network. Si network y cluster viven en proyectos distintos, esto es una concesión entre proyectos |
| **Endpoints de cluster privados** | Si el plano de control es privado, el runner de CI no puede alcanzar `cluster_endpoint` | O ejecuta la CI en un runner privado dentro de la VPC, o autoriza la IP de salida del runner en `master_authorized_networks`, o —en GKE, la opción de `qa`— usa el endpoint DNS del plano de control, alcanzable desde cualquier sitio y controlado solo por IAM (`landing-zone-qa` DZ4) |
| **`cluster_ca` es base64** | Un mock de `"mock"` rompe `base64decode()` en el momento del plan | Usa un mock con una cadena base64 válida (`"bW9jay1jYQ=="`, base64 de `mock-ca`: el valor decodificado conserva el prefijo) |
| **Protección contra borrado** | `deletion_protection = true` bloquea `tofu destroy` | Fíjala desde `global.cluster.deletion_protection`; `false` para demos, `true` para prod, reforzado con un `assert` |

### 5.7 Línea base de IAM y seguridad de GKE

| Control | Requisito | Justificación |
|---|---|---|
| Service account del nodo | SA dedicada con `roles/logging.logWriter`, `roles/monitoring.metricWriter`, `roles/stackdriver.resourceMetadata.writer`, `roles/artifactregistry.reader` | La SA de compute por defecto tiene `roles/editor`; cada nodo llevaría escritura a nivel de proyecto |
| Workload Identity | Habilitado a nivel de cluster y en cada node pool | Sin ello, los pods caen en la SA del nodo y todos los tenants comparten una identidad |
| Ocultación de metadatos | Endpoints de metadatos legacy deshabilitados (`metadata.disable-legacy-endpoints = true`) | Los endpoints legacy dejan que un pod lea directamente el token de la SA del nodo, anulando Workload Identity |
| Plano de control | Nodos privados; endpoint IP público desactivado y endpoint DNS solo IAM, o `master_authorized_networks` restringido | `landing-zone-qa` DZ4 |
| Nodos | Nodos GKE blindados (shielded), Container-Optimized OS, secure boot, monitorización de integridad | |
| Node pool | `enable_private_nodes = true`, sin IPs externas | |
| Secretos | Cifrado de secretos a nivel de aplicación con una clave de Cloud KMS | Cifrado de etcd en reposo con una clave que controlas |
| Procedencia de imagen | Binary Authorization requiriendo atestación | Bloquea imágenes no escaneadas o no confiables |
| RBAC | Cluster-admin ligado a un **Google Group**, nunca a usuarios individuales | La pertenencia a un grupo es auditable y revocable centralmente |
| Tenencia de namespace | Un namespace por instancia de arquetipo, `pod-security.kubernetes.io/enforce = restricted` | §12.3 |
| Permisos del deployer | `roles/container.admin` **más** `roles/iam.serviceAccountUser` sobre la SA del nodo | Crear un cluster que se ejecuta como una SA requiere `actAs` |
| Binding de Workload Identity | `serviceAccount:POOL[${global.platform.namespace}/${ksa}]` — nunca un comodín | Un comodín concede a cada pod del cluster los permisos de la GSA |

```hcl
assert {
  assertion = global.capability != "cluster" || global.cloud != "gcp" || global.gke.workload_identity_enabled
  message   = "Los clusters GKE deben habilitar Workload Identity"
}

assert {
  assertion = global.capability != "cluster" || global.cloud != "gcp" || global.gke.private_nodes
  message   = "Los node pools de GKE deben usar nodos privados"
}
```

Políticas de organización que respaldan esto (§11.7): `constraints/compute.requireShieldedVm`, `constraints/compute.vmExternalIpAccess`, `constraints/iam.disableServiceAccountKeyCreation`.

---

## 6. Guía B — Plataforma EKS y su cadena de dependencias

### 6.1 Grafo de dependencias

```mermaid
graph LR
    NET["<b>network</b><br/>aws-ENV-network"] --> SUB["<b>eks-subnets</b><br/>aws-ENV-eks-subnets"] --> EKS["<b>eks</b><br/>aws-ENV-eks"]
    NET --> EKS
    EKS --> SVC["<b>services</b><br/>aws-ENV-services"]
    NET --> DATA["<b>data</b><br/>aws-ENV-INST-data"]
    EKS --> IRSA["<b>app IAM</b><br/>aws-ENV-INST-app"]
    SVC --> IRSA
    DATA --> IRSA
```

Estructuralmente idéntico a GKE, también en quién es dueño de las subredes del runtime (§5.2): las crea el arquetipo `eks` en su primer stack. Las diferencias están enteramente en *qué hechos* cruzan las fronteras.

| # | Stack | Produce | Consume |
|---|---|---|---|
| 1 | `aws-ENV-network` | VPC, subredes públicas, NAT gateways, una tabla de rutas privada por AZ, la etiqueta `kubernetes.io/role/elb` en las subredes públicas | — |
| 2a | `aws-ENV-eks-subnets` | Subredes de nodos y del plano de control por AZ — los claims del runtime (AM §9.5) — asociadas a las tablas de rutas privadas, con las etiquetas `kubernetes.io/cluster/<name>` y `kubernetes.io/role/internal-elb` | network |
| 2b | `aws-ENV-eks` | Cluster, node groups, **proveedor OIDC**, access entries | network, eks-subnets |
| 3 | `aws-ENV-services` | AWS Load Balancer Controller, external-dns, karpenter | eks |
| 4a | `aws-ENV-INST-data` | RDS, ElastiCache, entradas de Secrets Manager | network |
| 4b | `aws-ENV-INST-app` | Workload, **rol IRSA**, recursos de namespace | eks, services, data |

### 6.2 Stack 1 — network, y la dependencia circular que ya no aparece

```hcl
# imports/contracts/contract_network_aws.tm.hcl
output "vpc_id"                  { backend = "tofu"  value = module.vpc.vpc_id }
output "vpc_cidr"                { backend = "tofu"  value = module.vpc.vpc_cidr_block }
output "public_subnet_ids"       { backend = "tofu"  value = module.vpc.public_subnets }
output "private_route_table_ids" { backend = "tofu"  value = module.vpc.private_route_table_ids }   # una por AZ, en orden de AZ
output "azs"                     { backend = "tofu"  value = module.vpc.azs }
output "nat_gateway_ips"         { backend = "tofu"  value = module.vpc.nat_public_ips }
```

> **La trampa del etiquetado de subredes, y por qué ya no aparece.** El AWS Load Balancer Controller descubre las subredes por etiqueta: `kubernetes.io/role/elb` en las públicas, `kubernetes.io/role/internal-elb` en las privadas y `kubernetes.io/cluster/<CLUSTER_NAME> = shared` en las que usa el cluster. Cuando el stack de **network** era dueño de todas las subredes, esas etiquetas referenciaban el nombre del **cluster**, producido por el stack **eks**, y cablear eso con outputs sharing creaba un ciclo: network → eks → network.
>
> **Con el runtime como dueño de sus subredes, el ciclo desaparece.** Las etiquetas que nombran al cluster van en subredes que crea el propio arquetipo `eks` (`eks-subnets`). La única etiqueta que escribe la red es `kubernetes.io/role/elb` en las subredes públicas, que no nombra al cluster: el controlador ya no necesita la etiqueta del cluster para descubrir subredes **(verificar en la versión fijada del controlador)**. El nombre del cluster se sigue derivando de forma determinista a partir de globals, porque lo leen `eks-subnets` y `eks`, y un nombre determinista es el remedio general siempre que outputs sharing parece necesitar un ciclo.

```hcl
# stacks/platforms/aws/config.tm.hcl
globals {
  cloud = "aws"
}

# stacks/platforms/aws/demos/config.tm.hcl
globals {
  env          = "demos"
  account_id   = "111122223333"
  region       = "eu-west-1"
  # Determinista: conocido en el momento de generar por AMBOS stacks. Rompe el ciclo.
  cluster_name = "disasterproject-demos-eks"
}
```

Tanto el generador de `eks-subnets` (para las etiquetas) como el de cluster (para el recurso del cluster) leen `global.cluster_name`. No hace falta ninguna arista de tiempo de ejecución. Este es el remedio general siempre que outputs sharing parece requerir un ciclo: **promociona el hecho compartido a un global**. Aquí la regla de propiedad ya elimina el ciclo; el global mantiene de acuerdo en el nombre a los dos stacks de un mismo arquetipo.

Añade una aserción para que los dos nunca puedan divergir:

```hcl
assert {
  assertion = tm_can(tm_regex("^[a-z0-9-]{1,38}$", global.cluster_name))
  message   = "cluster_name debe ser un nombre de cluster EKS válido"
}
```

### 6.3 Stack 2 — cluster EKS

```hcl
# imports/contracts/contract_cluster_eks.tm.hcl

## ---- consume del stack de network ----
input "vpc_id" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.vpc_id.value  mock = "vpc-mock00000000000"
}

## ---- consume del stack de subred propio (aws-demos-eks-subnets) ----
input "private_subnet_ids" {
  backend = "tofu"  from_stack_id = global.platform.cluster_subnet_stack_id
  value = outputs.private_subnet_ids.value
  mock  = ["subnet-mock0000000000a", "subnet-mock0000000000b", "subnet-mock0000000000c"]
}
input "intra_subnet_ids" {
  backend = "tofu"  from_stack_id = global.platform.cluster_subnet_stack_id
  value = outputs.intra_subnet_ids.value
  mock  = ["subnet-mock0000000000d", "subnet-mock0000000000e"]
}

## ---- produce ----
output "cluster_name"     { backend = "tofu"  value = module.eks.cluster_name }
output "cluster_endpoint" { backend = "tofu"  value = module.eks.cluster_endpoint }
output "cluster_ca" {
  backend = "tofu"  value = module.eks.cluster_certificate_authority_data  sensitive = true
}
output "cluster_version"            { backend = "tofu"  value = module.eks.cluster_version }
output "cluster_security_group_id"  { backend = "tofu"  value = module.eks.cluster_security_group_id }
output "node_security_group_id"     { backend = "tofu"  value = module.eks.node_security_group_id }
# Los dos hechos de los que depende cada rol IRSA en cada instancia de arquetipo:
output "oidc_provider_arn" { backend = "tofu"  value = module.eks.oidc_provider_arn }
output "oidc_provider_url" { backend = "tofu"  value = module.eks.oidc_provider }
```

Nótese que el mock de `private_subnet_ids` es una **lista**, coincidiendo con el tipo real. Un mock de cadena aquí produce un plan que tipa correctamente en local y explota al aplicar.

```hcl
# stacks/platforms/aws/demos/eks/stack.tm.hcl
stack {
  id    = "aws-demos-eks"
  name  = "AWS demos — EKS"
  tags  = ["aws", "demos", "cluster", "eks", "platform", "producer", "consumer"]
  after = ["/stacks/platforms/aws/demos/network", "/stacks/platforms/aws/demos/eks-subnets"]
}

globals { capability = "cluster" }
globals "platform" {
  network_stack_id        = "aws-demos-network"
  cluster_subnet_stack_id = "aws-demos-eks-subnets"
}
```

### 6.4 Stack 3 — servicios de plataforma

Mismo patrón de provider que GKE, con obtención de token específica de AWS:

```hcl
generate_hcl "_providers.tf" {
  condition = global.capability == "platform-services" && global.cloud == "aws"

  content {
    data "aws_eks_cluster_auth" "this" {
      name = var.cluster_name
    }

    provider "kubernetes" {
      host                   = var.cluster_endpoint
      cluster_ca_certificate = base64decode(var.cluster_ca)
      token                  = data.aws_eks_cluster_auth.this.token
    }

    provider "helm" {
      kubernetes {
        host                   = var.cluster_endpoint
        cluster_ca_certificate = base64decode(var.cluster_ca)
        token                  = data.aws_eks_cluster_auth.this.token
      }
    }
  }
}
```

De nuevo: el endpoint y el CA viajan por sharing; el token lo obtiene localmente cada consumidor.

El propio AWS Load Balancer Controller necesita IRSA, así que el stack de services también es consumidor de los outputs OIDC:

```hcl
input "oidc_provider_arn" {
  backend = "tofu"  from_stack_id = global.platform.cluster_stack_id
  value = outputs.oidc_provider_arn.value
  mock  = "arn:aws:iam::000000000000:oidc-provider/oidc.eks.eu-west-1.amazonaws.com/id/MOCK"
}
input "oidc_provider_url" {
  backend = "tofu"  from_stack_id = global.platform.cluster_stack_id
  value = outputs.oidc_provider_url.value
  mock  = "oidc.eks.eu-west-1.amazonaws.com/id/MOCK"
}

output "alb_controller_ready" { backend = "tofu"  value = helm_release.alb_controller.status }
output "ingress_class"        { backend = "tofu"  value = "alb" }
output "external_dns_zone_id" { backend = "tofu"  value = local.hosted_zone_id }   # un local que emite el generador (§4.3)
```

### 6.5 Stack 4 — instancia de arquetipo e IRSA

IRSA es el caso de uso canónico de outputs sharing en AWS: una trust policy que literalmente no puede escribirse sin un valor producido por el apply de otro stack.

```hcl
# imports/generators/v1/gen_app.tm.hcl (rama AWS, extracto)
generate_hcl "_irsa.tf" {
  condition = global.capability == "app" && global.platform.cloud == "aws"

  content {
    data "aws_iam_policy_document" "assume" {
      statement {
        effect  = "Allow"
        actions = ["sts:AssumeRoleWithWebIdentity"]

        principals {
          type        = "Federated"
          identifiers = [var.oidc_provider_arn]
        }

        condition {
          test     = "StringEquals"
          variable = "${var.oidc_provider_url}:sub"
          values   = ["system:serviceaccount:${global.platform.namespace}:${global.app.name}"]
        }

        condition {
          test     = "StringEquals"
          variable = "${var.oidc_provider_url}:aud"
          values   = ["sts.amazonaws.com"]
        }
      }
    }

    resource "aws_iam_role" "app" {
      name               = "${global.instance}-${global.app.name}-irsa"
      assume_role_policy = data.aws_iam_policy_document.assume.json
      tags               = global.tags
    }

    resource "kubernetes_service_account" "app" {
      metadata {
        name      = global.app.name
        namespace = global.platform.namespace
        annotations = {
          "eks.amazonaws.com/role-arn" = aws_iam_role.app.arn
        }
      }
    }
  }
}
```

La condición `sub` embebe `global.platform.namespace`. En un cluster compartido, esto es precisamente lo que evita que el rol IRSA de `demo-alpha` pueda ser asumido por los pods de `demo-beta`.

### 6.6 Advertencias específicas de EKS

| Advertencia | Impacto | Mitigación |
|---|---|---|
| **Ciclo del etiquetado de subredes** | Dependencia circular network ↔ eks, cuando la red era dueña de las subredes del cluster | No aparece: las subredes etiquetadas con el cluster son del arquetipo `eks` (§6.2); `global.cluster_name` sigue siendo determinista |
| **El proveedor OIDC es por cluster** | Cada instancia de arquetipo en un cluster compartido consume los *mismos* dos outputs | Está bien — pero significa que reconstruir el cluster invalida cada rol IRSA en cada instancia. Trata el reemplazo del cluster como un evento a nivel de flota |
| **`aws-auth` / access entries** | Escrituras concurrentes de múltiples stacks corrompen el ConfigMap | Posee el acceso al cluster **solo** en el stack eks. Usa EKS Access Entries (modo API) en lugar del ConfigMap `aws-auth`; las instancias de arquetipo nunca deben escribir en él |
| **Lecturas de estado entre cuentas** | El job de eks ejecuta `tofu output -json` en el directorio del stack de network | El rol de CI para el job del cluster necesita `s3:GetObject` sobre la clave de estado de network y `kms:Decrypt` sobre su clave KMS. Añade estos explícitamente a la trust policy del rol OIDC |
| **`cluster_endpoint` incluye el esquema** | A diferencia de GKE, EKS ya devuelve `https://...` | **No** prefijes `https://` de nuevo en el bloque provider. Esta asimetría entre las dos clouds es un bug de copiar-pegar común |
| **Endpoint API privado** | El runner de CI no puede alcanzar el plano de control | Runner privado de GitHub en la VPC, o `public_access_cidrs` permitiendo la salida del runner |
| **Ordenamiento de `private_subnet_ids`** | El orden de la lista desde el módulo VPC está ordenado por AZ pero no se garantiza estable entre actualizaciones del módulo | Ordena explícitamente en la expresión del output si algún consumidor indexa la lista |

### 6.7 Línea base de IAM y seguridad de EKS

| Control | Requisito | Justificación |
|---|---|---|
| Rol de cluster y rol de nodo | Roles separados, nunca fusionados | Principales de confianza y ciclos de vida distintos |
| Políticas del rol de nodo | `AmazonEKSWorkerNodePolicy`, `AmazonEC2ContainerRegistryReadOnly` | Mantén `AmazonEKS_CNI_Policy` **fuera** del rol de nodo — adjúntala vía IRSA a la service account `aws-node` en su lugar, para que los pods no puedan asumir permisos CNI a través del instance profile |
| IMDS | Hop limit 1, IMDSv2 requerido | Evita que un pod comprometido alcance el instance profile del nodo |
| Acceso al cluster | **EKS Access Entries** (modo de autenticación API), no el ConfigMap `aws-auth` | El ConfigMap no tiene rastro de auditoría IAM y se corrompe con escrituras concurrentes |
| Propiedad de access entries | Solo el stack `eks` escribe access entries | Las instancias de arquetipo nunca deben tocar el acceso al cluster |
| Condición de confianza IRSA | `StringEquals` tanto en `:sub` como `:aud`; `sub` fijado a `system:serviceaccount:NAMESPACE:SA` | `StringLike` con `*` concede el rol a cada pod del cluster |
| Límite de permisos | Adjuntado a cada rol IRSA creado por una instancia de arquetipo | Evita que un tenant escale privilegios a través de su propio stack |
| Cifrado de secretos | Cifrado envelope con una clave KMS gestionada por el cliente | Cifrado de etcd en reposo bajo una clave que controlas |
| Plano de control | Endpoint privado, o `public_access_cidrs` limitado a rangos de CI y admin | |
| Registro del plano de control | `api`, `audit`, `authenticator`, `controllerManager`, `scheduler` habilitados | El log de auditoría es el único registro de las decisiones de RBAC |
| Node groups | Bottlerocket o AL2023, launch template con EBS cifrado | |
| Tenencia de namespace | Un namespace por instancia, Pod Security Standard `restricted`, NetworkPolicy default-deny | §12.3 |

```hcl
data "aws_iam_policy_document" "assume" {
  statement {
    # ...
    condition {
      test     = "StringEquals"                      # NO StringLike
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${global.platform.namespace}:${global.app.name}"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name                 = "${global.instance}-${global.app.name}-irsa"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  permissions_boundary = var.task_role_boundary_arn   # publicado por el stack de plataforma
}
```

```hcl
assert {
  assertion = global.capability != "app" || global.platform.cloud != "aws" || tm_can(global.iam.permission_boundary)
  message   = "Los roles IRSA deben adjuntar el límite de permisos de la plataforma"
}
```

**EKS Pod Identity** es la alternativa más reciente a IRSA y elimina por completo la complejidad de la trust policy OIDC — la asociación se hace a través de la API de EKS en lugar de un documento de confianza IAM. Si la adoptas, el stack de cluster produce un flag `pod_identity_agent_ready` en lugar de los dos hechos OIDC, y el stack de app crea una asociación en lugar de una trust policy federada. La propiedad de alcance por namespace es idéntica.

SCPs de respaldo (§11.7): denegar `iam:CreateUser`, denegar `iam:DeleteRolePermissionsBoundary`, confinar regiones.

### 6.8 Comparación de contratos entre runtimes

| Concepto | Output GKE | Output EKS | Notas |
|---|---|---|---|
| Identidad de cluster | `cluster_name`, `cluster_location` | `cluster_name`, `cluster_version` | |
| Endpoint API | `cluster_endpoint` (sin esquema) | `cluster_endpoint` (**con** `https://`) | Asimetría — normalizar en el generador |
| Certificado CA | `cluster_ca` (base64) | `cluster_ca` (base64) | Misma forma |
| Token de autenticación | *no se comparte* — `google_client_config` | *no se comparte* — `aws_eks_cluster_auth` | Nunca compartir |
| Identidad de workload | `workload_identity_pool` | `oidc_provider_arn` + `oidc_provider_url` | AWS necesita dos hechos, GCP uno |
| Handle de network | `network_self_link` (network); `subnet_self_link` (stack de subred propio del runtime) | `vpc_id` (network); `private_subnet_ids` (lista, stack de subred propio del runtime) | Los self-links de GCP son cadenas, las subredes de AWS son listas |
| Networking de pods | `gke_pods_range_name`, `gke_services_range_name` (stack de subred propio del runtime) | — (VPC CNI usa los CIDR de subred) | GCP requiere rangos secundarios con nombre |
| Clase de ingress | `"gce"` | `"alb"` | Ambos desde el stack de services |

Mantener los *nombres* alineados donde el *significado* está alineado (`cluster_name`, `cluster_endpoint`, `cluster_ca`, `ingress_class`) es lo que permite que un único generador `gen_app.tm.hcl` sirva a ambas clouds con una sola rama `condition` para las partes específicas de cloud.

---

## 7. Guía C — Plataforma Cloud Run y su cadena de dependencias

Cloud Run elimina el cluster de la topología, lo que cambia la forma de la capa de plataforma pero no el patrón. El límite de aislamiento se mueve de *namespace de Kubernetes* a *servicio más su service account de runtime*, y eso resulta hacer que los entornos compartidos sean considerablemente más baratos — Cloud Run escala a cero, así que una instancia demo inactiva cuesta casi nada.

### 7.1 Grafo de dependencias

```mermaid
graph LR
    NET["<b>network</b><br/>gcp-ENV-network"] --> SUB["<b>run-subnet</b><br/>gcp-ENV-run-subnet"] --> APP["<b>app</b><br/>gcp-ENV-INST-run"]
    NET --> SP["<b>serverless-platform</b><br/>gcp-ENV-srvless"]
    NET --> DATA["<b>data</b><br/>gcp-ENV-INST-data"]
    SP --> APP["<b>app</b><br/>gcp-ENV-INST-run"]
    DATA --> APP
    APP --> EDGE["<b>edge-routing</b><br/>gcp-ENV-edge"]
```

| # | Stack | Produce | Consume |
|---|---|---|---|
| 1 | `gcp-ENV-network` | VPC, Cloud NAT, rango PSA | — |
| 2a | `gcp-ENV-run-subnet` | Subred de Direct VPC egress (o el conector Serverless VPC Access y su `/28`) — la reclamación del runtime (AM §9.5) — con Private Google Access y sus reglas de firewall | network |
| 2b | `gcp-ENV-srvless` | Artifact Registry, IP estática, mapa de Certificate Manager, política Cloud Armor, log sink | network |
| 3a | `gcp-ENV-INST-data` | Cloud SQL (IP privada), secretos de Secret Manager | network |
| 3b | `gcp-ENV-INST-run` | Servicio Cloud Run, SA de runtime, NEG serverless, backend service | run-subnet, srvless, data |
| 4 | `gcp-ENV-edge` | URL map, HTTPS proxy, forwarding rule | *ver §7.5 — fan-in* |

Los dos stacks del nivel 2 pertenecen al arquetipo `cloudrun`, con la misma forma que GKE (§5.1): el runtime crea la subred que reclama, y `network` no conoce ningún runtime.

Nótese la inversión de orden en el paso 4: el stack de edge-routing se ejecuta **después** de cada instancia, porque agrega sus backends. Ese fan-in es la única forma que outputs sharing maneja mal, y §7.5 cubre el remedio.

### 7.2 Stack 1 — network, y la subred de egress del runtime

El stack de network es **el mismo que usa GKE** (§5.2): el contrato `contract_network_gcp.tm.hcl`, versión 3.0.0, sin outputs serverless. No existe `contract_network_gcp_serverless.tm.hcl`. Cloud NAT cubre `ALL_SUBNETWORKS_ALL_IP_RANGES`, así que una subred que un runtime crea después sale sin ningún cambio en `network`.

Cloud Run alcanza recursos privados de una de dos formas. Elige una vez, en globals; el primer stack del arquetipo `cloudrun`, `gcp-ENV-run-subnet`, crea la que se elija.

| Mecanismo | Cuándo | Qué produce el stack `run-subnet` |
|---|---|---|
| **Direct VPC egress** | Preferido para builds nuevos — sin conector que dimensionar ni pagar | `direct_egress_subnet_id` (una subred reservada para Cloud Run) |
| **Conector Serverless VPC Access** | Legacy, o cuando necesitas un CIDR de conector fijo para reglas de firewall | `vpc_connector_id` |

```hcl
# imports/contracts/contract_run_subnet_gcp.tm.hcl
input "network_self_link" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.network_self_link.value
  mock  = "projects/mock-project/global/networks/mock-vpc"
}

output "direct_egress_subnet_id"  { backend = "tofu"  value = try(google_compute_subnetwork.egress[0].id, "") }
output "vpc_connector_id"         { backend = "tofu"  value = try(google_vpc_access_connector.this[0].id, "") }
output "egress_cidr"              { backend = "tofu"  value = local.serverless_subnet }
```

La subred es la reclamación del runtime (AM §9.5, `/24` mínimo), así que su propietario es también quien escribe sus reglas de firewall: las reglas de egress desde `egress_cidr` hacia el rango PSA y hacia los servicios privados del entorno viven en este stack, no en `network`. Reconstruir o eliminar la plataforma Cloud Run nunca toca la red. Los consumidores encuentran el stack mediante `global.platform.runtime_subnet_stack_id` (`gcp-demos-run-subnet`), la contrapartida serverless de `cluster_subnet_stack_id` (§5.3).

```hcl
# stacks/platforms/gcp/demos/config.tm.hcl (adiciones serverless)
globals "serverless" {
  egress_mode          = "direct"                # "direct" | "connector"
  egress_setting       = "PRIVATE_RANGES_ONLY"   # evita ALL_TRAFFIC a menos que el egress deba inspeccionarse
  serverless_subnet    = "10.4.40.0/24"          # borde de zona; /24 mínimo para Direct VPC egress — la reclamación del stack run-subnet
  ingress              = "INTERNAL_AND_CLOUD_LOAD_BALANCING"
}
```

> **Línea base de seguridad.** `ingress = "ALL"` en un servicio Cloud Run evita tu load balancer, y con él Cloud Armor, tus reglas WAF y tu logging. Fija `INTERNAL_AND_CLOUD_LOAD_BALANCING` en globals y refuérzalo con una aserción — esta es la configuración de Cloud Run mal configurada con más frecuencia.

```hcl
assert {
  assertion = global.serverless.ingress != "ALL"
  message   = "Cloud Run ingress=ALL evita el load balancer y Cloud Armor"
}
```

### 7.3 Stack 2 — plataforma serverless

```hcl
# imports/contracts/contract_serverless_platform.tm.hcl
input "network_self_link" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.network_self_link.value
  mock  = "projects/mock-project/global/networks/mock-vpc"
}

output "artifact_registry_repo" { backend = "tofu"  value = module.registry.repository_url }
output "artifact_registry_id"   { backend = "tofu"  value = module.registry.id }
output "static_ip_address"      { backend = "tofu"  value = module.edge.global_ip_address }
output "static_ip_name"         { backend = "tofu"  value = module.edge.global_ip_name }
output "cert_map_id"            { backend = "tofu"  value = module.edge.certificate_map_id }
output "cloud_armor_policy_id"  { backend = "tofu"  value = module.edge.security_policy_id }
output "dns_zone_name"          { backend = "tofu"  value = module.dns.zone_name }
output "run_service_agent"      { backend = "tofu"  value = "service-${local.project_number}@serverless-robot-prod.iam.gserviceaccount.com" }
```

`run_service_agent` importa: el **agente de servicio de Cloud Run**, no la service account de runtime, es quien extrae imágenes de Artifact Registry. Conceder `roles/artifactregistry.reader` al principal equivocado es un fallo clásico del primer despliegue.

### 7.4 Stack 3b — el servicio Cloud Run, y su IAM

Aquí es donde vive casi toda la postura de seguridad de Cloud Run.

```hcl
# imports/contracts/contract_app_cloudrun.tm.hcl
input "artifact_registry_repo" {
  backend = "tofu"  from_stack_id = global.platform.services_stack_id
  value = outputs.artifact_registry_repo.value
  mock  = "europe-west1-docker.pkg.dev/mock-project/mock-repo"
}
input "direct_egress_subnet_id" {
  backend = "tofu"  from_stack_id = global.platform.runtime_subnet_stack_id   # gcp-ENV-run-subnet, §7.2
  value = outputs.direct_egress_subnet_id.value
  mock  = "projects/mock-project/regions/europe-west1/subnetworks/mock-serverless"
}
input "cloud_armor_policy_id" {
  backend = "tofu"  from_stack_id = global.platform.services_stack_id
  value = outputs.cloud_armor_policy_id.value
  mock  = "projects/mock-project/global/securityPolicies/mock-policy"
}
input "db_connection_name" {
  backend = "tofu"  from_stack_id = global.platform.data_stack_id
  value = outputs.db_connection_name.value
  mock  = "mock-project:europe-west1:mock-db"
}
input "db_secret_id" {
  backend = "tofu"  from_stack_id = global.platform.data_stack_id
  value = outputs.db_secret_id.value
  mock  = "projects/mock-project/secrets/mock-secret"
}

# producido para el stack de edge-routing y para la CMDB
output "service_name"          { backend = "tofu"  value = google_cloud_run_v2_service.this.name }
output "service_uri"           { backend = "tofu"  value = google_cloud_run_v2_service.this.uri }
output "runtime_sa_email"      { backend = "tofu"  value = google_service_account.runtime.email }
output "backend_service_id"    { backend = "tofu"  value = google_compute_backend_service.this.id }
output "neg_id"                { backend = "tofu"  value = google_compute_region_network_endpoint_group.this.id }
```

```hcl
# imports/generators/v1/gen_app_cloudrun.tm.hcl (extracto)
generate_hcl "_service.tf" {
  condition = global.capability == "app" && global.platform.runtime == "cloudrun"

  content {
    # --- Identidad de runtime dedicada. NUNCA la service account de compute por defecto. ---
    resource "google_service_account" "runtime" {
      account_id   = "run-${global.instance}-${global.app.name}"
      display_name = "Cloud Run runtime — ${global.instance}/${global.app.name}"
      project      = global.project_id
    }

    # --- Concesiones de mínimo privilegio, ligadas al recurso exacto, nunca a nivel de proyecto ---
    resource "google_secret_manager_secret_iam_member" "db" {
      secret_id = var.db_secret_id
      role      = "roles/secretmanager.secretAccessor"
      member    = "serviceAccount:${google_service_account.runtime.email}"
    }

    resource "google_project_iam_member" "sql_client" {
      project = global.project_id
      role    = "roles/cloudsql.client"
      member  = "serviceAccount:${google_service_account.runtime.email}"
      # cloudsql.client no tiene binding a nivel de recurso; restringe con una condition en su lugar.
      # IAM evalúa projects/<p>/instances/<i>, NO el nombre de conexión <p>:<región>:<i> —
      # comparar con el nombre de conexión nunca coincide y el grant no hace nada, en silencio.
      condition {
        title      = "only-this-instance"
        expression = "resource.type == \"sqladmin.googleapis.com/Instance\" && resource.name == \"projects/${global.project_id}/instances/${element(split(":", var.db_connection_name), 2)}\""
      }
    }

    resource "google_cloud_run_v2_service" "this" {
      name     = "${global.instance}-${global.app.name}"
      location = global.region
      project  = global.project_id
      ingress  = global.serverless.ingress

      template {
        service_account = google_service_account.runtime.email

        # Direct VPC egress — sin recurso de conector que gestionar
        vpc_access {
          network_interfaces {
            subnetwork = var.direct_egress_subnet_id
          }
          egress = global.serverless.egress_setting
        }

        scaling {
          min_instance_count = global.app.min_instances
          max_instance_count = global.app.max_instances
        }

        containers {
          image = "${var.artifact_registry_repo}/${global.app.name}:${global.app.image_tag}"

          # Los secretos llegan por referencia, resueltos por Cloud Run al arrancar.
          # NO son variables de entorno en texto plano en la spec del servicio.
          env {
            name = "DB_PASSWORD"
            value_source {
              secret_key_ref {
                secret  = var.db_secret_id
                version = "latest"
              }
            }
          }

          resources {
            limits = {
              cpu    = global.app.cpu
              memory = global.app.memory
            }
          }
        }
      }

      # Tráfico fijado a la última revisión sana
      traffic {
        type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
        percent = 100
      }
    }

    # --- Invoker: solo el agente de servicio del LB, nunca allUsers cuando está detrás de un LB ---
    resource "google_cloud_run_v2_service_iam_member" "invoker" {
      name     = google_cloud_run_v2_service.this.name
      location = google_cloud_run_v2_service.this.location
      project  = global.project_id
      role     = "roles/run.invoker"
      member   = global.app.public ? "allUsers" : "serviceAccount:${global.app.invoker_sa}"
    }
  }
}
```

**Checklist de IAM de Cloud Run**

| Control | Requisito | Por qué |
|---|---|---|
| Service account de runtime | Dedicada por servicio; nunca la SA de compute por defecto | La SA de compute por defecto tiene `roles/editor` a nivel de proyecto |
| Permisos del deployer | `roles/run.admin` **más** `roles/iam.serviceAccountUser` sobre la SA de runtime | Desplegar un servicio que se ejecuta *como* una SA requiere `actAs`; que falte esto es el fallo de pipeline más común |
| Acceso a secretos | `roles/secretmanager.secretAccessor` sobre el **secreto específico** | Las concesiones a nivel de proyecto exponen los secretos de todos los tenants en una plataforma compartida |
| Cloud SQL | `roles/cloudsql.client` con una condition de IAM que restrinja a la instancia | El rol no tiene binding a nivel de recurso; las conditions son el único mecanismo de restricción |
| Extracción de imagen | `roles/artifactregistry.reader` al **agente de servicio de Cloud Run** | La SA de runtime no extrae imágenes |
| Invoker | Nunca `allUsers` en un servicio detrás de un LB | `allUsers` más `ingress=ALL` hace el servicio directamente alcanzable, evadiendo Cloud Armor |
| Procedencia de imagen | Política de Binary Authorization requiriendo atestación | Evita desplegar imágenes no escaneadas |
| Egress | `PRIVATE_RANGES_ONLY` a menos que se requiera inspección de egress | `ALL_TRAFFIC` enruta el tráfico hacia internet a través de la VPC y tu NAT, cambiando tu superficie de ataque de egress y el coste |

Restricciones de política de organización que merece la pena reforzar por encima del pipeline (§11.7): `constraints/iam.disableServiceAccountKeyCreation`, `constraints/run.allowedIngress`, `constraints/sql.restrictPublicIp`.

### 7.5 Stack 4 — enrutamiento de borde, y el límite de fan-in

El URL map debe referenciar el backend service de cada instancia. Expresado como outputs sharing, eso necesitaría un bloque `input` por tenant — pero la lista de tenants es dinámica, y los bloques `input` son declaraciones estáticas. **Aquí es donde outputs sharing deja de ser la herramienta adecuada.**

Dos remedios viables:

**Remedio A — nombres deterministas más data sources (recomendado).**

```hcl
# imports/generators/v1/gen_edge_routing.tm.hcl
generate_hcl "_url_map.tf" {
  condition = global.capability == "edge-routing"

  content {
    tm_dynamic "data" {
      for_each   = global.tenants
      labels     = ["google_compute_backend_service", tm_element(each.value, 0)]
      attributes = {
        name    = "bes-${each.value.instance}-${each.value.app}"
        project = global.project_id
      }
    }

    resource "google_compute_url_map" "this" {
      name            = "${global.env}-urlmap"
      default_service = data.google_compute_backend_service.default.id

      tm_dynamic "host_rule" {
        for_each = global.tenants
        content {
          hosts        = ["${host_rule.value.instance}.${global.dns_suffix}"]
          path_matcher = host_rule.value.instance
        }
      }
    }
  }
}
```

El stack de instancia nombra su backend service de forma determinista (`bes-<instance>-<app>`), el stack de edge lo busca. `global.tenants` es una lista de tiempo de compilación mantenida en el `config.tm.hcl` de la plataforma — añadir un tenant es un cambio revisable de una línea, y `terramate generate` muestra el diff.

**Remedio B — load balancer por instancia.** Cada instancia posee una forwarding rule completa que solo comparte la IP estática y el mapa de certificados. Más recursos y más coste, pero cero acoplamiento: destruir una instancia no puede romper el enrutamiento de otra. Preferible para entornos dedicados regulados; derrochador para una plataforma demo compartida.

> **La regla general.** Outputs sharing modela **1-a-N** (un productor, muchos consumidores) limpiamente. No modela el fan-in **N-a-1**, porque los bloques `input` no pueden generarse a partir de una lista dinámica. Cuando te topas con fan-in, recurre a nombres deterministas más data sources — el mismo remedio que el ciclo de etiquetado de subredes de EKS en §6.2.
>
> **En la arquitectura objetivo este problema no surge.** Gateway API invierte la dependencia de enrutamiento: un `HTTPRoute` vive en el namespace de la aplicación y se adjunta al Gateway, así que el borde nunca necesita conocer a sus tenants (§10.6). Los remedios A y B anteriores son para un borde basado en URL map, que es el fallback, no el plan.

### 7.6 Compartido y dedicado para Cloud Run

| Dimensión | Plataforma demo compartida | Producción dedicada |
|---|---|---|
| Límite de aislamiento | Servicio + service account de runtime | Proyecto |
| Aislamiento de cómputo | Sandbox por servicio (gVisor) — fuerte por defecto | Igual, más el límite de proyecto |
| Aislamiento de datos | Instancia de Cloud SQL propia por instancia de arquetipo, secretos separados — los datos nunca se comparten | Igual |
| Network | VPC del entorno, una subred de egress creada por `run-subnet` y compartida por los servicios del entorno | VPC dedicada, subred de egress propia |
| Coste en reposo | Casi cero — escala a cero | Cloud SQL y NAT siguen facturando |
| Control de cuotas | `max_instance_count` por servicio | Igual, más cuotas de proyecto |
| Radio de impacto de un cambio de plataforma | Todos los tenants | Un tenant |

El modelo general, las barandillas de ciclo de vida y la seguridad del destroy están en §12; esta tabla solo registra lo específico de Cloud Run.

Como Cloud Run aísla las cargas de trabajo en un sandbox por servicio en lugar de en nodos de kernel compartido, una plataforma Cloud Run compartida es **materialmente más segura que un node pool GKE compartido** para cargas de trabajo demo no confiables o semi-confiables. Las superficies compartidas restantes son la VPC, la instancia de base de datos y el load balancer — todo lo que cubre la tabla anterior.

Barandillas por tenant en una plataforma compartida:

```hcl
assert {
  assertion = global.platform.model != "shared" || global.app.max_instances <= 10
  message   = "Los tenants de Cloud Run compartido deben limitar max_instances para proteger el egress y las conexiones de BD compartidas"
}

assert {
  assertion = global.platform.model != "shared" || !global.app.public || global.app.cloud_armor_required
  message   = "Los servicios públicos en una plataforma compartida deben estar detrás de Cloud Armor"
}
```

Los límites de conexión de Cloud SQL son el fallo habitual de las plataformas compartidas: diez tenants escalando cada uno hasta 10 instancias con un pool de 5 agotarán una instancia pequeña. Limita `max_instances` y dimensiona la base de datos a partir de la suma, no de la media.

### 7.7 Advertencias de Cloud Run

| Advertencia | Impacto | Mitigación |
|---|---|---|
| `ingress = ALL` evade el LB | Cloud Armor, WAF y logs de acceso todos evadidos | Valor por defecto en globals + aserción + política de organización `constraints/run.allowedIngress` |
| SA de compute por defecto | El servicio se ejecuta con Editor de proyecto | SA de runtime dedicada, reforzada con una política personalizada de Checkov |
| Falta `iam.serviceAccountUser` | El deploy falla con un error confuso de `actAs` | Concédelo sobre la SA de runtime en el mismo stack que la crea |
| Dimensionamiento de la subred de Direct VPC egress | `/24` mínimo; el agotamiento estrangula el escalado | Dimensiona en globals con `tm_cidrsubnet`, revisa a nivel de plataforma |
| Fan-in en el URL map | Ciclo o lista de inputs inmanejable | Nombres deterministas + data sources (§7.5) |
| Proliferación de revisiones | Las revisiones antiguas retienen configuración de tráfico y confunden los rollbacks | Fija `traffic` a la última; poda revisiones según un calendario |
| Agotamiento de conexiones de Cloud SQL en plataformas compartidas | Un pico de tráfico del tenant A tumba al tenant B | Limita `max_instances`; usa el conector de Cloud SQL con pooling |

---

## 8. Guía D — Plataforma ECS Fargate y su cadena de dependencias

ECS sobre Fargate es la contrapartida AWS de Cloud Run en esta arquitectura: sin nodos que gestionar, aislamiento de kernel por tarea, y un límite de aislamiento que se sitúa en el *rol de tarea* en lugar de en un namespace. El modelo de IAM es la parte más distintiva — ECS separa los permisos de tiempo de ejecución y de tiempo de arranque en **dos roles separados**, y equivocarse en esa separación es el defecto de seguridad más común en los despliegues ECS.

> Esta guía cubre **ECS sobre Fargate**. Los perfiles de EKS Fargate son un producto distinto — ver §8.8 sobre cómo encajan en la guía EKS en su lugar.

### 8.1 Grafo de dependencias

```mermaid
graph LR
    NET["<b>network</b><br/>aws-ENV-network"] --> SUB["<b>ecs-subnets</b><br/>aws-ENV-ecs-subnets"] --> ECS["<b>ecs-platform</b><br/>aws-ENV-ecs"]
    NET --> ECS
    NET --> DATA["<b>data</b><br/>aws-ENV-INST-data"]
    ECS --> APP["<b>app</b><br/>aws-ENV-INST-svc"]
    SUB --> APP
    DATA --> APP
```

| # | Stack | Produce | Consume |
|---|---|---|---|
| 1 | `aws-ENV-network` | VPC, subredes públicas, NAT gateways, una tabla de rutas privada por AZ, **endpoints de VPC** en sus propias subredes de endpoints `/28`, SG del endpoint | — |
| 2a | `aws-ENV-ecs-subnets` | Subredes de tareas por AZ — la reclamación del runtime (AM §9.5), una ENI por tarea — asociadas a las tablas de rutas privadas | network |
| 2b | `aws-ENV-ecs` | Cluster ECS, ALB, WAF, repos ECR, namespace de Cloud Map, log groups, SG del ALB | network, ecs-subnets |
| 3a | `aws-ENV-INST-data` | RDS, secreto de Secrets Manager, security group de BD | network |
| 3b | `aws-ENV-INST-svc` | Definición de tarea, **rol de tarea**, **rol de ejecución**, servicio, target group, listener rule, SG del servicio | ecs-subnets, ecs, data |

Los dos stacks del nivel 2 pertenecen al arquetipo `fargate`, con la misma forma que EKS (§6.1): el runtime crea las subredes de tareas que reclama, y `network` no conoce ningún runtime.

A diferencia de Cloud Run, no hay stack de fan-in: las listener rules del ALB son recursos separados que posee cada instancia, adjuntados al listener compartido por ARN. Añadir o eliminar un tenant solo toca el stack de ese tenant.

### 8.2 Stack 1 — network, con endpoints de VPC

Las tareas Fargate en subredes privadas deben alcanzar ECR, CloudWatch Logs y Secrets Manager. Enrutar eso a través de un NAT gateway funciona pero cuesta dinero y envía tráfico de plano de control por internet. **Los endpoints de VPC son la línea base de mejores prácticas** y son un asunto del stack de network: sirven a todos los runtimes del entorno, no solo a Fargate.

El contrato de network es **el mismo que usa EKS** (§6.2), más el security group de los endpoints. No hay `private_subnet_ids`: las subredes de tareas son del arquetipo `fargate`, creadas en `aws-ENV-ecs-subnets` y asociadas a las tablas de rutas que publica la red.

```hcl
# imports/contracts/contract_network_aws.tm.hcl
output "vpc_id"                  { backend = "tofu"  value = module.vpc.vpc_id }
output "vpc_cidr"                { backend = "tofu"  value = module.vpc.vpc_cidr_block }
output "public_subnet_ids"       { backend = "tofu"  value = module.vpc.public_subnets }
output "private_route_table_ids" { backend = "tofu"  value = module.vpc.private_route_table_ids }   # una por AZ, en orden de AZ
output "endpoint_sg_id"          { backend = "tofu"  value = module.vpc.vpc_endpoint_security_group_id }
output "azs"                     { backend = "tofu"  value = module.vpc.azs }
```

Dónde viven los endpoints, y por qué esto no reintroduce un runtime en `network`:

| Pieza | Propietario | Por qué |
|---|---|---|
| Endpoints de tipo interface | `network`, en sus propias subredes de endpoints `/28` por AZ (zona `infra`) | Infraestructura compartida por todos los runtimes, como la subred de private endpoints de AKS (§9.2) |
| Endpoint gateway de S3 | `network`, asociado a las tablas de rutas privadas | Las tablas de rutas son de la red; cualquier subred asociada después lo hereda |
| SG de los endpoints | `network` | Admite 443 desde `vpc_cidr`, así que no nombra ninguna subred de runtime y no necesita cambios cuando se crea una |
| Subredes de tareas | `ecs-subnets` | La reclamación del runtime; propietario de la reclamación, creador y escritor del firewall son uno |

```hcl
# imports/contracts/contract_ecs_subnets.tm.hcl
input "private_route_table_ids" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.private_route_table_ids.value
  mock  = ["rtb-mock0000000000a", "rtb-mock0000000000b"]
}

output "task_subnet_ids" { backend = "tofu"  value = aws_subnet.task[*].id }   # en orden de AZ, una por AZ
```

Los consumidores — el stack `ecs` y cada stack `svc` — lo encuentran mediante `global.platform.runtime_subnet_stack_id` (`aws-demos-ecs-subnets`). Las subredes de tareas se dimensionan para el pico de tareas del entorno, porque cada tarea ocupa una dirección.

Endpoints requeridos, generados a partir de globals:

| Endpoint | Tipo | Por qué |
|---|---|---|
| `ecr.api`, `ecr.dkr` | Interface | Extracción de imagen sin NAT |
| `s3` | Gateway | Las capas de ECR se almacenan en S3 |
| `logs` | Interface | Driver `awslogs` |
| `secretsmanager` / `ssm` | Interface | Inyección de secretos al arrancar la tarea |
| `sts` | Interface | Emisión de credenciales del rol de tarea |
| `ssmmessages` | Interface | Solo si ECS Exec está habilitado |

```hcl
assert {
  assertion = global.env == "demos" || tm_contains(global.network.vpc_endpoints, "secretsmanager")
  message   = "Los entornos no-demo deben alcanzar Secrets Manager por un endpoint de VPC, no por NAT"
}
```

### 8.3 Stack 2 — plataforma ECS

```hcl
# imports/contracts/contract_ecs_platform.tm.hcl
input "vpc_id" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.vpc_id.value  mock = "vpc-mock00000000000"
}
input "task_subnet_ids" {
  backend = "tofu"  from_stack_id = global.platform.runtime_subnet_stack_id   # aws-ENV-ecs-subnets, §8.2
  value = outputs.task_subnet_ids.value
  mock  = ["subnet-mock0000000000a", "subnet-mock0000000000b"]
}
input "public_subnet_ids" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.public_subnet_ids.value
  mock  = ["subnet-mock0000000000c", "subnet-mock0000000000d"]
}

output "cluster_arn"            { backend = "tofu"  value = module.ecs.cluster_arn }
output "cluster_name"           { backend = "tofu"  value = module.ecs.cluster_name }
output "alb_arn"                { backend = "tofu"  value = module.alb.arn }
output "alb_dns_name"           { backend = "tofu"  value = module.alb.dns_name }
output "alb_zone_id"            { backend = "tofu"  value = module.alb.zone_id }
output "alb_https_listener_arn" { backend = "tofu"  value = module.alb.https_listener_arn }
output "alb_security_group_id"  { backend = "tofu"  value = module.alb.security_group_id }
output "ecr_registry_url"       { backend = "tofu"  value = module.ecr.registry_url }
output "cloudmap_namespace_id"  { backend = "tofu"  value = module.ecs.cloudmap_namespace_id }
output "log_group_prefix"       { backend = "tofu"  value = "/ecs/${local.cluster_name}" }
output "task_role_boundary_arn" { backend = "tofu"  value = aws_iam_policy.tenant_boundary.arn }
```

Ese último output es la piedra angular de la multi-tenencia. La plataforma publica una **política de límite de permisos**, y cada instancia de arquetipo está obligada a adjuntarla a cualquier rol IAM que cree. Un tenant no puede entonces concederse a sí mismo más de lo que permite el límite, aunque su propio stack esté comprometido o mal escrito.

```hcl
# imports/generators/v1/gen_ecs_platform.tm.hcl (extracto)
resource "aws_iam_policy" "tenant_boundary" {
  name = "${global.env}-tenant-boundary"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Permite solo los namespaces de servicio que un workload de tenant necesita legítimamente
        Effect = "Allow"
        Action = [
          "s3:*", "sqs:*", "sns:*", "dynamodb:*",
          "secretsmanager:GetSecretValue", "kms:Decrypt",
          "logs:CreateLogStream", "logs:PutLogEvents",
          "xray:PutTraceSegments", "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      },
      {
        # Denegaciones duras que ninguna política de tenant puede sobrescribir
        Effect = "Deny"
        Action = [
          "iam:CreateUser", "iam:CreateAccessKey", "iam:AttachUserPolicy",
          "iam:PutRolePolicy", "iam:AttachRolePolicy", "iam:DeleteRolePermissionsBoundary",
          "organizations:*", "account:*"
        ]
        Resource = "*"
      },
      {
        # Confinamiento de región
        Effect = "Deny"
        NotAction = ["iam:*", "sts:*", "cloudfront:*", "route53:*"]
        Resource = "*"
        Condition = { StringNotEquals = { "aws:RequestedRegion" = global.region } }
      }
    ]
  })
}
```

### 8.4 Stack 3b — el servicio, y el modelo de dos roles

**Esta es la sección que hay que leer dos veces.** ECS separa los permisos en dos roles con ciclos de vida y modelos de amenaza completamente distintos.

| | **Rol de ejecución de tarea** | **Rol de tarea** |
|---|---|---|
| Usado por | El agente ECS / la infraestructura de Fargate | El código de tu aplicación |
| Cuándo | Antes de que arranque el contenedor | Durante toda la vida del contenedor |
| Permisos típicos | Extraer imagen de ECR, crear log streams, leer secretos referenciados en la definición de tarea | S3, SQS, DynamoDB — lo que sea que llame la app |
| ¿Alcanzable desde dentro del contenedor? | **No** | **Sí**, vía el endpoint de metadatos de la tarea |
| Impacto de un compromiso | El atacante necesita ejecución de código *antes* de arrancar — raro | Un atacante con RCE en el contenedor tiene estos permisos inmediatamente |

> **En un cluster compartido, no compartas el rol de ejecución entre tenants.** Un rol de ejecución compartido debe poder leer los secretos de cada tenant, lo que significa que los ARNs de secreto del tenant B son legibles por el rol que arranca las tareas del tenant A. Crea un **rol de ejecución por instancia** restringido a los secretos de esa instancia, aunque duplique los permisos de ECR y logs. La duplicación es barata; la exposición de secretos entre tenants no lo es.

```hcl
# imports/generators/v1/gen_app_fargate.tm.hcl (extracto)
generate_hcl "_iam.tf" {
  condition = global.capability == "app" && global.platform.runtime == "fargate"

  content {
    data "aws_iam_policy_document" "ecs_assume" {
      statement {
        effect  = "Allow"
        actions = ["sts:AssumeRole"]
        principals {
          type        = "Service"
          identifiers = ["ecs-tasks.amazonaws.com"]
        }
        # Protección contra el "confused deputy": fijado a esta cuenta y este cluster
        condition {
          test     = "ArnLike"
          variable = "aws:SourceArn"
          values   = ["arn:aws:ecs:${global.region}:${global.account_id}:*"]
        }
        condition {
          test     = "StringEquals"
          variable = "aws:SourceAccount"
          values   = [global.account_id]
        }
      }
    }

    # ---------- ROL DE EJECUCIÓN — por instancia, no compartido ----------
    resource "aws_iam_role" "execution" {
      name                 = "${global.instance}-${global.app.name}-exec"
      assume_role_policy   = data.aws_iam_policy_document.ecs_assume.json
      permissions_boundary = var.task_role_boundary_arn
      tags                 = global.tags
    }

    resource "aws_iam_role_policy" "execution" {
      role = aws_iam_role.execution.id
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Effect   = "Allow"
            Action   = ["ecr:GetAuthorizationToken"]
            Resource = "*"                                   # esta acción no tiene alcance de recurso
          },
          {
            Effect   = "Allow"
            Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
            Resource = ["arn:aws:ecr:${global.region}:${global.account_id}:repository/${global.app.name}"]
          },
          {
            Effect   = "Allow"
            Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
            Resource = ["${var.log_group_prefix}/${global.instance}/*"]
          },
          {
            # SOLO los secretos de esta instancia
            Effect   = "Allow"
            Action   = ["secretsmanager:GetSecretValue"]
            Resource = [var.db_secret_arn]
          },
          {
            Effect   = "Allow"
            Action   = ["kms:Decrypt"]
            Resource = [var.secrets_kms_key_arn]
            Condition = {
              StringEquals = { "kms:ViaService" = "secretsmanager.${global.region}.amazonaws.com" }
            }
          }
        ]
      })
    }

    # ---------- ROL DE TAREA — lo que la propia aplicación puede hacer ----------
    resource "aws_iam_role" "task" {
      name                 = "${global.instance}-${global.app.name}-task"
      assume_role_policy   = data.aws_iam_policy_document.ecs_assume.json
      permissions_boundary = var.task_role_boundary_arn
      tags                 = global.tags
    }

    resource "aws_iam_role_policy" "task" {
      role = aws_iam_role.task.id
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Effect   = "Allow"
            Action   = ["s3:GetObject", "s3:PutObject"]
            Resource = ["arn:aws:s3:::${global.instance}-${global.app.name}-data/*"]
          }
        ]
      })
    }
  }
}
```

Definición de tarea — nótese que los secretos van en `secrets`, nunca en `environment`:

```hcl
generate_hcl "_task_definition.tf" {
  condition = global.capability == "app" && global.platform.runtime == "fargate"

  content {
    resource "aws_ecs_task_definition" "this" {
      family                   = "${global.instance}-${global.app.name}"
      requires_compatibilities = ["FARGATE"]
      network_mode             = "awsvpc"
      cpu                      = global.app.cpu
      memory                   = global.app.memory

      execution_role_arn = aws_iam_role.execution.arn
      task_role_arn      = aws_iam_role.task.arn

      runtime_platform {
        operating_system_family = "LINUX"
        cpu_architecture        = global.app.architecture   # ARM64 cuando sea posible: más barato, menor superficie de ataque
      }

      container_definitions = jsonencode([{
        name      = global.app.name
        image     = "${var.ecr_registry_url}/${global.app.name}:${global.app.image_tag}"
        essential = true

        readonlyRootFilesystem = true
        user                   = "10001:10001"           # nunca root
        linuxParameters = {
          capabilities = { drop = ["ALL"] }
          initProcessEnabled = true
        }

        portMappings = [{ containerPort = global.app.port, protocol = "tcp" }]

        # Solo configuración no sensible
        environment = [
          { name = "DB_HOST", value = var.db_endpoint },
          { name = "ENV",     value = global.env }
        ]

        # Valores sensibles por referencia — resueltos por el rol de ejecución al arrancar.
        # Nunca aparecen en la salida de DescribeTaskDefinition.
        secrets = [
          { name = "DB_PASSWORD", valueFrom = "${var.db_secret_arn}:password::" }
        ]

        logConfiguration = {
          logDriver = "awslogs"
          options = {
            "awslogs-group"         = "${var.log_group_prefix}/${global.instance}"
            "awslogs-region"        = global.region
            "awslogs-stream-prefix" = global.app.name
          }
        }
      }])
    }

    resource "aws_ecs_service" "this" {
      name            = "${global.instance}-${global.app.name}"
      cluster         = var.cluster_arn
      task_definition = aws_ecs_task_definition.this.arn
      desired_count   = global.app.desired_count
      launch_type     = "FARGATE"
      platform_version = "LATEST"

      enable_execute_command = global.app.ecs_exec_enabled   # false por defecto

      network_configuration {
        subnets          = var.task_subnet_ids               # de ecs-subnets (§8.2), nunca de network
        security_groups  = [aws_security_group.service.id]
        assign_public_ip = false                             # siempre false en subredes privadas
      }

      load_balancer {
        target_group_arn = aws_lb_target_group.this.arn
        container_name   = global.app.name
        container_port   = global.app.port
      }
    }
  }
}
```

Los security groups se referencian entre sí, nunca por CIDR:

```hcl
resource "aws_security_group" "service" {
  name   = "${global.instance}-${global.app.name}-svc"
  vpc_id = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "from_alb" {
  security_group_id            = aws_security_group.service.id
  referenced_security_group_id = var.alb_security_group_id   # solo el ALB compartido
  from_port                    = global.app.port
  to_port                      = global.app.port
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "to_db" {
  security_group_id            = aws_security_group.service.id
  referenced_security_group_id = var.db_security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
```

### 8.5 Checklist de IAM y seguridad de Fargate

| Control | Requisito | Justificación |
|---|---|---|
| Separación en dos roles | Rol de ejecución y rol de tarea siempre distintos | El rol de tarea es alcanzable desde dentro del contenedor; el de ejecución no |
| Rol de ejecución por instancia | En clusters compartidos, nunca compartirlo | Un rol de ejecución compartido puede leer los secretos de cada tenant |
| Límite de permisos | Adjuntado a ambos roles, publicado por la plataforma | Evita la escalada de privilegios desde el propio stack de un tenant |
| Confused deputy | `aws:SourceArn` + `aws:SourceAccount` en la trust policy | Bloquea la asunción de rol entre cuentas vía el principal de servicio ECS |
| Secretos | Bloque `secrets`, nunca `environment` | Los valores de `environment` son visibles en `DescribeTaskDefinition` para cualquiera con acceso de lectura |
| Sistema de ficheros raíz | `readonlyRootFilesystem = true` | Bloquea la mayoría de las herramientas post-explotación |
| Usuario del contenedor | UID no-root, `capabilities.drop = ["ALL"]` | Fargate aísla las tareas, pero la defensa en profundidad sigue aplicando |
| IP pública | `assign_public_ip = false` | Las tareas en subredes privadas salen solo vía NAT o endpoints |
| ECS Exec | Deshabilitado a menos que esté justificado; cuando esté habilitado, requiere logging a CloudWatch/S3 y `ssmmessages` en el rol de **tarea** | Exec es una shell interactiva hacia producción |
| ECR | Escaneo al push, tags inmutables, política de ciclo de vida | Los tags inmutables evitan la sustitución silenciosa de imágenes |
| Log groups | Prefijo por instancia, retención fijada, cifrado con KMS | Evita la lectura de logs entre tenants |
| Arquitectura | ARM64 donde la carga de trabajo lo permita | Menor coste y una cadena de suministro de imagen distinta |

Barandillas complementarias por encima del pipeline (§11.7): SCPs denegando `iam:CreateUser`, denegando el borrado de límites de permisos, y confinando regiones.

### 8.6 Compartido y dedicado para ECS Fargate

| Dimensión | Cluster demo compartido | Producción dedicada |
|---|---|---|
| Límite de aislamiento | Rol de tarea + rol de ejecución + security group | Cuenta |
| Aislamiento de cómputo | **Aislamiento a nivel de VM por tarea** — más fuerte que los nodos EKS compartidos | Igual |
| Network | VPC del entorno, subredes de tareas creadas por `ecs-subnets`, SG por servicio | VPC dedicada |
| Ingress | ALB compartido, listener rule por tenant basada en host | ALB dedicado |
| Secretos | Secreto por tenant + rol de ejecución por tenant | Por cuenta |
| Control de escalada | Límite de permisos publicado por la plataforma | Límite + SCP |
| Coste en reposo | `desired_count = 0` fuera del horario de demos | Siempre encendido |

El modelo general y la seguridad del destroy están en §12; esta tabla solo registra lo específico de Fargate.

El argumento de aislamiento merece decirse claramente: **Fargate da a cada tarea su propia micro-VM.** Un cluster Fargate compartido no tiene la exposición de kernel compartido de un node pool EKS compartido, lo que lo convierte en el valor por defecto más fuerte para entornos demo multi-tenant donde el código del tenant no es totalmente confiable.

Listener rules por tenant en el ALB compartido:

```hcl
resource "aws_lb_listener_rule" "this" {
  listener_arn = var.alb_https_listener_arn
  priority     = global.app.listener_priority        # desde globals — debe ser única por tenant

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }

  condition {
    host_header {
      values = ["${global.instance}.${global.dns_suffix}"]
    }
  }
}
```

```hcl
assert {
  assertion = global.platform.model != "shared" || tm_can(global.app.listener_priority)
  message   = "Los tenants de cluster compartido deben declarar una listener priority única de ALB"
}
```

Las prioridades de listener rule son un espacio de nombres compartido y finito. Asígnalas desde un bloque por tenant en el `config.tm.hcl` de la plataforma (`alpha = 100–199`, `beta = 200–299`) para que dos pull requests no puedan colisionar.

### 8.7 Advertencias de Fargate

| Advertencia | Impacto | Mitigación |
|---|---|---|
| Rol de ejecución compartido | Exposición de secretos entre tenants | Rol de ejecución por instancia (§8.4) |
| Secretos en `environment` | Texto plano en `DescribeTaskDefinition` y en la consola | Usa `secrets`; añade una política personalizada de Checkov que falle ante nombres de secreto probables en `environment` |
| Colisiones de listener priority | El segundo apply falla, o peor, enruta el tráfico mal | Asigna rangos por tenant en globals; refuerza con una aserción |
| Sin endpoints de VPC | La extracción de imagen y la obtención de secretos atraviesan NAT | Lista de endpoints en globals, con aserción para entornos no-demo |
| Las revisiones de la definición de tarea se acumulan | Difícil auditar qué revisión está viva | Etiqueta las revisiones; poda según un calendario; registra la revisión viva en la CMDB |
| `ecr:GetAuthorizationToken` no puede restringirse por recurso | Parece una concesión demasiado amplia en la revisión | Documéntalo; solo concede un token, y las acciones de extracción están restringidas |
| ECS Exec dejado habilitado | Shell interactiva hacia producción | `false` por defecto en globals; aserción bloqueándolo para `prod` |
| Fargate no tiene daemonsets | Los agentes basados en sidecar deben añadirse por definición de tarea | Genera el sidecar desde la capa de plataforma para que cada tenant lo reciba uniformemente |

### 8.8 Variante — perfiles EKS Fargate

Los perfiles EKS Fargate son una *opción de cómputo para la guía EKS*, no una plataforma separada. Si los adoptas, los cambios a §6 son:

- El stack `eks` produce adicionalmente `fargate_profile_arn` y el **ARN del rol de ejecución de pods de Fargate**.
- Ese rol de ejecución de pods reemplaza al rol de nodo para los namespaces seleccionados; concédele solo extracción de ECR y logs de CloudWatch.
- Los perfiles de Fargate seleccionan por **namespace y labels**, lo que mapea directamente a `global.platform.namespace` — un perfil por namespace de tenant en un cluster compartido da aislamiento de cómputo por tenant sin un cluster separado.
- IRSA no cambia: `oidc_provider_arn` y `oidc_provider_url` siguen viniendo del stack de cluster.
- Advertencias: sin DaemonSets, sin contenedores privilegiados, sin host networking, y una demanda de IP a escala `/16` en las subredes de pods. Esas son del stack `eks-subnets` (§6.2), así que se dimensionan en las reclamaciones del arquetipo `eks`, no en `network`.

---

## 9. Guía E — Plataforma AKS y su cadena de dependencias

AKS completa la paridad de tres clouds. Estructuralmente refleja la guía EKS; las diferencias son el modelo de identidad (Workload Identity vía Entra ID en lugar de IRSA), la decisión del modo de networking, y el adjunto de borde.

### 9.1 Grafo de dependencias

```mermaid
graph LR
    NET["<b>network</b><br/>azure-ENV-network"] --> SUB["<b>aks-subnets</b><br/>azure-ENV-aks-subnets"] --> AKS["<b>aks</b><br/>azure-ENV-aks"]
    NET --> AKS
    NET --> DATA["<b>data</b><br/>azure-ENV-INST-data"]
    AKS --> SVC["<b>services</b><br/>azure-ENV-services"]
    SVC --> APP["<b>app</b><br/>azure-ENV-INST-app"]
    DATA --> APP
```

| # | Stack | Produce | Consume |
|---|---|---|---|
| 1 | `azure-ENV-network` | VNet **sin subredes inline**, NAT gateway, zonas DNS privadas, subred de endpoint privado | — |
| 2a | `azure-ENV-aks-subnets` | Subred de nodos (y de pods con Azure CNI tradicional) — los claims del runtime (AM §9.5) — con su NSG y su asociación al NAT gateway | network |
| 2b | `azure-ENV-aks` | Cluster, node pools, URL del emisor OIDC, identidad de kubelet | network, aks-subnets |
| 3 | `azure-ENV-services` | AGFC o Envoy Gateway, integración de certificados, monitorización | aks |
| 4a | `azure-ENV-INST-data` | Flexible Server, secretos de Key Vault, endpoint privado | network |
| 4b | `azure-ENV-INST-app` | Workload, identidad gestionada asignada por el usuario, credencial federada | aks, services, data |

### 9.2 Modo de networking — decide una vez, en globals

| Modo | Direccionamiento de pods | Cuándo |
|---|---|---|
| **Azure CNI Overlay** | Pods en un CIDR overlay privado, no en IPs de VNet | **Elección por defecto.** Elimina por completo la presión de IPs de VNet |
| Azure CNI (tradicional) | Cada pod recibe una IP de VNet | Solo cuando los pods deben ser directamente enrutables desde fuera del cluster |
| Azure CNI potenciado por Cilium | Overlay más plano de datos eBPF | Cuando quieres NetworkPolicy con rendimiento eBPF |

Sea cual sea el modo, las subredes del runtime son del stack `aks-subnets` del propio arquetipo `aks`, como en GKE (§5.2) y EKS (§6.2): la de nodos siempre, y la de pods solo con Azure CNI tradicional. El CIDR de pods de Overlay no es una subred de la VNet, así que no se crea nada para él.

El modo overlay cambia significativamente el plan de direcciones: la mitad de pods de la `/17` pasa a ser reserva en lugar de consumida, porque las direcciones de pod provienen de un espacio overlay separado y no enrutable que puede reutilizarse entre entornos. Esa es una ventaja genuina sobre EKS con VPC CNI, y debería registrarse como un trait para que la planificación de capacidad la refleje.

### 9.3 Identidad — Workload Identity con Entra ID

```hcl
# imports/contracts/contract_cluster_aks.tm.hcl
input "vnet_id" {
  backend = "tofu"  from_stack_id = global.platform.network_stack_id
  value = outputs.vnet_id.value
  mock  = "/subscriptions/mock/resourceGroups/mock/providers/Microsoft.Network/virtualNetworks/mock"
}

## ---- consume del stack de subred propio (azure-demos-aks-subnets) ----
input "node_subnet_id" {
  backend = "tofu"  from_stack_id = global.platform.cluster_subnet_stack_id
  value = outputs.node_subnet_id.value
  mock  = "/subscriptions/mock/.../subnets/mock-nodes"
}

output "cluster_name"     { backend = "tofu"  value = azurerm_kubernetes_cluster.this.name }
output "cluster_endpoint" { backend = "tofu"  value = azurerm_kubernetes_cluster.this.kube_config.0.host }
output "cluster_ca" {
  backend = "tofu"  value = azurerm_kubernetes_cluster.this.kube_config.0.cluster_ca_certificate
  sensitive = true
}
# El único hecho del que depende cada workload identity en cada instancia:
output "oidc_issuer_url"  { backend = "tofu"  value = azurerm_kubernetes_cluster.this.oidc_issuer_url }
output "kubelet_identity_object_id" {
  backend = "tofu"  value = azurerm_kubernetes_cluster.this.kubelet_identity.0.object_id
}
```

El stack de aplicación crea una identidad gestionada asignada por el usuario y una credencial federada restringida a exactamente un namespace y una service account:

```hcl
resource "azurerm_user_assigned_identity" "app" {
  name                = "${global.instance}-${global.app.name}"
  resource_group_name = global.resource_group
  location            = global.region
}

resource "azurerm_federated_identity_credential" "app" {
  name                = "${global.instance}-${global.app.name}-fic"
  resource_group_name = global.resource_group
  parent_id           = azurerm_user_assigned_identity.app.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.oidc_issuer_url
  # Restringido por namespace, nunca un comodín
  subject             = "system:serviceaccount:${global.platform.namespace}:${global.app.name}"
}
```

El campo `subject` es el análogo exacto de la condition `sub` de EKS y de la cadena de miembro de Workload Identity de GKE. Los tres están restringidos por namespace, y en los tres un comodín concede silenciosamente la identidad a cada pod del cluster.

### 9.4 Línea base de IAM y seguridad de AKS

| Control | Requisito | Justificación |
|---|---|---|
| Identidad del cluster | Identidad gestionada asignada por el usuario, no asignada por el sistema | Sobrevive a la recreación del cluster; concedible por adelantado |
| Workload identity | Habilitada con emisor OIDC; una UAMI por workload | La identidad de kubelet nunca debe ser la identidad de workload |
| Identidad de kubelet | Restringida solo a extracción de ACR | Es alcanzable desde el nodo |
| Acceso al cluster | **Integración de Entra ID con Azure RBAC**, cuentas locales deshabilitadas | `local_account_disabled = true` elimina el kubeconfig admin estático |
| Acceso admin | Grupo de Entra, nunca usuarios individuales | Auditable y revocable centralmente |
| Servidor API | Cluster privado, o rangos de IP autorizados | |
| Secretos | Key Vault vía el driver CSI de Secrets Store, usando workload identity | Nunca Kubernetes Secrets como fuente de verdad |
| Node pools | Discos de SO efímeros, `enable_host_encryption`, Azure Linux o Ubuntu con parcheado automático | |
| Registro | ACR con content trust y escaneo de vulnerabilidades; extracción de ACR vía identidad gestionada | |
| Política | Add-on de Azure Policy reforzando los Pod Security Standards | Equivalente al PSS `restricted` en otros lugares |
| Permisos del deployer | Rol personalizado restringido, no Owner ni Contributor a nivel de suscripción | |

Las asignaciones de Azure Policy a nivel de grupo de gestión son el equivalente de las Organisation Policies de GCP y las SCP de AWS: denegar IPs públicas en node pools, requerir endpoints privados en servicios de datos PaaS, confinar regiones, y denegar la creación de clusters con cuentas locales habilitadas.

### 9.5 Advertencias de AKS

| Advertencia | Impacto | Mitigación |
|---|---|---|
| `kube_config` es sensible y queda en el estado | El estado se convierte en un almacén de credenciales | Usa `local_account_disabled = true` y autenticación Entra; nunca compartas `kube_config` como output |
| Grupo de recursos del nodo | AKS crea un segundo grupo de recursos, gestionado por AKS | No gestiones su contenido en Terraform; el reconciliador del cluster luchará contra ti |
| Delegación de subred para AGFC | La subred de App Gateway for Containers necesita delegación a `Microsoft.ServiceNetworking/TrafficController` | Resérvala en el layout de direcciones del entorno |
| Zonas DNS privadas para endpoints privados | Cada servicio PaaS necesita su propia zona enlazada a la VNet | Poséelas en el stack de network; se comparten entre instancias |
| Overlay vs CNI es inmutable | Cambiar el modo de networking requiere recrear el cluster | Decídelo en globals antes del primer apply |
| Bloques `subnet` inline en la VNet | Si el stack de red declara subredes inline en `azurerm_virtual_network`, cada apply de la red borra las subredes que crearon otros stacks, `aks-subnets` incluido | La VNet no tiene bloques `subnet` inline; cada subred es un `azurerm_subnet` aparte, del que la reclama. Un `assert` en el generador de red lo impone |
| Funcionalidades preview | Varias capacidades de AKS se lanzan detrás de flags `--enable-preview` | Fija el provider y registra la dependencia preview en el manifiesto del arquetipo |

---

## 10. Adjunto de borde entre clouds

Este es el elemento menos portable de la arquitectura, y el que decide si un entorno se gana el trait `iac-owned-edge` en el modelo de arquetipos. El patrón es el mismo en todas partes — Envoy Gateway (o AGFC) dentro del cluster, un load balancer de cloud delante, ningún LB externo gestionado por la cloud por Service — pero el mecanismo de adjunto difiere estructuralmente.

### 10.1 Comparación

| | GCP | AWS | Azure |
|---|---|---|---|
| Mecanismo | NEG independiente | CRD `TargetGroupBinding` | AGFC en modo **BYO** |
| Creado por | Controlador NEG de GKE | **Terraform** crea el target group | **Terraform** crea ALB + Frontend + Association |
| ¿En el estado de Terraform? | **No** | **Sí** | **Sí** |
| Disparador | Anotación en el Service | Recurso personalizado `TargetGroupBinding` | Anotación en `Gateway` / `Ingress` |
| Ligado por | Nombre del NEG | ARN o nombre del target group | ID del recurso Frontend |
| Zonalidad | Un NEG por zona | Target group único | Frontend único |
| Trait `iac-owned-edge` | No | Sí | Sí |

### 10.2 GCP — NEG independiente

Terraform posee el backend service, el health check, el URL map, el target proxy, la forwarding rule, el certificado y las reglas de firewall. **No** posee el NEG.

- Referencia el NEG por su URL, construida a partir del nombre determinista (`projects/<proyecto>/zones/<zona>/networkEndpointGroups/<neg_name>`), nunca como un `resource` — Terraform y el controlador lucharían en cada plan — y tampoco como fuente `data`: una fuente `data` se lee al planificar y hace fallar la preview siempre que el Gateway aún no exista, y `--mock-on-fail` cubre solo bloques `input`, nunca fuentes `data`.
- Nómbralo explícitamente en la anotación `EnvoyProxy` para que la búsqueda sea determinista.
- Los NEG son **zonales**. Refuerza `minReplicas ≥ número de zonas` más topology spread con una aserción, o una zona sin pods de Envoy produce un NEG ausente y un apply fallido.
- Arranque en frío: el NEG no existe hasta que los pods de Envoy están Ready. Divide en tres stacks (`aks`/`gke` → `gateway` → `edge`) con `after`. Ningún `input` respalda ese `after` — el nombre del NEG es un global — así que la regla de R2 no lo ve; lo ve una regla G1 con nombre (§13.3).
- **El tramo hacia el backend es HTTP.** El TLS público termina en el balanceador con el certificado de la capa 1 (Certificate Manager en GCP, ACM en AWS, certificados de App Gateway en Azure); el balanceador habla HTTP con Envoy. Un certificado de `cert-manager` en ese tramo haría depender la capa 1 de la capa 3, y el balanceador tampoco lo valida. La única arista hacia arriba que conserva el borde es el nombre del NEG (AM §3). Si algún día se exige autenticar el tramo, la raíz de confianza tiene que ser una CA de plataforma en la capa 1 (propuesta `envoy-gateway-qa`, DG14).

### 10.3 AWS — TargetGroupBinding

El más fuerte de los tres para propiedad IaC completa. `TargetGroupBinding` expone pods a través de un target group de ALB o NLB aprovisionado enteramente fuera de Kubernetes, mientras el controlador gestiona el registro de targets desde el Service de Kubernetes.

Dos precauciones:

- **Nunca uses `aws_lb_target_group_attachment` junto a él.** El controlador registra y desregistra targets dinámicamente conforme los pods aparecen y desaparecen; que Terraform gestione los mismos targets garantiza una lucha en cada plan.
- **Restringe la creación con RBAC en clusters compartidos.** El CRD puede referenciar cualquier target group de la cuenta donde reside el cluster, así que un tenant podría importar el target group de otra carga de trabajo a su namespace y redirigir el tráfico. En esta arquitectura, solo el arquetipo `gateway` crea recursos `TargetGroupBinding`, y RBAC deniega `create` y `update` sobre el CRD a los namespaces de aplicación. Restringe la política IAM del controlador a los target groups específicos en lugar de `Resource: "*"`.

### 10.4 Azure — AGFC bring-your-own

El modo BYO pone el recurso Application Gateway for Containers, su Association y sus hijos Frontend en Terraform. La contrapartida es un ciclo de vida acoplado: cada objeto `Gateway` o `Ingress` requiere un Frontend aprovisionado de antemano y referenciado por anotación, y borrado después de eliminar el objeto de Kubernetes.

Con un Gateway por entorno — que el diseño de plataforma compartida ya exige — eso es un Frontend por entorno. Con un Gateway por tenant no escalaría.

Una diferencia arquitectónica que merece decidirse pronto: **AGFC es en sí misma una implementación de Gateway API.** Colocar Envoy Gateway detrás de ella es un doble salto L7 sin ganancia. En Azure, la elección real es AGFC directamente, o Envoy Gateway detrás de un Load Balancer interno estándar. AGFC no expone el `SecurityPolicy` OIDC nativo de Envoy, así que una integración con Keycloak necesita ahí un mecanismo distinto.

### 10.5 Configuración de Envoy Gateway

El Service que lleva la anotación de borde es **generado por el controlador de Envoy Gateway**, no escrito en tu chart. Configúralo mediante `EnvoyProxy`, referenciado desde la `GatewayClass`:

```yaml
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: EnvoyProxy
metadata: { name: edge-proxy, namespace: envoy-gateway-system }
spec:
  provider:
    type: Kubernetes
    kubernetes:
      envoyService:
        type: ClusterIP                      # sin LB de cloud por Service
        annotations:
          # GCP
          cloud.google.com/neg: '{"exposed_ports":{"8080":{"name":"eg-demos-neg"}}}'
      envoyDeployment:
        replicas: 3
        pod:
          topologySpreadConstraints: [ ... ]
```

**Evita el recurso `kubernetes_manifest`** para `GatewayClass`, `EnvoyProxy` y `Gateway`. Requiere que el CRD exista y que el API server sea alcanzable *en el momento del plan*, lo que rompe las previews de PR y `--mock-on-fail`. Empaqueta los recursos personalizados en el propio chart de Helm del arquetipo `gateway` y despliega con `helm_release`, de modo que un plan sea un diff de values en lugar de una llamada a la API.

### 10.6 Por qué esto elimina el problema del fan-in

Gateway API invierte la dirección de la dependencia de enrutamiento. Un `HTTPRoute` vive en el namespace de la aplicación y se adjunta al Gateway con `parentRefs`; el Gateway controla quién puede adjuntarse vía `allowedRoutes`. **El borde ya no necesita conocer a sus tenants.**

Eso elimina tres cosas de la arquitectura: el URL map generado a partir de una lista `global.tenants` (§7.5), el ledger de listener-priority, y el stack de edge-routing que tenía que ejecutarse después de cada instancia. Lo que sigue siendo un claim es el hostname, porque solo un tenant puede poseer `alpha.mfrwzdp.disasterproject.com`.

Usa **un Gateway por entorno** con `allowedRoutes.namespaces.from: Selector`, no uno por tenant — cada `Gateway` genera su propio Deployment de Envoy, Service y NEG, así que los Gateways por tenant reintroducen exactamente el fan-in que pretendían eliminar. Si más adelante necesitas varios (interno y externo, por ejemplo), `mergeGateways` en `EnvoyProxy` permite que compartan una flota de proxies.

### 10.7 El ciclo de arranque de Keycloak

Envoy Gateway provee OIDC nativo mediante `SecurityPolicy`, lo que probablemente elimina la necesidad de autorización externa. Pero hay un ciclo que hay que diseñar explícitamente:

> El Gateway necesita a Keycloak para autenticar, y Keycloak se expone a través del Gateway.

Dos invariantes:

- El propio `HTTPRoute` de Keycloak no lleva **ningún** `SecurityPolicy`.
- El endpoint de descubrimiento OIDC del Gateway se resuelve a través del Service dentro del cluster, no del hostname público.

Sin esto, un entorno en frío no arranca y la causa no es obvia. Decide también el comportamiento ante el fallo del IdP: si Keycloak está caído, el Gateway deja de autenticar todo lo demás. Aceptable en `demos`; en producción requiere Keycloak en alta disponibilidad y una decisión explícita entre fail-open y fail-closed.

### 10.8 Riesgos de borde

| Riesgo | Mitigación |
|---|---|
| NEG ausente en una zona sin pods de Envoy | `minReplicas ≥ zonas`, topology spread, aserción |
| Redirección de tráfico entre tenants por `TargetGroupBinding` | RBAC denegando el CRD a los namespaces de tenant; IAM del controlador restringido |
| Frontend de AGFC huérfano tras borrar el Gateway | Ciclo de vida del Frontend poseído por el mismo stack que el Gateway; destruir en orden inverso |
| Envoy Gateway es un SPOF por entorno | PDB, despliegue surge, `minReplicas ≥ 3` |
| Cadencia de release de Envoy Gateway; APIs alfa en `EnvoyProxy` y `SecurityPolicy` | Fija las versiones del chart y de Gateway API; actualiza primero en un entorno efímero |
| NEG retenido en `tofu destroy` | Orden inverso correcto — el backend service debe borrarse antes que el Service de Kubernetes |
| Doble salto L7 sin justificar | Confirma la necesidad de `SecurityPolicy` OIDC, mTLS o rate limiting por ruta antes de comprometerte |

---

## 11. Identidad, acceso y línea base de seguridad

Todo lo anterior asume una identidad de pipeline que puede leer y escribir recursos de cloud en varias cuentas y proyectos. Esa identidad es el objetivo de mayor valor de todo el sistema: por construcción, posee más privilegio que cualquier workload individual que despliegue. Esta sección especifica cómo se concede, se acota y se audita.

### 11.1 Principios

1. **Ninguna credencial de larga duración en ningún sitio.** Sin claves JSON de service account, sin claves de acceso IAM en secretos de GitHub. Solo federación OIDC.
2. **Separa la identidad de plan de la identidad de apply.** Plan es de solo lectura; apply es de escritura. Un pull request desde un fork nunca debe poder alcanzar un rol de apply.
3. **Identidad separada por entorno.** El rol que despliega `demos` no debe poder tocar `prod`.
4. **Acota el radio de impacto por encima del pipeline.** Las Organisation Policies y las SCP son el control que el pipeline no puede deshabilitar; los límites de permisos son el control que el propio código de un tenant no puede escapar.
5. **Los workloads nunca heredan el privilegio del pipeline.** El rol que crea un servicio Cloud Run y la service account con la que se ejecuta ese servicio son principales distintos con permisos disjuntos.
6. **Los secretos se referencian, nunca se transportan.** Nada sensible cruza la frontera de outputs sharing.

### 11.2 Identidad de pipeline — GitHub Actions hacia Google Cloud

Workload Identity Federation, con el pool y el provider poseídos por un stack de bootstrap que el propio pipeline no gestiona.

```hcl
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "gh-disasterproject-infra"   # uno por repositorio, nunca un nombre genérico: los ids de pool son por proyecto, y un pool borrado retiene su id 30 días
  project                   = var.bootstrap_project_id
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"

  attribute_mapping = {
    "google.subject"         = "assertion.sub"
    "attribute.repository"   = "assertion.repository"
    "attribute.environment"  = "assertion.environment"
    "attribute.ref"          = "assertion.ref"
  }

  # SIN ESTA CONDICIÓN, CUALQUIER REPOSITORIO DE GITHUB EN EL MUNDO PUEDE
  # SUPLANTAR ESTE POOL. No es opcional.
  attribute_condition = "assertion.repository == 'disasterproject/infra' && assertion.repository_owner_id == '123456'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}
```

Dos service accounts por entorno, ligadas a conjuntos de principales *distintos*:

```hcl
# Plan: solo lectura, permitido desde cualquier rama (para que funcionen las PR de ramas feature)
resource "google_service_account_iam_member" "plan" {
  service_account_id = google_service_account.tf_plan_shared_demo.name
  role               = "roles/iam.workloadIdentityUser"
  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/disasterproject/infra"
}

# Apply: escritura, permitido SOLO desde el GitHub Environment protegido
resource "google_service_account_iam_member" "apply" {
  service_account_id = google_service_account.tf_apply_shared_demo.name
  role               = "roles/iam.workloadIdentityUser"
  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/demos"
}
```

**En el proyecto non-prod compartido**, `tf-apply-qa@` y `tf-apply-dev@` son identidades distintas, pero un rol concedido a nivel de proyecto alcanza a todos los entornos del proyecto. Concede a nivel de recurso donde el servicio lo admita (secretos, buckets, claves, cuentas de servicio, instancias de Cloud SQL con condiciones IAM sobre el prefijo del nombre); donde solo existe un rol de proyecto (`roles/container.admin`, `roles/compute.networkAdmin`), acepta que una identidad de apply no productiva puede tocar otro entorno no productivo, y apóyate en los prefijos de estado por entorno, CODEOWNERS, la puerta de entorno y la regla G3 `terraform.own_network`, que mantiene los recursos de red de un entorno en su propia VPC (§13.4). DNS no está en esa lista: la zona pública del entorno vive en el mismo proyecto, así que un `dns.admin` de proyecto alcanzaría los nombres de los demás entornos, y el permiso que crea zonas privadas va condicionado al prefijo de zona (`network-qa` DW8). Esa exposición nunca llega a `prod`, que es otro proyecto.

**Dónde viven las identidades.** Las cuentas de servicio del pipeline (`tf-plan-<env>@`, `tf-apply-<env>@`, `tf-destroy-<env>@`) se crean en el proyecto de la landing zone, no en el del entorno: así una identidad de entorno no puede editar su propia política IAM ni la de otra. El acceso al estado es por prefijo, con una condición IAM sobre el bucket (`resource.name.startsWith("projects/_/buckets/<bucket-de-estado>/objects/<env>/") || api.getAttribute("storage.googleapis.com/objectListPrefix", "").startsWith("<env>/")` — la segunda mitad porque el listado se evalúa contra el bucket, no contra un objeto, y lo mantiene dentro del prefijo), de modo que `tf-plan-qa@` lee el estado de los productores de `qa` y no el de `dev`. Las cuentas de servicio que reciben grants entre proyectos —la SA de nodos de un runtime, por ejemplo— también las crea la landing zone, para que la capa 0 nunca espere a la capa 2 (`landing-zone-qa` §5, §6.3).


**Quién puede conceder roles.** Solo la identidad de apply de la landing zone administra IAM en los proyectos de entorno, y solo **acotada por rol**: `resourcemanager.projectIamAdmin` con `api.getAttribute('iam.googleapis.com/modifiedGrantsByRole', []).hasOnly([...])`, ≤10 roles por binding, generado de la misma lista `global.identities` de la que concede `gcp-lz-identities`. Puede conceder exactamente los roles de la plataforma — nunca `owner`, `editor` ni la propia administración de IAM (`landing-zone-qa` DZ13). Un `folderAdmin` o `projectIamAdmin` sin cota es un camino de escalada.

**Las coordenadas de la federación se commitean** (`ci/federation.env`), no son variables de repositorio: son identificadores, no secretos, y un fichero revisado no puede desviarse como lo hace una variable editada por un administrador (`landing-zone-qa` DZ12).

El claim `attribute.environment` solo está presente cuando el job del workflow declara `environment:`. Ligar la SA de apply a ese atributo significa que **el rol de apply es inalcanzable desde un job sin la puerta de entorno**, lo que hace que el control de required-reviewers de GitHub sea un límite de seguridad real en lugar de una conveniencia de UI.

| Identidad | Roles | Alcance |
|---|---|---|
| `tf-plan-<env>@` | Una lista de lectura enumerada (`compute.viewer`, `compute.networkViewer`, `container.viewer`, `dns.reader`, `iam.serviceAccountViewer`, `iam.roleViewer`, `certificatemanager.viewer`, `cloudkms.viewer`, `secretmanager.viewer`, `cloudsql.viewer`, `monitoring.viewer`, `serviceusage.serviceUsageViewer`), `roles/storage.objectViewer` sobre el prefijo del bucket de estado — **nunca `roles/viewer`**: esta identidad es alcanzable desde cualquier PR, y `roles/viewer` lee la configuración de todos los servicios | Solo lectura; puede leer el estado del productor para outputs sharing; nunca el contenido de un secreto, nunca un descifrador más allá de su propia clave de estado |
| `tf-apply-<env>@` | Conjunto de mínimo privilegio por entorno (`roles/container.admin`, `roles/run.admin`, `roles/compute.networkAdmin`, …) más `roles/storage.objectAdmin` sobre el prefijo de estado | Nunca `roles/owner`, nunca `roles/editor` |
| `tf-apply-<env>@` extras | `roles/iam.serviceAccountUser` sobre cada SA de runtime que deba `actAs` | Restringido por SA, no a nivel de proyecto |
| SAs de runtime (`run-*`, SA de nodo GKE) | Específicas del workload, mínimas | Creadas por el pipeline, nunca asumibles por él más allá de `actAs` |

Políticas de organización que el pipeline no puede anular:

```
constraints/iam.disableServiceAccountKeyCreation      # sin claves exportables, nunca
constraints/iam.allowedPolicyMemberDomains            # sin identidades externas en políticas IAM
constraints/compute.vmExternalIpAccess                # denegar por defecto
constraints/sql.restrictPublicIp                      # Cloud SQL solo con IP privada
constraints/run.allowedIngress                        # bloquea ingress=ALL en toda la flota
constraints/compute.requireShieldedVm                 # nodos GKE
constraints/gcp.resourceLocations                     # residencia de datos
```

### 11.3 Identidad de pipeline — GitHub Actions hacia AWS

```hcl
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [var.github_oidc_thumbprint]
}

data "aws_iam_policy_document" "apply_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # StringEquals sobre el sub completo, fijado al entorno protegido.
    # NUNCA uses StringLike con "repo:disasterproject/infra:*" — eso concede
    # cada rama, cada PR de fork y cada workflow del repositorio.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:disasterproject/infra:environment:${var.environment}"]
    }
  }
}

resource "aws_iam_role" "tf_apply" {
  name                 = "tf-apply-${var.environment}"
  assume_role_policy   = data.aws_iam_policy_document.apply_trust.json
  permissions_boundary = aws_iam_policy.pipeline_boundary.arn
  max_session_duration = 3600
}
```

| Control | Ajuste | Por qué |
|---|---|---|
| Condition `sub` | `StringEquals` sobre el `repo:ORG/REPO:environment:ENV` exacto | `StringLike` con un comodín es la mala configuración OIDC de AWS más común |
| Condition `aud` | Siempre presente | Sin ella, la trust policy acepta tokens emitidos para otras audiencias |
| Límite de permisos sobre el rol del pipeline | Deniega `iam:DeleteRolePermissionsBoundary`, `organizations:*`, `iam:CreateUser` | El pipeline crea roles IAM; no debe poder crear unos más poderosos que él mismo |
| `max_session_duration` | 1 hora | Limita la ventana de un token de sesión filtrado |
| Nombre de sesión | Fijado al ID de ejecución del workflow | Cada evento de CloudTrail traza de vuelta a una ejecución de pipeline y un commit específicos |
| Rol de plan | Rol separado, `ReadOnlyAccess` + lectura de estado | Alcanzable sin la puerta de entorno |

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ vars.AWS_APPLY_ROLE }}
    role-session-name: gha-${{ github.run_id }}-${{ github.run_attempt }}
    aws-region: eu-west-1
```

Service Control Policies a nivel de organización o de OU:

```
Deny  iam:CreateUser, iam:CreateAccessKey                 # solo federación
Deny  iam:DeleteRolePermissionsBoundary                   # los límites son inmutables para los workloads
Deny  organizations:LeaveOrganization
Deny  * fuera de las regiones aprobadas (con las excepciones habituales de servicios globales)
Deny  ec2:* cuando aws:RequestedRegion no está aprobada
Deny  s3:PutBucketPolicy que conceda Principal "*"
Deny  kms:ScheduleKeyDeletion para las claves de cifrado de estado
```

### 11.4 Matriz de segregación de roles

| Job | Identidad GCP | Identidad AWS | Puerta de entorno de GitHub | Acceso al estado |
|---|---|---|---|---|
| `preview` (PR) | `tf-plan-<env>@` | `tf-plan-<env>` | ninguna | lectura |
| `deploy` (main), landing zone | `tf-apply-lz@` | — | **Environment `landing-zone`**: revisores de plataforma y de seguridad | lectura + escritura, prefijo `lz/` |
| `deploy` (main) | `tf-apply-<env>@` | `tf-apply-<env>` | **Environment `<env>`**: reviewers requeridos | lectura + escritura |
| `drift` (cron) | `tf-plan-<env>@` | `tf-plan-<env>` | ninguna | lectura |
| `destroy` (manual) | `tf-destroy-<env>@` | `tf-destroy-<env>` | **Environment `<env>-destroy`**: reviewers requeridos + grupo aprobador separado | lectura + escritura |

El destroy merece su propia identidad. En una plataforma compartida es la operación que puede tumbar a cada tenant (§12.4), y separarla significa que un camino de deploy comprometido no puede borrar infraestructura.

Las ejecuciones de plan deben usar `-lock=false`, así que la identidad de plan no necesita escritura sobre la tabla de lock ni el objeto de estado. Eso es lo que hace posible un rol de plan genuinamente de solo lectura:

```bash
tofu plan -lock=false -out out.tfplan
```

### 11.5 Permisos del backend de estado y el requisito de outputs sharing

Outputs sharing ejecuta `tofu output -json` **dentro del directorio del productor**, lo que lee el estado del productor. Este es un requisito de permiso que no existe en un repositorio sin sharing, y es el bloqueador más común en la primera semana de adopción.

| El consumidor necesita | GCS | S3 |
|---|---|---|
| Leer el estado del productor | `roles/storage.objectViewer` sobre `gs://BUCKET/PREFIX/producer/*` | `s3:GetObject` sobre `arn:aws:s3:::BUCKET/PREFIX/producer/*` |
| Descifrar el estado del productor | `roles/cloudkms.cryptoKeyDecrypter` si es CMEK | `kms:Decrypt` sobre la clave del bucket |
| Descifrar el cifrado de estado de OpenTofu | La clave de cifrado de estado del productor | Igual |
| Lock | **No requerido** — `tofu output` no bloquea | No requerido |

> **El cifrado de estado del lado del cliente de OpenTofu cambia el cálculo.** Si habilitas el bloque `encryption` (recomendado), el consumidor necesita la *clave de cifrado* del productor, no solo lectura del objeto. Usa una clave por entorno en lugar de una por stack, o el sharing entre stacks se convierte en un problema de gestión de claves. Documenta explícitamente el alcance de la clave.

```hcl
# generado por el mixin de backend
terraform {
  encryption {
    key_provider "gcp_kms" "env" {
      kms_encryption_key = var.state_kms_key      # una clave por ENTORNO
      key_length         = 32
    }
    method "aes_gcm" "default" {
      keys = key_provider.gcp_kms.env
    }
    state    { method = method.aes_gcm.default }
    plan     { method = method.aes_gcm.default }
  }
}
```

Topologías entre cuentas y entre proyectos:

- **Entre proyectos (GCP).** La SA del consumidor necesita la concesión de viewer sobre el bucket del *productor*. Concédela sobre el prefijo del bucket, no sobre el bucket, para que un consumidor de `demos` no pueda leer el estado de `prod`.
- **Entre cuentas (AWS).** O la política del bucket de estado concede al rol consumidor directamente, o el consumidor asume un rol en la cuenta del productor. La primera es más simple; la segunda es auditable por cuenta. Elige una convención y aplícala en todas partes.
- **Nota sobre el radio de impacto.** Cada arista de sharing es también un permiso de lectura de estado. Antes de añadir una, pregúntate si el valor podría ser un global en su lugar (§4.6) — eso cuesta cero permisos.

### 11.6 Lo que nunca cruza la frontera de sharing

Outputs sharing resuelve valores en variables de entorno `TF_VAR_<name>` en el proceso del consumidor. Las variables de entorno se filtran: a volcados de memoria, a entornos de subprocesos, a logs de depuración de CI, a la salida de `ps`.

| Valor | ¿Compartir? | En su lugar |
|---|---|---|
| Contraseña de base de datos | **No** | ID de secreto de Secret Manager / ARN de Secrets Manager |
| Token de autenticación de cloud | **No** | `google_client_config` / `aws_eks_cluster_auth` por consumidor |
| Clave privada TLS | **No** | ID de mapa de Certificate Manager / ARN de certificado ACM |
| Clave API | **No** | La referencia del secreto |
| Material de clave KMS | **No** | ARN o nombre de recurso de la clave |
| Certificado CA del cluster | Sí, marcado `sensitive` | Es un certificado público |
| Endpoint de cluster, ID de VPC, IDs de subred, ARN de proveedor OIDC | Sí | — |

Refuérzalo mecánicamente en lugar de por revisión:

```bash
# scripts/lint-no-secrets-shared.sh
if grep -rEn 'output\s+"[^"]*(password|secret_value|private_key|token|credential)' \
     imports/contracts/ | grep -v '_id"\|_arn"\|_name"'; then
  echo "::error::Un bloque output parece exportar un valor secreto. Comparte una referencia en su lugar."
  exit 1
fi
```

### 11.7 Barandillas por encima del pipeline

Tres capas, cada una reforzando lo que la capa de abajo no puede evadir:

```mermaid
flowchart TD
    ORG["<b>Org Policies (GCP) · SCPs (AWS) · Azure Policy</b><br/>confinamiento de región · sin claves de SA · sin IPs públicas · sin usuarios IAM<br/><i>el pipeline no puede deshabilitar esto</i>"]
    PB["<b>Límites de permisos</b><br/>publicados por el stack de plataforma, adjuntados por aserción<br/><i>un tenant no puede escapar de esto</i>"]
    RP["<b>Políticas de rol de mínimo privilegio</b><br/>por entorno · por fase · por workload<br/><i>revisadas en el pull request</i>"]
    ORG --> PB --> RP
```

Aserción que refuerza la capa intermedia:

```hcl
assert {
  assertion = global.capability != "app" || tm_can(global.iam.permission_boundary)
  message   = "Los stacks de aplicación deben adjuntar el límite de permisos de la plataforma a cada rol IAM"
}

assert {
  assertion = global.env != "prod" || !global.app.ecs_exec_enabled
  message   = "ECS Exec no debe habilitarse en producción"
}
```

### 11.8 Workload identity a través de las guías

| Guía | Mecanismo de workload identity | Hechos compartidos desde la plataforma | Dónde se restringe el binding |
|---|---|---|---|
| **GKE** (§5) | Workload Identity Federation para GKE | `workload_identity_pool` | `serviceAccount:POOL[NAMESPACE/KSA]` — restringido por namespace |
| **EKS** (§6) | IRSA (o EKS Pod Identity) | `oidc_provider_arn`, `oidc_provider_url` | `sub = system:serviceaccount:NAMESPACE:SA` — restringido por namespace + SA |
| **Cloud Run** (§7) | Service account de runtime por servicio | *ninguno* — la identidad la crea el stack de app | El propio servicio es el límite |
| **ECS Fargate** (§8) | Rol de tarea (+ rol de ejecución separado) | `task_role_boundary_arn` | La definición de tarea es el límite |
| **AKS** (§9) | Workload Identity (Entra ID) | `oidc_issuer_url` | `subject = system:serviceaccount:NAMESPACE:SA` — restringido por namespace + SA |

Dos observaciones que dan forma al diseño multi-tenant:

- **GKE y EKS restringen la identidad por namespace**, así que el namespace *es* el límite de tenencia y nunca debe compartirse entre instancias.
- **Cloud Run y Fargate restringen la identidad por servicio o tarea**, un límite más fino que no requiere RBAC a nivel de cluster — una razón por la que ambos son mejores valores por defecto para entornos demo compartidos.

**El pool de GKE es por proyecto, no por cluster.** `PROJECT.svc.id.goog` lo comparten todos los clusters del proyecto, y el principal solo nombra namespace y KSA. En el proyecto non-prod compartido, `sonarqube/eso-sonarqube` de `dev` y el de `qa` serían una sola identidad. Por eso todo KSA que recibe IAM de GCP se llama `<env>-<nombre>` (`qa-eso-sonarqube`); la regla P12 de Gatekeeper rechaza un ServiceAccount con el prefijo de otro entorno, y G1 rechaza un `member` de IAM sin el prefijo del entorno dueño (R54). Los generadores construyen ese nombre de una sola forma, a partir de `global.ksa_prefix = "${global.env}-"`, fijado una vez en el `config.tm.hcl` del entorno; G1 rechaza un nombre de KSA literal en `imports/generators/`, porque un nombre escrito a mano es el que olvida el prefijo. EKS y AKS no tienen esta trampa: su emisor OIDC es por cluster, y la condición de confianza o la credencial federada lo nombra.

Nunca escribas un comodín en una condición de confianza de workload identity. `system:serviceaccount:*:*` o `POOL[*/*]` concede el rol a cada pod del cluster, anulando silenciosamente todo el modelo.

### 11.9 Línea base de seguridad de red

| Control | GKE | EKS | AKS | Cloud Run | ECS Fargate |
|---|---|---|---|---|
| Plano de control privado | Cluster privado + endpoint DNS (solo IAM) o redes autorizadas | Endpoint privado + `public_access_cidrs` | Cluster privado + rangos de IP autorizados | n/a | n/a |
| Egress de workload | Cloud NAT, sin IPs externas; egress de la VPC denegado por defecto, con 443, el rango del entorno y el VIP privado permitidos (`network-qa` DW6) | NAT, `assign_public_ip=false` | NAT gateway, sin IPs públicas de nodo | `PRIVATE_RANGES_ONLY` | `assign_public_ip=false` |
| Acceso privado a servicios | Rango PSA para Cloud SQL | Endpoints de VPC | Endpoints privados + zonas DNS privadas | PSA + Direct VPC egress | Endpoints de VPC |
| Política este-oeste | NetworkPolicy default-deny | NetworkPolicy default-deny | NetworkPolicy (Cilium o Calico) | IAM servicio-a-servicio | Referencias a security groups |
| Filtrado de ingress | Cloud Armor en el LB | AWS WAF en el ALB | Azure WAF en App Gateway / AGFC | Cloud Armor + configuración `ingress` | AWS WAF en el ALB |
| Alcanzabilidad del runner de CI | Runner privado o network autorizada | Runner privado o CIDR público permitido | Runner privado o rango de IP autorizado | API pública | API pública |

La fila del runner de CI es la que muerde durante el despliegue: un plano de control totalmente privado significa que los runners alojados por GitHub no pueden planificar ni aplicar. Decide pronto entre runners autoalojados dentro de la VPC y una autorización de redes para el rango de egress del runner, porque cambia el diseño del pipeline.

### 11.10 Auditoría y trazabilidad

- **Nombrado de sesión.** `gha-<run_id>-<run_attempt>` en AWS, y el claim `google.subject` de WIF en GCP, atan cada llamada a la API de cloud a una ejecución de workflow y por tanto a un commit.
- **Lecturas del estado.** Quién leyó un objeto de estado lo responden Cloud Audit Logs (`DATA_READ` sobre `storage.googleapis.com`) y los data events de CloudTrail, no el access logging del bucket. En GCP, el access logging del bucket exige concederlo a `group:cloud-storage-analytics@google.com`, que `iam.allowedPolicyMemberDomains` prohíbe; sin la concesión el bucket queda configurado para registrar y no escribe nada (`landing-zone-qa` §1.1, DZ11).
- **Etiquetado de recursos.** Cada recurso generado lleva `Archetype`, `Instance`, `Environment`, `ManagedBy=terramate`, `CommitSha`. Esto es lo que permite que la CMDB reconcilie la realidad de la cloud contra el repositorio.
- **Log sinks.** GCP Audit Logs y AWS CloudTrail exportados a un proyecto o cuenta separado, de solo anexado, en el que la identidad del pipeline no puede escribir.
- **Procedencia del código generado.** Como los ficheros generados se commitean, `git blame` en una línea de `_main.tf` apunta al cambio del generador que la produjo — una propiedad que los orquestadores basados en wrappers no tienen.
- **`CODEOWNERS`** sobre `imports/contracts/**` e `imports/generators/**` que requiere revisión del equipo de plataforma: esos dos directorios son donde un único cambio alcanza a cada entorno.

---

## 12. Gestión de entornos: dedicados y compartidos

Aquí es donde la arquitectura se gana su sitio. Las cargas de trabajo de demo, ingeniería de ventas y evaluación necesitan muchas instancias de arquetipo en **una** plataforma; producción necesita **una** instancia de arquetipo por plataforma. La misma definición de arquetipo debe servir a ambas.

### 12.1 Los tres modelos

```mermaid
flowchart TD
    subgraph DED["DEDICADO — 1 plataforma : 1 instancia"]
        D1["network · cluster · services"] --> D2["instancia disasterproject-prod"]
    end
    subgraph SHR["COMPARTIDO — 1 plataforma : N instancias"]
        S1["network · cluster · services"] --> S2["alpha"]
        S1 --> S3["beta"]
        S1 --> S4["gamma"]
    end
    subgraph HYB["HÍBRIDO — network compartida, clusters dedicados"]
        H1["network (compartida)"] --> H2["cluster A + instancia 1"]
        H1 --> H3["cluster B + instancia 2"]
    end
```

| | Dedicado | Compartido | Híbrido |
|---|---|---|---|
| **Límite de aislamiento** | Cuenta/proyecto/suscripción de cloud para `prod`; su propia VPC y cluster dentro del proyecto non-prod compartido en los demás | Namespace de Kubernetes + IAM | Cluster |
| **Radio de impacto de un cambio de plataforma** | 1 instancia | Todas las instancias | Instancias en ese cluster |
| **Coste por instancia** | Alto | Muy bajo | Medio |
| **Tiempo de aprovisionar una instancia** | 20–40 min (plataforma completa) | 2–5 min (solo stacks de app) | 10–20 min |
| **Uso típico** | prod, qa, regulado | demos, formación, PoC | dev, integración |
| **Acoplamiento del ciclo de vida** | Destroy de instancia = destroy de plataforma | El destroy de instancia **no debe** tocar la plataforma | Destroy de cluster = sus instancias |

**La ubicación en proyectos es ortogonal al modelo.** `prod` tiene su propio proyecto de cloud; todo entorno no productivo (`dev`, `qa`, `demos`, `sandbox`, `ephemeral-*`) vive en un proyecto non-prod compartido, cada uno con su propia VPC, cluster, bases de datos y borde, con nombres prefijados por el entorno y la facturación repartida por etiquetas (`CLAUDE.md`). Un `qa` dedicado lo es, por tanto, a nivel de VPC y cluster, no de proyecto. Dos cosas que antes daba gratis el límite del proyecto hay que reconstruirlas dentro del proyecto compartido: **Workload Identity**, cuyo pool es uno por proyecto, así que todo KSA con IAM de GCP lleva el prefijo del entorno (§11.8, R54); y **el IAM del pipeline**, tratado en §11.2.

### 12.2 El mecanismo de binding

Todo lo anterior se expresa mediante un fichero por instancia de arquetipo. Este es todo el truco.

```hcl
# stacks/archetypes/webapp-3tier/instances/disasterproject-prod/binding.tm.hcl
# ---- DEDICADO: esta instancia posee su plataforma ----
globals "platform" {
  cloud             = "aws"
  env               = "prod"
  model             = "dedicated"

  network_stack_id  = "aws-prod-network"
  cluster_stack_id  = "aws-prod-eks"
  services_stack_id = "aws-prod-services"
  data_stack_id     = "aws-prod-disasterproject-data"

  namespace         = "disasterproject"
}

globals {
  instance = "disasterproject"
  tags = {
    Environment = "prod"
    Instance    = "disasterproject"
    Model       = "dedicated"
    Archetype   = "webapp-3tier"
  }
}
```

```hcl
# stacks/archetypes/webapp-3tier/instances/alpha/binding.tm.hcl
# ---- COMPARTIDO: esta instancia alquila espacio en la plataforma demo compartida ----
globals "platform" {
  cloud             = "gcp"
  env               = "demos"
  model             = "shared"

  network_stack_id  = "gcp-demos-network"
  cluster_stack_id  = "gcp-demos-gke"
  services_stack_id = "gcp-demos-services"
  data_stack_id     = "gcp-demos-alpha-data"

  namespace         = "demo-alpha"        # límite de aislamiento
}

globals {
  instance = "alpha"
  ttl_days = 14                            # las demos expiran
  tags = {
    Environment = "demos"
    Instance    = "alpha"
    Model       = "shared"
    Archetype   = "webapp-3tier"
    ExpiresOn   = tm_formatdate("YYYY-MM-DD", tm_timeadd(tm_timestamp(), "336h"))
  }
}
```

Ni una línea de los generadores, contratos o módulos del arquetipo cambia entre los dos. Solo el binding.

### 12.3 Aislamiento en un entorno compartido

Una plataforma compartida es un sistema multi-tenant, y debe construirse como tal. El generador del arquetipo emite esto por instancia siempre que `global.platform.model == "shared"`:

```hcl
# imports/generators/v1/gen_app.tm.hcl (barandillas del modelo compartido)
generate_hcl "_tenancy.tf" {
  condition = global.capability == "app" && global.platform.model == "shared"

  content {
    resource "kubernetes_namespace" "this" {
      metadata {
        name = global.platform.namespace
        labels = {
          "archetype"                          = global.archetype
          "instance"                           = global.instance
          "pod-security.kubernetes.io/enforce" = "restricted"
        }
      }
    }

    resource "kubernetes_resource_quota" "this" {
      metadata {
        name      = "tenant-quota"
        namespace = kubernetes_namespace.this.metadata[0].name
      }
      spec {
        hard = {
          "requests.cpu"    = global.quota.cpu
          "requests.memory" = global.quota.memory
          "pods"            = global.quota.pods
          "count/services.loadbalancers" = global.quota.loadbalancers
        }
      }
    }

    resource "kubernetes_limit_range" "this" {
      metadata {
        name      = "tenant-limits"
        namespace = kubernetes_namespace.this.metadata[0].name
      }
      spec {
        limit {
          type            = "Container"
          default         = { cpu = "500m", memory = "512Mi" }
          default_request = { cpu = "100m", memory = "128Mi" }
        }
      }
    }

    resource "kubernetes_network_policy" "default_deny" {
      metadata {
        name      = "default-deny-ingress"
        namespace = kubernetes_namespace.this.metadata[0].name
      }
      spec {
        pod_selector {}
        policy_types = ["Ingress"]
      }
    }
  }
}
```

Reforzado mediante aserción, para que una instancia compartida no pueda fusionarse sin cuotas:

```hcl
assert {
  assertion = global.platform.model != "shared" || tm_can(global.quota.cpu)
  message   = "Las instancias de modelo compartido deben definir global.quota"
}

assert {
  assertion = global.platform.model != "shared" || global.platform.namespace != "default"
  message   = "Las instancias de modelo compartido no deben desplegarse en el namespace default"
}
```

| Dimensión de aislamiento | Dedicado | Compartido |
|---|---|---|
| Cómputo | Cluster separado | Namespace + ResourceQuota + LimitRange |
| Network | VPC separada | NetworkPolicy default-deny + permisos explícitos |
| Identidad | Cuenta/proyecto de cloud separado | Binding de IRSA / Workload Identity por namespace |
| Datos | Instancia de base de datos separada | Base de datos separada *dentro* de una instancia compartida, secretos separados |
| Ingress | Load balancer dedicado | Controlador compartido, hostname por instancia |
| Atribución de coste | A nivel de cuenta | Labels de namespace + tags de asignación de coste |

### 12.4 Ciclo de vida: el problema del destroy

La operación más peligrosa en un entorno compartido es desmontar una demo. `terramate run -- tofu destroy --reverse` contra el selector de tag equivocado tumbará la plataforma junto con la instancia, matando cada otra demo que haya en ella.

**Barandilla 1 — destroy restringido por tag, nunca por ruta.**

```bash
# CORRECTO: destruye solo los stacks propios de la instancia
terramate run \
  --tags instance/alpha \
  --reverse \
  --enable-sharing \
  -- tofu destroy -auto-approve

# INCORRECTO: --changed o un selector de directorio puede arrastrar stacks de plataforma
```

**Barandilla 2 — los stacks de plataforma llevan un tag protector y la CI se niega a destruirlos fuera de un flujo de break-glass.**

```hcl
stack {
  id   = "gcp-demos-gke"
  tags = ["gcp", "demos", "cluster", "platform", "protected"]
}
```

```bash
# En el job de destroy, antes de ejecutar nada:
# --tags a:b es a Y b. Dos opciones --tags son O: la guarda casaría con todo stack protegido y bloquearía cualquier destroy
if terramate list --tags protected:instance/${INSTANCE} | grep -q .; then
  echo "::error::El selector de destroy coincidió con un stack de plataforma protegido. Abortando."
  exit 1
fi
```

**Barandilla 3 — conteo de referencias antes de destruir la plataforma.** Una plataforma compartida no debe destruirse mientras haya stacks que la consuman. Se cuentan **aristas de la CMDB** (§12.7), no nombres de stack: un patrón de nombre como `^gcp-demos-.*-app$` no casa con nada en un entorno cuyos consumidores se llaman `gcp-qa-policy` o `gcp-qa-kafka-cluster`, el conteo sale 0 y el destroy pasa.

```bash
# Consumidores vivos de un stack: aristas entrantes cuyo origen no está en el propio set de destroy
jq -r --arg p "$STACK" --argjson set "$DESTROY_SET" '
  . as $idx
  | [.edges[] | select(.producer == $p) | .consumer]
  | map(select(. as $c | ($set | index($c)) == null))
  | map(select($idx.stacks[.].observed.lastApply.outcome != "destroyed"))
  | .[]' index.json
```

Cualquier nombre que salga para el destroy, con la lista. Destruir el productor **junto con** todos sus consumidores sí se permite: es destruir el entorno, y lo aprueba el grupo de aprobadores de destroy (§11.4). El conteo solo ve consumidores que son stacks; un servicio al que llegan por HTTP pipelines de fuera del repositorio tiene usuarios que la CMDB no conoce, y por eso se mantiene la aprobación humana. El conteo es tan bueno como las aristas: `archetypectl cmdb check` falla cuando un stack tiene bloques `input` y ningún `consumes` evaluado (R56).

### 12.5 Entornos compartidos efímeros

Las demos son el caso arquetípico de los entornos compartidos, y deberían expirar.

```
environments/
├── demos/binding.yaml                     # de larga duración, siempre encendido
├── ephemeral-conf-2026-q3/binding.yaml    # creado para un evento, destruido después
└── ephemeral-poc-disasterproject/binding.yaml
```

Una plataforma efímera es un binding, como cualquier entorno (§12.8): puede partir del binding de `demos`, pero no se copia nada de sus stacks. Su nombre es libre de prefijo frente a todos los demás, su rango sale del ledger, su proyecto de su jurisdicción, y todos los demás nombres se derivan; lleva `metadata.expiresOn`. Un workflow programado lee los bindings, no los stacks, y abre una PR de destroy por cada uno cuya fecha haya pasado — nunca destruyendo automáticamente, siempre con un humano aprobando.

```bash
today=$(date -u +%F)
for b in environments/ephemeral-*/binding.yaml; do
  [ -e "$b" ] || continue                       # ningún entorno efímero: nada que caducar, dicho explícitamente
  exp=$(yq '.metadata.expiresOn' "$b")
  if [[ "$exp" < "$today" ]]; then echo "$(yq '.metadata.name' "$b") expired $exp"; fi
done
```

### 12.6 Promoción entre entornos

La promoción es un **diff de binding**, no un diff de código. Los mismos generadores y contratos aplican en todas partes; solo difiere el binding, y lo que se deriva de él (§12.8). Los entornos pueden diferir además en composición y región: la tabla compara lo que comparten.

| Global | demos | dev | qa | prod |
|---|---|---|---|---|
| `cluster.min_nodes` | 1 | 2 | 3 | 3 |
| `cluster.max_nodes` | 12 | 20 | 40 | 60 |
| `cluster.release_channel` | `REGULAR` | `REGULAR` | `STABLE` | `STABLE` |
| `cluster.deletion_protection` | `false` | `false` | `true` | `true` |
| `policy.enforce_namespace_quota` | `true` | `false` | `false` | `false` |
| `data.backup_retention_days` | 1 | 7 | 14 | 35 |
| `data.multi_az` | `false` | `false` | `true` | `true` |
| Presupuesto de `managed_db_instances` | 25 | 10 | 10 | por instancia |

Como `generate_hcl` es compartido, un cambio en cómo se construye un cluster llega a todos los entornos a la vez. Ese es precisamente el punto — y también por qué los cambios de generador necesitan la disciplina de versionado `v1`/`v2` de §4.7, para poder desplegarlos entorno por entorno.

### 12.7 Integración con la CMDB

Terramate ofrece un inventario declarativo independiente del estado, que es una mejor fuente de CMDB que analizar los ficheros de estado. Dos comandos lo transportan:

```bash
./ci/stacks-json.sh                                     # inventario lógico, pre-apply
terramate run --changed -- tofu show -json              # inventario físico, post-apply
```

El modelo completo — disposición de ficheros, los tres niveles, los tipos de arista extraídos estáticamente de los bloques `input`, y el conteo de referencias que protege a una plataforma compartida del desmontaje de una instancia — está especificado en el documento complementario, `archetype-model.md` §11. No se repite aquí.

En resumen: la mitad **declarada** (stacks, aristas, claims) se genera y se comprueba en la pull request, en `main`; la mitad **observada** (`lastApply`, `resourceCount`, salidas no sensibles, drift) se escribe tras cada apply en la rama `cmdb-observed` con el workflow reutilizable de §14.2; el modelo de lectura es un asset de release privado, `cmdb-latest`. El ejemplo desarrollado para un entorno es la propuesta `cmdb-qa`.

### 12.8 Muchos entornos, muchas regiones

Los entornos no son copias unos de otros: difieren en composición, proveedor por capacidad, versión, tamaño, región y jurisdicción, y comparten generadores, contratos, convenciones y reglas (propuesta `multi-environment`).

| Regla | Qué significa |
|---|---|
| Un entorno es su binding | `environments/<env>/binding.yaml` es el único fichero escrito a mano. Los nombres que no son claims se derivan de `global.env` y `global.region` en `imports/platform/environment.tm.hcl`; los rangos salen del ledger; un entorno solo tiene los stacks de lo que enlaza, y un módulo de plataforma nunca nombra a un consumidor |
| Jurisdicción, después región | `metadata.jurisdiction` elige la carpeta (con su `gcp.resourceLocations`), el proyecto no productivo y el bucket de estado; `metadata.region`, una de las regiones de la jurisdicción, sitúa los recursos del entorno y su key ring. La landing zone enumera las jurisdicciones una vez, en `global.lz.jurisdictions` |
| Compartido, por región | Un registro de imágenes regional por región distinta de los bindings, en el proyecto de la landing zone; promover entre regiones es una copia por digest |
| Nombres | Los nombres de entorno son libres de prefijo; el entorno nunca se extrae del id de un stack; toda comparación de prefijo lleva su separador (`europe-west1` es prefijo de `europe-west10`) |
| Valores por defecto | Ningún default de chart o módulo es el valor de un entorno real: un override que falta debe fallar en el primer entorno, no crear en el segundo los nombres del primero |
| Comprobaciones | G1 `environment.names` y `environment.placement`; G3 `terraform.own_location` y `terraform.own_network` (§13.3, §13.4) |

## 13. Validación de políticas y seguridad

Tres puntos de refuerzo, aplicados en el orden en que capturan un problema tanto antes como sea posible. Ninguno de los tres subsume a los otros.

```mermaid
flowchart LR
    CI["<b>1 · CI</b><br/>conftest + Checkov<br/><i>cada runtime</i>"]
    CP["<b>2 · Plano de control de cloud</b><br/>Org Policy · SCP · Azure Policy<br/><i>cada runtime · no evadible</i>"]
    AD["<b>3 · Admisión de cluster</b><br/>Gatekeeper<br/><i>solo runtimes de Kubernetes</i>"]
    CI -->|"captura en el pull request"| CP
    CP -->|"captura lo que el pipeline se perdió"| AD
    AD -->|"captura lo que se creó fuera del pipeline"| DONE([reforzado])

    style AD fill:#fff4e5
```

> **La paridad de runtimes no es alcanzable, y la brecha debería documentarse en lugar de descubrirse.** Cloud Run y ECS Fargate no tienen capa de admisión de Kubernetes, así que la capability `policy` solo existe donde existe `cluster`. Para los runtimes serverless, el tercer punto se reemplaza por controles del plano de control de la cloud — más gruesos, pero no evadibles desde dentro de un workload.

### 13.1 División del trabajo entre el resolver y OPA

El resolver y OPA no deben implementar las mismas reglas dos veces.

| | Resolver | OPA |
|---|---|---|
| Naturaleza | **Computa** — cierre, asignación, ordenamiento | **Asegura** — invariantes sobre lo computado |
| Estado | Escribe ledgers | Sin estado, sin efectos secundarios |
| Entrada | Manifiestos, bindings, ledgers | `resolution.json`, `stacks.json` (`ci/stacks-json.sh`), `.tf` generado, plan JSON |
| Falla en | Pasos 1–17 | Después de la resolución y después de la generación |
| Autoría | Equipo de plataforma, en código | Plataforma **y** seguridad, sin tocar el resolver |

OPA no vuelve a resolver nada. Valida que lo que el resolver y los generadores produjeron es legal. Eso es defensa en profundidad — un bug del resolver no pasa desapercibido — y es donde viven las reglas específicas de la organización sin recompilar nada.

### 13.2 Cuatro puertas

| Puerta | Cuándo | Comando | Bloqueante |
|---|---|---|---|
| **G0 — integridad de la generación** | Cada PR | `terramate generate && git diff --exit-code` | Siempre |
| **G1 — estructura y composición** | Cada PR | `conftest test --all-namespaces --policy policy/ --data registry/registry.json …` | Siempre |
| **G2 — escaneo estático de seguridad** | Cada PR | `checkov -d . --framework terraform` | HIGH/CRITICAL |
| **G3 — escaneo del plan** | Antes del apply | `checkov -f plan.json --framework terraform_plan` + `conftest --namespace terraform.<paquete>` | HIGH/CRITICAL |

G0 existe porque el código generado se commitea. Sin ella, alguien edita a mano un `_main.tf`, el escaneo pasa, y el siguiente `terramate generate` revierte silenciosamente el arreglo.

**Checkov y OPA son complementarios, no alternativas.** Checkov aporta la biblioteca estándar de malas configuraciones de cloud conocidas — cientos de comprobaciones que nadie de tu equipo tiene que escribir. OPA lleva lo que es específico de esta plataforma y no puede expresarse como una comprobación genérica: el invariante `input`↔`after`, las reglas de composición de capabilities, las reglas de categoría demo, los presupuestos de tenant.

### 13.3 G1 — políticas de estructura y composición

Esta puerta **reemplaza** el lint de shell que antes protegía el invariante de ordenamiento. Ese invariante es el caso de uso canónico de Rego, y es el riesgo R2.

```rego
package terramate.stacks

# Cada stack que consume un output debe declarar al productor en 'after'.
deny contains msg if {
    some stack in input.stacks
    some dep in stack.consumes
    not dep.from_stack_id in stack.after_ids
    msg := sprintf(
        "el stack %q consume el output %q de %q pero no lo declara en 'after'",
        [stack.id, dep.output, dep.from_stack_id])
}

# Los IDs de stack siguen la convención de nombres.
deny contains msg if {
    some s in input.stacks
    not regex.match(`^[a-z0-9]+-[a-z0-9-]+-[a-z0-9-]+$`, s.id)
    msg := sprintf("el id de stack %q no sigue <cloud>-<env>-<capability>", [s.id])
}

# Los stacks de aplicación llevan un tag de instance, para que el destroy restringido por tag sea seguro.
deny contains msg if {
    some s in input.stacks
    s.capability == "app"
    count({t | some t in s.tags; startswith(t, "instance/")}) == 0
    msg := sprintf("el stack de aplicación %q no tiene tag instance/", [s.id])
}
```

**La regla de R2 exige al productor mismo en `after`; el orden transitivo no la satisface, a propósito.** Un stack que lee `cluster_endpoint` de `gcp-qa-gke` y se ejecuta `after` `gcp-qa-gke-baseline` — que va después del clúster — está bien ordenado hoy, y falla G1. Outputs sharing resuelve contra el estado que exista, así que "da la casualidad de que va después" solo se sostiene hasta que alguien reordena el stack intermedio. Cada stack lista cada productor del que tiene un `input`, el clúster incluido, aunque la cadena ya lo arrastre.

**Un `after` sin `input` detrás no lo comprueba nadie** (`network-qa` §8.1). Dos remedios: convertir el valor determinista en `input` de todos modos, para que la regla de R2 cubra la arista; o, donde el valor no puede ser una salida, una **regla con nombre**. El modelo tiene exactamente una arista así, la ascendente del borde a los proxies del gateway (§10.2), y tiene su propia regla, probada con fixtures antes de que exista ninguno de los dos stacks:

```rego
package terramate.order

import rego.v1

# La arista ascendente (AM §3): <cloud>-<env>-edge lee el NEG por su nombre determinista, un global,
# así que ningún `input` respalda su `after` y la regla de R2 de arriba no lo ve.
# El entorno nunca se extrae del id (los nombres pueden llevar "-"): el borde y los proxies
# de un mismo entorno comparten todo lo que precede a su sufijo.
deny contains msg if {
    some edge in input.stacks
    endswith(edge.id, "-edge")
    some proxy in input.stacks
    endswith(proxy.id, "-gateway-proxy")
    trim_suffix(proxy.id, "-gateway-proxy") == trim_suffix(edge.id, "-edge")
    not proxy.id in edge.after_ids
    msg := sprintf("%q referencia el NEG de %q pero no se ejecuta después (arista ascendente, AM §3)", [edge.id, proxy.id])
}
```

Los fixtures emparejan dos entornos en los que un nombre es prefijo del otro, que la forma anterior de la regla (`split(id, "-")[1]`) resolvía mal en los dos sentidos:

```rego
package terramate.order_test

import rego.v1
import data.terramate.order

stack(id, after) := {"id": id, "after_ids": after}

# Dos entornos, uno con "-" en el nombre y el otro prefijo de él.
wired := [
    stack("gcp-sandbox-gateway-proxy", []),
    stack("gcp-sandbox-edge", ["gcp-sandbox-gateway-proxy"]),
    stack("gcp-sandbox-eu-gateway-proxy", []),
    stack("gcp-sandbox-eu-edge", ["gcp-sandbox-eu-gateway-proxy"]),
]

test_two_environments_pass if count(order.deny) == 0 with input as {"stacks": wired}

test_missing_after_fails if {
    count(order.deny) == 1 with input as {"stacks": [
        stack("gcp-sandbox-eu-gateway-proxy", []),
        stack("gcp-sandbox-eu-edge", []),
    ]}
}

test_cross_environment_after_fails if {
    count(order.deny) == 1 with input as {"stacks": [
        stack("gcp-qa-gateway-proxy", []),
        stack("gcp-x-gateway-proxy", []),
        stack("gcp-x-edge", ["gcp-qa-gateway-proxy"]),
    ]}
}
```

Tres reglas más de G1 vienen de llevar muchos entornos (`multi-environment` DX3, DX5): `environment.names` (ningún `<nombre>-` de un entorno es prefijo del de otro), `environment.placement` (la jurisdicción existe, la región es una de las suyas, el proyecto es el de la jurisdicción) y una guarda que falla con un `from_stack_id = "<cloud>-` literal en cualquier parte de `imports/`.

```rego
package terramate.contracts

secret_fragments := {"password", "private_key", "token", "credential", "secret_value"}
reference_suffixes := {"_id", "_arn", "_name", "_uri"}

# Un bloque output nunca debe exportar un valor secreto — solo una referencia.
deny contains msg if {
    some s in input.stacks
    some o in s.produces
    some frag in secret_fragments
    contains(o, frag)
    every suffix in reference_suffixes { not endswith(o, suffix) }
    msg := sprintf("el stack %q exporta %q — comparte una referencia, no un valor", [s.id, o])
}

# Cada salida consumida existe en el produces de su productor: R6 detectado en la PR, nombrando al consumidor.
deny contains msg if {
    some s in input.stacks
    some dep in s.consumes
    some p in input.stacks
    p.id == dep.from_stack_id
    not dep.output in p.produces
    msg := sprintf("el stack %q consume %q de %q, que no la produce", [s.id, dep.output, dep.from_stack_id])
}

# Un productor que no está en el inventario: una errata en from_stack_id, o un stack eliminado bajo sus consumidores.
deny contains msg if {
    some s in input.stacks
    some dep in s.consumes
    not dep.from_stack_id in {p.id | some p in input.stacks}
    msg := sprintf("el stack %q consume de %q, que no está en el inventario", [s.id, dep.from_stack_id])
}
```

**Los mocks se comprueban por su forma, no se dan por buenos.** G0 no ve un mock de tipo incorrecto — no cambia ningún fichero generado —, así que el enriquecedor registra también el `mock` de cada `input` en `consumes[]`, y una regla comprueba las formas de las que avisan las guías. Un identificador de proveedor conserva su formato (`vpc-mock…`, `projects/mock-project/…`, un ARN que acaba en `MOCK`), así que la regla pide la palabra `mock` en cualquier posición en lugar de un prefijo `mock-`; las excepciones son una lista con nombre, visible en la revisión:

```rego
package terramate.mocks

import rego.v1

# Valores cuya forma el consumidor valida literalmente (una versión de API): con nombre, nunca en silencio.
exempt := {"template_api_version"}

mocks contains [s.id, dep.output, m] if {
    some s in input.stacks
    some dep in s.consumes
    not dep.output in exempt
    some m in as_list(dep.mock)
}

as_list(x) := x if is_array(x)
as_list(x) := [x] if is_string(x)

# Un mock dice que lo es, para que un valor mockeado que llega a un log sea reconocible.
deny contains msg if {
    some [id, output, m] in mocks
    not endswith(output, "_ca")
    not contains(lower(m), "mock")
    msg := sprintf("stack %q: el mock de %q (%q) no dice que es un mock", [id, output, m])
}

# Un mock *_ca es base64 que se decodifica a un valor mock: el consumidor le aplica base64decode().
deny contains msg if {
    some [id, output, m] in mocks
    endswith(output, "_ca")
    not contains(lower(decoded(m)), "mock")
    msg := sprintf("stack %q: el mock de %q no es base64 de un valor mock", [id, output])
}

decoded(m) := base64.decode(m) if base64.is_valid(m)
decoded(m) := "" if not base64.is_valid(m)

# Un endpoint de GKE no lleva esquema (uno de EKS sí): un mock con :// esconde el error de copiar y pegar.
deny contains msg if {
    some [id, output, m] in mocks
    startswith(id, "gcp-")
    endswith(output, "_endpoint")
    contains(m, "://")
    msg := sprintf("stack %q: el mock del endpoint GKE de %q lleva esquema", [id, output])
}
```

Las dos reglas de contrato se ejecutan sobre la mitad declarada de la CMDB de la pull request (`index.json`), así que el inventario es el mismo que lee la guarda de destroy. El colector que escribe la mitad observada solo publica salidas sin `sensitive = true`; la regla de nombres de secreto de arriba es la que impide que un valor secreto llegue a ser una salida.

**Los nombres públicos nunca llevan el nombre del entorno** (propuesta `edge-qa`, DL10). Todo lo visible sin credenciales usa el `network.public_id` aleatorio del entorno. La regla se comprueba dos veces, porque los nombres viven en dos sitios: G1 comprueba el binding, donde se declaran el identificador y el sufijo público; G3 comprueba el plan, donde aparecen por fin los nombres de bucket, los registros DNS públicos y los dominios de los certificados (§13.4). El realm del proveedor de identidad, que sale en las URLs públicas de OIDC/SAML, es un global y lo guarda un `assert` en su propio arquetipo.

```rego
package environment.public_names

# Palabras que nombran un entorno. Ningún nombre público puede contener una.
env_words := {"prod", "prd", "production", "qa", "dev", "develop", "test", "tst", "uat",
              "stg", "stage", "staging", "pre", "preprod", "demo", "demos", "sandbox", "sbx",
              "ephemeral", "nonprod"}

words := env_words | {input.metadata.name}

# El identificador público es aleatorio; si una tirada contiene por azar una palabra de entorno, se repite.
deny contains msg if {
    input.kind == "EnvironmentBinding"
    some w in words
    contains(input.network.public_id, w)
    msg := sprintf("public_id %q contains %q: generate a new one", [input.network.public_id, w])
}

# El sufijo público es <public_id>.<dominio>...
deny contains msg if {
    input.kind == "EnvironmentBinding"
    not startswith(input.network.dns_suffix, sprintf("%s.", [input.network.public_id]))
    msg := sprintf("dns_suffix %q must start with public_id %q", [input.network.dns_suffix, input.network.public_id])
}

# ...y ninguna de sus etiquetas nombra un entorno.
deny contains msg if {
    input.kind == "EnvironmentBinding"
    some label in split(input.network.dns_suffix, ".")
    label in words
    msg := sprintf("dns_suffix %q carries the environment word %q", [input.network.dns_suffix, label])
}
```

```rego
package archetype.composition

# Los arquetipos demo son hojas con una expiración obligatoria.
deny contains msg if {
    input.metadata.kind == "demo"
    count(input.provides) > 0
    msg := "los arquetipos demo no deben publicar capabilities"
}

deny contains msg if {
    input.metadata.kind == "demo"
    not input.metadata.expiresOn
    msg := "los arquetipos demo deben fijar metadata.expiresOn"
}

deny contains msg if {
    input.metadata.kind == "demo"
    time.parse_rfc3339_ns(sprintf("%sT00:00:00Z", [input.metadata.expiresOn])) < time.now_ns()
    msg := sprintf("expiresOn %q está en el pasado", [input.metadata.expiresOn])
}

# Los traits deben existir en el registro — una errata que no coincide con nada es peor que no comprobar.
deny contains msg if {
    some p in input.provides
    some t in p.traits
    not t in data.registry.traits
    msg := sprintf("trait no registrado %q en provides", [t])
}
```

**Las políticas necesitan sus propios tests.** Una regla que nunca se dispara da una falsa confianza. Mantén `policy/*_test.rego` junto a las reglas y ejecuta `conftest verify` en el mismo job.

### 13.4 G2 y G3 — escaneo de seguridad

El escaneo estático ve la *llamada* al módulo; el escaneo del plan ve el *resultado* del módulo. Una mala configuración dentro de un módulo alcanzable solo con una combinación particular de globals aparece solo en G3. En una plataforma compartida donde un generador sirve a cinco entornos, eso importa.

```bash
terramate run --changed --enable-sharing --mock-on-fail -- \
  sh -c 'tofu show -json out.tfplan > plan.json'

terramate run --changed -- \
  checkov -f plan.json --framework terraform_plan \
          --config-file "${TM_ROOT}/.checkov/${TM_CLOUD}.yaml"

conftest test --policy policy/ --data registry/registry.json --data env.json \
  --namespace terraform.public_names --namespace terraform.own_network \
  --namespace terraform.own_location plan.json       # un --namespace por paquete de G3
```

`--namespace` coincide con un paquete **exactamente**: `--namespace terraform` no coincide con ningún `package terraform.public_names` y el paso pasa con `0 tests` (medido, conftest 0.70.1). G3 nombra cada uno de sus paquetes, en lugar de `--all-namespaces`, para que las reglas de G1 no se ejecuten sobre un plan; y lleva la misma salvaguarda de cero reglas que G1 (§14.4).

En G3 el plan lleva los nombres que G1 no ve. `env_words` se importa del paquete de G1, así que las dos comprobaciones usan la misma lista:

```rego
package terraform.public_names

import data.environment.public_names.env_words

# Todo recurso gestionado del plan, a cualquier profundidad de módulo.
resources contains r if {
    walk(input.planned_values, [_, r])
    is_object(r)
    r.mode == "managed"
}

# Nombres que cualquiera ve sin credenciales.
public_names contains [r.address, r.values.name] if {
    some r in resources
    r.type == "google_storage_bucket"                       # espacio de nombres global, se puede sondear
}

public_names contains [r.address, r.values.name] if {
    some r in resources
    r.type == "google_dns_record_set"
    not endswith(r.values.name, ".internal.")              # las zonas privadas (qa.internal) conservan el nombre
}

public_names contains [r.address, d] if {
    some r in resources
    r.type == "google_certificate_manager_certificate"     # queda en los logs de Certificate Transparency
    some m in r.values.managed
    some d in m.domains
}

deny contains msg if {
    some [addr, name] in public_names
    some token in split(replace(name, ".", "-"), "-")
    token in env_words
    msg := sprintf("%s: public name %q carries the environment word %q (edge-qa DL10)", [addr, name, token])
}
```

`terraform.own_network` mantiene los recursos de red y DNS de un entorno en su propia VPC. En el proyecto non-prod compartido, `compute.networkAdmin` alcanza todas las VPC del proyecto, y nada en IAM impide hacer visible una zona privada a la VPC de otro entorno (`network-qa` DW8). Corre sobre los stacks de entorno; los planes de la landing zone tienen sus propias reglas (`landing-zone-qa` §11.1). `env.json` se escribe por stack desde los globals (`{"env": {"name": "qa", "region": "europe-west1", "network": "projects/<proyecto>/global/networks/qa"}}`):

```rego
package terraform.own_network

import data.terraform.public_names.resources

own := data.env.network
prefix := sprintf("%s-", [data.env.name])

# Un self link, una URL completa o un nombre a secas, todos de la VPC de este entorno.
same_network(v) if endswith(v, own)
same_network(v) if v == data.env.name

# Un mock es un productor aún sin aplicar (preview); deploy ejecuta G3 sin mocks.
checked(v) if { is_string(v); not contains(v, "mock") }

network_bound := {"google_compute_firewall", "google_compute_subnetwork", "google_compute_router",
                  "google_compute_route", "google_service_networking_connection"}

deny contains msg if {
    some r in resources
    r.type in network_bound
    checked(r.values.network)
    not same_network(r.values.network)
    msg := sprintf("%s: network %q is not this environment's VPC (network-qa DW8)", [r.address, r.values.network])
}

deny contains msg if {
    some r in resources
    r.type == "google_dns_managed_zone"
    some c in r.values.private_visibility_config
    some n in c.networks
    checked(n.network_url)
    not same_network(n.network_url)
    msg := sprintf("%s: private zone visible to %q, another environment's VPC (network-qa DW8)", [r.address, n.network_url])
}

deny contains msg if {
    some r in resources
    r.type in {"google_dns_managed_zone", "google_dns_record_set"}
    zone := object.get(r.values, "managed_zone", r.values.name)
    not startswith(zone, prefix)
    msg := sprintf("%s: zone %q does not carry the prefix %q (network-qa DW8)", [r.address, zone, prefix])
}
```

`terraform.own_location` mantiene los recursos regionales de un entorno en su región (`multi-environment` DX5). `gcp.resourceLocations` impide que un recurso salga de la jurisdicción; dentro de ella, solo esta regla distingue una región de otra. La comparación lleva el separador, porque `europe-west1` es prefijo de `europe-west10`:

```rego
package terraform.own_location

import data.terraform.public_names.resources

region := data.env.region

# Dónde dice vivir un recurso: region, location o zone, en minúsculas (los buckets responden "EUROPE-WEST1").
located contains [r.address, lower(v)] if {
    some r in resources
    some k in ["region", "location", "zone"]
    v := r.values[k]
    is_string(v)
}

# La propia región o una de sus zonas; europe-west10 no está en europe-west1.
in_region(loc) if loc == region
in_region(loc) if startswith(loc, sprintf("%s-", [region]))

# Los recursos globales (el balanceador, Cloud Armor, DNS) no tienen región que equivocar.
deny contains msg if {
    some [addr, loc] in located
    loc != "global"
    not in_region(loc)
    msg := sprintf("%s: located in %q, outside the environment's region %q (multi-environment DX5)", [addr, loc, region])
}
```

Configuración de Checkov por cloud, ya que las comprobaciones difieren:

```yaml
# .checkov/gcp.yaml
framework: [terraform, terraform_plan]
skip-check:
  # Los clusters demo permiten intencionadamente endpoints públicos para el acceso del presentador.
  # Restringido por directorio, no globalmente.
  - CKV_GCP_69
directory: [stacks/platforms/gcp, stacks/archetypes]
soft-fail-on: [LOW, MEDIUM]
hard-fail-on: [HIGH, CRITICAL]
```

Cada `skip-check` necesita un comentario que nombre la razón y el alcance. Las supresiones para `demos` no deben filtrarse a producción — divide los ficheros de configuración por entorno si una única lista de skip empieza a servir a ambos.

### 13.5 Admisión de cluster — Gatekeeper como capa 2b

El control de admisión pertenece a la **capa 2b**, entre el runtime y los servicios de plataforma. No puede estar en la capa 3: si Gatekeeper refuerza los Pod Security Standards, debe estar en su sitio antes de que se admitan las cargas de trabajo de gateway y monitorización. También tiene alcance de cluster en lugar de ser un servicio consumido por nombre. El precedente es la capa 1b para la monitorización de cloud.

```mermaid
flowchart BT
    L2["<b>Capa 2 · cluster</b><br/>gke · gke-autopilot · eks · aks"]
    L2B["<b>Capa 2b · policy</b><br/>policy-gatekeeper"]
    L3["<b>Capa 3</b><br/>gateway · monitoring · certs · dns · secrets"]
    L2 --> L2B --> L3
    style L2B fill:#fff4e5
```

**Gatekeeper autogestionado en las tres clouds.** Las alternativas gestionadas — Policy Controller en GKE, el add-on de Azure Policy en AKS — son mutuamente excluyentes con una instalación autogestionada: AKS rechaza el add-on si Gatekeeper v3 ya está presente. Elegirlas significa tres comportamientos distintos que depurar, una versión que no controlas, plantillas personalizadas restringidas en Azure, y una licencia de GKE Enterprise. Autogestionado da una versión, un conjunto de `ConstraintTemplate`s y un modelo de exención en todas partes. Mantener la actualización vosotros mismos es barato en comparación.

Los proveedores alternativos se modelan de todos modos, por si el cumplimiento normativo alguna vez exige uno:

```yaml
# archetypes/policy-gatekeeper/manifest.yaml   ← portable, recomendado
provides:
  - capability: policy
    version: 1.0.0
    traits: [gatekeeper, custom-templates, audit-api, referential-constraints]
conflicts:
  - archetype: policy-controller-gke
  - archetype: policy-azure-aks

# archetypes/policy-azure-aks/manifest.yaml    ← solo si el cumplimiento lo requiere
provides:
  - capability: policy
    version: 1.0.0
    traits: [gatekeeper, audit-api]            # SIN custom-templates
```

Un arquetipo que necesita sus propias plantillas declara `traits: [custom-templates]`, y el resolver rechaza el binding gestionado de Azure. Para eso están exactamente los traits.

**Rego se comparte como lenguaje, no como reglas.** Gatekeeper envuelve las políticas en `ConstraintTemplate` y la entrada es un `AdmissionReview`, no `resolution.json`. El equipo mantiene un lenguaje de políticas y un conjunto de bibliotecas auxiliares; las reglas en sí son separadas.

### 13.6 Sin mutación

Gatekeeper puede inyectar labels y anotaciones automáticamente. No lo uses.

La mutación introduce una fuente de cambio invisible en los diffs de Terraform, y divide la propiedad de las labels requeridas entre el generador y el controlador de admisión. El generador emite las labels; Gatekeeper las valida. Un escritor, un validador.

Esto es también lo que hace que el registro único sea load-bearing: si la lista de labels obligatorias vive en dos sitios, cualquier divergencia bloquea despliegues legítimos en la admisión — el peor lugar posible para descubrirlo.

### 13.7 Modo de refuerzo por entorno

Empezar cada regla en `deny` en un cluster que ya lleva cargas de trabajo va mal. Pilota ambos ajustes desde globals:

| Entorno | `enforcementAction` | `failurePolicy` |
|---|---|---|
| ephemeral, demos | `warn` | `Ignore` |
| dev, qa | `deny` | `Ignore` |
| prod | `deny` | `Fail` |

Las reglas nuevas siempre entran en `dryrun`, se revisan los resultados de auditoría, y se promueven una a una. Una política mal escrita entonces no puede bloquear producción el día que se fusiona.

> **`failurePolicy: Fail` puede dejarte fuera del cluster.** Si el webhook de Gatekeeper está caído, el cluster rechaza toda admisión — incluida la propia recuperación de Gatekeeper. Mitígalo con `exemptNamespaces` para `kube-system` y el namespace de Gatekeeper, al menos tres réplicas con un PodDisruptionBudget, y `Ignore` en todas partes excepto producción.

**Despliega los recursos `ConstraintTemplate` y `Constraint` mediante el propio chart de Helm del arquetipo**, nunca con `kubernetes_manifest`. Ese provider requiere que el CRD exista y que el API server sea alcanzable en el momento del plan, lo que rompe las previews de PR y `--mock-on-fail` — la misma razón por la que se evita para los recursos de Gateway API (§10.5).

### 13.8 El registro único

Las capabilities, los traits, los nombres de zona de pool y las labels obligatorias se expresan actualmente en varios sitios: como `enum`s en los JSON Schemas, como `data` para conftest, y como valores para el chart de Gatekeeper. Dejados así, divergen en cuestión de meses.

```
registry/
├── capabilities.yaml     # enum de capability
├── traits.yaml           # vocabulario de traits
├── zones.yaml            # nombres de zona de pool
└── labels.yaml           # labels obligatorias por tipo de recurso
```

Todo lo demás se **genera** a partir de estos:

| Artefacto generado | Consumidor |
|---|---|
| Bloques `enum` en `schemas/*.schema.json` | `check-jsonschema` |
| Bundle `registry/registry.json` (clave de primer nivel `registry`) | `conftest --data` |
| `values.yaml` del chart de Gatekeeper | Parámetros de `ConstraintTemplate`: etiquetas obligatorias, registros permitidos y los namespaces con un nivel de Pod Security distinto de `restricted` (propuesta de Gatekeeper §7.1) |

Protégelo con una puerta `registry-generate --check` en CI, exactamente igual que `terramate generate --detailed-exit-code`. El YAML es la fuente; un schema editado a mano es un bug.

---

## 14. CI/CD con GitHub Actions

### 14.1 Workflow de preview (pull request)

**Cada job de workflow que toca una nube actúa para exactamente un entorno**, con la identidad de ese entorno. Las identidades del pipeline son por entorno (§11.2, §11.4) y la identidad de apply está ligada al GitHub Environment del mismo nombre, así que un solo job no puede aplicar dos entornos, y no debe intentarlo. Por eso la preview va en dos partes: las puertas que no necesitan credenciales, una vez; después, un job de plan por cada entorno que toca la pull request.

```yaml
name: preview
on:
  pull_request:                # cualquier rama base: un pull request apilado sobre otro pasa las mismas puertas

permissions:
  contents: read
  pull-requests: write
  id-token: write            # OIDC hacia la nube, solo lo usan los jobs de plan

jobs:
  gates:                     # G0 y G1 — sin credenciales de nube
    runs-on: ubuntu-latest
    outputs:
      envs: ${{ steps.envs.outputs.envs }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0     # la detección de cambios necesita historial

      - uses: jdx/mise-action@v2       # fija terramate, tofu, checkov, conftest

      # --- G0: integridad de la generación ---
      - name: Check generated code is current
        run: |
          terramate generate --detailed-exit-code || {
            echo "::error::El código generado está obsoleto. Ejecuta 'terramate generate' y commitea."
            exit 1
          }

      # --- G1: estructura, composición, orden (§14.4) ---
      - name: Policy
        run: ./ci/g1.sh

      - name: Checkov (static)
        run: checkov -d stacks --framework terraform --config-file .checkov/gcp.yaml

      # --- ¿qué entornos toca este PR? ---
      - name: Changed environments
        id: envs
        run: |
          envs=()
          for e in landing-zone $(ls environments); do
            [ -n "$(terramate list --changed --tags "$e")" ] && envs+=("$e")
          done
          echo "envs=$(jq -cn '$ARGS.positional' --args "${envs[@]}")" >> "$GITHUB_OUTPUT"

  plan:                      # un job por entorno tocado, con su propia identidad de solo lectura
    needs: gates
    if: needs.gates.outputs.envs != '[]'
    strategy:
      fail-fast: false
      matrix:
        env: ${{ fromJSON(needs.gates.outputs.envs) }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: ./.github/actions/setup              # mise + identidad derivada de ci/federation.env (landing-zone-qa DZ12)
        with: { identity: tf-plan, env: "${{ matrix.env }}" }

      # --- plan con sharing + mocks, solo los stacks de este entorno ---
      - name: Plan
        run: terramate script run --changed --tags ${{ matrix.env }} tofu preview

      # --- G2: escaneo del plan ---
      - name: Checkov (plan)
        run: |
          terramate run --changed --tags ${{ matrix.env }} -- sh -c '
            tofu show -json out.tfplan > plan.json &&
            checkov -f plan.json --framework terraform_plan
          '

      - name: Summary
        run: |
          {
            echo "### ${{ matrix.env }} — changed stacks"
            echo '```'
            terramate list --changed --tags ${{ matrix.env }} --run-order
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
```

Puntos clave:

- **`terramate script run --changed tofu preview`** usa el script de §4.8, así que `enable_sharing = true` y `mock_on_fail = true` están garantizados. Una invocación cruda de `terramate run` que olvide `--enable-sharing` produce un plan contra variables sin fijar.
- **`fetch-depth: 0`** — la detección de cambios compara contra `main`; un clon superficial reporta silenciosamente cero stacks cambiados.
- **G0 es `terramate generate --detailed-exit-code`**: 0 si el código generado está al día, 2 si la generación cambió un fichero, 1 si hay error. No existe la opción `--check` (`poc/RESULTS.es.md`).
- **Un entorno por job de plan.** Cada stack lleva su entorno como tag (`qa`, `prod`, …) y los de la landing zone llevan `landing-zone`, así que `--tags <env>` selecciona exactamente los stacks de una identidad. Una pull request que cambia un generador compartido toca todos los entornos y recibe un job de plan por entorno, cada uno leyendo solo su propio prefijo de estado. Un job que se autenticara una vez y lo planificara todo necesitaría una identidad que leyera el estado de todos los entornos — justo lo que §11.2 existe para impedir.
- **Otras nubes.** Un entorno de AWS o Azure cambia el paso de autenticación (`aws-actions/configure-aws-credentials` con `tf-plan-<env>`, `azure/login` con la credencial federada del entorno); la forma del job es la misma. Las plantillas completas, con una acción compuesta que oculta el paso por nube, están en la propuesta `infra-repo-qa`.

### 14.2 Workflow de despliegue (merge a main)

El workflow de deploy aplica lo que se ha fusionado, **entorno a entorno, cada uno en un job ligado al GitHub Environment de ese entorno**. El Environment es lo que hace alcanzable la identidad de apply (§11.2), lleva los revisores de ese entorno y serializa las ejecuciones contra él. Orden: la landing zone, después los entornos no productivos en paralelo, después `prod`.

```yaml
name: deploy
on:
  push:
    branches: [main]

permissions:
  contents: read
  id-token: write

jobs:
  changes:                   # por entorno: ¿cambiado desde su último deploy con éxito?
    runs-on: ubuntu-latest
    outputs:
      lz:      ${{ steps.c.outputs.lz }}        # {"env":"landing-zone","base":"<sha>"} o ""
      nonprod: ${{ steps.c.outputs.nonprod }}   # [{"env":"qa","base":"<sha>"}, …]
      prod:    ${{ steps.c.outputs.prod }}      # {"env":"prod","base":"<sha>"} o ""
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: jdx/mise-action@v2
      - run: ./ci/fetch-observed.sh                # un repositorio nuevo aún no tiene cmdb-observed
      - id: c
        run: ./ci/changed-envs.sh   # lee cmdb-data/observed/deployed/<env>.json; escribe lz, nonprod, prod

  landing-zone:
    needs: changes
    if: needs.changes.outputs.lz != ''
    uses: ./.github/workflows/apply-env.yml
    with: { env: landing-zone, base: "${{ fromJSON(needs.changes.outputs.lz).base }}" }

  nonprod:
    needs: [changes, landing-zone]
    if: ${{ !cancelled() && needs.changes.outputs.nonprod != '[]' && needs.landing-zone.result != 'failure' }}
    strategy:
      fail-fast: false       # un fallo en dev no para qa
      matrix:
        include: ${{ fromJSON(needs.changes.outputs.nonprod) }}
    uses: ./.github/workflows/apply-env.yml
    with: { env: "${{ matrix.env }}", base: "${{ matrix.base }}" }

  prod:
    needs: [changes, landing-zone, nonprod]
    if: ${{ !cancelled() && needs.changes.outputs.prod != '' && needs.landing-zone.result != 'failure' && needs.nonprod.result != 'failure' }}
    uses: ./.github/workflows/apply-env.yml
    with: { env: prod, base: "${{ fromJSON(needs.changes.outputs.prod).base }}" }

  cmdb:
    needs: [landing-zone, nonprod, prod]
    if: ${{ !cancelled() && !(needs.landing-zone.result == 'skipped' && needs.nonprod.result == 'skipped' && needs.prod.result == 'skipped') }}
    permissions: { contents: write }
    uses: ./.github/workflows/cmdb-sync.yml
    with: { pattern: "cmdb-observed-${{ github.run_id }}-*" }
```

El job por entorno es un único workflow reutilizable, así que los tres llamadores no pueden divergir:

```yaml
# .github/workflows/apply-env.yml
name: apply-env
on:
  workflow_call:
    inputs:
      env:  { type: string, required: true }
      base: { type: string, required: true }   # commit del último deploy con éxito de env

jobs:
  apply:
    runs-on: ubuntu-latest
    environment: ${{ inputs.env }}             # revisores; pone environment=<env> en el token OIDC
    concurrency: { group: "deploy-${{ inputs.env }}", cancel-in-progress: false }
    permissions: { contents: read, id-token: write }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: jdx/mise-action@v2

      - name: Verify generated code
        run: terramate generate --detailed-exit-code

      - uses: ./.github/actions/setup              # mise + identidad derivada de ci/federation.env (landing-zone-qa DZ12)
        with: { identity: tf-apply, env: "${{ inputs.env }}" }

      - name: Apply changed stacks
        id: apply
        run: terramate script run --changed -B "${{ inputs.base }}" --tags "${{ inputs.env }}" --no-tags bootstrap tofu deploy   # mocks DESACTIVADOS

      - name: Collect CMDB observations
        if: ${{ !cancelled() }}                          # también tras un apply fallido: registra outcome failed
        run: |
          terramate run --changed -B "${{ inputs.base }}" --tags "${{ inputs.env }}" --no-tags bootstrap -- \
            archetypectl cmdb observe --out "$RUNNER_TEMP/observed"
      - name: Record the deploy marker
        if: ${{ !cancelled() && steps.apply.outcome == 'success' }}   # el apply, no el job: una observación fallida no retiene el marcador
        run: |
          mkdir -p "$RUNNER_TEMP/observed/deployed"
          jq -n --arg sha "$GITHUB_SHA" --argjson run "$GITHUB_RUN_NUMBER" '{sha:$sha, run:$run}' \
            > "$RUNNER_TEMP/observed/deployed/${{ inputs.env }}.json"
      - uses: actions/upload-artifact@v4
        if: ${{ !cancelled() }}
        with: { name: "cmdb-observed-${{ github.run_id }}-${{ inputs.env }}", path: "${{ runner.temp }}/observed" }
```

Puntos clave:

- **Un entorno, una identidad, una puerta por job.** `environment: ${{ inputs.env }}` pone `environment=<env>` en el token OIDC, que es el único principal autorizado a suplantar a `tf-apply-<env>@` (§11.2). `.github/actions/setup` deriva la identidad del entorno del job y de las coordenadas commiteadas en `ci/federation.env` (`landing-zone-qa` DZ12), así que el mismo texto de workflow se resuelve a `tf-apply-qa@` en `qa` y a `tf-apply-prod@` en `prod`, y ninguna variable puesta a mano puede apuntar un job a la identidad de otro entorno. El job único `environment: production` de borradores anteriores no podía funcionar: su token llevaba un entorno e intentaba aplicarlos todos.
- **La base de cambios es el último deploy con éxito del entorno, no `HEAD^`.** Con `HEAD^`, una ejecución fallida o cancelada deja sus stacks sin aplicar y el siguiente merge ya no los ve; además GitHub mantiene solo una ejecución pendiente por grupo de concurrencia y cancela las demás, así que con una ráfaga de merges algunos commits nunca se despliegan por sí mismos. El marcador `deployed/<env>.json` en la rama `cmdb-observed` solo se escribe cuando el apply de un entorno tuvo éxito completo, y `cmdb-sync` solo lo mueve hacia delante (`run` mayor). La siguiente ejecución compara desde ahí y recoge todo lo posterior.
- **El marcador sigue al paso de apply, no al job.** `steps.apply.outcome == 'success'` lo escribe aunque falle el paso de observación que va después: un observador que no puede ejecutarse (una herramienta ausente, un rechazo del esquema) pone el job en rojo y se informa, pero no retiene el marcador. Atado a `success()`, un observador roto deja a todos los entornos sin marcador para siempre, y cada ejecución vuelve a aplicar todo desde el primer despliegue.
- **Un repositorio nuevo no tiene rama `cmdb-observed`.** `ci/fetch-observed.sh` distingue "la rama aún no existe" (`git ls-remote --exit-code` devuelve 2: ningún entorno tiene marcador) de un remoto que falló (cualquier otro código: error), y `cmdb-sync` crea la rama vacía en su primera ejecución. Un `git fetch origin cmdb-observed` sin protección hace fallar el primer `deploy`.
- **Un entorno sin marcador no lo despliega este workflow.** Su primer apply es escalonado (§4.11) y se ejecuta desde `first-deploy`, un workflow manual con el mismo Environment; es el que escribe el primer marcador. `changes` informa de ese entorno como aviso, no como error.
- **No productivo antes que producción.** Un cambio en un generador compartido llega primero a `qa` y `dev` en la misma ejecución; `prod` solo empieza si ninguno falló, y sus revisores ven el resultado. Es orden, no promoción — la promoción de imágenes de aplicación es asunto de la guía de desarrollo (`developer-guide.md` §5).
- **La landing zone va primero y sola**, desde el Environment `landing-zone` con `tf-apply-lz@`. Los workflows de entorno seleccionan por `--tags <env>`, que nunca incluye los stacks de la landing zone, y sus identidades tampoco podrían aplicarlos (`landing-zone-qa` §5.2). El único stack de la landing zone que el pipeline nunca aplica es `gcp-lz-bootstrap`, que crea la propia federación e identidades del pipeline: `--no-tags bootstrap` lo excluye, y lo aplica una persona (`landing-zone-qa` §1, DZ8).

Las observaciones llegan a la CMDB por un workflow reutilizable, el mismo para `deploy`, `drift` y `destroy`. Es el único punto del pipeline con `contents: write`, y nunca escribe en `main` (`archetype-model.md` §11.1):

```yaml
# .github/workflows/cmdb-sync.yml
name: cmdb-sync
on:
  workflow_call:
    inputs:
      pattern: { type: string, required: true }   # patrón de nombre de los artifacts de este run

jobs:
  aggregate:
    runs-on: ubuntu-latest
    permissions: { contents: write }              # el ruleset de main no tiene bypass para github-actions
    concurrency: { group: cmdb-write, cancel-in-progress: false }
    steps:
      - uses: actions/checkout@v4
        with: { path: observed }
      - name: La rama cmdb-observed, creada vacía en la primera ejecución
        working-directory: observed
        run: |
          rc=0; git ls-remote --exit-code --heads origin cmdb-observed >/dev/null || rc=$?
          case $rc in
            0) git fetch origin cmdb-observed && git switch -c cmdb-observed FETCH_HEAD ;;
            2) git switch --orphan cmdb-observed ;;
            *) exit $rc ;;
          esac
      - uses: actions/checkout@v4
        with: { path: main, sparse-checkout: schemas }
      - uses: actions/download-artifact@v4
        with: { pattern: "${{ inputs.pattern }}", merge-multiple: true, path: "${{ runner.temp }}/in" }
      - name: Validate
        run: |
          shopt -s nullglob; files=("$RUNNER_TEMP"/in/*.json)
          [ ${#files[@]} -gt 0 ] || { echo "::notice::ninguna observación en esta ejecución"; exit 0; }
          check-jsonschema --schemafile main/schemas/cmdb-observed.schema.json "${files[@]}"
      - name: Merge; deploy markers only move forward
        run: |
          cp "$RUNNER_TEMP"/in/*.json observed/cmdb-data/observed/ 2>/dev/null || true
          mkdir -p observed/cmdb-data/observed/deployed
          for m in "$RUNNER_TEMP"/in/deployed/*.json; do
            [ -e "$m" ] || continue
            cur="observed/cmdb-data/observed/deployed/$(basename "$m")"
            if [ ! -e "$cur" ] || [ "$(jq .run "$m")" -gt "$(jq .run "$cur")" ]; then cp "$m" "$cur"; fi
          done
      - name: Commit and push, with rebase and retry
        working-directory: observed
        run: |
          git add cmdb-data/observed
          git diff --cached --quiet && exit 0
          git -c user.name=cmdb-bot -c user.email=cmdb-bot@users.noreply.github.com \
            commit -m "observed: run ${{ github.run_id }}"
          for i in 1 2 3; do
            if git ls-remote --exit-code --heads origin cmdb-observed >/dev/null; then git pull --rebase origin cmdb-observed || exit 1; fi
            git push origin HEAD:cmdb-observed && exit 0
            sleep $((i*5))
          done
          exit 1

  publish:
    needs: aggregate
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - run: ./ci/fetch-observed.sh                # un repositorio nuevo aún no tiene cmdb-observed
      - name: Join both halves
        run: archetypectl cmdb publish --observed origin/cmdb-observed --out dist/   # index.json, graph.jsonld
      - name: Replace the release asset
        run: gh release upload cmdb-latest dist/index.json dist/graph.jsonld --clobber
        env: { GH_TOKEN: "${{ github.token }}" }
```

`publish` avisa de cualquier stack cuya última observación sea más antigua que el intervalo del drift: un agregador que dejó de fallar en voz alta es como una CMDB empieza a mentir con confianza.

> **`terramate run --changed` respeta el orden de dependencia** derivado del anidamiento y de `after`. **No** deriva el orden de los bloques `input`. Si una PR cambia solo el stack de app pero los outputs de la plataforma también cambiaron en una fusión anterior, el stack de app leerá los outputs actuales (correctos) — pero si ambos cambian en la misma PR, el orden viene enteramente de tus declaraciones `after`. Esta es la razón por la que §4.5 insiste en el invariante input↔after.

### 14.3 Workflow de drift (programado)

```yaml
name: drift
on:
  schedule:
    - cron: '0 5 * * *'

permissions:
  contents: read
  id-token: write

jobs:
  drift:                     # un job por entorno, con su identidad de solo lectura
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        env: ${{ fromJSON(vars.DRIFT_ENVS) }}   # variable del repositorio: ["landing-zone","qa","prod",…]
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: ./.github/actions/setup              # mise + identidad derivada de ci/federation.env (landing-zone-qa DZ12)
        with: { identity: tf-plan, env: "${{ matrix.env }}" }
      - name: Detect drift and record it
        id: drift
        run: |
          terramate run --tags ${{ matrix.env }} --enable-sharing -- \
            archetypectl cmdb observe --drift --out "$RUNNER_TEMP/observed"
          # por stack: tofu plan -detailed-exitcode -lock=false; salida 2 → outcome drifted, driftAt
          if grep -rqs '"outcome": "drifted"' "$RUNNER_TEMP/observed"; then
            echo "::warning::Drift detectado en ${{ matrix.env }}"
            echo "drifted=true" >> "$GITHUB_OUTPUT"
          fi
      - uses: actions/upload-artifact@v4
        with: { name: "cmdb-observed-${{ github.run_id }}-${{ matrix.env }}", path: "${{ runner.temp }}/observed" }
      - if: steps.drift.outputs.drifted == 'true'
        run: exit 1

  cmdb:
    needs: drift
    if: ${{ !cancelled() }}
    permissions: { contents: write }
    uses: ./.github/workflows/cmdb-sync.yml
    with: { pattern: "cmdb-observed-${{ github.run_id }}-*" }
```

### 14.4 Puerta de políticas en el pipeline

El invariante de ordenamiento que antes dependía de un script de shell es ahora una política Rego (§13.3). El pipeline ejecuta conftest sobre tres artefactos:

```yaml
- name: Build policy inputs
  run: |
    registry-generate --check                 # el registro es la fuente de verdad
    archetypectl resolve --dry-run > resolution.json
    ./ci/stacks-json.sh > stacks.json         # Terramate 0.17 no tiene `list --json`
    archetypectl enrich stacks.json           # añade consumes[] y after_ids[]

- name: G1 — structure and composition
  run: |
    conftest verify --policy policy/          # los tests propios de las políticas
    ct() {                                    # conftest que se niega a pasar sin haber evaluado nada
      out=$(conftest test --all-namespaces --policy policy/ --data registry/registry.json -o json "$@") \
        || { jq -r '.[] | .filename as $f | .failures[]? | "FAIL \($f): \(.msg)"' <<<"$out"; return 1; }
      jq -e '[.[] | .successes + (.failures // [] | length)] | add > 0' <<<"$out" >/dev/null \
        || { echo "G1: no rule evaluated for $*" >&2; return 1; }
    }
    ct resolution.json stacks.json
    for m in archetypes/*/manifest.yaml; do ct "$m"; done
    for b in environments/*/binding.yaml; do ct "$b"; done   # nombres públicos: public_id y dns_suffix (§13.3)
```

Dos flags sostienen la puerta, y la ausencia de cualquiera de ellos hace que **pase sin haber evaluado nada** (medido, conftest 0.70.1):

| Flag | Sin él |
|---|---|
| `--all-namespaces` | conftest solo evalúa `package main`. Las políticas son `terramate.stacks`, `terramate.contracts`, `archetype.composition`, `environment.public_names`: no se ejecuta ninguna regla y el resultado es `0 tests, 0 passed`, salida 0 |
| `--data registry/registry.json` | `--data registry/` carga cada fichero **en la raíz** de `data`, así que `data.registry.traits` no está definido, `not t in data.registry.traits` nunca se cumple y un rasgo desconocido pasa. El paquete que escribe `registry-generate` tiene la clave de primer nivel `registry` |

La función `ct` es la tercera salvaguarda: una puerta que evaluó cero reglas falla, sea cual sea la causa — un paquete renombrado, un fichero movido, un flag nuevo en una versión de conftest. **Una puerta que no puede ejecutarse es peor que una ausente, porque informa de éxito.**

`ci/stacks-json.sh` construye el inventario de stacks. Terramate 0.17 **no tiene `list --json`** (medido): `terramate list` solo imprime rutas. `terramate experimental eval` expone `terramate.stack.id`, `tags` y `path` pero **no `after`** (medido, 0.17.3: *"This object does not have an attribute named after"*), y sin `after` el inventario no puede alimentar la regla de R2. `terramate debug show metadata` imprime los metadatos de cada stack, `after` incluido, un `clave=valor` por línea con el valor en JSON; el script lo convierte en un único array:

```bash
#!/usr/bin/env bash
# ci/stacks-json.sh — id, ruta, tags y after de cada stack, como un único array JSON
set -euo pipefail
terramate debug show metadata | jq -Rn '
  reduce (inputs | select(test("^\\s+terramate\\.stack\\."))
          | capture("^\\s+terramate\\.stack\\.(?<k>[a-z_.]+)=(?<v>.*)$")) as $m
    ([]; if $m.k == "id" then . + [{}] else . end | .[-1][$m.k] = ($m.v | fromjson))
  | map({id, path: .["path.relative"], tags, after})
  | if length == 0 then error("stacks-json: no stack parsed") else . end'
```

`debug` es un comando de diagnóstico, no una interfaz estable: el script está fijado a la versión de Terramate de `mise.toml`, y un cambio de formato que no se pueda leer produce un array vacío, que el script rechaza en lugar de entregar a G1 un inventario sin stacks. Sustitúyase por `list --json` cuando Terramate ofrezca uno que lleve `after`.

`archetypectl enrich` es la única pieza a medida: el inventario no expone los bloques `input`, así que el enriquecedor lee los bloques `input` de cada stack — `from_stack_id`, la salida y el `mock` — en `consumes[]`, y resuelve el `after` del inventario (rutas y filtros por tag) en `after_ids[]`; las políticas comparan esos campos. Mantener esa extracción en una pequeña herramienta, en lugar de en la política, mantiene el Rego portable y testable contra fixtures.


---

## 15. Registro de riesgos

El registro completo — 69 riesgos agrupados por dominio (66 activos; R28 retirado como duplicado de R26, R38 y R39 retirados con el endpoint DNS del plano de control), con probabilidad, impacto, mitigación y la sección que especifica cada control — se mantiene en su propio documento, `risk-register.md`. Se revisa en cada hito de fase de la hoja de ruta en lugar de leerse de principio a fin.

Los cinco sobre los que actuar primero:

| Puesto | Riesgo | Por qué encabeza la lista |
|---|---|---|
| 1 | **R2** — falta `after` en un stack consumidor | Fallo silencioso; aplica un valor incorrecto sin error (§14.4) |
| 2 | **R12** — `sub` comodín en una trust policy OIDC | Cualquier rama o PR de fork puede asumir el rol de apply (§11.3) |
| 3 | **R26** — rango de pods dimensionado para muy pocos nodos | Inmutable; solo se arregla reconstruyendo el cluster (§9.2, AM §9.4) |
| 4 | **R34** — deriva del registro | Falla en la admisión, después de que el generador y el `Constraint` divergieran (§13.8) |
| 5 | **R5** — plataforma compartida destruida por el desmontaje de una instancia | Un selector de tag equivocado tumba a cada tenant (§12.4) |

---

## 16. Hoja de ruta de adopción

### Fase 0 — Validar suposiciones (1 semana)

Construye un repositorio desechable con dos stacks y confirma, contra tu versión fijada de Terramate. El soporte de expresiones en `from_stack_id` se toma como una decisión de diseño; lo que queda es confirmar sus variantes. **Las cinco primeras se midieron el 2026-09-16 (Terramate 0.16.0, OpenTofu 1.10.6) y se repitieron el 2026-09-28 con 0.16.0 y con 0.17.3, con salida idéntica; la evidencia está en `poc/RESULTS.es.md`.** El resto necesita un proyecto en la nube y se comprueba en el primer despliegue de `qa` (`landing-zone-qa` VZ1–VZ5):

- [x] `from_stack_id` resuelve un global **heredado de un directorio padre**, no solo uno definido en el propio stack
- [x] `from_stack_id` acepta **interpolación** (`"${global.env}-gke"`), no solo una referencia desnuda
- [x] `stack.after` acepta una ruta derivada de globals — **refutado, con un error de análisis, no en silencio**; los filtros de tag (`after = ["tag:network"]`) y las rutas literales funcionan, así que el resolver escribe literales
- [x] `--mock-on-fail` se comporta como está documentado cuando el productor no tiene estado — y no enmascara un stack productor inexistente
- [x] `tofu output -json` se ejecuta con éxito como `sharing_backend.command` (en local; repetir en la imagen de CI)
- [ ] Las lecturas de estado entre proyectos / entre cuentas funcionan con tus roles OIDC
- [ ] La federación OIDC funciona de extremo a extremo con una condición de confianza **sin comodines** (§11.2, §11.3)
- [ ] El plano de control es alcanzable desde el tipo de runner elegido — en GKE por el endpoint DNS solo con IAM, así que no hace falta camino de red del runner (`landing-zone-qa` DZ4, VZ5); en otras nubes, o has aceptado runners autoalojados (§11.9)
- [ ] Las claves de cifrado de estado de OpenTofu están restringidas por entorno, no por stack (§11.5)

Si las variantes de globals heredados o de interpolación fallan, el modelo de binding tardío de §12.2 necesita reemplazarse por un fichero de contrato generado por instancia por el resolver — más maquinaria y pull requests más ruidosas, pero no un rediseño. Mejor averiguarlo ahora.

### Fase 0b — Esqueleto del resolver (1 semana, en paralelo a la Fase 1)

- Validación de JSON Schema de manifiestos, bindings y ledgers en CI
- Pasos 1–8 del algoritmo de resolución (sin escrituras de ledger)
- Un arquetipo de catálogo y un binding de entorno, escritos a mano
- Demostrar que el `binding.tm.hcl` generado por el resolver pilota `terramate generate` sin cambios

### Fase 1 — Una cloud, una plataforma compartida (2–3 semanas)

- Configuración raíz, `sharing_backend`, mixins, `gen_network` + `gen_cluster`
- Plataforma `gcp/demos` o `aws/demos`, tres stacks
- Workflows de preview + deploy con G0 y G1
- Un arquetipo con una instancia

### Fase 2 — Segunda cloud (1–2 semanas)

- Segundo conjunto de mixins y ramas de generador
- Demostrar que los ficheros de contrato del arquetipo son genuinamente agnósticos de cloud donde §6.8 dice que deberían serlo
- Escaneo del plan G2
- Límites de permisos publicados por el stack de plataforma y asegurados en los stacks de app

### Fase 2a — Paridad de Azure (2 semanas)

- Arquetipos `landing-zone-azure`, `environment-azure`, `aks`
- Decide Azure CNI Overlay frente a CNI tradicional **antes** del primer cluster; es inmutable
- Borde: AGFC en modo BYO, o Envoy Gateway detrás de un Load Balancer interno — no ambos
- Resuelve la brecha AGFC/Keycloak OIDC si la capa 4 está en alcance en Azure
- Test de aceptación: un manifiesto de aplicación de capa 5 se despliega en Azure **sin ser editado**

### Fase 2b — Runtimes serverless (1–2 semanas, opcional pero barato)

Cloud Run y ECS Fargate reutilizan los mismos stacks de network y data, así que añadirlos es sobre todo una nueva rama de generador más un switch `global.platform.runtime`.

- `gen_app_cloudrun.tm.hcl` y `gen_app_fargate.tm.hcl` junto a los generadores de Kubernetes
- Demostrar el switch de runtime: la misma instancia de arquetipo desplegable con `runtime = "gke"` o `runtime = "cloudrun"` cambiando un global
- Validar la separación en dos roles en Fargate y el patrón de SA de runtime en Cloud Run
- Confirmar el remedio de fan-in para el stack de edge-routing de Cloud Run (§7.5)

### Fase 2c — Capa de políticas (2–3 semanas)

Secuenciada para que nada bloquee un despliegue real hasta que se haya observado primero en modo auditoría.

**2c.1 — Registro (2–3 días).** `registry/{capabilities,traits,zones,labels}.yaml`, los tres generadores (`enum`s de schema, bundle `--data` de conftest, values del chart de Gatekeeper), y la puerta `registry-generate --check`. Esto va primero porque todo lo que sigue consume el registro. Retroadaptar una única fuente una vez existen tres copias es materialmente más difícil (R34).

**2c.2 — `archetypectl enrich` (2 días).** El inventario de stacks (`ci/stacks-json.sh`, §14.4) no expone los bloques `input`, así que el enriquecedor lee los bloques `input` de cada stack (`from_stack_id`, salida, `mock`) en `consumes[]` y resuelve `after` en `after_ids[]`. Mantén la extracción aquí, no en Rego, para que las políticas sigan siendo portables y testables contra fixtures.

**2c.3 — Puerta G1, consultiva (3 días).** La política `input`↔`after` más las reglas de nombrado de stacks y de outputs secretos, ejecutándose **sin bloquear**. Mide la tasa de falsos positivos contra el repositorio existente antes de activarla.

**2c.4 — Puerta G1, bloqueante (1 día).** Retira el lint de shell. R2 solo se mitiga una vez que esto bloquea.

**2c.5 — Tests de políticas (2 días).** `policy/*_test.rego` con `conftest verify` en el mismo job. Una regla que nunca se dispara da una falsa confianza (R36); los fixtures deben cubrir tanto el caso de aprobación como el de fallo para cada regla.

**2c.6 — `policy-gatekeeper` en la capa 2b (1 semana).** Autogestionado, desplegado vía el propio chart de Helm del arquetipo — nunca `kubernetes_manifest`. Aterrízalo primero en un **entorno efímero**, con `enforcementAction: dryrun` y `failurePolicy: Ignore`. Revisa la salida de auditoría durante una semana laboral completa antes de promover cualquier regla a `warn`, y promuévela a `deny` una regla a la vez.

**Criterios de salida, todos requeridos:**

- [ ] `registry-generate --check` bloqueante; no queda ningún `enum` editado a mano
- [ ] G1 bloqueante; lint de shell borrado
- [ ] Cada regla Rego tiene un fixture de aprobación y uno de fallo
- [ ] Gatekeeper ejecutándose en un entorno efímero con una auditoría limpia durante cinco días laborables
- [ ] Simulacro de bloqueo ensayado: mata el webhook con `failurePolicy: Fail` y recupera, para que el runbook esté probado en lugar de teórico (R33)
- [ ] Respuesta medida a la pregunta abierta: **cuánto Rego se comparte genuinamente** entre conftest y los `ConstraintTemplate`s, dado que las entradas difieren (`resolution.json` frente a `AdmissionReview`). Si la respuesta es "solo la biblioteca auxiliar", dilo y deja de planificar más

### Fase 3 — Multi-tenencia (2 semanas)

- Segunda y tercera instancia en la plataforma compartida
- Generación de namespace/cuota/NetworkPolicy
- Barandillas de destroy y el lint de §14.4

### Fase 4 — Entornos dedicados y CMDB (2–3 semanas)

- Plataforma `prod` dedicada por cloud
- Matriz de globals de promoción
- Sincronización de CMDB nivel 1 y nivel 2
- Workflow de drift

### Fase 5 — Endurecimiento

- Ensayo de migración de generador `v2`
- Runbooks de break-glass
- Proceso de deprecación de contratos

---

## 17. Apéndice — chuleta de convenciones

### Nomenclatura

| Cosa | Patrón | Ejemplo |
|---|---|---|
| ID de stack | `<cloud>-<env>-<capability>[-<instance>]` | `aws-demos-eks`, `gcp-prod-disasterproject-app` |
| Tags de stack | `<cloud>`, `<env>`, `<capability>`, `platform`\|`archetype/<name>`, `instance/<id>`, `producer`\|`consumer`, `protected` | |
| Ficheros generados | `_<purpose>.tf` | `_main.tf`, `_backend.tf`, `_sharing_generated.tf` |
| Directorio de generador | `imports/generators/v<N>/gen_<capability>.tm.hcl` | `imports/generators/v1/gen_cluster.tm.hcl` |
| Fichero de contrato | `imports/contracts/contract_<capability>[_<stack>][_<cloud>].tm.hcl`; `<stack>` nombra un stack interno de un arquetipo de varios stacks, cuyas salidas son internas al arquetipo | `contract_cluster_eks.tm.hcl`, `contract_run_subnet_gcp.tm.hcl` |
| Valores mock | prefijados `mock-` / `mock` | `mock-endpoint.example.invalid` |

### Referencia de comandos

| Tarea | Comando |
|---|---|
| Regenerar todo el código | `terramate generate` |
| Verificar que la generación está al día | `terramate generate && git diff --exit-code` |
| Listar todos los stacks | `terramate list` |
| Listar stacks cambiados | `terramate list --changed` |
| Inspeccionar los globals resueltos | `terramate debug show globals` |
| Inspeccionar el orden de ejecución | `terramate experimental run-graph` |
| Plan con sharing + mocks | `terramate script run --changed tofu preview` |
| Apply con sharing | `terramate script run --changed tofu deploy` |
| Desplegar una instancia | `terramate run --tags instance/alpha --enable-sharing -- tofu apply -auto-approve` |
| Destruir una instancia | `terramate run --tags instance/alpha --reverse --enable-sharing -- tofu destroy -auto-approve` |
| Comprobación de drift | `terramate run --tags prod --enable-sharing -- tofu plan -detailed-exitcode` |
| Regenerar el registro | `registry-generate` |
| Verificar que el registro está al día | `registry-generate --check` |
| Ejecutar los tests de políticas | `conftest verify --policy policy/` |
| Ejecutar la puerta de políticas | `./ci/g1.sh` (`conftest test --all-namespaces --data registry/registry.json`, rechazando cero reglas) |
| Resultados de auditoría de Gatekeeper | `kubectl get constraints -o json \| jq '.items[].status.violations'` |

### Tabla de decisión — ¿globals u outputs sharing?

| Pregunta | Respuesta | Usa |
|---|---|---|
| ¿Se conoce el valor antes de cualquier apply? | Sí | Globals |
| ¿Es un nombre que puedes hacer determinista? | Sí | Globals (y rompe los ciclos de dependencia de este modo) |
| ¿Lo genera el proveedor de cloud en el momento del apply? | Sí | Outputs sharing |
| ¿Es una credencial o un valor secreto? | Sí | **Ninguno** — comparte una referencia, obtenla mediante un data source |
| ¿Es un token de corta duración? | Sí | **Ninguno** — obtenlo localmente por consumidor |
| ¿Compartirlo crearía un ciclo? | Sí | Promuévelo a un global |

### Ficheros que deben existir antes del primer `terramate generate`

```
/terramate.tm.hcl                        # bloque terramate + sharing_backend
/mise.toml                               # versiones de herramientas fijadas
/imports/mixins/backend_<cloud>.tm.hcl
/imports/mixins/provider_<cloud>.tm.hcl
/imports/generators/v1/gen_<capability>.tm.hcl
/imports/contracts/contract_<capability>.tm.hcl
/imports/contracts/guards.tm.hcl         # bloques assert
/stacks/platforms/<cloud>/config.tm.hcl  # globals: cloud
```

---

## Fuentes y lecturas adicionales

- Terramate — Outputs Sharing: `https://terramate.io/docs/cli/orchestration/outputs-sharing`
- Terramate — referencias de bloques `sharing_backend`, `input`, `output`: `https://terramate.io/docs/cli/reference/blocks/`
- Terramate — Orden de ejecución: `https://terramate.io/docs/cli/orchestration/order-of-execution`
- Terramate — Generación de código HCL: `https://terramate.io/docs/cli/code-generation/generate-hcl`
- Arquitectura de referencia de Terramate para AWS: `https://github.com/terramate-io/terramate-quickstart-aws`
- Arquitectura de referencia de Terramate para Azure: `https://github.com/terramate-io/terramate-quickstart-azure`
- Mattias Fjellström, *A pattern for Terraform stacks* (el patrón nativo de HCP que adapta esta arquitectura): `https://mattias.engineer/blog/2026/terraform-stacks-pattern/`

**Nota sobre las fuentes.** Las afirmaciones comparativas sobre Terramate frente a otros orquestadores que circulan públicamente son en su mayoría publicadas por proveedores. La semántica técnica de los bloques documentada más arriba proviene de la propia documentación de referencia de Terramate y debería reverificarse contra la versión exacta del CLI que fijes, particularmente para la superficie experimental de outputs sharing.
