---
source_ids:
- design-patterns-for-securing-llm-agents-against-d40186ec
content_mode: article
label: ARTICLE
---

A new paper by 11 authors from IBM, Invariant Labs, ETH Zurich, Google, Microsoft and others is an *excellent* addition to the literature on prompt injection. Its premise: agents built on current models are unlikely to offer reliable safety guarantees, so it proposes six design patterns that deliberately limit what agents can do. One principle runs under all of them. Once an agent has ingested untrusted input, it must be impossible for that input to trigger consequential actions. Ten case studies show the patterns applied.

#### The scope of the problem

The authors write that "as long as both agents and their defenses rely on the current class of language models, we believe it is unlikely that general-purpose agents can provide meaningful and reliable safety guarantees." Their trade-off, limiting an agent's ability to perform arbitrary tasks, isn't popular, but it gives the paper a lot of credibility in my eye.

Their guiding principle is that a restricted agent must not be able to invoke tools that break the integrity or confidentiality of the system, and its outputs must not pose downstream risks, such as exfiltrating data through embedded links.

The way I think about it: any exposure to potentially malicious tokens entirely taints the output for that prompt. An attacker who sneaks in their tokens should be considered to control what happens next, both the text and any tool calls.

#### The patterns

**Action-Selector.** The agent can trigger tools but never sees their responses. It can send the user to a web page; it can't read one. They call it an "LLM-modulated switch statement", which feels accurate to me.

**Plan-Then-Execute.** Tool calls are planned before any exposure to untrusted content. "Send today's schedule to my boss John Doe" becomes `calendar.read()` followed by `email.write(..., 'john.doe@company.com')`. The calendar output might corrupt the email's body, but it won't be able to change the recipient.

**LLM Map-Reduce.** Sub-agents face the untrusted content and their results are aggregated safely. To send this month's invoices to accounting, each file goes to a sub-agent that answers with a boolean: relevant or not.

**Dual LLM.** This is the pattern I described in April 2023, cited and diagrammed in the paper. A privileged LLM coordinates a quarantined LLM and never touches untrusted content. The quarantined LLM returns symbolic variables, such as `$VAR1` for a summarized web page, which the privileged LLM can ask to show the user without seeing them.

**Code-Then-Execute.** This is the pattern from DeepMind's CaMeL paper, an improved version of my dual LLM pattern. The privileged LLM writes code in a sandboxed DSL that specifies which tools to call and how their outputs pass between them. The DSL allows full data flow analysis, so tainted data can be tracked through the entire process.

**Context-Minimization.** I'm slightly confused by this one, but I think I understand it. A user's prompt is turned into something like a database query, and the prompt is removed from the context before the results come back. If the returned data cannot include any text from the original prompt, any chance of an injection sneaking through should be eliminated.

#### The case studies

There are ten, and most are extremely practical and detailed. The SQL Agent study, an LLM that queries databases and runs Python, spends three pages on building that highly challenging case responsibly.

The Software Engineering Agent study suggests letting a quarantined LLM convert untrusted documentation into a strictly formatted API description, with method names limited to 30 characters, for example. Utility drops, since the agent sees no prose or code examples. An injection would have to survive the formatting, which the authors consider unlikely if the requirements are strict enough. I wonder if 30 characters is indeed safe: a creative attacker might come up with `run_rm_dash_rf_for_compliance()`.

#### Closing thoughts

I've written about prompt injection for nearly three years without the patience to produce a formal paper, so it's a huge relief to see papers of this quality emerge. Prompt injection remains the biggest challenge to responsibly deploying agentic systems, and the more attention it gets from researchers the better.
