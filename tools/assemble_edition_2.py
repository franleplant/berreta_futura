from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import subprocess

import yaml

from magazine.manifest import _edition_copy_sha256, load_edition
from magazine.media_schema import caption_sha256, credit_sha256
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
        "note": "Addy Osmani spent 14 years leading engineering teams across Chrome, Gemini, and Google Cloud AI.",
        "es_title": "Fábricas de software, con luz y a oscuras",
        "es_short": "con luz y a oscuras",
        "es_emphasis": "Fábricas",
        "es_note": "Addy Osmani pasó 14 años liderando equipos de ingeniería de Chrome, Gemini y Google Cloud AI.",
        "figures": [
            {
                "id": "loop-harness-factory",
                "decision": "include",
                "source_id": "software-factories-light-and-dark-ef463732",
                "asset_id": "raster-003-c84acad9",
                "caption": "A loop becomes a harness when it gains sandbox, tools, memory, and gates; many harnesses become a factory when they converge on a human-owned review gate.",
                "alt_text": "Three panels show one agent loop becoming a harness and then a software factory with multiple harnesses, review, merge, and production.",
                "anchor": "Loop, harness, factory",
                "layout": "evidence_band_prose",
                "criteria": ["important", "useful"],
                "rationale": "The diagram compresses the article's core hierarchy into one legible progression.",
            },
            {
                "id": "factory-closed-loop",
                "decision": "include",
                "source_id": "software-factories-light-and-dark-ef463732",
                "asset_id": "raster-004-99565ac9",
                "caption": "The factory closes the circuit from intent to queue, harness, automated checks, review and deployment, then returns production signals to the work queue.",
                "alt_text": "A closed loop connects intent, queue, harness, automated checks, human review, deployment, monitoring, and operational signals.",
                "anchor": "The narrow neck",
                "layout": "evidence_band_prose",
                "criteria": ["important", "useful"],
                "rationale": "The review gate makes the article's central throughput constraint visible.",
            },
            {
                "id": "lights-on-factory",
                "decision": "include",
                "source_id": "software-factories-light-and-dark-ef463732",
                "asset_id": "raster-002-d955f82f",
                "caption": "A lights-on factory keeps humans at the review boundary while agents build and automated checks, deployment, monitoring, incidents, and user feedback complete the loop.",
                "alt_text": "A software factory flow from leadership and user signals through an agent, automated checks, human review, production, and monitoring.",
                "anchor": "Turning the lights on where judgment lives",
                "layout": "evidence_band",
                "criteria": ["important", "useful"],
                "rationale": "The source sketch shows how human judgment and automated feedback coexist in a lit factory.",
            },
        ],
        "es_figures": [
            {
                "id": "loop-harness-factory",
                "caption": "Un ciclo se convierte en arnés cuando incorpora entorno aislado, herramientas, memoria y puertas; varios arneses forman una fábrica al converger en una puerta de revisión bajo responsabilidad humana.",
                "credit": "Diagrama de Addy Osmani; fuente: Software Factories, Light and Dark.",
                "alt_text": "Tres paneles muestran cómo un ciclo de un agente se convierte en arnés y luego en una fábrica con varios arneses, revisión, integración y producción.",
                "anchor": "Ciclo, arnés, fábrica",
            },
            {
                "id": "factory-closed-loop",
                "caption": "La fábrica cierra el circuito desde la intención hasta la cola, el arnés, los controles automáticos, la revisión y el despliegue; después devuelve las señales de producción a la cola de trabajo.",
                "credit": "Diagrama de Addy Osmani; fuente: Software Factories, Light and Dark.",
                "alt_text": "Un circuito cerrado conecta intención, cola, arnés, controles automáticos, revisión humana, despliegue, observabilidad y señales operativas.",
                "anchor": "El cuello estrecho",
            },
            {
                "id": "lights-on-factory",
                "caption": "Una fábrica con luz mantiene a las personas en la frontera de revisión mientras los agentes construyen y los controles automáticos, el despliegue, la observabilidad, los incidentes y la respuesta de usuarios completan el ciclo.",
                "credit": "Diagrama de Addy Osmani; fuente: Software Factories, Light and Dark.",
                "alt_text": "Un flujo de fábrica de software va desde la dirección y las señales de usuarios hasta un agente, controles automáticos, revisión humana, producción y observabilidad.",
                "anchor": "Encender la luz donde vive el criterio",
            },
        ],
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
        "es_body": """Una fábrica de software consiste en ciclos con arnés a escala. Con personas dentro —una fábrica con luz— intercambia criterio y concentración por velocidad y riesgo. Sin ellas —una fábrica a oscuras— los agentes pueden delimitar, construir y desplegar código sin que nadie lea los detalles. Si las personas dejan de leer, dejan de comprender el software. Lo más difícil es decidir qué controles construir y cuánta autonomía delegar.

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
        "minimum_reader_pages": 5,
        "emphasis": "Swarms",
        "author": "Wilson Lin",
        "note": "Wilson Lin is a researcher at Cursor, where he works on long-running autonomous coding systems.",
        "es_title": "Enjambres de agentes y la nueva economía de los modelos",
        "es_short": "Enjambres de agentes",
        "es_emphasis": "Enjambres",
        "es_note": "Wilson Lin es investigador en Cursor, donde trabaja en sistemas de programación autónoma de larga duración.",
        "body": """Earlier this year, a long-running swarm built a web browser from scratch: a useful proof of concept, but far from polished software. After that deliberately empirical hill-climb, we wanted to engineer the system with intent. We returned to a task the old swarm had struggled with—implementing SQLite in Rust from its documentation alone—and the new harness beat it with every model mix. Grok 4.5 reached 80 percent in four hours while the old run spiraled before hour two. More agents were not the decisive variable; topology, memory, coordination, and the planning-execution split changed quality and cost.

## Trees and memory

Large tasks naturally form trees: a goal at the root divides recursively until the leaves are concrete units of work. Our swarm uses two roles around that structure. Planner agents, powered by the strongest models, decompose goals and delegate them. Worker agents, generally faster and cheaper, execute the leaves. Rather than impose a fixed orchestration graph, the swarm grows to match the contours of the problem, so compute and context scale with complexity.

This design has generalized to math problems, GPU kernels, vulnerability fixes, test coverage, and synthetic data. We think its scaling advantage comes more from context efficiency than parallelism. A single agent must traverse the whole tree while remembering its position and wider goal; it either focuses locally and loses the whole, or preserves the whole and weakens its local work. A planner never implements, so detail does not consume its context; a worker never plans and can focus on one leaf. Like the bounded tiers in Ronald Coase's account of firms, the tree contains coordination costs that otherwise grow faster than the work.

## Failure modes at swarm speed

The browser swarm peaked around 1,000 Git commits per hour; the new system can approach 1,000 per second. Coarse-locking tools cannot operate at that tempo, so we built a version-control system from scratch. Because every change passes through it, that layer also became the natural place to detect collisions and coordinate.

Two unaware planners could create split-brain designs, implementing one concept incompatibly. We changed the prompts so planners own design decisions and delegated subtrees cannot decide the same question. When planners still fought over files, merge tooling could not reconcile their different pictures of reality. Agents now record decisions in shared documents; code carries compile-checked references to them; and a reconciler merges contradictions so resolutions propagate downstream.

Workers were poor at absorbing another agent's context during a merge, so a neutral third party now resolves collisions. Workers can flag megafiles, block further commits, and hand decomposition to an outside agent. To counter learned reluctance to touch core code, intentional breakage lets an agent make a focused change, leave its reasoning, and use compiler failures to carry the new design through dependent work.

Review became another system, not a single pass. We tried reviewers with the worker's full transcript, only its output, or only the codebase; we also varied model and personality. No lens catches everything, but decorrelated lenses stack. Because review is cheaper than the work it audits, that compute had unusually high returns and appears to have helped quality survive long runs.

## Letting agents shape the environment

Rules such as “keep notes” and “document decisions” are a form of stigmergy: agents change the environment, which guides the next agent. We extended this with a Field Guide owned by the swarm and injected into every new trajectory. Under a line budget, agents preserve surprising encounters so successors take shorter paths. Model weights stay frozen, but the working environment can learn.

## Rebuilding SQLite from a manual

We gave the improved swarm the 835-page SQLite manual and withheld the source, tests, binary, and internet access. We graded the result against millions of sqllogictest queries with known answers. The swarm was never told that suite existed; after each run we manually checked for shortcuts and verified that the system had been built broadly rather than only where tests happened to look.

We tested four model mixes: GPT-5.5 everywhere; Grok 4.5 everywhere; Opus 4.8 planning with Composer 2.5 working; and Fable 5 planning with Composer 2.5 working. Strategies differed—some built broad foundations before a late score spike, others scored early and then plateaued—but the harness result did not. At four hours the new runs were between 73 and 85 percent while the old runs ranged from 11 to 77 percent. Every new configuration later passed the full suite.

## A deep dive into the runs

Activity alone was misleading. The old Grok run made 68,000 commits in under two hours, about seventy times the new run's pace, but accumulated more than 70,000 merge conflicts and accelerated rather than stabilizing. The new run logged fewer than 1,000 conflicts across its full four hours. One old megafile attracted 7,771 conflicts from 1,173 agents; the most contested file in the new codebase saw 47.

Split-brain showed up in the package structure too. The old swarm sprawled to 54 Rust crates, including three competing SQL packages. The new swarm settled on nine crates early and never added another. That coherence reached the final code: in the Fable mix, both harnesses eventually passed the suite, but the old one needed 64,305 lines of engine code and the new one 9,908. With the Opus mix, the old harness used 19,013 lines to reach 97 percent; the new one reached 100 percent in 4,645.

## Model economics

Similar quality concealed enormous cost differences: $1,339 for the Opus-and-Composer hybrid versus $10,565 for GPT-5.5 alone. Workers carried at least 69 percent of tokens in every run and more than 90 percent in most. Planner tokens cost more, but there are only a few moments when frontier intelligence is indispensable—the initial decomposition, major design decisions, and difficult trade-offs. Once ambiguity has been collapsed into explicit instructions, inexpensive models can perform most of the execution.

In the all-GPT-5.5 run, workers alone cost $9,373. In the Opus-planner, Composer-worker run, the whole worker fleet cost $411. Yet cheap planning is not automatically cheap overall. Fable used fewer planning tokens than Opus despite its higher per-token price, but its workers consumed several times as many tokens, making the complete run substantially more expensive. Models have to be selected by role and by their effect on downstream work, not by one headline token price.

## Specs become prompts

Each capability jump raises the working abstraction: autocomplete operated on a line, early models on a block, agents on a file or feature. With swarms, the unit becomes the specification. We handed the system 835 pages of prose and it returned a database; the scarce resource was the right description of intent.

A swarm therefore resembles a compiler. Planners parse a goal into task trees and lower it step by step into executable work. The difference is that a compiler preserves meaning deterministically while a swarm is probabilistic at every stage. The task tree, shared memory, coordination machinery, review lenses, and verification environment all exist to close that semantic gap.""",
        "figures": [
            {"id":"swarm-task-tree","decision":"include","source_id":"agent-swarms-and-the-new-model-economics-8b346f57","asset_id":"raster-002-c12295d4","caption":"Planner agents recursively decompose the goal; worker agents spend their context on bounded leaves of the task tree.","alt_text":"A goal branches through planner agents into narrow tasks handled by worker agents.","anchor":"Trees and memory","layout":"evidence_band_prose","criteria":["important","useful"],"rationale":"The light print export makes the topology and its internal labels legible at A5 size."},
            {"id":"swarm-model-cost","decision":"include","source_id":"agent-swarms-and-the-new-model-economics-8b346f57","asset_id":"raster-001-a065638c","caption":"Comparable SQLite outcomes carried radically different costs depending on which models planned and which performed the worker load.","alt_text":"A cost comparison across four planner and worker model configurations under old and new swarm harnesses.","anchor":"Model economics","layout":"evidence_band_prose","criteria":["important","useful"],"rationale":"The light print export keeps model labels and values legible while showing model roles as an economic choice."}
        ],
        "es_body": """A comienzos de este año, un enjambre construyó un navegador desde cero: una prueba útil, pero lejos de ser software pulido. Después quisimos diseñar el sistema con intención. Volvimos a una tarea que al enjambre anterior le había costado —implementar SQLite en Rust desde su documentación— y el arnés nuevo lo superó con todas las combinaciones de modelos. Más agentes no fueron la variable decisiva: la topología, la memoria, la coordinación y la división entre planificación y ejecución cambiaron la calidad y el coste.

## Árboles y memoria

Las tareas grandes forman árboles de manera natural: una meta en la raíz se divide recursivamente hasta que las hojas son unidades concretas de trabajo. Nuestro enjambre organiza dos funciones alrededor de esa estructura. Los agentes planificadores, impulsados por los modelos más capaces, descomponen metas y delegan. Los agentes trabajadores, por lo general más rápidos y baratos, ejecutan las hojas. En vez de imponer un grafo fijo de orquestación, el enjambre crece según los contornos del problema, de modo que el cómputo y el contexto escalan con la complejidad.

El diseño se ha generalizado a problemas matemáticos, kernels de GPU, vulnerabilidades, cobertura de pruebas y datos sintéticos. Creemos que su ventaja procede más de la eficiencia de contexto que del paralelismo. Un solo agente debe recorrer todo el árbol mientras recuerda su posición y la meta general; o se concentra en lo local y pierde el conjunto, o conserva el conjunto y debilita su trabajo local. Un planificador nunca implementa, así que el detalle no consume su contexto; un trabajador nunca planifica y se concentra en una hoja. Como los niveles acotados de la empresa en la explicación de Ronald Coase, el árbol contiene costes de coordinación que crecerían más deprisa que el trabajo.

## Fallos a la velocidad del enjambre

El enjambre del navegador alcanzaba unos 1.000 commits por hora en Git; el sistema nuevo puede acercarse a 1.000 por segundo. Las herramientas con bloqueos gruesos no funcionan a ese ritmo, así que construimos un sistema de control de versiones desde cero. Como cada cambio pasa por esa capa, también se convirtió en el lugar natural para detectar colisiones y coordinar.

Dos planificadores que no se conocían podían crear diseños divergentes e implementar un concepto de formas incompatibles. Cambiamos los prompts para que los planificadores posean las decisiones de diseño y los subárboles delegados no resuelvan la misma cuestión. Cuando aun así luchaban por archivos, ninguna herramienta de merge podía reconciliar sus imágenes distintas de la realidad. Ahora registran decisiones en documentos compartidos; el código mantiene referencias comprobadas por el compilador; y un reconciliador fusiona contradicciones para propagar la resolución.

Los trabajadores tampoco absorbían bien el contexto ajeno durante un merge, por lo que un tercero neutral resuelve las colisiones. Pueden marcar megaarchivos, bloquear commits nuevos y encargar su descomposición a un agente externo. Para contrarrestar la resistencia aprendida a tocar el núcleo, una rotura intencional permite un cambio acotado, deja su razonamiento y usa los fallos del compilador para llevar el diseño nuevo al trabajo dependiente.

La revisión pasó a ser otro sistema, no una única etapa. Probamos revisores con la transcripción completa del trabajador, solo con su salida o únicamente con el código; también variamos modelo y personalidad. Ninguna lente detecta todo, pero las lentes no correlacionadas se acumulan. Como revisar cuesta menos que producir el trabajo auditado, ese cómputo rindió especialmente bien y parece haber sostenido la calidad durante ejecuciones largas.

## Dejar que los agentes moldeen el entorno

Reglas como «tomar notas» y «documentar decisiones» son una forma de estigmergia: los agentes cambian el entorno y este guía al siguiente. Lo ampliamos con una Guía de campo propiedad del enjambre e inyectada en cada trayectoria nueva. Bajo un límite de líneas, conserva encuentros sorprendentes para acortar el camino de los sucesores. Los pesos permanecen congelados, pero el entorno puede aprender.

## Reconstruir SQLite desde un manual

Entregamos al enjambre mejorado el manual de SQLite de 835 páginas y ocultamos el código fuente, las pruebas, el binario y el acceso a internet. Evaluamos el resultado contra millones de consultas de sqllogictest con respuestas conocidas. El enjambre nunca supo que existía esa prueba; tras cada ejecución comprobamos manualmente que no hubiera atajos y que el sistema se hubiese construido de forma amplia, no solo donde parecían mirar los tests.

Probamos cuatro combinaciones: GPT-5.5 para todo; Grok 4.5 para todo; Opus 4.8 planificando y Composer 2.5 trabajando; y Fable 5 planificando con Composer 2.5. Las estrategias variaron —algunas construyeron bases amplias antes de un salto tardío, otras puntuaron pronto y luego se estancaron—, pero el efecto del arnés no. A las cuatro horas, las ejecuciones nuevas estaban entre el 73 y el 85 por ciento y las anteriores entre el 11 y el 77. Todas las configuraciones nuevas terminaron aprobando la prueba completa.

## Una mirada profunda a las ejecuciones

La actividad por sí sola engañaba. La ejecución antigua de Grok hizo 68.000 commits en menos de dos horas, unas setenta veces el ritmo de la nueva, pero acumuló más de 70.000 conflictos de merge y aceleró en vez de estabilizarse. La nueva registró menos de 1.000 conflictos en sus cuatro horas. Un megaarchivo antiguo atrajo 7.771 conflictos de 1.173 agentes; el archivo más disputado del código nuevo tuvo 47.

La divergencia también apareció en la estructura de paquetes. El enjambre antiguo se extendió a 54 crates de Rust, incluidos tres paquetes SQL rivales. El nuevo se asentó pronto en nueve y no añadió otro. Esa coherencia llegó al código final: con Fable, ambos arneses terminaron aprobando, pero el antiguo necesitó 64.305 líneas de motor y el nuevo 9.908. Con Opus, el viejo usó 19.013 líneas para llegar al 97 por ciento; el nuevo alcanzó el 100 por ciento con 4.645.

## Economía de modelos

Una calidad similar ocultaba diferencias enormes de coste: 1.339 dólares para el híbrido Opus-Composer y 10.565 para GPT-5.5 solo. Los trabajadores consumieron al menos el 69 por ciento de los tokens en todas las ejecuciones y más del 90 por ciento en la mayoría. Los tokens del planificador cuestan más, pero solo unos pocos momentos requieren inteligencia de frontera: la descomposición inicial, las decisiones de diseño y los intercambios difíciles. Cuando la ambigüedad se convierte en instrucciones explícitas, modelos económicos pueden realizar casi toda la ejecución.

En la ejecución íntegra con GPT-5.5, solo los trabajadores costaron 9.373 dólares. Con Opus como planificador y Composer como trabajador, toda la flota de ejecución costó 411. Pero una planificación barata no abarata automáticamente el total. Fable usó menos tokens de planificación que Opus pese a su mayor precio unitario, pero sus trabajadores consumieron varias veces más tokens y encarecieron mucho la ejecución completa. Hay que elegir los modelos por función y por su efecto sobre el trabajo posterior, no por un único precio de tokens.

## Las especificaciones se vuelven prompts

Cada salto de capacidad eleva la abstracción de trabajo: autocompletado sobre una línea, primeros modelos sobre un bloque y agentes sobre un archivo o una funcionalidad. Con enjambres, la unidad es la especificación. Entregamos al sistema 835 páginas de prosa y devolvió una base de datos; el recurso escaso era la descripción correcta de la intención.

Por eso un enjambre se parece a un compilador. Los planificadores analizan una meta en árboles de tareas y la reducen paso a paso a trabajo ejecutable. La diferencia es que un compilador preserva el significado de forma determinista, mientras que el enjambre es probabilístico en cada etapa. El árbol, la memoria compartida, la coordinación, las lentes de revisión y el entorno de verificación existen para cerrar esa brecha semántica.""",
        "es_figures": [
            {"id":"swarm-task-tree","caption":"Los agentes planificadores descomponen la meta de forma recursiva; los trabajadores dedican su contexto a hojas acotadas del árbol de tareas.","credit":"Diagrama de Wilson Lin; fuente: Agent Swarms and the New Model Economics.","alt_text":"Una meta se ramifica mediante agentes planificadores en tareas acotadas para agentes trabajadores.","anchor":"Árboles y memoria"},
            {"id":"swarm-model-cost","caption":"Resultados comparables de SQLite tuvieron costes radicalmente distintos según qué modelos planificaron y cuáles absorbieron la carga de ejecución.","credit":"Diagrama de Wilson Lin; fuente: Agent Swarms and the New Model Economics.","alt_text":"Comparación de costes entre cuatro configuraciones de modelos planificadores y trabajadores con los arneses antiguo y nuevo.","anchor":"Economía de modelos"}
        ],
    },
    {
        "id": "loop-engineering-roadmap",
        "source_id": "loop-engineering-the-14-step-roadmap-from-prompt-76a8ae0f",
        "title": "Loop Engineering: A Roadmap Beyond the Prompt",
        "short_title": "Loop Engineering",
        "emphasis": "Loop",
        "author": "Codez",
        "note": "Codez is the publishing name of Lev Deviatkin.",
        "es_title": "Ingeniería de ciclos: una hoja de ruta más allá del prompt",
        "es_short": "Ingeniería de ciclos",
        "es_emphasis": "Ciclos",
        "es_note": "Codez es el nombre con el que publica Lev Deviatkin.",
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
        "note": "Praveen Neppalli Naga is Uber's chief technology officer and previously held engineering leadership roles at LinkedIn.",
        "es_title": "Pods de agentes: llevar la IA más allá de ingeniería",
        "es_short": "Pods de agentes",
        "es_emphasis": "Pods",
        "es_note": "Praveen Neppalli Naga es director de tecnología de Uber y antes ocupó puestos de liderazgo en ingeniería en LinkedIn.",
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

The loop is small: context, action, check, repeat. A factory begins when it gains walls, memory, a queue, and neighbors. Edition 2 moves from reusable libraries to swarms, and from verified automation to redesigned workflows.

Across these accounts, generation becomes abundant before judgment. Addy Osmani identifies the expensive box: review. Cursor measures it—a thousand commits a second are useless without coordination. Topology, memory, and verification turn activity into progress.

Beyond code, Mitchell Hashimoto sees agents multiplying clean building blocks. Praveen Neppalli pairs system and domain experts because workflows exceed their diagrams. Codez makes verification the loop's product. Cerebras builds a visible path from question to evidence.

The point is to design the outer loop deliberately. Human attention belongs where consequences are expensive, signals ambiguous, and misunderstanding compounds. Everything else earns autonomy through narrow scope and cheap evidence.

A good factory preserves intent, attaches evidence to decisions, makes failure legible, and leaves enough light for its owners to understand what they built.
"""
    editorial_es = """---
label: EDITORIAL — TEXTO DE LA REDACCIÓN
title: La casilla costosa
byline: La redacción
---

El ciclo es pequeño: contexto, acción, comprobación, repetición. Una fábrica comienza cuando adquiere paredes, memoria, una cola y vecinos. La edición 2 pasa de bibliotecas reutilizables a enjambres, y de la automatización verificada al rediseño de flujos.

En estos relatos, la generación se vuelve abundante antes que el criterio. Addy Osmani identifica la casilla costosa: la revisión. Cursor mide la restricción: mil commits por segundo son inútiles sin coordinación. Topología, memoria y verificación convierten actividad en progreso.

Fuera del código, Mitchell Hashimoto ve agentes que multiplican bloques limpios. Praveen Neppalli une expertos de sistemas y de dominio porque los flujos exceden sus diagramas. Codez convierte la verificación en el producto del ciclo. Cerebras traza un camino visible desde la pregunta hasta la evidencia.

La cuestión es diseñar deliberadamente el ciclo exterior. La atención humana pertenece donde las consecuencias son caras, las señales ambiguas y la incomprensión se acumula. Todo lo demás gana autonomía mediante un alcance estrecho y evidencia barata.

Una buena fábrica preserva la intención, une la evidencia a las decisiones, vuelve legible el fallo y deja luz para comprender lo construido.
"""
    write(EDITION / "manuscript" / "editorial.md", editorial_en)
    write(ES / "manuscript" / "editorial.md", editorial_es)

    base = yaml.safe_load((EDITION / "edition.yaml").read_text())
    base.pop("sections", None)
    cerebras = next(row for row in base["articles"] if row["id"] == "how-we-built-our-knowledge-base")
    tail_art_paths = {
        "the-building-block-economy": "editions/002-unreleased/art/article-tails/modular-ascent-v1.png",
        "loop-engineering-roadmap": "editions/002-unreleased/art/article-tails/verified-circuit-v1.png",
        "agentic-pods": "editions/002-unreleased/art/article-tails/pod-exchange-v1.png",
        "how-we-built-our-knowledge-base": "editions/002-unreleased/art/article-tails/evidence-fold-v1.png",
    }
    article_rows = []
    variants = ["split_axis", "edge_medallion", "stepped_title", "split_axis", "edge_medallion"]
    for article, variant in zip(ARTICLES, variants):
        row = {
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
        }
        if article.get("figures"):
            row["figures"] = article["figures"]
        if article.get("minimum_reader_pages"):
            row["minimum_reader_pages"] = article["minimum_reader_pages"]
        if article["id"] in tail_art_paths:
            row["tail_art_path"] = tail_art_paths[article["id"]]
        article_rows.append(row)
    cerebras["opener_variant"] = "stepped_title"
    cerebras["author_note"] = (
        "Isaac Tai, Daniel Kim, and Mike Gao work at Cerebras Systems, "
        "the AI-chip company behind the Wafer-Scale Engine."
    )
    cerebras["tail_art_path"] = tail_art_paths["how-we-built-our-knowledge-base"]
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
        "closing_plates": [
            {
                "title": "Systems in Motion",
                "art_path": "editions/002-unreleased/art/coda-convergence-v1.png",
            },
            {
                "title": "Intent, Preserved",
                "art_path": "editions/002-unreleased/art/coda-branches-v2.png",
            },
            {
                "title": "Signals Return",
                "art_path": "editions/002-unreleased/art/coda-return-v1.png",
            },
        ],
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
    cerebras_es["author_note"] = (
        "Isaac Tai, Daniel Kim y Mike Gao trabajan en Cerebras Systems, "
        "la empresa de chips de IA creadora del Wafer-Scale Engine."
    )
    translated_rows = []
    loaded_articles = {article.id: article for article in loaded.articles}
    for article in ARTICLES:
        source_path = EDITION / "articles" / f"{article['id']}.md"
        row = {
            "id": article["id"],
            "title": article["es_title"],
            "short_title": article["es_short"],
            "display_emphasis": article["es_emphasis"],
            "author_note": article["es_note"],
            "manuscript": f"articles/{article['id']}.md",
            "source_sha256": sha(source_path),
        }
        if article.get("es_figures"):
            base_figures = {figure.id: figure for figure in loaded_articles[article["id"]].figures}
            row["figures"] = [
                {
                    **figure,
                    "source_caption_sha256": caption_sha256(
                        figure["id"], base_figures[figure["id"]].caption
                    ),
                    "source_credit_sha256": credit_sha256(
                        figure["id"], base_figures[figure["id"]].credit
                    ),
                }
                for figure in article["es_figures"]
            ]
        translated_rows.append(row)
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
        "closing_plate_titles": [
            "Sistemas en movimiento",
            "Intención preservada",
            "Las señales regresan",
        ],
        "editorial": {"path": "manuscript/editorial.md", "source_sha256": sha(EDITION / "manuscript" / "editorial.md")},
        "articles": translated_rows + [cerebras_es],
        "sections": [],
    }
    write(ES / "edition.yaml", yaml.safe_dump(translation, sort_keys=False, allow_unicode=True, width=110))


if __name__ == "__main__":
    main()
