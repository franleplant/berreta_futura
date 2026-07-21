---
source_id: agent-swarms-and-the-new-model-economics-8b346f57
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

Hemos estado experimentando hasta dónde pueden escalar los enjambres de agentes de programación. Un arnés nuevo, construido a partir de la documentación de SQLite, superó nuestro enfoque anterior con todas las configuraciones de modelos. El resultado llamativo no fue solo que ayudaran más agentes. La topología, la memoria, el control de versiones y la separación entre planificación y ejecución cambiaron tanto la calidad como el coste.

## Los árboles preservan el contexto

Nuestro enjambre forma un árbol. Un planificador capaz divide el trabajo y lo delega; trabajadores más baratos ejecutan tareas acotadas. El planificador nunca implementa y el trabajador nunca planifica. Esta separación importa menos por la velocidad paralela que por la eficiencia de contexto: cada agente ve la memoria necesaria para su función, en vez de arrastrar todo el proyecto hasta perder el rumbo.

La coordinación exigió infraestructura. El experimento anterior con un navegador producía alrededor de mil commits por hora; el de SQLite podía acercarse a mil por segundo, así que construimos una capa propia de control de versiones. Documentos de diseño compartidos, referencias de compilación, reconciliadores neutrales, límites a archivos gigantes y roturas controladas redujeron los diseños divergentes y los conflictos. Varias revisiones independientes costaron poco y ofrecieron un rendimiento inusual.

## Un manual como mundo

Para SQLite, los agentes recibieron un manual de 835 páginas, pero no el código fuente, las pruebas, el binario ni acceso a internet. Los evaluamos contra millones de casos de sqllogictest y reservamos un conjunto para proteger el resultado final. Cuatro configuraciones de planificador y trabajadores alcanzaron entre el 73 y el 85 por ciento tras cuatro horas con el arnés nuevo y más tarde llegaron al 100 por ciento; el arnés anterior osciló entre el 11 y el 77 por ciento en el mismo punto.

Las trazas explican la diferencia. El sistema anterior hizo decenas de miles de commits tempranos, pero atravesó unos setenta mil conflictos, creó implementaciones SQL solapadas y acumuló mucho más código. El nuevo hizo menos cambios y más coherentes. Una ejecución correcta llegó al cien por cien con 4.645 líneas, mientras otra anterior necesitó 19.013 para alcanzar el 97 por ciento.

## Los modelos son funciones, no una única factura

Los costes fueron desde unos 1.339 dólares para un híbrido con Opus como planificador hasta 10.565 para una configuración íntegra con GPT-5.5. Los trabajadores consumieron al menos el 69 por ciento de los tokens y más del 90 por ciento en la mayoría de las ejecuciones. El razonamiento de frontera importó en algunos momentos de planificación; el grueso de la ejecución pudo usar modelos más baratos. En una comparación, los trabajadores GPT-5.5 costaron 9.373 dólares y los Composer, 411.

La consecuencia es arquitectónica y económica: hay que elegir modelos por función. El criterio adicional de un planificador puede justificar su precio porque da forma a miles de acciones más baratas. Un planificador nominalmente económico todavía puede elevar la factura total si su descomposición obliga a los trabajadores a consumir muchos más tokens.

## Las especificaciones se vuelven prompts

A medida que mejoran los agentes, la unidad entregada al modelo asciende de línea a bloque, archivo, función y finalmente especificación. Un enjambre empieza a parecerse a un compilador probabilístico: la intención se convierte en tareas, las tareas en trabajo coordinado y la verificación cierra la distancia semántica. El insumo escaso no es la generación de código. Es una intención precisa sostenida por un entorno que permita conservarla entre muchos agentes.
