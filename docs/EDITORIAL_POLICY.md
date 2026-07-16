# Editorial policy

## Two voices

Every piece is explicitly one of:

- `faithful_edit`: the source author's work, minimally adapted for print;
- `faithful_synthesis`: a compact, attributed restatement that preserves the source's argument, evidence, qualifications, and conclusions;
- `selected_extracts`: attributed passages with editorial framing;
- `original_synthesis`: a new source-grounded article;
- `original_editorial`: the magazine's own voice.

The default for source articles is `faithful_edit`. The opening editorial is `original_editorial` and may be opinionated, interpretive, and stylistically distinct.

## Print-length budget

Every rendered source article, including its title and credit, has a hard maximum of seven A5 reader pages. The deterministic renderer measures the real pagination and refuses an over-budget build.

The opening editorial must declare a non-empty title in its frontmatter. Its label, title, and byline are rendered on the opener and its title appears in the contents. The complete editorial has a hard maximum of two A5 reader pages. The renderer measures the real span and refuses an over-budget or untitled build.

An over-budget `faithful_edit` is converted to `faithful_synthesis`. The synthesis must retain the source's central argument, important evidence and examples, uncertainty, counterarguments, and conclusion. It must not introduce a new thesis or flatten disagreement into generic summary language. The credit must identify it as a synthesis rather than presenting edited prose as the source author's verbatim writing.

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

## Rights and distribution

The workspace defaults to `private`. Complete third-party captures are committed in source-local, content-addressed raw bundles so link loss cannot erase the editorial evidence. The repository must remain private while those captures lack a public redistribution basis; credentials and browser-session data are never part of a bundle.

Rights status is explicit: `unknown`, `private_reference`, `licensed`, `permission`, `public_domain`, or `author_owned`. Public packaging of a faithful reprint is blocked unless its status permits republication. The workflow records and surfaces rights decisions; it does not invent them.
