---
source_ids:
- 8-major-updates-to-cloudflare-observability-cd838e82
content_mode: article
label: ARTICLE
---

Today we're launching eight updates that bring logs, traces, analytics, alerts, dashboards, and exporting into one observability platform, with simpler and more predictable pricing. Logs from across Cloudflare now share one home. Traces follow a request from our edge to your origin. One SQL API serves people and agents alike. From December 1, 2026, logs and traces are priced by the volume you ingest and store. Alerts and dashboards draw on the same data, domain analytics keep 30 days on every plan, and Logpush reaches all self-serve plans.

## Why one platform

A spike in 5xx responses could come from a Worker, from your origin, or from Cloudflare failing to connect to your origin, globally or regionally. Investigating it today requires knowing which product owns each signal and how to query it. Observability should be a platform-wide capability. Over the coming months, more Cloudflare products, datasets, and workflows will join, with more consistent pricing, product experiences, and features. These eight updates are the first step.

## Logs in one place

The new Logs home combines Workers Observability with Log Explorer. You choose a dataset (HTTP events, firewall events, Workers, Containers, R2, AI Gateway) and use the same tools on each. Start with a rise in latency, group it by hostname or data center, narrow to affected paths, and inspect single requests by Ray ID. If the trail leads to another product, switch datasets without leaving Logs. Querying across multiple datasets is coming soon. You can query with raw SQL or built-in filters, create visualizations in natural language, and investigate detected anomalies.

## Tracing, in open beta

Cloudflare Traces gives a request-level view of supported security rules, transformations, cache decisions, routing, Workers, and origin handling, connecting how you've configured Cloudflare to processing time and routing decisions. Set a baseline sampling rate, then use Trace Rules to capture specific traffic at a higher rate during an investigation, targeting hostnames, paths, IP addresses, or headers. Traces export over OpenTelemetry, and W3C trace context propagation accepts incoming context and passes it on to your origin.

## One SQL API, in beta

Instead of integrating separately with Workers logs, Containers security events, HTTP request logs, and analytics data, people and agents can query them with one SQL dialect, authentication model, and API. Agents can use the `cf` CLI or Cloudflare's Observability MCP server. A native Workers binding lets a Worker query Analytics Engine data to meter usage and power billing, build customer-facing dashboards, generate health reports, or automate incident investigation, without a separate API client.

## New pricing

Beginning **December 1, 2026**, one Observability subscription applies across all plans (upon renewal for Enterprise customers), covering existing Developer Platform logs, including Workers, Containers, and AI Gateway, and all tracing data. Because logs and traces vary dramatically in size, pricing follows the **volume you ingest and store**, not an event count.

| Plan | Included | Retention | Additional |
| --- | --- | --- | --- |
| Free | 0.5 GB ingestion per day | 7 days | Not available |
| Paid and Enterprise | 50 GB ingestion, 10 GB-month storage per billing cycle | Up to 1 year (coming soon) | $0.25 per GB ingested, $0.10 per GB-month stored |

## Custom alerts, in beta

Notifications, now called Alerts, can be defined on anything the SQL API supports: HTTP request logs, Workers events, Workers Analytics Engine datasets, analytics datasets, traces, and security events. Pick a dataset or write SQL, choose a threshold, anomaly, or SLO, set the window, and choose a destination. You might alert when origin 5xx responses exceed a threshold for five minutes, or when Worker errors rise after a deployment. Webhooks are now on all plans, so an alert can reach a custom service or your agent.

## Domain analytics, with 30 days

Traffic, performance, security, cache, origin, and DNS data now sit together, so when latency rises you can see whether a data center, hostname, or origin is involved. Every plan gets 30 days of history: enough to compare today with the same day in previous weeks and to tell a one-time spike from a trend.

## Custom dashboards

Custom Dashboards bring analytics from across Cloudflare, Workers logs and traces, and security events into one shared view of request volume, errors, latency, storage, and blocked traffic.

## Logpush on self-serve plans

Logpush, previously Enterprise-only, now exports all Cloudflare logs on every self-serve plan. Transformers is generally available, applying any SQL transformation (filtering, redaction, enrichment, reshaping) without a separate ETL pipeline.

| Export usage | Included monthly | Additional |
| --- | --- | --- |
| To Cloudflare destinations | 25 GB | $0.03 per GB |
| To external destinations | 25 GB | $0.10 per GB |
| Logpush Transformers | 1 GB | $0.04 per GB |

## Coming up

Retention of logs and traces for up to one year; more OpenTelemetry APIs in Workers, such as adding attributes to existing spans or getting trace context; metrics export to OpenTelemetry-compatible destinations. The new pricing takes effect December 1, 2026, and we'll notify you before it does.

## Ready to start investigating?

We hear you when you say Cloudflare can feel like a black box. These updates are just the beginning of exposing what's happening and giving you the context to act. That matters more as agents move from writing software to operating it. An agent can only close the loop between a change and its outcome if it can query what happened. By building on OpenTelemetry, W3C Trace Context, and SQL, we're committed to giving you and your agents standard, portable interfaces to that context.
