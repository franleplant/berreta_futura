---
source_id: the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

La candidata a versión de la especificación del Model Context Protocol del 28 de julio de 2026 es la mayor revisión desde su lanzamiento. Introduce un núcleo sin estado, extensiones de primera clase, Tasks de larga duración, MCP Apps, un refuerzo de la autorización, una política formal de obsolescencia y JSON Schema completo para las herramientas.

El efecto práctico es operativo. Un servidor MCP remoto que antes necesitaba sesiones persistentes y un almacén de sesiones compartido puede ejecutarse detrás de un balanceador de carga round-robin convencional. Los gateways pueden enrutar solicitudes a partir de encabezados. Los clientes pueden almacenar en caché las respuestas de enumeración durante un período explícito.

## Un protocolo sin estado

En la especificación de 2025, un cliente de Streamable HTTP iniciaba una sesión, recibía un `Mcp-Session-Id` y adjuntaba ese identificador a las solicitudes posteriores. La sesión fijaba el tráfico a la instancia del servidor que la había creado o exigía compartir estado entre instancias.

En el nuevo protocolo, una llamada a una herramienta es autocontenida. La versión del protocolo, la información del cliente y las capacidades pertinentes viajan en `_meta` con cada solicitud. Desaparecen el intercambio de inicialización y la sesión en el nivel del protocolo.

Los clientes pueden llamar a `server/discover` cuando necesitan conocer las versiones y capacidades del servidor antes de realizar otra solicitud. Cualquier solicitud puede llegar a cualquier instancia compatible del servidor.

Esto no obliga a las aplicaciones a olvidar su estado. Una herramienta puede crear un identificador explícito, como `basket_id` o `browser_id`, devolverlo al modelo y aceptarlo como argumento ordinario en la siguiente llamada.

Los identificadores explícitos suelen ser más útiles que los metadatos de transporte. El modelo puede verlos, combinarlos entre herramientas, razonar sobre su propiedad y pasarlos de un paso a otro. El estado sigue siendo posible, pero pasa a ser un dato de la aplicación y deja de ser una propiedad invisible de la conexión.

## Solicitudes del servidor sin un canal permanente

Los servidores todavía necesitan pedir información al cliente durante una llamada a una herramienta. Una operación puede exigir confirmación, credenciales u otra elección del usuario.

La nueva regla establece que un servidor solo puede iniciar esa solicitud mientras procesa una solicitud del cliente. Un usuario nunca debería recibir un prompt no relacionado de un servidor inactivo.

Las solicitudes con múltiples viajes de ida y vuelta reemplazan el supuesto de un único flujo persistente. El servidor devuelve un resultado `input_required` que contiene una o más solicitudes de datos y un `requestState` opaco. El cliente reúne las respuestas, repite la operación original con `inputResponses` y replica el estado.

Cualquier instancia del servidor puede procesar el reintento porque la carga contiene todo lo necesario para continuar.

## Enrutable, almacenable en caché y trazable

Streamable HTTP ahora exige los encabezados `Mcp-Method` y `Mcp-Name`. Un balanceador de carga puede enrutar y limitar la frecuencia de `tools/call` para `search` sin analizar el cuerpo JSON-RPC. Los servidores rechazan una solicitud cuando los encabezados y el cuerpo no coinciden.

Los resultados de enumeración y de lectura de recursos pueden declarar `ttlMs` y `cacheScope`. El cliente sabe durante cuánto tiempo se mantiene vigente una respuesta de `tools/list` y si puede compartirla entre usuarios. Los servidores ya no necesitan un flujo de eventos de larga duración solo para mantener actualizado cada catálogo.

El contexto de trazas se mueve mediante los encabezados estándar `traceparent`, `tracestate` y baggage. Una llamada a una herramienta puede aparecer dentro de la misma traza de OpenTelemetry que la acción del host y las llamadas a servicios posteriores.

Estos cambios hacen que el tráfico de MCP sea legible para la infraestructura HTTP existente, en lugar de exigir gateways específicos para el protocolo.

## Las extensiones evolucionan de forma independiente

El protocolo central es más pequeño porque las capacidades opcionales pueden evolucionar como extensiones con mantenedores delegados y versiones independientes.

MCP Apps es una extensión oficial para interfaces renderizadas por el servidor. Un servidor puede devolver una interfaz interactiva cuando el texto plano o los datos estructurados no son suficientes.

Tasks también pasa a ser una extensión. Admite trabajos de larga duración que pueden consultarse y recuperarse después de la solicitud inicial. El ciclo de vida anterior de tareas dentro del núcleo se elimina porque no podía delimitarse de manera segura sin sesiones.

La separación permite que el núcleo permanezca estable mientras los patrones de interfaz y trabajo asincrónico evolucionan con mayor rapidez.

## Refuerzo de la autorización

Las revisiones de autorización acercan MCP a implementaciones reales de OAuth y OpenID Connect.

Los indicadores de recursos se vuelven más estrictos para que los tokens se emitan para el servidor previsto. Los metadatos del servidor de autorización deben identificar al emisor de manera coherente. El registro de clientes puede usar mecanismos basados en estándares, en vez de suponer que cada servidor opera su propio registro personalizado.

La especificación también contempla recursos que migran entre servidores de autorización y documenta cómo deben pedir los clientes tokens de actualización a proveedores de estilo OpenID Connect.

La dirección es clara: MCP debe encajar en los sistemas de identidad existentes en lugar de inventar uno paralelo.

## Obsolescencias y esquemas

Roots, Sampling y Logging quedan obsoletos en el núcleo.

Roots puede reemplazarse con parámetros de herramientas, URI de recursos o configuración del servidor. Sampling puede trasladarse a una integración directa con las API de proveedores de modelos. Logging puede usar infraestructura estándar de observabilidad.

En esta versión, estas obsolescencias son solo anotaciones. Los métodos y los indicadores de capacidad siguen disponibles mientras las implementaciones migran.

Los esquemas de herramientas ahora usan JSON Schema 2020-12 completo. Servidores y clientes pueden expresar reglas de validación más ricas, pero deberían tratar los esquemas como entradas no confiables, limitar la recursión y el tiempo de validación, y evitar resolver automáticamente referencias remotas.

Un recurso inexistente ahora usa la familia estándar de JSON-RPC para método no encontrado, en vez del valor específico de MCP `-32002`. Las implementaciones que comparan literalmente el código anterior deben cambiar.

## Cómo evoluciona el protocolo

Los cambios incompatibles deberían ser menos frecuentes. Las funcionalidades pasan por los estados Activa, Obsoleta y Eliminada, con al menos doce meses entre los dos últimos. Los niveles de los SDK fijan el soporte de las implementaciones oficiales.

La candidata abre una ventana de diez semanas para que mantenedores de SDK, autores de clientes, operadores de servidores y proveedores de gateways validen el comportamiento frente a la especificación anterior. La versión final se publica el 28 de julio de 2026.

El cambio duradero no es un encabezado ni un método. MCP se vuelve un protocolo web sin estado, con estado de aplicación explícito, enrutamiento, caché y trazas estándar, y funciones opcionales fuera del núcleo.
