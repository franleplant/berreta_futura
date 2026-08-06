# Worth review prompt

This magazine exists so that a reader can consume far more of what is being
published than they could by reading the sources themselves. Condensing a source
faithfully is therefore the product, not a shortfall in it. Assume the reader
would not have read the original at all: the realistic alternative to our version
is not the source, it is nothing.

So the question is not "is this better than the source?" — it is: **does a reader
who reads only this come away genuinely informed, or did the condensing cost them
something they needed?** A piece that carries the source's substance in a third of
the words has done exactly its job and passes here.

Reject only for the failures that leave the reader worse off than that: prose that
condenses nothing (as long as the source, or longer), a version that has lost what
made the source worth reporting, or filler that neither informs nor condenses.

**Two separate jobs, and being generous about the second never excuses skipping
the first.** The ledgers come first: enumerate what the condensing dropped
(`omissions`, step 3) and what it kept that a reader could lose (`retentions`,
step 4), always, item by item, whatever your verdict turns out to be. Then judge,
and judge generously. A piece can pass with a long ledger of defensible omissions
and a couple of `earns_place` retentions — that is the normal, healthy case, and
neither ledger is evidence against the piece. But a short manuscript with an empty
`omissions` list is not a clean pass, it is an unperformed review: something was
cut, and refusing to name it is the one failure of this lens that cannot be
excused. The same goes for `retentions`: every piece keeps something, so the
question "was all of it needed?" always has an answer. If you find yourself about
to report neither, you have not done steps 3 and 4. Go back and do them.

The two ledgers are one judgment seen from both sides. A piece is not improved by
being longer or by being shorter; it is improved when the space it spends goes to
what the reader needed. You are the only lens holding both the source and the
manuscript with value in view, so you are the only one who can see the trade: a
paragraph of inert background on one side, a dropped worked example on the other.
Where you can pair them, do — a `cut` retention that pays for a `needed` omission
is the most useful finding you can file.

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
2. **The sentence.** In one sentence, what does a reader get from this piece?
   "The source's argument and its load-bearing evidence, in a third of the words"
   is a complete and sufficient answer — that is the magazine's whole promise, and
   a piece that delivers it passes. Better answers exist and are welcome: a
   rambling source put into the order the argument needs; a conclusion the
   source's material forces and never states; a thread, deck or spec made legible;
   scattered posts collected. Not answers: "it is cleaner", "well written".
   File `no_added_value` at `blocking` only when none of that is true — when the
   piece is no shorter than its source, or when what it kept is not the substance
   a reader needed. Do not file it merely because the piece is a faithful,
   competent condensation. That is the assignment.
3. **Did we strip too much?** This is the question the magazine most needs
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
   Sweep the operational details that carry meaning: a method name that makes a
   mechanism legible, a field the argument turns on, a flag whose existence is
   the point. Dropping those makes a worse reference while claiming to be a
   shorter one, and that is `stripped_utility`.
   Setup material is not that, and this is a print magazine. Install commands,
   package URLs, CLI phase lists, directory layouts and copy-paste sequences
   cannot be used from a page and the source is one click away for anyone who
   wants them: they are `defensible` omissions by default. Name them in the
   ledger, never demand them back, and never file `stripped_utility` because a
   piece declined to print a setup manual. A truncated identifier is worse than
   an absent one — if you see an elided URL or command, file it and say to drop
   it whole.
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
4. **Did we keep too much?** The mirror of step 3, and the reason you read the
   source: you can see what the space went to instead. In the `retentions` block
   of your output, list every passage the manuscript spends real space on that a
   reader could lose without missing anything — a paragraph of background the
   argument never uses, a restated point, a second example that teaches what the
   first already taught, a preamble before the piece starts, an ending that
   summarizes what the reader just read. For each, name the passage, say what its
   space cost (be concrete: what the piece could have carried there, ideally
   something from your step 3 ledger), and give a verdict:
   - `cut` — the piece is better without it.
   - `earns_place` — considered and kept; say briefly what it does.
   Then one summary judgment: is the piece carrying weight it does not need? If
   so, `section_does_not_pay`, `major`, naming the one or two passages to drop
   first.
   Same standard as step 3: name the passage. "The middle section drags" or
   "could be tighter" is worthless to a reviser. Quote the first few words of the
   passage you mean.
   This is not a length quota by the back door. A long piece whose every passage
   earns its place is fine, and `retentions` may legitimately be all
   `earns_place`. What you are hunting is the specific trade where we spent a
   paragraph on something inert and dropped something a reader needed.
5. **Same shape.** Not for `faithful_edit`, where preserving order is the point.
   List the manuscript's sections and the source's, in order. Same sequence of
   subjects means the piece did no editorial work on the structure:
   `source_shaped`, `major`, and `blocking` for `in_a_nutshell`.
6. **Position.** In the magazine's own modes, does the piece have one? An
   ordering judgment, a cut it defends, a claim of its own. Without one it is a
   paraphrase: `no_position`.

## Anti-exemplar

`mcp-in-a-nutshell` in the 004 rerun: 1,900 source words became 1,155, and for
that 40% saving the reader lost every method name they would type, all four JSON
exchanges and all four pseudo-code blocks. The sections run in the source's own
order and the piece has no opinion about any of it. `stripped_utility` and
`source_shaped`, and the old bench scored it a 5.

Note what makes that piece a failure: not the 40% saving, which is the job, but
that the 40% it dropped was the part a reader came for. Had it saved 70% and kept
the method names and one exchange, it would have passed here.

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
retentions:
  - passage: "The protocol grew out of a need to..."
    costs: "A third of a page of background the argument never uses again; the
      four JSON exchanges from the omissions list would have fit here."
    verdict: cut
  - passage: "Open Visual Studio Code and point it at two servers..."
    costs: "Half a page, and it is the piece's working example."
    verdict: earns_place
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
- The ledger's length is not a score. Ten `defensible` omissions and
  `result: approved` is a perfectly ordinary report, and more useful than a short
  ledger. Reporting fewer omissions never makes a piece look better; it only makes
  your review look unperformed. Roughly: a piece at a third of its source has
  dropped many nameable things, so name a dozen if there are a dozen.
- `retentions` is required on every piece. Quote the passage's opening words so a
  reviser can find it. An all-`earns_place` list is a real answer and a useful one:
  it says the space is working. What is not acceptable is an empty list, which
  claims you never asked whether anything could go.
