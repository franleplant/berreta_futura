# Editorial policy

## Two voices

Every piece is explicitly one of:

- `verbatim`: the source author's work printed unchanged, when it fits the
  verbatim page budget; the pipeline copies the captured text with no model
  call, stripping only capture chrome (the captured title line, byline line,
  and image references, which the figure system owns). A verbatim article's
  title is the captured source title, unchanged; the loader refuses retitles.
  New plan rows auto-promote to verbatim when the captured text fits seven
  reader pages; `--mode` at capture time or editing plan.yaml overrides the
  auto decision in either direction;
- `faithful_edit`: the source author's work, minimally adapted for print;
- `faithful_synthesis`: a compact adaptation in the source author's voice that preserves the source's argument, evidence, qualifications, and conclusions;
- `selected_extracts`: attributed passages with editorial framing;
- `original_synthesis`: a new source-grounded article;
- `in_a_nutshell`: the magazine's own explainer, teaching one source's principles to a reader who has never met the topic (`prompts/in-a-nutshell.md`);
- `original_editorial`: the magazine's own voice.

The default for source articles is `faithful_edit`. The opening editorial is `original_editorial` and may be opinionated, interpretive, and stylistically distinct.

## Opening editorial contract

Discontinued: editions from 010 on carry no opening editorial. The contract
below governs editions 001-009, whose editorials remain in their runs.


The opening editorial develops a distinct unifying idea, set of ideas, or
emergent narrative across the edition. Its value lies in the new argument the
editors discover between the sources, not in recounting what each source says.
It must not summarize the articles one by one, tour them in sequence, or act as
a prose table of contents. It may name one or two sources when the argument
needs their evidence, with precise attribution.

Draft and edit every opening editorial with the Orwell-based method in
`docs/WRITING_RULES.md`. The method sharpens the magazine's idea; it does not
replace editorial judgment or flatten necessary technical language. The
publication-ready manuscript keeps a visible title, byline, and label that
identifies it as original editor text. AI may propose the draft, but a human
must approve the argument and final prose.

## Print-length budget

Every rendered source article, including its title and credit, has a hard maximum
of seven A5 reader pages. A `verbatim` article has a hard maximum of ten A5
reader pages instead: unchanged author text is the one case worth more room,
and a source that cannot fit ten pages verbatim is condensed under the
rules below rather than trimmed silently. `measureArticle` reports the actual opener fit and
page count from the production layout interface; character counts and
hand-reproduced wrapping are not substitutes.

The opening editorial must have a visible title, label, and byline, and must fit
on one A5 reader page in every configured language. The editorial is the
reader's front door, not a multi-page introduction. Historical rendered editions
remain immutable records; their old layout settings do not relax this policy for
new work.

An over-budget `faithful_edit` is converted to `faithful_synthesis`. The synthesis must retain the source's central argument, important evidence and examples, uncertainty, counterarguments, and conclusion. It must not introduce a new thesis or flatten disagreement into generic summary language. The byline and mode label provide attribution and disclose that the text is condensed rather than verbatim.

Synthesis prose stays in the source's grammatical person and point of view. If the source author speaks in the first person, the synthesis does too; if the source is impersonal or already uses third person, preserve that choice. Do not wrap adapted prose in magazine-narrator scaffolding such as “Narayanan argues” or “Joshi explains.” Exact source wording may remain unchanged. Prefer retained passages and light edits, and summarize only where length requires it.

A synthesis is verified by reading, not by bookkeeping: read the manuscript
against its captured source claim by claim for invented claims, dropped
qualifications, reversed claim strength, and missing counterarguments.
Deciding what a shorter piece must lose is the writer's job and is governed
by this cut order: repeated examples first, a claim's supporting evidence
before the claim, and qualifications and the source's own conclusions last
and almost never. Short articles remain `faithful_edit`; synthesis is a
length remedy, not the default editorial voice.

## Automatically permitted faithful edits

- remove navigation, advertisements, subscription prompts, and duplicated boilerplate;
- normalize whitespace, typography, headings, lists, links, and footnotes;
- repair obvious extraction and OCR errors;
- adapt figures and captions without changing their meaning;
- remove purely promotional material unrelated to the argument.

## Review-required edits

- changing source wording;
- removing substantive paragraphs;
- reordering sections;
- combining multiple sources into continuous prose;
- adding transitions in the source author's apparent voice;
- changing the source's tone, uncertainty, or claim strength.

Editor additions must be visibly labeled, and the magazine does not print editorial apparatus inside an article. Editor text belongs in the furniture around a piece: the opening editorial, a standfirst, a figure caption, a section of its own. It does not belong in labeled notes interrupting the prose. A note is how a piece keeps a defect while appearing to answer one, and it puts the editor's voice where the reader came for the author's. Where a piece lacks context the original page supplied, restore the referent inside the author's own sentence if the captured source supports it, or leave it alone.

## Captured sources and the evidence review

A captured source is ``library/sources/<id>/``: ``article.md`` with the
source's substantive text in source order, its images under ``media/``, and a
small ``record.yaml`` naming title, author, URL, and dates. The capture keeps
the author's wording, headings, and structure; interface chrome and navigation
may be omitted. No summarization, editorial voice, or invented headings.

The source-aware evidence reviewer reads the manuscript against the captured
``article.md`` of every assigned source. Rewriting an article means re-reading
it against its sources; an earlier review does not carry over.

## Exact source code

Whether prose represents its sources is a source-aware editorial judgment.
Source code has a narrower rule: every fenced code block in a manuscript must
be a contiguous exact run from one of that article's captured sources.
Preserve indentation, line breaks, and characters. If the block cannot be
reproduced exactly, drop it whole.

## Translation editions

English is the source edition. A Spanish edition is a faithful translation of
the already edited English magazine, not a second opportunity to summarize,
expand, strengthen, or soften the source. It preserves paragraph order,
headings, examples, qualifications, links, code, and attribution. A changed
English article means its translation is redone, not patched.

Spanish uses educated castellano with restrained Argentine preferences and no
slang. Spain Spanish is the default fallback. Generic Latin American, Mexican,
Caribbean, and other unrelated regional variants are excluded from the house
style. Both languages obey the same editorial and seven-page article budgets;
the editorial's one page must hold in Spanish too, which makes compression part
of translation rather than an afterthought.
