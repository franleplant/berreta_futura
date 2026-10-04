---
source_ids:
- 8-major-updates-to-cloudflare-observability-cd838e82
content_mode: article
label: ARTICLE
---

Today, we're launching eight updates that bring your logs, traces, analytics, alerts, dashboards, and exporting into one observability platform, with simpler and more predictable pricing. Logs from across Cloudflare now share one home. Traces follow a request from our edge to your origin (open beta). One SQL API, in beta, lets people and agents query it all. Alerts and dashboards can be built on that data, domain analytics keep 30 days on every plan, and Logpush reaches all self-serve plans. From December 1, 2026, logs and traces are priced by the volume you ingest and store.

## Why one platform

A spike in 5xx responses could come from a Worker, from your origin, or from Cloudflare failing to connect to your origin globally or regionally. Investigating it today requires knowing which product owns each signal and how to query it. Observability should be a platform-wide capability that gives you the complete context needed to resolve an issue. Over the coming months, more Cloudflare products, datasets, and workflows will join this shared platform. These eight updates are the first step.

## Logs

The new Logs home combines Workers Observability, for debugging Workers applications and their connected resources, with Log Explorer, for searching security logs. Choose a dataset (HTTP events, firewall events, Workers, Containers, R2, AI Gateway) and use the same tools on each.

Start with an increase in request latency, group it by hostname or data center, narrow to affected paths, and inspect individual requests by Ray ID. If the investigation leads to another Cloudflare product, switch datasets without leaving Logs. Querying across multiple datasets at once is coming soon. You can use raw SQL or built-in filters, create visualizations with natural language, and investigate detected anomalies.

## Traces, in open beta

Cloudflare Traces gives a request-level view of supported security rules, transformations, cache decisions, routing, Workers, and origin handling. You see how your traffic moved through our platform and how your configuration influences processing time and routing decisions.

Set a baseline sampling rate, then use Trace Rules to capture specific traffic at a higher rate during an investigation, targeting hostnames, paths, IP addresses, or headers. Search by Ray ID and inspect the spans in the dashboard. Traces export over OpenTelemetry, and W3C trace context propagation lets you accept incoming trace context and pass it along to your origin.

## One SQL API, in beta

Agents need a consistent way to sift through observability data, investigate issues, correlate signals, and verify fixes. Instead of integrating separately with Workers logs, Containers security events, HTTP request logs, and analytics data, people and agents can query them with one SQL dialect, authentication model, and API. Your agent can use the new `cf` CLI or Cloudflare's Observability MCP server. Dataset schemas, fields, and example queries are documented.

A native binding brings the same SQL into Workers. Your Worker can query Analytics Engine data to meter customer usage and power billing workflows, build customer-facing analytics dashboards, generate health reports, or automate incident investigation, without configuring a separate API client.

## Pricing

Beginning **December 1, 2026**, one Observability subscription will cover all logs and traces ingested and stored on Cloudflare. It applies across all plans (effective upon renewal for Enterprise customers) and covers existing Developer Platform logs, including Workers, Containers, and AI Gateway, as well as all tracing data. Because logs and traces vary dramatically in size, the model is based on the **volume you ingest and store**, not an event count.

| Plan | Included Usage | Retention | Additional usage |
| --- | --- | --- | --- |
| Free | 0.5 GB of ingestion per day | 7 days | Not available |
| Paid and Enterprise | 50 GB of ingestion <br>10 GB-month of storage per billing cycle | Up to 1 year <br>(coming soon) | $0.25 per GB ingested<br>$0.10 per GB-month stored |

## Alerts, in beta

Notifications, now called Alerts, can be defined on anything the unified SQL API supports: HTTP request logs, Workers events, Workers Analytics Engine datasets, analytics datasets, traces, and security events. Choose a dataset or write custom SQL, select a threshold, anomaly, or SLO, set the evaluation window, and choose where the alert goes. You might alert when origin 5xx responses exceed a threshold for five minutes, a Container repeatedly fails, Worker errors increase after a deployment, or trace latency crosses an expected limit.

Alerts can go to incident management tools, chat platforms, and webhooks. Webhooks are now available on all plans, so an alert can reach a custom service, or your agent, to begin investigating immediately.

## Domain analytics and custom dashboards

We're bringing traffic, performance, security, cache, origin, and DNS data together. If latency increases, you can quickly see whether it is tied to a specific Cloudflare data center, hostname, or origin. Every plan now gets 30 days of domain analytics: time to investigate after the fact, compare today with the same day in previous weeks, and tell a one-time spike from a longer trend.

Custom Dashboards bring analytics from across Cloudflare, logs and traces from the Workers platform, and security events into one view you can share with your team. Instead of rebuilding queries during every investigation, you have one place to monitor the signals that matter.

## Logpush for self-serve plans

Logpush, previously Enterprise-only, is now available on all self-serve plans, exporting all Cloudflare logs to the tools and destinations you already use. Transformers, now generally available, applies any SQL transformation (filtering, redaction, enrichment, reshaping) before delivery, without a separate ETL pipeline. Both get usage-based pricing with a free monthly allowance:

| Export usage | Included each month | Additional usage |
| --- | --- | --- |
| Exports to Cloudflare destinations | 25 GB | $0.03 per GB |
| Exports to external destinations | 25 GB | $0.10 per GB |
| Logpush Transformers | 1 GB | $0.04 per GB |

## What's coming

- Retention of logging and tracing data for up to one year.
- More OpenTelemetry APIs in Workers, for adding attributes to existing spans or getting trace context.
- Export of Cloudflare metrics to OpenTelemetry-compatible destinations.
- The new pricing, on December 1, 2026. We'll notify you before it takes effect.

## Why it matters

We hear you when you say Cloudflare can feel like a black box. These updates are just the beginning of exposing what's happening and making the underlying data accessible. That transparency matters even more as agents move from writing software to operating it. An agent can only close the loop between a change and its outcome if it can query what happened, identify the failure, and verify the fix. By building around OpenTelemetry, W3C Trace Context, and SQL, we are committed to giving you and your agents standard, portable interfaces to that context.
