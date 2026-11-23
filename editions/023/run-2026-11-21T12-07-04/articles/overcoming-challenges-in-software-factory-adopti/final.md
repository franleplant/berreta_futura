---
source_ids:
- overcoming-challenges-in-software-factory-adopti-0c459f66
content_mode: article
label: ARTICLE
---

Setting up a software factory is technically hard; anyone who claims otherwise isn't doing it for real. But the bigger challenge might be getting developers excited to use one. Two things stand in the way. The name suggests an assembly line, when the engineer's real job is designing the factory. And a factory moves agents off each developer's laptop into shared infrastructure owned by the team, which removes some autonomy and forces people to work in public. I believe that change is necessary and ultimately positive, and the most successful companies are going to embrace it now.

## Designing the factory, not working the line

"Software factory" conjures a mechanized, non-creative process: an assembly line turning out identical commodities, like cars. Working on an assembly line isn't what I signed up for as a developer, and teams offered that vision won't get excited.

So the engineer's job is not working on the line; it's designing the factory. You aren't suiting up in a blue jumpsuit to push slop out the door. You're engineering a state of the art Tesla factory, but for useful software, and it produces bespoke software for your customers, not one kind of thing. The term fits only because if you build a Tesla factory, you'd better care about optimizing throughput while minimizing cost and maintaining quality. That is the factory mindset.

## From a private cockpit to working in public

Developers have always built their own cockpit: terminal, IDE or emacs/vim, keybinds, theme. With agents, it's each developer's harness, model, skills, and MCPs. Engineering your own productivity is part of the fun. Until now, work became public only when you opened a PR.

In a software factory you work in public by default, and this is good. Every developer managing agents their own way does not scale. Your VP Eng, CFO or CISO might not have cared whether you used emacs or vim, but they care if you're using Fable or GLM to spend millions of dollars in tokens. They care if insecure skills could let a prompt-injected agent act as you and reach sensitive systems. They care if some engineers are 100x more productive than others.

Software factories remove some developer choice and variance. They move the agent system into cloud infrastructure, where its behaviors are owned by the team, defined in code, and engineered over time for collective improvement.

## The cost, and how to lead through it

The flip side is lost autonomy, and working in public in a way that may be uncomfortable. This is where leaders may face the biggest hurdles. Senior engineers especially may rightfully say their productivity depends on their local setup.

For some this may be true for now, but bespoke setups are not the long-term answer. Acknowledge the friction; for engineers who optimized their setups, it might feel like a temporary step backwards. Then paint the end state, where agentic coding systems belong to the team and organization. Cast it as a problem to solve together: how to build the best shared infrastructure that everyone benefits from and improves. Factory engineering is a team endeavor, not a solo one.

You might need to take a firm stand. The future of coding agents is not a million bespoke ways of pushing PRs into CI. It's a fully encoded system for building software together, in the cloud, with well defined guardrails and collective measurement and improvement over time. A year ago some developers still claimed they were more productive writing code by hand. The same shift is going to happen here, and the most successful companies are going to get their factory infra humming today.
