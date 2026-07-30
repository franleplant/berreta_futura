---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

## Software factories are super real

Software factories are super real, but we need to be realistic. The factory aspects haven’t been cracked yet; the innovators are toying around with discovering practices and pieces.

If someone is selling you a factory right now and they aren’t in the super-small cohort (likely startups created in the last six months), or among the roughly ten people in the who’s-who who have been trying and realistically failing over the last two years, they are selling bullshit. It isn’t cracked, but it’s a puzzle that’s being solved daily.

The target is an almost-lights-out factory. The best practice right now is to build the abstractions and pieces we need. That entails solving non-agent topics: sandboxing, monorepos, reproducible builds, CI/CD, identity and secret management, and smashing corporate friction in the realm of developer experience for agents.

At home, in your homelab, you should be cracking on this problem space in your free time if you want a super-fast promotion and red-carpet service at your next interview. The highest ROI you can have right now is learning the entire stack, automating it, and showing it at your next interview or in a recorded talk at a meetup.

## A systems engineering and corporate culture problem

I must stress that factories are not a token or LLM problem. They won’t be solved through tokens or how you apply them, although that is a piece of the puzzle.

## Keep the service bus deterministic

Second hot take, as it seems the first one landed. n8n was a silly idea, which I’ve always suspected was developed by young folks in Silicon Valley who are all in on the LLM craze, have never worked in corporate in their lives, and thus didn’t know that service buses are a solved problem with deep prior art in the spooky land of enterprise.

Look up anything in the [`.NET`](https://x.com/dotnet) space, such as MassTransit, NServiceBus, or WCF, if you want to steal ideas for prompting. WCF gives me lots of bad memories. The implementation isn’t great, but the theory and education are generally on point.

If you want a modern plug-and-play choice, [Temporal](https://x.com/temporalio) exists. Use it and have a job invoke an agent as a process.
