---
source_id: how-we-built-our-knowledge-base-e986baa0
content_mode: selected_extracts
label: EXTRACTOS SELECCIONADOS
---

Los empleados le hacen más de 15.000 preguntas por día a nuestra base de conocimiento interna. Desde su lanzamiento, hace 3 meses, se ha convertido en una de las herramientas internas con mayor adopción de la empresa. La usan personas, automatizaciones y agentes.

En Cerebras, nuestros equipos trabajan en operaciones de centros de datos, diseño de chips, hardware, entrenamiento, inferencia, plataforma en la nube y mucho más. Con cientos de nuevos empleados que se incorporan cada año, nuestros canales de comunicación se llenaban de las mismas preguntas:

Construimos Cerebras Knowledge para ayudar a conectar a las personas y los sistemas con información útil.

## Encontrar los datos donde están

Encontrar información dentro de una organización es difícil. Los datos están dispersos entre herramientas y, aproximadamente cada trimestre, alguien propone la misma solución brillante: registremos todo en una plataforma para que la información esté en un único lugar. El sueño de una única fuente de verdad, por supuesto, rara vez funciona en la práctica.

La información se genera allí donde resulta conveniente y ergonómico: ediciones sugeridas en un documento, hilos de Slack, referencias de código en GitHub y metadatos de estado en Jira. Estas plataformas están hechas a medida de sus dominios específicos y optimizadas durante años de ingeniería de producto y análisis. Debatir una solicitud de cambios en Google Docs sería una experiencia espantosa.

Por eso nos propusimos diseñar un sistema que exigiera cambios mínimos en los comportamientos existentes. Del lado de la recopilación, eso implicaba extraer los datos directamente de cada plataforma.

## Anatomía de una base de conocimiento

Nuestra base de conocimiento ofrece tres cosas:

En el centro hay una única tabla de Postgres que contiene embeddings, resúmenes en bruto y metadatos de numerosas fuentes. El sistema ingiere datos de toda la empresa de forma continua y mantiene un almacén listo para consultas.

Queríamos una interfaz de datos sencilla que pudiera funcionar con la mayoría de las formas de datos. También queríamos que otros desarrolladores de Cerebras pudieran crear conectores a medida. El resultado es deliberadamente simple: cada fuente, desde hilos de Slack hasta netlists, aterriza en la misma tabla de embeddings, y todo lo que entra en ella puede consultarse de inmediato mediante la misma interfaz:

Cada fuente define qué son los datos, cómo conectarse a ellos y con qué frecuencia obtenerlos. Cada fila de embeddings resultante respeta la misma interfaz, ya provenga de Slack, de un repositorio de código, de un sistema documental o de una base de datos personalizada.

## Slack

Slack era la fuente de datos más importante para la que necesitábamos diseñar. Allí ocurren las conversaciones de ingeniería más actualizadas de toda la empresa.

## Cómo procesamos conversaciones no estructuradas de Slack

Al principio probamos si bastaban embeddings sencillos sobre texto en bruto. Pronto comprobamos que la búsqueda vectorial por sí sola era insuficiente para encontrar todos los datos relevantes.

Necesitábamos un enfoque híbrido. Construimos la ingesta de Slack para que cada hilo pudiera recuperarse mediante varias técnicas de búsqueda a la vez, donde cada técnica compensara las debilidades de las demás:

## Planificación y abanico de herramientas

Para cada consulta, primero ejecutamos una breve etapa de planificación en la que un LLM decide qué herramientas y fuentes de datos probablemente importen. Las herramientas principales:

- subsystem_index: resúmenes por archivo producidos por un LLM.

- search: el canal vectorial unificado que abarca Slack, la wiki, el código y otras fuentes indexadas, combinadas y reordenadas internamente.

- search_slack: recuperación directa desde Slack.

- search_code: ripgrep sobre los repositorios de código fuente.

- recent_prs: solicitudes de cambios recientes relevantes para la pregunta.

- who_knows: personas con experiencia demostrada en un tema.

El planificador trabaja con una descripción compacta de lo que hemos indexado: qué proyectos existen, qué fuentes están disponibles en cada proyecto y para qué tipo de respuestas sirve cada una. A partir de la consulta y el alcance activo del usuario, emite selecciones de herramientas que el ejecutor distribuye en paralelo, normaliza en un formato de evidencia común y entrega a un LLM de síntesis final.(4)

## Reordenamiento

Un documento puede aparecer cerca del primer puesto solo porque comparte vocabulario con la consulta, aunque responda otra pregunta. Antes de reordenar, combinamos las listas incompatibles de los recuperadores mediante fusión recíproca de rangos, o RRF. Para cada documento, sumamos peso / (60 + posición) por cada lista en la que aparece, con un peso predeterminado de 1,0 y una constante de suavizado de 60.

Enviamos la consulta original y esos candidatos a un pequeño modelo de reordenamiento. Asigna a cada documento una puntuación de cero a diez y conservamos los diez mejores.(6)

El resultado de la búsqueda es, por tanto, un rico paquete de evidencia: resultados fusionados desde distintos recuperadores, deduplicados en el nivel de la fuente, reordenados respecto de la pregunta real y, solo entonces, ampliados con el contexto circundante.

## MCP

En la integración con MCP exponemos los componentes básicos de recuperación como herramientas directas, en lugar de esconderlos detrás de un único punto de acceso de «responde esta pregunta». Estas herramientas son deliberadamente sencillas y evitan los LLM en la medida de lo posible, para que los clientes puedan consultarlas con rapidez y a bajo coste.(5)

Cada herramienta MCP corresponde a una primitiva de recuperación subyacente, como search_slack, search_code, search o who_knows. Sus entradas y salidas son acotadas, estructuradas y estables, por lo que cualquier cliente o agente puede invocarlas sin incorporar más lógica de orquestación dentro de la herramienta.

Claude Code, o cualquier agente compatible con MCP, se convierte en el motor de orquestación. Decide qué herramientas llamar, en qué orden y cómo reunir los resultados en una respuesta final o una edición de código. La capa de recuperación no depende de esas decisiones del LLM para atender las solicitudes.

## Interfaz web

En la interfaz web existen las mismas herramientas, pero están conectadas a un canal de consulta completo que se ejecuta de principio a fin para cada pregunta del usuario. El agente de la interfaz se ocupa de las etapas de planificación y ejecución.

Síntesis: una etapa final con un LLM recibe el paquete tipado de evidencia y la pregunta original; después produce la respuesta que se muestra en la interfaz, con citas, salvedades y síntesis entre fuentes.

Desde la perspectiva del usuario, la interfaz web es simplemente «hacer una pregunta y obtener una respuesta». Por debajo, ejecuta el mismo patrón planificador → ejecutor → sintetizador que los clientes MCP pueden recrear de forma explícita.

## Reflexiones finales

En definitiva, la base de conocimiento funciona porque encuentra a las personas allí donde ya vive la información, en lugar de obligar a meterlo todo en un sistema rígido. Al combinar distintas técnicas de búsqueda, podemos hacer aflorar evidencia con rapidez. El resultado es una experiencia de búsqueda lo bastante flexible para los datos reales de una empresa, pero lo bastante estructurada para seguir siendo útil mientras Cerebras crece.
