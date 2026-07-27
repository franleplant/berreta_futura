---
source_ids:
- why-software-factories-fail-f53679d7
- why-software-factories-fail-turning-the-lights-b-1312d1ad
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
source_body_sha256:
  why-software-factories-fail-f53679d7: d33fdc4b32b52fc15f7182bdcd5745446577528e319f95736b29305f233b1299
  why-software-factories-fail-turning-the-lights-b-1312d1ad: e2b15724ecd99d724de29cd01cb5920ff35ead723a0da2e53629304307524939
---

Todos corremos a poner la programación con IA en producción, y la sabiduría dominante dice que deberíamos escribir más ciclos. La promesa de la fábrica a oscuras es sucinta: tú eres el cuello de botella, los modelos ya son lo bastante buenos, el código es gratis y nadie tiene que leerlo. Gasta más tokens, añade revisores automáticos y avanza de 10 a 100 veces más rápido.

Mientras tanto, hay empresas que sufren caídas por percances de agentes de programación y bases de código que se desmoronan más rápido que nunca. Faros AI informó de una menor calidad de revisión, más solicitudes de cambios fusionadas sin revisar y un aumento de incidentes y errores por desarrollador tras la adopción de herramientas de programación con IA. Es correlación, no una prueba irrefutable, pero la dirección parece válida. Esto no trata de levantar por vibe coding un proyecto lateral desechable. Trata de problemas difíciles en bases de código complejas, donde el coste de una mala decisión llega meses después.

Ninguna cantidad de ingeniería de arneses ni de «loopsmaxxing» puede resolver lo que es, en el fondo, un problema de entrenamiento de los modelos. Los modelos son mucho mejores en tareas puntuales, pero no confío en que mantengan y mejoren la calidad de una base de código con el tiempo sin dirección humana. No hay buenos benchmarks para esa capacidad.

## Por qué fracasa la fábrica a oscuras

Antes de la IA, los equipos ya usaban ciclos: decidir qué construir, anotarlo en un gestor, implementarlo, revisar la solicitud de cambios, desplegar, monitorizar y devolver a la cola lo que descubren los usuarios. Las fábricas agénticas sustituyen sobre todo «alguien construye la cosa» por «un agente construye la cosa». Construir baja de días a horas o minutos, mientras revisar sigue siendo caro; la revisión se vuelve el cuello de botella. La fábrica a oscuras la elimina y traslada la confianza a pruebas, entornos aislados, revisión automática, monitorización, despliegue gradual y respuesta de usuarios.

Lo intentamos en julio de 2025: agentes en segundo plano para el trabajo pequeño y mediano, sin lectura rutinaria del código. Al final apareció un problema que el agente no podía resolver. Tuve que volver a una base de código que llevaba tres meses sin leer mientras el sitio estaba caído y los usuarios estaban enfadados. La primera vez decidí que la velocidad justificaba el riesgo. Más o menos a la tercera, resultó más fácil reescribir desde cero; mi cofundador pasó dos semanas reconstruyendo los patrones a mano.

El fallo es la mantenibilidad: cambiar una parte empieza a amenazar con romper otra. Las pruebas pueden responder aprobado o suspenso en segundos, de modo que el aprendizaje por refuerzo optimiza millones de trayectorias contra ellas. El coste de una mala arquitectura aparece en semanas, meses o años, cuando un cambio de una línea debe repetirse en once sitios. No existe un oráculo igual de rápido y fiable para el buen diseño.

## No hay castigo por el mal diseño

Un benchmark puede preguntar si un agente corrigió un error sin romper las pruebas existentes. Si la batería pasa, el parche gana, aunque vuelva más difícil cambiar la base de código. Así se termina con try-catch alrededor de todo.

Empiezan a aparecer evaluaciones prometedoras con tareas más largas, recompensas compuestas, pruebas de mutación y reglas de calidad juzgadas por modelos. Pero si un modelo pudiera reconocer con fiabilidad el buen código, quizá lo habría escrito bien desde el principio. Más tokens y agentes revisores elevan el suelo; no elevan el techo más allá de lo aprendido por el modelo. La frontera mejora; el bombo va por delante de la disciplina.

## Volver a encender la luz

Por ahora, el juez eres tú: devuelve la revisión de código, pero busca ventaja antes de la solicitud de cambios, cuando corregir el rumbo es barato. Usamos IA para adelantar la alineación en cuatro fases: revisión de producto, arquitectura del sistema, diseño del programa y cortes verticales.

Una revisión de producto fija el dolor del usuario, qué resultado contaría como éxito y, cuando sirve, una maqueta aproximada. Resérvala para trabajos donde malinterpretar la intención saldría caro.

La arquitectura del sistema alinea servicios, endpoints, esquemas, colas, almacenes y flujo de datos sin decidir la forma interna del código. Revísala con quien revisará la solicitud de cambios; disentir aquí cuesta menos que rehacer.

## Diseña el programa antes de que el agente cocine

La arquitectura no basta. Antes de implementar, baja al diseño del programa: tipos, firmas de métodos, distribución de archivos y pilas de llamadas. El pseudocódigo, los árboles de llamadas y los diffs de archivos hacen visibles las decisiones. El modelo prepara el borrador; tú discutes con él antes del costoso momento de revisar código.

Construye cortes verticales en vez de planes horizontales. Los modelos avanzan por capas —base de datos, servicios, API, interfaz— y no dejan nada tangible hasta el final. Prefiero una franja de extremo a extremo: servir datos simulados, consumirlos en la interfaz, probarlos y después conectar servicios, almacenamiento, lógica y manejo de errores.

Cuando el código importa o el modelo trabaja en una zona difícil del sistema, revisa también cada corte. Comprobar entre 100 y 200 líneas y corregir el rumbo cuesta menos que llegar al otro lado de 2.000 líneas sin saber qué está roto. Normalmente envío al modelo entre uno y tres cortes cada vez.

## Trabaja dentro de las restricciones

El proceso es proporcional. Alrededor del 40 por ciento de las tareas todavía puede resolverse de una vez o con comentarios ligeros. El trabajo mediano puede reunir producto y sistema en un solo plan. Los cambios grandes o arriesgados reciben la secuencia completa, omitiendo las fases que no correspondan.

Yo quería el mundo donde pudiéramos pedir software de producción, dejar cocinar a los modelos y no volver a leer código. Pero estas son restricciones, no un argumento contra la IA. Apréndelas, desarrolla intuición, optimiza dentro de ellas y busca ventaja. Es posible perder el tiempo persiguiendo promesas de 10 a 100 veces cuando podrías avanzar de dos a tres veces más rápido y con seguridad.

Lee el maldito código.
