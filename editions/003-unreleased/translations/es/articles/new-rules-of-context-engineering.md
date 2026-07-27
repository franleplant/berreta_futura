---
source_id: the-new-rules-of-context-engineering-for-claude--aa1b1ea8
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
source_body_sha256: aaeea1ef2ec0a1645ec0eae72d75b920dc73b91bd30dc736cf5eecd6624902a9
---

Cuando le envías un mensaje a Claude, el prompt es solo una pequeña parte del contexto que recibe: mucho se ensambla a partir de tu prompt de sistema, las Skills, los archivos CLAUDE.md, la memoria y otras fuentes. A diferencia de un prompt, este contexto sirve a muchas solicitudes y no puede ser tan específico; lo llamamos ingeniería de contexto, y tiene un gran impacto en tus resultados.

Esto puede resultar sorprendentemente difícil a medida que evolucionan las capacidades del propio Claude. Hace poco notamos un gran salto en la manera de escribir prompts para la generación más reciente de modelos Claude. Eliminamos más del 80 por ciento del prompt de sistema de Claude Code para modelos como Claude Opus 5 y Claude Fable 5 sin pérdida medible en nuestras evaluaciones de programación.

## Quitarle las trabas a Claude

En conjunto, descubrimos que estábamos sobrerrestringiendo a Claude Code, tanto en nuestro prompt de sistema como en nuestros archivos CLAUDE.md y skills.

En transcripciones de nuestro propio uso interno de Claude Code vemos mensajes contradictorios dentro de una misma solicitud —«deja documentación donde corresponda», «NO añadas comentarios»— cuando chocan el prompt de sistema, las skills y las peticiones del usuario. Claude, por lo general, puede interpretar la intención del usuario y llegar a la respuesta correcta, pero debe pensar con más cuidado en estos conflictos antes de decidir. Las restricciones que antes hacían falta para evitar los peores escenarios ahora pueden borrarse: el modelo usa, en su lugar, el contexto circundante y su criterio.

## Antes y ahora

### Antes: dale reglas a Claude. Ahora: deja que Claude use su criterio

Cuando lanzamos Claude Code por primera vez dimos indicaciones especialmente firmes para alejar a Claude de los peores escenarios, como borrar archivos; indicaciones que no siempre serían ciertas. En el prompt de sistema solíamos decir:

> En código: por defecto, no escribas comentarios. Nunca escribas docstrings de varios párrafos ni bloques de comentarios de varias líneas: una línea corta como máximo. No crees documentos de planificación, decisión o análisis salvo que el usuario los pida: trabaja desde el contexto de la conversación, no desde archivos intermedios.

Para cierto subconjunto de prompts esta indicación sería errónea: el usuario puede tener sus propias preferencias de documentación, o un código muy complejo puede necesitar bloques de comentarios de varias líneas. Los modelos antiguos solían escribir comentarios incorrectos sin estas salvaguardas, una contrapartida que aceptamos; los modelos nuevos tienen mejor criterio y toman estas decisiones sin reglas explícitas.

En el nuevo prompt de sistema decimos: escribe código que se lea como el código circundante: iguala su densidad de comentarios, su nomenclatura y sus modismos.

### Antes: dale ejemplos a Claude. Ahora: diseña interfaces

La regla número uno para el uso de herramientas era darle ejemplos a Claude; con nuestros modelos más recientes, los ejemplos en realidad los restringen a cierto espacio de exploración. En su lugar, piensa en el diseño de tus herramientas, scripts y archivos: ¿qué parámetros tiene Claude y cómo pueden ser más expresivos? En la herramienta Todo, listar el estado como una enumeración entre pending, in_progress y completed insinúa cómo usarla.

### Antes: ponlo todo por delante. Ahora: usa la revelación progresiva

Nuestro prompt de sistema orientado a programación incluía información detallada sobre revisión de código y verificación: no siempre necesaria, pero crucial cuando lo era. Claude Code se ha vuelto desde entonces muy competente en la revelación progresiva, cargando el contexto adecuado en el momento adecuado, y trasladamos la verificación y la revisión de código a sus propias skills de invocación selectiva.

La revelación progresiva no es solo para las skills: algunas herramientas son de «carga diferida» —el agente debe buscar sus definiciones completas con ToolSearch—, de modo que no ocupan contexto hasta que hacen falta. Lo mismo vale para tus archivos CLAUDE.md y Skill.md: en lugar de un repositorio central con cada práctica conocida, considera un árbol de archivos que se cargan en el momento oportuno.

### Antes: repítete. Ahora: descripciones de herramientas sencillas

Los modelos Claude anteriores podían necesitar instrucciones repetidas, o escuchar más el final de su ventana de contexto que el principio, así que nuestro prompt de sistema hacía referencia a herramientas cuyas descripciones llevaban las mismas indicaciones. Borramos esas repeticiones y dejamos las instrucciones de cada herramienta en su descripción, no en el prompt de sistema.

### Antes: memoria en archivos CLAUDE.md. Ahora: memoria automática

Antes animábamos a los usuarios a guardar cosas en la memoria de Claude usando el atajo # para escribir automáticamente en su CLAUDE.md. Ahora, en cambio, Claude guarda automáticamente los recuerdos relevantes para el trabajo y para ti.

### Antes: especificaciones simples. Ahora: referencias ricas

En el modo de planificación, Claude Code ha dependido mucho de archivos de plan en markdown, y una práctica parecida era guardar especificaciones en la base de código para proyectos largos.

Pero hemos comprobado que Claude puede manejar referencias cada vez más complejas. En lugar de simples archivos markdown, Claude puede tomar como referencia artefactos HTML creados con nuestra nueva función de artefactos.

También puedes dar referencias en forma de código: una batería de pruebas detallada, o una función de otra base de código que Claude podría portar. Las rúbricas son otra forma: agentes verificadores en flujos dinámicos intentan verificar tu gusto en un campo como el diseño de API.

## Aplicar esto a tu contexto

### CLAUDE.md

Mantén tu CLAUDE.md ligero y describe brevemente para qué es tu repositorio, pero gasta la mayoría de los tokens en las trampas ocultas de la base de código. Por ejemplo, puede que organices tu código para mantener los tipos en un único archivo monolítico y en ningún otro sitio. Evita enunciar «lo obvio», lo que Claude debería saber con mirar tu sistema de archivos o tu repositorio.

### Skills

Piensa en las skills como guías ligeras que permiten a Claude encontrar información cuando la necesita, y evita sobrerrestringirlas salvo en áreas muy importantes; divide las skills largas en muchos archivos de revelación progresiva. Las skills rinden más cuando codifican opiniones, conocimiento o buenas prácticas propias de ti, de tu equipo o de tu producto.

### Referencias

Puedes mencionar archivos con @ como referencias a información en profundidad sobre el plan actual: especificaciones, maquetas o incluso bases de código enteras. En general, prefiere archivos en código: instrucciones claras y de alta fidelidad en un lenguaje que Claude conoce muy bien. Una maqueta HTML producirá por lo general mejores resultados que una descripción o una captura de pantalla.

## Prueba a simplificar

En tu prompt de sistema, tus skills y tus archivos CLAUDE.md, puede que necesites simplificar igual que hicimos nosotros. Lanzamos un nuevo comando llamado `claude doctor,` que también te ayudará a hacerlo automáticamente. Para más detalles sobre cómo escribir prompts específicamente para los modelos más avanzados, consulta nuestra guía de campo de Fable.
