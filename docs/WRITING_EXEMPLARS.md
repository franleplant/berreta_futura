# Writing exemplars

Eight moves stolen from writers who solved a problem this magazine has. Read
this once at the start of a writing session; `docs/WRITING_RULES.md` cites the
moves by number and is the file you work from.

Each entry gives the borrowed passage, the mechanism in one sentence, the same
move working in our own pages, the same move failing in our own pages, and the
repair. House quotations are exact and cite their file. Where a borrowed passage
is described rather than quoted, it says so.

Nothing here licenses imitation of a writer's subject or persona. You are taking
one structural move, not a voice.

Paths are shortened. `articles/<id>.md` and `rerun-004/` mean
`editions/rerun-004-the-systems-around-the-model/`; `004/` means
`editions/004-the-systems-around-the-model/`, the originally shipped edition.

---

## Move 1. Put the concrete word where the abstract one wants to go

**Orwell**, *Politics and the English Language*, translating Ecclesiastes into
"modern English of the worst sort".

> I returned and saw under the sun, that the race is not to the swift, nor the
> battle to the strong, neither yet bread to the wise, nor yet riches to men of
> understanding, nor yet favour to men of skill; but time and chance happeneth
> to them all.

> Objective consideration of contemporary phenomena compels the conclusion that
> success or failure in competitive activities exhibits no tendency to be
> commensurate with innate capacity, but that a considerable element of the
> unpredictable must invariably be taken into account.

**Mechanism.** Orwell's own diagnosis: race, battle and bread are concrete
illustrations, and they dissolve into "success or failure in competitive
activities" because a writer reaching for that register would never have
tabulated his thoughts in the precise and detailed way that required naming a
race, a battle and a loaf.

**Working, ours.** `articles/eval-engineering.md`:

> A thermometer tells you the room is cold. A thermostat turns the heat on.

Two objects, no abstract nouns, and the distinction between measurement and
control is settled in fourteen words.

**Failing, ours.** `004/manuscript/editorial.md`:

> Capability becomes useful only when the system around it can expose state,
> preserve evidence, constrain action, and change course.

Six abstractions and no object. "Expose state" is a race and a battle that never
got named.

**Repair.** Name one of the four and let it stand for the rest: *An agent that
cannot show which credential it used is an agent nobody can revoke.*

---

## Move 2. Let a physical detail carry the idea, and do not name the idea

**E.B. White**, *Once More to the Lake*, closing line, watching his son pull on
a cold wet swimsuit:

> As he buckled the swollen belt suddenly my groin felt the chill of death.

**Mechanism.** The essay is about mortality and inheritance and never uses either
word; a wet belt buckle does the work, and the reader supplies the abstraction,
which is why it lands as discovery rather than as assertion.

**Working, ours.** `articles/eval-engineering.md` opens on what the agent
actually said, then withholds the verdict for one beat:

> A travel agent, the software kind, answered a question about a trip: an
> exchange rate to one decimal place, the temperature for the week, the opening
> hours of a museum. All of it invented.

"Hallucination" is never used. The decimal place is the whole argument: nobody
invents precision unless they are inventing.

**Failing, ours.** `004/prototypes/editorial-emergent-narrative.md`:

> Autonomy becomes dangerous when it erases its path.

The idea is stated and nothing is seen. Six paragraphs later the piece is still
naming the idea.

**Repair.** The rerun editorial found the object:
`rerun-004/manuscript/editorial.md` opens "An intruder loose in someone else's
cloud estate attached `DryRun=True` to every destructive call it tried". Same
claim, and the reader arrives at it themselves.

---

## Move 3. Demonstrate. Do not assert

**Feynman**, Rogers Commission hearing, February 1986, holding a piece of O-ring
in a glass of ice water:

> I took this stuff that I got out of your seal, and I put it in ice water. And
> I discovered that when you put some pressure on it for awhile and then undo
> it, it doesn't stretch back. It stays the same dimension. In other words,
> there is no resilience in this particular material when it is at a temperature
> of 32 degrees. I believe that has some significance for our problem.

**Mechanism.** He performs the failure in front of you at the smallest scale on
which it is real, then states the conclusion in the flattest available words;
the understatement of the last sentence is affordable only because the
demonstration already made the argument.

**Working, ours.** `articles/mcp-in-a-nutshell.md` never argues that MCP's
one-client-per-server rule is sensible. It runs it:

> Picture Visual Studio Code with a server in front of your team's database.
> [...] Connect a second server, say the filesystem server on the same laptop,
> and the host builds a second client, one to one.

**Failing, ours.** `articles/mcp-protocol-update.md`:

> Authorization moves closer to how OAuth 2.0 and OpenID Connect are deployed in
> practice.

An assertion about a direction of travel, with nothing performed. The paragraph
under it contains the demonstration and buries it: a client that omits `iss`
validation can be walked into the wrong authorization server.

**Repair.** Lead with the failure the change prevents, then name the change.
Feynman's order: ice water first, significance last.

---

## Move 4. Choose the vantage point that makes a known fact astonishing

**Lewis Thomas**, *The Lives of a Cell*, opening of "The World's Biggest
Membrane":

> Viewed from the distance of the moon, the astonishing thing about the earth,
> catching the breath, is that it is alive.

**Mechanism.** He adds no fact the reader lacked; he moves the camera until an
ordinary fact becomes the only thing in frame, which is the cheapest value a
retelling can add and the one our modes are always allowed to add.

**Working, ours.** `articles/from-gpt2-to-kimi3.md`:

> Twenty-two thousand five hundred and eighty. That's how many GPT-2 models from
> 2019 fit inside KimiK3 from 2026, 124 million parameters against 2.8 trillion.

Both parameter counts were in the source. The ratio, spelled out and put first,
is the moon.

**Failing, ours.** `004/manuscript/editorial.md`:

> This edition follows those surroundings at six scales.

The camera is in the editor's chair, looking at the table of contents. Nothing
in the sentence is visible from any position a reader occupies.

**Repair.** Ask where a reader would have to be standing for this to be worth
saying, then start there. Vantage is free; a new fact is not, and in the
author-voiced modes a new fact is forbidden.

---

## Move 5. Omission is the work. White space is a place the reader writes

**Strunk**, *The Elements of Style*:

> Vigorous writing is concise. A sentence should contain no unnecessary words, a
> paragraph no unnecessary sentences, for the same reason that a drawing should
> have no unnecessary lines and a machine no unnecessary parts. This requires
> not that the writer make all his sentences short, or that he avoid all detail
> and treat his subjects only in outline, but that every word tell.

**McPhee**, *Draft No. 4*, in the essay "Omission":

> Writing is selection.

> The creative reader silently articulates the unwritten thought that is present
> in the white space.

**Mechanism.** Strunk removes the word that does not tell; McPhee removes the
paragraph the reader can supply, which is a larger and more frightening cut and
the one that separates a retelling from a summary. The second clause of Strunk
matters as much as the first: compression is not shortness, and a piece of
uniformly short sentences has usually cut detail instead of cutting slack.

**Working, ours.** `articles/frontier-lab-agent-intrusion.md` compresses two and
a half days into three clauses and lets the gap do the pacing:

> Day one bought the foothold and the channels. Day two was quiet. Day three
> carried every escalation that mattered.

**Failing, ours.** `articles/mcp-protocol-update.md` omits nothing. Its eight
sections are the release notes' eight sections, each faithfully shortened, none
dropped. It is a machine with all its parts and no selection, which is why it
reads as a changelog: the writer never decided anything, so the reader is never
told anything.

**Repair.** Before drafting, name the two sections of the source that will not
appear at all. If you cannot, you have not understood the source well enough to
retell it.

---

## Move 6. Length grows from the material and then stops

**McPhee**, *Draft No. 4*, paraphrased rather than quoted: a piece should grow
to whatever length its selected material sustains, and then stop.

**Mechanism.** Length is an output of selection, not an input to it. A budget
tells you the maximum a page can hold; it cannot tell you how much you have.

**Working, ours.** `articles/factory-systems-problem.md` runs 431 words and
`articles/pragmatic-leverage.md` 516, against a budget that would have allowed
1,100. Both are complete. Neither was padded to the ceiling.

**Failing, ours.** No shipped piece yet fails this loudly, which is the point of
writing it down before one does. The failure shape to watch for is a source of a
few hundred words arriving as a full-budget article, its extra length carried by
restatement, a second example, and a closing paragraph that recaps.

**Repair.** See "Right-sizing" in `docs/WRITING_RULES.md`. The test is the
paragraph deletion pass, and it is run before the page check, not after.

---

## Move 7. A number is not a fact until someone has to live with it

**Michael Lewis**, *Flash Boys*. The opening chapter is a description rather than
a quotation here: a fibre line is run 827 miles from Chicago to New Jersey,
blasted straight through the Alleghenies where going around would have been
cheaper, to take the round trip down to roughly thirteen milliseconds. Only
afterwards does Lewis state what the milliseconds made:

> The U.S. stock market was now a class system, rooted in speed, of haves and
> have-nots.

**Mechanism.** Thirteen milliseconds is unreadable as a quantity. It becomes
readable when you know a man dynamited a mountain to get it and what he got for
it, so the number is placed between the cost of obtaining it and the thing it
decided.

**Working, ours.** `articles/eval-engineering.md`:

> How good the answers were: 83.9%. How much of those answers was grounded in
> what the tools actually returned: 32.3%. The agent wrote beautifully and told
> the truth about a third of the time.

Two numbers, set against each other, then converted into a sentence about
behaviour. The same piece does it again with a person: "That is a 21-year-old
founder in Tokyo with 258 followers; his post on it got two likes."

**Failing, ours.** `articles/from-gpt2-to-kimi3.md`:

> Every layer after the first swaps the feed-forward network for a latent
> Mixture-of-Experts, 898 in all, two shared and run on every token, with the
> router picking 16 of the remaining 896.

Four numbers, none of which changes if you change it. 896 is arithmetic the
reader can do and 898 decides nothing in the argument.

**Repair.** Keep the number whose alteration would alter the claim, and give it
the sentence that says what it cost or what it bought. Cut the rest to a word:
*a router that wakes a handful of experts per token and leaves the rest asleep.*

---

## Move 8. Read it aloud, and cut what you would not say

**Paul Graham**, *Write Like You Talk*:

> Here's a simple trick for getting more people to read what you write: write in
> spoken language.

> They write in a different language than they'd use if they were talking to a
> friend.

> Before I publish a new essay, I read it out loud and fix everything that
> doesn't sound like conversation.

**Mechanism.** Every register failure in this magazine is audible and almost
none of them are visible; the sentence you would not say to a colleague at a
desk is exactly the sentence that was assembled rather than meant.

**Working, ours.** `rerun-004/manuscript/editorial.md`:

> Good engineering, from the wrong desk.

A fragment, and sayable. It survives being read aloud because someone could mean
it.

**Failing, ours.** `004/manuscript/editorial.md`:

> The model remains important. It is simply no longer an adequate unit of
> analysis.

Nobody says "adequate unit of analysis" to another person. Read aloud, the
sentence has the cadence of a conclusion and the content of a shrug.

**Repair.** The repo already ran this exact pass in
`004/prototypes/editorial-orwell-comparison.md` and produced "it no longer
explains enough on its own", which is better and still did not save the piece,
because that editorial's defect was structural. Move 8 fixes sentences. It
cannot fix a tour.

---

## Considered and declined

**Joan Didion.** Her power is rhythm, repetition, and the withheld clause. Our
characteristic failure is already too much cadence carrying too little content;
studying her would sharpen the tic rather than the prose. Revisit only once the
balanced-clause problem in `docs/WRITING_RULES.md` is gone from an edition.

**Tracy Kidder.** *The Soul of a New Machine* works by scene, character, and a
year of reporting access. We work from a text we did not gather, and inventing a
scene is a fabrication in every mode we publish. The move is unavailable to us,
not unwanted.
