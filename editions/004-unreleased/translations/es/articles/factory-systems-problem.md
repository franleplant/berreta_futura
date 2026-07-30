---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: EDICIÓN FIEL
---

## Las fábricas de software son muy reales

Las fábricas de software son muy reales, pero tenemos que ser realistas. Los aspectos fabriles todavía no están resueltos; los innovadores experimentan para descubrir prácticas y piezas.

Si alguien te está vendiendo una fábrica ahora mismo y no pertenece al grupo muy reducido de empresas emergentes que probablemente nacieron en los últimos seis meses, ni está entre las aproximadamente diez personas del quién es quién que llevan dos años intentándolo y, siendo realistas, fracasando, te está vendiendo humo. El problema no está resuelto, pero es un rompecabezas que se resuelve a diario.

El objetivo es una fábrica casi a oscuras. La mejor práctica actual consiste en construir las abstracciones y las piezas que necesitamos. Eso exige resolver cuestiones ajenas a los agentes: aislamiento, monorrepositorios, compilaciones reproducibles, CI/CD, gestión de identidades y secretos, y la eliminación de las fricciones corporativas en la experiencia de desarrollo para agentes.

En casa, en tu laboratorio doméstico, deberías avanzar sobre este campo en tu tiempo libre si quieres un ascenso muy rápido y trato de alfombra roja en tu próxima entrevista. El mayor retorno de la inversión que puedes obtener ahora mismo consiste en aprender toda la pila, automatizarla y mostrarla en tu próxima entrevista o en una charla grabada durante un encuentro.

## Un problema de ingeniería de sistemas y cultura empresarial

Debo insistir en que las fábricas no son un problema de tokens ni de LLM. No se resolverán mediante tokens ni por cómo los apliques, aunque eso sea una pieza del rompecabezas.

## Mantén determinista el bus de servicios

Segunda opinión polémica, ya que parece que la primera llegó. n8n fue una idea absurda que siempre sospeché que habían desarrollado jóvenes de Silicon Valley entregados por completo a la fiebre de los LLM, que nunca habían trabajado en una gran empresa y, por tanto, ignoraban que los buses de servicios son un problema resuelto y cuentan con muchos antecedentes en el inquietante mundo del software empresarial.

Busca cualquier cosa en el espacio de [`.NET`](https://x.com/dotnet), como MassTransit, NServiceBus o WCF, si quieres robar ideas para el diseño de prompts. WCF me trae muchos malos recuerdos. La implementación no es gran cosa, pero la teoría y el material educativo suelen ser acertados.

Si quieres una opción moderna lista para usar, [Temporal](https://x.com/temporalio) existe. Úsala y haz que un job invoque a un agente como proceso.
