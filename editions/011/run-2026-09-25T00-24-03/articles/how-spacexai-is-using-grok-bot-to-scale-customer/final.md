---
source_ids:
- how-spacexai-is-using-grok-bot-to-scale-customer-03d2992c
content_mode: article
label: ARTICLE
---

When Cursor became part of SpaceXAI on August 14, our two support teams began merging around a broader portfolio, just as we prepared to launch Grok Bot, an AI teammate you can give real work to. We put Grok Bot to work throughout support. Our combined team has seen a 175% increase in tickets, and we have not had to hire anyone; we might have hired 200 additional people otherwise. Traditional AI support tools charge a flat $1 to $4 per resolution. With Grok Bot, you pay only for actual usage, already included in your plan, and with minor optimizations we've resolved tickets for as low as $0.20 to $0.30.

## Crawl, walk, run

We connected Grok Bot to a few core systems, Plain for ticketing and Linear for issue tracking, and had it act as though it owned tickets. It could write only internal notes, and every write action needed human approval. This let us check whether it understood each issue and proposed the right next step without touching the customer experience.

As results became more reliable, we added traces and evaluations to every run. When something went wrong, we could see where Grok Bot had gone off course, adjust, and try again. Grok Bot could analyze these runs itself.

Then we rolled it out on the least complex tickets. On the first day, we reviewed its interpretations and proposed responses by hand. By the end of the day, we trusted it to answer customers directly, and we widened its range gradually from there.

## From intake to resolution

Most of the time it takes to resolve a ticket goes to discovery, investigation, and troubleshooting, so Grok Bot pre-investigates every ticket the moment it enters our system. This could get expensive. We've classified common issues to spend fewer tokens, and we don't exhaust troubleshooting capacity when a help center check does the trick.

For known issues (it connects to Linear) or common backend errors (it connects to Datadog), we've trained Grok Bot to add to the existing issue or create a new one. It also reproduces the issue on video, which helps engineering resolve it quickly.

We've trained it on over one million customer interactions, so it has learned our tone and voice from our humans. It pushes every ticket toward resolution and won't ask a question whose answer is already in our logs. Given clear refund instructions, it resolves 99% of refund requests without human intervention.

## Managing the queue

Grok Bot watches inbound volume continuously. It reprioritizes tickets, reassigns ownership by urgency, and alerts the organization when we near a response-time SLA breach.

When volume around one issue reaches a set threshold, it can declare an incident automatically. It also monitors X for shifts in sentiment and repeated reports of the same problem. At our scale, raw volume alerts would create a lot of noise, so Grok Bot judges whether a spike is a real support issue and begins investigating before it alerts the team.

## Improving the operation

Grok Bot reviews interactions handled by both people and Bots, gives specific feedback, and surfaces coaching opportunities for each. Every week it sends leadership a summary of where our AI responses fall short. Sometimes the answer is more training or better documentation; other times the summary confirms that our guardrails are working.

As more users ask Grok for support, our help center increasingly becomes source material for its answers. To keep those answers accurate, Grok Bot reviews changes to our codebase and suggests matching help center updates.

Grok Bots now coach other Grok Bots: they find gaps in the knowledge system, fill them, and feed what they learn back in. The teachers and the taught are the same machine. We are scaling this loop across the portfolio to cover every product surface.

## Turning data into decisions

Grok Bot has become our default data analyst, posting daily reports to our Slack channels. When a ticket goes back and forth more than three times between a customer and one of our team members, human or Bot, it flags the interaction for management review so leadership can step in and save the experience. As it learns which signals the team finds useful, its reporting becomes more relevant.

Each day it synthesizes more than 20,000 points of product feedback from tickets into clear themes for engineering, showing the product team where customers struggle.

## How the team changes

Grok Bot is still a new way of working, but it has already changed how our team operates. Instead of spending most of the day on repetitive work, we set guardrails, handle cases that require judgment, and decide how the operation should improve. We are still learning what this model makes possible, and we will keep sharing what we find.
