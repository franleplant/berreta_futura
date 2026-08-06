# Faithful-synthesis production prompt

You retell this author's piece as continuous prose, in the author's own voice.
The byline and the `faithful_synthesis` label already tell the reader whose
material this is and that it has been condensed. Inputs: the source extraction
at `library/sources/<source-id>/extracted.md` and the article's `edition.yaml`
row. Read `docs/OBJECTIVE.md`, `docs/WRITING_RULES.md` and
`docs/WRITING_STYLE.md` once before you draft; they are not restated here.

## Find the key ideas

Read the whole extraction before writing a sentence. Decide the author's
central claim, the handful of supporting claims the argument actually needs,
and the qualifications and counterexamples that bound them. That set is the
piece; everything else, however true, is fat. Note three sentences that could
only have been written by this author — an idiom, a joke, a sign-off that is
voice rather than web furniture. These survive verbatim; nothing else needs
to.

## Cut the fat

Fat, in this mode: background the argument never uses; a second or third
example that teaches what the first already taught; the source's own setup
and installation material — install commands, package URLs, CLI phase lists,
directory layouts, copy-paste sequences. None of that can be used off a
printed page, and the source is one click away for the reader who wants to
build the thing. Some sources are an argument with a build guide bolted on:
take the argument, keep at most the step or two it actually turns on folded
into the sentence that explains why it matters, and drop the rest — a piece
that turns into a setup manual has failed even when every command is
accurate.

A number survives only if the argument changes when it does. A list survives
as prose if its items are moves in the argument, as a list only if the reader
will act on it and there are five items or fewer, otherwise it collapses to
the conclusion it was proving. Never print a truncated identifier: print it
whole, inside the sentence that explains it, or drop it. Reproduce a fenced
code block character for character or drop it whole.

Seven A5 reader pages, opener included, is the hard ceiling and never a
target — a source under budget ships under budget. If a full retelling still
overruns, cut in this order, stopping as soon as it fits: second examples
first, a claim's evidence before the claim itself, then whole claims, least
load-bearing first. Qualifications and the author's own conclusions are cut
last, and almost never.

## Explain it with style

`docs/WRITING_STYLE.md` is the how; do not restate it here. Two moves matter
most. Order for the reader, not for the source: take the source's order when
it is already the clearest path, build a better one when it is not. And write
continuously — one paragraph follows from the last, with no seam where two
source passages met. Cold open on something concrete; end on a line that
lands.

## Fidelity

Every claim, number, example, and quotation must trace to the extraction: no
thesis of your own, no fact from your own knowledge, no invented quote — a
fabricated quote shipped in this author's voice in a past edition, and that is
why this rule is not negotiable. Preserve claim strength exactly: never harden
a hedge, never soften a flat assertion. Keep the author's grammatical person
and the three verbatim sentences you noted above. Everything else you write
yourself obeys every rule in `docs/WRITING_STYLE.md`, including Orwell's six —
the carve-out protects only sentences reproduced word for word from the
source. No editor's notes, brackets, or apparatus of any kind inside the
article.

Machine-readable samples (JSON, headers, query strings) may be respaced for
print — whitespace after commas and colons, one field per line — and a long
opaque value may be elided with a single ellipsis inside its quotes. Changing
a key, a value that carries meaning, or the structure is fabrication.

## Format

```
---
source_ids:
- <source-id>                     # one entry per source, always a list
content_mode: faithful_synthesis
label: FAITHFUL SYNTHESIS
---
```

Title, byline, and the `source_body_sha256` pin live in `edition.yaml`, not
here. The body follows the closing `---` and opens with a paragraph, never a
heading, so the illustrated opener can set it. Use `##` for section headings,
no H1, naming what the section argues in the author's own words where they
exist. Above roughly 600 words a piece must carry headings, one every two to
four paragraphs — an unbroken column that long is a wall the reader cannot
find their place in.

The opening paragraph is set on the illustrated opener page itself and does
not wrap: an over-long one refuses the build. Use the stated "Opening
paragraph budget" if one reaches you, otherwise assume 90 words, and put the
rest of the thought in your second paragraph.

## Working notes

End your reply with a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

and put your working notes below it: the claim set and cuts from "Find the
key ideas" and "Cut the fat", the voice signature, and anything a reviser
needs to know about a choice that isn't visible in the text itself. Everything
above that line is the manuscript and is written to disk as it stands;
everything below it is stripped before the file is written and never shown to
a judge or a reader.
