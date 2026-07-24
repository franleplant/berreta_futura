from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from magazine.manifest import _edition_copy_sha256, load_edition
from magazine.media_schema import caption_sha256
from magazine.records import load_records


ROOT = Path(__file__).resolve().parents[1]
EDITION_ID = "002-unreleased"
SOURCE_ID = "how-we-built-our-knowledge-base-e986baa0"
BUNDLE_ID = "19af9e64b33b5ee3ed43671788c1c3772d628ebe7097db77e1f62dccd51db169"
EDITION_DIR = ROOT / "editions" / EDITION_ID
TRANSLATION_DIR = EDITION_DIR / "translations" / "es"
CAPTURE = (
    ROOT
    / "library"
    / "sources"
    / SOURCE_ID
    / "raw"
    / BUNDLE_ID
    / "artifacts"
    / "capture.json"
)


SELECTED = (
    2,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    25,
    84,
    85,
    86,
    87,
    88,
    89,
    90,
    91,
    92,
    93,
    94,
    96,
    98,
    99,
    100,
    101,
    103,
    104,
    105,
    108,
    109,
    118,
    119,
)


SPANISH = {
    2: (
        "Los empleados le hacen más de 15.000 preguntas por día a nuestra base de conocimiento "
        "interna. Desde su lanzamiento, hace 3 meses, se ha convertido en una de las herramientas "
        "internas con mayor adopción de la empresa. La usan personas, automatizaciones y agentes.\n\n"
        "En Cerebras, nuestros equipos trabajan en operaciones de centros de datos, diseño de chips, "
        "hardware, entrenamiento, inferencia, plataforma en la nube y mucho más. Con cientos de nuevos "
        "empleados que se incorporan cada año, nuestros canales de comunicación se llenaban de las "
        "mismas preguntas:"
    ),
    4: "Construimos Cerebras Knowledge para ayudar a conectar a las personas y los sistemas con información útil.",
    5: "Encontrar los datos donde están",
    6: (
        "Encontrar información dentro de una organización es difícil. Los datos están dispersos entre "
        "herramientas y, aproximadamente cada trimestre, alguien propone la misma solución brillante: "
        "registremos todo en una plataforma para que la información esté en un único lugar. El sueño de "
        "una única fuente de verdad, por supuesto, rara vez funciona en la práctica."
    ),
    7: (
        "La información se genera allí donde resulta conveniente y ergonómico: ediciones sugeridas en "
        "un documento, hilos de Slack, referencias de código en GitHub y metadatos de estado en Jira. "
        "Estas plataformas están hechas a medida de sus dominios específicos y optimizadas durante años "
        "de ingeniería de producto y análisis. Debatir una solicitud de cambios en Google Docs sería una "
        "experiencia espantosa."
    ),
    8: (
        "Por eso nos propusimos diseñar un sistema que exigiera cambios mínimos en los comportamientos "
        "existentes. Del lado de la recopilación, eso implicaba extraer los datos directamente de cada "
        "plataforma."
    ),
    9: "Anatomía de una base de conocimiento",
    10: "Nuestra base de conocimiento ofrece tres cosas:",
    14: (
        "En el centro hay una única tabla de Postgres que contiene embeddings, resúmenes en bruto y "
        "metadatos de numerosas fuentes. El sistema ingiere datos de toda la empresa de forma continua y "
        "mantiene un almacén listo para consultas."
    ),
    15: (
        "Queríamos una interfaz de datos sencilla que pudiera funcionar con la mayoría de las formas de "
        "datos. También queríamos que otros desarrolladores de Cerebras pudieran crear conectores a "
        "medida. El resultado es deliberadamente simple: cada fuente, desde hilos de Slack hasta netlists, "
        "aterriza en la misma tabla de embeddings, y todo lo que entra en ella puede consultarse de "
        "inmediato mediante la misma interfaz:"
    ),
    16: (
        "Cada fuente define qué son los datos, cómo conectarse a ellos y con qué frecuencia obtenerlos. "
        "Cada fila de embeddings resultante respeta la misma interfaz, ya provenga de Slack, de un "
        "repositorio de código, de un sistema documental o de una base de datos personalizada."
    ),
    17: "Slack",
    18: (
        "Slack era la fuente de datos más importante para la que necesitábamos diseñar. Allí ocurren las "
        "conversaciones de ingeniería más actualizadas de toda la empresa."
    ),
    19: "Cómo procesamos conversaciones no estructuradas de Slack",
    20: (
        "Al principio probamos si bastaban embeddings sencillos sobre texto en bruto. Pronto comprobamos "
        "que la búsqueda vectorial por sí sola era insuficiente para encontrar todos los datos relevantes."
    ),
    25: (
        "Necesitábamos un enfoque híbrido. Construimos la ingesta de Slack para que cada hilo pudiera "
        "recuperarse mediante varias técnicas de búsqueda a la vez, donde cada técnica compensara las "
        "debilidades de las demás:"
    ),
    26: (
        "La búsqueda de texto completo encuentra los tokens exactos que los embeddings difuminan: mensajes "
        "de error, nombres de opciones y nombres de hosts. Cuando un ingeniero pega un mensaje de error literal, "
        "una coincidencia léxica exacta casi siempre es la mejor evidencia y ninguna similitud semántica debería superarla."
    ),
    27: (
        "La búsqueda por embeddings encuentra paráfrasis. Quien pregunta «la restauración se cuelga después "
        "de cargar el manifiesto» y quien respondió «el checkpoint se atasca en el montaje NFS» quizá no "
        "compartan vocabulario. La similitud vectorial conecta una pregunta con una respuesta escrita con otras palabras.(1)"
    ),
    84: "Planificación y abanico de herramientas",
    85: (
        "Para cada consulta, primero ejecutamos una breve etapa de planificación en la que un LLM decide "
        "qué herramientas y fuentes de datos probablemente importen. Las herramientas principales:"
    ),
    86: "subsystem_index: resúmenes por archivo producidos por un LLM.",
    87: (
        "search: el canal vectorial unificado que abarca Slack, la wiki, el código y otras fuentes "
        "indexadas, combinadas y reordenadas internamente."
    ),
    88: "search_slack: recuperación directa desde Slack.",
    89: "search_code: ripgrep sobre los repositorios de código fuente.",
    90: "recent_prs: solicitudes de cambios recientes relevantes para la pregunta.",
    91: "who_knows: personas con experiencia demostrada en un tema.",
    92: (
        "El planificador trabaja con una descripción compacta de lo que hemos indexado: qué proyectos "
        "existen, qué fuentes están disponibles en cada proyecto y para qué tipo de respuestas sirve cada "
        "una. A partir de la consulta y el alcance activo del usuario, emite selecciones de herramientas "
        "que el ejecutor distribuye en paralelo, normaliza en un formato de evidencia común y entrega a un "
        "LLM de síntesis final.(4)"
    ),
    93: "Reordenamiento",
    94: (
        "Un documento puede aparecer cerca del primer puesto solo porque comparte vocabulario con la "
        "consulta, aunque responda otra pregunta. Antes de reordenar, combinamos las listas incompatibles "
        "de los recuperadores mediante fusión recíproca de rangos, o RRF. Para cada documento, sumamos "
        "peso / (60 + posición) por cada lista en la que aparece, con un peso predeterminado de 1,0 y una "
        "constante de suavizado de 60."
    ),
    95: (
        "La constante de suavizado hace que el consenso importe más que un único voto fuerte: un documento "
        "que aparece cerca del primer puesto en varios recuperadores puede superar a otro que ocupa el "
        "primer lugar en uno solo. Después reunimos los fragmentos duplicados en una sola fuente, limitamos "
        "cuántos resultados puede aportar cada archivo y obtenemos un grupo de veinte resultados más diverso."
    ),
    96: (
        "Enviamos la consulta original y esos candidatos a un pequeño modelo de reordenamiento. Asigna a "
        "cada documento una puntuación de cero a diez y conservamos los diez mejores.(6)"
    ),
    97: (
        "Cuando la clasificación es definitiva, devolvemos contexto a los ganadores. Por ejemplo, si "
        "encontramos una sección de la wiki, incorporamos las dos secciones vecinas para no perder el "
        "título, las condiciones previas ni las salvedades que el troceado separó. Así, el lector recibe "
        "un fragmento completo en vez de un párrafo solitario al que le falta contexto importante."
    ),
    98: (
        "El resultado de la búsqueda es, por tanto, un rico paquete de evidencia: resultados fusionados "
        "desde distintos recuperadores, deduplicados en el nivel de la fuente, reordenados respecto de la "
        "pregunta real y, solo entonces, ampliados con el contexto circundante."
    ),
    99: "MCP",
    100: (
        "En la integración con MCP exponemos los componentes básicos de recuperación como herramientas "
        "directas, en lugar de esconderlos detrás de un único punto de acceso de «responde esta pregunta». "
        "Estas herramientas son deliberadamente sencillas y evitan los LLM en la medida de lo posible, "
        "para que los clientes puedan consultarlas con rapidez y a bajo coste.(5)"
    ),
    101: (
        "Cada herramienta MCP corresponde a una primitiva de recuperación subyacente, como search_slack, "
        "search_code, search o who_knows. Sus entradas y salidas son acotadas, estructuradas y estables, "
        "por lo que cualquier cliente o agente puede invocarlas sin incorporar más lógica de orquestación "
        "dentro de la herramienta."
    ),
    102: (
        "La mayoría de las herramientas ejecuta un canal de consulta —como búsqueda vectorial, búsqueda "
        "léxica o ripgrep—, aplica heurísticas ligeras de puntuación y devuelve filas de evidencia en bruto."
    ),
    103: (
        "Claude Code, o cualquier agente compatible con MCP, se convierte en el motor de orquestación. "
        "Decide qué herramientas llamar, en qué orden y cómo reunir los resultados en una respuesta final "
        "o una edición de código. La capa de recuperación no depende de esas decisiones del LLM para "
        "atender las solicitudes."
    ),
    104: "Interfaz web",
    105: (
        "En la interfaz web existen las mismas herramientas, pero están conectadas a un canal de consulta "
        "completo que se ejecuta de principio a fin para cada pregunta del usuario. El agente de la interfaz "
        "se ocupa de las etapas de planificación y ejecución."
    ),
    106: (
        "Planificador: una etapa ligera con un LLM examina la consulta y el proyecto activo; luego elige qué "
        "herramientas de recuperación invocar, como search, search_slack y subsystem_index."
    ),
    107: (
        "Ejecutor: el sistema distribuye en paralelo esas llamadas, reúne los resultados y los normaliza en "
        "un esquema compartido de evidencia con puntuaciones, actualidad e indicios sobre la fuente."
    ),
    108: (
        "Síntesis: una etapa final con un LLM recibe el paquete tipado de evidencia y la pregunta original; "
        "después produce la respuesta que se muestra en la interfaz, con citas, salvedades y síntesis entre fuentes."
    ),
    109: (
        "Desde la perspectiva del usuario, la interfaz web es simplemente «hacer una pregunta y obtener una "
        "respuesta». Por debajo, ejecuta el mismo patrón planificador → ejecutor → sintetizador que los "
        "clientes MCP pueden recrear de forma explícita."
    ),
    112: "Proyectos y búsqueda acotada",
    113: (
        "Introdujimos los proyectos como forma principal de organizar el espacio de trabajo sobre el que se "
        "ejecuta una consulta. Un proyecto es un conjunto de fuentes con nombre: canales específicos de "
        "Slack, repositorios de código, bases de datos internas y espacios documentales relevantes para un "
        "equipo o una iniciativa."
    ),
    114: (
        "Los proyectos son deliberadamente ligeros. Una misma fuente, como un canal compartido de incidentes "
        "o el repositorio de una plataforma central, puede pertenecer a varios proyectos sin duplicarse."
    ),
    118: "Reflexiones finales",
    119: (
        "En definitiva, la base de conocimiento funciona porque encuentra a las personas allí donde ya vive "
        "la información, en lugar de obligar a meterlo todo en un sistema rígido. Al combinar distintas "
        "técnicas de búsqueda, podemos hacer aflorar evidencia con rapidez. El resultado es una experiencia "
        "de búsqueda lo bastante flexible para los datos reales de una empresa, pero lo bastante estructurada "
        "para seguir siendo útil mientras Cerebras crece."
    ),
}


def dump_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=110),
        encoding="utf-8",
    )


def markdown_block(kind: str, text: str) -> str:
    if kind in {"h2", "h3", "h4"}:
        return f"## {text}"
    if kind == "li":
        return f"- {text}"
    if kind in {"quote", "blockquote"}:
        return f"> {text}"
    return text


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    blocks = capture["blocks"]
    selected = set(SELECTED)
    if selected - set(range(len(blocks))):
        raise SystemExit("Selected source blocks are out of range")
    if not selected.issubset(SPANISH):
        raise SystemExit("Spanish translations do not cover every selected source block")

    english_article = EDITION_DIR / "articles" / "how-we-built-our-knowledge-base.md"
    spanish_article = TRANSLATION_DIR / "articles" / "how-we-built-our-knowledge-base.md"
    english_article.parent.mkdir(parents=True, exist_ok=True)
    spanish_article.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---\n"
        f"source_id: {SOURCE_ID}\n"
        "content_mode: selected_extracts\n"
        "label: SELECTED EXTRACTS\n"
        "---\n\n"
    )
    english_body = "\n\n".join(
        markdown_block(blocks[index]["kind"], blocks[index]["text"])
        for index in SELECTED
    )
    spanish_frontmatter = frontmatter.replace("SELECTED EXTRACTS", "EXTRACTOS SELECCIONADOS")
    spanish_body = "\n\n".join(
        markdown_block(blocks[index]["kind"], SPANISH[index])
        for index in SELECTED
    )
    english_article.write_text(frontmatter + english_body + "\n", encoding="utf-8")
    spanish_article.write_text(spanish_frontmatter + spanish_body + "\n", encoding="utf-8")

    paragraphs = []
    for index, block in enumerate(blocks):
        kind = block["kind"]
        if kind in {"h2", "h3", "h4"}:
            kind = "h2"
        elif kind == "li":
            kind = "bullet"
        status = "retained" if index in selected else "substantive_cut"
        if index in {0, 1}:
            status = "boilerplate_removed"
        paragraphs.append(
            {
                "id": f"source-{index + 1:03d}",
                "kind": kind,
                "status": status,
                "source": block["text"],
            }
        )
    dump_yaml(
        EDITION_DIR / "fidelity" / "how-we-built-our-knowledge-base.yaml",
        {
            "schema_version": 1,
            "source_ids": [SOURCE_ID],
            "content_mode": "selected_extracts",
            "source_body_sha256": "ee07d26dc95a01cde7cf1145adbe49f1cf4e9fef10aeed8815efd47c0edb7967",
            "paragraphs": paragraphs,
        },
    )

    english_editorial = EDITION_DIR / "manuscript" / "editorial.md"
    spanish_editorial = TRANSLATION_DIR / "manuscript" / "editorial.md"
    english_editorial.parent.mkdir(parents=True, exist_ok=True)
    spanish_editorial.parent.mkdir(parents=True, exist_ok=True)
    english_editorial.write_text(
        """---
kind: original_editorial
label: ORIGINAL EDITORIAL
title: The Shape of a Good Question
byline: The editors
---

A knowledge system becomes interesting when its diagrams explain decisions rather than decorate pages. The three images in this provisional issue were not chosen because they existed. They were chosen because each compresses a different layer of the argument: the whole pipeline, the moment a question fans out into tools, and the boundary between raw retrieval and a complete answer.

That distinction is also the editorial test. Useful images let a reader alternate between overview and detail. They interrupt long passages without interrupting thought. Their captions add orientation instead of repeating what is already visible.

This is a working edition, not a finished claim. Its purpose is to see whether automatic curation can produce a magazine rhythm that feels intentional: one image when the system comes into view, another when the machinery branches, and a final comparison when the interface changes what the system must own.
""",
        encoding="utf-8",
    )
    spanish_editorial.write_text(
        """---
kind: original_editorial
label: EDITORIAL ORIGINAL
title: La forma de una buena pregunta
byline: Los editores
---

Un sistema de conocimiento se vuelve interesante cuando sus diagramas explican decisiones en vez de decorar páginas. Las tres imágenes de este número provisional no fueron elegidas porque existían. Fueron elegidas porque cada una condensa una capa distinta del argumento: el canal completo, el momento en que una pregunta se abre en abanico hacia distintas herramientas y el límite entre la recuperación en bruto y una respuesta completa.

Esa distinción es también la prueba editorial. Las imágenes útiles permiten que el lector alterne entre la visión general y el detalle. Interrumpen pasajes largos sin interrumpir el pensamiento. Sus epígrafes orientan en lugar de repetir lo que ya se ve.

Esta es una edición de trabajo, no una afirmación definitiva. Su propósito es comprobar si la curaduría automática puede producir un ritmo de revista que parezca intencional: una imagen cuando el sistema aparece en conjunto, otra cuando la maquinaria se ramifica y una comparación final cuando la interfaz modifica aquello de lo que el sistema debe hacerse cargo.
""",
        encoding="utf-8",
    )

    figures = [
        {
            "id": "knowledge-pipeline",
            "decision": "include",
            "source_id": SOURCE_ID,
            "asset_id": "svg-001-2157c84f",
            "caption": (
                "Cerebras Knowledge moves source material through distillation, embeddings, retrieval, "
                "fusion and reranking, then answer synthesis with citations."
            ),
            "alt_text": (
                "A vertical architecture diagram traces source material through distillation, embeddings, "
                "multiple retrieval paths, fusion, reranking and a cited answer."
            ),
            "anchor": "__opener__",
            "layout": "evidence_band",
            "criteria": ["important", "useful", "beautiful"],
            "rationale": (
                "The overview makes the article's complete information path legible before the reader "
                "encounters its individual components."
            ),
        },
        {
            "id": "planner-tool-fanout",
            "decision": "include",
            "source_id": SOURCE_ID,
            "asset_id": "svg-007-a8dd9756",
            "caption": (
                "A planning pass fans one question out across specialized search tools before evidence "
                "normalization and answer synthesis."
            ),
            "alt_text": (
                "A horizontal diagram shows a user query entering a planner, branching to several search "
                "tools, then converging into normalized evidence and synthesis."
            ),
            "anchor": "Planning and tool fan-out",
            "layout": "evidence_band",
            "criteria": ["important", "useful", "cool"],
            "rationale": (
                "The diagram converts an abstract orchestration sequence into a memorable visual flow at "
                "the exact point where the article introduces planning."
            ),
        },
        {
            "id": "mcp-web-ui-comparison",
            "decision": "include",
            "source_id": SOURCE_ID,
            "asset_id": "svg-008-b42cddcd",
            "caption": (
                "MCP exposes raw retrieval primitives to external clients; the web UI owns the complete "
                "planner–executor–synthesis loop."
            ),
            "alt_text": (
                "A side-by-side architecture comparison contrasts direct MCP retrieval tools with the web "
                "interface's integrated planning, execution and synthesis pipeline."
            ),
            "anchor": "Web UI",
            "layout": "evidence_band",
            "criteria": ["important", "useful", "beautiful"],
            "rationale": (
                "The comparison clarifies the most consequential interface distinction more efficiently "
                "than another paragraph of prose."
            ),
        },
    ]
    edition = {
        "schema_version": 1,
        "id": EDITION_ID,
        "issue_number": 2,
        "publication_date": "2026-07-17",
        "title": "Knowledge, Where It Lives",
        "subtitle": "Retrieval, orchestration, and useful evidence across the tools where work already happens",
        "language": "en",
        "distribution": "private",
        "status": "provisional",
        "format": {
            "trim": "A5",
            "home_sheet": "A4",
            "binding": "saddle_stitch",
            "max_article_pages": 7,
            "max_editorial_pages": 2,
        },
        "cover": {
            "headline": "Knowledge, Where It Lives",
            "deck": "How a useful internal search system meets information without forcing it into one place",
            "back_text": (
                "The best knowledge systems do not begin by moving everything. They begin by respecting "
                "where work already happens—and making the path from question to evidence visible."
            ),
        },
        "sources": [SOURCE_ID],
        "editorial": "manuscript/editorial.md",
        "articles": [
            {
                "id": "how-we-built-our-knowledge-base",
                "title": "How We Built Our Knowledge Base",
                "short_title": "Our Knowledge Base",
                "display_emphasis": "Knowledge",
                "opener_variant": "split_axis",
                "author": "Isaac Tai, Daniel Kim & Mike Gao",
                "author_note": "Isaac Tai, Daniel Kim, and Mike Gao built Cerebras Knowledge for internal search.",
                "content_mode": "selected_extracts",
                "source_ids": [SOURCE_ID],
                "manuscript": f"editions/{EDITION_ID}/articles/how-we-built-our-knowledge-base.md",
                "fidelity": f"editions/{EDITION_ID}/fidelity/how-we-built-our-knowledge-base.yaml",
                "tail_art_path": (
                    f"editions/{EDITION_ID}/art/article-tails/evidence-fold-v1.png"
                ),
                "figures": figures,
            }
        ],
        "rights": {
            "faithful_source_reprint": "private_only_while_rights_unknown",
            "public_release": "blocked_pending_permission_or_applicable_exception",
        },
    }
    dump_yaml(EDITION_DIR / "edition.yaml", edition)

    records = load_records(ROOT / "library" / "sources")
    by_id = {record.id: record for record in records}
    base = load_edition(
        ROOT,
        EDITION_ID,
        set(by_id),
        publication_name="The Work Left to Us",
        source_records=by_id,
    )
    localized_figures = [
        {
            "id": "knowledge-pipeline",
            "caption": (
                "Cerebras Knowledge conduce el material de las fuentes a través de destilación, embeddings, "
                "recuperación, fusión y reordenamiento, hasta sintetizar una respuesta con citas."
            ),
            "alt_text": (
                "Un diagrama vertical de arquitectura recorre el material desde la destilación y los "
                "embeddings hasta varias rutas de recuperación, la fusión, el reordenamiento y una respuesta citada."
            ),
            "anchor": "__opener__",
        },
        {
            "id": "planner-tool-fanout",
            "caption": (
                "Una etapa de planificación abre cada pregunta en abanico hacia herramientas de búsqueda "
                "especializadas antes de normalizar la evidencia y sintetizar la respuesta."
            ),
            "alt_text": (
                "Un diagrama horizontal muestra una consulta que entra en un planificador, se ramifica hacia "
                "varias herramientas y converge en evidencia normalizada y síntesis."
            ),
            "anchor": "Planificación y abanico de herramientas",
        },
        {
            "id": "mcp-web-ui-comparison",
            "caption": (
                "MCP expone primitivas de recuperación en bruto a clientes externos; la interfaz web se "
                "ocupa del ciclo completo de planificación, ejecución y síntesis."
            ),
            "alt_text": (
                "Una comparación arquitectónica contrapone las herramientas directas de recuperación MCP "
                "con el canal integrado de planificación, ejecución y síntesis de la interfaz web."
            ),
            "anchor": "Interfaz web",
        },
    ]
    for base_figure, localized in zip(figures, localized_figures, strict=True):
        localized["source_caption_sha256"] = caption_sha256(
            base_figure["id"], base_figure["caption"]
        )
    translation = {
        "schema_version": 1,
        "language": "es",
        "source_language": "en",
        "locale": "es-AR",
        "fallback_locale": "es-ES",
        "base_copy_sha256": _edition_copy_sha256(base),
        "policy": {
            "register": "educated_castellano",
            "regional_preference": "restrained_argentinian",
            "fallback": "spain",
            "prohibited_fallbacks": ["generic_latin_american", "mexican", "caribbean"],
        },
        "title": "El conocimiento, donde vive",
        "subtitle": (
            "Recuperación, orquestación y evidencia útil a través de las herramientas donde ya ocurre el trabajo"
        ),
        "cover": {
            "headline": "El conocimiento, donde vive",
            "deck": (
                "Cómo un sistema útil de búsqueda interna encuentra la información sin obligarla a vivir "
                "en un solo lugar"
            ),
            "back_text": (
                "Los mejores sistemas de conocimiento no comienzan por trasladarlo todo. Comienzan por "
                "respetar dónde ocurre el trabajo y por hacer visible el camino entre la pregunta y la evidencia."
            ),
        },
        "editorial": {
            "path": "manuscript/editorial.md",
            "source_sha256": sha256(english_editorial),
        },
        "articles": [
            {
                "id": "how-we-built-our-knowledge-base",
                "title": "Cómo construimos nuestra base de conocimiento",
                "short_title": "base de conocimiento",
                "display_emphasis": "conocimiento",
                "author_note": (
                    "Isaac Tai, Daniel Kim y Mike Gao construyeron Cerebras Knowledge para la búsqueda interna."
                ),
                "manuscript": "articles/how-we-built-our-knowledge-base.md",
                "source_sha256": sha256(english_article),
                "figures": localized_figures,
            }
        ],
        "sections": [],
    }
    dump_yaml(TRANSLATION_DIR / "edition.yaml", translation)


if __name__ == "__main__":
    main()
