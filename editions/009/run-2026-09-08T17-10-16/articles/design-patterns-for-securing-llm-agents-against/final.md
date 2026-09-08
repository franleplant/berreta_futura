---
source_ids:
- design-patterns-for-securing-llm-agents-against-d40186ec
content_mode: article
label: ARTICLE
---

Eleven authors from IBM, Invariant Labs, ETH Zurich, Google and Microsoft have produced an excellent addition to the prompt injection literature. Their premise: as long as both agents and their defenses rely on the current class of language models, it's unlikely that general-purpose agents can provide meaningful and reliable safety guarantees. So they ask the more productive question, what can we build today, and answer with six design patterns that constrain agents so untrusted input can't trigger consequential actions, plus ten case studies. The price is that these agents can no longer solve *arbitrary* tasks. That's not a popular trade-off, but it gives the paper a lot of credibility in my eye.

## The scope

The authors very clearly understand the scope of the problem. Their patterns share one guiding principle: once an LLM agent has ingested untrusted input, it must be constrained so that it is impossible for that input to trigger consequential actions, and its outputs must not pose downstream risks either, such as exfiltrating data through embedded links or manipulating future agent behavior. The way I think about this is that any exposure to potentially malicious tokens entirely taints the output for that prompt. An attacker who can sneak in their tokens controls the text and the tool calls alike.

## The six patterns

- **Action-Selector**: the agent triggers tools but gets no feedback from them. An LLM-modulated switch statement.
- **Plan-Then-Execute**: plan the calls before any exposure to untrusted content. "Send today's schedule to my boss John Doe" becomes `calendar.read()` then `email.write(..., 'john.doe@company.com')`. The calendar output might corrupt the body; it can't change the recipient.
- **LLM Map-Reduce**: sub-agents meet the untrusted content on the coordinator's behalf. Asked to find files with this month's invoices, each sub-agent returns a boolean for relevance, and the relevant ones are aggregated and sent.
- **Dual LLM**: my pattern from April 2023, which also influenced the CaMeL paper. A privileged LLM coordinates a quarantined one and handles only symbolic variables, `$VAR1` standing for a summarized web page it is never itself exposed to.
- **Code-Then-Execute**: CaMeL's improvement on that, where the privileged LLM writes code in a custom sandboxed DSL designed for full data flow analysis, so tainted data can be marked and tracked throughout.
- **Context-Minimization**: remove unnecessary content from the context over multiple interactions. A customer service chatbot turns the request into a database query, then the user's prompt is removed before the results go back, taking the injected discount demand with it.

## The case studies

Ten, most of them extremely practical and detailed, each with threat models and mitigations: OS Assistant, SQL Agent, Email & Calendar Assistant, Customer Service Chatbot, Booking Assistant, Product Recommender, Resume Screening Assistant, Medication Leaflet Chatbot, Medical Diagnosis Chatbot, Software Engineering Agent. The SQL Agent gets three pages of a highly challenging environment. The Software Engineering Agent proposes that the safest design is one where the code agent sees untrusted documentation only through a strictly formatted interface: a formal API description produced by a quarantined LLM, with method names limited to 30 characters. Utility drops, since no natural language or examples survive; security holds because an injection would have to survive the formatting. I wonder whether 30 characters is indeed safe. A truly creative attacker might arrive at `run_rm_dash_rf_for_compliance()`.

## Closing

I've been writing about prompt injection for nearly three years and never had the patience to produce a formal paper on it, so it's a huge relief to see papers of this quality start to emerge. Prompt injection remains the biggest challenge to responsibly deploying the agentic systems everyone is so excited to build. The more attention this family of problems gets from the research community the better.
