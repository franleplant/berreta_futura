---
source_ids:
- revisiting-some-of-my-priors-about-openclaw-a876bb49
content_mode: article
label: ARTICLE
---

Peter Steinberg was ahead of his time with OpenClaw. I ran it for a bit, but I couldn't see the value, because I didn't want to maintain it while the lethal trifecta problem remains unsolved. What I want is OpenClaw, managed: a product team losing sleep over the trifecta instead of me. It's not full protection. For almost a year that meant Interaction Labs Poke. Last week I switched to Grokbot full-time, after Poteto nerd-sniped me on X and, in full disclosure, gave me enough credits to reevaluate. The lesson so far: build small bots, one per function, and pipe them together. Most importantly, these tools carry risks.

## Why Managed

The lethal trifecta is, categorically, a billion-dollar problem, perhaps more. I'd rather make it someone else's problem as much as possible. Knowing a product team is paid to think about these issues and resolve them at scale puts me at ease.

I'm writing this of my own free will, hoping it changes some people's view of what these assistants are for, and above all to highlight the risks.

## Now What?

Grokbot is weird. The hardest thing about it is how generic it is. Once installed, the question becomes "now what?" You need curiosity and imagination. When you have an idea, ask for it. If functionality is missing, ask for it and turn it into a skill.

Install the dr eggbot skill pack first. Every time you need a new bot, which is often, ask it to create one.

## Some Bots

- **Inbox Diet** finds newsletters worth unsubscribing from and lists them for me to click. I've unsubscribed from probably upwards of 300. Finally, my inbox is under control.
- **Conference Reimbursement** watches PocketSmith for travel money that community conferences promised to reimburse. Right now I'm probably out close to $10,000 this year. If the money hasn't landed, the bot asks my permission before nudging anyone by WhatsApp or email.
- **Family** digests WhatsApp messages about my kids and pulls classwork and homework reminders from school emails.
- **WhatsApp** and **Mac Mini** are function pipes for other bots. The bot reaches my Mac Mini over Tailscale, which also lets it tunnel out past geo-blocks on data center IPs.
- **PocketSmith** categorizes my spending with an LLM instead of relying on me to train the rules. It is good.

## Lessons Learned

Don't build a fat bot. Build one bot per function, as on the Unix command line: small bots that call other small bots, piped together in a chain. You can also install software on a Grok bot; I tunnel through Tailscale.

## The Future

If the lethal trifecta is ever solved at a fundamental level, I'll move all this into a self-hosted OpenClaw, but not before. OpenClaw does a good job with security. Still, I sleep better knowing a product team's arse is on the line, with staff, a funded security organization, and a VDP program that loses sleep over these topics so I don't have to.
