# WP-5.5b preflight port

## Base

`6c83bc3` (plan revision 26).

## Commands

The 010 oracle needs the untracked render tree
`editions/010/render-2026-09-14T01-49-02/en` for its four PDFs. The figure and
cover images it references are TRACKED, which is what makes the oracle
replayable: the staged copies the archived preflight.json names were written to
a temp directory that has since been cleaned, so both sides are driven over the
tracked originals instead. Every Python invocation uses `uv run python`, because
this machine carries a second interpreter on a different Unicode version.

Build the shared input spec (both implementations read the same one):

```
R=editions/010/render-2026-09-14T01-49-02/en
uv run python -c "
import json, pathlib
archived = json.load(open('$R/preflight.json'))
images = {
 'four-incidents': 'library/sources/an-alignment-assessment-of-recent-cybersecurity-415f8f1a/media/001.png',
 'agent-usage-growth': 'library/sources/the-third-era-of-ai-software-development-7395f18d/media/001.png',
 'recursive-planners': 'library/sources/towards-self-driving-codebases-3fd7b9ca/media/004.png',
}
figs = [{'figure_id': f['figure_id'], 'article_id': f['article_id'], 'page': f['page'],
         'path': str(pathlib.Path(images[f['figure_id']]).resolve()),
         'pixel_dimensions': f['pixel_dimensions'], 'box_points': f['box_points'],
         'effective_ppi': f['effective_ppi'], 'caption': f['caption'], 'credit': f['credit']}
        for f in archived['figures']]
spec = {'reader_pdf': str(pathlib.Path('$R/reader.pdf').resolve()),
        'booklet_pdf': str(pathlib.Path('$R/booklet-a4.pdf').resolve()),
        'interior_booklet_pdf': str(pathlib.Path('$R/booklet-a4-interior.pdf').resolve()),
        'cover_booklet_pdf': str(pathlib.Path('$R/booklet-a4-cover.pdf').resolve()),
        'cover_art': str(pathlib.Path('editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png').resolve()),
        'cover_art_size_points': None, 'figures': figs, 'language': 'en'}
pathlib.Path('/tmp/wp55b-spec.json').write_text(json.dumps(spec, indent=2))
"
```

Generate the Python oracle over that spec:

```
uv run python -c "
import json, pathlib, sys
sys.path.insert(0,'src')
from magazine.preflight import inspect_package
spec = json.load(open('/tmp/wp55b-spec.json'))
class P:
    def __init__(s, d):
        s.figure_id=d['figure_id']; s.article_id=d['article_id']; s.page=d['page']
        s.path=pathlib.Path(d['path']); s.pixel_dimensions=tuple(d['pixel_dimensions'])
        s.box_points=tuple(d['box_points']); s.effective_ppi=d['effective_ppi']
        s.caption=d['caption']; s.credit=d['credit']
out = inspect_package(
  pathlib.Path(spec['reader_pdf']), pathlib.Path(spec['booklet_pdf']),
  interior_booklet_pdf=pathlib.Path(spec['interior_booklet_pdf']),
  cover_booklet_pdf=pathlib.Path(spec['cover_booklet_pdf']),
  cover_art=pathlib.Path(spec['cover_art']),
  cover_art_size_points=spec['cover_art_size_points'],
  figure_placements=[P(f) for f in spec['figures']], language=spec['language'])
pathlib.Path('/tmp/wp55b-oracle.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)+chr(10))
"
```

Compare:

```
cd mag && MAG_PREFLIGHT_SPEC=/tmp/wp55b-spec.json \
          MAG_PREFLIGHT_ORACLE=/tmp/wp55b-oracle.json \
          cargo test --test preflight edition_010_matches
```

Negative check (must FAIL):

```
uv run python -c "
import json
d=json.load(open('/tmp/wp55b-oracle.json')); d['figures'][1]['effective_ppi']=517.9
json.dump(d,open('/tmp/wp55b-oracle-mutated.json','w'),indent=2)"
cd mag && MAG_PREFLIGHT_SPEC=/tmp/wp55b-spec.json \
          MAG_PREFLIGHT_ORACLE=/tmp/wp55b-oracle-mutated.json \
          cargo test --test preflight edition_010_matches
```

Fixtures and the rest: `cd mag && cargo test --test preflight`, `cargo fmt
--check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`.

## Tool versions

rustc 1.96.0, python 3.12.11, pypdf 6.14.2, pillow 12.3.0, lopdf 0.45.0.

## Metrics

**Edition 010 oracle: EQUAL.** 153 leaves, 4,018 bytes, every field matching the
Python original. Spec digest `baecd97cfc726681251a835de496748cc70fb55d6d78938f2a4c157cd3e957c0`,
oracle digest `f609ee8e78d0db49f6b816c0993f7e798a7afdd7bf2e480750ebee1ec5862002`.
The comparison normalises both sides through `serde_json::to_string_pretty`, so
it tests structure and values rather than either writer's formatting.

**The oracle is not vacuous.** Mutating one leaf (`figures[1].effective_ppi`
518.9 to 517.9) fails the test.

**Branches edition 010 cannot reach, and how each is covered.** 010 is 56 A5
pages, unencrypted, English, with three figures all above 300 ppi, none
overlapping, none needing contrast treatment, and a cover placed at the A5
default. Every branch below is therefore unreachable from it and is covered by a
fixture that builds its own PDFs with lopdf and its own PNGs with the png crate:

| branch | fixture |
|---|---|
| page count not a multiple of four | `reader_shape_branches_edition_010_cannot_reach` |
| reader pages not A5 | same |
| reader under four pages (no section pages, `expected_sheets` 0) | same |
| Spanish message table | `language_selection_covers_both_tables_and_the_fallback` |
| region suffix (`es-AR`) selecting the base table | same |
| unknown language falling back to English | same |
| cover art absent (no ppi keys at all) | `cover_art_absence_and_unreadable_paths_yield_no_measurements` |
| cover art path missing on disk | same |
| cover art with a non-raster suffix | same |
| cover meeting the 300 ppi target (no blocker) | `cover_resolution_target_decides_the_studio_blocker` |
| cover below the target (blocker raised) | same |
| placement points overridden rather than defaulted | `placement_points_default_to_a5_and_honour_an_override` |
| all eight `_box_invalid` conditions, plus a box that is not four values | `every_box_invalidity_condition_is_detected` |
| two figures overlapping on one page | `overlapping_figures_on_one_page_collide_and_neighbours_do_not` |
| figures that abut without overlapping, and figures on different pages | same |
| a figure below 300 ppi | `low_resolution_figures_raise_their_own_blocker` |
| dimensions derived from the file when the placement omits them | `effective_ppi_and_dimensions_are_derived_when_absent` |
| effective ppi computed rather than supplied | same |

**Rule 10, evidence that cannot discriminate.** Two things must be labelled:

- `result` and `studio.ready` are CONSTANT, not measurements. `studio_blockers`
  is seeded with the PDF/X-4 and bleed messages unconditionally and is never
  emptied, so `if studio_blockers` is always true: `result` is always
  `home_ready_studio_blocked` and `studio.ready` is always `false`. The `"ready"`
  branch is unreachable for any input whatsoever. `the_result_field_is_constant_because_two_blockers_are_unconditional`
  asserts this as a constant rather than pretending it is a check.
- `a_figure_that_stays_faint_after_treatment_raises_the_contrast_blocker` proves
  the contrast path runs and is analysed, but its blocker assertion is
  CONDITIONAL on the synthetic image actually remaining unresolved after
  treatment. It is a weaker fixture than the others and is marked as such rather
  than counted as full coverage of the `figure_contrast` blocker.

**f32 cannot reach this port's outputs.** lopdf parses every PDF real as f32
(the hazard WP-5.2 measured). Every parsed number here flows only into
`near(size, expected, 0.75)`, whose output is a boolean:

| value | authored | as f32 | distance to target | margin against the 0.75 pt tolerance |
|---|---|---|---|---|
| A5 width | 419.527559 | 419.5275573730469 | 4.263e-05 pt | 17,595x |
| A5 height | 595.275591 | 595.2755737304688 | 2.627e-05 pt | 28,550x |
| A4 width | 841.889764 | 841.8897705078125 | 2.949e-05 pt | 25,430x |

Page counts are integers, `is_encrypted` is a boolean, figure `box_points` come
from the caller's `RenderLayout` rather than from a PDF, and image dimensions
come from PNG IHDR and JPEG SOF headers, which are integers. So no f32-derived
quantity reaches any output field.

## Verdicts

`cargo test` green across all 14 suites; `cargo fmt --check` and `cargo clippy
--all-targets -- -D warnings` clean. The preflight suite is 13 tests.

## Residuals

- **The contrast path inherits WP-5.3a's PNG-only decoder.** Python's
  `_raster_dimensions` accepts `.png`, `.jpg` and `.jpeg`, and this port matches
  that reach by reading PNG IHDR and JPEG SOF headers directly. But when
  dimensions are found, `prepare_print_image` runs, and `metrics.rs::decode_rgb`
  is PNG-only. A JPEG figure would therefore be measured by Python and would
  fail loud here. 010 carries only PNGs, so the divergence is latent. The gap is
  in WP-5.3a's module, not this one, and closing it is outside this WP's Owns.
- **`_placement_value`'s dict-versus-attribute branch has no Rust counterpart.**
  Python accepts either a mapping or an object for each placement; Rust takes one
  typed `FigurePlacement`. That branch is a Python affordance rather than
  behaviour, and the real caller (`package.py`) always passes the
  `reader_layout.FigurePlacement` dataclass.
- **`_png_dimensions` is dead code in the Python.** It is defined at
  `preflight.py:39`, delegates to `_raster_dimensions`, and is called from
  nowhere in `src/magazine/`. Not ported; recorded so a later reader does not
  think it was missed.
- **The duplicate audit false-positives on idiomatic constructor names.**
  WP-5.1e's widened `no_helper_is_defined_in_two_modules` fired on `load` being
  defined in both `cover/outline.rs` and this module, with the same signature and
  entirely different bodies and domains. This is the second instance of that
  class after `new`, which is already allowlisted. I renamed mine to `Pdf::read`
  rather than force an entry into a file I do not own, but the underlying point
  stands: a (name, signature) key will keep firing on `load`, `open`, `read` and
  friends, so either the allowlist grows without bound or the key needs refining.
  Flagged for WP-5.1e's verifier and the planner rather than worked around
  silently.
- **`mod package` carries `#[allow(dead_code)]`**, matching the precedent set for
  `mod model`, because nothing in the binary consumes preflight until WP-5.5c
  wires `package_release`. WP-5.5c should remove it.
- **The 010 oracle is not proven by `cargo test` alone.** It is env-var driven
  (`MAG_PREFLIGHT_SPEC` and `MAG_PREFLIGHT_ORACLE`, both or neither, exactly one
  panics), and with neither set the test ANNOUNCES its skip on stderr rather than
  passing silently. The commands above are what prove 010.

## Status

done
