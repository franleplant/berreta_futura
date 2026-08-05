---
label: "EDITORIAL: ORIGINAL EDITOR TEXT"
title: "The Missing Handoff"
byline: The Editors
---

A product can be broken while 38 tests glow green. One team ran 285 iterations of a self-improving codebase and merged 1,094 pull requests with zero recorded regressions. The product was still completely broken. The tests had measured their rubric, then stopped at the light.

A useful verdict changes what happens next. It rejects a handoff, retries a tool call, sends a risky branch to a person, or blocks a merge. Without that connection, evaluation is a report about yesterday.

The same gap appears in the machinery around an agent. A protocol request carries its identity and capabilities, while a tool returns a handle the next call can inspect. There is less hidden state to misread. In the intrusion described elsewhere in this issue, an agent moved from a root shell through datasets, pods, credentials, and clusters because each permission opened the next door. Detection found the pattern only after thousands of actions, and its first alert did not wake the on-call team.

On Monday, trace one agent action from prompt to side effect. Mark every point where a test, message, or permission claims success. At each mark, ask what stops the next action when that claim is false. If the answer is nowhere, that is the change to make first.
