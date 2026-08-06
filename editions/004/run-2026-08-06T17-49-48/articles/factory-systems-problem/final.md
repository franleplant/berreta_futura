---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

Software factories are real. None of them are finished. The factory I mean is almost lights-out, and the lights-out part is a systems engineering and corporate culture problem, not a token problem. Anyone selling you one today is selling bullshit unless they belong to a very small cohort. Don't make your service bus non-deterministic. Build the whole stack at home.

## What isn't cracked

The innovators are toying with pieces and practices. That's the state of it. The exception is a handful of startups founded in the last six months, and maybe ten people in the who's-who who have spent two years trying and, realistically, failing. It isn't solved, but it's a puzzle being worked on daily.

## Where the work is

Not in the agents. In the things underneath them: sandboxing, monorepo, reproducible builds, CI/CD, identity and secret management, and the slow murder of corporate friction so that developer experience covers agents too. Tokens are a piece of the puzzle. They are not the puzzle.

## The bus

n8n was a silly idea — built, I suspect, by people who never worked in corporate and so never learned that service buses are a solved problem. The prior art sits in the spooky land of enterprise, a library everyone walks past: MassTransit, NServiceBus, WCF. WCF left me with bad memories as an implementation, but the theory holds and it's worth stealing from for prompting. If you want modern and plug-and-play, Temporal. Have a job invoke an agent as a process.

## Homelab

Learn the entire damn stack, automate it, then show it at your next interview or record a talk at a meetup. Highest ROI available right now: fast promotion, red carpet.

Blog post coming.
