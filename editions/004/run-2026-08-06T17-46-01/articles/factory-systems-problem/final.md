---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

Software factories are real, but nobody has cracked them. The people worth listening to are a handful — a few startups born in the last six months, maybe ten known names who have spent two years mostly failing at it. Anyone else selling you a factory is selling bullshit.

The bottleneck is not tokens. It is not how you apply tokens. It is systems engineering and corporate culture. The work that matters is the unglamorous work: sandboxing, monorepos, reproducible builds, CI/CD, identity and secret management, and grinding down the corporate friction that keeps agents from having a decent developer experience. Almost lights out.

And don't make the service bus non-deterministic. n8n was a silly idea — the sort of thing built by people who never worked in a corporation and so never learned that service buses are a solved problem. The prior art sits in the enterprise: MassTransit, NServiceBus, WCF. Or take Temporal, plug it in, and have a job invoke an agent as a process. Determinism in the bus; the agent is the piece that gets to be strange.

## What to do about it

Build the abstractions and the pieces. Almost all of them are non-agent problems.

Do it at home, in your homelab, on your own time. Learn the whole stack, automate it, then show it — at your next interview, or in a recorded talk at a meetup. That is the highest return available right now: a fast promotion and red carpet service at the next door you knock on.

## The tail

WCF is not great technology. The theory and the education in it are generally on point, which is why it is still worth stealing from for prompting.

It isn't cracked. It is a puzzle being solved daily.
