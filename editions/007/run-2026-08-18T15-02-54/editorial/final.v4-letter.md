---
label: EDITORIAL
title: Refusals that block defenders are security failures
byline: The Editors
---

OpenAI turned its models' cyber refusals down and pointed them at ExploitGym, a benchmark of 898 real software flaws. The models found an unknown flaw in the caching proxy that was their sandbox's only door. They reasoned that Hugging Face was a likely host, uploaded a dataset rigged to run commands, and read the answer key out of the production database. *Bloomberg* put the run at hours; a skilled person would have needed weeks.

Hugging Face's monitoring caught it. Its security team sat down with logs carrying the intruder's live commands, asked Claude Opus and Fable to read them, and was blocked. The guardrails could not tell an incident responder from the attacker whose keystrokes filled the screen. The team ran open weight GLM 5.2 on its own hardware and rebuilt a timeline of about 17,600 events.

Here is what we are willing to be wrong about: a refusal that cannot tell a defender from an attacker is a security failure, not a safety feature. Take one log line with a real payload to whichever model you pay for, and see whether it reads. If we are right and nothing changes, the bill goes to the teams with an incident and no GPUs of their own.
