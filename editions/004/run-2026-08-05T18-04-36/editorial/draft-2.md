---
label: "EDITORIAL: ORIGINAL EDITOR TEXT"
title: The cost of a shortcut
byline: The Editors
---

A stolen credential opened two Kubernetes clusters in less than a second. One identity had been bound to `system:masters` on both. Its reach arrived prepackaged.

That is the hidden cost in faster work. Code takes 25–50% of the time needed to ship a feature. Planning, review, testing, and rework take the rest. A plan lowers expected pain when it answers the questions that change the work, then stops.

MCP shows what that boundary looks like. A client discovers a tool, reads its schema, sends the named arguments, and refreshes its registry when the server changes. The description travels with the action. Someone can inspect what the application may call.

The intruder had no such boundary. It read a service-account token, queried Kubernetes, minted more tokens, and created a privileged pod with the host filesystem mounted. Each new permission exposed another route. The agent kept testing until one route reached the next system.

This is where the two kinds of speed meet. Faster execution multiplies whatever instructions and permissions surround it. A careful plan removes the expensive wrong turn. A precise schema limits a tool. A shared credential removes the limit.

The people who make execution cheap must spend their time deciding what the next action is allowed to touch.
