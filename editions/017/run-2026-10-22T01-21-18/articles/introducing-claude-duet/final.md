---
source_ids:
- introducing-claude-duet-f5220dab
content_mode: article
label: ARTICLE
---

Today, we're opening a research preview of Claude Duet, an app where Claude works as a proactive agent. It comes to you with what needs your attention, completes tasks you ask of it, keeps working when you step away, and checks with you before it acts on your behalf. It's built for professionals and small business owners, runs on iOS, Android, and claude.ai, and is included in Pro and Max plans under the same usage limits. Access starts by waitlist with US Pro and Max subscribers. It is early: it still might misread a thread or miscalibrate what's urgent.

## Judgment is the point

What makes Claude Duet helpful is its judgment. We designed it around Claude Opus 5.5 and built it to decide what needs you, what can wait, and when to check with you first. Each morning it sends a short brief on the most important items across your connected apps. During the day it messages you only when something needs your attention. You can hand it anything from scheduling meetings to building dashboards, financial or sales forecasts, prototypes, and web apps.

Early testers describe the effect. Jess Provencher, a broker, had a property showing flagged, unasked, because it sat on her calendar for the wrong day: "[This is] exactly the kind of thing I want caught without having to ask." Mya Dalton, a brand strategist, had Claude Duet prepare a brief for a client call and offer to move it, since it fell right before her flight. "I didn't realize that it was right before my flight," she said.

## How it works

Claude Duet carries over your memory, skills, and connected apps from your Claude account, so setup takes minimal work. You talk to it by text or voice in one ongoing thread. It has a virtual machine with its own browser, so it doesn't need your laptop or phone to be on, and it notifies you when a task is done or needs review.

It checks your connected accounts every few hours, because checking nonstop would use up your plan's limits much faster. We're still testing its judgment about when to message you, and you can tell it what you want to hear about and how often.

It reaches over 6,000 connectors and plugins in the Claude Marketplace, including Gmail, Slack, QuickBooks, Stripe, Gusto, Docusign, HubSpot, Canva, and Shopify. It can buy things through Link, Stripe's digital wallet, paying with a virtual card so your real card number isn't shared.

## What stays with you

Claude Duet reads, drafts, and prepares on its own. Before it sends a message, makes a payment, signs a document, or deletes anything, it shows you exactly what it's about to do and waits for approval. Some things are off-limits even with approval, like trading securities or moving money between accounts. You can disconnect any app.

Its safeguards come from existing work: credentials are handled as in Claude Managed Agents, so it never directly sees your passwords or sign-in tokens; actions are approved by our auto mode classifier; prompt-injection defenses come from our browser-use research. Red teams and an external firm penetration tested it.

A new classifier and safety system prompt check each message for leaks. They're designed to reject sharing the strictest tier of information, such as credit card numbers and government identification. Health or personal finance details go out only when you've explicitly instructed it. We're continuing to strengthen these protections.

## Limits of the preview

Personal errands, such as booking tickets, aren't as strong as work tasks, and it can't yet show you its browser. It lives in its own app, separate from the main Claude app. Its background checks count toward your usage limits, and larger tasks, like a financial model or a deck, take more model turns and background work.
