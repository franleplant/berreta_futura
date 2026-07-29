---
source_id: architecture-overview-ce5cb1d1
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

El Model Context Protocol define cómo una aplicación de IA intercambia contexto y acciones con programas externos. No define cómo usa la aplicación un modelo de lenguaje, cómo planifica una tarea ni cómo administra su contexto interno. Define el límite.

El proyecto MCP incluye la especificación, SDK para distintos lenguajes, herramientas de desarrollo como Inspector e implementaciones de servidores de referencia. La mayoría de los desarrolladores interactúa con los SDK. Aun así, vale la pena entender la arquitectura subyacente porque explica qué se conecta con qué, qué puede exponer un servidor y cómo una solicitud se convierte en una acción.

## Host, cliente y servidor

Un host MCP es la aplicación de IA. Visual Studio Code, Claude Code o un asistente de escritorio pueden actuar como host.

El host crea un cliente MCP para cada servidor MCP. El cliente es el componente que mantiene la conexión, descubre capacidades, envía solicitudes y devuelve al host los resultados del servidor.

Un servidor MCP es un programa que ofrece contexto o acciones. Puede ejecutarse de forma local o remota.

Supongamos que Visual Studio Code se conecta a un servidor local de sistema de archivos y a un servidor remoto de Sentry. VS Code es un solo host. Dentro de él, un cliente se conecta al servidor de archivos y otro cliente se conecta a Sentry. Las conexiones permanecen separadas aunque el host pueda usar ambas durante la misma tarea.

El servidor de archivos podría leer archivos mediante la entrada y salida estándar en la misma máquina. El servidor de Sentry podría aceptar solicitudes HTTP autenticadas de muchos usuarios. Ambos son servidores MCP porque hablan el mismo protocolo de capa de datos.

## Dos capas

MCP separa la capa de datos de la capa de transporte.

La capa de datos define mensajes JSON-RPC, descubrimiento de capacidades y versiones, herramientas, recursos, prompts, solicitud de información, notificaciones e informes de progreso. Esta es la parte que describe el significado.

La capa de transporte mueve esos mensajes. Los servidores locales suelen usar stdio, que conecta dos procesos sin sobrecarga de red. Los servidores remotos usan Streamable HTTP, con HTTP POST para las solicitudes y Server-Sent Events opcionales para transmitir notificaciones. La autenticación pertenece a esta capa exterior.

El mismo mensaje `tools/call` puede viajar por cualquiera de los dos transportes. Cambia la ubicación del servidor, no la semántica del protocolo.

## Las tres primitivas del servidor

Las herramientas son funciones ejecutables. Una herramienta puede leer un archivo, consultar una base de datos, crear un issue, enviar un mensaje o llamar a una API. El host decide cuándo invocarla, por lo general después de que el modelo la selecciona como parte de una tarea.

Los recursos son datos de contexto. Un recurso puede ser un archivo, un esquema de base de datos, un registro, un flujo de logs o la respuesta de una API. Los recursos permiten que el host recupere información sin fingir que toda lectura es una acción.

Los prompts son plantillas de interacción reutilizables. Un servidor puede publicar un prompt que codifique un flujo de trabajo conocido, las entradas esperadas o ejemplos de pocos disparos para usar sus herramientas.

Pensemos en un servidor de base de datos. Podría exponer `query_database` como herramienta, el esquema actual como recurso y un prompt `diagnose_slow_query` con ejemplos. El host puede leer el esquema, aplicar el prompt y luego llamar a la herramienta de consulta con un argumento bien informado.

Cada primitiva admite descubrimiento. Un cliente enumera herramientas con `tools/list`, recursos con `resources/list` y prompts con `prompts/list`. Solo recupera o ejecuta algo después de saber qué ofrece actualmente el servidor.

## Una solicitud, del descubrimiento a la acción

Primero, el cliente pregunta al servidor qué versiones del protocolo y qué capacidades admite mediante `server/discover`. Cada solicitud identifica en `_meta` la versión del protocolo y las capacidades pertinentes, de modo que el servidor pueda procesarla sin un estado de conexión oculto.

Luego, el cliente llama a `tools/list`. La respuesta describe el nombre, el propósito y el esquema de entrada de cada herramienta.

Supongamos que el servidor devuelve una herramienta llamada `weather_current`, con una cadena obligatoria `location` y un campo opcional `units`. El host ya tiene una acción tipada que puede presentar al modelo.

El usuario pregunta por el tiempo en San Francisco. El modelo selecciona `weather_current` y aporta `{"location":"San Francisco","units":"imperial"}`. El cliente envía `tools/call`. El servidor valida la entrada, realiza la consulta y devuelve contenido estructurado.

El host puede colocar ese resultado en el contexto del modelo, llamar a otra herramienta o pedir confirmación al usuario antes de un paso con consecuencias.

Esta es la forma completa de MCP en miniatura: descubrir, enumerar, seleccionar, llamar y devolver.

## Usos prácticos

Un host de programación como Visual Studio Code puede conectarse a un servidor local de sistema de archivos y a un servidor remoto de Sentry. Cada conexión recibe su propio cliente MCP, mientras que el host puede usar ambas durante la misma tarea.

Un servidor de base de datos puede exponer funciones de consulta como herramientas, su esquema como recurso y ejemplos de pocos disparos como prompt. El host puede leer el esquema antes de pedir al modelo que seleccione y llame a una herramienta de consulta.

Una aplicación de IA puede reunir las herramientas de todos los servidores conectados en un único registro. El modelo ve las acciones disponibles, selecciona una durante una conversación y recibe el resultado como contexto.

Un servidor local de sistema de archivos puede usar stdio en la misma máquina. Un servicio remoto como Sentry puede exponer el mismo protocolo mediante Streamable HTTP autenticado.

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
