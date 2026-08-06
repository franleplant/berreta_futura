# Writing rules

The magazine's house method. It applies to everything we publish: source
articles in every content mode, in-a-nutshell explainers, opening editorials,
captions, and social posts. A writer prompt may add rules for its mode; none may
suspend these.

Voice, taste, method, and sentence craft now live in `docs/WRITING_STYLE.md`;
read it first, and read it before this file, since it is the authority on how a
sentence should sound. What remains here is operational: who we write for, what
a retelling must add over its source, how long a piece may run, and the two
failure catalogs, the robot-prose register and the banned tics, that catch what
taste alone misses.

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

**3. Replace the abstraction with the concrete thing it stands for.** This is
Orwell's move in `docs/WRITING_STYLE.md`: replace vague abstractions with
concrete meaning, and use concrete nouns and active verbs. The source says
"observability layer"; you know from three paragraphs later that it means a log
line nobody reads. Say the log line.

**4. Deploy each fact where it decides something.** A number
survives only if the argument changes when the number changes, and a surviving
number gets the sentence that says what it cost or what it bought.

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
the size it should aim for. This is Hemingway's constraint in
`docs/WRITING_STYLE.md`: restraint is not mere brevity, and length is an output
of selection, never a budget.

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
`docs/EDITORIAL_POLICY.md`. Under-length is not a failure at all.

## The register that produces robot prose

Nine failures below the level `docs/WRITING_STYLE.md` reaches. Each is a shape
that sounds like good writing and carries nothing, which is why line editing
misses them and why they survived edition 004 in quantity. Style and taste will
not catch any of them: every specimen quoted here is made of short common words
in the active voice.

### The abstraction stack

Three or more abstract nouns doing the work one concrete thing would do.

> A model never arrives alone. It arrives inside a protocol, a runtime, a set of
> tools, a review policy, an evaluation loop, and a network full of assumptions.

*Mechanism:* a list of six abstractions is not more specific than one. It is a
refusal to choose, wearing the costume of thoroughness.

*Repair:* pick one, make it an object, and let it stand for the rest. This is
Orwell's concrete-noun move in `docs/WRITING_STYLE.md`.

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
go. See Hemingway's restraint and omission in `docs/WRITING_STYLE.md`.

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
   "simply put". The list is not the point and will never be complete. Read the
   sentence aloud and cut anything you would not say to a colleague at their
   desk.
6. **Narrator scaffolding in an author-voiced piece.** "the author argues",
   "Narayanan explains", "according to the speaker". Naming a document is
   allowed and often necessary: "the specification calls this elicitation".
7. **The em dash character U+2014.** Use a period, comma, colon, semicolon, or
   parentheses.

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
Run two checks, in order.

1. **Run `docs/WRITING_STYLE.md`'s Final Editing Test, all ten questions,
   verbatim.** That test covers voice, mechanism, concreteness, significance,
   humor, and the clean landing. Do not paraphrase it; run it.
2. **Scan this file.** Check the piece against every item in "Banned tics"
   above, one at a time. Then check it against every register in "The register
   that produces robot prose" above: read only the short sentences and ask
   whether each delivers a fact or a turn rather than rating something; read
   only the first and last sentence of each paragraph and ask whether any two
   say the same thing; look for the abstraction stack, the definite-article
   equation, the balanced clause, the ownerless imperative, false profundity,
   the throat-clearing opener, the restating summary, and the changelog shape,
   in turn.

Both checks must find nothing before the piece ships.
