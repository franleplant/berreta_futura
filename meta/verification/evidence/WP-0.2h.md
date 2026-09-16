# WP-0.2h the shared tracer text path

## Base

804ffa7 (plan revision 22). Landed after WP-0.2i (18e35ed) freed the
comparator lane.

## Commands

Build and the three standing checks:

    cd mag && cargo fmt && cargo clippy --all-targets -- -D warnings && cargo test

Verdict digests, from the two matched pre-5504e5a render trees:

    T=/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59
    U=/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-49-02
    M=./mag/target/release/mag
    $M parity 010 --pre-rendered $T $T   # A-vs-A, twice
    shasum -a 256 output/parity/010/verdict.json
    $M parity 010 --pre-rendered $T $U   # A-vs-B
    shasum -a 256 output/parity/010/verdict.json

The cover and booklet measurements need a probe, because the compared domain
is pages 2..n-1 and the covers sit outside it. Recreate it as
`mag/tests/zzprobe.rs`, run it, then remove it (it is deliberately not
committed: it reads untracked render trees):

    #[path = "../src/parity/streams.rs"]
    #[allow(dead_code)]
    mod streams;
    #[path = "../src/parity/display.rs"]
    #[allow(dead_code)]
    mod display;

    use std::collections::BTreeMap;
    use std::path::Path;

    const ROOT: &str = "/Users/franguijarro/code/magazine";
    const TREE: &str = "/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en";

    fn font_map() -> BTreeMap<String, streams::Face> {
        let text = std::fs::read_to_string(format!("{ROOT}/meta/verification/parity.yaml")).unwrap();
        let doc: serde_yaml::Value = serde_yaml::from_str(&text).unwrap();
        let mut map = BTreeMap::new();
        let m = doc["normalization"]["font_name_map"]["entries"].as_mapping().unwrap();
        for (k, v) in m {
            map.insert(k.as_str().unwrap().to_string(), streams::Face {
                face: v["face"].as_str().unwrap().to_string(),
                file: format!("{ROOT}/{}", v["file"].as_str().unwrap()),
            });
        }
        map
    }

    #[test]
    fn probe() {
        let map = font_map();
        let reader = format!("{TREE}/reader.pdf");
        for page in [1u32, 56u32] {
            match display::extract(Path::new(&reader), page, page, &map) {
                Ok(d) => {
                    let e = &d.pages[0].elements;
                    let (mut chars, mut shows) = (0, 0);
                    let mut modes = std::collections::BTreeSet::new();
                    for el in e {
                        if let streams::Element::Text { s, tr, .. } = el {
                            chars += s.chars().count();
                            shows += 1;
                            modes.insert(*tr);
                        }
                    }
                    println!("PAGE {page}: OK {} elements, {shows} shows, {chars} chars, tr {modes:?}", e.len());
                }
                Err(e) => println!("PAGE {page}: ERR {e:#}"),
            }
        }
        let booklet = format!("{TREE}/booklet-a4.pdf");
        match display::extract(Path::new(&booklet), 1, 28, &map) {
            Ok(d) => println!("BOOKLET extract: OK {} pages", d.pages.len()),
            Err(e) => println!("BOOKLET extract: ERR {e:#}"),
        }
        match display::trace_elements(Path::new(&booklet), 1, 28, &map) {
            Ok(p) => println!("BOOKLET trace_elements: OK {} pages, {} elements",
                p.len(), p.iter().map(|x| x.len()).sum::<usize>()),
            Err(e) => println!("BOOKLET trace_elements: ERR {e:#}"),
        }
    }

Run it from the repository root, not from `mag/`: the vendored font paths in
`font_name_map` are repository-relative and a probe run with `cargo test`'s
default working directory resolves them against `mag/` and fails with
`No such file or directory`. That is a probe artifact, not a tracer defect.

## Tool versions

Unchanged from parity.yaml `tools:`. rustc 1.96.0, lopdf 0.45.0. No crate
added, so `mag/Cargo.toml` and `mag/Cargo.lock` are untouched and rule 1a's
only-gained check is not applicable.

## Metrics

**The covers had THREE fail-loud reasons, not two.** The plan and WP-5.4
named two. Tracing page 1 with each fix applied in turn shows the order:

| stop | error | owner before this WP |
|---|---|---|
| 1 | `operator Tf: loading font F1: font Helvetica lacks ToUnicode` | WP-0.2h |
| 2 | `operator Do: decoding image: decoding SMask: image Decode array unsupported` | none |
| 3 | `text render mode != 0 unsupported` (reached only after 1 and 2) | WP-0.2h |

The second was unowned and undiscovered. The cover's full-page Form XObject
raster carries an SMask whose dictionary states `/Decode [0, 1]` explicitly,
which for 8-bit DeviceGray IS the specification's default, so it remaps
nothing. The tracer rejected any Decode array at all. It now accepts an
array that equals the identity for the colour space and fails loud on one
that does not, which is the case that would genuinely change pixels.

**WP-5.4's stream-order pointer is confirmed by measurement**, not accepted.
On page 1 the offsets are `/F1` at 19, `3 Tr` at 240, `/F2+0` at 280; on
page 56, 19, 201 and 235. So `/F1` precedes any `3 Tr`, the Helvetica decode
is the first stop and the render mode the second, exactly as WP-5.4 predicted
without running the tracer.

**The covers now trace.**

| page | elements | text shows | characters | render modes |
|---|---|---|---|---|
| 1 | 8 | 5 | 166 | {3} |
| 56 | 12 | 10 | 371 | {3} |

Every show on both faces is mode 3, which corroborates WP-5.4's finding that
the visible marks are path fills plus a Form XObject raster and that all text
is the invisible selectable layer.

Page 56's 371 characters against WP-5.3d's pypdf figure of 380 is a
DIFFERENCE, not an agreement, and it is the expected one: WP-5.3d measured
that pypdf injects synthetic spaces into letter-spaced runs, so pypdf's count
is a superset. Recorded as a difference rather than reported as a match.

**`/F1` is set but never shown.** Every `Tj`/`TJ` on both covers uses
`/F2+0` (Inter-Regular, which carries ToUnicode). `/F1 12 Tf` sits inside an
empty `BT ... ET` at the head of the stream, which is reportlab's default
font setup. So the Helvetica decode is needed to get PAST the `Tf`, and no
Helvetica glyph is ever measured.

**The seam.** `display::trace_elements` returns per-page `Vec<Element>` and
touches no annotation, outline or named destination. On `booklet-a4.pdf`:

| entry point | result |
|---|---|
| `display::extract` (pages 1-28) | ERR `annotations page 3: resolving named destination: missing required dictionary key "Names"` |
| `display::trace_elements` (pages 1-28) | OK, 28 pages, 2252 elements |

The plan's claim that `extract` dies on this file while `trace_page` reads it
is therefore CONFIRMED, but it was not reproducible before this WP: the
Helvetica stop on sheet 1 masked it, so both entry points failed on the same
earlier error and the `/Names` failure only becomes visible once the covers
decode. The booklet's catalog carries `/Type` and `/Pages` and nothing else,
so imposition drops the name tree while keeping annotations that reference
it.

**Verdict digests, unchanged from WP-0.2i**, which is the clause this WP
must meet (a seam and a decode addition, not a semantic change):

| run | digest | matches WP-0.2i |
|---|---|---|
| A-vs-A run 1 | `0e21644ee602ff8a78fc6ac2` | yes |
| A-vs-A run 2 | `0e21644ee602ff8a78fc6ac2` | yes |
| A-vs-B | `6e932ea43678b91add20a138` | yes |

All clauses pass on both: page_count 56 vs 56, boxes 0 mismatches, text 0
pages differ, colour 0, navigation 0, glyph positions 68800 glyphs over 1488
shows at worst ratio 0.0000, display list 0 pages differ, Tier V max channel
delta 0, Tier E raster `not_evaluated` as WP-0.2f left it. Adding `tr` to
every Text element does not move the digest because verdict.json records
clause outcomes rather than the display list, and every interior show is
mode 0 on both legs.

**Suite**: 107 tests pass across 11 binaries, including WP-0.2d's fault
suite, whose expected-detections matrix is unchanged. No
`assert_vocabulary_observable` handoff was needed, because this WP adds no
new evaluated clause.

## Verdicts

A-vs-A `0e21644ee602ff8a78fc6ac20289c8032c5ba5c4905f8327668a436784b189e0`,
reproduced twice. A-vs-B
`6e932ea43678b91add20a13847e633555e2a3a8b19ef159e86fc0cc2b6015836`. Both
identical to WP-0.2i's recorded digests.

## Residuals

**The simple-font sentinel stays open, deliberately.** WP-0.2i gives simple
fonts `UNRESOLVED_GID` rather than real glyph identity. Simple fonts appear
on pages 1 and 56 and nowhere else, measured across all 56 pages: `/Type1
/Helvetica` and `/TrueType /AAAAAA+Inter-Regular`, both only on the covers.
So the sentinel is outside the compared domain until WP-5.4g, and closing it
now would have no consumer. It should not be closed by halves either: the
Inter-Regular subset CAN be closed by WP-0.2i's outline-hash route, but
non-embedded Helvetica CANNOT, because there is no embedded font program
whose outlines could be hashed. For a standard-14 face glyph identity is
defined by the encoding, which is exactly what this WP now records as the
decoded string. Closing one and not the other would leave an asymmetry
looking like a closed hole. This is WP-5.4g's obligation and WP-0.2i already
assigned it there.

**`/Differences` is not implemented and fails loud.** The spec allows a base
encoding to be overridden per code by a `/Differences` array of glyph names.
Implementing it needs a glyph-name-to-Unicode table (the Adobe Glyph List),
which nothing in this repository requires today: reportlab emits
`/Encoding /WinAnsiEncoding` bare. A font that carries `/Differences` now
fails with a message naming the encoding rather than decoding it wrongly.

**`MacRomanEncoding` fails loud** for the same reason: not emitted here, not
implemented, named in the error rather than silently mapped.

**Standard-14 metrics are not implemented.** A standard-14 font may omit
`/Widths`, and the widths then come from the AFM metrics that ship with the
face. This WP decodes such a font's codes but fails loud at SHOW time if it
ever draws a glyph, with `shows text but carries no Widths; standard-14 AFM
metrics are not implemented`. The failure moved from load time to show time
deliberately: 010's `/F1` is set and never shown, so the covers trace, while
a future PDF that genuinely shows Helvetica text fails loudly rather than
advancing by a guessed width. Symbol and ZapfDingbats are excluded from the
standard-14 list entirely, since they use built-in encodings rather than
StandardEncoding or WinAnsiEncoding.

**`3 Tr` is recorded, other modes still fail loud.** Modes 0 and 3 are
accepted and carried on the element as `tr`; 1, 2, 4, 5, 6 and 7 fail with
the mode named. Revision 19 decided recording over skipping, and WP-0.2i
endorsed it independently: `pdftotext` extracts invisible text, so Tier S
already compares it, and silently equating invisible with visible text would
let a real difference through.

## Status

done
