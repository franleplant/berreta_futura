# Editorial policy

## Two voices

Every piece is explicitly one of:

- `faithful_edit`: the source author's work, minimally adapted for print;
- `faithful_synthesis`: a compact adaptation in the source author's voice that preserves the source's argument, evidence, qualifications, and conclusions;
- `selected_extracts`: attributed passages with editorial framing;
- `original_synthesis`: a new source-grounded article;
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

Every rendered source article, including its title and credit, has a hard maximum of seven A5 reader pages. The deterministic renderer measures the real pagination and refuses an over-budget build.

The opening editorial must declare a non-empty title in its frontmatter. Its label, title, and byline are rendered on the opener and its title appears in the contents. The current standard is that the complete editorial fits a single A5 reader page: the editorial is the reader's front door, and a door that turns is not one. The budget is per-edition — `format.max_editorial_pages` in the edition manifest — because edition 001 shipped a two-page editorial and its frozen artifact must keep rebuilding; two A5 pages remain the publication's hard ceiling, which no edition may raise. Editions from 003 on declare `max_editorial_pages: 1`; editions 001 and 002 keep the older `2`. The renderer measures the real span in every language and refuses an over-budget or untitled build.

An over-budget `faithful_edit` is converted to `faithful_synthesis`. The synthesis must retain the source's central argument, important evidence and examples, uncertainty, counterarguments, and conclusion. It must not introduce a new thesis or flatten disagreement into generic summary language. The byline and mode label provide attribution and disclose that the text is condensed rather than verbatim.

Synthesis prose stays in the source's grammatical person and point of view. If the source author speaks in the first person, the synthesis does too; if the source is impersonal or already uses third person, preserve that choice. Do not wrap adapted prose in magazine-narrator scaffolding such as “Narayanan argues” or “Joshi explains.” Exact source wording may remain unchanged. Prefer retained passages and light edits, and summarize only where length requires it.

Every synthesis maps the complete substantive source into edited ledger entries, reports source and output word counts, and passes manuscript-integrity validation. Short articles remain `faithful_edit`; synthesis is a length remedy, not the default editorial voice.

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

Editor additions must be visibly labeled as an introduction, editor's note, annotation, caption, sidebar, or afterword.

## Source extractions and the evidence review

`library/sources/<source-id>/extracted.md` is the canonical faithful
extraction of a source: its substantive text reproduced verbatim from one
committed raw bundle, in source order, with no summarization, no editorial
voice, and no invented headings. Interface chrome and navigation may be
omitted, and the frontmatter must name the source id, the raw bundle the text
was transcribed from, and the extraction method. For repository captures the
extraction covers each documentation file in a stable, declared order with
visible file boundaries.

The extraction body is everything after the frontmatter's closing `---` line,
and `source_body_sha256` in a fidelity ledger is the SHA-256 of the UTF-8
bytes of exactly that body. Extraction files are byte-exact: LF newlines only,
no BOM — a carriage return anywhere in the file fails validation rather than
being silently normalized. A ledger over one source declares a single digest;
a ledger synthesizing several sources declares a mapping from source id to
digest. Validation fails whenever a pinned hash does not match the committed
extraction. Every source of the open (unreleased) edition must carry an
extraction and a matching pin before the edition can validate, and each open
edition ledger's `source_ids` must equal its article's `source_ids` in
`edition.yaml` exactly, so neither declaration can cover a source the other
omits. Editions released before extractions existed keep their recorded pins
unverified (and their recorded coverage as it was).

The evidence review (`prompts/evidence-review.md`) is recorded with
`mag review record --kind evidence` to
`editions/<edition-id>/reviews/evidence.yaml`. The record binds the reviewer's
decision to the exact manuscript, ledger, and extraction bytes audited — for
each source both the extraction body and the whole `extracted.md` file,
provenance frontmatter included, across every source the article or its ledger
declares; any later change to those inputs makes the decision stale, and
`mag release` refuses a missing, stale, or changes-required evidence review.

## Fidelity report

Each faithful article reports:

- substantive source word count;
- retained source words;
- words classified as boilerplate;
- words removed through substantive cuts;
- modified sentences;
- reordered paragraphs;
- unlabeled additions, which must be zero;
- labeled editor notes.

The review artifact includes a paragraph-level source/manuscript diff and a reason for every substantive deletion or modification.

## Translation editions

English is the source edition. A Spanish edition is a faithful translation of
the already edited English magazine, not a second opportunity to summarize,
expand, strengthen, or soften the source. It preserves paragraph order,
headings, examples, qualifications, links, code, and attribution. The compiler
pins every translated manuscript to the SHA-256 of its English counterpart and
rejects translations whose ordered Markdown block structure diverges.

Spanish uses educated castellano with restrained Argentine preferences and no
slang. Spain Spanish is the default fallback. Generic Latin American, Mexican,
Caribbean, and other unrelated regional variants are excluded from the house
style. Both languages obey the same editorial and seven-page article budgets --
the editorial's one page has to hold in Spanish too, which is what makes
compression part of the translation rather than an afterthought -- and generate
equivalent reader, home-booklet, and preflight packages.

## Rights and distribution

The workspace defaults to `private`. Complete third-party captures are committed in source-local, content-addressed raw bundles so link loss cannot erase the editorial evidence. The repository must remain private while those captures lack a public redistribution basis; credentials and browser-session data are never part of a bundle.

Rights status is explicit: `unknown`, `private_reference`, `licensed`, `permission`, `public_domain`, or `author_owned`. Public packaging of a faithful reprint is blocked unless its status permits republication. The workflow records and surfaces rights decisions; it does not invent them.
