---
source_id: agent-swarms-and-the-new-model-economics-8b346f57
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

A comienzos de este año, un enjambre construyó un navegador desde cero: una prueba útil, pero lejos de ser software pulido. Después quisimos diseñar el sistema con intención. Volvimos a una tarea que al enjambre anterior le había costado —implementar SQLite en Rust desde su documentación— y el arnés nuevo lo superó con todas las combinaciones de modelos. Más agentes no fueron la variable decisiva: la topología, la memoria, la coordinación y la división entre planificación y ejecución cambiaron la calidad y el coste.

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

Por eso un enjambre se parece a un compilador. Los planificadores analizan una meta en árboles de tareas y la reducen paso a paso a trabajo ejecutable. La diferencia es que un compilador preserva el significado de forma determinista, mientras que el enjambre es probabilístico en cada etapa. El árbol, la memoria compartida, la coordinación, las lentes de revisión y el entorno de verificación existen para cerrar esa brecha semántica.
