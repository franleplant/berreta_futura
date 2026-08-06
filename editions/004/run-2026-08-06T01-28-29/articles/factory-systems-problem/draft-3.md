---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

Software factories are super real, but we need to be realistic. The factory aspects haven’t been cracked yet. The innovators are toying around with discovering practices and pieces.

If someone is selling you a factory right now and they aren’t in the super small cohort (i.e., they are likely startups created in the last six months!) or circa <10 people in the who’s-who who have been trying (and realistically failing) over the last two years, they are selling bullshit. It isn’t cracked, but it is a puzzle that’s being solved daily. The best practices right now are to build the abstractions and pieces needed for sandboxing, monorepos, reproducible builds, CI/CD, identity and secret management, and to smash corporate friction in the realm of DevEx for agents. We are almost at lights-out. At home, in your homelab, you should be cracking on this problem space in your free time if you want a super-fast promotion and red-carpet service at your next interview. The highest ROI you can have right now is learning the entire damn stack, automating it, and showing it at your next interview or doing a recorded talk at a meetup.

I must stress that factories are not a token or LLM problem. It’s a systems engineering and corporate culture problem. It won’t be solved through tokens or how you apply the tokens (but it is a piece of the puzzle). It is time for a blog post.

n8n was a silly idea, which I’ve always suspected was developed by young folks in Silicon Valley who are all in on the LLM craze who have never worked in corporate in their lives, thus didn’t have the knowledge that service buses are a solved problem and there’s deep prior art in the spooky land of enterprise. Look up anything in the @dotnet space, such as MassTransit, NServiceBus, WCF, if you wanna steal ideas for prompting. If you want a modern plug-and-play choice, @temporalio exists. Use it and have a job invoke an agent as a process. Don’t make the entire service bus non-deterministic. I have lots of bad memories here; the tech implementation was not great, but the theory/education is generally on point.
