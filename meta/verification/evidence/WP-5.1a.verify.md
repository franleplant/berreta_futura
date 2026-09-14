# WP-5.1a verification (document model port)

## Verdict

**ACCEPTED.**

This replaces an earlier rejection. The first submission (worker commit
`cc39664`, verify commit `77f6f77`) was REJECTED for a real divergence:
`document_structure.py` collapses whitespace inside each nested container and
then concatenates, so a container contributes an already-stripped string,
while the Rust `inline_visible` flattened every descendant raw into one buffer
and collapsed once at the end. `Alpha[ beta ](url)gamma.` yielded
`Alphabetagamma.` in Python and `Alpha beta gamma.` in Rust. It was masked
because neither edition 010 nor any fixture placed a space-padded container
against non-space text.

The rework is commit `7d79b9d`. Every claim in its evidence reproduced, and
the fix is correct on eight further shapes the worker did not cover.

## Base

- Rework commit verified: `7d79b9d` (parent `5f16548`)
- Rejected submission: `cc39664`, rejecting verify `77f6f77`
- Worktree: `7d79b9d` detached, run directory copied in

## Owns check

`7d79b9d` touches exactly four paths, all owned:

- `mag/src/model/doc.rs`
- `mag/tests/model_doc_fixtures/padded_containers.md`
- `mag/tests/model_doc_expected.json`
- `meta/verification/evidence/WP-5.1a.md`

It does NOT touch `mag/src/model/mod.rs` or the Cargo files, which a
concurrent WP-5.1b agent held, and touches no `*.verify.md` and no
`baseline.json`. Checked against the commit itself rather than a range,
because other agents' commits landed around it.

## Commands replayed

Repository gate in the worktree: `cargo fmt --check` clean,
`cargo clippy --all-targets -- -D warnings` clean, `cargo test` green
(3 model_doc tests, no_comments, parity_faults 20.75 s).

Edition 010 oracle, the replay that matters, with
`MAG_MODEL_ARTICLES` and `MAG_MODEL_ORACLE` set (without them the edition
test passes vacuously by early return):

- Python dump regenerated: sha256
  `e17ca71cffabe08b08820dd268863dcbda04615a871e5feaf52c34ca907cda50`,
  208052 bytes, matching the evidence exactly.
- Rust projection compared against it: `edition_manuscripts_match_the_python_projection`
  passed.

Committed fixture expectation regenerated from the Python oracle and diffed:
identical, sha256
`4a5845241374af7ca953a326dad01d40789463783cf1ca0771319723ba1066d0`,
matching the evidence.

Settable codepoint intersection regenerated and diffed: identical, 503
codepoints.

Negative check, run with my own mutation rather than the worker's (a
different article, `dario-amodei-we-must-pace-the-frontier`, and an arbitrary
substring replacement rather than their word swap): the edition oracle
FAILED as required, so it is not vacuous.

## The discriminating proof, reproduced independently

With `mag/src/model/doc.rs` restored to its `cc39664` content, the fixture
test fails on exactly `padded_containers` and no other fixture, with 7 of its
8 blocks differing and `Upsilon phi chi.` identical in both, exactly as the
evidence claims. Observed pairs include `Alpha beta gamma.` against
`Alphabetagamma.`, `Delta( epsilon )zeta.` against `Delta(epsilon)zeta.`, and
`Pi rho sigma tau.` against `Pirho sigmatau.`. Restored, green again.

## Critique: eight shapes the worker did not cover

I built an independent fixture of eight constructs chosen for positions the
committed fixture leaves untested, generated the Python projection for each,
regenerated the expectation, and ran the Rust side against it. All eight
agree after the fix, and all eight diverge before it, so each is a genuine
discriminator rather than a shape that happens to pass either way:

| construct | Python and fixed Rust | pre-fix Rust |
|---|---|---|
| container as first child, `[ alpha ](u)beta.` | `alphabeta.` | `alpha beta.` |
| container as last child, `alpha[ beta ](u)` | `alphabeta` | `alpha beta` |
| whitespace-only container, `Alpha[ ](u)Beta.` | `AlphaBeta.` | `Alpha Beta.` |
| container adjacent to inline code | `Alphacodebetagamma.` | `Alphacode beta gamma.` |
| depth-3 nesting, emphasis > link > emphasis | `Alpha(beta gamma delta)omega` | `Alpha( beta gamma delta )omega` |
| hard line break inside a container | `Deltaalpha betaepsilon.` | `Delta alpha beta epsilon.` |
| container inside a heading | `Headingwithcontainer` | `Heading with container` |
| container inside a list item | `itempaddedtail` | `item padded tail` |

These answer the specific questions the rejection raised. The recursion is
faithful at depth three, not merely at depth one: the inner emphasis collapses
within the link, the link is edge-stripped, and the parent concatenates the
result bare. Edge-stripping applies when the container is the first child and
when it is the last. A `LineBreak` inside a container still contributes its
single space, which is then stripped at that container's edge and not
reintroduced by the parent, which is why the hard-break case yields
`Deltaalpha betaepsilon.` with an internal space but none at the seams. A
container whose entire content is whitespace collapses to the empty string.
Heading and list-item block contexts behave as paragraph context does.

I read the Python rule directly to confirm the mapping: `document_structure.py`
appends `Text` and `InlineCode` values raw (:57), recurses for `Emphasis`,
`Strong` and `Link` (:59), appends one space for `LineBreak` (:61), and
applies `" ".join("".join(parts).split())` at :64, which executes at every
recursion level. There is no soft-break inline variant; any unsupported
inline raises. The port mirrors this.

The evidence's 24-construct generality sweep ran as isolated throwaway
corpora and is not replayable from the worktree, so I did not reproduce its
"13 of 24 diverge pre-fix" figure. My own eight-construct set is independent
of it and establishes the same property more directly, so the sweep figure is
recorded as unverified rather than doubted.

## Residuals confirmed recorded

Both carried-forward items are present in the evidence:

- The oracle constrains only the five projected fields. Link destinations,
  link titles, code info strings and frontmatter metadata VALUES are never
  compared, only metadata keys. WP-2.1 and WP-5.1c must not treat those as
  proven by this WP. This narrowness is exactly why the container defect
  reached verification.
- The character-count label is corrected: 65300 is the sum of visible-block
  text, while the projection itself is 65490 characters.
- The `#[allow(dead_code)]` on `mod model;` is recorded for WP-2.1 and
  WP-5.1c to remove when they consume the model.

One observation for the orchestrator, outside this WP: edition 010 contains
no padded-container shape, so the edition corpus alone could never have
caught this defect class. Fixtures, not the current edition, are the guard
for constructs 010 happens not to use. The same reasoning applies to the
plan's other known 010 gaps.

## Status

`done`, accepted.
