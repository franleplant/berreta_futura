---
source_ids:
- building-commerce-agents-with-claude-4a77cb2e
content_mode: article
label: ARTICLE
---

Retailers running shopping agents on Claude have seen carts up to 35% larger and shoppers 60% more likely to complete a purchase. Today we're launching a blueprint for building commerce agents on Claude: the harnesses, patterns, and guardrails an engineering team needs to get one running in days. It holds reference implementations of a shopping agent and a merchant agent for retail, travel, telecom, and ticketing, plus a Claude Code plugin. It's available today, with live demos for each vertical.

## What's in the blueprint

Both agents can be built with the Messages API, the Agent SDK, or Claude Managed Agents (beta). You can watch them run in a self-guided demo before writing any code, then work with Claude Code to fit them to your catalogs, policies, and brand. The code deploys on the Claude API, Amazon Bedrock, Microsoft Foundry, or Google Cloud Vertex AI. Accenture, Mastercard, and Visa are working with us to bring the blueprints to their clients and merchant communities.

### The shopping agent

It lives inside your app or website. The blueprint includes the integration points for catalog, cart, checkout, customer preferences, and order history. Payment it leaves to you, whether your existing checkout or an agentic payments provider.

A customer can say "I need a tent, sleeping bag, and stove for a weekend trip with two kids," and the agent can take it from there. It searches the catalog and assembles the set, remembers preferences, shows products and the cart in the conversation, builds the cart and hands it to checkout. It also answers service questions about orders, returns, and refunds in the same conversation, instead of sending the customer to a support page.

Its guardrails are designed to constrain prices and products to actual catalog data, and it avoids manipulative upsell patterns.

### The merchant agent

It serves the people running the store. Ask "what should we discount to clear last season's inventory?" and the answer comes from the store's own data. It reports what's selling and what isn't, flags problems such as an item about to sell out before a promotion starts, recommends pricing and promotions from the sales history, and drafts campaigns.

When it suggests a change, a person approves it before anything goes live. The agent watches the store; the people keep the final say.

## What builders report

At Wix, "our engineers had a working commerce agent taking prompts within fifteen minutes," says Dror Zalika, Head of Commerce.

Akhil Bansal, Senior Engineering Manager, says their engineers had it running "with no blockers," and that its practices, "from tool iteration limits to prompt caching," are the ones they recognized from building Zomato's own agent.

Ashley Nader, Staff Product Manager, had both agents running locally "in well under an hour." Running the Claude Code workflow twice returned two different architectures, "each designed to what we'd asked for."

Partners keep returning to one word. Visa: "trust must remain at the center of every transaction." Mastercard: "Trust is the currency of commerce." Square: "Trust is the hardest part of that work, and Claude helps us meet a high standard."

## Getting started

Fork the repository at [github.com/anthropics/commerce-agents](https://github.com/anthropics/commerce-agents), read the [engineering deep-dive](http://claude.com/blog/the-anatomy-of-effective-commerce-agents), and see the vertical demos at [claude.com/solutions/commerce](https://claude.com/solutions/commerce). [Contact our sales team](https://claude.com/contact-sales) for a demonstration, or register for the [webinar](http://anthropic.com/webinars/building-claude-commerce-agents).
