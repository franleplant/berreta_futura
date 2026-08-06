---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

First hot take: software factories are super real but we need to be realistic. The factory aspects haven’t been cracked yet, the innovators are toying around with discovering practices and pieces. If someone is selling you a factory rn and they aren’t in the super small cohort (i.e. they are likely startups created in the last six months!) or circa <10 people in the who’s-who, who have been trying (and realistically failing) over the last two years. They are selling bullshit.

It isn’t cracked but it’s a puzzle that’s being solved daily. The work now is to build the pieces needed by solving non-agent topics: sandboxing, a monorepo, reproducible builds, CI/CD, identity and secret management, and smashing corporate friction in the realm of DevEx for agents. We are almost at lights-out. At home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. Highest ROI you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.

I must stress that factories are not a token or LLM problem. It’s a systems engineering and corporate culture problem. It won’t be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. Blog post time.

Here is the second hot take, since the first hot take seems to have landed. n8n was a silly idea, which I’ve always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn’t have the knowledge that service buses are a solved problem and there’s deep prior art in the spooky land of enterprise. The @dotnet space offers mass transit, nservicebus, and wcf if you wanna steal ideas for prompting. A modern plug and play choice is @temporalio. Use it and have a job invoke an agent as a process. Don’t make the entire service bus non-deterministic. Lots of bad memories here, not great tech impl but the theory / education is generally on point. Keeping the service bus deterministic and invoking the agent as a process is the systems-engineering work factories still have to solve.
