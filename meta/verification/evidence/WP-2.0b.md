# WP-2.0b parity render mode and page sets

## Base

`443aaa8` (verify(cover): WP-5.4a rework accepted).

## Commands

The 010 run directory is untracked and must be copied into any worktree first:

    cp -R <repo>/editions/010/run-2026-09-13T01-34-51 editions/010/

1. Oracle-only, which renders the weasyprint leg and compares it against itself:

       mag parity 010 --run editions/010/run-2026-09-13T01-34-51 --oracle-only

2. Both legs, with the typst leg stubbed until WP-2.2a:

       mag parity 010 --run editions/010/run-2026-09-13T01-34-51

3. Scoring one page set:

       mag parity 010 --run editions/010/run-2026-09-13T01-34-51 --oracle-only --set body

4. Staleness guard, demonstrated by seeding a digest that cannot match and
   restoring afterwards. `baseline.json` is a verifier-owned file, so this is a
   demonstration in the working tree, never a committed change:

       cp meta/verification/baseline.json /tmp/baseline_backup.json
       uv run python -c "import json;p='meta/verification/baseline.json';d=json.load(open(p));d['staged_input_digest']='0'*64;json.dump(d,open(p,'w'),indent=2)"
       mag parity 010 --run editions/010/run-2026-09-13T01-34-51 --oracle-only --set body ; echo "exit=$?"
       cp /tmp/baseline_backup.json meta/verification/baseline.json

5. Shape compatibility with the accepted comparator WPs:

       mag parity 010 --pre-rendered <render-A> <render-B>

## Tool versions

rustc 1.96.0; poppler 25.08.0 and the lopdf-0.45.0 tracer, both asserted at
startup from `parity.yaml tools:`; python 3.12.11 via `uv run python`.

## Metrics

All figures below are OBSERVATIONS of edition 010 as it stands today, not
thresholds. No pass condition in this WP compares against any of them
(protocol rule 9); the page sets are recomputed from the oracle leg's manifest
on every run.

Page sets derived from `en/edition-manifest.json`:

| set | size today | derivation |
|---|---|---|
| furniture | 54 | every page in the compared domain |
| openers | 9 | the set of `layout.toc` values |
| placement | 11 | `layout.figures[*].page` plus, for each printed `layout.tail_arts` entry, `layout.toc[article] + layout.article_pages[article] - 1` |
| body | 34 | furniture minus openers minus placement |
| code | 0 | first lines of staged fenced runs located in the oracle leg's page text |

The arithmetic closes: 54 = 34 + 9 + 11, so openers and placement are disjoint
on this edition and body is exactly the remainder.

Staged-input digest for the run above:
`ac856f9f4b827d5eeaa54039c0c56f581c628a41b9262115d16dd14e4d10661a`. It is
computed from the oracle leg's own `request.json`, hashing each row's
`targetPath` together with the content of its `sourcePath`, sorted. It
deliberately ignores `sourcePath` itself, which is absolute and differs between
checkouts (WP-2.0a's verifier measured 48 such leaves).

Oracle-only run, all clauses over the interior domain: page_count pass (56 vs
56), boxes pass, text pass, colour pass, navigation pass, Tier G max dx and dy
0.000 pt with zero lines beyond G1 or G2, Tier E display list pass, Tier E
glyph positions pass over 68,530 glyphs in 1,501 shows with zero violations,
Tier V dimensions pass with max channel delta 0. Tier E raster remains
`not_evaluated` naming WP-0.2d, which is correct: WP-0.2f proved the raster
guard unreachable and revision 15 withdrew it.

Full run wall-clock is dominated by the render; the comparison itself is the
~87 s WP-0.2i measured.

## Verdicts

- Oracle-only, run twice on the same inputs:
  `11a9c0a8f256a0de6a99df9d98cfe8fe1022662bfd11d271dd9b54edcc7b625b` both times,
  so the verdict stays byte-deterministic in the new mode.
- `--pre-rendered` verdicts keep the exact key set they had before this WP
  (`edition, mode, inputs, domain, tier_s, tier_g, tier_v, tier_e`). Every field
  this WP adds carries `#[serde(skip_serializing_if = "Option::is_none")]`, so a
  pre-rendered verdict serialises byte-identically to the accepted comparator
  WPs' recordings and their digests remain reproducible at this commit. This was
  deliberate: adding unconditional fields would have silently invalidated the
  digests recorded in WP-0.2a through WP-0.2i's evidence.
- Proof rather than assertion, by re-running WP-0.2i's own comparison at this
  commit against the same two render trees:
  A-vs-A `0e21644ee602ff8a78fc6ac20289c8032c5ba5c4905f8327668a436784b189e0` and
  A-vs-B `6e932ea43678b91add20a13847e633555e2a3a8b19ef159e86fc0cc2b6015836`,
  both byte-identical to the values WP-0.2i recorded.

## Residuals

**Staging is verified rather than constructed.** The plan asks for one staged
copy feeding both legs. `render::run` stages internally on each invocation and
`mag/src/render.rs` is outside this WP's Owns, so the two legs are staged twice
and the run asserts the staged-input digest is identical across them, failing
loud with both digests if content moved between renders. Same bytes in is
therefore proven per run instead of guaranteed by construction. Collapsing the
two stagings into one needs a change to `render.rs` and belongs to whichever WP
owns that file next.

**A failed engine leg exits nonzero.** The first implementation exited 0 when
the typst leg failed, because every evaluated clause passed on the oracle leg
compared against itself. That is a green result for a comparison that did not
happen, which protocol rule 10 forbids, so `all_evaluated_pass` now requires
`typst_leg` to be absent. The clean report the plan asks for means a legible
message rather than a crash, not a success code.

**The `code` rule is non-discriminating on this corpus** (protocol rule 10).
Edition 010 carries no fenced code blocks and no extracts, so the set is empty
and the rule proves nothing today. It is implemented rather than stubbed: staged
manuscripts are scanned for fenced runs and each run's first line is located in
the oracle leg's normalised page text. WP-3.3 gates on its own fixture edition.

**The `openers` rule reaches article openers only.** `layout.toc` maps an
article id to its opener page; the contents page itself is not a manifest field,
so it is currently scored under `body`. Recorded here rather than implied, since
a set that silently omits a page class is the shape rule 10 exists to surface.

**CLI flags in `main.rs` are an orchestrator grant**, the same shape WP-0.2a
received for the original `parity` subcommand registration: `--run`,
`--oracle-only` and `--set` are registered on the existing `Cmd::Parity` variant
and nothing else in that file changed except the test module described below.

**Scope addition: the text seam is exported.** `mag/src/parity.rs` declared
`mod display` and `mod streams` privately, so WP-0.2h's `display::trace_elements`,
built specifically as the critic's text path, was unreachable from
`mag/src/critic/`, and WP-5.3b was blocked on it. This WP adds `pub(crate) use`
re-exports of `trace_elements`, `Element`, `Color` and `Face` (as `TextFace`),
plus a `text_font_map` helper. The navigation path is not exported: `display::extract`
keeps its previous reach, which is the point of the seam.

The re-exports carry `#[allow(unused_imports)]` and `text_font_map` carries
`#[allow(dead_code)]` because their consumer, WP-5.3b's critic text source, does
not exist yet. This follows the precedent set when `mod model` carried
`#[allow(dead_code)]` until its consumers landed; both should be removed when
WP-5.3b lands.

**Why the seam's gap was invisible until now, worth recording as method.**
WP-0.2h demonstrated `trace_elements` through a `#[path]` test include, which
bypasses module privacy entirely. The demonstration passed, its verification
confirmed it, and the seam was still unusable from the module it was built for.
The mechanism that proved the feature was the one mechanism that routes around
the defect.

Proving the export therefore could not use `mag/tests/`: the crate has **no
library target**, so an integration test cannot import from the binary at all,
which is precisely why `#[path]` includes are used throughout. The consumer test
lives in `mag/src/main.rs` under `#[cfg(test)]`, outside the `parity` module, and
imports the items normally. A `#[path]` include cannot fake that.

**`text_font_map` is repo-root relative.** It reads `meta/verification/parity.yaml`
through `SPEC_PATH`, so it resolves only when the process runs from the repo
root, which is how `mag parity` is invoked. The consumer test therefore builds an
empty font map instead of calling it. A future critic consumer running from a
different directory will hit the same thing.

## Status

done
