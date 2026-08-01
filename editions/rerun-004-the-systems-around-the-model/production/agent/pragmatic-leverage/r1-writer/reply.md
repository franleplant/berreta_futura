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

<!-- SCRATCH: not part of the manuscript -->

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
