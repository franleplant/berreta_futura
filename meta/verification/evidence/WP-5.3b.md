# WP-5.3b critic rules

## Base

df1398d (plan revision 25). Worktree `/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp53b`.

## Status

blocked. Two independent blockers, one structural and one of scope. The text
source this WP depends on is built and measured; it cannot be landed as a
consumable module, and the remaining port is larger than one WP.

## Blocker 1: the tracer seam is unreachable from outside the comparator

WP-0.2h built `display::trace_elements` as the text path for this WP, and it
works. It cannot be imported.

`mag/src/parity.rs:1-6` declares every submodule privately:

    mod display;
    mod geometry;
    mod raster;
    mod report;
    mod streams;
    mod text;

There is no `pub use` re-export anywhere in `mag/src/parity.rs` or
`mag/src/parity/*.rs` (checked). So `crate::parity::display::trace_elements`
and the `Element` and `Face` types it returns are private to the `parity`
module tree, and a `mag/src/critic/text.rs` that imports them fails to
compile:

    error[E0603]: module `streams` is private
     --> src/critic/text.rs:7:20
    error[E0603]: module `display` is private
     --> src/critic/text.rs:6:20

The fix is one line (`pub mod display; pub mod streams;`, or a narrower
`pub use`), and it is in `mag/src/parity.rs`, which this WP may not touch:
the Phase 5 preamble says no Phase 5 WP touches comparator territory, and
WP-2.0b holds that file right now. It needs an Owns grant or a WP-0.2h
follow-up.

Note the seam is reachable from a TEST via `#[path]` include, which is how
the measurement below was taken. That is why the privacy did not surface
until a non-test consumer existed.

## Blocker 2: scope

The oracle is the critic's decisions on 010, and those decisions span the
whole module rather than a subset. Measured surface of
`src/magazine/render_critic.py` (1596 lines):

| region | lines | feeds decisions |
|---|---|---|
| check functions (`_imposition_checks` .. `_contents_issues`) | 133-550 | yes, 31 issue sites |
| `inspect_render` orchestration | 551-815 | yes |
| page/raster inspection helpers | 865-1380 | yes |
| contact sheets, review crops | 1384-1596 | no (WP-5.6 needs them) |

31 issue call sites emitting 31 distinct codes. Producing a comparable
decision set needs all of: rasterising three PDFs at 144 dpi, `_inspect_page`
with PIL-exact grayscale/point/histogram/getbbox/getextrema, void geometry
(`_annotate_void_geometry`, `_largest_empty_rectangle`), tail bands, opener
offset colour detection, opener crop fidelity (MAE), and the five check
functions. A partial port yields a partial decision set, which cannot be
compared against Python's full one, so there is no smaller honest unit that
still satisfies the stated oracle.

Recommended split, along the seam the dependencies already create:

- **WP-5.3b-i text source**: `mag/src/critic/text.rs`. Built and measured
  below; needs only blocker 1 cleared. It is the dependency of five of the
  eleven issue sites and of WP-5.3c.
- **WP-5.3b-ii page inspection**: rasterisation, `_inspect_page`, void
  geometry, tail bands. Needs PIL-exact grayscale and `getbbox`, neither of
  which `metrics.rs` currently exposes (it has `decode_rgb`, `thumbnail`
  (LANCZOS), `round_half_even`, `round_places`, `ordered_map`).
- **WP-5.3b-iii the checks**: the five check functions and `inspect_render`,
  plus the opener offset and crop-fidelity inspections.

## The text source, built and measured

Implementation held at
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp53b-heldback/text.rs`
(110 lines) rather than committed, because a module that cannot compile in
the tree would break every other agent's pre-commit hook. Precedent: WP-5.4
held back a red test for the same reason and revision 25's rule 5b blesses
it.

Line reconstruction: group `Element::Text` shows by quantised device y within
100 (0.01 pt units, i.e. 1 pt), order by x, and join adjacent shows on a line
with a space when the x gap exceeds 0.25 of the larger font size, else with
nothing. Show width is estimated from the WP-0.2i per-glyph offsets as
`(last.x - first.x) * n / (n - 1)`.

`body_text_lines` uses `py_strip` from `model::shared` (WP-5.1e's lift) and
`char::is_lowercase`, matching Python's `line.strip()` and
`any(c.islower() for c in line)`.

## Metrics

Re-measured against the CURRENT post-WP-0.2i, post-WP-0.2h tracer, per rule 9;
WP-5.3d's figures are not inherited. 56 pages of
`editions/010/render-2026-09-14T01-47-59/en/reader.pdf`.

| field | tracer vs pypdf | discriminating? |
|---|---|---|
| text-emptiness | **56 of 56** | DISCRIMINATING. pypdf partitions 7 empty (pages 2, 10, 30, 35, 45, 54, 55) against 49 non-empty, and the tracer reproduces that exact partition. |
| `body_text_lines` | 49 of 56 | 7 differences, one cause (below). |
| `text_characters` | 16 of 56 | feeds NO issue site (verified: `text_characters` appears only at its definition). |

Better than WP-5.3d measured, on two counts. Text-emptiness is 56 of 56
rather than 54 of 54, because WP-0.2h's standard-14 decode gained the two
cover pages WP-5.3d could not read at all. `text_characters` agreement rose
from 9 of 56 (empty-string join) to 16 of 56 (geometric join).

`standalone_punctuation_lines` is not tabulated because it is zero on every
page under both implementations: an EMPTY-SET agreement, per rule 10. It
proves the tracer invents no such lines and nothing about whether it would
produce the same ones. WP-5.3c's fault coverage for that field is the only
evidence there will be.

### The seven `body_text_lines` differences are one cause, confirmed not inherited

Pages 4, 11, 31, 36, 40, 46, 50, each with the tracer counting exactly ONE
MORE line than pypdf. All seven are article opener pages. Mechanism confirmed
directly on two of them by reading pypdf's own output:

- page 4: `'Government Rails Site HitHours After CVE Patch'` — the missing
  space between `Hit` and `Hours` is pypdf merging a two-line headline.
- page 36: `'The third era of AI softwaredevelopment'` — `software` and
  `development` merged the same way.

The tracer keeps them as two shows 28.8 pt apart in y, which is correct. This
reproduces WP-5.3d's finding on the current tracer and extends it with a
second confirmed page.

### The join rule does not discriminate on this corpus

184 of 1263 reconstructed lines carry more than one show. Switching the
separator between empty-string and the geometric rule changes
`text_characters` (9 to 16 of 56) and changes NEITHER text-emptiness nor
`body_text_lines`: the seven differences are identical under both rules. So
on edition 010 the join rule is not discriminating for any field that feeds a
decision, and the geometric rule is chosen because it is principled rather
than because 010 can tell the difference. Recorded per rule 10.

The mirror failure WP-5.3d warned of (a word split across adjacent shows
gaining a spurious space) is not reachable through the geometric rule as
written, since a split word has a gap far below 0.25 of the font size; it was
reachable through the naive space-always join.

## Commands

    # pypdf reference
    uv run python -c "
    import json
    from pypdf import PdfReader
    r = PdfReader('editions/010/render-2026-09-14T01-47-59/en/reader.pdf')
    rows = []
    for i, p in enumerate(r.pages, 1):
        t = p.extract_text() or ''
        lines = [l.strip() for l in t.splitlines()]
        body = sum(1 for l in lines if l and any(c.islower() for c in l))
        rows.append({'page': i, 'lines': len(t.splitlines()), 'body': body,
                     'chars': len(t.strip()), 'empty': not t.strip()})
    print(json.dumps({'pages': len(r.pages), 'rows': rows}))"

    # tracer side: restore the probe, which includes the private modules by path
    cp /Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp53b-heldback/probe_text.rs \
       mag/tests/probe_text.rs
    cargo test --manifest-path mag/Cargo.toml --test probe_text probe -- --exact --nocapture

    # headline-merge mechanism
    uv run python -c "
    from pypdf import PdfReader
    r=PdfReader('editions/010/render-2026-09-14T01-47-59/en/reader.pdf')
    for pg in (4,36):
        t=r.pages[pg-1].extract_text() or ''
        for l in [l.strip() for l in t.splitlines() if l.strip()][:5]:
            print(pg, repr(l[:70]))"

The probe resolves `normalization.font_name_map.entries` from
`meta/verification/parity.yaml` and rewrites each `file` against the worktree
root; the tracer fails loud without it (`font Magazine-Sans-Medium has no
vendored face in font_name_map`).

## Tool versions

rustc 1.96.0, lopdf 0.45.0, `uv run python` 3.12.11 (pypdf 6.14.2). Note this
machine also has system python3 3.9.6 on Unicode 13.0.0; all Python here is
`uv run python`.

## Verdicts

No parity verdicts produced: this WP does not run `mag parity` (Phase 5
preamble forbids it for oracle tests) and landed no code.

## Residuals

- Blocker 1 needs a one-line visibility change in `mag/src/parity.rs`. The
  same privacy will block WP-5.5a and WP-5.3c if either consumes the tracer.
- `metrics.rs` does not expose PIL-exact grayscale or `getbbox`; WP-5.3b-ii
  needs both and they are `render_critic.py`'s own raster helpers, which this
  WP was told it owns.
- The Unicode pinning rule is satisfied for `body_text_lines` via
  `py_strip` plus `char::is_lowercase`. `is_lowercase` is NOT pinned to
  Python's tables; the 55 divergent codepoints are all uppercase-mapping
  differences plus U+1C89 lowercase, so a page containing U+1C89 could in
  principle differ. Unmeasured, and it should be either pinned or swept
  before WP-5.3b-i is accepted.
- WP-5.3c still owes fault coverage on all five text-derived fields
  (`text_order_matches`, `blank`, `ink_free`,
  `standalone_punctuation_lines`, `body_text_lines`), and the near-threshold
  fixture for `pages[39].largest_void.height_points` at 96.0 against the 96.0
  `>=` boundary. `standalone_punctuation_lines` is the one where fault
  coverage is the only evidence, since its agreement here is empty-set.
