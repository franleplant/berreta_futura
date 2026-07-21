---
source_id: the-building-block-economy-af6644bd
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The most effective way to build software—and to drive adoption—has shifted toward creating building blocks that enable quantity. Ghostty spent roughly eighteen months reaching a million daily update checks. Its embeddable library, libghostty, reached several million daily checks in about two months. I now spend much of my time making Ghostty easier to embed because downstream software factories multiply those blocks faster than I ever could alone.

## Imports are up

Software factories are extremely good at gluing proven, documented components together. Importing once required a person to discover a library, understand it, and judge whether the integration effort was worthwhile. Agents erase much of that human barrier, so they reach deeper into dependency graphs and use smaller, more specialized packages.

That changes the value of a clean interface. A reusable block no longer needs a huge audience of people who happen to know it exists; it needs to be legible to machines that are continuously searching for capabilities. Documentation, stable APIs, and composability become distribution.

## Exports are up

The growth has real costs: security exposure, instability, and software whose operators may not understand its internals. But four forces also make exporting blocks more attractive. The quality bar for a useful component is lower, awareness is greater, maintenance is cheaper when agents can help, and downstream users effectively outsource research and development by discovering new uses and fixes.

This encourages purposeful libraries and forks. A feature that would make the main application brittle can live in an embeddable layer or a downstream project. The parent project can remain stable while a broader community explores the design space around it.

## Commercial tension

The unresolved question is commercialization. Closed, paid software is harder for agents to discover, inspect, and compose than open, free building blocks. That creates a genuine disadvantage for conventional product boundaries. I do not have a concrete answer, and false certainty would be less useful than admitting the problem.

The shift has already happened. Building blocks and software factories now reinforce each other: more reusable parts make factories stronger, and more factories increase the value of reusable parts. Resisting the change does not restore the old economics. The practical task is learning how to build stable, understandable foundations inside the new one.
