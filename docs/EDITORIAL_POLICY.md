# Editorial policy

## Two voices

Every piece is explicitly one of:

- `faithful_edit`: the source author's work, minimally adapted for print;
- `faithful_synthesis`: a compact adaptation in the source author's voice that preserves the source's argument, evidence, qualifications, and conclusions;
- `selected_extracts`: attributed passages with editorial framing;
- `original_synthesis`: a new source-grounded article;
- `in_a_nutshell`: the magazine's own explainer, teaching one source's principles to a reader who has never met the topic (`prompts/in-a-nutshell.md`);
- `original_editorial`: the magazine's own voice.

The default for source articles is `faithful_edit`. The opening editorial is `original_editorial` and may be opinionated, interpretive, and stylistically distinct.

## Opening editorial contract

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
of seven A5 reader pages. `measureArticle` reports the actual opener fit and
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
against its committed extraction claim by claim for invented claims, dropped
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

Editor additions must be visibly labeled, and the magazine does not print editorial apparatus inside an article. Editor text belongs in the furniture around a piece: the opening editorial, a standfirst, a figure caption, a section of its own. It does not belong in labeled notes interrupting the prose. A note is how a piece keeps a defect while appearing to answer one, and it puts the editor's voice where the reader came for the author's. Where a reprint lacks context the original page supplied, restore the referent inside the author's own sentence if the extraction supports it, or leave it alone.

## Source extractions and the evidence review

Each source revision is represented by immutable artifacts for its submitted
lead, durable raw evidence bundle, faithful extraction, media, metadata, and
human source decision. An extraction reproduces the source's substantive text
in source order with no summarization, editorial voice, or invented headings.
Interface chrome and navigation may be omitted. A repository extraction covers
each declared source file in stable order with visible file boundaries.

The artifact graph, not a mutable manifest pin, binds an article to the exact
source revisions it uses. Every source-backed article receives all of its
assigned extraction artifact IDs. The source-aware evidence reviewer receives
those same artifacts and the exact manuscript revision. Its finding or approval
is an immutable judgment artifact whose parents name every input it audited.

Changing a source, extraction, assignment, manuscript, prompt, content mode, or
attribution creates a new artifact and successor work. The earlier judgment
remains in history but cannot approve the new input graph. Edition review,
translation, render, and release consume only current approving decisions.

## Exact source code

Whether prose represents its sources is a source-aware editorial judgment.
Source code has a narrower rule: every fenced code block in a manuscript must
be a contiguous exact run from one of that article's assigned extraction
artifacts. Preserve indentation, line breaks, and characters. If the block
cannot be reproduced exactly, drop it whole. A contract failure names the
manuscript, block, and source revision and cannot be converted into approval by
the worker that produced the manuscript.

## Translation editions

English is the source edition. A Spanish edition is a faithful translation of
the already edited English magazine, not a second opportunity to summarize,
expand, strengthen, or soften the source. It preserves paragraph order,
headings, examples, qualifications, links, code, and attribution. Every
translation offer names the exact current English artifact ID; a changed
English revision makes the prior translation historical rather than current.

Spanish uses educated castellano with restrained Argentine preferences and no
slang. Spain Spanish is the default fallback. Generic Latin American, Mexican,
Caribbean, and other unrelated regional variants are excluded from the house
style. Both languages obey the same editorial and seven-page article budgets;
the editorial's one page must hold in Spanish too, which makes compression part
of translation rather than an afterthought. The engine creates translation,
measurement, render, and preflight artifacts for every configured language
before assembly.

## Rights and distribution

The workspace defaults to `private`. Complete third-party captures are retained
as immutable raw-evidence artifacts so link loss cannot erase the editorial
evidence. A checksum may protect a captured bundle at that integrity boundary,
but it never identifies workflow state. The repository must remain private while
those captures lack a public redistribution basis; credentials and browser-session
data are never part of a bundle.

Rights status is explicit: `unknown`, `private_reference`, `licensed`, `permission`, `public_domain`, or `author_owned`. Public packaging of a faithful reprint is blocked unless its status permits republication. The workflow records and surfaces rights decisions; it does not invent them.
