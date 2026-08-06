---
label: "EDITORIAL: ORIGINAL EDITOR TEXT"
title: "The Message Carries Its Own Passport"
byline: The Editors
---

When a connection drops, the client can return without reconstructing the server’s memory: the next request carries the protocol version, capabilities, and client identity in `_meta`.

Reliability therefore sits in each message. MCP links hosts, clients, servers, transports, and discovery, yet a local process using standard streams and a remote service using HTTP can speak the same JSON-RPC language. The transport moves the envelope; it does not own the meaning.

That makes integrations easier to inspect. A tool declares its name and input schema. The client can cache the list, subscribe to changes, and refresh it when a notification arrives. Those notifications are best effort, so after reconnecting, a client polls when it needs to know whether its picture is current.

The practical lesson reaches beyond MCP. Put the facts needed to interpret an action beside the action. A registry earns trust when its contents can be inspected and refreshed. Context carried with each request gives a system fewer hidden stories to remember.

Then failure becomes ordinary: one request is lost, another arrives with enough context to stand on its own. The ghosts leave fewer places to hide.
