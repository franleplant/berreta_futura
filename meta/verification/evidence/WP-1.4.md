# WP-1.4 Typst measurement interface and version pin

Phase 1 spike. Throwaway code, binding numbers. Verification is the rule-3
evidence-consistency audit.

## Base

0bd7cc0e6ab2a4dc74caec6c89bf0155afe07b30

Spike code lived uncommitted under
`/Users/franguijarro/.claude/jobs/7d99e27f/tmp/wp14` (a standalone cargo
project outside the repo, so no repo worktree was needed and no tracked file
was touched). `git status --short` is clean at WP end; only this evidence
file is committed.

## Status

done

Both halves of the target are proven by a running program, not by reading
documentation: the typst crates expose per-element page and box for every
line, figure, heading, ornament and link at far better than 0.1 pt, from
Rust, without parsing the PDF; and the exact versions to pin are fixed.

## Verdicts

The pin, for WP-2.0a to write into `mag/Cargo.toml` and `parity.yaml`:

```toml
typst = "=0.15.1"
typst-layout = "=0.15.1"
typst-library = "=0.15.1"
typst-pdf = "=0.15.1"
typst-syntax = "=0.15.1"
```

Five direct dependencies, resolving to 295 packages total. Every typst-family
crate in the lock resolves to 0.15.1 (`typst-assets`, `typst-eval`,
`typst-html`, `typst-layout`, `typst-library`, `typst-macros`, `typst-pdf`,
`typst-realize`, `typst-svg`, `typst-syntax`, `typst-timing`, `typst-utils`).

Notes that change what WP-2.0a writes:

- `typst-layout` is a REQUIRED direct dependency. `PagedDocument`,
  `PagedIntrospector` and `Page` are defined there, and the `typst` facade
  does not re-export them.
- `typst-syntax` is a required direct dependency: constructing the main
  `FileId` needs `RootedPath`, `VirtualRoot` and `VirtualPath`.
- `comemo` is NOT needed as a direct dependency. It was added first and then
  removed; the minimal embedding builds and runs without it.
- `typst-library` is needed directly for `Selector`, `Element`,
  `NativeElement`, `Introspector`, `Frame`, `FrameItem`, `Geometry` and the
  element types (`HeadingElem`, `FigureElem`). Some of these are reachable
  through `typst::*` re-exports, but not all, so the direct dependency is
  simpler.

MSRV: typst 0.15.1 and typst-pdf 0.15.1 both declare `rust-version = 1.92`.
The repo builds on rustc 1.96.0 (parity.yaml `tools:`), so there is margin.

Edition: the spike was first written on edition 2024 and then rebuilt on
edition 2021, which is what `mag/Cargo.toml` declares. It builds and runs
identically. No API in this path requires edition 2024, so `mag` does not
need an edition bump.

## Tool versions

- rustc 1.96.0 (ac68faa20 2026-05-25)
- cargo 1.96.0 (30a34c682 2026-05-25)
- typst crates 0.15.1 (all)
- fonts read from `src/magazine/assets/fonts/` (12 TTF faces, unmodified)

## Commands

Standalone-replayable. The spike is outside the repo; nothing in the repo is
required except the font directory and one image used as a figure fixture.

```sh
mkdir -p /tmp/wp14 && cd /tmp/wp14
cargo init --name wp14_spike --vcs none
cargo add typst@=0.15.1 typst-layout@=0.15.1 typst-library@=0.15.1 \
          typst-pdf@=0.15.1 typst-syntax@=0.15.1
sed -i '' 's/^edition = "2024"/edition = "2021"/' Cargo.toml
cp /Users/franguijarro/code/magazine/library/sources/\
why-software-factories-fail-f53679d7/media/003.png fig.png
# write src/main.rs exactly as reproduced below
cargo run --quiet
```

Determinism check (two runs, compare walk output and exported PDF):

```sh
cd /tmp/wp14
cargo run --quiet 2>/dev/null | grep -v compile_ms > run1.txt && cp out.pdf out1.pdf
cargo run --quiet 2>/dev/null | grep -v compile_ms > run2.txt && cp out.pdf out2.pdf
diff -q run1.txt run2.txt && cmp out1.pdf out2.pdf && echo DETERMINISTIC
shasum -a 256 out1.pdf out2.pdf
```

Edition and dependency-minimality checks:

```sh
cd /tmp/wp14
cargo remove comemo && cargo build    # still builds: comemo is not needed
sed -i '' 's/^edition = "2024"/edition = "2021"/' Cargo.toml && cargo build
```

`Cargo.toml` after the above:

```toml
[package]
name = "wp14_spike"
version = "0.1.0"
edition = "2021"

[dependencies]
typst = "=0.15.1"
typst-layout = "=0.15.1"
typst-library = "=0.15.1"
typst-pdf = "=0.15.1"
typst-syntax = "=0.15.1"
```

`src/main.rs` in full:

```rust
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

use typst::diag::{FileError, FileResult};
use typst::foundations::{Bytes, Datetime, Smart};
use typst::layout::{Abs, Point, Transform};
use typst::text::{Font, FontBook};
use typst::utils::LazyHash;
use typst::{Library, LibraryExt, World};
use typst_layout::{PagedDocument, PagedIntrospector};
use typst_library::foundations::{Duration, Element, NativeElement, Selector};
use typst_library::introspection::{Introspector, Location};
use typst_library::layout::{Frame, FrameItem};
use typst_library::visualize::Geometry;
use typst_syntax::{FileId, RootedPath, Source, VirtualPath, VirtualRoot};

const FONT_DIR: &str = "/Users/franguijarro/code/magazine/src/magazine/assets/fonts";

struct MagWorld {
    library: LazyHash<Library>,
    book: LazyHash<FontBook>,
    fonts: Vec<Font>,
    main: FileId,
    source: Source,
    root: PathBuf,
}

impl MagWorld {
    fn new(text: &str, root: impl AsRef<Path>) -> Self {
        let mut fonts = Vec::new();
        let mut paths: Vec<PathBuf> = Vec::new();
        for family in std::fs::read_dir(FONT_DIR).expect("font dir") {
            let family = family.expect("font family entry").path();
            if !family.is_dir() {
                continue;
            }
            for face in std::fs::read_dir(&family).expect("font family") {
                let face = face.expect("font face entry").path();
                if face.extension().and_then(|e| e.to_str()) == Some("ttf") {
                    paths.push(face);
                }
            }
        }
        paths.sort();
        for path in &paths {
            let data = std::fs::read(path).expect("read font");
            let bytes = Bytes::new(data);
            for font in Font::iter(bytes) {
                fonts.push(font);
            }
        }
        let book = FontBook::from_fonts(&fonts);
        let vpath = VirtualPath::new("main.typ").expect("vpath");
        let main = RootedPath::new(VirtualRoot::Project, vpath).intern();
        Self {
            library: LazyHash::new(Library::builder().build()),
            book: LazyHash::new(book),
            fonts,
            main,
            source: Source::new(main, text.into()),
            root: root.as_ref().to_path_buf(),
        }
    }
}

impl World for MagWorld {
    fn library(&self) -> &LazyHash<Library> {
        &self.library
    }

    fn book(&self) -> &LazyHash<FontBook> {
        &self.book
    }

    fn main(&self) -> FileId {
        self.main
    }

    fn source(&self, id: FileId) -> FileResult<Source> {
        if id == self.main {
            Ok(self.source.clone())
        } else {
            Err(FileError::NotFound(id.vpath().get_without_slash().into()))
        }
    }

    fn file(&self, id: FileId) -> FileResult<Bytes> {
        let path = id
            .vpath()
            .realize(&self.root)
            .map_err(|_| FileError::AccessDenied)?;
        std::fs::read(&path)
            .map(Bytes::new)
            .map_err(|e| FileError::from_io(e, &path))
    }

    fn font(&self, index: usize) -> Option<Font> {
        self.fonts.get(index).cloned()
    }

    fn today(&self, _offset: Option<Duration>) -> Option<Datetime> {
        None
    }
}

static FIXTURE: LazyLock<String> = LazyLock::new(|| {
    r#"
#set page(width: 148mm, height: 210mm, margin: (x: 14mm, y: 16mm), numbering: "1")
#set text(font: "Source Serif 4 SmText", size: 10pt, lang: "en")
#set par(leading: 4pt, linebreaks: "simple", justify: false)

= The Speed Limit

Body text line one that runs long enough to wrap across the measure and
produce several distinct lines, which is what the measurement interface has to
report back with page and box for every one of them.

#line(length: 100%, stroke: 0.5pt)

#figure(image("fig.png", width: 60mm), caption: [A figure caption])

== Second Heading

More body text after the figure, again long enough to wrap so that the frame
walk has multiple text items to report on the second page or lower on the
first.

#link("https://example.com")[An external link]

#pagebreak()

= Second Article Opener

#lorem(220)

#pagebreak()

= Third Article Opener

#lorem(40)
"#
    .to_string()
});

struct Walker<'a> {
    introspector: &'a PagedIntrospector,
    page: usize,
    rows: Vec<String>,
}

impl Walker<'_> {
    fn walk(&mut self, frame: &Frame, ts: Transform) {
        for (pos, item) in frame.items() {
            let p = pos.transform(ts);
            match item {
                FrameItem::Group(group) => {
                    self.walk(
                        &group.frame,
                        ts.pre_concat(
                            group
                                .transform
                                .pre_concat(Transform::translate(pos.x, pos.y)),
                        ),
                    );
                }
                FrameItem::Text(text) => {
                    let width: Abs =
                        text.glyphs.iter().map(|g| g.x_advance.at(text.size)).sum();
                    self.rows.push(format!(
                        "page={} kind=text x={:.3} y={:.3} w={:.3} size={:.3} font={} text={:?}",
                        self.page,
                        p.x.to_pt(),
                        p.y.to_pt(),
                        width.to_pt(),
                        text.size.to_pt(),
                        text.font.info().family,
                        text.text.as_str()
                    ));
                }
                FrameItem::Shape(shape, _) => {
                    let (kind, w, h) = match &shape.geometry {
                        Geometry::Line(to) => ("line", to.x.to_pt(), to.y.to_pt()),
                        Geometry::Rect(size) => ("rect", size.x.to_pt(), size.y.to_pt()),
                        Geometry::Curve(_) => ("curve", f64::NAN, f64::NAN),
                    };
                    self.rows.push(format!(
                        "page={} kind=shape:{} x={:.3} y={:.3} w={:.3} h={:.3}",
                        self.page,
                        kind,
                        p.x.to_pt(),
                        p.y.to_pt(),
                        w,
                        h
                    ));
                }
                FrameItem::Image(_, size, _) => {
                    self.rows.push(format!(
                        "page={} kind=image x={:.3} y={:.3} w={:.3} h={:.3}",
                        self.page,
                        p.x.to_pt(),
                        p.y.to_pt(),
                        size.x.to_pt(),
                        size.y.to_pt()
                    ));
                }
                FrameItem::Link(dest, size) => {
                    self.rows.push(format!(
                        "page={} kind=link x={:.3} y={:.3} w={:.3} h={:.3} dest={:?}",
                        self.page,
                        p.x.to_pt(),
                        p.y.to_pt(),
                        size.x.to_pt(),
                        size.y.to_pt(),
                        dest
                    ));
                }
                FrameItem::Tag(_) => {}
            }
        }
        let _ = self.introspector;
    }
}

fn content_extent(
    frame: &Frame,
    ts: Transform,
    body_bottom: Abs,
    lowest: &mut Abs,
    count: &mut usize,
) {
    for (pos, item) in frame.items() {
        let p = pos.transform(ts);
        match item {
            FrameItem::Group(group) => content_extent(
                &group.frame,
                ts.pre_concat(
                    group
                        .transform
                        .pre_concat(Transform::translate(pos.x, pos.y)),
                ),
                body_bottom,
                lowest,
                count,
            ),
            FrameItem::Tag(_) => {}
            _ if p.y > body_bottom => {}
            FrameItem::Image(_, size, _) => {
                *count += 1;
                *lowest = (*lowest).max(p.y + size.y);
            }
            _ => {
                *count += 1;
                *lowest = (*lowest).max(p.y);
            }
        }
    }
}

fn query_positions(doc: &PagedDocument, label: &str, sel: Selector) {
    let introspector: &PagedIntrospector = doc.introspector();
    for content in Introspector::query(introspector, &sel) {
        let Some(loc): Option<Location> = content.location() else {
            continue;
        };
        let Some(pos) = introspector.position(loc) else {
            continue;
        };
        println!(
            "QUERY {label}: page={} x={:.3} y={:.3}",
            pos.page,
            pos.point.x.to_pt(),
            pos.point.y.to_pt()
        );
    }
}

fn main() {
    let root = std::env::current_dir().expect("cwd");
    let world = MagWorld::new(&FIXTURE, &root);

    println!("FONTS available to typst:");
    let mut families: Vec<String> = world.book.families().map(|(n, _)| n.to_string()).collect();
    families.sort();
    families.dedup();
    for f in &families {
        println!("  family: {f}");
    }

    let started = std::time::Instant::now();
    let result = typst::compile::<PagedDocument>(&world);
    let doc = match result.output {
        Ok(doc) => doc,
        Err(errors) => {
            for e in errors {
                eprintln!("COMPILE ERROR: {}", e.message);
            }
            std::process::exit(1);
        }
    };
    let compile_ms = started.elapsed().as_millis();
    for w in &result.warnings {
        eprintln!("WARNING: {}", w.message);
    }

    println!("PAGES: {}", doc.pages().len());
    for (i, page) in doc.pages().iter().enumerate() {
        println!(
            "PAGE {} number={} size={:.3}x{:.3}pt",
            i + 1,
            page.number,
            page.frame.size().x.to_pt(),
            page.frame.size().y.to_pt()
        );
    }

    let mut walker = Walker {
        introspector: doc.introspector(),
        page: 0,
        rows: Vec::new(),
    };
    for (i, page) in doc.pages().iter().enumerate() {
        walker.page = i + 1;
        let frame = page.frame.clone();
        walker.walk(&frame, Transform::identity());
    }
    println!("FRAME WALK ({} items):", walker.rows.len());
    for row in &walker.rows {
        println!("  {row}");
    }

    println!("DERIVED RenderLayout fields (body region only, folio excluded):");
    let margin_y = Abs::pt(45.354);
    for (i, page) in doc.pages().iter().enumerate() {
        let height = page.frame.size().y;
        let body_bottom = height - margin_y;
        let body_height = body_bottom - margin_y;
        let mut lowest = Abs::zero();
        let mut count = 0usize;
        content_extent(
            &page.frame,
            Transform::identity(),
            body_bottom,
            &mut lowest,
            &mut count,
        );
        let used = lowest - margin_y;
        println!(
            "  page {}: body_items={} content_bottom={:.3}pt frame_usage={:.4} terminal_gap={:.3}pt",
            i + 1,
            count,
            lowest.to_pt(),
            used.to_pt() / body_height.to_pt(),
            (body_bottom - lowest).to_pt()
        );
    }

    query_positions(
        &doc,
        "heading",
        Selector::Elem(Element::of::<typst_library::model::HeadingElem>(), None),
    );
    query_positions(
        &doc,
        "figure",
        Selector::Elem(Element::of::<typst_library::model::FigureElem>(), None),
    );
    let _ = <typst_library::model::HeadingElem as NativeElement>::ELEM;

    let pdf = typst_pdf::pdf(
        &doc,
        &typst_pdf::PdfOptions {
            ident: Smart::Custom("wp14-spike".into()),
            ..Default::default()
        },
    )
    .expect("pdf export");
    std::fs::write("out.pdf", &pdf).expect("write pdf");
    println!("PDF bytes: {}", pdf.len());
    println!("compile_ms: {compile_ms}");
    let _ = Point::zero();
}
```

## Metrics

Compile of the 3-page A5 fixture: 52-71 ms. PDF export: 221348 bytes. Build
emits zero warnings.

Fonts: all 12 vendored TTFs load through the `World`; typst reports five
families, which is the correct grouping of the twelve faces (Archivo, Geist
Mono, Inter, Source Serif 4 Display, Source Serif 4 SmText).

Page geometry read back exactly as set: `419.528 x 595.276 pt` = 148 x 210 mm
= A5, on all three pages.

Frame walk, 45 items over 3 pages. Representative extracted positions (page,
x, y in pt from the top-left, all sub-0.1 pt; `Abs` is an f64 scalar
internally so the printed 3 decimals are a formatting choice, not the
resolution limit):

| element | page | x | y | extent |
|---|---|---|---|---|
| heading "The Speed Limit" (14 pt) | 1 | 39.685 | 54.734 | w 108.724 |
| body line 1 (10 pt) | 1 | 39.685 | 68.934 | w 337.380 |
| body line 2 | 1 | 39.685 | 79.634 | w 333.900 |
| body line 3 | 1 | 39.685 | 90.334 | w 276.150 |
| ornament (`#line`, stroked) | 1 | 39.685 | 102.334 | w 340.157 h 0.000 |
| figure image | 1 | 124.724 | 114.334 | w 170.079 h 156.690 |
| figure caption | 1 | 151.144 | 284.224 | w 117.240 |
| subheading (12 pt) | 1 | 39.685 | 306.664 | w 92.928 |
| link annotation rect | 1 | 39.685 | 352.264 | w 75.210 h 10.700 |
| folio "1" | 1 | 207.169 | 570.228 | w 5.190 |
| opener heading page 2 | 2 | 39.685 | 54.734 | w 151.158 |
| opener heading page 3 | 3 | 39.685 | 54.734 | w 140.504 |

Body leading is visible and exact in the walk: consecutive body lines sit
10.700 pt apart (68.934, 79.634, 90.334), which is the 10 pt size plus the
4 pt `leading` minus the font's own line metrics, i.e. the layout engine's
own resolved value rather than anything this spike computed.

Introspection query results (element anchors, distinct from text baselines):

```
QUERY heading: page=1 x=39.685 y=45.354
QUERY heading: page=1 x=39.685 y=298.624
QUERY heading: page=2 x=39.685 y=45.354
QUERY heading: page=3 x=39.685 y=45.354
QUERY figure:  page=1 x=39.685 y=114.334
```

Derived layout metrics, body region only (folio excluded), proving the
plan's per-page aggregates fall out of the frame walk:

```
page 1: body_items=13 content_bottom=360.964pt frame_usage=0.6255 terminal_gap=188.957pt
page 2: body_items=23 content_bottom=293.634pt frame_usage=0.4921 terminal_gap=256.287pt
page 3: body_items=6  content_bottom=111.734pt frame_usage=0.1316 terminal_gap=438.187pt
```

Determinism: two consecutive runs produce identical frame-walk and query
output, and a byte-identical PDF,
`80eb42c4c651c082ed4fe1e5efffed6d5fed35edb3e3c40b3d190d7db7a047ea` both
times. Typst's PDF export is reproducible for a fixed input.

## The API path

Both APIs are needed; they answer different questions.

**Frame walk is the primary path** (`PagedDocument::pages()` ->
`Page::frame` -> `Frame::items()` yielding `(Point, FrameItem)`, recursing
into `FrameItem::Group` while composing `Transform`). It gives the physical
page and box of every laid-out thing:

- `FrameItem::Text(TextItem)` carries `text`, `font`, `size`, `fill`,
  `glyphs` (each with `x_advance`, so the run's advance width is a sum), and
  its `Point` is the baseline origin. One `TextItem` per laid-out line, which
  is exactly the granularity Tier G and `RenderLayout` need.
- `FrameItem::Shape(Shape, Span)` covers rules and ornaments;
  `Shape::geometry` is `Line(Point)`, `Rect(Size)` or `Curve(Curve)`.
  There is no `bbox_size()` helper, so the extent is read per variant.
- `FrameItem::Image(Image, Size, Span)` gives the placement rect directly:
  the `Point` is the top-left, the `Size` is the drawn box, which is
  `figure placement box_points` without touching the PDF.
- `FrameItem::Link(Destination, Size)` gives link rects and destinations
  before PDF export, so navigation is measurable engine-side.
- `FrameItem::Tag(Tag)` carries introspection markers, not geometry.

**Introspection query is the secondary path**
(`PagedDocument::introspector()` -> `Introspector::query(&Selector)` ->
`Content::location()` -> `PagedIntrospector::position(loc)` ->
`PagedPosition { page: NonZeroUsize, point: Point }`). It answers "where did
this semantic element land", which is what the toc and opener logic need:
`Selector::Elem(Element::of::<HeadingElem>(), None)` returns every heading
with its page, no frame walking and no text matching.

The two give different y for the same heading (45.354 from the query, 54.734
from the walk): the query returns the element's layout anchor, the walk
returns the text baseline. Both are correct; the consumer must pick
deliberately. For page attribution, which is what `RenderLayout` mostly
needs, they agree.

## RenderLayout field mapping

Per the Architecture section's list. "Proven" means this spike produced the
number; "derivable" means the inputs are proven present and the arithmetic
is mechanical; nothing is omitted.

| field | source | state |
|---|---|---|
| `toc` (article id -> page) | query `HeadingElem` -> `position().page`; article identity comes from the content the engine itself emits (label or metadata attached at template level) | proven for page attribution (3 headings, 3 correct pages); article-id binding is template work for WP-2.2b |
| `article_pages` | page span between consecutive opener positions from the same query | derivable, arithmetic only |
| `editorial_pages` | same mechanism; editions 010+ carry no editorial, so this is empty by scope | derivable |
| figure placements with `box_points` | `FrameItem::Image` `Point` + `Size`, transformed to page space | proven (170.079 x 156.690 at 124.724, 114.334) |
| `frame usage` | body-region content extent from the walk over page body height | proven (0.6255 / 0.4921 / 0.1316 on the fixture) |
| `terminal balance` | body bottom minus content extent on an article's last page | proven as `terminal_gap` (188.957 / 256.287 / 438.187 pt) |
| `article_opener_fits` | opener heading position plus the extent of the following body items on the opener page, both from the walk | derivable; NOT exercised here because it needs the real opener template (WP-2.2b/2.3), and note the oracle side of this comparison is currently vacuous, see Residuals |
| page count, page sizes | `pages().len()`, `Page::frame.size()` | proven |
| page numbering | `Page::number` (logical, counter-aware) | proven (1, 2, 3) |

No `RenderLayout` field was found to be unsupplied by the typst API.

## Residuals

- The margin constant in the derived-metrics block is hardcoded to the
  fixture's 16 mm. The real engine must take the body region from the
  template's own page setup rather than a literal; this is template work,
  not an API limitation.
- Article identity for `toc` is not an intrinsic Typst concept. The template
  must attach a label or `metadata` to each opener so the query can recover
  which article a heading belongs to. Proven possible in principle (the
  query returns `Content`, whose fields and label are readable); not
  exercised here.
- Oracle-side caveat carried over from WP-0.0b, relevant to the
  `article_opener_fits` row above: the WeasyPrint leg currently emits `{}`
  for that field on every render, so a Typst-vs-oracle comparison of it is
  vacuous until that is resolved. Recorded there; not this WP's to fix.
- `Font::iter(bytes)` is used rather than `Font::new(bytes, index)` so that
  collection files would be handled; all 12 vendored faces are single-face
  TTFs, so this is a no-op today.
- The spike disables justification and sets `linebreaks: "simple"` to match
  the parity-phase template decisions (the plan's known-divergence table).
  Those settings are the template's business in WP-2.2a, not a constraint
  discovered here.
- `typst-assets` resolves as a transitive dependency at 0.15.1. The
  embedding here serves only the repo's own fonts through the `World`, so no
  bundled asset is relied upon.
- Deprecated API avoided: `VirtualPath::as_rootless_path` and
  `VirtualPath::resolve` are deprecated in 0.15.1 in favour of
  `get_without_slash` and `realize`; the reproduced source uses the current
  ones and builds warning-free.
