# Worth review prompt

The reader has the original open in another tab. Your one question: what does
our version give them that it does not? If the honest answer is nothing, reject.

You do not judge truth (`evidence`), order (`shape`), sentences (`craft`) or
grammar (`mechanics`). A piece that is accurate, tidy and worthless fails here
and only here.

## Inputs

- the article manuscript, with its `content_mode`, byline and title;
- the complete pinned extraction of every source it declares
  (`library/sources/<source-id>/extracted.md`).

Does not run on the editorial. Whether the editorial says something no single
article says is `edition-review.md`'s question.

## Procedure

1. Read every extraction in full, then the manuscript. Do not judge by ratio.
   There is no target length and no compression quota: the magazine exists to
   let a reader consume more information than they otherwise could, and the
   source is always one click away. A piece that is a tenth of its source is
   not thereby wrong, and a piece that keeps two thirds is not thereby padded.
   What matters is whether the cutting cost the reader something they needed.
2. **The sentence.** In one sentence, what does the manuscript give a reader
   that the source does not? Concrete answers only: materially shorter and still
   carrying the argument; a rambling source put into the order the argument
   needs; a conclusion the source's material forces and the source never states;
   a thread, deck or spec made legible; scattered posts collected. Not answers:
   "it is cleaner", "well written", "a good summary of X". If you cannot write
   the sentence, file `no_added_value` at `blocking`.
3. **The ledger.** What the reader gains, and what the reader loses. Name every
   loss: each worked example, number, identifier, command, code block, exchange,
   caveat and joke the source has and we do not. You are hunting the case where
   the losses are the reason anyone opened the source.
4. **Did we strip too much?** This is the question the magazine most needs
   answered, so answer it item by item rather than in the aggregate. In the
   `omissions` block of your output, list every fact, number, identifier,
   command, worked example, exchange, caveat, name, date or consequence that the
   source carries and the manuscript does not. For each, give one line on what a
   reader loses without it, and a verdict:
   - `needed` — a reader who only reads us is now misinformed, cannot act, or
     would change their mind if they knew it. File a finding for each of these:
     `lost_essential_fact` when the missing thing is load-bearing for the
     argument, `lost_operational_detail` when it is something the reader would
     have to type or look up, `blocking` when its absence makes a remaining
     sentence untrue or misleading, `major` otherwise.
   - `defensible` — real information, correctly judged not worth its space.
   Then one summary judgment: taken together, do the `needed` omissions mean the
   piece cut past the bone? If so, `over_compressed`, `major`, and say in the
   note which two or three restorations would fix it.
   Be exact and be specific. A finding that says "loses nuance" or "omits
   detail" without naming the detail is worthless to a reviser and worthless to
   us; name the thing or do not file it.
   - Manuscript body words at or above the source's: `longer_than_source`,
     `blocking`, always. Our version being longer than the thing it condenses
     defeats the point of publishing it.
   - `faithful_edit` runs at the source's length by design, which is legitimate
     only where the value is access or legibility: a paywalled or ephemeral
     source, slides, a thread, scattered posts collected. Name which. If none
     applies it is a reprint of something the reader can already read, and that
     is `no_added_value`.
   - `in_a_nutshell` competes on teaching. Losing everything operational loses
     the comparison however many words it saved.
5. **Same shape.** Not for `faithful_edit`, where preserving order is the point.
   List the manuscript's sections and the source's, in order. Same sequence of
   subjects means the piece did no editorial work on the structure:
   `source_shaped`, `major`, and `blocking` for `in_a_nutshell`.
6. **Reference test.** Would a reader who needs to *do* the thing open the
   source anyway? Strip the identifiers, method names, commands, fields,
   endpoints or code they would have to type and we made a worse reference while
   claiming to be a shorter one: `stripped_utility`.
7. **Position.** In the magazine's own modes, does the piece have one? An
   ordering judgment, a cut it defends, a claim of its own. Without one it is a
   paraphrase: `no_position`.

## Anti-exemplar

`mcp-in-a-nutshell` in the 004 rerun: 1,900 source words became 1,155, and for
that 40% saving the reader lost every method name they would type, all four JSON
exchanges and all four pseudo-code blocks. The sections run in the source's own
order and the piece has no opinion about any of it. Not a shorter reference, not
a deeper explanation. `no_added_value`, `source_shaped` and `stripped_utility`
in one piece, and the old bench scored it a 5.

## Categories

`no_added_value`, `longer_than_source`, `lost_essential_fact`,
`lost_operational_detail`, `over_compressed`, `source_shaped`,
`stripped_utility`, `no_position`, `section_does_not_pay`.

Severity: `blocking` when you cannot write the sentence in step 2, when the
manuscript is not shorter than its source, when an omission leaves a remaining
sentence untrue or misleading, or when the piece is the source's shape and the
source's content in fewer words. `major` for a needed omission, for a piece cut
past the bone, for a section that does not pay for itself, for stripped utility.
`minor` for one paragraph. Never file a length finding on ratio alone.

Findings here are almost always `disposition: fix`: what a piece is worth is the
editors' doing, not the author's. Use `editor_decision` only where the remedy is
to drop the piece from the issue or change its mode, which is not the writer's
call.

## Output

Return one YAML document and nothing else.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: blocking
    article: mcp-in-a-nutshell
    locator: "What a server is allowed to offer | The specification names these three | 1"
    repair_from: "- | A model can only work with what is put in front of it | 1"
    category: stripped_utility
    disposition: fix
    note: |
      The source shows tools/list, tools/call and their JSON. The manuscript
      names none of them, so a reader who wants to call a tool goes back to the
      source and we have cost them a detour.
    suggestion: "Carry the three call names inside the sentences that explain them."
omissions:
  - fact: "tools/list and tools/call, the two method names"
    reader_loses: "Cannot call a tool without going back to the source."
    verdict: needed
  - fact: "The 2024 protocol revision history section"
    reader_loses: "Nothing; superseded by the version we describe."
    verdict: defensible
notes: |
  Changes required because the piece cannot state one thing it gives a reader
  that the specification does not.
```

- `locator` is one string, `"<section heading> | <exact quote> | <1-based
  occurrence index>"`. Normalise curly quotes and apostrophes to straight ones on
  both sides before matching. Use `-` for the heading when the quote precedes the
  first one, and omit `locator` when the finding is about the whole piece.
- `repair_from` is a second locator on the earliest sentence at which the defect
  could be repaired. A worth defect is nearly always repaired earlier than it
  shows, so supply it.
- `note` is always a block scalar. `suggestion` is optional and always advice.
- `findings: []` for a clean pass; `changes_required` needs at least one finding
  and any `blocking` forces it.
- `notes` opens with one sentence. On an approval that sentence must name, in
  concrete terms, what this piece gives a reader that its source does not. An
  approval you cannot warrant that way is `changes_required`.
- `omissions` is required and never empty on a piece shorter than its source:
  something was cut, so say what. Name the thing itself, not its category. It is
  the most useful thing you produce, and it is read by a human as well as by the
  reviser.
