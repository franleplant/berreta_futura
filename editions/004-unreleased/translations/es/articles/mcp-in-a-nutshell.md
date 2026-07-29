---
source_id: architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

El Model Context Protocol define cómo una aplicación de IA intercambia contexto y acciones con programas externos. No define el uso del modelo, la planificación ni el contexto interno; define el límite.

El proyecto incluye la especificación, SDK, Inspector y servidores de referencia. Entender la arquitectura aclara las conexiones, lo que expone cada servidor y cómo una solicitud se vuelve acción.

## Host, cliente y servidor

Un host MCP es la aplicación de IA. Visual Studio Code, Claude Code o un asistente de escritorio pueden actuar como host.

El host crea un cliente por servidor. Cada cliente mantiene la conexión, descubre capacidades, envía solicitudes y devuelve resultados.

Un servidor MCP es un programa que ofrece contexto o acciones. Puede ejecutarse de forma local o remota.

Si Visual Studio Code conecta un servidor local de archivos y Sentry remoto, sigue siendo un host con dos clientes separados, aunque use ambos en una tarea.

El servidor de archivos puede usar stdio local y Sentry, HTTP autenticado. Ambos hablan la misma capa de datos MCP.

## Dos capas

MCP separa la capa de datos de la capa de transporte.

La capa de datos define JSON-RPC, versiones, capacidades, herramientas, recursos, prompts, solicitudes de información, notificaciones y progreso: describe el significado.

La capa de transporte mueve esos mensajes. Los servidores locales suelen usar stdio, que conecta dos procesos sin sobrecarga de red. Los servidores remotos usan Streamable HTTP, con HTTP POST para las solicitudes y Server-Sent Events opcionales para transmitir notificaciones. La autenticación pertenece a esta capa exterior.

El mismo mensaje `tools/call` puede viajar por cualquiera de los dos transportes. Cambia la ubicación del servidor, no la semántica del protocolo.

## Las tres primitivas del servidor

Las herramientas son funciones ejecutables: pueden leer un archivo, consultar una base, crear un issue, enviar un mensaje o llamar a una API. El host decide cuándo invocarlas.

Los recursos son contexto: archivos, esquemas, registros, logs o respuestas de API. Permiten leer sin fingir que toda lectura es una acción.

Los prompts son plantillas de interacción reutilizables. Un servidor puede publicar un prompt que codifique un flujo de trabajo conocido, las entradas esperadas o ejemplos de pocos disparos para usar sus herramientas.

Un servidor de base de datos podría exponer `query_database`, el esquema como recurso y `diagnose_slow_query` como prompt. El host lee el esquema, aplica el prompt y consulta con un argumento informado.

Cada primitiva admite descubrimiento. Un cliente enumera herramientas con `tools/list`, recursos con `resources/list` y prompts con `prompts/list`. Solo recupera o ejecuta algo después de saber qué ofrece actualmente el servidor.

## Una solicitud, del descubrimiento a la acción

Primero, el cliente pregunta al servidor qué versiones del protocolo y qué capacidades admite mediante `server/discover`. Cada solicitud identifica en `_meta` la versión del protocolo y las capacidades pertinentes, de modo que el servidor pueda procesarla sin un estado de conexión oculto.

Luego, el cliente llama a `tools/list`. La respuesta describe el nombre, el propósito y el esquema de entrada de cada herramienta.

Supongamos que el servidor devuelve una herramienta llamada `weather_current`, con una cadena obligatoria `location` y un campo opcional `units`. El host ya tiene una acción tipada que puede presentar al modelo.

El usuario pregunta por el tiempo en San Francisco. El modelo selecciona `weather_current` y aporta `{"location":"San Francisco","units":"imperial"}`. El cliente envía `tools/call`. El servidor valida la entrada, realiza la consulta y devuelve contenido estructurado.

El host puede colocar ese resultado en el contexto del modelo, llamar a otra herramienta o pedir confirmación al usuario antes de un paso con consecuencias.

Esta es la forma completa de MCP en miniatura: descubrir, enumerar, seleccionar, llamar y devolver.

## Usos prácticos

Un host de programación puede combinar archivos locales con un servicio remoto como Sentry, manteniendo un cliente por conexión.

Un servidor de base de datos puede ofrecer consultas como herramientas, el esquema como recurso y ejemplos como prompt.

El host reúne esas capacidades; el modelo selecciona una acción y recibe el resultado como contexto.

El servidor local puede usar stdio y el remoto, Streamable HTTP autenticado.

El protocolo no decide cómo usa la aplicación un modelo de lenguaje ni cómo administra el contexto que recibe. Esas decisiones siguen en manos del host.

## Funciones del cliente y notificaciones

Los servidores pueden pedir más información al usuario mediante solicitudes de datos. Una herramienta destructiva podría pedir al host que confirme «¿Eliminar estos tres archivos?» antes de continuar. El host controla cómo aparece esa solicitud y si devuelve la respuesta.

Los servidores también pueden publicar notificaciones. Un cliente puede suscribirse a cambios en la lista de herramientas. Si un servidor agrega o elimina una herramienta, envía una notificación y el cliente actualiza su catálogo.

Las notificaciones importan porque las herramientas disponibles pueden cambiar mientras el cliente está conectado.

Los trabajos prolongados pueden informar su progreso o usar extensiones de tareas. El intercambio central sigue compuesto por solicitudes, respuestas y notificaciones con esquemas explícitos.

## El límite útil

MCP suele describirse como un estándar de conectores. Su arquitectura es más precisa.

El host controla la inteligencia y la orquestación. Cada cliente mantiene una relación de protocolo. Cada servidor ofrece un conjunto acotado de contexto y acciones. La capa de datos define el significado de los mensajes; la de transporte, cómo se mueven.

Esa separación es el valor práctico. Un servidor puede ser sencillo e independiente del modelo. Un host puede combinar varios sin fusionar sus implementaciones. Quienes crean herramientas publican primitivas tipadas y estables; las aplicaciones de IA compiten por usarlas mejor.
