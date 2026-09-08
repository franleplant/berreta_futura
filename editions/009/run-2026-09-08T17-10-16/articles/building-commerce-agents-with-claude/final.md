---
source_ids:
- building-commerce-agents-with-claude-4a77cb2e
content_mode: article
label: ARTICLE
---

Today we're launching a blueprint for building commerce agents on Claude: the harnesses, patterns, and guardrails an engineering team needs to get an agent running in days, with reference implementations of a shopping agent and a merchant agent for retail, travel, telecom, and ticketing platforms. It's available now, with a Claude Code plugin, live demos for each vertical, and an engineering deep-dive, just in time for holiday season planning. The shopping agent searches, compares, builds a cart, and answers support questions. The merchant agent reads the store's own data and proposes what to discount. Payment stays yours.

## What ships

Many of the world's largest retailers, marketplaces, e-commerce platforms, and travel companies already use Claude to build shopping agents. Shopify, Priceline, and others have agents that let consumers search in plain language, find, compare, and buy.

The repository holds complete, working implementations you can build with the Messages API, the Agent SDK, or Claude Managed Agents (beta), and deploy where you already build: the Claude API, Amazon Bedrock, Microsoft Foundry, or Google Cloud Vertex AI. Try the self-guided demo before writing code, then customize to your catalogs, policies, and brand with Claude Code. Accenture, Mastercard, and Visa are working with us to enable clients and merchant communities.

## The shopping agent

It lives inside your app or website. You get integration points for catalog, cart, checkout, customer preferences, and order history. Payment is left to you, whether that's your existing checkout or an agentic payments provider.

A customer says "I need a tent, sleeping bag, and stove for a weekend trip with two kids," and the agent can take it from there: search the catalog, assemble the multi-item set, remember preferences, show products, comparisons, and the cart inside the conversation rather than as text, and hand the cart to checkout. It can also say where an order is, how to return or exchange an item, and what the refund policy says, in the same conversation instead of at a support page.

A catalog is a finite list. The guardrails are designed to keep prices and products inside it, and to avoid manipulative upsell patterns. In the repository these arrive as skills and tools for catalog search, multi-item planning, deep research, personalization, customer care, and in-conversation UI.

## The merchant agent

It supports the people running the store. Ask "what should we discount to clear last season's inventory?" and get an answer based on your own data. It reports what's selling and what isn't, tracks inventory and proactively flags problems such as an item about to sell out before a promotion starts, recommends pricing and promotions from the store's sales history, and drafts campaigns to move the products that need moving. When it suggests a change, a person approves it before anything goes live: users get the final say while their agent watches the store. These ship as skills for sales analytics, catalog and inventory management, marketing and promotions, and in-portal UI such as charts and dashboards.

## Getting started

Fork github.com/anthropics/commerce-agents, read the deep-dive, and see the vertical demos, where you can request a working session. Contact our sales team to schedule a demonstration or discuss implementation, and register for the webinar for live walkthroughs.
