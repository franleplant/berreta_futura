---
source_id: src-joshi-dsls-reliable-use-llms
content_mode: faithful_synthesis
source_body_sha256: 1effc901980761de45a8ff4b1a359558003ab561e8f6fba92b48bfbfbc61de27
rights_status: private_reference
---

Los modelos de lenguaje (LLM) pueden generar código a una velocidad extraordinaria, pero la velocidad no garantiza que el resultado exprese el diseño buscado. Sostengo que las abstracciones y los lenguajes específicos de dominio (DSL) proporcionan una estructura con límites claros: ayudan a las personas a descubrir un diseño junto con un LLM y luego ofrecen al modelo un vocabulario acotado y verificable con el cual aplicar ese diseño de manera confiable.

## Una especificación es una hipótesis inicial

Los sistemas grandes contienen muchas decisiones pequeñas que no pueden quedar resueltas por completo en una especificación previa. Durante la implementación aparecen restricciones, disyuntivas y casos límite. Por lo tanto, una especificación útil es una hipótesis que debe revisarse, no un plano terminado. El ciclo productivo es breve e iterativo: precisar la intención, generar un cambio que pueda revisarse, examinar qué revela e incorporar ese aprendizaje a la siguiente ronda.

Revisar código generado no equivale a escribirlo. La revisión puede confirmar que un fragmento se parece a la intención declarada y, aun así, eludir las decisiones que ponen de manifiesto un diseño: dónde corresponde una responsabilidad, qué límite debería ser público o cómo debería encajar una extensión. Los lenguajes y paradigmas de programación también determinan qué advierten quienes diseñan. Las implementaciones funcionales y las orientadas a objetos hacen visibles conceptos y tensiones diferentes.

Le asigno dos funciones al LLM. Durante el diseño, es un interlocutor para explorar ideas, vocabulario y posibles abstracciones. Una vez establecido ese vocabulario, se convierte en una interfaz de lenguaje natural para un sistema acotado.

## Por qué ayudan los lenguajes acotados

El diseño dirigido por el dominio construye un modelo compartido y un lenguaje ubicuo que un equipo puede usar tanto en el código como en la conversación. Un DSL añade una sintaxis deliberadamente limitada para expresar los conceptos y las operaciones del modelo. Entre los ejemplos conocidos se encuentran SQL, Mermaid, PlantUML, Graphviz y el YAML de Kubernetes. Son eficaces con los LLM precisamente porque reducen la cantidad de formas válidas de expresar una intención.

Un lenguaje de propósito general como Java admite muchas arquitecturas y expresiones idiomáticas. Un DSL pequeño elimina buena parte de esa variación, por lo que unos pocos ejemplos dentro del contexto suelen bastar para comunicar toda su superficie. Para un agente que opera en un ciclo de generación y comprobación, el lenguaje suele aportar otro componente crucial: un validador determinista, como un analizador sintáctico, un esquema, un comprobador de tipos o un compilador. El agente puede proponer una alternativa, recibir un error expresado en términos del dominio y corregirla sin pedirle a una persona que interprete el seguimiento de pila de un gran sistema generado.

La afirmación tiene límites. El lenguaje debe seguir siendo lo bastante pequeño como para poder mostrarlo con unos pocos ejemplos, y su modelo semántico debe encarnar decisiones de diseño sólidas. Diseñar y mantener un DSL tiene un costo inicial real. El beneficio es mayor en un dominio bien descompuesto y genuinamente acotado, respaldado por una validación determinista.

## De los diagramas a un modelo semántico

Primero construí una herramienta de presentaciones para enseñar sistemas distribuidos. Necesitaba convertir diagramas de secuencia de PlantUML en diapositivas de PowerPoint que avanzaran paso a paso. Un formato YAML compacto indica el nombre de un diagrama, un título y los pasos que deben revelarse. Con la herramienta y unos pocos ejemplos en contexto, un LLM puede traducir una petición en inglés al YAML exacto que acepta el generador.

Este ejemplo ya contiene las dos funciones. El LLM ayuda a diseñar los marcadores de pasos y el vocabulario de las diapositivas; una vez que existe el formato, convierte el lenguaje natural en una especificación válida. El YAML no es útil porque los modelos sean buenos, en términos generales, para producir sangrías. Es útil porque un programa define con exactitud qué significan los campos y rechaza todo lo que queda fuera de ese contrato.

Los dominios más complejos requieren un modelo semántico distinto de su sintaxis superficial. Los sistemas distribuidos son un ejemplo exigente porque los hilos, los relojes, las demoras de red, el almacenamiento, los reintentos y las distintas intercalaciones de fallos crean un espacio enorme de diseño y verificación. Pedirle a un modelo que genere un sistema entero deja abiertas todas esas decisiones en cada instrucción.

Mi entorno de trabajo [Tickloom](https://github.com/unmeshjoshi/tickloom) cierra gran parte de ese espacio. Los nodos ejecutan un ciclo de tick de un solo hilo. Cada tick hace avanzar un reloj lógico y procesa el trabajo en un orden fijo. Los mensajes son registros. Una abstracción `Replica` ya comprende pares, difusiones y cuórums. `Process`, `Network`, `Storage` y `Clock` definen las principales separaciones. Al fijar los hilos, el tiempo y la entrega, una instrucción puede concentrarse en la lógica del protocolo en lugar de inventar la infraestructura.

Por ejemplo, una petición de un almacén con cuórum en el que prevalezca la última escritura puede nombrar conceptos de Tickloom como `Replica`, `quorumRequest`, `countResponseIf`, `MessageType` y `Handler`. Esos nombres remiten a tipos y comportamientos concretos del código base. El modelo semántico se convierte en contexto ejecutable: el LLM completa un protocolo acotado sobre un sustrato que el equipo ya comprende.

## Un DSL para escenarios de fallo

Implementar un algoritmo distribuido es solo la mitad del problema. Los errores aparecen en ordenamientos concretos de los sucesos: una partición se recompone en el momento equivocado, los relojes se desvían o un cuórum de lectura se solapa con uno de escritura de una manera inesperada. Una prueba directa debe coordinar futuros y ciclos manuales de tick, lo que oculta la intención del escenario.

Por eso, Tickloom añade un DSL interno de escenarios. Su vocabulario describe servidores, clientes, escrituras, lecturas, particiones, cambios de hora, ticks y aserciones. La superficie declarativa se compila en una representación intermedia pura compuesta por pasos; un intérprete independiente ejecuta esos pasos sobre un clúster. La construcción, la representación y la ejecución se mantienen separadas.

Una vez que existe este lenguaje, la descripción en lenguaje natural de un fallo se corresponde estrechamente con código de escenario válido. El espacio de resultados posibles es mucho menor que el de los programas Java arbitrarios. El compilador del lenguaje anfitrión comprueba la sintaxis, el constructor de escenarios comprueba las reglas del dominio y la simulación determinista comprueba el comportamiento resultante. Los mensajes de error permanecen en el nivel del escenario, lo que hace que la corrección resulte útil tanto para el modelo como para quien realiza la revisión humana.

La cuestión más profunda es que no siempre hace falta una sintaxis personalizada. Las abstracciones claras ya forman un vocabulario capaz de dar fundamento a un modelo. Un DSL es el extremo más acotado de ese espectro. Antes de asumir el costo de un lenguaje nuevo, los equipos deberían preguntarse si los tipos con nombre, las interfaces estrechas, los ejemplos y los validadores ya ofrecen estructura suficiente.

## Dos fases, una sola fuente de verdad

En la primera fase, el LLM ayuda a dar forma a una abstracción o un DSL. Este trabajo sigue siendo iterativo porque la implementación revela conceptos ausentes y límites incómodos. El modelo puede sugerir alternativas y acelerar los experimentos, pero las personas siguen eligiendo el modelo semántico y aceptando la responsabilidad por él.

En la segunda fase, el lenguaje establecido se convierte en la interfaz estable. El modelo traduce la intención a su vocabulario; las herramientas deterministas analizan, validan, compilan y prueban el resultado. La confiabilidad procede menos de una instrucción mejor que de reducir los grados de libertad y hacer que los resultados incorrectos puedan detectarse a bajo costo.

Esto cambia qué se considera la fuente de verdad. Una instrucción en prosa es ambigua, difícil de combinar y endeble como artefacto de software duradero. Un DSL registra las decisiones del dominio en una forma que admite control de versiones, validación, comparación de diferencias y ejecución. Las instrucciones se convierten en peticiones prácticas dirigidas a ese modelo, en lugar de ser el modelo mismo. En un flujo de trabajo con un uso intensivo de LLM, el activo perdurable es la abstracción diseñada con cuidado y su validador: la parte del sistema que determina qué resultados son posibles, qué significan y cómo puede cualquiera saber que son correctos.
