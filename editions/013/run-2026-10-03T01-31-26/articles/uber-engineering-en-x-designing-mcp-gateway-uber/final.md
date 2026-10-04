---
source_ids:
- uber-engineering-en-x-designing-mcp-gateway-uber-c421ca43
content_mode: article
label: ARTICLE
---

As hundreds of Uber teams began building agents, each wired up MCP (Model Context Protocol) on its own. The result was fragmented tooling, duplicated infrastructure, and tools that were hard to discover, hard to operate reliably, and tied to particular services or agents. We built the MCP Gateway to fix this. It's a single microservice between AI agents and our back-end services. It translates MCP into HTTP, gRPC, and TChannel and back, enforces consistent security and observability, and makes tools easy to create, discover, and reuse. It currently hosts over 800 MCP servers and over 5000 tools.

## Two halves

The platform has two parts. The MCP Registry is the control plane: a catalog of servers and tools, and the single source of truth for discovery, ownership, and enablement. The Proxy Gateway is the data plane: it executes MCP requests at runtime, forwards them to the right back-end service, and converts the responses into MCP results. The underlying services don't change.

## Control plane

Uber runs thousands of internal services. Asking each team to hand-write an MCP server would be slow and painful, so we built AutoCrawler. It's a Cadence-powered workflow system subscribed to Uber's IDL registry and internal service signals. On a fixed schedule it scans for new services, APIs, and schema changes.

For services defined in Protobuf or Thrift, AutoCrawler creates or updates a virtual MCP server and parses the IDL for method names, schemas, and documentation comments. An LLM then writes agent-friendly tool descriptions from those, and the schemas are translated into MCP-compatible JSON-RPC 2.0. Each tool is registered disabled.

Native MCP servers, built with our MCPFx framework, emit a heartbeat metric. AutoCrawler watches for it, calls *listTools* on each new server, and creates a virtual proxy server in the registry, also disabled.

Third-party servers such as Jira and Google work differently. The gateway relays the caller's user token while enforcing authorization, rate limiting, and redaction. A separate service exchanges that token for a third-party one.

The governing principle is that discovery doesn't imply exposure. We may create a server without the service team, but the team owns it. Owners review and refine the generated definitions and enable them. Every change to a tool description produces a config diff that owners must approve, and they can roll back to a previous known version.

## Data plane

The data plane reads server and tool configuration from the control plane and refreshes its in-memory state at a fixed cadence, so changes take effect in real time without restarts or redeployments. Each virtual server gets one */<service-name>/mcp* endpoint.

Security is built in at tool-level granularity. Uber's Access Control System applies charter policies to the detected caller, whether human, service, or agent. Policies are set per server, with optional per-tool overrides. PII and other sensitive data are redacted from responses.

For an IDL-backed tool, the handler translates the JSON payload into the wire format, serializes it into Protobuf or Thrift, forwards it, and translates the reply back into JSON. The call runs through Muttley, Uber's service mesh sidecar, so the gateway gets existing service-to-service routing for free. Native servers are proxied transparently in both directions.

## At scale

Hundreds of servers and thousands of tools brought problems that don't exist at small scale: context bloat and excessive cost.

MCP has no cross-server search. An agent must already know which server to call, and wiring up URLs, credentials, and tool lists for hundreds of servers would consume the model's context limit. Omni MCP is a single proxy that lets clients reach every gateway server through incremental discovery, using four tools: *discover_server*, *discover_tools*, *get_tool_schema*, and *invoke_tool*.

Response Projection works like GraphQL. The gateway adds a field to the tool's request schema, the LLM fills it with paths to the fields it needs, and the gateway trims the response to those fields at runtime.

Code Mode serves coding agents in shell environments, where writing output to files is more efficient than loading it into context. Through aifx, Uber's CLI for agentic operations, agents run `aifx mcp list`, `search`, and `call`, write the results to files, and grep only what they need. No MCP server needs to be installed. Code Mode is now the company default for MCP tool use in coding agents.

## Conclusion

Our core insight was that existing APIs are the fastest way to give an agent tools. Rather than asking teams to rewrite their services, the gateway translates their calls with zero changes downstream, and any team can plug in within minutes.

If you're building agentic systems at scale, the hardest part isn't the AI. It's the connective tissue, the discovery, the security, the reliability, that makes agents trustworthy enough to act for real users in production.
