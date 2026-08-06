---
source_id: why-harness-engineering-is-so-hard-fe732038
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

Cinco meses, 104 commits y una lección que se repite: la ingeniería de arneses es difícil.

Sobre casi todo proyecto construido sobre un gran modelo de lenguaje se instala una ilusión: que el modelo es el producto. Una llamada a la API, un prompt, una primera demo impresionante, y la parte difícil parece terminada. No lo está.

Lo difícil es convertir esa demostración en un comportamiento del que puedas depender: las mismas restricciones para todas las entradas, las ideas correctas sin derivas, sobrevivir a las actualizaciones del modelo, fallar de forma visible en lugar de silenciosa, una salida que pueda probarse aunque nunca sea perfectamente determinista.

Esa capa de comportamiento es buena parte de lo que entiendo por arnés: los prompts, ejemplos, esquemas, validadores, evaluaciones y salvaguardas entre un modelo probabilístico y la persona que usa tu producto. El modelo genera la salida; el arnés la hace utilizable.

Esto sigue sorprendiendo a ingenieros por lo demás excelentes. Llevo meses metido en ello; la mayor parte del dolor viene de hechos estructurales que parecen problemas corrientes de software, pero no lo son.

## No puedes escribir la prueba que quieres escribir

Tu instinto de pruebas es lo primero que se rompe. Cada práctica que has construido supone determinismo: con esta entrada, el código produce esta salida, y yo afirmo la igualdad. Dale a un modelo de lenguaje la misma entrada dos veces y obtendrás dos salidas distintas: unas pocas palabras de diferencia, pero suficientes para que la igualdad estricta sea inútil.

Esto me quitó el suelo bajo la estrategia de calidad. Puedes hacer aserciones sobre estructura e invariantes, pero ambas son más débiles de lo que los ingenieros acostumbran y dejan pasar salidas inesperadas. En lugar de una salida igual a una respuesta esperada, preguntas si el sistema satisface una rúbrica sobre una distribución de entradas y ejecuciones repetidas: un nivel de confianza, no una demostración.

El fallo, mientras tanto, es silencioso y gradual, no binario. El software corriente anuncia sus fallos; la salida de un modelo no se estrella. Un modelo correcto en un 95 por ciento y roto en un 5 por ciento produce una respuesta que parece bien, con el 5 por ciento erróneo entretejido en el 95 por ciento correcto. Las salidas más peligrosas casi aprueban: derivar respecto de una restricción, inventar un valor plausible en lugar de admitir ignorancia, obedecer la letra de una regla rompiendo su espíritu. Ninguna se estrella. Todas se despachan. No puedes atrapar lo que no puedes ver, así que buena parte de la ingeniería de arneses consiste en hacer visible lo invisible: comprobaciones que revelan la deriva, humanos en el ciclo donde la confianza es baja.

## Depuras prosa, no código

Cuando el arnés se rompe, el «código» culpable suele ser un párrafo de inglés; el único depurador es tu criterio. Una sola palabra puede ser el error: he pasado horas rastreando una regresión hasta un adjetivo que el modelo leyó como permiso para hacer algo que yo nunca pretendí. Un error de una palabra es invisible: desplaza el comportamiento del modelo unos grados, lo suficiente para corromper la salida en silencio. Razonas sobre un prompt como un escritor razona sobre un párrafo, por intuición: una destreza genuinamente distinta de la depuración.

El patrón de fallo más fiable es la trampa aditiva: algo se rompe y añades una regla al prompt. Pero el prompt que crece es la enfermedad, no la cura. Las reglas en lenguaje natural interactúan de manera impredecible: el arreglo de un fallo contradice un arreglo anterior; «nunca hagas X» hace que el modelo piense en X, y X aparece donde nunca aparecía; el modelo sobrerrestringido elige en silencio una regla que violar. He visto un prompt crecer de veinte líneas a doscientas hasta apenas poder producir algo bueno. El arreglo, todas las veces, fue restar —eliminar reglas, fusionar duplicados, imponer restricciones en el código—, y los saltos de calidad vinieron de borrar, no de añadir.

Un corolario: los ejemplos dirigen con más fuerza que las reglas. Escribe «no hagas X», incluye un ejemplo que hace X, y el modelo hará X. El ejemplo gana. Todo lo que hay en un prompt es un programa de comportamiento; ninguna parte es neutral y cada token empuja al modelo hacia algún lado.

## Los cimientos se reescriben solos

El modelo no es un cimiento estable. Los proveedores lo actualizan, a veces sin anuncio, y el comportamiento cambia. Tus defensas, afinadas para los modos de fallo del modelo antiguo, ahora protegen contra problemas que ya no ocurren mientras los nuevos quedan sin guardia. Con Opus 5, muchos cuentan que archivos de skills antes fiables sencillamente dejaron de funcionar.

Tus pruebas pueden estar en verde mientras tu producto retrocede: hacen aserciones contra el comportamiento del modelo antiguo, y el modelo se movió. Ninguna salida de emergencia del tipo «fija la versión» aguanta para siempre. Un arnés nunca está «terminado»; la respuesta honesta son prompts mínimos, validación que atrape la deriva y la humildad de esperar que la próxima actualización rompa algo que todavía no sabes nombrar.

Los ciclos de retroalimentación, además, son lentos y caros. Una llamada al modelo cuesta dinero, y una prueba de extremo a extremo puede llevar de minutos a horas. No puedes probar veinte variantes por fuerza bruta en un minuto; pruebas tres, esperas, lees con atención, pruebas una más. El gasto también engendra pruebas insuficientes: te convences de que un cambio es lo bastante pequeño como para saltarte la ejecución completa. Casi nunca lo es, y probar de menos un sistema probabilístico es la manera de despachar deriva.

## La dificultad es el sentido

El último dolor es social: nadie puede ver el trabajo. «Ingeniería de prompts» suena tan difícil como escribir un correo. El ajuste, las contradicciones eliminadas, los fallos silenciosos atrapados antes de salir: todo invisible. Hazlo visible a propósito —lleva registro de los fallos que atrapaste, mide la deriva que evitaste— y acepta que parte del valor nunca será legible para quienes te rodean.

Cada uno de estos dolores es estructuralmente difícil. Vienen del sustrato: un sistema probabilístico sin traza de pila, sin determinismo, sin contrato estable, sin separación entre «el programa» y «los datos con los que fue entrenado». No puedes eliminar esos hechos con ingeniería; solo puedes construir un arnés que los absorba.

Y eso, honestamente, es el foso. Si la ingeniería de arneses fuera fácil, el modelo sería el producto y cualquiera con una clave de API podría competir. Una aplicación real es difícil de construir por la misma razón por la que es difícil de copiar: convertir salida probabilística en algo despachable, fiable y probado es invisible, doloroso y no se transfiere leyendo tu prompt.

El dolor es el trabajo, y el trabajo es el foso.
