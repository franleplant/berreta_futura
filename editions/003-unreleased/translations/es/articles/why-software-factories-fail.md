---
source_id: why-software-factories-fail-f53679d7
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
source_body_sha256: d33fdc4b32b52fc15f7182bdcd5745446577528e319f95736b29305f233b1299
---

Todos corremos a poner la programación con IA en producción, y la sabiduría dominante dice que deberíamos escribir más ciclos. StrongDM contó su fábrica de software a oscuras, donde ningún humano lee código y ningún humano escribe código. La narrativa: tú eres el cuello de botella, los modelos ya son lo bastante buenos, el código es gratis, basta con despachar más cosas. Esta gente es tremendamente inteligente, pero la lectura más cínica: otra excusa para bombear más dinero de capital de riesgo en el cañón de bazofia.

Mientras tanto, empresas que no tienen por qué sufrir caídas por percances de agentes de programación están, en fin, sufriendo caídas por percances de agentes de programación, y las bases de código se desmoronan más rápido que nunca. Faros AI publicó un informe: desde que todos adoptamos estas herramientas, la calidad de la revisión cayó en picado, montones de solicitudes de cambios se fusionan sin revisión alguna y los incidentes y errores por desarrollador subieron con fuerza. Es correlación, no una prueba irrefutable, pero la dirección parece válida.

La gente te dirá que es cuestión de destreza: gasta más tokens, suelta la lectura del código. La promesa de toda esa cháchara de «basta con gastar más tokens» es, en síntesis: de 10 a 100 veces más rápido, con alta calidad y sin que nadie tenga que volver a hacer revisión de código. Lo que voy a intentar demostrarte es que ninguna cantidad de ingeniería de arneses ni de «loopsmaxxing» puede resolver lo que es, en el fondo, un problema de entrenamiento de los modelos.

Un apunte: esto no tiene nada que ver con el vibe coding; el resto va dirigido a quienes resuelven problemas difíciles en bases de código complejas, donde una base construida por agentes empieza a tambalearse a los tres a seis meses.

## Breve historia de la fábrica de software

El término se remonta a una conferencia de la OTAN en 1968, la misma que nos dio «ingeniería de software». En una fábrica típica de 2022, justo antes de la IA: las personas deciden qué construir, la tarea entra en un gestor de incidencias, alguien la construye, una solicitud de cambios recibe comprobaciones automáticas y una revisión humana, se despliega, la monitorización avisa a un ingeniero a las 3 de la madrugada y las quejas de los usuarios alimentan el gestor. Todavía no hemos llegado a la IA y ya hay varios ciclos en esta imagen.

Ahora cada empresa y su madre —Ramp, Stripe, WorkOS, Brex— ha explicado cómo montó una fábrica de agentes que despacha del orden del 75 por ciento de su código, cambiando «alguien construye la cosa» por «un agente construye la cosa». Construir baja a minutos u horas; revisar sigue llevando horas o días, así que la revisión es ahora el cuello de botella. Se acelera la revisión con revisión de código agéntica y pruebas de regresión, se canalizan los incidentes y la respuesta de los usuarios, y el trabajo queda reducido a dos preguntas: cuánto puedes meter en la cola y a qué velocidad puedes revisar lo que sale.

## La fábrica de software a oscuras

Dan Shapiro acuñó el término; Simon Willison escribió sobre la implementación de StrongDM: ya no leemos el código. ¿Ese pequeño y fastidioso paso de la revisión de código? No, gracias. Se elimina, se invierte en pruebas, entornos aislados, revisión automatizada, monitorización, despliegue gradual y señales de respuesta, y el trabajo queda reducido a una sola pregunta: ¿qué porción del océano queremos hervir? Voy a plantear algo potencialmente polémico: la fábrica a oscuras no funciona.

En julio de 2025 pasamos a oscuras del todo: agentes en segundo plano para todo lo pequeño y lo mediano. Encuentras un problema lo bastante enrevesado como para que el agente no pueda resolverlo, y te toca escarbar en la base de código que dejaste de leer hace tres meses, con tu sitio caído, tus usuarios furiosos y tú, desdichado, leyendo toda la bazofia de código que dejaste colar. La primera vez me lo sacudí de encima: el riesgo valía la velocidad. A la tercera, en noviembre, resultó más fácil reescribir desde cero, y mi cofundador pasó dos semanas desentrañando los patrones a mano.

Adonde quiero llegar es a esto: los modelos no pueden mantener y mejorar la calidad de una base de código con el tiempo, no sin una buena dosis de dirección humana. Por mantenibilidad me refiero a eso tan concreto de que se vuelve muy, muy difícil cambiar una parte de la base de código sin romper otra: la cirugía de escopeta de Martin Fowler.

¿Seguro que los modelos han mejorado desde entonces? Mucho mejores en problemas puntuales y en levantar por vibe coding un sitio de marketing; no mucho mejores en mejorar la calidad de una base de código, hasta donde alcanzo a ver. No puedo demostrarlo; tú tampoco: no hay buenos benchmarks de la capacidad de un modelo para mantener la calidad de una base de código. Trabaja un tiempo con agentes de programación, eso sí, y te queda la sensación: empeoran las cosas con el tiempo.

## No hay castigo por el mal diseño

Claude Code pasó de la nada a unos 9.000 millones de dólares de ingresos en menos de un año, aunque grandes agentes de línea de comandos —aider, cline, codebuff— lo precedieron con las mismas herramientas. La explicación canónicamente aceptada: Anthropic aplicó RL al modelo dentro del arnés, la primera vez que un laboratorio entrenó un modelo contra las herramientas exactas con las que se distribuiría. Construye un arnés sin poseer los pesos y estarás en desventaja frente a un equipo que posee ambos.

El RL de agentes de programación en sesenta segundos: se generan trayectorias de agente que resuelven un problema, se puntúan con un verificador, se actualizan los pesos para hacer más probables las trayectorias buenas y se repite millones de veces. La puntuación puede ser caprichosamente unidimensional.

Tomemos SWE-bench Multilingual: tareas de quince minutos extraídas de repositorios de código abierto, recompensadas con uno o cero: ¿arreglaste la cosa sin romper nada más? En una tarea real de fastlane, el arreglo humano eran dos líneas. El agente aplica parches desde un commit base y un informe de error; sus ediciones de archivos de prueba se descartan (hemos pillado a un modelo comentando en silencio la prueba que fallaba); encima van las pruebas del benchmark y la batería se ejecuta. Si pasan, ganamos; pero no hay castigo por erosionar la mantenibilidad de la base de código. Así se acaba con try-catch alrededor de todo.

Las pruebas dan respuesta en segundos; por eso el RL puede ejecutar millones de ciclos. La función de coste de la mala arquitectura se mide en semanas, meses, quizá años: la primera vez que alguien abre un archivo para un cambio de una línea y descubre que la misma edición vive ahora en once sitios. El mal diseño es lo único que los benchmarks actuales no pueden evaluar, y no me fío de que las mejoras en los benchmarks signifiquen que los modelos dejaron de llenar de bazofia las bases de código.

Mucha gente inteligente trabaja en esto; el bombo va por delante de la disciplina. SWE-Marathon puntúa tareas de unas 400 horas con un canal de recompensa compuesto; DeepSWE construye tareas que no pueden estar ya en el conjunto de entrenamiento; Frontier Code penaliza las pruebas que no fallan sobre el código previo al parche. Pero si un modelo pudiera distinguir con fiabilidad el buen código del malo, quizá habría escrito la versión buena desde el principio: el RL necesita un oráculo rápido, y la mantenibilidad no lo tiene. Más agentes de revisión y más tokens elevan el suelo, no el techo; el techo es lo que le enseñamos al modelo en el RL. Son las primeras evaluaciones que al menos intentan puntuar la mantenibilidad. Aun así, no apostaría mi base de código por ellas.

## Volver a encender la luz

Quizá un modelo futuro sencillamente entienda esto y podamos parar. Si quieres tirar prompts a la buena de Dios hasta que salga GPT-7, adelante; pero, al diablo con la lección amarga, tenemos problemas que resolver ahora. Cómo los resolvemos es la parte II. Atentos.
