---
source_ids:
- genie-4-a-new-generation-of-world-simulation-goo-393575ee
content_mode: article
label: ARTICLE
---

Today we are announcing Genie 4, our new world model. You set an event in motion and Genie 4 simulates what happens next: how the world responds, how it sounds, and how the people in it move, react, and speak. It generates audio natively, dialogue included. Gemini Omni anchors its simulations in real-world appearance and behavior, while other Gemini models supply the reasoning that keeps them coherent. Understanding and simulating the world is a crucial aspect of building AGI, and safe, infinitely variable simulations can help with everything from training robots and agents to new interactive experiences. Genie 4 is an early, experimental model, released as a research preview to trusted testers before it reaches Google AI Ultra subscribers in Project Genie and early access partners of the Gemini API and Google AI Studio.

## Steering a world as it runs

Users move with standard keyboard controls and steer with text. Natural language changes the simulation in real time: the weather, the camera, a new person or object. Gemini adapts each prompt to the surrounding scene and, between inputs, steers the world so it keeps progressing cohesively.

## Physics and people

Genie 4 simulates real-world physics such as aerodynamics and collisions. The most dramatic leap is in people: characters that move naturally, respond organically to their environments, and can be steered in real time.

## Sound

Genie 4 is our first real-time world model to generate audio natively. Every world carries the ambient sound of its own setting, from wind in the trees to waves on the beach. The true frontier is speech: characters converse and react to your inputs, or to events in the world, as they happen.

## Gemini in the loop

Gemini 3.8 Flash acts as a guiding agent. While Genie 4 generates the world, Gemini watches the scene, breaks goals into steps, and reviews incoming frames to verify that each step succeeded. When the world shifts or the user intervenes, it adapts the plan, which gives the worlds reliable causality, procedural behavior, and multi-step reasoning.

We have also paired Gemini 4 Argon with Genie 4. Argon splits a task into steps and feeds them to Genie as text captions while the simulation renders. In one example, the two simulate Apptronik's Apollo humanoid playing checkers.

## What testers found

Trusted testers across creative industries, journalism, education, gaming, and engineering are testing Genie 4 as:

- a "draft mode" in which filmmakers run several takes of a scene, adjusting camera, lighting, dialogue, and action on the fly;
- a way to turn one archival photograph into a grounded simulation in seconds, or to visualize short events like a flash flood or wildfire;
- a path from idea to explorable game prototype before writing a line of engine code;
- a tool for rapid "zero-to-one" scenario generation, for enterprise partners who are also identifying gaps.

## Toward hybrid world models

A promising path lies in hybrid world models, which combine the structured reasoning of code and language models with pixel-level simulation. Gemini maps the structure and the narrative timeline; Genie renders how the world looks, sounds, and responds. Together, these strengths can unlock world models far more coherent, controllable, and grounded than either approach alone.

## Safety and limits

Genie 4 has safety guardrails consistent with our other models and passed internal safety evaluations before this preview. We deployed it first to trusted testers on purpose, to gather feedback before a broader release. All video and audio it generates carries SynthID, our imperceptible watermark.

It remains early research. Environments hold together over short sessions, but details and object permanence can drift, especially in longer runs, after many complex prompt edits, or while navigating the scene. Complex physical interactions, real-time audio accuracy, legible text, spatial accuracy, and long-term consistency are still open research.
