---
source_ids:
- uber-engineering-en-x-designing-mcp-gateway-uber-c421ca43
content_mode: article
label: ARTICLE
---

Early MCP integrations at Uber showed that agents grow far more capable when they can reach live business context, query internal services, and act for users. But teams built those integrations separately, and the result was fragmented, duplicated, hard to discover, and hard to run. We built the MCP Gateway: one microservice between AI agents and our back-end services and native MCP servers. A registry catalogs servers and tools. A proxy translates MCP calls into HTTP, gRPC, or TChannel and back. A crawler turns existing APIs into tools, each one disabled until its owners enable it. The gateway now hosts over 800 MCP servers and over 5000 tools.

## Why a gateway

As hundreds of teams began exploring agentic workflows, ad-hoc integrations didn't meet our needs. Without a unified architecture, scaling MCP would increase operational complexity, security risk, and developer friction. We needed one place to abstract protocol differences, enforce consistent security and observability, and make tools easy to create, discover, and reuse.

The gateway has two parts: the MCP Registry, which is the control plane, and the Proxy Gateway, which is the data plane.

## Control plane

Thousands of internal services expose APIs over HTTP, gRPC, and TChannel. Asking teams to author MCP servers by hand would be slow and painful, so we built AutoCrawler, a Cadence-powered workflow that, on a fixed schedule, scans Uber's IDL registry for new services, APIs, and schema changes.

For Protobuf or Thrift services, AutoCrawler creates or updates a virtual MCP server, parses the IDL for method names, schemas, and documentation comments, uses an LLM to write agent-friendly tool descriptions, translates the schemas into MCP-compatible JSON-RPC 2.0 schemas, and registers the tools.

Native MCP servers, built with our MCPFx framework, emit a heartbeat metric. AutoCrawler watches for it, makes a *listTools* call to each new server, and creates a virtual proxy server holding its tools.

Third-party servers such as Jira and Google rely on two pieces. The gateway relays the caller's user token while enforcing authorization, rate limiting, and sensitive data redaction. A Third-Party MCP Service exchanges that token for the external one.

We may create a server without the service team, but the team owns it. Every server and tool starts disabled, and the owning team must review and enable it. Every change to a tool description produces a config diff that owners approve, deploy, and, if needed, roll back.

## Data plane

The data plane consumes configurations from the control plane and refreshes its in-memory state at a fixed cadence, so changes take effect without restarts or redeployments. Each virtual server gets a single */<service-name>/mcp* endpoint.

For IDL-backed tools, the handler translates the JSON payload into the wire format, serializes it into Protobuf or Thrift bytes, forwards it, and translates the reply back into MCP-compatible JSON. Requests run through Muttley, our service mesh sidecar, so the gateway inherits existing service-to-service routing. Native MCP requests are proxied through to the downstream server and back.

Authorization and redaction apply to every server at tool granularity. Our Access Control System applies charter policies to callers (humans, services, and agents), set per server with optional tool-level overrides. PII and sensitive data are redacted from tool responses out of the box.

## Extending the gateway

At hundreds of servers and thousands of tools, problems appeared that don't exist at small scale: context bloat and excessive cost. MCP has no native cross-server search. An agent must already know which server to talk to, and wiring up hundreds of servers would eat up the model's context limit. We added three things.

- **Omni MCP:** a single proxy server that reaches every gateway server through incremental discovery, using four tools: `discover_server`, `discover_tools`, `get_tool_schema`, and `invoke_tool`.
- **Response Projection:** a GraphQL-like calling pattern. A field injected into the tool request schema lets the LLM list the nested paths it needs, and the gateway trims the response to those fields at runtime.
- **Code Mode:** aifx, Uber's CLI for agentic operations, routes MCP calls through the gateway with no MCP server installed, through `aifx mcp list`, `aifx mcp search`, and `aifx mcp call`. Agents chain them, write output to files, and grep only what they need. Code Mode is now the company default for MCP tool use in coding agents.

## Conclusion

Our core insight was simple: existing APIs are the fastest way to give an agent tools. Rather than asking teams to rewrite their services, the gateway translates their HTTP, gRPC, and TChannel calls into MCP through Muttley, with zero changes to downstream services.

If you're building agentic systems at scale, the hardest part isn't the AI. It's the connective tissue: the discovery, the security, the reliability that makes agents trustworthy enough to act for real users in production.
