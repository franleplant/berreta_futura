---
source_ids:
- previewing-the-model-hardware-standard-35305757
content_mode: article
label: ARTICLE
---

We're opening a research preview of the Model Hardware Standard (MHS), a shared specification for AI agents to safely operate physical devices, to a first group of scientific research labs and advanced manufacturers. A lab or manufacturing facility typically takes weeks, if not months, to set up and integrate its hardware; most devices don't communicate with each other. MHS reduces this integration work to hours or minutes, and lets agents reason through each step of an experiment, update parameters in real time, and, in some cases, recover from hardware errors without intervention. Partners saw faster integration, faster iteration, and real-time fault detection. Claude's spatial and physical reasoning still has limitations that require expert oversight. We're sharing an early version to build safety evaluations and best practices with partners, ahead of making the standard open source. It began as a collaboration between Anthropic and HHMI Janelia Research Campus.

## How MHS works

Each device has its own programming interface, and there has been no standard way to connect them, share their data with an agent, or let the agent operate them safely. MHS introduces a standardized driver with a simple set of primitives, "read" (get temperature) and "write" (set temperature), and makes each device discoverable in a standard format, so devices and agents find each other without a bespoke translator in between.

Much of what an agent needs to know isn't in code: a robot arm's weight, for example, has lived in paper manuals or as tacit knowledge. The driver has tags where users write this in natural language, themselves or by being interviewed by an agent. From them, MHS produces a reference file stating what the device can measure, what can be adjusted, and what safety limits will be enforced.

The agent controls devices through MCP, the command line, or code files. It sequences steps across instruments, monitors results, and adjusts parameters as conditions change. For long-running tasks, or for speeds its online reasoning can't match, it chains driver commands in code files so the devices run without the agent reasoning at every step. MHS works with any device that has a programmable interface, and it is model-agnostic.

## Genentech: automating a protein assay

Genentech researchers tested MHS on the BCA protein assay, which coordinates a liquid handler, a robotic arm, and a microplate reader. Setting up such automated systems is currently a manual process that can take weeks or even months.

On the standard protocol, Claude chose the same flow rate for aqueous and viscous solutions, which caused bubbles and inaccurate transfers. We then asked it to optimize flow rates within our expert-defined range, using trial transfers of dyed liquid, absorbance readings, and an expert's transfer as ground truth. It concluded ~140 µL/s for water (0.016 RMSE) and 10 µL/s for viscous BSA (0.181 RMSE), parameters our automation experts confirmed were reasonable. Ordinarily, a specialist writes custom programming logic for every parameter set.

Claude recovered on its own from tip pickup failures and fluid detection errors, a capability current instruments mostly lack. But when bubbles caused errors during mixing, its instinct was to retry in the same well with different parameters, which only made more bubbles. It did not yet understand the physics, so we had to guide it. Once told to move to a clean well and reduce mixing cycles, it kept that context for the rest of the run, and we codified the lessons into reusable skills that reduced liquid handling errors.

## Carnegie Mellon University: dose-response curves

Finding a drug's dosage means serial dilution, which by hand can take weeks, and automating it usually takes weeks of engineering. Our setup spans three computers: a robotic arm driven by job files dropped in a directory, a liquid handler with only an old COM scripting interface, and a plate reader with no API at all, only a GUI. MHS turns each into one manifest of states and procedures. Writing the drivers and an orchestration layer for a Claude Opus 4.8 agent took about eight hours, versus the several weeks a vendor-built setup typically takes.

We induced six faults, including a missing plate, a rotated plate, and an active emergency stop. The system blocked all six before any device moved. On the first real run, using a colorimetric dye as a stand-in for a drug, the agent judged the fit too poor (R² < 0.9, from saturation at high concentrations), discarded the plate, and reran with the top concentration cut from 200 to 100 µg/mL. The second run gave R² > 0.98, with no human input at any point. Overall, MHS let us run these experiments roughly three times faster.

## QuEra Computing: quantum laser stabilization

QuEra's quantum computers need each laser to hold its frequency to roughly one part in a trillion. When the lock drops, an expert takes 5 to 10 minutes to recover it. A bespoke script, built over several months by a team of four, worked about 58% of the time and took around 150 seconds per attempt; being a fixed sequence, it had to start over whenever a disturbance undid a finished step.

Through MHS, we gave Claude the goal of a standalone relock script. Four Claude instances, proposing, coding, running against the live laser, and reading the log, cycled hundreds of times overnight. Claude rewrote the sequence as a decision tree that touches only the controls the disturbance calls for. In a blind test with no agent involved, it recovered the lock in 695 of 700 trials (99.3%), in 10 to 14 seconds for the hardest cases and 0.9 to 5.4 seconds for the rest. The result is a deterministic, inspectable script.

We then had Claude tune the lock's 12 PID parameters, measuring the full noise spectrum after every change, which is not realistic for a human. Over 363 experiments and 16 unattended hours, it took residual error from the specialist's 15.7 mV to 1.55 mV. On a phase noise analyzer, its tune matched the specialist's independent retune except at a ~220 kHz resonance, where the manual tune left about a thousand times more noise. Over 19 hours, Claude's tune never lost the lock; the expert's unlocked about 1.6 times an hour.

MHS and agents did not replace expertise. Claude couldn't troubleshoot physical hardware faults, often waited for human approval before slightly risky actions, sometimes pausing experiments overnight, and needed a great deal of context. Still, an overly cautious agent is preferable to one that is not cautious enough.

## Joining the research preview

We have more work to do before we open-source the standard. Claude learns about the physical world through text and images, so its spatial and physical reasoning have limitations that still require expert oversight. MHS doesn't yet work with hardware that lacks a programming interface; we're working with manufacturers on drivers. During the preview we'll build safety evaluations with our partners and develop a physical safety roadmap. When we open-source MHS, we'll release the findings as guidance for deploying it safely.

To participate, join the waitlist at [modelhardwarestandard.com](https://www.modelhardwarestandard.com/).
