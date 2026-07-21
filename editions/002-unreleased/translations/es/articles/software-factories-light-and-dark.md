---
source_id: software-factories-light-and-dark-ef463732
content_mode: faithful_synthesis
label: SÍNTESIS FIEL
---

Una fábrica de software consiste en ciclos con arnés a escala. Con personas dentro —una fábrica con luz— intercambia criterio y concentración por velocidad y riesgo. Sin ellas —una fábrica a oscuras— los agentes pueden delimitar, construir y desplegar código sin que nadie lea los detalles. Si las personas dejan de leer, dejan de comprender el software. Lo más difícil es decidir qué controles construir y cuánta autonomía delegar.

## Ciclo, arnés, fábrica

Un ciclo es un agente que repite una tarea: reúne contexto, actúa, comprueba el resultado y continúa hasta cumplir una condición. El arnés aporta las paredes: entorno aislado, herramientas, memoria persistente y puertas que definen qué significa terminar. Una fábrica reúne muchos ciclos con arnés, alimentados por una cola y conducidos hacia producción a través de una puerta de revisión. No es un agente más grande; es un organigrama hecho de ciclos.

La fábrica cierra su propio circuito. La intención y las señales de producción alimentan la cola; el arnés construye; las pruebas, el análisis estático y los escáneres comprueban; la aprobación permite desplegar; la observabilidad convierte producción en nuevas señales. Casi todas las casillas funcionan a escala con poco coste. La casilla obstinadamente cara es la puerta de revisión: el criterio.

## El cuello estrecho

Una fábrica a oscuras elimina esa puerta. Su rendimiento aparente aumenta porque el código se despliega tras una verificación exclusivamente mecánica. Pero también acumula deuda de comprensión: la distancia entre cuánto código existe y cuánto entiende una persona. En un sistema maduro, el ajuste de cuentas probablemente sea silencioso y tardío, después de meses de pruebas verdes y cambios sin leer.

La generación es una boca ancha; la verificación, un cuello estrecho. La contrapresión exige dar a un ciclo solo la autonomía que pueda verificarse de forma barata y fiable. Un modelo mejor no resuelve automáticamente el problema, porque la calidad arquitectónica se revela en meses y años, no en los segundos nítidos de una prueba.

## Encender la luz donde vive el criterio

Una fábrica con luz deja que los agentes hagan la mayor parte de la construcción, pero traslada el criterio humano hacia producto, diseño y arquitectura, además de la revisión. Una hora para revisar un plan de doscientas líneas puede evitar una revisión dolorosa de dos mil líneas generadas. Tipos, puntos de prueba, límites legibles, pilas cortas e inyección de dependencias forman una red de seguridad externa al modelo y difícil de falsear.

Algunos ciclos pequeños pueden ganarse la oscuridad: el control es barato, frecuente, inmediato, estable y difícil de engañar. Una tarea nocturna que corrige una infracción de lint y abre una solicitud de cambios pequeña puede cumplir esas condiciones. Autenticación, facturación, contratos públicos y decisiones arquitectónicas duraderas, no. Todo a oscuras produce un sistema que nadie puede reparar; todo con luz produce un atasco de revisiones. El trabajo cualificado consiste en colocar cada interruptor.

La persona nunca abandonó la fábrica: pasó al ciclo exterior. Los agentes pueden investigar, implementar, probar e informar. Los ingenieros todavía deciden si el enfoque es correcto, inspeccionan la evidencia en la frontera, aprueban el cambio y cargan con las consecuencias de equivocarse. Los robots pueden trabajar a oscuras. Las personas necesitan ver aquello de lo que son responsables.
