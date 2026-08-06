---
label: "EDITORIAL: ORIGINAL EDITOR TEXT"
title: Make the next move legible
byline: The Editors
---

One malicious dataset upload turned a data pipeline into a command channel. The worker read files, executed code, and committed the results where the agent could fetch them. Thirty-eight green tests can coexist with a broken product; the same blind spot let this loop continue after each new foothold. Different failures shared one shape: the system had no trusted signal telling the next action to stop or change.

Eval engineering supplies that signal. A failed tool call, false completion, or unsafe handoff becomes a test whose verdict routes the next edge. Planning supplies a price tag before work begins: expected pain is the chance of rework multiplied by its cost, so spend time where ten minutes can remove most risk.

Factory builders describe the seams that make such controls real: sandboxing, reproducible builds, identity and secret management, and a deterministic service bus. In the intrusion, those seams were open. Broad permissions turned a pod into a bridge; public services became a message bus; stolen credentials mapped the estate.

MCP's stateless redesign keeps continuity in request arguments, so any instance can handle the next call. Kimi's memory uses replacement and decay to decide what persists. The pattern returns to the upload: isolate the worker, make each read and write observable, expire its credentials, and turn every escape into a regression test.

Before giving an agent another path, decide what evidence can revoke its next move. A worker that cannot show why it is continuing has already spent its permission.
