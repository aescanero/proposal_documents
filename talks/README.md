# Talks · Charlas

*English below · [Español](#español)*

One-hour talks as self-contained HTML slide decks. Each file works offline: open it in a browser, nothing is loaded from the network. The decks are **English only** and are **not** part of the specification. Where they describe this platform, `docs/` is authoritative, and the decks cite its sections.

| # | Deck | Slides | About |
|---|---|---|---|
| 1 | [`01-gitops-and-shim.html`](01-gitops-and-shim.html) | 44 | GitOps and source-hydrated infrastructure models (SHIM): principles, the hydration gap, gates, trade-offs, adoption |
| 2 | [`02-platform-as-shim.html`](02-platform-as-shim.html) | 42 | This platform as a source-hydrated model: intent, resolver and generators, `_rendered/`, gates G0–G3, push delivery |
| 3 | [`03-agent-platforms-evolution.html`](03-agent-platforms-evolution.html) | 45 | From prompts to agent platforms, vendor-agnostic: history, protocols (MCP, A2A), standards, reference architecture. Status as of October 2026 |
| 4 | *planned* | | Agnostic monitoring of agents and models |
| 5 | *planned* | | Agent memory models |

## Presenting

| Key | Action |
|---|---|
| `→` `Space` `PgDn` / `←` `PgUp` | Next / previous slide (`Home`, `End` also work) |
| `N` | Presenter window: speaker notes, next slide, timer |
| `O` or `Esc` | Overview grid; click a slide to jump to it |
| `F` | Fullscreen |
| `P` | Print. Choose *Save as PDF*: one slide per page, 16:9 |

The URL hash is the slide number (`…/01-gitops-and-shim.html#12`), and `?print` opens the print dialog directly. Speaker notes live in each slide's `<aside class="notes">`, with timing hints per section.

## Editing

Each deck carries its own copy of the slide engine (CSS and JS) inline, so it can be sent as a single file. Slides are `<section class="slide">` elements. Diagrams are inline SVG that use the theme's CSS variables. A change to the engine is made in all three files.

Talk 3 records the state of the field in October 2026. Re-check its protocol and governance slides before each delivery.

---

## Español

Charlas de una hora como presentaciones HTML autocontenidas. Cada fichero funciona sin conexión: se abre en el navegador y no carga nada de la red. Las presentaciones están **solo en inglés** y **no** forman parte de la especificación. Donde describen esta plataforma, la referencia es `docs/`, y las presentaciones citan sus secciones.

| # | Presentación | Diapositivas | Tema |
|---|---|---|---|
| 1 | [`01-gitops-and-shim.html`](01-gitops-and-shim.html) | 44 | GitOps y modelos de infraestructura hidratados en la fuente (SHIM): principios, el hueco de la hidratación, puertas, compromisos, adopción |
| 2 | [`02-platform-as-shim.html`](02-platform-as-shim.html) | 42 | Esta plataforma como modelo hidratado en la fuente: intención, resolver y generadores, `_rendered/`, puertas G0–G3, entrega push |
| 3 | [`03-agent-platforms-evolution.html`](03-agent-platforms-evolution.html) | 45 | De los prompts a las plataformas de agentes, agnóstica: historia, protocolos (MCP, A2A), estándares, arquitectura de referencia. Estado a octubre de 2026 |
| 4 | *prevista* | | Monitorización agnóstica de agentes y modelos |
| 5 | *prevista* | | Modelos de memoria de agentes |

Teclas: `→`/`←` para avanzar y retroceder; `N` abre la ventana del ponente (notas, siguiente diapositiva, cronómetro); `O` muestra la vista general; `F` pasa a pantalla completa; `P` imprime (*Guardar como PDF*: una diapositiva por página). El motor de diapositivas va copiado dentro de cada fichero, así que un cambio en el motor se hace en los tres. Las diapositivas de protocolos y gobernanza de la charla 3 se revisan antes de cada exposición.
