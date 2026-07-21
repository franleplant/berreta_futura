from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import subprocess

import yaml

from magazine.manifest import _edition_copy_sha256, load_edition
from magazine.media_schema import caption_sha256
from magazine.records import load_records


ROOT = Path(__file__).resolve().parents[1]
EDITION = ROOT / "editions" / "002-unreleased"
ES = EDITION / "translations" / "es"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def manuscript(source_id: str, label: str, body: str) -> str:
    return f"""---
source_id: {source_id}
content_mode: faithful_synthesis
label: {label}
---

{body}
"""


def visible_blocks(body: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for chunk in body.strip().split("\n\n"):
        line = " ".join(chunk.split())
        if line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("- "):
            blocks.append(("bullet", line[2:]))
        else:
            blocks.append(("p", line))
    return blocks


def fidelity(source_id: str, author: str, body: str, source_passages: list[str]) -> dict:
    blocks = visible_blocks(body)
    if len(blocks) != len(source_passages):
        raise ValueError(f"fidelity mismatch for {source_id}: {len(blocks)} != {len(source_passages)}")
    rows = []
    for index, ((kind, edited), source) in enumerate(zip(blocks, source_passages), 1):
        rows.append({
            "id": f"synthesis-{index:03d}",
            "kind": kind,
            "status": "modified",
            "source": source,
            "edited": edited,
        })
    return {
        "schema_version": 1,
        "source_ids": [source_id],
        "source_author": author,
        "content_mode": "faithful_synthesis",
        "source_body_sha256": hashlib.sha256("\n\n".join(source_passages).encode()).hexdigest(),
        "paragraphs": rows,
    }


ARTICLES = [
    {
        "id": "software-factories-light-and-dark",
        "source_id": "software-factories-light-and-dark-ef463732",
        "title": "Software Factories, Light and Dark",
        "short_title": "Light and Dark",
        "emphasis": "Factories",
        "author": "Addy Osmani",
        "note": "Addy Osmani writes about engineering systems, developer experience, and AI-assisted software.",
        "es_title": "Fábricas de software, con luz y a oscuras",
        "es_short": "con luz y a oscuras",
        "es_emphasis": "Fábricas",
        "es_note": "Addy Osmani escribe sobre sistemas de ingeniería, experiencia de desarrollo y software asistido por IA.",
        "body": """A software factory is harnessed loops at scale. Run the loop with humans in it—a light factory—and you trade judgment and concentration against speed and breakage. Ignore the humans—a dark factory—and agents can scope, build, and ship code without anyone reading the details. If people stop reading, however, they stop understanding the software. The hardest job becomes deciding which checks to build and how much autonomy to delegate.

## Loop, harness, factory

A loop is one agent doing one job repeatedly: gather context, act, check the result, and continue until a condition is met. A harness supplies the walls around it—the sandbox, tools, durable memory, and gates that define done. A factory is many harnessed loops drawing from a queue and flowing through a review gate into production. It is not a bigger agent; it is an org chart made of loops.

The factory closes its own circuit. Intent and production signals feed the queue; the harness builds; tests, static analysis, and scanning check the work; approval permits deployment; monitoring turns production back into signals. Almost every box can run cheaply at scale. The stubbornly expensive box is the review gate: judgment.

## The narrow neck

A dark factory removes that gate. Its apparent throughput rises dramatically because code ships after machine verification alone. Yet it also accumulates comprehension debt: the gap between how much code exists and how much any person understands. In a mature system, the reckoning is likely to be quiet and late, after months of green tests and unread changes.

Generation is a wide mouth; verification is the narrow neck. Back pressure means giving a loop only as much autonomy as can be cheaply and reliably verified. A better model does not automatically solve the problem, because architectural quality reveals itself over months and years rather than in the crisp seconds of a test result.

## Turning the lights on where judgment lives

A lit factory keeps agents doing most of the building but moves human judgment upstream into product, design, and architecture as well as review. An hour spent reviewing a two-hundred-line plan can prevent a painful review of two thousand generated lines. Types, test seams, legible boundaries, short call stacks, and dependency injection become a hard-to-fake safety net outside the model.

Some small loops can earn the dark: the check is cheap, frequent, immediate, stable, and difficult to game. A nightly job that fixes one lint violation and opens one small pull request may qualify. Authentication, billing, public contracts, and long-lived architectural decisions do not. All dark produces a system no one can repair; all lit produces a review bottleneck. The skilled work is placing each switch.

The person never left the factory; the person moved to the outer loop. Agents can investigate, implement, test, and report. Engineers still decide whether the approach is right, inspect the evidence at the boundary, approve the change, and carry the consequences of being wrong. Robots can operate in the dark. Humans need to see what they are responsible for.""",
        "es_body": """Una fábrica de software consiste en ciclos con arnés ejecutados a escala. Si el ciclo incluye personas —una fábrica con luz—, se intercambian criterio y concentración por velocidad y riesgo de rotura. Si se ignora a las personas —una fábrica a oscuras—, los agentes pueden delimitar, construir y desplegar código sin que nadie lea los detalles. Pero si las personas dejan de leer, dejan de comprender el software. El trabajo más difícil pasa a ser decidir qué controles construir y cuánta autonomía delegar.

## Ciclo, arnés, fábrica

Un ciclo es un agente que repite una tarea: reúne contexto, actúa, comprueba el resultado y continúa hasta cumplir una condición. El arnés aporta las paredes: entorno aislado, herramientas, memoria persistente y puertas que definen qué significa terminar. Una fábrica reúne muchos ciclos con arnés, alimentados por una cola y conducidos hacia producción a través de una puerta de revisión. No es un agente más grande; es un organigrama hecho de ciclos.

La fábrica cierra su propio circuito. La intención y las señales de producción alimentan la cola; el arnés construye; las pruebas, el análisis estático y los escáneres comprueban; la aprobación permite desplegar; la observabilidad convierte producción en nuevas señales. Casi todas las casillas funcionan a escala con poco coste. La casilla obstinadamente cara es la puerta de revisión: el criterio.

## El cuello estrecho

Una fábrica a oscuras elimina esa puerta. Su rendimiento aparente aumenta porque el código se despliega tras una verificación exclusivamente mecánica. Pero también acumula deuda de comprensión: la distancia entre cuánto código existe y cuánto entiende una persona. En un sistema maduro, el ajuste de cuentas probablemente sea silencioso y tardío, después de meses de pruebas verdes y cambios sin leer.

La generación es una boca ancha; la verificación, un cuello estrecho. La contrapresión exige dar a un ciclo solo la autonomía que pueda verificarse de forma barata y fiable. Un modelo mejor no resuelve automáticamente el problema, porque la calidad arquitectónica se revela en meses y años, no en los segundos nítidos de una prueba.

## Encender la luz donde vive el criterio

Una fábrica con luz deja que los agentes hagan la mayor parte de la construcción, pero traslada el criterio humano hacia producto, diseño y arquitectura, además de la revisión. Una hora para revisar un plan de doscientas líneas puede evitar una revisión dolorosa de dos mil líneas generadas. Tipos, puntos de prueba, límites legibles, pilas cortas e inyección de dependencias forman una red de seguridad externa al modelo y difícil de falsear.

Algunos ciclos pequeños pueden ganarse la oscuridad: el control es barato, frecuente, inmediato, estable y difícil de engañar. Una tarea nocturna que corrige una infracción de lint y abre una solicitud de cambios pequeña puede cumplir esas condiciones. Autenticación, facturación, contratos públicos y decisiones arquitectónicas duraderas, no. Todo a oscuras produce un sistema que nadie puede reparar; todo con luz produce un atasco de revisiones. El trabajo cualificado consiste en colocar cada interruptor.

La persona nunca abandonó la fábrica: pasó al ciclo exterior. Los agentes pueden investigar, implementar, probar e informar. Los ingenieros todavía deciden si el enfoque es correcto, inspeccionan la evidencia en la frontera, aprueban el cambio y cargan con las consecuencias de equivocarse. Los robots pueden trabajar a oscuras. Las personas necesitan ver aquello de lo que son responsables.""",
    },
    {
        "id": "the-building-block-economy",
        "source_id": "the-building-block-economy-af6644bd",
        "title": "The Building Block Economy",
        "short_title": "Building Block",
        "emphasis": "Building",
        "author": "Mitchell Hashimoto",
        "note": "Mitchell Hashimoto is the creator of Ghostty and co-founder of HashiCorp.",
        "es_title": "La economía de los bloques de construcción",
        "es_short": "Bloques de construcción",
        "es_emphasis": "Bloques",
        "es_note": "Mitchell Hashimoto es creador de Ghostty y cofundador de HashiCorp.",
        "body": """The most effective way to build software—and to drive adoption—has shifted toward creating building blocks that enable quantity. Ghostty spent roughly eighteen months reaching a million daily update checks. Its embeddable library, libghostty, reached several million daily checks in about two months. I now spend much of my time making Ghostty easier to embed because downstream software factories multiply those blocks faster than I ever could alone.

## Imports are up

Software factories are extremely good at gluing proven, documented components together. Importing once required a person to discover a library, understand it, and judge whether the integration effort was worthwhile. Agents erase much of that human barrier, so they reach deeper into dependency graphs and use smaller, more specialized packages.

That changes the value of a clean interface. A reusable block no longer needs a huge audience of people who happen to know it exists; it needs to be legible to machines that are continuously searching for capabilities. Documentation, stable APIs, and composability become distribution.

## Exports are up

The growth has real costs: security exposure, instability, and software whose operators may not understand its internals. But four forces also make exporting blocks more attractive. The quality bar for a useful component is lower, awareness is greater, maintenance is cheaper when agents can help, and downstream users effectively outsource research and development by discovering new uses and fixes.

This encourages purposeful libraries and forks. A feature that would make the main application brittle can live in an embeddable layer or a downstream project. The parent project can remain stable while a broader community explores the design space around it.

## Commercial tension

The unresolved question is commercialization. Closed, paid software is harder for agents to discover, inspect, and compose than open, free building blocks. That creates a genuine disadvantage for conventional product boundaries. I do not have a concrete answer, and false certainty would be less useful than admitting the problem.

The shift has already happened. Building blocks and software factories now reinforce each other: more reusable parts make factories stronger, and more factories increase the value of reusable parts. Resisting the change does not restore the old economics. The practical task is learning how to build stable, understandable foundations inside the new one.""",
        "es_body": """La forma más eficaz de construir software —y de impulsar su adopción— se ha desplazado hacia la creación de bloques que permiten multiplicar la cantidad. Ghostty tardó unos dieciocho meses en alcanzar un millón de comprobaciones diarias de actualizaciones. Su biblioteca integrable, libghostty, llegó a varios millones en unos dos meses. Ahora dedico buena parte de mi tiempo a facilitar la integración de Ghostty, porque las fábricas de software posteriores multiplican esos bloques más deprisa de lo que yo podría hacerlo solo.

## Aumentan las importaciones

Las fábricas de software son extraordinariamente buenas para unir componentes probados y documentados. Antes, importar exigía que una persona descubriera una biblioteca, la comprendiera y evaluara si valía la pena integrarla. Los agentes eliminan buena parte de esa barrera humana, así que penetran más en los grafos de dependencias y emplean paquetes más pequeños y especializados.

Eso cambia el valor de una interfaz limpia. Un bloque reutilizable ya no necesita un público enorme de personas que sepan que existe; necesita ser legible para máquinas que buscan capacidades continuamente. La documentación, las API estables y la capacidad de composición se convierten en distribución.

## Aumentan las exportaciones

El crecimiento tiene costes reales: exposición de seguridad, inestabilidad y software cuyos operadores quizá no entiendan sus entrañas. Pero cuatro fuerzas también hacen más atractiva la exportación de bloques. El umbral de calidad de un componente útil es menor, su visibilidad es mayor, el mantenimiento resulta más barato con ayuda de agentes y los usuarios posteriores externalizan investigación y desarrollo al descubrir usos y correcciones.

Esto favorece bibliotecas y bifurcaciones deliberadas. Una función que volvería frágil la aplicación principal puede vivir en una capa integrable o en un proyecto posterior. El proyecto matriz conserva la estabilidad mientras una comunidad más amplia explora el espacio de diseño que lo rodea.

## Tensión comercial

La pregunta sin resolver es la comercialización. El software cerrado y de pago resulta más difícil de descubrir, inspeccionar y componer para los agentes que los bloques abiertos y gratuitos. Eso crea una desventaja genuina para los límites convencionales de producto. No tengo una respuesta concreta, y fingir certeza sería menos útil que admitir el problema.

El cambio ya ocurrió. Los bloques y las fábricas de software se refuerzan mutuamente: más piezas reutilizables fortalecen las fábricas y más fábricas aumentan el valor de las piezas. Resistirse no restaura la economía anterior. La tarea práctica es aprender a construir cimientos estables y comprensibles dentro de la nueva.""",
    },
    {
        "id": "agent-swarms-and-model-economics",
        "source_id": "agent-swarms-and-the-new-model-economics-8b346f57",
        "title": "Agent Swarms and the New Model Economics",
        "short_title": "Agent Swarms",
        "emphasis": "Swarms",
        "author": "Cursor",
        "note": "Cursor reports experiments in scaling coding-agent swarms and their economics.",
        "es_title": "Enjambres de agentes y la nueva economía de los modelos",
        "es_short": "Enjambres de agentes",
        "es_emphasis": "Enjambres",
        "es_note": "Cursor presenta experimentos para escalar enjambres de agentes de programación y su economía.",
        "body": """We have been experimenting with how far coding-agent swarms can scale. A new harness, built from the SQLite documentation, outperformed our earlier approach in every model configuration. The striking result was not simply that more agents helped. It was that topology, memory, version control, and the division between planning and execution changed both quality and cost.

## Trees preserve context

Our swarm forms a tree. A capable planner splits work and delegates it; cheaper workers execute focused tasks. The planner never implements and the worker never plans. This separation is valuable less for parallel speed than for context efficiency: each agent sees the memory required for its role instead of carrying the entire project until it drifts.

Coordination required infrastructure. The old browser experiment produced around a thousand commits an hour; the SQLite experiment could approach a thousand a second, so we built a custom version-control layer. Shared design documents, compile references, neutral reconcilers, megafile limits, and controlled breakage reduced split-brain designs and merge thrash. Multiple decorrelated review lenses were cheap and delivered unusually high returns.

## A manual as the world

For SQLite, agents received an 835-page manual but no source code, tests, binary, or internet access. We evaluated them against millions of sqllogictest cases, with a held-out set protecting the final result. Four planner/worker configurations reached between 73 and 85 percent after four hours in the new harness and later reached 100 percent; the old harness ranged from 11 to 77 percent at the same checkpoint.

The traces explain the difference. The old system made tens of thousands of early commits yet thrashed through roughly seventy thousand conflicts, spawned overlapping SQL implementations, and grew far more code. The new system made fewer, more coherent changes. One successful run reached full correctness in 4,645 lines where an older run used 19,013 lines for 97 percent.

## Models are roles, not a single bill

Costs ranged from roughly $1,339 for an Opus-planner hybrid to $10,565 for an all-GPT-5.5 configuration. Workers consumed at least 69 percent of tokens and more than 90 percent in most runs. Frontier reasoning mattered at a few planning moments, while the bulk of execution could use cheaper models. In one comparison, GPT-5.5 workers cost $9,373 and Composer workers $411.

The implication is architectural and economic: select models by role. A planner's extra judgment can be worth its price because it shapes thousands of cheaper actions. A nominally inexpensive planner can still raise the total bill if its decomposition causes workers to consume far more tokens.

## Specs become prompts

As agents improve, the unit given to a model rises from line, to block, to file, feature, and eventually specification. A swarm begins to resemble a probabilistic compiler: intent becomes tasks, tasks become coordinated work, and verification closes the semantic gap. The scarce input is not code generation. It is precise intent, supported by an environment that lets many agents preserve it.""",
        "es_body": """Hemos estado experimentando hasta dónde pueden escalar los enjambres de agentes de programación. Un arnés nuevo, construido a partir de la documentación de SQLite, superó nuestro enfoque anterior con todas las configuraciones de modelos. El resultado llamativo no fue solo que ayudaran más agentes. La topología, la memoria, el control de versiones y la separación entre planificación y ejecución cambiaron tanto la calidad como el coste.

## Los árboles preservan el contexto

Nuestro enjambre forma un árbol. Un planificador capaz divide el trabajo y lo delega; trabajadores más baratos ejecutan tareas acotadas. El planificador nunca implementa y el trabajador nunca planifica. Esta separación importa menos por la velocidad paralela que por la eficiencia de contexto: cada agente ve la memoria necesaria para su función, en vez de arrastrar todo el proyecto hasta perder el rumbo.

La coordinación exigió infraestructura. El experimento anterior con un navegador producía alrededor de mil commits por hora; el de SQLite podía acercarse a mil por segundo, así que construimos una capa propia de control de versiones. Documentos de diseño compartidos, referencias de compilación, reconciliadores neutrales, límites a archivos gigantes y roturas controladas redujeron los diseños divergentes y los conflictos. Varias revisiones independientes costaron poco y ofrecieron un rendimiento inusual.

## Un manual como mundo

Para SQLite, los agentes recibieron un manual de 835 páginas, pero no el código fuente, las pruebas, el binario ni acceso a internet. Los evaluamos contra millones de casos de sqllogictest y reservamos un conjunto para proteger el resultado final. Cuatro configuraciones de planificador y trabajadores alcanzaron entre el 73 y el 85 por ciento tras cuatro horas con el arnés nuevo y más tarde llegaron al 100 por ciento; el arnés anterior osciló entre el 11 y el 77 por ciento en el mismo punto.

Las trazas explican la diferencia. El sistema anterior hizo decenas de miles de commits tempranos, pero atravesó unos setenta mil conflictos, creó implementaciones SQL solapadas y acumuló mucho más código. El nuevo hizo menos cambios y más coherentes. Una ejecución correcta llegó al cien por cien con 4.645 líneas, mientras otra anterior necesitó 19.013 para alcanzar el 97 por ciento.

## Los modelos son funciones, no una única factura

Los costes fueron desde unos 1.339 dólares para un híbrido con Opus como planificador hasta 10.565 para una configuración íntegra con GPT-5.5. Los trabajadores consumieron al menos el 69 por ciento de los tokens y más del 90 por ciento en la mayoría de las ejecuciones. El razonamiento de frontera importó en algunos momentos de planificación; el grueso de la ejecución pudo usar modelos más baratos. En una comparación, los trabajadores GPT-5.5 costaron 9.373 dólares y los Composer, 411.

La consecuencia es arquitectónica y económica: hay que elegir modelos por función. El criterio adicional de un planificador puede justificar su precio porque da forma a miles de acciones más baratas. Un planificador nominalmente económico todavía puede elevar la factura total si su descomposición obliga a los trabajadores a consumir muchos más tokens.

## Las especificaciones se vuelven prompts

A medida que mejoran los agentes, la unidad entregada al modelo asciende de línea a bloque, archivo, función y finalmente especificación. Un enjambre empieza a parecerse a un compilador probabilístico: la intención se convierte en tareas, las tareas en trabajo coordinado y la verificación cierra la distancia semántica. El insumo escaso no es la generación de código. Es una intención precisa sostenida por un entorno que permita conservarla entre muchos agentes.""",
    },
    {
        "id": "loop-engineering-roadmap",
        "source_id": "loop-engineering-the-14-step-roadmap-from-prompt-76a8ae0f",
        "title": "Loop Engineering: A Roadmap Beyond the Prompt",
        "short_title": "Loop Engineering",
        "emphasis": "Loop",
        "author": "Codez",
        "note": "Codez maps a practical progression from manual prompting to verified, scheduled agent loops.",
        "es_title": "Ingeniería de ciclos: una hoja de ruta más allá del prompt",
        "es_short": "Ingeniería de ciclos",
        "es_emphasis": "Ciclos",
        "es_note": "Codez traza una progresión práctica desde los prompts manuales hasta ciclos de agentes verificados y programados.",
        "body": """Most developers still prompt an agent by hand, inspect the answer, and decide what to do next. Loop engineering starts when the system finds work, hands it to an agent, checks the result, records state, and chooses the next step. The upgrade is not a cleverer prompt. It is automation, state, a verifier, and a schedule.

## Decide whether a loop belongs

A useful candidate repeats, has an objective completion gate, fits a token or cost budget, and can give the agent senior-engineer tools: code, logs, a reproducible failure, and a command to run. Before automating, ask whether it happens weekly, whether a machine can prove success, whether the agent can execute the work, whether there is a hard stop, and whether a person remains before irreversible action.

CI triage, dependency maintenance, lint cleanup, flaky-test investigation, and issue drafting often fit. Architecture, authentication, payments, deployment, and vague product work usually do not. The economics favor repetitive, machine-checkable, asynchronous work; judgment-heavy tasks remain better as deliberate prompts.

## Five building blocks

Automations provide the heartbeat, either on a cadence or until a goal is met. Worktrees isolate concurrent attempts. Skills preserve reusable operating knowledge. Connectors bring the loop into the systems where work lives. Sub-agents separate making from checking so the same context is not asked to invent and certify its own answer.

A small state file prevents amnesia across runs: current goal, completed work, failed approaches, next action, and hard constraints. The minimum viable loop can be humble—select one bounded task, execute it in isolation, run one decisive verifier, record the result, and stop or continue according to an explicit rule.

## Verification is the product

The quiet failure is a loop that keeps producing plausible work while its notion of success drifts. Tests, type checks, linters, reproducible benchmarks, and human approval at high-risk boundaries turn motion into progress. The schedule is not the automation; the verifier is.

Autonomy also creates comprehension debt. Read diffs, sample the evidence behind green gates, keep agents away from unilateral architecture, and pair with them on design. Security adds another tax: generated code, hostile instructions hidden in skills or retrieved content, credentials in logs, and gradually expanding permissions. Use sandboxes, allowlists, scoped secrets, audit trails, budgets, and human gates for irreversible operations.

Most teams do not need a grand autonomous factory. Start with one reliable manual procedure. Turn it into a reusable skill, then a bounded loop, then a scheduled automation. Add one state file and one objective gate. Keep the progression legible enough that automation amplifies engineering rather than replacing it.""",
        "es_body": """La mayoría de los desarrolladores todavía escribe un prompt a mano, inspecciona la respuesta y decide qué hacer después. La ingeniería de ciclos comienza cuando el sistema encuentra trabajo, se lo entrega a un agente, comprueba el resultado, registra el estado y elige el paso siguiente. La mejora no es un prompt más ingenioso. Es automatización, estado, un verificador y una cadencia.

## Decidir si corresponde un ciclo

Un buen candidato se repite, tiene una puerta objetiva de finalización, cabe en un presupuesto de tokens o coste y puede ofrecer al agente herramientas de ingeniería sénior: código, registros, un fallo reproducible y un comando que ejecutar. Antes de automatizar, hay que preguntar si ocurre cada semana, si una máquina puede demostrar el éxito, si el agente puede ejecutar el trabajo, si existe un límite estricto y si una persona interviene antes de una acción irreversible.

El triaje de CI, el mantenimiento de dependencias, la limpieza de lint, la investigación de pruebas inestables y los borradores de incidencias suelen encajar. Arquitectura, autenticación, pagos, despliegues y producto ambiguo, normalmente no. La economía favorece trabajo repetitivo, verificable por máquinas y asíncrono; las tareas cargadas de criterio siguen funcionando mejor como prompts deliberados.

## Cinco bloques

Las automatizaciones aportan el latido, según una cadencia o hasta cumplir un objetivo. Los worktrees aíslan intentos concurrentes. Las skills conservan conocimiento operativo reutilizable. Los conectores llevan el ciclo a los sistemas donde vive el trabajo. Los subagentes separan creación y comprobación, para no pedir al mismo contexto que invente y certifique su propia respuesta.

Un pequeño archivo de estado evita la amnesia entre ejecuciones: objetivo actual, trabajo terminado, enfoques fallidos, próxima acción y restricciones duras. El ciclo mínimo viable puede ser modesto: seleccionar una tarea acotada, ejecutarla de forma aislada, aplicar un verificador decisivo, registrar el resultado y detenerse o continuar según una regla explícita.

## La verificación es el producto

El fallo silencioso aparece cuando un ciclo sigue produciendo trabajo plausible mientras deriva su idea del éxito. Pruebas, comprobaciones de tipos, linters, benchmarks reproducibles y aprobación humana en fronteras de riesgo convierten el movimiento en progreso. La cadencia no es la automatización; lo es el verificador.

La autonomía también crea deuda de comprensión. Hay que leer diffs, muestrear la evidencia detrás de las puertas verdes, impedir que los agentes decidan solos la arquitectura y diseñar con ellos. La seguridad añade otro impuesto: código generado, instrucciones hostiles ocultas en skills o contenido recuperado, credenciales en registros y permisos que crecen poco a poco. Convienen entornos aislados, listas permitidas, secretos acotados, auditoría, presupuestos y puertas humanas para operaciones irreversibles.

La mayoría de los equipos no necesita una gran fábrica autónoma. Se empieza con un procedimiento manual fiable. Después se convierte en una skill reutilizable, luego en un ciclo acotado y finalmente en una automatización programada. Basta añadir un archivo de estado y una puerta objetiva. La progresión debe seguir siendo legible para que la automatización amplifique la ingeniería en vez de sustituirla.""",
    },
    {
        "id": "agentic-pods",
        "source_id": "agentic-pods-taking-ai-beyond-engineering-at-ube-5b9382d4",
        "title": "Agentic Pods: Taking AI Beyond Engineering",
        "short_title": "Agentic Pods",
        "emphasis": "Pods",
        "author": "Praveen Neppalli",
        "note": "Praveen Neppalli describes Uber's two-week method for redesigning business workflows with AI.",
        "es_title": "Pods de agentes: llevar la IA más allá de ingeniería",
        "es_short": "Pods de agentes",
        "es_emphasis": "Pods",
        "es_note": "Praveen Neppalli describe el método de dos semanas de Uber para rediseñar flujos de negocio con IA.",
        "body": """Agentic AI adoption at Uber has changed how we build. Ninety-nine percent of our engineers use AI tools, more than 70 percent of pull requests are attributed to local or cloud agents, and engineers have built more than 2,500 agent skills across the development lifecycle. Those numbers raised a larger question: how do we bring agentic AI beyond engineering?

## Pair system knowledge with domain knowledge

Finance, legal, operations, marketing, support, HR, and procurement depend on nuanced workflows spread across many systems. Process diagrams do not show how that work actually happens. We created Agentic Pods by pairing about thirty AI-proficient engineers, each with deep knowledge of Uber's systems, with domain experts from business functions.

Each pod gets two weeks. On days one and two, the engineer shadows the expert, documents every step, asks questions, and builds intuition. Day three prioritizes opportunities by scale, repetition, business impact, and data availability. Days four and five produce a working agent beside the person doing the job. Days six through nine test whether it generalizes with other practitioners. Day ten ships.

## The workflow is the unit

In two months, sixteen pods worked across sixteen business functions. Capital allocation across 150 cities fell from fifteen hours to thirty minutes. Financial pacing reports went from two days to ten minutes. Marketing web quality assurance went from two weeks to fifty minutes. Support moved from nine thousand manually created workflows toward self-service automation.

The biggest surprise was not speed. Engineers embedded in unfamiliar domains found opportunities hidden in plain sight. The strongest gains rarely came from automating one task; they came from redesigning a workflow around AI, eliminating handoffs and unnecessary approvals, replacing legacy tooling, reducing vendor spend, and accelerating decisions.

The workflow becomes the unit of automation, not the individual task. The most valuable agent skills cross teams, organizations, functions, tools, and systems. Those opportunities are rarely visible from outside. They appear when we sit beside the people doing the work, understand each friction point, and build with them rather than for them.

We are forming a dedicated team to scale the approach. Its job is to understand work deeply, redesign it from the ground up, and use AI to change how the business operates—not merely to bolt an agent onto the process that already exists.""",
        "es_body": """La adopción de IA agéntica en Uber ha cambiado nuestra forma de construir. El 99 por ciento de nuestros ingenieros usa herramientas de IA, más del 70 por ciento de las solicitudes de cambios se atribuye a agentes locales o en la nube y los ingenieros han creado más de 2.500 skills de agentes a lo largo del ciclo de desarrollo. Esas cifras plantearon una pregunta mayor: ¿cómo llevamos la IA agéntica más allá de ingeniería?

## Unir conocimiento del sistema y del dominio

Finanzas, legal, operaciones, marketing, soporte, RR. HH. y compras dependen de flujos matizados y repartidos entre muchos sistemas. Los diagramas de proceso no muestran cómo ocurre realmente el trabajo. Creamos los Agentic Pods emparejando a unos treinta ingenieros muy competentes en IA y conocedores de los sistemas de Uber con expertos de distintas funciones de negocio.

Cada pod dispone de dos semanas. Los días uno y dos, el ingeniero acompaña al experto, documenta cada paso, pregunta y desarrolla intuición. El día tres prioriza oportunidades por escala, repetición, impacto y disponibilidad de datos. Los días cuatro y cinco construye un agente junto a quien realiza el trabajo. Del sexto al noveno comprueba con otros profesionales si el resultado se generaliza. El décimo día se despliega.

## El flujo es la unidad

En dos meses, dieciséis pods trabajaron en dieciséis funciones. La asignación de capital en 150 ciudades bajó de quince horas a treinta minutos. Los informes de ritmo financiero, de dos días a diez minutos. El control de calidad web de marketing, de dos semanas a cincuenta minutos. Soporte pasó de nueve mil flujos creados manualmente hacia una automatización de autoservicio.

La mayor sorpresa no fue la velocidad. Ingenieros inmersos en dominios desconocidos encontraron oportunidades ocultas a plena vista. Las mejores mejoras rara vez surgieron de automatizar una tarea; aparecieron al rediseñar un flujo alrededor de la IA, eliminar traspasos y aprobaciones innecesarias, sustituir herramientas heredadas, reducir gasto en proveedores y acelerar decisiones.

El flujo se convierte en la unidad de automatización, no la tarea individual. Las skills más valiosas atraviesan equipos, organizaciones, funciones, herramientas y sistemas. Esas oportunidades rara vez se ven desde fuera. Aparecen cuando nos sentamos junto a quienes hacen el trabajo, comprendemos cada punto de fricción y construimos con ellos, no para ellos.

Estamos formando un equipo dedicado a escalar el enfoque. Su trabajo será comprender profundamente las tareas, rediseñarlas desde cero y usar IA para cambiar cómo opera el negocio, no limitarse a añadir un agente al proceso existente.""",
    },
]


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has", "have",
    "in", "into", "is", "it", "its", "not", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "we", "when", "with", "you",
}


def tokens(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9][a-z0-9'-]+", text.casefold())
        if len(word) > 2 and word not in STOPWORDS
    }


def source_text(source_id: str) -> tuple[str, str]:
    raw = ROOT / "library" / "sources" / source_id / "raw"
    text_files = sorted(raw.glob("*/artifacts/authenticated-x-*.txt"))
    if text_files:
        path = text_files[0]
        return path.read_text(encoding="utf-8"), hashlib.sha256(path.read_bytes()).hexdigest()
    pdf_files = sorted(raw.glob("*/artifacts/primary-article.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No article evidence found for {source_id}")
    path = pdf_files[0]
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout, hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    for paragraph in re.split(r"\n\s*\n", raw):
        cleaned = " ".join(paragraph.split())
        if len(cleaned.split()) >= 4:
            candidates.append(cleaned)
    for line in raw.splitlines():
        cleaned = line.strip()
        match = re.match(r"- (?:generic|heading \".*?\" \[level=\d+\]):\s*(.*)", cleaned)
        if match:
            value = match.group(1).strip().strip('"')
            if len(value.split()) >= 3:
                candidates.append(value)
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def map_source_passages(body: str, raw: str) -> list[str]:
    candidates = evidence_candidates(raw)
    if not candidates:
        raise ValueError("Source evidence did not yield any candidate passages")
    passages: list[str] = []
    for _, edited in visible_blocks(body):
        wanted = tokens(edited)
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                len(wanted & tokens(candidate)) / math.sqrt(max(1, len(tokens(candidate)))),
                len(wanted & tokens(candidate)),
            ),
            reverse=True,
        )
        selected: list[str] = []
        word_total = 0
        for candidate in ranked[:4]:
            selected.append(candidate)
            word_total += len(candidate.split())
            if word_total >= max(12, int(len(edited.split()) * 1.15)):
                break
        passages.append("\n\n".join(selected))
    return passages


def main() -> None:
    for article in ARTICLES:
        source_id = article["source_id"]
        write(
            EDITION / "articles" / f"{article['id']}.md",
            manuscript(source_id, "FAITHFUL SYNTHESIS", article["body"]),
        )
        write(
            ES / "articles" / f"{article['id']}.md",
            manuscript(source_id, "SÍNTESIS FIEL", article["es_body"]),
        )
        raw_source, raw_sha256 = source_text(source_id)
        ledger = fidelity(
            source_id,
            article["author"],
            article["body"],
            map_source_passages(article["body"], raw_source),
        )
        ledger["source_body_sha256"] = raw_sha256
        write(
            EDITION / "fidelity" / f"{article['id']}.yaml",
            yaml.safe_dump(ledger, sort_keys=False, allow_unicode=True, width=110),
        )

    editorial_en = """---
label: EDITORIAL — ORIGINAL EDITOR TEXT
title: The Expensive Box
byline: The Editors
---

The loop is small: context, action, check, repeat. The factory is what happens when that loop gains walls, memory, a queue, and neighbors. Edition 2 follows this movement upward—from a reusable library to a swarm, from one verified automation to an organization redesigning whole workflows.

Across these six accounts, generation becomes abundant before judgment does. Addy Osmani draws the factory as a closed circuit and points to its expensive box: the review gate. Cursor's experiments make the same constraint measurable. A thousand commits a second are not useful when coordination collapses. Topology, memory, and verification turn activity into progress.

The same pattern appears outside code. Mitchell Hashimoto sees agents multiplying clean building blocks. Praveen Neppalli pairs system experts with domain experts because workflow knowledge cannot be recovered from a process diagram. Codez insists that a schedule is not a loop's product; its verifier is. Cerebras leaves knowledge where work happens, then builds a visible path from question to evidence.

These are not arguments for putting a person into every inner loop. They are arguments for designing the outer loop deliberately. Human attention belongs where consequences are expensive, signals are ambiguous, and the cost of misunderstanding compounds. Everything else should earn autonomy through narrow scope and evidence that is cheap to inspect.

A good factory therefore does more than produce software. It preserves intent as work crosses boundaries. It keeps evidence attached to decisions. It makes failure legible. And it leaves enough light on that the people responsible for the system can still understand what they have built.
"""
    editorial_es = """---
label: EDITORIAL — TEXTO ORIGINAL DE LA REDACCIÓN
title: La casilla costosa
byline: La redacción
---

El ciclo es pequeño: contexto, acción, comprobación, repetición. La fábrica aparece cuando ese ciclo adquiere paredes, memoria, una cola y vecinos. La edición 2 sigue este ascenso: de una biblioteca reutilizable a un enjambre, de una automatización verificada a una organización que rediseña flujos completos.

En estos seis relatos, la generación se vuelve abundante antes que el criterio. Addy Osmani dibuja la fábrica como un circuito cerrado y señala su casilla costosa: la puerta de revisión. Los experimentos de Cursor vuelven medible la misma restricción. Mil commits por segundo no sirven cuando la coordinación colapsa. Topología, memoria y verificación convierten actividad en progreso.

El mismo patrón aparece fuera del código. Mitchell Hashimoto ve agentes que multiplican bloques limpios. Praveen Neppalli empareja expertos de sistemas con expertos de dominio porque el conocimiento de un flujo no puede recuperarse de un diagrama. Codez insiste en que una cadencia no es el producto de un ciclo; lo es su verificador. Cerebras deja el conocimiento donde ocurre el trabajo y construye un camino visible desde la pregunta hasta la evidencia.

No son argumentos para poner a una persona en cada ciclo interior. Son argumentos para diseñar deliberadamente el ciclo exterior. La atención humana pertenece donde las consecuencias son caras, las señales ambiguas y el coste de no comprender crece con el tiempo. Todo lo demás debe ganarse la autonomía mediante un alcance estrecho y evidencia barata de inspeccionar.

Una buena fábrica, por tanto, hace más que producir software. Preserva la intención al cruzar fronteras, mantiene la evidencia unida a las decisiones, vuelve legible el fallo y deja suficiente luz encendida para que las personas responsables todavía comprendan lo que han construido.
"""
    colophon_en = """Edition 2 is a private, provisional evaluation proof assembled from six submitted sources. Source articles are presented as labeled faithful syntheses or selected extracts, with source-mapped fidelity ledgers and durable raw evidence bundles in the project library.

The opening editorial is original editor text. Cover typography and all interior layout are generated by the magazine compiler; the cover illustration contains no baked-in lettering. English is the source edition. The Spanish edition uses educated castellano with restrained Argentine preferences and is pinned to exact English input hashes.

This proof is not released or press-ready. Public distribution remains blocked pending permission or another applicable rights basis; print readiness additionally requires a named printer profile and passing preflight.
"""
    colophon_es = """La edición 2 es una prueba privada y provisional de evaluación preparada a partir de seis fuentes enviadas. Los artículos se presentan como síntesis fieles o extractos seleccionados debidamente rotulados, con registros de fidelidad vinculados a la fuente y paquetes de evidencia duradera en la biblioteca del proyecto.

El editorial de apertura es texto original de la redacción. La tipografía de cubierta y toda la composición interior las genera el compilador; la ilustración de portada no contiene letras incrustadas. El inglés es la edición fuente. La versión española usa castellano culto con preferencias argentinas moderadas y está fijada a hashes exactos de los textos ingleses.

Esta prueba no está publicada ni lista para imprenta. La distribución pública sigue bloqueada hasta contar con permiso u otra base de derechos aplicable; la preparación para impresión exige además un perfil de imprenta identificado y una verificación previa satisfactoria.
"""
    write(EDITION / "manuscript" / "editorial.md", editorial_en)
    write(ES / "manuscript" / "editorial.md", editorial_es)
    write(EDITION / "manuscript" / "colophon.md", colophon_en)
    write(ES / "manuscript" / "colophon.md", colophon_es)

    base = yaml.safe_load((EDITION / "edition.yaml").read_text())
    cerebras = next(row for row in base["articles"] if row["id"] == "how-we-built-our-knowledge-base")
    article_rows = []
    variants = ["split_axis", "edge_medallion", "stepped_title", "split_axis", "edge_medallion"]
    for article, variant in zip(ARTICLES, variants):
        article_rows.append({
            "id": article["id"],
            "title": article["title"],
            "short_title": article["short_title"],
            "display_emphasis": article["emphasis"],
            "opener_variant": variant,
            "author": article["author"],
            "author_note": article["note"],
            "content_mode": "faithful_synthesis",
            "source_ids": [article["source_id"]],
            "manuscript": f"editions/002-unreleased/articles/{article['id']}.md",
            "fidelity": f"editions/002-unreleased/fidelity/{article['id']}.yaml",
        })
    cerebras["opener_variant"] = "stepped_title"
    base.update({
        "publication_date": "2026-07-21",
        "title": "The Systems That Build",
        "subtitle": "Software factories, agent swarms, reusable blocks, and the human judgment that keeps them coherent",
        "cover": {
            "headline": "The Systems That Build",
            "deck": "Six field reports on what happens when code, knowledge, and work become systems of loops",
            "back_text": "The loop is small. The factory is vast. Between them sits the difficult work: preserving intent, evidence, and human understanding.",
            "art_path": "art/cover-art-v3.png",
        },
        "sources": [a["source_id"] for a in ARTICLES] + ["how-we-built-our-knowledge-base-e986baa0"],
        "articles": article_rows + [cerebras],
    })
    write(EDITION / "edition.yaml", yaml.safe_dump(base, sort_keys=False, allow_unicode=True, width=110))

    records = load_records(ROOT / "library" / "sources")
    loaded = load_edition(
        ROOT,
        "002-unreleased",
        {record.id for record in records},
        source_records={record.id: record for record in records},
    )
    old_translation = yaml.safe_load((ES / "edition.yaml").read_text())
    cerebras_es = next(
        row for row in old_translation["articles"] if row["id"] == "how-we-built-our-knowledge-base"
    )
    translated_rows = []
    for article in ARTICLES:
        source_path = EDITION / "articles" / f"{article['id']}.md"
        translated_rows.append({
            "id": article["id"],
            "title": article["es_title"],
            "short_title": article["es_short"],
            "display_emphasis": article["es_emphasis"],
            "author_note": article["es_note"],
            "manuscript": f"articles/{article['id']}.md",
            "source_sha256": sha(source_path),
        })
    cerebras_source = EDITION / "articles" / "how-we-built-our-knowledge-base.md"
    cerebras_es["source_sha256"] = sha(cerebras_source)
    for figure, base_figure in zip(cerebras_es.get("figures", []), cerebras.get("figures", [])):
        figure["source_caption_sha256"] = caption_sha256(base_figure["id"], base_figure["caption"])
    translation = {
        "schema_version": 1,
        "language": "es",
        "source_language": "en",
        "locale": "es-AR",
        "fallback_locale": "es-ES",
        "base_copy_sha256": _edition_copy_sha256(loaded),
        "policy": old_translation["policy"],
        "title": "Los sistemas que construyen",
        "subtitle": "Fábricas de software, enjambres de agentes, bloques reutilizables y el criterio humano que los mantiene coherentes",
        "cover": {
            "headline": "Los sistemas que construyen",
            "deck": "Seis informes de campo sobre lo que ocurre cuando el código, el conocimiento y el trabajo se convierten en sistemas de ciclos",
            "back_text": "El ciclo es pequeño. La fábrica es inmensa. Entre ambos queda el trabajo difícil: preservar la intención, la evidencia y la comprensión humana.",
        },
        "editorial": {"path": "manuscript/editorial.md", "source_sha256": sha(EDITION / "manuscript" / "editorial.md")},
        "articles": translated_rows + [cerebras_es],
        "sections": [{
            "kind": "colophon",
            "title": "Colofón",
            "path": "manuscript/colophon.md",
            "source_sha256": sha(EDITION / "manuscript" / "colophon.md"),
        }],
    }
    write(ES / "edition.yaml", yaml.safe_dump(translation, sort_keys=False, allow_unicode=True, width=110))


if __name__ == "__main__":
    main()
