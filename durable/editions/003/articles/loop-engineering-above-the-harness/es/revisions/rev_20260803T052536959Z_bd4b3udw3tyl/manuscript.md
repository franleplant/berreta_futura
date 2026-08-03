---
source_id: loop-engineering-f0ddfd76
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
source_body_sha256: 624d44585e591681ee548b14eab033af3804c66e68cae256d1b3e626203c86f0
---

La ingeniería de ciclos consiste en reemplazarte como la persona que escribe los prompts del agente: diseñas el sistema que lo hace en tu lugar, una meta recursiva donde la IA itera hasta terminar. Creo que este puede ser el futuro de cómo trabajamos con agentes de programación; pero es temprano, soy escéptico y hay que vigilar el coste en tokens.

Peter Steinberger dijo hace poco: «Ya no deberías estar escribiendo prompts para tus agentes de programación. Deberías estar diseñando los ciclos que les escriben los prompts». En la misma línea, Boris Cherny, responsable de Claude Code en Anthropic, dijo: «Ya no le escribo prompts a Claude. Tengo ciclos corriendo que le escriben prompts a Claude y van decidiendo qué hacer. Mi trabajo es escribir ciclos».

Durante dos años escribiste un prompt, leíste lo que volvía, escribiste lo siguiente. Esa parte se terminó, más o menos, o al menos algunos lo creen. Ahora un sistema pequeño encuentra el trabajo, lo reparte, lo comprueba, registra lo hecho, decide qué sigue: el arnés de agentes un piso más arriba, alimentándose solo.

Esto ya no es realmente una cuestión de herramientas. Hace un año un ciclo era una pila de bash que mantenías para siempre; ahora las piezas vienen dentro de los productos, con la misma forma en Codex y en Claude Code, así que diseñas un ciclo que funciona en cualquiera de los dos.

## Las cinco piezas, y después las notas

Un ciclo necesita cinco cosas y un lugar donde recordar: automatizaciones que hacen descubrimiento y triaje según un calendario; worktrees para que los agentes paralelos no se pisen; skills para lo que el agente, si no, adivinaría; plugins y conectores hacia tus herramientas; y subagentes, para que uno tenga la idea y otro la compruebe.

La sexta es la memoria: un archivo markdown o un tablero de Linear, cualquier cosa fuera de la conversación que guarde lo hecho y lo que sigue. El modelo olvida todo entre ejecuciones, así que la memoria vive en disco. El agente olvida; el repositorio, no.

Las automatizaciones son lo que convierte un ciclo en un ciclo de verdad, no en una ejecución que hiciste una vez. Codex las programa en una pestaña de Automatizaciones; Claude Code usa /loop, cron, hooks o GitHub Actions. Y /goal, en ambos, corre hasta que una condición que escribiste se cumple: en Claude Code, un modelo pequeño aparte la comprueba en cada turno, para que el agente que escribió el código no sea quien lo califica.

Los worktrees impiden que lo paralelo se convierta en caos: un directorio de trabajo separado en su propia rama, de modo que las ediciones de un agente literalmente no pueden tocar la copia de otro. Pero el techo sigues siendo tú: tu capacidad de revisión decide cuántos puedes correr, no la herramienta.

Una skill es la manera de dejar de reexplicar el proyecto en cada sesión: una carpeta con un SKILL.md, tu intención escrita una sola vez, donde el agente la lee en cada ejecución. Sin skills, el ciclo rederiva tu proyecto desde cero en cada vuelta; con skills, se acumula.

Un ciclo que solo ve el sistema de archivos es un ciclo diminuto. Los conectores, construidos sobre MCP, le permiten leer tu gestor de incidencias, escribir a Slack: la diferencia entre «aquí está el arreglo» y un ciclo que abre la solicitud de cambios y avisa al canal cuando la CI se pone en verde.

Los subagentes mantienen separados al que hace y al que comprueba: el modelo es demasiado indulgente calificando sus propios deberes, y un segundo agente atrapa aquello de lo que el primero se convenció. El ciclo corre mientras no miras, así que un verificador en el que confíes es la única razón por la que puedes alejarte.

## Cómo es un ciclo por dentro

Una automatización corre cada mañana; una skill de triaje lee los fallos de CI, las incidencias y los commits de ayer. Cada hallazgo que vale la pena recibe un worktree aislado, donde un subagente redacta el arreglo y un segundo lo revisa; lo que el ciclo no puede manejar aterriza en mi bandeja de triaje. El archivo de estado recuerda qué se intentó y qué queda abierto, así la ejecución de mañana retoma donde paró la de hoy. Lo diseñaste una vez; no escribiste ningún prompt. La idea de Steinberger hecha realidad.

## Lo que el ciclo todavía no hace por ti

El ciclo cambia el trabajo, no te borra de él. La verificación sigue siendo tuya: «terminado» es una afirmación, no una prueba. La deuda de comprensión crece más rápido cuanto más código despacha el ciclo que tú no escribiste, salvo que leas lo que hizo. Y la postura cómoda es la peligrosa: la rendición cognitiva. Diseñar el ciclo con criterio es la cura; diseñarlo para no pensar es el acelerante.

Creo que esto es un anticipo de cómo evolucionará nuestro trabajo; pero si dejara de revisar el código yo mismo, o si dependiera por completo de los ciclos, la calidad sufriría. Monta tus ciclos; pero escribirles prompts directamente a tus agentes también es eficaz: es cuestión de equilibrio.

Dos personas pueden construir exactamente el mismo ciclo y obtener resultados opuestos: una para avanzar más rápido en un trabajo que comprende a fondo, la otra para evitar comprenderlo en absoluto. El ciclo no nota la diferencia. Tú sí.

Eso es lo que hace el diseño de ciclos más difícil que la ingeniería de prompts, no más fácil. La idea de Cherny no es que el trabajo se volvió más fácil. Es que el punto de apalancamiento se movió.

Construye el ciclo. Pero constrúyelo como alguien que piensa seguir siendo el ingeniero, no solo la persona que aprieta el botón.
