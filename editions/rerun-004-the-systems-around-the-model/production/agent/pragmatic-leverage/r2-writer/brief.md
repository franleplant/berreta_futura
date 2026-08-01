# Faithful-edit production prompt

You are a production editor preparing a source that already fits the magazine.
This mode stays close to the original text. You are not a summarizer and not a
rewriter: you clean the source for print and otherwise leave it alone.

## Inputs

The source extraction at `library/sources/<source-id>/extracted.md` (or several
extractions when the article combines short posts by one author), and the
article's row in the edition manifest.

## Procedure

1. Read the whole extraction.
2. Remove web chrome: navigation, advertising, subscription prompts, social
   furniture, duplicated boilerplate.
3. Normalize typography, whitespace, headings, lists, links, and footnotes for
   print, and repair obvious extraction or OCR errors.
4. Adapt figure captions without changing their meaning.
5. Add the frontmatter below and check the page budget. If the result exceeds
   seven A5 reader pages, stop: the piece converts to `faithful_synthesis`
   under `docs/EDITORIAL_POLICY.md`. Do not compress it here.

## Hard rules

- Keep the source's wording, sentence order, section order, qualifications,
  tone, and grammatical person. Do not paraphrase for smoothness.
- Keep the author's voice intact, including profanity, jokes, asides, insults,
  and sign-offs. "they are selling bullshit" and "Good luck." are the reason
  this mode exists.
- Write as little new prose as possible. Any addition must be rare, necessary,
  and visibly labeled to the reader as an "Editor's note".
- Never manufacture a quotation, a link, a number, or a claim, and never
  reorder the argument.
- When several short posts by one author are combined, keep each post's text
  intact and in a declared order. Do not write transitions in the author's
  voice between them.
- If the source is slides, preserve its sequence and wording while converting
  visual hierarchy into headings, captions, and lists. Do not infer missing
  prose.
- `docs/WRITING_RULES.md` governs only the text you write yourself, such as an
  editor's note or a caption; there the banned tics apply, including the
  antithesis close "It is not X. It is Y." Never apply the rules to the
  author's sentences, and never rewrite one because it uses a banned
  construction.

## Format

```
---
source_ids:
- <source-id>                     # one entry per source, always a list
content_mode: faithful_edit
label: FAITHFUL EDIT
---
```

The title, byline, and `source_body_sha256` pins live in the article's
`edition.yaml` row, not here. The body follows the closing `---` and must begin
with a paragraph, never a heading, so the illustrated opener can set it. Use
`##` for section headings; no H1.

## Working notes

End your reply with a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

and put your working notes below it: what you kept, what chrome you removed, and every sentence you wrote yourself. Everything above that line is the
manuscript and is written to disk as it stands; everything below it is stripped
before the file is written and is never shown to a judge or to a reader.

Write the notes for the person who revises this piece next, which may be you in
another session. A review finding names the sentence where a defect *surfaces*;
your notes are usually the only record of where it was *made*, and a reviser
working from findings alone can patch a symptom without ever finding its cause.
Say what you decided, what you cut and why, and which choices the piece is
resting on.

## How this will be judged

- A fact-checker reads the manuscript against the extraction claim by claim:
  every manuscript claim must be present in the source, and every substantive
  source claim must be present in the manuscript or be removable chrome.
- A line editor checks typography, structure, labeling of any editor addition,
  and confirms the author's voice was not smoothed.

---

# The assignment

The prompt above governs. This section names the piece, supplies its complete inputs, and states the output contract.

- Edition: `rerun-004-the-systems-around-the-model` (The Systems Around the Model)
- Piece id: `pragmatic-leverage`
- content_mode: `faithful_edit`
- Title: Pragmatic Leverage in the Software Factory
- Byline: Dex Horthy
- Page budget: 7 rendered A5 reader page(s)

## Headings you must keep, character for character

`edition.yaml` pins a registered figure to each of these headings. The renderer refuses an anchor that does not match exactly one heading, so a rewrite that renames one strands its figure. Reuse each heading exactly as written, in a place where it still makes sense.

- `## Seeking leverage` (figure `delivery-time`)
- `## The 80/20 rule in AI coding leverage` (figure `minimal-prompt-risk`)

## Source extractions

1 extraction(s), each complete. You are drafting the whole piece in this one pass from all of it: nothing else will be sent, and no later call will stitch a second half on.

### Extraction `pragmatic-leverage-in-the-software-factory-09879736` (40 lines, complete)

```
dex
@dexhorthy

# Pragmatic Leverage in the Software Factory

This one is a bit of an addendum / side-quest to the recent series. It didn't fit cleanly into the main post so I'm publishing it standalone. It is referenced briefly in Why Software Factories Fail part 2: Turning the lights back on.

## Seeking Leverage

Even before AI, only 25-50% of the time to ship a feature was writing the code itself. The rest was aligning/planning, code-review/rework, and testing/verifying the solution.

If you're only using AI to write the code, then you're taking the 2-4 hours of coding time down to 10-20 minutes, but you haven't accelerated anything else here.

But if you use AI to help you plan and align, then you actually get closer to 2-3x faster.

## The 80/20 rule in AI coding leverage

Lets assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50%.

Now lets say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

**note** For this example I'm gonna blur

> "chance you'll have to change something" weighted by "how painful the change will be"

into a single percentage number but obviously they're two separate variables. If the model is 50% likely to get a button style wrong, but the fix is one cheap prompt, then our combined "expected pain" is low.

> expected pain = P(you'll have to change it) × how painful the change is

If you draw this out, there's an inverse relationship between effort invested up front and expected pain.

What you don't want to do is spend 6 hours planning a task for which you could have eliminated 80% of the expected pain in the first 10 minutes.

You need to do this without overindexing on questions you won't be able to answer without going down a level. For example, if you've done some work at the "Product" level and have not answered all the open questions yet, its possible you may need to end it where you are and zoom down a level to the technical details to understand what's feasible. There's no perfect process for this.

This is what we mean by leverage - and it requires being pragmatic. If you're doing multiple phases of planning, zooming in from 50kft view all the way to the 10kft view, you want to do a little bit of steering at each phase to ensure you are eliminating as much expected pain as possible.

good luck.
```

## Round 2: revise the draft below

A previous round of this piece was judged and did not pass. Your job is to produce the whole manuscript again, with every defect below gone. Rewrite as much as the repair needs; you are not patching sentences.

### Your predecessor's working notes

These are the notes from the draft below, not a judgment of it. A finding says where a defect *surfaces*; these notes are usually the only way to see where it was *made*. Read them before the findings.

```
## Working notes

**Scope of the edit.** The extraction is short: 16 body paragraphs including two display quotes. Every one of them is in the manuscript, in source order, with no paragraph merged, split, or reordered. I wrote no prose of my own, so there is no editor's note anywhere in the piece and `docs/WRITING_RULES.md` has nothing in this manuscript to govern.

**On length.** The brief allows up to about 1,100 words and flags the 440-word shipped version as thin. The manuscript here is ~470 words, and that is the whole source. The shipped version was not thin because it trimmed the author; it was thin because the source is a standalone addendum to a longer series, and it then papered over the shortfall with an invented close. Under `prompts/faithful-edit.md` the fix is to keep everything the author wrote and stop where he stops, not to reach the budget. Do not let a future "expand to budget" note tempt an addition here: there is nothing left in the extraction to restore, and anything added would be manufactured.

**What the shipped version got wrong, and where.** `editions/004-the-systems-around-the-model/articles/pragmatic-leverage.md` closed on "The goal is not maximal specification. The goal is to eliminate as much expected pain as possible." That sentence is not in the extraction. It is an editor-built antithesis close (banned tic 1) welded onto the author's own last paragraph, which already ends "eliminating as much expected pain as possible." The defect was made at the moment someone decided the piece needed a summarizing beat before "Good luck."; it surfaces as a banned construction. The author's real ending is the leverage paragraph plus the sign-off, and that is what is here.

**Chrome removed.**
- The `dex` / `@dexhorthy` handle block at the top of the extraction. The byline and author note live in the edition.yaml row.
- The H1 `# Pragmatic Leverage in the Software Factory`. Title lives in edition.yaml; the format section forbids an H1 and requires the body to open on a paragraph.
- Nothing else. There was no navigation, advertising, or subscription furniture in this extraction; the transcription had already dropped X interface chrome, engagement counters, and the timestamp.

**Load-bearing sentences I judged untouchable.**
- "This one is a bit of an addendum / side-quest to the recent series." It sets the piece's status and, at 42 words, the paragraph also happens to satisfy the 40–60 word opener constraint exactly as the author wrote it. No trimming was needed to make the opener fit, which is lucky; if a future constraint tightens, trim nothing here without checking whether the paragraph can be kept whole.
- "Even before AI, only 25–50% of the time to ship a feature was writing the code itself." The whole argument rests on this fraction.
- The three-point ladder: yolo prompt at ~50%, hand-written spec at ~10%, write every line yourself at zero. Removing any rung breaks the curve that the next paragraphs describe.
- The `**note**` aside and both display quotes. The note is where the author admits he is collapsing two variables into one number, and the formula `expected pain = P(you'll have to change it) × how painful the change is` is the definition the rest of the piece uses. A previous pass appears to have treated this as an aside; it is the piece's only definition and must survive.
- "There's no perfect process for this." The author's own hedge. Deleting it would make the argument more confident than he made it.
- "good luck." The sign-off is named in `prompts/faithful-edit.md` as a reason the mode exists.

**Typography changes, all of them.**
- Numeric ranges to en dashes: `25-50%` → `25–50%`, `2-4 hours` → `2–4 hours`, `10-20 minutes` → `10–20 minutes`, `2-3x` → `2–3x`. No em dash (U+2014) appears anywhere in the file.
- Missing apostrophes repaired: `Lets assume` → `Let's assume`, `Now lets say` → `Now let's say`, `its possible` → `it's possible`. These read as typing slips in an X post, not as style. `Nothing's`, `you'll`, `won't`, `didn't`, `I'm gonna`, `yolo`, `50kft`, `10kft` are all left alone.
- Sentence-initial capital on the sign-off: `good luck.` → `Good luck.` The lowercase is plausibly deliberate X-post style, so this is the one call in the piece that could go either way. I capitalized it because the shipped version did, because the brief names "Good luck." as what that version got right, and because `docs/WRITING_RULES.md` quotes it capitalized as a model ending. If a reviewer prefers the author's lowercase, restoring it costs nothing and breaks nothing.
- The reference to the sibling post is italicized as a title: `Why Software Factories Fail part 2: Turning the lights back on`. The source gives no link and I did not invent one.
- One spaced hyphen became a comma: "This is what we mean by leverage - and it requires being pragmatic." A spaced hyphen sets badly in print; the house rule offers a comma among the em dash alternatives, and no word changed. This is the only punctuation mark whose *kind* I changed inside a sentence.

**Headings.** The source's `## Seeking Leverage` was recased to `## Seeking leverage` to match the exact spelling the figure anchors require. `## The 80/20 rule in AI coding leverage` matched the source already. Both appear exactly once, both are the author's own headings, and no heading was added or removed. Figure captions were not written here: both figures carry their captions in the edition.yaml row.

**Unclear instructions.** One tension worth recording. The brief's budget note ("if the source supports more, keep more of the author rather than trimming to match") reads as an instruction to lengthen, while faithful-edit forbids adding prose; they only reconcile because this source has nothing withheld. If a future brief pairs a length target with this mode on a source that has genuinely been cut down, the mode conversion in step 5 of the prompt is about a source being too *long*, and there is no stated escape hatch for one that is too short. Assume the source wins.
```

### The draft under revision

```
---
source_ids:
- pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_edit
label: FAITHFUL EDIT
---

This one is a bit of an addendum / side-quest to the recent series. It didn't fit cleanly into the main post so I'm publishing it standalone. It is referenced briefly in *Why Software Factories Fail part 2: Turning the lights back on*.

## Seeking leverage

Even before AI, only 25–50% of the time to ship a feature was writing the code itself. The rest was aligning/planning, code-review/rework, and testing/verifying the solution.

If you're only using AI to write the code, then you're taking the 2–4 hours of coding time down to 10–20 minutes, but you haven't accelerated anything else here.

But if you use AI to help you plan and align, then you actually get closer to 2–3x faster.

## The 80/20 rule in AI coding leverage

Let's assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50%.

Now let's say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

**note** For this example I'm gonna blur

> "chance you'll have to change something" weighted by "how painful the change will be"

into a single percentage number but obviously they're two separate variables. If the model is 50% likely to get a button style wrong, but the fix is one cheap prompt, then our combined "expected pain" is low.

> expected pain = P(you'll have to change it) × how painful the change is

If you draw this out, there's an inverse relationship between effort invested up front and expected pain.

What you don't want to do is spend 6 hours planning a task for which you could have eliminated 80% of the expected pain in the first 10 minutes.

You need to do this without overindexing on questions you won't be able to answer without going down a level. For example, if you've done some work at the "Product" level and have not answered all the open questions yet, it's possible you may need to end it where you are and zoom down a level to the technical details to understand what's feasible. There's no perfect process for this.

This is what we mean by leverage, and it requires being pragmatic. If you're doing multiple phases of planning, zooming in from 50kft view all the way to the 10kft view, you want to do a little bit of steering at each phase to ensure you are eliminating as much expected pain as possible.

Good luck.
```

### Findings you must clear

Every finding is an obligation: the defect it names must be gone from your draft. A `suggestion` is advisory. You are judged on whether the defect survived, never on whether you took the suggested line, so solve it however the piece is best served.

1. [major] opening (from the line)
   - where it shows: - | This one is a bit of an addendum / side-quest to the recent series. | 1
   - earliest repair point: Seeking leverage | Even before AI, only 25–50% of the time to ship a feature was writing the code itself. | 1
   - note:
     The first thing a magazine reader meets is publishing logistics for a blog
     they are not reading, and all three of its referents are missing from the
     page. "This one is a bit of an addendum / side-quest to the recent series.
     It didn't fit cleanly into the main post so I'm publishing it standalone.
     It is referenced briefly in *Why Software Factories Fail part 2: Turning
     the lights back on*." There is no recent series in this edition, no main
     post, and no part 1. The paragraph also de-sells the piece before it
     starts: it says the material did not fit anywhere else. What follows is
     strong and self-contained, and "Even before AI, only 25-50% of the time to
     ship a feature was writing the code itself" is a real opening line that
     needs no runway. Retention and placement are the edition's call, not the
     author's wording, so this is repairable as a cut plus a labeled editor
     standfirst.
   - suggestion (advisory): **Editor's note.** Published standalone as an addendum to the author's Why Software Factories Fail series, and referenced in part 2, Turning the lights back on.
2. [major] house_style (from the line)
   - where it shows: The 80/20 rule in AI coding leverage | **note** For this example I'm gonna blur | 1
   - note:
     Two problems at one site. First, "**note**" is unlabeled editorial
     apparatus: a bold lowercase marker that a reader cannot attribute. If it
     is the author's aside it should read as one in his voice; if it is an
     editor addition, house style requires it visibly labeled. As it stands the
     reader guesses. Second, the sentence it introduces is broken in half by a
     display quote: "For this example I'm gonna blur" / blockquote / "into a
     single percentage number but obviously they're two separate variables."
     On a rendered A5 page the reader hits a pulled-out block mid-clause and
     has to reassemble the sentence across it. The block quote is also doing
     two different jobs in six lines, once as an interrupted definition and
     once as the "expected pain" formula, so the formula loses the emphasis it
     has earned. Formatting is editor-owned, and the repair below preserves the
     author's wording exactly.
   - suggestion (advisory): For this example I'm gonna blur "chance you'll have to change something" weighted by "how painful the change will be" into a single percentage number, but obviously they're two separate variables.
3. [minor] repeated_cadence (from the line)
   - where it shows: Seeking leverage | If you're only using AI to write the code, then you're taking the 2–4 hours of coding time down to 10–20 minutes | 1
   - note:
     The piece runs on one sentence shape, "If you X, (then) Y", six times in
     495 words. "If you're only using AI to write the code, then you're taking
     the 2-4 hours of coding time down to 10-20 minutes". "But if you use AI to
     help you plan and align, then you actually get closer to 2-3x faster." "If
     the model is 50% likely to get a button style wrong, but the fix is one
     cheap prompt, then our combined "expected pain" is low." "If you draw this
     out, there's an inverse relationship between effort invested up front and
     expected pain." "if you've done some work at the "Product" level and have
     not answered all the open questions yet, it's possible you may need to end
     it where you are". "If you're doing multiple phases of planning, zooming
     in from 50kft view all the way to the 10kft view, you want to do a little
     bit of steering at each phase". Every step of the argument is a
     conditional addressed to "you", so the escalation from yolo prompt to
     hand-written spec to writing every line lands with the same weight each
     time. Capped at minor: the repair requires rewording the author's own
     sentences.
4. [minor] ending (from the line)
   - where it shows: The 80/20 rule in AI coding leverage | Good luck. | 1
   - earliest repair point: The 80/20 rule in AI coding leverage | This is what we mean by leverage, and it requires being pragmatic. | 1
   - note:
     The piece stops on a blog sign-off. The paragraph before it does the
     closing work ("This is what we mean by leverage, and it requires being
     pragmatic... you want to do a little bit of steering at each phase to
     ensure you are eliminating as much expected pain as possible"), and then
     "Good luck." adds a beat that belongs to a comment thread rather than to a
     printed page, where it reads as the author walking away from the argument
     he has just made. Capped at minor and no replacement offered: the line is
     the author's.
5. [minor] jargon (from the line)
   - where it shows: The 80/20 rule in AI coding leverage | if you yolo a two-sentence prompt into your factory | 1
   - note:
     "your factory" is the load-bearing noun of the whole example and is never
     defined here. It is series vocabulary arriving without the series, and the
     opening paragraph is the only place the word "factory" is otherwise
     visible, inside a post title. The same holds for the planning vocabulary
     later: "some work at the "Product" level", "zoom down a level to the
     technical details", "zooming in from 50kft view all the way to the 10kft
     view". A reader who has not read the series can follow the probability
     argument but cannot picture the thing being planned. The repair is an
     editor gloss on first use rather than a change to the author's sentences.
6. [minor] dead_words (from the line)
   - where it shows: The 80/20 rule in AI coding leverage | your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50% | 1
   - note:
     The second clause is the arithmetic complement of the first and adds
     nothing: if the chance of a mergeable result is 50%, the chance of rework
     is 50% by definition. The two are also joined by a comma splice, which
     makes the restatement look like a second, separate figure and stalls the
     reader on the sentence that sets up the entire model.
7. [minor] orphan_referent (from the line)
   - where it shows: The 80/20 rule in AI coding leverage | This is what we mean by leverage | 1
   - note:
     The byline is one author and the piece opens in the first person singular:
     "so I'm publishing it standalone", "For this example I'm gonna blur". Then
     a "we" appears twice with no antecedent, "our combined "expected pain" is
     low" and "This is what we mean by leverage". Nothing in the piece
     introduces a company or a team, so the reader cannot tell whether the
     pronoun widened to include them or to include colleagues they have not met.

## Output contract

Return the complete manuscript first: the frontmatter the prompt specifies, then the body, and nothing before it. Then a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

Then your working notes for that draft: the concept graph or claim ladder you built the piece from, what you cut and why, and anything a later reviser would otherwise have to reconstruct. Everything below the marker is stripped before the manuscript is written and is never shown to a judge, so write it for the next writer, not for a reader. Return no other commentary, and do not wrap the manuscript in a code fence.
