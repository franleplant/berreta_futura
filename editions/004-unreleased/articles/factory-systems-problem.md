---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

## Software factories are super real

Software factories are real, but we need to be realistic. The factory itself isn’t cracked; innovators are still discovering practices and pieces.

If someone is selling you a factory now and they aren’t in the small cohort of startups created in the last six months, or among the roughly ten people who have tried and realistically failed for two years, they are selling bullshit. It isn’t cracked, but the puzzle is being solved daily.

The target is an almost-lights-out factory. Best practice now is to build the needed abstractions and pieces by solving non-agent topics: sandboxes, monorepos, reproducible builds, CI/CD, identity and secret management, and corporate friction in developer experience for agents.

In your free time, crack on this problem in your homelab for a fast promotion and red-carpet treatment at your next interview. The highest ROI now is learning the entire damn stack, automating it, and showing the work at an interview or in a recorded meetup talk.

## Systems and culture, not tokens

I must stress: factories aren’t a token or LLM problem. Tokens and their application won’t solve them, though tokens are one piece of the puzzle.

## Keep the service bus deterministic

Second hot take. n8n was a silly idea. I suspect it was built by young Silicon Valley developers swept up in the LLM craze, without corporate experience or knowledge that service buses are a solved problem with deep prior art in the spooky land of enterprise.

Look in [`.NET`](https://x.com/dotnet), including MassTransit, NServiceBus, and WCF, for prompting ideas. WCF gives me bad memories. The implementation isn’t great, but the theory and education are generally on point.

For a modern plug-and-play option, use [Temporal](https://x.com/temporalio) and have a job invoke an agent as a process.
