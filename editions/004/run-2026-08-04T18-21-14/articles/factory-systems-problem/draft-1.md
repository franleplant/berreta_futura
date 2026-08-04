---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---
Software factories are super real, but we need to be realistic. The factory aspects haven’t been cracked yet; the innovators are still toying around with discovering practices and pieces. If someone is selling you a factory right now, and they aren’t in the super small cohort (i.e., they are likely startups created in the last six months, or the circa <10 people in the who’s-who who have been trying—and realistically failing—over the last two years), they are selling bullshit. It isn’t cracked, but it’s a puzzle that’s being solved daily. The best practices right now are to build abstractions or pieces, which entails solving non-agent topics like sandboxing, monorepo, reproducible builds, CI/CD, identity/secret management, or smashing corporate friction in the realm of devex for agents. At home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. The highest ROI you can have right now is learning the entire damn stack, automating it, and showing it at your next interview or doing a recorded talk at a meetup.

I must stress that factories is not a token or LLM problem. It’s a systems engineering and corporate culture problem. It won’t be solved through tokens or how you apply the tokens (but it is a piece of the puzzle), ugh.

Second hot take, as it seems the first hot take landed. N8n was a silly idea, which I’ve always suspected was developed by young folks in Silicon Valley who are all in on the LLM craze and who have never worked in a corporate environment in their life, thus not having the knowledge that service buses are a solved problem and there’s deep prior art in the spooky land of enterprise. Look up anything in the .NET space, such as Mass Transit or NServiceBus, or WCF, if you want to steal ideas for prompting. If you want a modern plug-and-play choice, Temporalio exists. Use it and have a job invoke an agent as a process. Don’t make the entire service bus non-deterministic.
