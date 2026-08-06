---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

software factories are real. nobody has cracked them. the hard parts aren't the agents — they're sandboxing, monorepos, reproducible builds, ci/cd, identity and secrets, and the corporate friction strangling devex. not a token problem. a systems engineering and culture problem. keep the bus deterministic; let a job invoke the agent. build it in your homelab and you'll walk into your next interview on a red carpet.

## who's actually selling one

the factory aspects haven't been cracked. innovators are still toying with the pieces. if someone is selling you a factory today and they aren't a startup born in the last six months, or one of the ten-odd names who have spent two years trying and mostly failing, they are selling bullshit. it isn't solved. it is a puzzle being solved daily — the sort you can only map by walking it.

## the work that isn't agent work

almost lights out is the target. getting there means building the abstractions and pieces, and those live outside the agent: sandboxing, monorepo, reproducible builds, ci/cd, identity and secret management, and smashing the corporate friction around developer experience for agents.

tokens are a piece of the puzzle. they are not the puzzle. no amount of them, and no clever application of them, gets you a factory.

## the bus stays deterministic

n8n was a silly idea — the work, i suspect, of young people all in on the llm craze who never spent a day in corporate and so never learned that service buses are a solved problem. the prior art sits in the spooky land of enterprise. look at mass transit, nservicebus, wcf in the .net space if you want ideas worth stealing for prompting. the wcf implementation was not great tech; the theory and the education generally hold.

for something modern and plug and play, temporal exists. use it. have a job invoke an agent as a process. don't make the entire service bus non-deterministic.

## the homelab payoff

do this at home, in your free time, if you want a fast promotion. the highest roi available right now: learn the entire damn stack, automate it, and show it — at your next interview, or on a recorded talk at a meetup.
