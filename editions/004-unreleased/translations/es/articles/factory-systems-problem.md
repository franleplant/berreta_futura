---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: EDICIÓN FIEL
---

## Las fábricas de software son muy reales

Las fábricas de software son reales, pero debemos ser realistas. La fábrica misma no está resuelta; los innovadores aún descubren prácticas y piezas.

Si alguien te vende una fábrica y no pertenece al pequeño grupo de startups creadas en los últimos seis meses ni a las cerca de diez personas que llevan dos años intentándolo y fracasando, te vende humo. Aún no está resuelto, pero el rompecabezas avanza cada día.

La meta es una fábrica casi a oscuras. La mejor práctica es construir las abstracciones y piezas necesarias resolviendo cuestiones ajenas a los agentes: aislamiento, monorrepositorios, builds reproducibles, CI/CD, gestión de identidades y secretos, y fricción corporativa en la experiencia de desarrollo.

En tu tiempo libre, avanza sobre este problema en tu laboratorio doméstico si quieres un ascenso rápido y trato de alfombra roja en tu próxima entrevista. El mayor retorno está en aprender toda la pila, automatizarla y mostrar el trabajo en una entrevista o charla grabada.

## Sistemas y cultura, no tokens

Debo insistir: las fábricas no son un problema de tokens ni de LLM. Los tokens y su aplicación no las resolverán, aunque sean una pieza del rompecabezas.

## Mantén determinista el bus de servicios

Segunda opinión polémica. n8n fue una idea absurda. Sospecho que la construyeron jóvenes desarrolladores de Silicon Valley arrastrados por la fiebre de los LLM, sin experiencia corporativa ni conocimiento de que los buses de servicios son un problema resuelto con muchos antecedentes en el inquietante mundo empresarial.

Busca en [`.NET`](https://x.com/dotnet), incluidos MassTransit, NServiceBus y WCF, ideas para diseñar prompts. WCF me trae malos recuerdos. La implementación no es gran cosa, pero la teoría y la formación suelen ser acertadas.

Para una opción moderna lista para usar, emplea [Temporal](https://x.com/temporalio) y haz que un job invoque a un agente como proceso.
