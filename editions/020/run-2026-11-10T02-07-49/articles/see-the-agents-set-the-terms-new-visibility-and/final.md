---
source_ids:
- see-the-agents-set-the-terms-new-visibility-and-982ed481
content_mode: article
label: ARTICLE
---

Personal agents turn a person’s instructions into requests on websites. To a site owner, that shows up as automated traffic, and blocking it all can mean losing customers. Today, we’re launching analytics that show which personal agents visit your site and what they do, plus per-agent access policies, so you can welcome agents on your own terms.

## See the agents

Cloudflare maintains the largest verified bot directory in the world, and we’re bringing it into your traffic details. In Security Analytics, Bot Analysis now shows Personal Assistants as a category, beside Verified Bot, Likely Human, Likely Automated, and Automated. A new Personal Assistants widget in Top statistics lists which agents visit and how many requests each sends. Filter on one, and every other widget shows only its traffic: the paths it requests, the status codes it receives, the networks it comes from. You can see whether an agent is logging in, reading product pages, reaching checkout, or hitting errors on pages it cannot use.

Sites using Account Abuse Protection (currently in early access) can also see which user each agent represents. They see which agents are active across their users, how many accounts use them, and, on every login and sign-up, whether a personal agent made the request and which one. A fraud analyst can tell an agent the customer has relied on for weeks from one that appeared for the first time today. If an attacker seems to be using an agent on an account, analysts can mitigate that account with a WAF rule on its Hashed User ID, without blocking the agent for everyone else who relies on it.

## Set the terms

This summer we introduced AI bot policies, with separate choices for Search, Training, and Agent behaviors. We’re now expanding the Agents policy with controls for each supported personal agent, and renaming the setting **AI Crawler and Agent access policies**. In **Security Settings**, set an overall Agents policy, then choose for each supported agent: **Allow (do not block)**, **Block on pages with ads**, or **Block**. Your Search and Training policies stay as they are. When you add a new zone, we ask whether you monetize pages with ads and tailor the recommended policies to your answer; you can revisit them later.

One publisher may allow a supported agent throughout its site so readers can find its articles. Another may block that same agent on pages where ads support the content. Both are choosing what works for their business.

## What comes next

A site may recognize the agent making a request yet lack what it would otherwise know about the user: whether they are an existing customer, what they authorized the agent to do, whether they have a subscription, which protections should apply. Our next goal is to help sites keep that context. Reaching it will require privacy-aware ways to carry user context through an agent, help sites assess reputation, and establish clear accountability when something goes wrong. We’ll be sharing more as we work with agent operators and others across the ecosystem.

The person asking an agent to compare products, find support, or complete a purchase is still a customer trying to reach your business. Review how personal agents access your site, then set your terms in **Security Settings → AI Crawler and Agent access policies**.
