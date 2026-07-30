---
source_id: eval-engineering-the-step-that-turns-a-200-model-9f6f868f
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

Ahora todos alquilan el mismo cerebro. El modelo disponible por unos pocos cientos de dólares al mes se parece al que puede usar una empresa con mil ingenieros. Eso debía nivelar el terreno. En cambio, hizo que la diferencia entre equipos que usan el mismo modelo dependa de lo que lo rodea.

Un agente de viajes respondió con un tipo de cambio, un pronóstico semanal y los horarios de un museo. El resultado era específico y parecía útil. También era inventado. La herramienta de búsqueda no había devuelto nada y el modelo llenó el vacío en silencio.

En cien sesiones reales, la calidad de las respuestas alcanzó el 83,9 por ciento, mientras que el respaldo en resultados reales de herramientas llegó al 32,3 por ciento. El agente escribía maravillosamente y decía la verdad aproximadamente un tercio de las veces.

## Qué es la ingeniería de evaluaciones

La evaluación se convierte en ingeniería cuando una puntuación cambia lo que hace el sistema a continuación. El trabajo no es un tablero junto al agente. Es la capa de control dentro del agente: determina si aceptar una transferencia, reintentar una llamada a una herramienta, cambiar un nodo, poner una rama en cuarentena, bloquear una arista, pedir una aclaración o enviar el trabajo a una persona.

El modelo es alquilado. El examinador es tuyo. Cada fallo de producción que conviertes en una prueba permanente conserva su utilidad después de que cambien el modelo, el framework de orquestación y el proveedor.

La secuencia es simple: primero bucles, luego grafos y después evaluaciones. Un bucle le da al agente otro intento. Un grafo le da un lugar adonde ir. Una evaluación decide qué arista puede tomar el resultado.

## El examinador que ya tienes

Muchos equipos suponen que la evaluación comienza con un contrato de plataforma y meses de preparación. Ese supuesto quedó anticuado.

En una comparación a ciegas, los investigadores reunieron cien trazas reales de agentes de voz, pidieron a un experto humano que etiquetara treinta y nueve tipos de fallos, ocultaron esas etiquetas y luego compararon sistemas de evaluación. Braintrust Loop recuperó el 87,2 por ciento de los fallos señalados por la persona. Codex con GPT-5.5 High llegó a un recall del 84,6 por ciento y una precisión del 82,8 por ciento. LangSmith alcanzó el 79,5 por ciento. Arize AX llegó a un recall del 74,4 por ciento con una precisión del 91,0 por ciento.

Un agente de programación general quedó por encima de dos plataformas especializadas. Luego, las plataformas comenzaron a empaquetar su conocimiento como skills instalables para los agentes de programación que la gente ya usa.

El punto operativo no es qué fila ganó. El conocimiento de evaluación se está volviendo portátil. Una herramienta puede extraer trazas de producción, otra puede preparar una evaluación y un agente de programación puede inspeccionar la aplicación, escribir evaluadores, ejecutar los casos y producir un informe. La primera evaluación útil ya no exige un plano de control nuevo.

Empieza con trazas reales. Extrae una muestra acotada, inspecciona la aplicación, identifica el fallo visible para el usuario y define qué significa el éxito antes de escribir el evaluador. El examinador debería conocer el sistema que juzga.

## Haz que la puntuación cambie la siguiente arista

Un número que nunca cambia el comportamiento es analítica.

Un bajo recall de contexto puede rechazar una transferencia. El mal uso de una herramienta puede activar un reintento o cambiar el nodo responsable. Una alucinación puede poner la rama en cuarentena. Un fallo de esquema puede bloquear una arista. Un riesgo de cumplimiento puede enviar la traza a revisión humana.

Estas son decisiones del grafo, no anotaciones de un informe. El evaluador debe devolver una salida estructurada que pueda usar el orquestador. También necesita calibración. Un juez barato puede filtrar ejecuciones rutinarias, mientras que los casos discutidos o de alto riesgo pasan a un juez más potente o a una persona.

No premies la forma de una respuesta. Una respuesta fluida, con títulos y citas, aún puede carecer de fundamento. Evalúa la propiedad que importa: si las afirmaciones se desprenden de la salida de las herramientas, si se eligió la herramienta correcta, si la respuesta satisface la tarea y si la ruta fue segura.

## Convierte ejecuciones fallidas en pruebas permanentes

Las pruebas inventadas con la imaginación protegen contra fallos que ya imaginaste. Las trazas de producción contienen los fallos que tu sistema realmente produjo.

Examina las trazas, identifica un fallo, construye una evaluación, mejora el agente y conserva la evaluación. Empieza con unas veinticinco trazas completas elegidas por su valor informativo: una ejecución reconocida como mala, una buena confirmada, una ruta inesperada, un reintento costoso o un fallo externo que el agente manejó mal.

La respuesta registrada no es la verdad. Una traza muestra lo que ocurrió, no lo que debería haber ocurrido. Escribe la rúbrica a partir de la tarea y la evidencia disponible. Separa los fallos externos de los fallos del agente. Un límite de frecuencia solo forma parte de tu evaluación cuando la reacción del agente ante ese límite fue incorrecta.

Cada caso necesita el contexto que podía ver el agente, la acción que tomó, la propiedad esperada y un evaluador que explique el fallo. Guarda los casos junto al sistema para que los cambios en prompts, herramientas, políticas y modelos puedan ejecutarse contra el mismo historial.

El resultado es un trinquete. Cada fallo se vuelve más difícil de repetir.

## Deja que la confianza gobierne la revisión

Un sistema de programación autónomo puede evaluar su propio pull request antes de pedir atención humana. La decisión de integración puede combinar comprobaciones automáticas, reglas de política, la trayectoria reciente de las evaluaciones, el riesgo del cambio y la confianza en el resultado generado.

Por encima del umbral, el sistema puede integrar. Por debajo, una persona recibe el cambio con la señal fallida ya identificada. La revisión empieza en el problema y no en la primera línea.

Esto debería comenzar en modo sombra. Puntúa cada cambio y no integres ninguno. Compara la barrera con los resultados reales de revisión y luego automatiza solamente la región de alta confianza. Mantén los bloqueos duros de política separados de las puntuaciones probabilísticas. Selecciona un pequeño porcentaje de trazas para una inspección más profunda, en vez de conservar todo para siempre.

El objetivo no es eliminar a las personas. Es gastar la atención humana donde se encuentran la incertidumbre y las consecuencias.

## Las primeras evaluaciones

Construye primero una evaluación de fidelidad: ¿la respuesta está respaldada por lo que devolvieron las herramientas? Después prueba la selección de herramientas, la finalización de tareas, la conformidad con el esquema y el cumplimiento de políticas. Agrega métricas de recuperación cuando el sistema dependa de búsquedas.

Mide la tasa de aprobación, el costo y la latencia. Conserva un conjunto de datos de fallos reales. Agrega un caso cada vez que el sistema te sorprenda.

El modelo será reemplazado. El grafo será reescrito. El examinador sobrevive a ambos porque contiene tu definición acumulada de comportamiento aceptable.

Todo fallo que no conviertas en una prueba permanente es un fallo que aceptaste volver a encontrar.
