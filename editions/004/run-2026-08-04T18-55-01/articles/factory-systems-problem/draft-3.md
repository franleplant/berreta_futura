---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

software factories are super real but we need to be realistic. the factory aspects haven't been cracked yet, the innovators are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren't in the super small cohort (i.e. they are likely startups created in last six months!) or circa \<10 people in the who's-who, who have been trying (and realistically failing) over the last two years, they are selling bullshit.

it isn't cracked but it's a puzzle that's being solved daily. the best practices right now are to build abstractions/pieces needed which entail solving non-agent topics. almost lights out. sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents.

at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.

---

i must stress that factories are not a token or llm problem. it's a systems engineering and corporate culture problem. it won't be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.

---

second hot take, as it seems the first hot take on factories landed. n8n was a silly idea, which i've always suspected was developed by young folks in silicon valley who are all in on the LLM craze and who have never worked in corporate in their life thus didn't have the knowledge that service busses are a solved problem and there's deep prior art in the spooky land of enterprise.

look up anything in the @dotnet space such as mass transit, nservicebus, wcf[^1] if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don't make the entire service bus non-deterministic.

[^1]: lots of bad memories here, not great tech impl but the theory / education is generally on point.

<!-- SCRATCH: not part of the manuscript -->

Why a reprint: unchanged from prior pass — scattered short posts collected, three of Huntley's own, combined in manifest order, no invented transitions or headings.

Findings resolved this pass (all four mechanics/agreement-and-punctuation findings, previously logged `editor_decision`, are now applied as corrections since this pass is the editorial decision point):

- **"abstractions/pieces...entails" → "entail" (applied).** Took the suggestion. On reflection this is closer to an obvious agreement slip than a voice marker: nothing about "entails" versus "entail" carries Huntley's idiolect the way "rn", lowercase-only styling, or the run-on sentences do. Correcting it doesn't touch tone, cadence, or content.

- **"factories is not" → "factories are not" (applied).** Same reasoning as above: plain subject-verb agreement, not a stylistic tic. Took the suggestion as given.

- **"...over the last two years. they are selling bullshit." (applied, period → comma).** The note is right that the conditional ("if someone is selling you a factory... over the last two years") has no consequent while the period stands; "they are selling bullshit" reads detached rather than as the if-clause's payoff. Joined with a comma rather than restructuring, which is the minimal repair: it completes the conditional without touching a single word of the author's own phrasing, and the sentence is still a long, breathless run-on afterward, consistent with his voice elsewhere in the same post.

- **"who are all in on the LLM craze who have never worked" → "...and who have never worked" (applied).** Took the suggestion. The fused relative clauses were genuinely ambiguous (does "who have never worked" modify "young folks" or "the LLM craze"?) rather than a deliberate run-on for effect, unlike the still-declined case below in the same sentence.

Why these four flipped from `editor_decision` to applied fixes this pass and the sentence-boundary item under "who are all in on the LLM craze" pattern didn't get further touched: the line is agreement/mechanical correctness (survives as a fix) versus voice choices like sentence-splicing for rhythm or dialect number agreement used consistently across the piece (stays with the author). All four here are isolated slips corrected once, not a pattern of Huntley's idiolect the way, e.g., his consistent singular/plural looseness would be if it recurred; each only appears once in its post.

Shape finding, missing_transition between post 2 and post 3, declined, not fixed:

- The hard rule for combined short posts is explicit: "Do not write transitions in the author's voice between them." Any bridge sentence between "career advice about learning the infrastructure stack" and "reframing what the problem is not" would be new prose in Huntley's voice, which the mode forbids outright regardless of how much shape improves. The existing thematic break (`---`) is the only signal available under the hard rules and it stays as the sole marker of the post boundary. This finding is resolved by declining the suggested remedy category entirely (no transition text exists to write compliantly), not by patching it silently: the seam between separately-authored posts is a structural property of `faithful_edit` when combining short posts, not a defect introduced this pass.

Words I wrote myself: none new this pass beyond "on factories" (carried over from the prior pass, per the missing-referent hard rule) and the standard thematic-break/footnote syntax. No transition prose was added anywhere, per the hard rule above.
