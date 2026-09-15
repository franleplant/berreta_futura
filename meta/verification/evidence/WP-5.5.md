# WP-5.5 preflight + package + web

## Base

8335e95 (plan revision 16). `art_directed` reached 6c24379 during the work;
nothing here depends on the difference.

## Status

**blocked.** Not on a difficulty found while porting, but on four
dependencies measured before writing code, three of which the plan's
dependency graph does not express. No Rust was written: `mag/src/package/`
and `mag/src/web/` do not exist, and the Cargo lane was never taken.

## Commands

Dependency surface, exact:

    grep -n "from .booklet import\|from .image_contrast import" src/magazine/preflight.py
    grep -n "from .booklet import\|from .render_critic import\|from .preflight import" src/magazine/package.py
    grep -n "^from \.\|^import " src/magazine/web_edition.py
    ls mag/src/impose.rs mag/src/critic/rules.rs mag/src/cover

Segno reproduction, all nine source codes of edition 010, against the
committed web tree of an existing render:

    uv run python -c "
    import io,glob
    from pathlib import Path
    import segno, yaml
    from src.magazine.manifest import source_code_payload
    files=sorted(glob.glob('editions/010/render-2026-09-14T01-33-59/en/web/assets/source-code-*.svg'))
    recs={}
    for r in glob.glob('library/sources/*/record.yaml'):
        d=yaml.safe_load(Path(r).read_text()); recs[d.get('id')]=d.get('url')
    ok=0
    for f in files:
        sid=Path(f).stem.replace('source-code-','')
        p=source_code_payload(recs[sid])
        q=segno.make(p,error='L',micro=False)
        buf=io.BytesIO(); q.save(buf,kind='svg',scale=1,border=4,dark='#17191c',light='#ffffff',xmldecl=False,svgns=True,nl=False)
        same=buf.getvalue()==Path(f).read_bytes(); ok+=same
        print(f'{sid[:38]:40s} v{q.version} mask{q.mask} {q.mode} req=L act={q.error} identical={same}')
    print('byte-identical:',ok,'/',len(files))
    "

## Tool versions

python 3.12.11, uv 0.8.17, segno as pinned by the project environment,
pypdf 6.14.2, rustc 1.96.0. The render tree used as the web-output oracle is
`editions/010/render-2026-09-14T01-33-59` (untracked; it postdates 5504e5a,
so its web tree matches the current stylesheet state).

## Metrics

### Blocker 1: preflight.py needs booklet.py (WP-5.2, not landed)

`src/magazine/preflight.py:8` imports `A4_LANDSCAPE_POINTS` and
`section_reader_pages` from `booklet.py`. `section_reader_pages` decides
`reader_pages` and `expected_sheets` for both booklet sections, which are
preflight.json fields inside the WP's own oracle. `mag/src/impose.rs` does
not exist; WP-5.2 is in flight.

Its other import, `prepare_print_image` from `image_contrast.py`, is
satisfied: `mag/src/critic/metrics.rs` is accepted (WP-5.3a, 0a68eb4 /
53d8b60) and is consumable as the plan directs.

### Blocker 2: package.py needs booklet.py and render_critic.py

`package.py:11` imports `impose_a5_on_a4`, `:14` imports `inspect_render`.
`package_release` calls imposition three times and writes render-critic.json
before writing preflight.json, and the SHA256SUMS file digests all of those
outputs plus the critic's contact sheets. So SHA256SUMS, the archive
comparison and the printing instructions (which count imposed sheets) cannot
be produced, let alone compared, until both land. `mag/src/critic/rules.rs`
does not exist and WP-5.3b is itself blocked.

The leaf parts of package.py are portable today and were not written, since
shipping half an orchestrator ahead of its callees would invite exactly the
stale-copy drift the Phase 5 preamble forbids: `sha256`,
`_adopt_rendered_layout`, `_printing_instructions`, `_studio_note`.

### Blocker 3: web_edition.py needs four cover.py helpers (WP-5.4, not started)

`web_edition.py:18` imports `_cover_contributors`, `_cover_date`,
`cover_tab_identity`, `cover_tab_issue` from `cover.py`. These are NOT the
cover PDF compiler WP-5.4 is scoped around (fontTools outlines, resvg,
reportlab). They are four pure text functions over `Edition`: an author
roster joined with " / " and upper-cased with a deck fallback, a date
re-spaced from hyphens, a `"{PUBLICATION} / BUENOS AIRES"` tab string, and an
`"ISSUE"`/`"NÚMERO"` label with a three-digit zero-padded number.

`mag/src/cover/` does not exist, so there is nothing to import and the
duplicated-helper rule forbids copying them. This is a seam the plan has not
assigned: whichever of WP-5.4 and WP-5.5 runs first must define them and the
other must import. It is a one-line decision and it belongs in the plan
rather than in whichever agent happens to arrive first.

### Blocker 4: the byte-identical web/ oracle requires reproducing segno

`web_edition.py:_materialize_source_codes` generates one QR code per
illustrated-opener article with `segno`, saved as SVG with `scale=1`,
`border=4`, `dark="#17191c"`, `light="#ffffff"`, `xmldecl=False`,
`svgns=True`, `nl=False`. Edition 010 emits nine of them into
`en/web/assets/`, so they are inside the WP's stated oracle.

Measured, all nine, regenerated against the committed render tree:

| source | version | mask | mode | requested | actual | identical |
|---|---|---|---|---|---|---|
| an-alignment-assessment-of-recent-cybe | 4 | 2 | byte | L | L | yes |
| countering-misuse-of-ai-september-2026 | 4 | 7 | byte | L | **M** | yes |
| dario-amodei-we-must-pace-the-frontier | 3 | 7 | byte | L | L | yes |
| deepseek-v4-1-flash-pushing-the-limits | 3 | 2 | byte | L | L | yes |
| government-rails-site-hit-hours-after- | 4 | 2 | byte | L | **M** | yes |
| rapidly-scaling-online-storage-to-serv | 4 | 7 | byte | L | **M** | yes |
| scenarios-for-our-economic-future-eaff | 3 | 5 | byte | L | **M** | yes |
| the-third-era-of-ai-software-developme | 2 | 3 | byte | L | **M** | yes |
| towards-self-driving-codebases-3fd7b9c | 3 | 5 | byte | L | **M** | yes |

9 of 9 byte-identical, so generation is deterministic and the parameters are
fully understood.

Two findings that decide how hard the reproduction is:

- **Every payload is byte mode**, because `source_code_payload` strips the
  scheme and `www.` from a lowercase URL and QR alphanumeric mode cannot
  carry lowercase. Mode segmentation, which is where independent QR encoders
  most often diverge, is therefore not a variable here at all.
- **Segno silently boosts the error level on 6 of 9.** `error="L"` is
  requested and `q.error` reports `M`: segno raises the correction level
  whenever a higher one fits the chosen version for free. That is a segno
  policy, not ISO/IEC 18004. A spec-correct encoder asked for level L would
  emit a different codeword stream, a different mask score and a different
  matrix for two thirds of this edition's codes, while looking entirely
  correct in isolation.

So the sub-problem is bounded and specifiable: byte-mode encoding, smallest
fitting version, spec mask-penalty selection, segno's error-boost rule, and
segno's run-length SVG path serialization. It is materially more tractable
than the pypdf text layer that blocked WP-5.7 and WP-5.3b, because four of
the five parts are a published specification and the fifth is one documented
policy. It is nonetheless a sub-project with a silent-divergence trap in it,
and it is not what "port preflight, package and web" was scoped to include.

### Branch enumeration, by reading the Python rather than the corpus

Recorded so the work is not re-derived when the WP is re-cut, per the
preamble's corpus rule. Branches edition 010 cannot reach:

- `preflight.py`: every studio blocker except the two unconditional ones.
  010's `result` is `ready`, so `cover_resolution` (cover below 300 ppi at
  placement), `figure_resolution`, `figure_geometry` and `figure_contrast`
  are all unreached, as are `_box_invalid`'s six disjuncts, `_figure_geometry`
  collision detection, the `es` message table, and `_raster_dimensions`
  returning None for a non-raster or unreadable path.
- `package.py`: the `render_report["result"] == "fail"` raise, and the `es`
  branches of `_printing_instructions` and `_studio_note`.
- `web_edition.py`: the filename-collision `ValidationError`, the
  no-illustrated-opener early return (010 has nine), the segno failure path,
  and every `alternates`/`source_urls` branch not exercised by a
  single-language edition.

## Verdicts

None produced. No comparison was run, because no Rust exists to compare and
three of the four artifacts in the oracle cannot be generated without WP-5.2
and WP-5.3b.

## Residuals

- The plan's graph carries only `WP-5.1c -> WP-5.5`. Measured, WP-5.5 needs
  WP-5.1a, WP-5.1c and WP-5.3a (all satisfied) **and** WP-5.2, WP-5.3b and
  WP-5.4 (none satisfied). This is the third undeclared dependency edge found
  in Phase 5, after WP-5.3b found `render_critic.py -> booklet.py` and this
  WP found both `preflight.py -> booklet.py` and `web_edition.py -> cover.py`.
  The common cause is that the graph was drawn from the plan's WP groupings
  rather than from the Python import graph, and the import graph is cheap to
  read: a WP that enumerates it before scheduling would have caught all three.
- Recommended re-cut, along the seam the dependencies actually create:
  **WP-5.5a web edition** (needs the cover-helper seam assigned and the segno
  decision taken), **WP-5.5b preflight** (needs WP-5.2 only), **WP-5.5c
  package orchestration and SHA256SUMS** (needs WP-5.2 and WP-5.3b). 5.5b is
  runnable the moment WP-5.2 lands and is the smallest of the three.
- The segno decision is a plan decision of the same family the plan has now
  taken three times: reproduce the library, or re-scope the oracle. Unlike
  pypdf it is mostly specification, and unlike `article.md` the QR SVGs are
  regenerated on every render, so a re-scope would have to say what replaces
  byte-identity. A structural oracle is available and cheap here in a way it
  was not for text: decode both SVGs back to a module matrix and compare
  matrices plus the decoded payload, which is insensitive to serialization
  but still catches a wrong version, mask or error level.
- The three brittle regexes WP-0.0c assigned to this WP (`_PRINT_ONLY_LINE`,
  `_SOURCE_LINK_LINE`, `_PIECE_OPENING`, plus `_ILLUSTRATED_OPENER_HEADER`
  still requiring the class to be exactly `article-opener`) remain unaddressed
  and should move to WP-5.5a with the rest of the web path.
- `web_edition.py` reaches into `cover.py`'s private `_cover_contributors`
  and `_cover_date` across a module boundary. Whichever WP defines them
  should give them a public home rather than preserving the underscore.
