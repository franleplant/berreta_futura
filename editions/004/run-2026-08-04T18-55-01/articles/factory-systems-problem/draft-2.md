---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

software factories are super real but we need to be realistic. the factory aspects haven't been cracked yet, the innovators are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren't in the super small cohort (i.e. they are likely startups created in last six months!) or circa \<10 people in the who's-who, who have been trying (and realistically failing) over the last two years. they are selling bullshit.

it isn't cracked but it's a puzzle that's being solved daily. the best practices right now are to build abstractions/pieces needed which entails solving non-agent topics. almost lights out. sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents.

at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.

---

i must stress that factories is not a token or llm problem. it's a systems engineering and corporate culture problem. it won't be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.

---

second hot take, as it seems the first hot take on factories landed. n8n was a silly idea, which i've always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn't have the knowledge that service busses are a solved problem and there's deep prior art in the spooky land of enterprise.

look up anything in the @dotnet space such as mass transit, nservicebus, wcf[^1] if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don't make the entire service bus non-deterministic.

[^1]: lots of bad memories here, not great tech impl but the theory / education is generally on point.

<!-- SCRATCH: not part of the manuscript -->

Why a reprint: unchanged from prior pass — scattered short posts collected, three of Huntley's own, combined in manifest order, no invented transitions or headings.

Findings addressed this pass:

- **"ie." → "i.e." (fix).** Applied as given. This is a punctuation-of-abbreviation fix, not a voice choice like "rn" or lowercase-only styling, so it falls under typography normalization in step 3 of the procedure rather than under the voice-preservation rule.

- **Orphan referent, "first hot take" (fix, shape lens).** Resolved by restoring the referent inside the author's own sentence, per the hard rule on missing referents: "second hot take, as it seems the first hot take landed" → "...the first hot take **on factories** landed." The insertion is drawn straight from the extraction — post one is about software factories, and post two independently anchors the same topic ("factories is not a token or llm problem") — so the referent is source-supported, not invented. I declined the heading option: a heading between the three posts is apparatus, and the hard rule bars "no apparatus of any kind inside the article." A two-word insertion into the author's own sentence is the smaller, rule-compliant repair.

Findings declined (left as editor_decision, not silently corrected):

- "abstractions/pieces...entails" (agreement) — left singular. Correcting the author's number agreement mid-sentence is a grammar smoothing of his own retained wording, which the mode reserves for a human call, not a reviser default.
- "...over the last two years. they are selling bullshit." (period vs. comma) — left as two sentences. Splicing his sentence boundary back into one conditional changes his own punctuation choice, not a typo; same reasoning.
- "who are all in on the LLM craze who have never worked..." (unjoined relative clauses) — left as the run-on. This is exactly the "broken rules survive intact" case the mode exists for; restructuring it would be paraphrasing for smoothness, which the hard rules forbid outright.
- "factories is not a token or llm problem" (agreement) — left singular, same reasoning as the first item, and consistent with leaving its sibling "abstractions/pieces...entails" alone: both are the same idiolect, not isolated slips.

All four are marked `editor_decision` in the review and sit in the author's own sentences; per the mode's judging rules that disposition is a human's call, and applying the suggested rewrites here would be me making that call instead. They remain blocking findings for the owner to resolve, not silently cleared.

Everything else — chrome removal, footnote handling, `@dotnet`/`@temporalio` styling, paragraph breaks, the `\<10` escape — is unchanged from the prior working notes.

Words I wrote myself: "on factories" (two words, inserted per the missing-referent hard rule) and the thematic-break dividers/footnote syntax, as before. No other prose added.
