---
source_id: pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_edit
label: EDICIÓN FIEL
---

Este es un apéndice a la reciente serie sobre la fábrica de software. No encajaba con naturalidad en la publicación principal, así que lo publico por separado.

## Buscar apalancamiento

Incluso antes de la IA, solo entre el 25 y el 50 por ciento del tiempo necesario para entregar una funcionalidad se dedicaba a escribir código. El resto era alineación y planificación, revisión del código y reelaboración, y luego pruebas y verificación.

Si usas la IA solamente para escribir código, puedes reducir dos o cuatro horas de programación a diez o veinte minutos sin acelerar nada de lo que la rodea.

Si usas la IA para ayudar a planificar y alinear, puedes acercarte a avanzar dos o tres veces más rápido.

## La regla 80/20 del apalancamiento al programar con IA

Supongamos que envías un prompt de dos oraciones a tu fábrica. La probabilidad de obtener un resultado listo para integrar podría rondar el 50 por ciento, con otro 50 por ciento de probabilidades de que necesites reelaborarlo.

Ahora supongamos que eres un ingeniero principal con diez años de experiencia y que tienes todo el código, repartido en cien repositorios, descargado en tu cabeza. Pasas una tarde escribiendo a mano una especificación perfectamente detallada. Tus probabilidades mejoran, pero probablemente siga existiendo una posibilidad considerable de que debas rehacer algo importante.

En el extremo opuesto, escribes cada línea por tu cuenta. No queda nada en lo que el agente pueda equivocarse, por lo que la probabilidad de reelaboración se acerca a cero.

Para este ejemplo, estoy condensando dos variables distintas en un único porcentaje: la probabilidad de que necesites cambiar algo, ponderada por lo doloroso que será el cambio.

> dolor esperado = P(tendrás que cambiarlo) × cuánto duele el cambio

Si un modelo tiene un 50 por ciento de probabilidades de equivocarse en el estilo de un botón, pero corregirlo cuesta un prompt barato, el dolor esperado es bajo.

Si dibujas la relación, obtienes una curva inversa entre el esfuerzo invertido de antemano y el dolor esperado. Lo que no quieres es dedicar seis horas a planificar una tarea cuando los primeros diez minutos podrían haber eliminado el 80 por ciento del dolor esperado.

Tampoco puedes invertir de más en preguntas que solo se vuelven respondibles después de bajar un nivel. La planificación de producto puede revelar una incertidumbre técnica. En ese momento, deja de intentar completar la visión del producto e inspecciona las restricciones de implementación. No existe una secuencia perfecta.

Eso significa apalancamiento en este contexto. Exige pragmatismo.

Si tu planificación baja desde la perspectiva de los 50.000 pies hacia la de los 10.000, orienta un poco el rumbo en cada fase. El objetivo no es una especificación máxima. Es eliminar la mayor cantidad posible de dolor esperado con el menor esfuerzo.

Buena suerte.
