---
source_ids:
- why-software-factories-fail-f53679d7
- why-software-factories-fail-turning-the-lights-b-1312d1ad
- why-software-factories-fail-benchmarking-the-new-f1d9c04a
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

Todos corremos a poner la programación con IA en producción, y la sabiduría dominante dice que deberíamos escribir más ciclos. La promesa de la fábrica a oscuras es sucinta: tú eres el cuello de botella, los modelos ya son lo bastante buenos, el código es gratis y nadie tiene que leerlo. Gasta más tokens, añade revisores automáticos y avanza de 10 a 100 veces más rápido.

Mientras tanto, hay empresas que sufren caídas por percances de agentes de programación y, como dijo Matt Pocock, bases de código que se desmoronan más rápido de lo que nunca lo habían hecho. Faros AI informó de una menor calidad de revisión, más solicitudes de cambios fusionadas sin revisar y un aumento de incidentes y errores por desarrollador tras la adopción de herramientas de programación con IA. Ese informe es más una señal de correlación que una prueba irrefutable y verificable, pero la dirección parece válida según lo que he visto. Esto no trata de levantar por vibe coding un proyecto lateral desechable. Trata de problemas difíciles en bases de código complejas, donde el coste de una mala decisión llega meses después.

Ninguna cantidad de ingeniería de arneses ni de «loopsmaxxing» puede resolver lo que es, en el fondo, un problema de entrenamiento de los modelos. Los modelos son mucho mejores en tareas puntuales, pero no confío en que mantengan y mejoren la calidad de una base de código con el tiempo sin una buena dosis de dirección humana. No hay buenos benchmarks para esa capacidad.

## Por qué fracasa la fábrica a oscuras

Antes de la IA, los equipos ya usaban ciclos: decidir qué construir, anotarlo en un gestor, implementarlo, revisar la solicitud de cambios, desplegar, monitorizar y devolver a la cola lo que descubren los usuarios. Las fábricas agénticas sustituyen sobre todo «alguien construye la cosa» por «un agente construye la cosa». Construir baja de días a horas o minutos, mientras revisar sigue siendo caro; la revisión se vuelve el cuello de botella. La fábrica a oscuras la elimina y traslada la confianza a pruebas, entornos aislados, revisión automática, monitorización, despliegue gradual y respuesta de usuarios.

Lo intentamos en julio de 2025: agentes en segundo plano para el trabajo pequeño y mediano, sin lectura rutinaria del código. Al final apareció un problema que el agente no podía resolver. Tuve que volver a una base de código que llevaba tres meses sin leer mientras el sitio estaba caído y los usuarios estaban enfadados. La primera vez decidí que la velocidad justificaba el riesgo. Más o menos a la tercera, resultó más fácil reescribir desde cero; mi cofundador pasó dos semanas reconstruyendo los patrones a mano.

El fallo es la mantenibilidad: cambiar una parte empieza a amenazar con romper otra. Las pruebas pueden responder aprobado o suspenso en segundos, de modo que el aprendizaje por refuerzo optimiza millones de trayectorias contra ellas. El coste de una mala arquitectura aparece en semanas, meses, quizá incluso años, cuando un cambio de una línea debe repetirse en once sitios. No existe un oráculo igual de rápido y fiable para el buen diseño.

## No hay castigo por el mal diseño

Un benchmark puede preguntar si un agente corrigió un error sin romper las pruebas existentes. Si la batería pasa, el parche gana, aunque vuelva más difícil cambiar la base de código. Así se termina con try-catch alrededor de todo.

Empiezan a aparecer evaluaciones prometedoras con tareas más largas, recompensas compuestas, pruebas de mutación y reglas de calidad juzgadas por modelos. Pero si un modelo pudiera reconocer con fiabilidad el buen código, quizá lo habría escrito bien desde el principio. Más tokens y agentes revisores elevan el suelo; no elevan el techo más allá de lo aprendido por el modelo. La frontera mejora; el bombo va por delante de la disciplina.

## El oráculo llega por puntos de control

Aquella afirmación sobre los benchmarks no era del todo cierta. SlopCodeBench revela los requisitos punto de control a punto de control. El modelo nunca ve el problema completo de antemano; debe hacer evolucionar su propio código mientras siguen vigentes todas las pruebas de regresión heredadas. Lo bueno de este benchmark es que no está saturado: en el momento de la ejecución, los mejores modelos disponibles, GPT-5.4 y Opus 4.6, obtuvieron el 11 y el 17 por ciento de aprobados estrictos, respectivamente.

Ejecuté Opus 4.8, Sonnet 5 y Opus 5 sobre tres problemas —fácil, mediano y difícil—, diecisiete puntos de control en total. Recibieron los mismos prompts y una ventana de contexto nueva en cada punto. Un aprobado estricto exigía superar todas las pruebas nuevas y heredadas en una evaluación de caja negra reservada.

Ningún modelo terminó limpio un desafío, ni siquiera el fácil. Opus 5 superó cuatro de diecisiete puntos de control, el 24 por ciento; Opus 4.8 y Sonnet 5 superaron uno cada uno. Tres de los aprobados de Opus 5 abrieron un único problema. Ganó en términos técnicos, pero nadie compró suficiente corrección. Evidentemente, este subconjunto pequeño no permite afirmar de forma definitiva que gastar más dinero conduzca a tasas de aprobado más altas. El titular es que ese 24 por ciento no supera por mucho el 17 por ciento de aprobados estrictos que Opus 4.6 obtuvo en el artículo original.

Las medidas de calidad son repetibles, pero no me convence que se pueda eliminar el *slop* con un linter. Todos los modelos aumentaron la verbosidad y la complejidad. Opus 5 escribió cinco veces más funciones que Opus 4.8, aunque su volumen de código de producción fue más bien 1,8 veces mayor. En duplicación, sin embargo, Opus 5 se mantiene prácticamente plano, de 2,41 a 2,64, así que si confías en la duplicación como métrica de referencia, podrías sostener que sí mejoramos algo en los últimos tres meses. Es un gran condicional, eso sí, y la mayoría de los expertos en arquitectura de software coincidiría en que no es blanco o negro. La mayoría de las 41 métricas no separó con claridad a los modelos; ninguna métrica aislada es un indicador establecido de facilidad de cambio.

## ¿Puede el siguiente modelo heredar el diseño?

El mejor oráculo es la trayectoria: ¿pueden las primeras decisiones de diseño sobrevivir a requisitos posteriores? El coste, el tiempo y los tokens también pueden importar; una base de código bien estructurada debería abaratar el siguiente cambio. Una prueba aún más incisiva dejaría que un modelo de frontera construyera los puntos de control uno a siete y después pediría a un modelo menor que implementara el octavo. Si puede heredar y ampliar el diseño, ese resultado pertenece al modelo que dejó atrás la base de código.

SlopCodeBench convierte mis sensaciones en una señal: en trabajos con forma real, todavía no se puede confiar en que los modelos actuales operen a oscuras sin dirección. Si superan el 80 por ciento en un benchmark bien reservado como este, me sentiré mucho mejor apagando la luz. Cuándo ocurra importa menos que saber que está ocurriendo.

## Volver a encender la luz

Por ahora, el juez eres tú: devuelve la revisión de código, pero busca ventaja antes de la solicitud de cambios, cuando corregir el rumbo es barato. Usamos IA para adelantar la alineación en cuatro fases: revisión de producto, arquitectura del sistema, diseño del programa y cortes verticales.

Una revisión de producto fija el dolor del usuario, qué resultado contaría como éxito y, cuando sirve, una maqueta aproximada. Resérvala para trabajos donde malinterpretar la intención saldría caro.

La arquitectura del sistema alinea servicios, endpoints, esquemas, colas, almacenes y flujo de datos sin decidir la forma interna del código. Revísala con quien revisará la solicitud de cambios; disentir aquí cuesta menos que rehacer.

## Diseña el programa antes de que el agente cocine

La arquitectura no basta. Antes de implementar, baja al diseño del programa: tipos, firmas de métodos, distribución de archivos y pilas de llamadas. El pseudocódigo, los árboles de llamadas y los diffs de archivos hacen visibles las decisiones. El modelo prepara el borrador; tú discutes con él antes del costoso momento de revisar código.

Construye cortes verticales en vez de planes horizontales. Los modelos avanzan por capas —base de datos, servicios, API, interfaz— y no dejan nada tangible hasta el final. Prefiero una franja de extremo a extremo: servir datos simulados, consumirlos en la interfaz, probarlos y después conectar servicios, almacenamiento, lógica y manejo de errores.

Cuando el código me importa mucho, o cuando dudo de la capacidad del modelo para hacer un buen trabajo en esta parte de la base de código, reviso también cada corte. Comprobar entre 100 y 200 líneas y corregir el rumbo cuesta menos que llegar al otro lado de 2.000 líneas sin saber qué está roto. Normalmente envío al modelo entre uno y tres cortes cada vez.

## Trabaja dentro de las restricciones

El proceso es proporcional. Yo diría que cerca del 40 por ciento de las tareas aún puede resolverse de una vez o con comentarios ligeros. El trabajo mediano reúne producto y sistema en un plan; los cambios grandes reciben la secuencia completa, salvo las fases que no correspondan.

Quería pedir software de producción, dejar cocinar a los modelos y no volver a leer código. Pero lo que he intentado exponer aquí no son más que restricciones: apréndelas, desarrolla intuición, optimiza y busca ventaja. Quizá persigas promesas de multiplicar por 100 cuando podrías avanzar dos o tres veces más rápido y con seguridad.

Lee el maldito código.
