---
source_ids:
- the-2026-07-28-mcp-specification-release-candida-1a1752b8
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---

The headline change is that MCP is now stateless at the protocol layer. The protocol is no longer fundamentally tied to specific session metadata, meaning that a remote MCP server that used to require sticky sessions, a shared session store, and deep packet inspection at the gateway can now operate simply behind a plain round-robin load balancer. This architectural rework delivers on the 2026 roadmap, allowing the entire system to scale without rewriting the underlying HTTP infrastructure.

This shift is achieved by removing the initial `initialize` handshake and the concept of the `Mcp-Session-Id` header. Where calls once required establishing a session first, the new version allows any server instance to handle a self-contained request. Instead of relying on hidden, transport-level metadata, all necessary context—the protocol version, client info, and method—is carried explicitly in the headers.

This forced the adoption of an explicit-handle pattern for managing application state. Instead of relying on an externally managed session, the model now has to pass identifiers (like a `basket_id`) as ordinary arguments through tools. As we’ve found, this is more than a workaround for session state; the explicit handling makes the state visible to the model, allowing it to compose handles across tools and reason about them in ways that previous session constraints never really allowed.

This new statelessness also refactors how servers ask clients for mid-call input. Instead of holding a Server-Sent Events stream open, multi-round-trip requests are handled by the server returning a structured JSON result that includes the requested input and the necessary `requestState`. Crucially, a user is never prompted out of nowhere, and every elicitation traces back to something they (or their agent) started.

The foundation is stabilized by treating peripherals as first-class citizens. Extensions now have formal mechanisms, being identified by reverse-DNS IDs and living in their own repositories. Likewise, the Tasks capability has graduated to a dedicated extension lifecycle. On the security side, requirements now align more closely with modern OAuth 2.0 and OpenID Connect deployments, forcing clients to validate the `iss` parameter on all authorization responses.

This release contains essential, foundational changes, but the deprecations of core features like Roots, Sampling, and Logging are temporary. These methods, types, and capability flags remain functional for at least a year, allowing implementers to adopt future revisions without immediately rewriting transport or lifecycle code.

Future revisions should, therefore, be built on a protocol that can run entirely without relying on sticky routing or shared stores, only requiring a clean, stateless protocol exchange.

Goodbye,
David Soria Parra and Den Delimarsky
