---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

software factories are super real but we need to be realistic. the factory aspects haven't been cracked yet, the innovators are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren't in the super small cohort (ie. they are likely startups created in last six months!) or circa \<10 people in the who's-who, who have been trying (and realistically failing) over the last two years. they are selling bullshit.

it isn't cracked but it's a puzzle that's being solved daily. the best practices right now are to build abstractions/pieces needed which entails solving non-agent topics. almost lights out. sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents.

at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.

---

i must stress that factories is not a token or llm problem. it's a systems engineering and corporate culture problem. it won't be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.

---

second hot take, as it seems the first hot take landed. n8n was a silly idea, which i've always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn't have the knowledge that service busses are a solved problem and there's deep prior art in the spooky land of enterprise.

look up anything in the @dotnet space such as mass transit, nservicebus, wcf[^1] if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don't make the entire service bus non-deterministic.

[^1]: lots of bad memories here, not great tech impl but the theory / education is generally on point.

<!-- SCRATCH: not part of the manuscript -->

Why a reprint: scattered short posts collected. Three of Huntley's own posts, none individually a page, combined in the order they appear in the edition manifest (factories-are-real → not-a-token-problem → service-bus). No transitions written between them; each is separated by a plain thematic break (`---`) with no invented heading or label, since a heading would have been prose I wrote.

Chrome removed: none of the usual nav/ad/social furniture was present in the extraction — these are raw post bodies already. What I did strip: the bracketed reference markers `[1] [2] [3]` scattered through the first post (e.g. "the [3] innovators", "solving [2] non-agent topics", "[1] almost lights out"). Unlike the third post, these have no matching footnote definitions anywhere in the extraction, and reassembling them by number doesn't produce grammatical sentences ("the" + "almost lights out" is broken), so they aren't a scrambled-but-recoverable footnote structure. My read is that they're references to attached images (screenshots) that this text-only DOM extraction didn't capture, and printing a bare, undefined citation number would read as broken typesetting rather than content. I removed the markers and left the running prose exactly as written otherwise. Flagging this for a human: if the original images are recoverable from the source bundle, they may be worth adding as figures in a future pass — I did not invent replacement content per the hard rule against manufacturing claims.

Footnote handled, not removed: the third post's `[1]` on "wcf" does pair with a definition given at the end of that extraction ("lots of bad memories here, not great tech impl but the theory / education is generally on point."), so I normalized that one into a standard markdown footnote (`wcf[^1]` / `[^1]: ...`) rather than dropping it — the difference from post one is that this one is actually resolvable from the text we have.

Left alone: `@dotnet` and `@temporalio` are the author's own wording (his sentence, not platform chrome), so I kept them as typed rather than expanding to ".NET" or "Temporal.io." Same for the pervasive lowercase-only style, "rn," "ie.," and "who's-who" — that's voice, not an error, so none of it was "corrected." No missing referents needed restoring; nothing here has an ambiguous "it"/"the post"/pronoun problem, since each piece is short enough that its antecedents stay in view.

Typography-only changes I made: paragraph breaks inside the first and third posts (each was one run-on paragraph in the extraction) for print legibility, no reordering or added words; and escaping `<10` as `\<10` so it doesn't get read as a stray HTML tag by a markdown renderer — same visible text, no wording change.

Words I wrote myself: none in the manuscript body. Everything is the author's own sentences; my only additions are the three thematic-break dividers and the footnote marker syntax, both pure formatting.
