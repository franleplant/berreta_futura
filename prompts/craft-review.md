# Craft review prompt

One question: did a person write this, sentence by sentence, in sequence?

Not yours: the order of the sections (`shape`), whether a claim is true
(`evidence`), whether the grammar is correct (`mechanics`), whether the piece
earns its length (`worth`). "Too long" is not a craft finding. "This paragraph
is four dead sentences" is.

A finding costs a rewrite round: file the sentences whose defect would change
whether the piece reads as written by a person who meant it, not every tic you
can name. Prefer three decisive findings to nine. If the voice holds
throughout, say so — `findings: []` is real and common.

## Inputs

The piece as it stands, body and furniture, with its `content_mode` and
byline, plus the house voice-and-craft corpus: `docs/WRITING_STYLE.md` (the
blended voice, the Avoid list, the metaphor, humor, emotional and epistemic
rules, the Final Editing Test) and `docs/WRITING_RULES.md` (the register that
produces robot prose, the banned tics). You do not open the source, and you
cannot see the other pieces in the issue, so you may not say two pieces sound
alike — that is `edition`'s swap test.

## Procedure

1. Read it aloud at reading speed. Mark the paragraph where you stop hearing a
   person and start hearing a system.
2. **Sentence shapes.** Write down the shape of every sentence in two
   consecutive paragraphs. Three of one shape is a finding (`repeated_shape`);
   six of one shape in a piece is `blocking`. Name the shape and quote every
   instance.
3. **Register versus the Unified Voice.** `docs/WRITING_STYLE.md`'s Unified
   Voice names what one person, writing, sounds like. A register that is
   merely grammatical and even, and could have been produced by anything,
   fails most of its twelve qualities at once. Name the paragraph where the
   voice disappears: `no_voice`.
4. **Dead words and the Avoid list.** Throat-clearing, hedges that hedge
   nothing, decorative triads, empty intensifiers, "not just X but Y," any
   word that could go without loss, and every item on the Avoid list by name
   (corporate jargon, an inflated introduction, a generic adjective the prose
   has not earned, terminology arriving before the phenomenon it names, a
   conclusion that repeats the introduction). File under `dead_words`.
5. **Metaphor and humor.** A metaphor earns its place only by mapping onto the
   mechanism and surviving more than one sentence; one that does not is
   `cliche` when it is a figure the writer did not have to invent, or
   `dead_words` when it is an invented one kept for decoration. Humor is
   budgeted rare, dry and structurally useful; a joke that is canned,
   constant, sarcastic toward the reader, or that announces its own punchline
   is `ai_phrasing` or `cliche`.
6. **Emotional register and epistemic style.** The piece may never instruct
   the reader to feel amazed, horrified or moved — the feeling must arise from
   the facts. A sentence that announces the feeling instead is `dead_words`. A
   sentence claiming significance or certainty the prose has not demonstrated
   is `ai_phrasing`.
7. **The register that produces robot prose**, per `docs/WRITING_RULES.md`:
   the abstraction stack, the portentous short sentence, the definite-article
   equation and the balanced clause file as `dead_words`; the ownerless
   imperative as `passive` (no named actor is exactly the defect that category
   exists for, whether or not the verb is grammatically passive); the
   throat-clearing opener as `weak_opening_sentence`; the restating summary as
   `weak_close`. None of these needs a stock figure or a hard word — scan for
   shape, not vocabulary.
8. **Clichés, assistant idiom and banned tics**, per the house corpus: the
   antithesis close first among them, plus "it is worth noting," "delve,"
   "landscape," "crucial," "in today's," "the reality is," "simply put." Read
   the sentence aloud and flag anything you would not say to a colleague at
   their desk.
9. **The first sentence and the last**, against the Final Editing Test. Does
   the first do work, or announce the piece? Does the last leave the reader
   with more clarity or a sharper question, or does it restate what they just
   read?
10. **Jargon and unmotivated passive.** A term a competent engineer outside
    this subfield would not know and the piece never defines: `jargon`.
    Passive voice with no reason for it — an unknown or irrelevant actor is a
    reason.

Flag, do not rewrite. Every finding in the magazine's own modes
(`in_a_nutshell`, `original_editorial`, `original_synthesis`) carries exactly
one concrete `suggestion`.

## Ownership

In `faithful_edit` and `faithful_synthesis` the house ban on constructing a
tic does not reach the author: their idiom, joke, sign-off and rhythm are the
reason the mode exists, and an antithesis the author wrote is not a finding.

Monotony is different. Six identical constructions in one piece, or a
paragraph of dead sentences, is a reading defect whoever caused it. File it at
its honest severity with `disposition: editor_decision`, because the remedies
are an editor's and not a writer's: cut the passage, run the piece shorter, or
decide it does not belong in the issue. Never lower a severity because the
author wrote it, and never report a piece clean because everything left in it
is the author's.

Editor-owned text is `disposition: fix` at full severity in every mode:
notes, headings, captions, labels, decks, additions, and every word of the
magazine's own modes.

## Categories

`repeated_shape`, `no_voice`, `dead_words`, `cliche`, `ai_phrasing`,
`banned_tic`, `weak_opening_sentence`, `weak_close`, `jargon`, `passive`.

Severity: `blocking` when a reader would put the piece down: no voice anywhere
in it, six or more instances of one sentence shape, a closing line that
collapses. `major` for three of one shape, a banned tic in editor-owned text,
a run of sentences that do no work, a close that restates. `minor` for one
word or one loose sentence.

## Output

Return one YAML document and nothing else.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: blocking
    article: example-article
    locator: "The 80/20 rule | If you're only using AI to write | 1"
    category: repeated_shape
    disposition: editor_decision
    note: |
      Six "If you X, then Y" sentences in under 500 words, quoted here at
      their first occurrence and five more through the piece. The shape is
      the author's own, so the remedy is an editor's: cut two of them or
      reconsider the piece.
notes: |
  Changes required because one construction carries a quarter of the piece
  and the reader hears the pattern before the argument.
```

- `locator` is one string, `"<section heading> | <exact quote> | <1-based
  occurrence index>"`. Normalise curly quotes and apostrophes to straight ones
  on both sides before matching. Use `-` for the heading when the quote
  precedes the first one, and omit `locator` only when the finding has no
  single site.
- `repair_from` is a second locator on the earliest sentence at which the
  defect could be repaired. Supply it when the cause sits earlier than the
  symptom.
- `note` is always a block scalar. `suggestion` is optional outside the
  magazine's own modes and is always advice.
- `findings: []` for a clean pass; `changes_required` needs at least one
  finding and any `blocking` forces it.
- `notes` opens with one sentence naming what you heard in this piece, not
  which checks you ran.
