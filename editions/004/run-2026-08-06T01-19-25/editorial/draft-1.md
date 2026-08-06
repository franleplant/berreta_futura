---
label: "EDITORIAL: ORIGINAL EDITOR TEXT"
title: "The Message Carries Its Own Passport"
byline: The Editors
---

A connection drops. When it returns, the client does not need to remember what the server believed about it. The next request carries the protocol version, capabilities, and client identity in `_meta`.

That small design choice changes where reliability lives. MCP still has hosts, clients, servers, transports, and a discovery exchange. But the durable unit is the message. A local process using standard streams and a remote service using HTTP can speak the same JSON-RPC language because the transport moves the envelope without owning its meaning.

This makes integrations easier to reason about and harder to fake. A tool declares its name and input schema. The client can cache the list, subscribe to changes, and refresh it when a notification arrives. Since those notifications are best effort, a reconnect is also a reminder to poll when freshness matters.

The practical lesson reaches beyond MCP. Put the facts needed to interpret an action beside the action. Make the registry observable. Treat a live connection as a convenience, not a memory.

Then a failure becomes ordinary: one request is lost, another arrives with enough context to stand on its own. The server has fewer stories to remember, and your system has fewer ghosts to debug.
