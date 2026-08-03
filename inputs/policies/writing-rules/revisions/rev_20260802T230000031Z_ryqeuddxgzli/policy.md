# Writing rules

The magazine's house method. It applies to everything we publish: source
articles in every content mode, in-a-nutshell explainers, opening editorials,
captions, and social posts. A writer prompt may add rules for its mode; none may
suspend these.

Read `docs/WRITING_EXEMPLARS.md` once at the start of a writing session. This
file cites its eight moves by number and assumes you have seen them. Rules do
not produce prose. Moves do, and the moves are in that file.

The failure this method exists to prevent has a name in the owner's words:
robotic, badly written, and offering no added value on top of the raw sources.
Every section below is aimed at one of those three.

Every quoted failure below is real and shipped. Paths are shortened:
`articles/<id>.md` and `rerun-004/` mean
`editions/rerun-004-the-systems-around-the-model/`, and `004/` means
`editions/004-the-systems-around-the-model/`.

## Audience

Developers and engineering managers inside one company's engineering
organization. Assume professional competence and no familiarity with the
specific topic. A manager must be able to follow the argument without the
implementation detail. A developer must not feel the detail was removed. Keep a
technical term when it carries meaning the plain word cannot.

They have seven minutes and they could have opened the source instead.

## What we are for

Reading our version must beat reading the original. Not be shorter than it:
beat it. A retelling that only removes words has produced a summary, and a
summary is worth less than the source it came from.

Five things a retelling may add. All five are legal in the author-voiced modes,
because none of them invents a claim.

**1. Choose the one example that carries the idea, and cut the second and
third.** A source can afford three illustrations of a point. We can afford one,
so ours has to be the best one, chosen and then returned to. Working:
`eval-engineering.md` picks the invented travel itinerary in its first sentence
and comes back to it four pages later ("Faithfulness is the one the travel agent
failed while every other number looked fine"). Failing:
`004/articles/mcp-in-a-nutshell.md` introduces the VS Code, filesystem and
Sentry example at line 19 and introduces it again at line 61, which is what
happens when nothing was chosen and both survived.

**2. Order for the reader, not for the author.** The source's order serves the
source's argument, the spec's release notes, or the order the author learned
things in. Ours serves a reader deciding what to do. `mcp-protocol-update.md`
takes the release notes' eight sections in the release notes' order. A reader's
order would have been: what breaks, what I change this week, what I can ignore
for a year. Reordering is not a review-required edit; the cut order and the
argument order are the writer's job under `docs/EDITORIAL_POLICY.md`.

**3. Replace the abstraction with the concrete thing it stands for.** Move 1.
The source says "observability layer"; you know from three paragraphs later that
it means a log line nobody reads. Say the log line.

**4. Deploy each fact where it decides something.** Move 7. A number survives
only if the argument changes when the number changes, and a surviving number
gets the sentence that says what it cost or what it bought.

**5. Say the consequence the source leaves implicit.** This is the highest-value
move available and the one closest to the fidelity line, so hold the line
exactly: joining two facts the source states, and drawing the conclusion its own
material forces, is yours to do. Adding a fact, a number, or a consequence the
source does not support is not. `mcp-protocol-update.md` opens on this move done
correctly, and it is the best sentence in the edition: "A remote MCP server that
needed sticky sessions, a shared session store, and deep packet inspection at
the gateway can now run behind a plain round-robin load balancer." No new fact.
The source said sessions are gone; the writer said what that does to your
deployment. The article then abandons the move for six sections.

**The test.** Before delivery, write one sentence naming what a reader can now
do, decide, or picture that the source alone would not have given them. If the
sentence is "read it faster", the piece has not earned publication.

## Right-sizing

Length is earned, never budgeted. A 350-word source does not become a 500-word
article. The page cap is a ceiling and never a target, and so is every word
count in a production prompt: "roughly a third of its length" and "around a
thousand body words" are the most a piece may be, derived from pagination, not
the size it should aim for. Move 6.

Two of edition 004's best pieces run 431 and 516 words against a budget that
allowed 1,100. Nothing was wrong with them. If the finished piece is 300 words
and complete, ship 300 words.

**The paragraph deletion pass.** Run it before you check pagination, never
after. Take each paragraph in turn and delete it. If the piece still makes its
case, that paragraph was length rather than content, and it goes. The paragraphs
that most often fail: the second example, the one restating the section above,
and the closing recap.

**The padding tells.** A piece that was stretched to fit shows it in four
places. A second example doing the first one's job. A sentence that summarizes
the paragraph it sits in. A definition of a term the audience already has. A
closing paragraph that recaps.

Over-length is a different failure and has its own remedy: the cut order in
`prompts/faithful-synthesis.md`. Under-length is not a failure at all.

## Orwell, operationally

The six rules are useless recited. Orwell's own instruction is that a scrupulous
writer asks four questions of every sentence before reaching for any rule:

> What am I trying to say? What words will express it? What image or idiom will
> make it clearer? Is this image fresh enough to have an effect?

and then two more: could I put it more shortly, and have I said anything that is
avoidably ugly. He also gives the method behind all six: "Probably it is better
to put off using words as long as possible and get one's meanings as clear as
one can through pictures and sensations." Get the picture first. The rules are
what you apply when you failed to.

Each rule below is given as Orwell wrote it, then what it forbids here, then a
real failure from edition 004 and its repair.

### i. "Never use a metaphor, simile or other figure of speech which you are used to seeing in print."

*Forbids:* any figure you did not have to invent. The test is Orwell's: can you
see it? A live figure resists being mixed; a dead one will sit happily beside a
figure it contradicts.

*Failure:* the section heading "Extensions become first-class"
(`mcp-protocol-update.md`). Nothing is seen. First-class is a phrase from
someone else's language design essay, arriving pre-worn, and it is the heading a
reader uses to decide whether to read the section.

*Repair:* say what changed. *An extension now has a reverse-DNS name, its own
repository, its own maintainers, and its own version number.*

*Counter-case, keep it:* "Eval engineering is the wiring that runs from the
reading to the furnace" (`eval-engineering.md`) is a figure the writer had to
build, extending the thermometer and thermostat two sentences earlier. It is
seen. Keep it.

### ii. "Never use a long word where a short one will do."

*Forbids:* the Latinate word chosen for weight. Not the technical term chosen
for precision, which is rule v's territory and usually survives.

*Failure:* "It is simply no longer an adequate unit of analysis."
(`004/manuscript/editorial.md`)

*Repair:* the repo's own pass produced "it no longer explains enough on its
own". Take it.

### iii. "If it is possible to cut a word out, always cut it out."

*Forbids:* the clause that announces the sentence, the hedge you added, the
adverb propping up a weak verb.

*Failure:* "That is the immediate effect of the `2026-07-28` Model Context
Protocol release candidate on a production deployment, and it is the largest
revision of the protocol since launch." Eleven words of frame around one claim.

*Repair:* "The `2026-07-28` release candidate is the largest revision of the
protocol since launch." Note what survives: "on a production deployment" was
doing work and stays in the sentence before it.

*The exception that is not optional:* never cut a hedge that belongs to the
source author. "We believe", "roughly", "in one sample", "we do not know why"
are claims about claim strength and are load-bearing evidence. Rule iii cuts
hedges you added. It never touches theirs.

### iv. "Never use the passive where you can use the active."

*Forbids:* the passive that hides who decided. It permits the passive when the
actor is unknown, irrelevant, or genuinely not the subject.

*Test:* add "by whom?" If the answer is in the piece and matters, the passive is
concealing it.

*Failure:* "Roots, Sampling, and Logging are deprecated under a new feature
lifecycle policy." The same article writes "We don't intend for that to be the
norm" six paragraphs later, so the first person exists and disappears exactly
where responsibility sits.

*Repair:* *The maintainers deprecated Roots, Sampling, and Logging.*

### v. "Never use a foreign phrase, a scientific word or a jargon word if you can think of an everyday English equivalent."

*Forbids:* the term used instead of thinking, not the term the reader needs to
recognize in the wild.

*The house resolution:* concept first, term second, in the same sentence.
Working: "The specification names these three: tools, resources and prompts."
(`mcp-in-a-nutshell.md`) The reader met all three as things a database server can
hand over before meeting the word for them.

*Failure:* "Authorization hardening" as a section heading. Hardening is a word
that arrives instead of a description of what got harder.

*Repair:* name the attack it stops. Feynman's order, Move 3.

### vi. "Break any of these rules sooner than say anything outright barbarous."

*Not an amnesty.* Two legitimate uses in this magazine, and they are the only
two.

1. A technical term whose plain paraphrase would be longer and vaguer. "KV
   cache" beats "the stored key and value vectors from earlier tokens" on the
   fifth mention.
2. An author's own sentence in an author-voiced mode. `faithful_edit` and
   `faithful_synthesis` keep the author's clichés, profanity, and broken rules.
   The ban is on writing them yourself.

Rule vi does not license an em dash, a banned tic, or a figure you are fond of.

## The register that produces robot prose

Nine failures below the level the six rules reach. Each is a shape that sounds
like good writing and carries nothing, which is why line editing misses them and
why they survived edition 004 in quantity. Orwell will not catch any of them:
every specimen quoted here is made of short common words in the active voice.

### The abstraction stack

Three or more abstract nouns doing the work one concrete thing would do.

> A model never arrives alone. It arrives inside a protocol, a runtime, a set of
> tools, a review policy, an evaluation loop, and a network full of assumptions.

*Mechanism:* a list of six abstractions is not more specific than one. It is a
refusal to choose, wearing the costume of thoroughness.

*Repair:* pick one, make it an object, and let it stand for the rest. Move 1.

### The portentous short sentence

A short sentence placed for weight, delivering a verdict rather than a fact.

> The model was never the interesting part.
>
> The constraint is the product.

*Test:* a short sentence earns its place by delivering a fact or turning the
argument, never by rating something. "Day two was quiet."
(`frontier-lab-agent-intrusion.md`) is a fact and it accelerates a chronology.
"All of it invented." (`eval-engineering.md`) reverses the sentence before it.
Those work.

*Repair:* replace the verdict with the fact that would make a reader reach it
themselves.

### The definite-article equation

Abstract noun, "is", abstract noun, with a definite article for authority.
Edition 004 built it at least four times across three pieces: "It is the
product." "The constraint is the product." "The model was never the interesting
part." "Most actions went nowhere, and that is the defender's new problem." One
cadence, which makes it a house tic rather than four insights.

*Repair:* delete it. The sentence before it has almost always already said this,
and the equation is the piece congratulating itself on having said it.

### The balanced clause that sounds like insight

Two clauses of matched length and opposed sense, no new information in the
second.

> We do not need perfect models. We need each important action to leave a trace.
>
> State must be explicit enough to inspect and revoke. Boundaries must explain
> who could do what. Failures must last long enough to become rules.

Both are from `004/prototypes/editorial-emergent-narrative.md`, which the
editorial prompt holds up as the standard. Its structure is the standard. Those
five sentences are the house's worst habit at its most fluent, and they are why
the tic is hard to see: it is most convincing in our best piece.

*Test:* delete the first clause. If the second still carries everything, the
first was cadence. Delete the triad's second and third members. If nothing is
lost, all three were.

*Repair:* keep the clause with the content, and give the space to an example.

### The ownerless imperative

"Must", "should", or "needs to" with no actor.

> Scaling laws remain relevant, but capacity must be added in the right place
> and in a form the system can use.

(`from-gpt2-to-kimi3.md`.)

*Mechanism:* a sentence that instructs nobody cannot be wrong, which is why it
feels safe and reads as filler.

*Repair:* name who does it and what they do. *Kimi Linear gives each channel its
own decay rate, so a layer can forget one association without flattening the
rest.*

### False profundity

A sentence that claims significance instead of demonstrating it.

> This changes what counts as intelligence.
>
> Autonomy becomes dangerous when it erases its path.

*Mechanism:* announcing that something is important is the cheapest sentence in
English and the only one that cannot be checked.

*Repair:* cut the announcement and keep what follows. If the next paragraph
demonstrates the significance, the announcement was redundant. If it does not,
the announcement was a bluff.

### The throat-clearing opener

A first sentence whose subject is the article rather than the world.

> The headline change is that MCP is now stateless at the protocol layer.

*Mechanism:* the writer orients themselves in public. "The headline change is
that" is four words telling the reader they are reading an article, which they
know.

*Repair:* delete the frame. "MCP is now stateless at the protocol layer. The
`initialize` handshake is gone." Same information, and the second sentence is
now free to carry a consequence.

### The restating summary

A sentence or paragraph whose content is the paragraph above it.

> The policy gives every feature an Active, Deprecated, and Removed lifecycle.

It follows a paragraph that has already listed the deprecations, their
replacements, and the guarantee period. Nothing in it is new.

*Mechanism:* restating feels like closure and reads like doubt that the reader
was paying attention.

*Repair:* cut it. If a section genuinely needs a landing, land it on the
consequence rather than the recap: *A method deprecated today still works in
every version published for the next year, so nothing in this release forces a
migration.*

### The changelog

Not a sentence but a whole piece. Every paragraph is a delta. No reader is in
the room, no fact is deployed, nothing is omitted, and the headings are the
source's headings with the verbs changed. `mcp-protocol-update.md` is the
specimen, and the tragedy is that its own first sentence knew better.

*Diagnosis:* the piece has a subject and no reader.

*Repair:* one pass answering, for each section, "who does something differently
on Monday because of this?" Sections with no answer merge into one paragraph or
go. See Move 5.

## Banned tics

Never construct any of these. When the phrasing is the source author's own
retained sentence in an author-voiced mode, keep it; the ban is on writing it
yourself.

1. **The antithesis close.** "It is not X. It is Y", and its variants "This is
   not X, it is Y", "X is not Y. It is Z", "not merely X but Y". Edition 004
   built it about a dozen times and closed three pieces on it.
2. **A closing paragraph that restates what the reader just read.** See "The
   restating summary" above.
3. **More than one three-item abstract list per piece, and never as the last
   sentence.**
4. **Openers that announce the piece.** "In this article", "This piece
   explores", "At its core", "In an era of", "The headline change is that". See
   "The throat-clearing opener" above.
5. **Assistant idiom.** "crucial", "vital", "delve", "landscape", "tapestry",
   "game-changer", "it is worth noting", "in today's world", "the reality is",
   "simply put". The list is not the point and will never be complete. The
   generative test is Move 8: read the sentence aloud and cut anything you would
   not say to a colleague at their desk.
6. **Narrator scaffolding in an author-voiced piece.** "the author argues",
   "Narayanan explains", "according to the speaker". Naming a document is
   allowed and often necessary: "the specification calls this elicitation".
7. **The em dash character U+2014.** Use a period, comma, colon, semicolon, or
   parentheses.

## Voice

Every piece carries the voice of whoever is credited on it. In the author-voiced
modes that is the source author: their person, idiom, sentence rhythm, humour,
profanity, and sign-off survive the edit. In the magazine's own modes it is the
editors' voice, and it still has to be a voice rather than a register.

Two pieces in the same edition must not sound like the same writer. If you can
swap the closing paragraphs of two articles without a reader noticing, both are
wrong, and the managing editor files it as one issue-level finding.

## Openings and endings

**Open cold, on something concrete, and earn the next paragraph.** The opener is
where Move 4 pays: you have no new facts, so the vantage point is all you have.
"Twenty-two thousand five hundred and eighty. That's how many GPT-2 models from
2019 fit inside KimiK3 from 2026, 124 million parameters against 2.8 trillion."
(`from-gpt2-to-kimi3.md`.) See also the throat-clearing opener above, which is
what this looks like when the writer flinches.

**End on one line that lands rather than summarizes.** Two tests, and it must
pass both. Delete the last line and reread: if the piece lost nothing but a
period, it summarized. Then ask whether you could have written that line before
the argument that precedes it; if you could, it is a thesis restated, not an
ending.

Endings that pass: "Fast verdicts are rented. Slow verdicts are the deed."
(edition 003's editorial.) "The intruder had a policy for its own mistakes.
Almost nothing it walked through did." (`rerun-004/manuscript/editorial.md`.)
"Good luck." (the author's own, kept.)

**Do not model on our published work** unless the passage appears in
`docs/WRITING_EXEMPLARS.md`. Two reasons. A shipped piece may carry a tic that
survived review, and a synthesis may be closing on a near-copy of a line in its
own source, which is the mode working correctly and no lesson in writing an
ending at all. Edition 004's eval piece does exactly that.

## Revising after review

A finding is an obligation; the `suggestion` printed beside it is advice. A
reviser is judged on whether the defect is gone, not on whether the reviewer's
line was taken. Decline a suggestion that would clear the finding by damaging
the piece (one that resolves a contradiction by having the article admit it
changed its mind, say), fix the defect another way, and say in your reply what
you did instead and why.

When a finding carries `repair_from`, repair there. A structural defect patched
where it surfaces reappears in the next draft.

## The final pass

Every question has a determinate answer. If one does not, you have not run it.

1. Write the sentence naming what a reader gains over the source. Not "read it
   faster".
2. Name the two things in the source that do not appear here at all.
3. Delete each paragraph in turn. Put back only the ones the piece needed.
4. Read the whole piece aloud. Cut every sentence you would not say.
5. For each number: does the claim change if the number changes? If not, cut it
   or reduce it to a word.
6. For each abstract noun in a load-bearing sentence: what is the object? Put
   the object in.
7. For each passive: by whom, and does the piece know? If it knows and it
   matters, make it active.
8. Read only the short sentences. Does each deliver a fact or a turn, or is it
   rating something?
9. Read only the first and last sentence of each paragraph. Do any two say the
   same thing?
10. Delete the last line. Did the piece lose more than a period?
11. Swap test: could this piece's closing paragraph sit at the end of another
    piece in this edition?
12. Would breaking one of these rules make the result clearer? Rule vi, and only
    its two legitimate uses.
