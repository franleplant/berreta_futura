use crate::typeset::content::{File, Tree};
use crate::typeset::hyphen::Hyphenation;
use crate::typeset::text_shim;
use crate::typeset::world::Sources;
use anyhow::{bail, ensure, Result};
use lopdf::{Object, ObjectId};
use std::path::Path;
use typst::foundations::Smart;
use typst::introspection::{Location, PagedPosition, Tag};
use typst::layout::{Abs, Frame, FrameItem, GroupItem, Point, Size, Transform};
use typst::model::{Destination, Document, Url};
use typst::text::TextItem;
use typst::visualize::{Curve, CurveItem, Geometry, Paint, Shape};
use typst_layout::PagedDocument;
use typst_pdf::{PdfOptions, PdfStandards};

pub const TEMPLATE_TYP: &str = include_str!("../../assets/typeset/template.typ");
pub const ROOT_TYP: &str = include_str!("../../assets/typeset/root.typ");
pub const FONT_DIR: &str = "src/magazine/assets/fonts";
const IDENT: &str = "mag-typeset-reader";
const INLINE_LINK: &str = " mag-inline-link";
const TYPST_DEST_LIFT: f64 = 10.0;
const CHIP_KAPPA: f64 = 0.55;
const CHIP_PAD_X: f64 = 3.0;
const LAYER: &str = "mag-layer";
const BACKDROP: &str = "mag-backdrop";
const CHIP_FILL: [u8; 4] = [244, 241, 249, 255];

pub fn world(tree: &Tree, font_dir: &Path) -> Result<Sources> {
    Sources::new(tree, TEMPLATE_TYP, ROOT_TYP, font_dir)
}

const PLATE_CONTENT: &str = "#closing-signature(none)\n";

pub fn paginate(
    tree: Tree,
    font_dir: &Path,
    hyphenation: Hyphenation,
) -> Result<(Tree, PagedDocument)> {
    let (tree, bare) = crate::typeset::runt::bound(tree, font_dir, hyphenation)?;
    let content = bare.pages().len() - 2;
    let files = tree.files.into_iter().map(|file| File {
        source: file.source.replacen(
            PLATE_CONTENT,
            &format!("#closing-signature({content})\n"),
            1,
        ),
        ..file
    });
    let tree = Tree {
        files: files.collect(),
    };
    let plated = document(&world(&tree, font_dir)?)?;
    let plates = plated
        .introspector()
        .elements()
        .all()
        .filter(|c| {
            c.label()
                .is_some_and(|l| l.resolve().as_str() == "mag-plate")
        })
        .count();
    let pages = plated.pages().len();
    ensure!(
        pages == content + 2 + plates,
        "the closing plates moved the reader's pagination: {content} content pages without \
         them, {pages} pages with {plates} plates"
    );
    ensure!(
        plates == 0 || pages % 4 == 0,
        "the Typst reader is {pages} pages, which is not an A4-fold signature"
    );
    Ok((tree, plated))
}

fn joined(messages: Vec<String>) -> String {
    messages.join("\n  ")
}

#[cfg(test)]
pub fn compile(world: &Sources) -> Result<Vec<u8>> {
    pdf(&document(world)?)
}

pub fn document(world: &Sources) -> Result<PagedDocument> {
    let compiled = typst::compile::<PagedDocument>(world);
    if let Some(warning) = compiled
        .warnings
        .iter()
        .find(|w| w.message.contains("did not converge"))
    {
        eprintln!(
            "warning: the Typst reader did not settle: {}",
            warning.message
        );
    }
    match compiled.output {
        Ok(document) => Ok(document),
        Err(errors) => bail!(
            "the Typst reader template did not compile:\n  {}",
            joined(
                errors
                    .iter()
                    .map(|e| format!(
                        "{}{}",
                        e.message,
                        if e.hints.is_empty() {
                            String::new()
                        } else {
                            format!(
                                " (hint: {})",
                                joined(e.hints.iter().map(|h| h.v.to_string()).collect())
                            )
                        }
                    ))
                    .collect()
            )
        ),
    }
}

type Run = (Point, Size);

fn flush(frame: &mut Frame, open: &mut Option<(Destination, Run, Vec<Run>)>) {
    if let Some((dest, (pos, size), inner)) = open.take() {
        frame.push(pos, FrameItem::Link(dest.clone(), size));
        for (pos, size) in inner {
            frame.push(pos, FrameItem::Link(dest.clone(), size));
        }
    }
}

fn weasyprint_links(frame: &mut Frame, at: &dyn Fn(Location) -> Option<PagedPosition>) {
    let items: Vec<_> = frame.items().cloned().collect();
    frame.clear();
    let mut open = None;
    for (pos, mut item) in items {
        let FrameItem::Link(dest, size) = &item else {
            if let FrameItem::Group(group) = &mut item {
                flush(frame, &mut open);
                weasyprint_links(&mut group.frame, at);
            }
            frame.push(pos, item);
            continue;
        };
        let (dest, inner) = match dest {
            Destination::Url(url) if url.ends_with(INLINE_LINK) => {
                let clean = url.trim_end_matches(INLINE_LINK);
                (
                    Destination::Url(Url::new(clean).expect("a url stays a url")),
                    true,
                )
            }
            Destination::Location(loc) => (
                at(*loc).map_or(dest.clone(), |p| {
                    Destination::Position(PagedPosition {
                        point: Point::new(p.point.x, p.point.y + Abs::pt(TYPST_DEST_LIFT)),
                        ..p
                    })
                }),
                false,
            ),
            other => (other.clone(), false),
        };
        match &mut open {
            Some((d, (p, s), _))
                if *d == dest
                    && p.y == pos.y
                    && s.y == size.y
                    && (p.x + s.x - pos.x).abs() < Abs::pt(1e-6) =>
            {
                s.x += size.x
            }
            _ => {
                flush(frame, &mut open);
                open = Some((dest, (pos, *size), vec![]));
            }
        }
        if inner {
            open.as_mut().expect("a run is open").2.push((pos, *size));
        }
    }
    flush(frame, &mut open);
}

fn chip(size: Size, [tl, tr, br, bl]: [Abs; 4]) -> Curve {
    let (w, h) = (size.x, size.y);
    let k = |r: Abs| r * (1.0 - CHIP_KAPPA);
    let mut c = Curve::new();
    c.move_(Point::new(Abs::zero(), tl));
    c.cubic(
        Point::new(Abs::zero(), k(tl)),
        Point::new(k(tl), Abs::zero()),
        Point::new(tl, Abs::zero()),
    );
    c.line(Point::new(w - tr, Abs::zero()));
    c.cubic(
        Point::new(w - k(tr), Abs::zero()),
        Point::new(w, k(tr)),
        Point::new(w, tr),
    );
    c.line(Point::new(w, h - br));
    c.cubic(
        Point::new(w, h - k(br)),
        Point::new(w - k(br), h),
        Point::new(w - br, h),
    );
    c.line(Point::new(bl, h));
    c.cubic(
        Point::new(k(bl), h),
        Point::new(Abs::zero(), h - k(bl)),
        Point::new(Abs::zero(), h - bl),
    );
    c.close();
    c
}

fn is_chip(shape: &Shape) -> Option<&Curve> {
    match (&shape.geometry, &shape.fill) {
        (Geometry::Curve(curve), Some(Paint::Solid(color))) if color.to_vec4_u8() == CHIP_FILL => {
            Some(curve)
        }
        _ => None,
    }
}

fn mono(text: &TextItem) -> bool {
    text.font.info().family == "Geist Mono"
}

fn weasyprint_chips(frame: &mut Frame) {
    let near = |a: Abs, b: Abs| (a - b).abs() < Abs::pt(0.001);
    let mut pads = vec![];
    let mut runs = vec![];
    for (pos, item) in frame.items() {
        if let FrameItem::Text(text) = item {
            match (mono(text), text.text.as_str() == "\u{a0}") {
                (true, true) => pads.push((pos.x, pos.x + text.width())),
                (true, false) => runs.push((pos.x, pos.x + text.width())),
                _ => {}
            }
        }
    }
    let items: Vec<_> = frame.items().cloned().collect();
    frame.clear();
    for (mut pos, mut item) in items {
        match &mut item {
            FrameItem::Group(group) => weasyprint_chips(&mut group.frame),
            FrameItem::Shape(shape, _) => {
                if let Some(curve) = is_chip(shape) {
                    let bbox = curve.bbox(None).size();
                    let radius = match curve.0.first() {
                        Some(CurveItem::Move(p)) => p.y,
                        _ => Abs::zero(),
                    };
                    let (mut left, mut right) = (pos.x, pos.x + bbox.x);
                    let inside = runs.iter().filter(|(a, _)| *a >= left && *a < right);
                    let start = inside.clone().map(|r| r.0).fold(right, Abs::min);
                    let end = inside.map(|r| r.1).fold(left, Abs::max);
                    let opens = pads.iter().any(|(_, b)| near(*b, start));
                    let closes = pads.iter().any(|(a, _)| near(*a, end));
                    let pad = |on: bool| if on { Abs::pt(CHIP_PAD_X) } else { Abs::zero() };
                    left = start - pad(opens);
                    right = end + pad(closes);
                    let (l, r) = (
                        if opens { radius } else { Abs::zero() },
                        if closes { radius } else { Abs::zero() },
                    );
                    pos.x = left;
                    shape.geometry =
                        Geometry::Curve(chip(Size::new(right - left, bbox.y), [l, r, r, l]));
                }
            }
            _ => {}
        }
        frame.push(pos, item);
    }
}

type Placed = (Point, FrameItem);

#[derive(Default)]
struct Layers {
    backdrops: Vec<Placed>,
    layers: Vec<Vec<Placed>>,
}

fn labelled(tag: &Tag, name: &str) -> Option<Location> {
    match tag {
        Tag::Start(content, _)
            if content
                .label()
                .is_some_and(|l| l.resolve().as_str() == name) =>
        {
            content.location()
        }
        _ => None,
    }
}

fn translation(group: &GroupItem) -> Option<Point> {
    let t = group.transform;
    (group.clip.is_none()
        && Transform {
            tx: Abs::zero(),
            ty: Abs::zero(),
            ..t
        }
        .is_identity())
    .then(|| Point::new(t.tx, t.ty))
}

fn lift(frame: &mut Frame, at: Point, out: &mut Layers, backdrop: bool) {
    let items: Vec<_> = frame.items().cloned().collect();
    frame.clear();
    let mut open: Option<(Location, Vec<Placed>)> = None;
    let mut backdrops = vec![];
    for (pos, mut item) in items {
        if let Some((loc, layer)) = &mut open {
            let done = matches!(&item, FrameItem::Tag(Tag::End(end, ..)) if end == loc);
            layer.push((at + pos, item));
            if done {
                out.layers.extend(open.take().map(|(_, l)| l));
            }
            continue;
        }
        let inside = backdrop || !backdrops.is_empty();
        match &mut item {
            FrameItem::Tag(tag) => {
                if let Some(loc) = labelled(tag, LAYER) {
                    open = Some((loc, vec![(at + pos, item)]));
                    continue;
                }
                backdrops.extend(labelled(tag, BACKDROP));
                if let Tag::End(end, ..) = tag {
                    backdrops.retain(|b| b != end);
                }
            }
            FrameItem::Group(group) => {
                if let Some(shift) = translation(group) {
                    lift(&mut group.frame, at + pos + shift, out, inside);
                }
            }
            FrameItem::Shape(shape, _) if inside && is_chip(shape).is_none() => {
                out.backdrops.push((at + pos, item));
                continue;
            }
            _ => {}
        }
        frame.push(pos, item);
    }
    out.layers.extend(open.map(|(_, l)| l));
}

fn painted(mut items: Vec<Placed>, own: bool) -> Vec<Placed> {
    let head = own.then(|| items.remove(0));
    let mut frame = Frame::soft(Size::zero());
    frame.push_multiple(items);
    let mut out = Layers::default();
    lift(&mut frame, Point::zero(), &mut out, false);
    let mut all: Vec<Placed> = head.into_iter().collect();
    all.extend(out.backdrops);
    all.extend(frame.items().cloned());
    all.extend(out.layers.into_iter().flat_map(|l| painted(l, true)));
    all
}

fn unlink(frame: &mut Frame, at: Point, out: &mut Vec<Placed>) {
    let items: Vec<_> = frame.items().cloned().collect();
    frame.clear();
    for (pos, mut item) in items {
        match &mut item {
            FrameItem::Link(..) => {
                out.push((at + pos, item));
                continue;
            }
            FrameItem::Group(group) => {
                if let Some(shift) = translation(group) {
                    unlink(&mut group.frame, at + pos + shift, out);
                }
            }
            _ => {}
        }
        frame.push(pos, item);
    }
}

fn weasyprint_paint_order(frame: &mut Frame) {
    let items: Vec<_> = frame.items().cloned().collect();
    let foreground = items
        .iter()
        .rposition(|(_, i)| matches!(i, FrameItem::Group(_)))
        .unwrap_or(items.len());
    let (body, furniture) = items.split_at(foreground);
    let mut links = vec![];
    let mut tree = Frame::soft(Size::zero());
    tree.push_multiple(body.to_vec());
    unlink(&mut tree, Point::zero(), &mut links);
    frame.clear();
    frame.push_multiple(painted(tree.items().cloned().collect(), false));
    frame.push_multiple(links);
    frame.push_multiple(furniture.to_vec());
}

pub fn pdf(document: &PagedDocument) -> Result<Vec<u8>> {
    let mut pages = document.pages().to_vec();
    let at = |loc| document.introspector().position(loc);
    for page in &mut pages {
        if text_shim::WEASYPRINT_69 {
            text_shim::weasyprint_text(&mut page.frame);
        }
        weasyprint_links(&mut page.frame, &at);
        weasyprint_chips(&mut page.frame);
        weasyprint_paint_order(&mut page.frame);
    }
    let document = PagedDocument::new(pages.into(), document.info().clone());
    let options = PdfOptions {
        ident: Smart::Custom(IDENT.to_string()),
        creator: Smart::Custom(Some(IDENT.to_string())),
        timestamp: None,
        page_ranges: None,
        standards: PdfStandards::default(),
        tagged: false,
        pretty: false,
    };
    let bytes = typst_pdf::pdf(&document, &options).map_err(|errors| {
        anyhow::anyhow!(
            "PDF export failed:\n  {}",
            joined(errors.iter().map(|e| e.message.to_string()).collect())
        )
    })?;
    weasyprint_annotations(&bytes)
}

fn open_outline(doc: &mut lopdf::Document, id: ObjectId) -> Result<i64> {
    let mut count = 0;
    let mut child = doc.get_dictionary(id)?.get(b"First").ok().cloned();
    while let Some(Object::Reference(kid)) = child {
        count += 1 + open_outline(doc, kid)?;
        child = doc.get_dictionary(kid)?.get(b"Next").ok().cloned();
    }
    doc.get_dictionary_mut(id)?.set("Count", count);
    Ok(count)
}

fn weasyprint_annotations(bytes: &[u8]) -> Result<Vec<u8>> {
    let mut doc = lopdf::Document::load_mem(bytes)?;
    for object in doc.objects.values_mut() {
        if let Ok(dict) = object.as_dict_mut() {
            if dict.get(b"Subtype").and_then(Object::as_name).ok() == Some(b"Link") {
                dict.remove(b"Border");
                dict.remove(b"F");
                dict.set("BS", lopdf::dictionary! { "W" => 0 });
            }
        }
    }
    if let Ok(root) = doc
        .catalog()?
        .get(b"Outlines")
        .and_then(Object::as_reference)
    {
        open_outline(&mut doc, root)?;
    }
    let mut out = Vec::new();
    doc.save_to(&mut out)?;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::{pipeline, File, Inputs};
    use lopdf::{Document, Object};
    use std::collections::BTreeSet;
    use std::path::PathBuf;
    use typst::visualize::{FillRule, Paint};

    const OLD_QUOTE_RULE: &str = "grid(\n      columns: (QUOTE-RULE, QUOTE-PAD, 1fr),\n      \
        rect(width: QUOTE-RULE, height: 100%, fill: VIOLET, stroke: none),\n      [],\n      \
        body,\n    )";

    const A5: [f64; 4] = [0.0, 0.0, 419.527_559_055_118_1, 595.275_590_551_181_1];
    const BOX_TOLERANCE_PT: f64 = 0.05;
    const MEASURE_FLOOR_PT: f64 = 325.010_000;
    const MEASURE_CEILING_PT: f64 = 325.040_000;

    fn roots() -> (&'static Path, &'static Path) {
        let crate_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo = crate_dir
            .parent()
            .expect("the crate sits inside the repository");
        (
            Box::leak(
                crate_dir
                    .join("tests/typeset_fixtures/corpus")
                    .into_boxed_path(),
            ),
            Box::leak(repo.join(FONT_DIR).into_boxed_path()),
        )
    }

    fn fixture_tree(edition_id: &'static str) -> Tree {
        let (root, font_dir) = roots();
        pipeline(&Inputs {
            root,
            edition_id,
            publication_name: "Fixture Press",
            fonts: font_dir,
            allow_missing_art: false,
            allow_unanchored_figures: false,
        })
        .expect("the fixture edition loads")
    }

    fn fixture_pdf(edition_id: &'static str) -> Vec<u8> {
        let (_, font_dir) = roots();
        let tree = fixture_tree(edition_id);
        compile(&world(&tree, font_dir).expect("the world builds")).expect("the fixture compiles")
    }

    fn media_boxes(pdf: &[u8]) -> Vec<[f64; 4]> {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        doc.get_pages()
            .values()
            .map(|id| {
                let array = doc
                    .get_dictionary(*id)
                    .and_then(|page| page.get(b"MediaBox"))
                    .and_then(Object::as_array)
                    .expect("every page carries a MediaBox")
                    .clone();
                let mut out = [0.0; 4];
                for (slot, value) in out.iter_mut().zip(&array) {
                    *slot = value.as_float().map(f64::from).unwrap_or_else(|_| {
                        value.as_i64().expect("a box coordinate is a number") as f64
                    });
                }
                out
            })
            .collect()
    }

    fn pages_off_the_box(pdf: &[u8], expected: [f64; 4], tolerance: f64) -> usize {
        media_boxes(pdf)
            .into_iter()
            .filter(|found| {
                found
                    .iter()
                    .zip(&expected)
                    .any(|(a, b)| (a - b).abs() > tolerance)
            })
            .count()
    }

    fn synthetic(main: String) -> Tree {
        Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: main,
            }],
        }
    }

    fn pages_of(tree: &Tree, template: &str) -> Result<usize> {
        let (_, font_dir) = roots();
        let world = Sources::new(tree, template, ROOT_TYP, font_dir)?;
        Ok(media_boxes(&compile(&world)?).len())
    }

    fn prose(lines: usize) -> String {
        (0..lines)
            .map(|n| format!("#doc-paragraph(standfirst: false, roster: false)[Line {n}.]\n"))
            .collect()
    }

    fn heading_run(paragraphs: usize) -> Tree {
        synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             {}#doc-heading(level: 2)[A heading]\n]\n",
            prose(paragraphs)
        ))
    }

    fn zeroed_clearance() -> String {
        TEMPLATE_TYP.replace(
            "#let HEADING-CLEARANCE = 25pt",
            "#let HEADING-CLEARANCE = 0pt",
        )
    }

    fn declared(name: &str) -> f64 {
        let needle = format!("#let {name} = ");
        let line = TEMPLATE_TYP
            .lines()
            .find(|line| line.starts_with(&needle))
            .unwrap_or_else(|| panic!("template.typ declares no {name}"));
        line[needle.len()..]
            .trim_end_matches("pt")
            .parse()
            .unwrap_or_else(|error| panic!("{name} is not a plain pt constant: {error}"))
    }

    fn called(tree: &Tree) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        for file in &tree.files {
            let mut rest = file.source.as_str();
            while let Some(at) = rest.find('#') {
                rest = &rest[at + 1..];
                let name: String = rest
                    .chars()
                    .take_while(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == '-')
                    .collect();
                if name.len() > 1 {
                    out.insert(name);
                }
            }
        }
        for own in ["include", "import", "set", "strong", "emph"] {
            out.remove(own);
        }
        out
    }

    fn undefined(names: &BTreeSet<String>) -> Vec<String> {
        names
            .iter()
            .filter(|name| !TEMPLATE_TYP.contains(&format!("#let {name}(")))
            .cloned()
            .collect()
    }

    #[test]
    fn the_template_defines_every_function_the_fixture_editions_call() {
        let mut names = BTreeSet::new();
        for edition_id in ["900", "901"] {
            names.extend(called(&fixture_tree(edition_id)));
        }
        assert!(
            names.len() >= 20,
            "the fixtures only call {} functions, too few to cover the seam",
            names.len()
        );
        assert_eq!(undefined(&names), Vec::<String>::new());
        let mut invented = names.clone();
        invented.insert("no-such-template-function".to_string());
        assert_eq!(
            undefined(&invented),
            vec!["no-such-template-function".to_string()],
            "the missing-function check cannot discriminate"
        );
    }

    #[test]
    fn the_fixture_editions_compile_to_a5_pages() {
        for edition_id in ["900", "901"] {
            let pdf = fixture_pdf(edition_id);
            let boxes = media_boxes(&pdf);
            assert!(
                !boxes.is_empty(),
                "edition {edition_id} compiled to no pages"
            );
            assert_eq!(
                pages_off_the_box(&pdf, A5, BOX_TOLERANCE_PT),
                0,
                "edition {edition_id} has pages off the A5 box; first is {:?}",
                boxes[0]
            );
        }
    }

    #[test]
    fn the_a5_page_box_check_discriminates() {
        let pdf = fixture_pdf("900");
        let pages = media_boxes(&pdf).len();
        let one_point_wider = [A5[0], A5[1], A5[2] + 1.0, A5[3]];
        assert_eq!(
            pages_off_the_box(&pdf, one_point_wider, BOX_TOLERANCE_PT),
            pages,
            "a 1pt-wider expectation must fail on every page"
        );
        let a4 = [0.0, 0.0, 595.275_590_551_181_1, 841.889_763_779_527_5];
        assert_eq!(
            pages_off_the_box(&pdf, a4, BOX_TOLERANCE_PT),
            pages,
            "an A4 expectation must fail on every page"
        );
    }

    #[test]
    fn the_body_measure_straddles_wp17s_admissible_window() {
        let measure = declared("MEASURE");
        let delta = declared("MEASURE-DELTA");
        assert_eq!(measure, 325.0);
        assert_eq!(delta, 0.025);
        let widened = measure + delta;
        assert!(
            (MEASURE_FLOOR_PT..MEASURE_CEILING_PT).contains(&widened),
            "{widened} is outside WP-1.7's admissible window"
        );
        assert!(measure < MEASURE_FLOOR_PT, "the unwidened column must fail");
        assert!(
            measure + 0.05 >= MEASURE_CEILING_PT,
            "a 0.05pt widening must fail"
        );
    }

    #[test]
    fn the_heading_clearance_reserves_twenty_five_points_below_a_heading() {
        let moved: Vec<usize> = (24..40)
            .filter(|paragraphs| {
                let tree = heading_run(*paragraphs);
                pages_of(&tree, TEMPLATE_TYP).expect("the reserved run compiles")
                    > pages_of(&tree, &zeroed_clearance()).expect("the zeroed run compiles")
            })
            .collect();
        assert!(
            !moved.is_empty(),
            "no paragraph count put a heading inside the 25pt reservation"
        );
        assert_eq!(
            declared("HEADING-CLEARANCE"),
            25.0,
            "the reservation drifted from weasyprint-a5.css:522"
        );
    }

    #[test]
    fn a_short_quote_does_not_swallow_the_rest_of_its_page() {
        let tree = synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             #doc-quote[#doc-paragraph(standfirst: false, roster: false)[Quoted.]]\n{}]\n",
            prose(10)
        ));
        assert_eq!(
            pages_of(&tree, TEMPLATE_TYP).expect("the ruled quote compiles"),
            5,
            "a two-line quote and ten short lines must fit the four blank outer pages plus one"
        );
        let swallowing = TEMPLATE_TYP.replace("ruled(QUOTE-PAD, 0pt, none, body)", OLD_QUOTE_RULE);
        assert_ne!(swallowing, TEMPLATE_TYP, "the quote call site moved");
        assert!(
            pages_of(&tree, &swallowing).expect("the swallowing quote compiles") > 5,
            "the 100% rule must fail this test, or it does not discriminate"
        );
    }

    #[test]
    fn the_page_cap_refuses_an_article_past_seven_reader_pages() {
        let (_, font_dir) = roots();
        let tree = fixture_tree("901");
        let capped = TEMPLATE_TYP.replace("#let ARTICLE-PAGE-CAP = 7", "#let ARTICLE-PAGE-CAP = 1");
        assert_ne!(capped, TEMPLATE_TYP, "the cap constant moved");
        let world = Sources::new(&tree, &capped, ROOT_TYP, font_dir).expect("the world builds");
        let error = compile(&world).expect_err("a one-page cap must refuse the fixture");
        assert!(
            error.to_string().contains("the hard cap is 1"),
            "the refusal names something else: {error}"
        );
        assert_eq!(declared("ARTICLE-PAGE-CAP"), 7.0);
        assert_eq!(declared("VERBATIM-PAGE-CAP"), 10.0);
    }

    #[test]
    fn a_verbatim_piece_is_not_refused_by_the_article_cap() {
        let (_, font_dir) = roots();
        let tree = synthetic(format!(
            "#piece(id: \"p\", kind: \"verbatim\", short-title: \"P\", opener: \"plain\")[\n{}]\n",
            prose(400)
        ));
        let capped = TEMPLATE_TYP.replace("#let ARTICLE-PAGE-CAP = 7", "#let ARTICLE-PAGE-CAP = 1");
        let world = Sources::new(&tree, &capped, ROOT_TYP, font_dir).expect("the world builds");
        assert!(
            compile(&world).is_ok(),
            "a verbatim overrun is a warning in render.py:2085-2091, never a refusal"
        );
        let article = synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n{}]\n",
            prose(400)
        ));
        let world = Sources::new(&article, &capped, ROOT_TYP, font_dir).expect("the world builds");
        assert!(
            compile(&world).is_err(),
            "the same run under kind article must be refused, or the branch is vacuous"
        );
    }

    #[test]
    fn the_opener_title_is_set_with_its_tracking() {
        let (_, font_dir) = roots();
        let tree = fixture_tree("901");
        let untracked = TEMPLATE_TYP.replace(
            "#let OPENER-TITLE-TRACKING = -0.045",
            "#let OPENER-TITLE-TRACKING = 0",
        );
        assert_ne!(untracked, TEMPLATE_TYP, "the tracking constant moved");
        let render = |template: &str| {
            compile(&Sources::new(&tree, template, ROOT_TYP, font_dir).expect("the world builds"))
                .expect("the opener run compiles")
        };
        assert_ne!(
            render(TEMPLATE_TYP),
            render(&untracked),
            "OPENER-TITLE-TRACKING reaches no glyph on the illustrated opener"
        );
    }

    #[test]
    fn the_illustrated_opener_owns_its_own_page() {
        let (_, font_dir) = roots();
        let tree = fixture_tree("901");
        let plain = TEMPLATE_TYP.replace(
            "#let ILLUSTRATED = \"illustrated_paper_spots_v1\"",
            "#let ILLUSTRATED = \"never-matched-opener\"",
        );
        assert_ne!(plain, TEMPLATE_TYP, "the opener name moved");
        let illustrated = pages_of(&tree, TEMPLATE_TYP).expect("the illustrated run compiles");
        let flowed = Sources::new(&tree, &plain, ROOT_TYP, font_dir)
            .and_then(|world| compile(&world))
            .map(|pdf| media_boxes(&pdf).len())
            .expect("the flowed run compiles");
        assert!(
            illustrated > flowed,
            "break-after: page on the opener header must cost a page ({illustrated} vs {flowed})"
        );
    }

    fn phase(step: usize) -> (usize, usize) {
        (4 + step / 4, (step % 4) * 5)
    }

    fn figure_run(step: usize, layout: &str, figure: Option<&str>) -> Tree {
        let (paragraphs, lift) = phase(step);
        let figure = figure.map_or(String::new(), |pixels| {
            format!(
                "#figure-block(id: \"f\", source-id: \"s\", anchor: \"Anchor\", layout: \"{layout}\", \
                 word: \"Figure\", alt: \"a\", path: \"{}\"{pixels})[#figure-caption[Cap.]]\n",
                fixture_png()
            )
        });
        synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             {}#v({lift}pt)\n#doc-heading(level: 2)[Anchor]\n{figure}{}]\n",
            prose(paragraphs),
            prose(27)
        ))
    }

    fn sweep(range: std::ops::Range<usize>, make: impl Fn(usize) -> (Tree, Tree)) -> Vec<usize> {
        let mut moved = Vec::new();
        for n in range {
            let (more, less) = make(n);
            let (a, b) = (
                pages_of(&more, TEMPLATE_TYP).expect("the first run compiles"),
                pages_of(&less, TEMPLATE_TYP).expect("the second run compiles"),
            );
            assert!(
                a >= b,
                "at step {n} the run expected to be taller took fewer pages"
            );
            if a > b {
                moved.push(n);
            }
        }
        moved
    }

    #[test]
    fn a_figure_carries_what_follows_to_the_next_page_when_four_lines_do_not_fit_under_it() {
        let bare = TEMPLATE_TYP.replace("  band-clearance()\n", "");
        assert_ne!(bare, TEMPLATE_TYP, "the clearance call moved");
        let tail = |n: usize| {
            let (paragraphs, lift) = phase(n);
            synthetic(format!(
                "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                 {}#v({lift}pt)\n#figure-block(id: \"f\", source-id: \"s\", anchor: \"A\", \
                 layout: \"evidence_band\", word: \"Figure\", alt: \"a\", path: \"{}\", \
                 pixels: (2400, 1350))[#figure-caption[Cap.]]\n#doc-paragraph[Tail words.]\n]\n",
                prose(paragraphs),
                fixture_png()
            ))
        };
        let carried: Vec<usize> = (0..64)
            .filter(|&n| {
                let with = pages_of(&tail(n), TEMPLATE_TYP).expect("it compiles");
                let without = pages_of(&tail(n), &bare).expect("it compiles");
                assert!(with >= without, "step {n}: the clearance saved a page");
                with > without
            })
            .collect();
        assert!(!carried.is_empty(), "the clearance never carried the tail");
        assert!(
            carried.len() < 64,
            "the clearance carried the tail every time"
        );
    }

    #[test]
    fn a_figure_reserves_the_image_height_its_pixel_ratio_fits() {
        let wide = Some(", pixels: (2400, 1350)");
        let tall = Some(", pixels: (2000, 1418)");
        let band = "evidence_band";
        let costs = sweep(0..64, |n| {
            (figure_run(n, band, wide), figure_run(n, band, None))
        });
        assert!(
            !costs.is_empty(),
            "no paragraph count made the figure cost a page"
        );
        let ratio = sweep(0..64, |n| {
            (figure_run(n, band, tall), figure_run(n, band, wide))
        });
        assert!(
            !ratio.is_empty(),
            "a height-limited and a width-limited figure never paginated differently"
        );
        let refused = pages_of(&figure_run(3, band, Some("")), TEMPLATE_TYP)
            .expect_err("a figure with no pixel size must refuse");
        assert!(
            refused.to_string().contains("carries no pixel size"),
            "{refused}"
        );
    }

    #[test]
    fn a_band_anchor_heading_follows_its_paragraph_on_the_space_after_alone() {
        let square = Some(", pixels: (1000, 1000)");
        let moved = sweep(0..64, |n| {
            (
                figure_run(n, "column_plate", square),
                figure_run(n, "evidence_band", square),
            )
        });
        assert!(
            !moved.is_empty(),
            "dropping the anchor heading's space-before never changed the pagination"
        );
    }

    fn laid(tree: &Tree, template: &str) -> Vec<Vec<Mark>> {
        let (_, font_dir) = roots();
        let world = Sources::new(tree, template, ROOT_TYP, font_dir).expect("the world builds");
        document(&world)
            .expect("the run compiles")
            .pages()
            .iter()
            .map(|page| {
                let mut out = vec![];
                marks(&page.frame, Point::zero(), &mut out);
                out
            })
            .collect()
    }

    fn heading_and_label(tree: &Tree, template: &str) -> [(usize, f64); 3] {
        let pages = laid(tree, template);
        let find = |keep: &dyn Fn(&Mark) -> bool| {
            pages
                .iter()
                .enumerate()
                .find_map(|(n, page)| page.iter().find(|m| keep(m)).map(|m| (n + 1, m.x)))
                .expect("the mark is laid")
        };
        [
            find(&|m| m.text == "Anchor" && (m.size - 18.5).abs() < 1e-6),
            find(&|m| m.text == "Cap." || m.text.starts_with("FIGURE")),
            find(&|m| m.text == "Line 0."),
        ]
    }

    #[test]
    fn an_editorial_opener_spans_the_live_width_and_wraps_on_it() {
        let run = |wide: bool| {
            let tree = synthetic(format!(
                "#piece(id: \"editorial\", kind: \"original_editorial\", short-title: \"E\")[\n\
                 #plain-opener(size: 35pt, field: 153.2756pt, title: \"Upkeep Scaled Quickly\", \
                 wide: {wide})[\n#content-label[#label-primary[Editorial]]\n\
                 #piece-title[Upkeep Scaled Quickly]\n\
                 #byline(code: none)[#byline-prefix[By]#byline-name[ The Editors]]\n]\n\
                 #doc-paragraph(standfirst: true, roster: false)[Standfirst words.]\n]\n"
            ));
            let page: Vec<Mark> = laid(&tree, TEMPLATE_TYP).into_iter().flatten().collect();
            let at = |keep: &dyn Fn(&Mark) -> bool| {
                page.iter()
                    .filter(|m| keep(m))
                    .map(|m| (m.x, m.y))
                    .collect::<Vec<_>>()
            };
            [
                at(&|m| m.text.starts_with("EDITORIAL")),
                at(&|m| (m.size - 35.0).abs() < 1e-6),
                at(&|m| m.text == "BY"),
                at(&|m| m.text.starts_with("Standfirst")),
            ]
        };
        let [label, title, byline, standfirst] = run(true);
        let rail = 4.00395;
        assert_eq!(title.len(), 1, "one line on the 333pt live width");
        for (x, _) in [label[0], title[0], byline[0]] {
            assert!(
                (x + rail - standfirst[0].0).abs() < 1e-3,
                "{x} vs {standfirst:?}"
            );
        }
        let [_, narrow, low, prose] = run(false);
        assert_eq!(narrow.len(), 2, "two lines on the 325pt article measure");
        assert!((narrow[0].0 - prose[0].0).abs() < 1e-3);
        assert!((low[0].1 - byline[0].1 - 35.0 * 0.96).abs() < 1e-3);
        assert!(
            (prose[0].1 - standfirst[0].1).abs() < 1e-3,
            "the field holds the standfirst"
        );
    }

    #[test]
    fn a_heading_goes_to_the_next_page_with_the_figure_it_anchors() {
        let loose = TEMPLATE_TYP.replace(
            "sticky: next-flow(index).kind == \"figure\",",
            "sticky: false,",
        );
        assert_ne!(loose, TEMPLATE_TYP, "the sticky rule moved");
        let wide = Some(", pixels: (2400, 1350)");
        let mut parted = vec![];
        for n in 0..64 {
            for layout in ["evidence_band", "column_plate"] {
                let tree = figure_run(n, layout, wide);
                let [heading, label, _] = heading_and_label(&tree, TEMPLATE_TYP);
                assert_eq!(heading.0, label.0, "step {n}, {layout}");
                let [heading, label, _] = heading_and_label(&tree, &loose);
                if heading.0 != label.0 {
                    parted.push(n);
                }
            }
        }
        assert!(
            !parted.is_empty(),
            "no step left the heading behind without sticky"
        );
        let extract = |n: usize| {
            let (paragraphs, lift) = phase(n);
            synthetic(format!(
                "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                 {}#v({lift}pt)\n#doc-heading(level: 2)[Anchor]\n#extract(id: \"e\", source-id: \"s\", \
                 anchor: \"Anchor\", style: \"quote\", word: \"Figure\")[#quote-line[{}]]\n{}]\n",
                prose(paragraphs),
                "Quoted words. ".repeat(60),
                prose(27)
            ))
        };
        assert!(
            (0..64).any(|n| {
                let [heading, label, _] = heading_and_label(&extract(n), TEMPLATE_TYP);
                heading.0 < label.0
            }),
            "a heading before an extract keeps its clearance break, as the adapter's does"
        );
    }

    #[test]
    fn a_band_carried_past_its_bridge_keeps_the_bridge_page_s_left_edge_as_the_adapter_does() {
        let left = |page: usize| if page % 2 == 1 { 44.0 } else { 42.5197 };
        let wide = Some(", pixels: (2400, 1350)");
        let (mut carried, mut stayed) = (0, 0);
        for n in 0..64 {
            let [heading, label, first] =
                heading_and_label(&figure_run(n, "evidence_band", wide), TEMPLATE_TYP);
            let [plain, column, _] =
                heading_and_label(&figure_run(n, "column_plate", wide), TEMPLATE_TYP);
            let bridge = heading.0 - usize::from(heading.0 > first.0);
            assert!((label.1 - left(bridge)).abs() < 1e-3, "step {n}: {label:?}");
            assert!(
                (column.1 - left(plain.0) - 4.004).abs() < 1e-3,
                "step {n}: {column:?}"
            );
            carried += usize::from(heading.0 > first.0 && heading.0 % 2 == 0);
            stayed += usize::from(heading.0 == first.0 && first.0 % 2 == 1);
        }
        assert!(
            carried > 0 && stayed > 0,
            "{carried} carried, {stayed} stayed"
        );
    }

    #[test]
    fn a_jpeg_figure_is_embedded_as_its_own_bytes_exif_and_all() {
        let (_, font_dir) = roots();
        let path = format!(
            "{}/tests/typeset_fixtures/media/exif.jpg",
            env!("CARGO_MANIFEST_DIR")
        );
        let bytes = std::fs::read(&path).expect("the fixture reads");
        assert!(
            bytes.windows(4).any(|w| w == b"Exif"),
            "the fixture lost its EXIF segment"
        );
        let tree = synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             #doc-heading(level: 2)[Anchor]\n#figure-block(id: \"f\", source-id: \"s\", anchor: \"Anchor\", \
             layout: \"evidence_band\", word: \"Figure\", alt: \"a\", path: \"{path}\", pixels: (24, 16))\
             [#figure-caption[Cap.]]\n]\n"
        ));
        let pdf = compile(&world(&tree, font_dir).expect("the world builds")).expect("it compiles");
        let doc = Document::load_mem(&pdf).expect("the emitted bytes are a PDF");
        let embedded: Vec<&[u8]> = doc
            .objects
            .values()
            .filter_map(|object| object.as_stream().ok())
            .filter(|stream| {
                stream.dict.get(b"Filter").and_then(Object::as_name).ok()
                    == Some(b"DCTDecode".as_slice())
            })
            .map(|stream| stream.content.as_slice())
            .collect();
        assert_eq!(embedded, vec![bytes.as_slice()]);
    }

    fn fixture_png() -> String {
        format!(
            "{}/tests/typeset_fixtures/media/landscape.png",
            env!("CARGO_MANIFEST_DIR")
        )
    }

    fn pages_where(pdf: &[u8], keep: impl Fn(&[u8]) -> bool) -> Vec<usize> {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        doc.get_pages()
            .into_iter()
            .filter(|(_, id)| keep(&doc.get_page_content(*id)))
            .map(|(number, _)| number as usize)
            .collect()
    }

    fn blank_pages(pdf: &[u8]) -> Vec<usize> {
        pages_where(pdf, |content| content.len() < 16)
    }

    fn plate_pages(pdf: &[u8]) -> Vec<usize> {
        pages_where(pdf, |content| content.windows(3).any(|w| w == b" Do"))
    }

    fn plated(articles: usize, plates: usize) -> Tree {
        let pieces: String = (1..=articles)
            .map(|n| {
                format!(
                    "#piece(id: \"article-p{n}\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                     #doc-paragraph(standfirst: false, roster: false)[Piece {n}.]\n]\n\
                     #plates-after({n}, of: {articles})\n"
                )
            })
            .collect();
        let plates: String = (1..=plates)
            .map(|n| {
                let art = if n == 1 { "landscape.png" } else { "portrait.jpg" };
                format!(
                    "#closing-plate(index: {n}, alt: \"Plate {n}\", path: \"{}/tests/typeset_fixtures/media/{art}\")\n",
                    env!("CARGO_MANIFEST_DIR")
                )
            })
            .collect();
        synthetic(plates + "#closing-signature(none)\n" + &pieces)
    }

    fn first_plate_page(pdf: &[u8]) -> Vec<usize> {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        doc.get_pages()
            .into_iter()
            .filter(|(_, id)| {
                doc.get_page_images(*id)
                    .expect("page images")
                    .iter()
                    .any(|image| image.width == 40)
            })
            .map(|(number, _)| number as usize)
            .collect()
    }

    #[test]
    fn closing_plates_close_the_signature_in_the_adapter_s_slots_and_order() {
        let (_, font_dir) = roots();
        let paged = |articles, plates| {
            paginate(plated(articles, plates), font_dir, Hyphenation::PARITY)
                .map(|(_, doc)| pdf(&doc).expect("a PDF"))
        };
        let pdf = paged(2, 7).expect("the plated run compiles");
        assert_eq!(plate_pages(&pdf), vec![4, 5, 6, 8, 9, 10]);
        assert_eq!(first_plate_page(&pdf), vec![10]);
        assert_eq!(blank_pages(&pdf), vec![1, 2, 11, 12]);
        let nine = paged(9, 7).expect("seven plates compile");
        assert_eq!(plate_pages(&nine), vec![4, 7, 9, 11, 13, 16, 18]);
        assert_eq!(blank_pages(&nine), vec![1, 2, 19, 20]);
        let short = paged(9, 6).expect_err("six plates cannot close a nine-article signature");
        assert!(
            format!("{short:#}").contains("needs 7 closing plates"),
            "{short:#}"
        );
        let unpaged =
            compile(&Sources::new(&plated(2, 7), TEMPLATE_TYP, ROOT_TYP, font_dir).unwrap())
                .expect("the bare run compiles");
        assert!(
            plate_pages(&unpaged).is_empty(),
            "plates print before the content is measured"
        );
    }

    fn straddling_run(before: usize) -> Tree {
        synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             {}#doc-paragraph(standfirst: false, roster: false)[{}]\n{}]\n",
            prose(before),
            "A long paragraph that runs on and on across the column. ".repeat(12),
            prose(26)
        ))
    }

    #[test]
    fn typst_prevents_orphans_and_widows_by_default_as_the_stylesheet_does() {
        let allowed = TEMPLATE_TYP.replace(
            "    hyphenate: false,\n    ..edges(BODY-SIZE, BODY-LEADING, HALF-SERIF),\n  )",
            "    hyphenate: false,\n    costs: (widow: 0%, orphan: 0%),\n    \
             ..edges(BODY-SIZE, BODY-LEADING, HALF-SERIF),\n  )",
        );
        assert_ne!(
            allowed, TEMPLATE_TYP,
            "the reader's text rule was not found"
        );
        let moved: Vec<usize> = (16..30)
            .filter(|before| {
                let tree = straddling_run(*before);
                let prevented = pages_of(&tree, TEMPLATE_TYP).expect("the default compiles");
                let permitted = pages_of(&tree, &allowed).expect("the zero-cost run compiles");
                assert!(prevented >= permitted);
                prevented > permitted
            })
            .collect();
        assert!(
            !moved.is_empty(),
            "no paragraph position made the default widow and orphan prevention move a line"
        );
    }

    #[test]
    fn the_architecture_constants_are_the_stylesheet_s_own() {
        for (name, value) in [
            ("RUNNING-BASELINE", 20.0),
            ("RUNNING-RULE", 0.55),
            ("RUNNING-RULE-TOP", 27.725),
            ("RUNNING-TICK", 1.15),
            ("RUNNING-TICK-TOP", 27.425),
            ("RUNNING-TICK-WIDTH", 14.0),
            ("CONTENTS-KICKER-TOP", -13.46915),
            ("CONTENTS-TITLE-TOP", 32.54098),
            ("CONTENTS-BAND-TOP", 74.2802),
            ("CONTENTS-BAND", 393.0),
            ("CONTENTS-RULE", 0.7),
            ("CONTENTS-ENTRY-LEFT", 47.0),
            ("OPENER-RAIL", 348.0),
            ("OPENER-ESCAPE", 11.5),
            ("OPENER-ART-HEIGHT", 207.1),
            ("OPENER-ART-LIFT", 12.0004),
            ("OPENER-FRAME-HEIGHT", 203.0),
            ("OPENER-OFFSET", 4.1),
            ("OPENER-BORDER", 2.4),
            ("OPENER-QR", 41.0),
            ("OPENER-META-MEASURE", 293.0),
        ] {
            assert_eq!(
                declared(name),
                value,
                "{name} drifted from weasyprint-a5.css"
            );
        }
        let band = declared("CONTENTS-BAND-TOP") + declared("CONTENTS-BAND");
        assert!(
            (band - 467.2802).abs() < 1e-9,
            "the contents band ends at {band}, not the stylesheet's 467.2802pt ol height"
        );
        let measure = declared("OPENER-RAIL") - declared("OPENER-QR") - declared("OPENER-GAP");
        assert!(
            (measure - declared("OPENER-META-MEASURE")).abs() < 1e-9,
            "the credit column measures {measure}, not the adapter's 293pt"
        );
        let escape = declared("MEASURE") + 2.0 * declared("OPENER-ESCAPE");
        assert!(
            (escape - declared("OPENER-RAIL")).abs() < 1e-9,
            "the 325pt measure escaped by 11.5pt a side is {escape}, not 348pt"
        );
    }

    #[test]
    fn the_page_frame_constants_are_the_stylesheet_s_own() {
        for (name, value) in [
            ("MARGIN-TOP", 42.0004),
            ("MARGIN-OUTER", 42.5197),
            ("MARGIN-BOTTOM", 54.9996),
            ("MARGIN-INNER", 44.0),
            ("DATUM", 10.0046),
            ("FOLIO-BASELINE", 19.5),
        ] {
            assert_eq!(
                declared(name),
                value,
                "{name} drifted from weasyprint-a5.css"
            );
        }
        let live = 419.527_559_055_118_1 - declared("MARGIN-INNER") - declared("MARGIN-OUTER");
        assert!(
            (live - 333.007_859_055_118_1).abs() < 1e-9,
            "the live width is {live}, not the stylesheet's 333.0079pt"
        );
        let content_height =
            595.275_590_551_181_1 - declared("MARGIN-TOP") - declared("MARGIN-BOTTOM");
        assert!(
            (content_height - 498.275_590_551_181_1).abs() < 1e-9,
            "the content height is {content_height}, not the reader's 498.2756pt"
        );
    }

    fn paints(frame: &Frame, out: &mut Vec<String>) {
        for (_, item) in frame.items() {
            match item {
                FrameItem::Group(group) => paints(&group.frame, out),
                FrameItem::Image(_, size, _) => {
                    out.push(format!("image {:.2}x{:.2}", size.x.to_pt(), size.y.to_pt()))
                }
                FrameItem::Shape(shape, _) => {
                    let size = shape.bbox(false).size();
                    let area = format!("{:.2}x{:.2}", size.x.to_pt(), size.y.to_pt());
                    if let Some(Paint::Solid(color)) = &shape.fill {
                        let [r, g, b, _] = color.to_vec4_u8();
                        let rule = match shape.fill_rule {
                            FillRule::EvenOdd => "evenodd",
                            FillRule::NonZero => "fill",
                        };
                        out.push(format!("{rule} {r},{g},{b} {area}"));
                    }
                    if shape.stroke.is_some() {
                        out.push(format!("stroke {area}"));
                    }
                }
                _ => {}
            }
        }
    }

    fn opener_paints(template: &str) -> Vec<String> {
        let (_, font_dir) = roots();
        let world = Sources::new(&fixture_tree("901"), template, ROOT_TYP, font_dir)
            .expect("the world builds");
        let document = document(&world).expect("the fixture compiles");
        document
            .pages()
            .iter()
            .map(|page| {
                let mut out = vec![];
                paints(&page.frame, &mut out);
                out
            })
            .find(|out| {
                out.iter()
                    .any(|p| p.starts_with("fill 240,87,56 348.00x203.00"))
            })
            .expect("one page carries the opener's orange offset")
    }

    #[test]
    fn the_illustrated_opener_paints_art_code_and_ring_in_the_oracle_order() {
        let found = opener_paints(TEMPLATE_TYP);
        let want = [
            "fill 240,87,56 14.50x2.40",
            "fill 240,87,56 348.00x203.00",
            "fill 200,192,179 348.00x1.00",
            "fill 255,255,255 41.00x41.00",
            "fill 14,19,22 ",
            "evenodd 23,25,28 348.00x203.00",
            "image 343.20x405.60",
        ];
        let mut at = 0;
        for paint in &found {
            if at < want.len() && paint.starts_with(want[at]) {
                at += 1;
            }
        }
        assert_eq!(at, want.len(), "paint order {found:?}");
        assert!(
            !found.iter().any(|p| p.starts_with("stroke")),
            "the opener strokes nothing: {found:?}"
        );
        let bare =
            opener_paints(&TEMPLATE_TYP.replace("opener-art(opener-part(rows, \"art\"))", "none"));
        assert!(
            !bare
                .iter()
                .any(|p| p.starts_with("image") || p.starts_with("evenodd")),
            "the check cannot tell a drawn opener from a bare one: {bare:?}"
        );
    }

    fn outline(pdf: &[u8]) -> (Option<String>, Vec<(usize, String)>) {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        let text = |o: &Object| match o {
            Object::String(bytes, _) => match bytes.strip_prefix(&[0xFE, 0xFF]) {
                Some(wide) => String::from_utf16_lossy(
                    &wide
                        .chunks(2)
                        .map(|c| u16::from_be_bytes([c[0], c[1]]))
                        .collect::<Vec<u16>>(),
                ),
                None => String::from_utf8_lossy(bytes).into_owned(),
            },
            _ => String::new(),
        };
        let title = doc
            .trailer
            .get(b"Info")
            .and_then(Object::as_reference)
            .and_then(|id| doc.get_dictionary(id))
            .and_then(|info| info.get(b"Title"))
            .map(text)
            .ok();
        let mut out = vec![];
        let mut stack: Vec<(usize, Option<&Object>)> = vec![];
        let root = doc
            .catalog()
            .and_then(|c| c.get(b"Outlines"))
            .and_then(Object::as_reference)
            .and_then(|id| doc.get_dictionary(id))
            .expect("the reader carries an outline");
        stack.push((1, root.get(b"First").ok()));
        while let Some((depth, next)) = stack.pop() {
            let Some(id) = next.and_then(|o| o.as_reference().ok()) else {
                continue;
            };
            let entry = doc
                .get_dictionary(id)
                .expect("an outline entry is a dictionary");
            out.push((depth, entry.get(b"Title").map(text).unwrap_or_default()));
            stack.push((depth, entry.get(b"Next").ok()));
            stack.push((depth + 1, entry.get(b"First").ok()));
        }
        (title, out)
    }

    fn weasyprint_outline(tree: &Tree) -> Vec<(usize, String)> {
        let mut levels: Vec<usize> = vec![];
        let mut out = vec![];
        let calls = tree
            .files
            .iter()
            .flat_map(|f| f.source.lines())
            .filter_map(|line| {
                let line = line.trim();
                let text = |rest: &str| {
                    rest.trim_start_matches('[')
                        .trim_end_matches(']')
                        .replace('\\', "")
                };
                if let Some(rest) = line.strip_prefix("#doc-heading(level: ") {
                    let (level, rest) = rest.split_once(')').expect("a heading call closes");
                    let level = level.split(',').next().unwrap_or(level);
                    Some((level.parse::<usize>().expect("a numeric level"), text(rest)))
                } else if let Some(rest) = line.strip_prefix("#piece-title") {
                    Some((1, text(rest)))
                } else {
                    line.strip_prefix("#contents-label")
                        .map(|rest| (1, text(rest)))
                }
            });
        for (level, title) in calls {
            while levels.last().is_some_and(|&l| l >= level) {
                levels.pop();
            }
            levels.push(level);
            out.push((levels.len(), title));
        }
        out
    }

    #[test]
    fn the_reader_carries_its_title_and_a_bookmark_per_heading_nested_as_weasyprint_does() {
        let (_, font_dir) = roots();
        for edition_id in ["900", "901"] {
            let tree = fixture_tree(edition_id);
            let pdf =
                compile(&world(&tree, font_dir).expect("the world builds")).expect("it compiles");
            let (title, found) = outline(&pdf);
            let want = weasyprint_outline(&tree);
            assert!(want.len() >= 3, "fixture {edition_id} carries {want:?}");
            assert!(
                want.iter().any(|w| w.0 == 2),
                "fixture {edition_id} never nests: {want:?}"
            );
            assert_eq!(found, want, "fixture {edition_id}");
            let title = title.expect("the reader carries a title");
            assert!(
                title.starts_with("Fixture Press: ") && title.len() > "Fixture Press: ".len(),
                "{title}"
            );
        }
    }

    fn descendants(doc: &Document, id: ObjectId, bad: &mut Vec<String>) -> i64 {
        let node = doc.get_dictionary(id).expect("an outline node");
        let mut total = 0;
        let mut child = node.get(b"First").and_then(Object::as_reference).ok();
        while let Some(kid) = child {
            total += 1 + descendants(doc, kid, bad);
            child = doc
                .get_dictionary(kid)
                .and_then(|k| k.get(b"Next"))
                .and_then(Object::as_reference)
                .ok();
        }
        if node.get(b"Count").and_then(Object::as_i64).ok() != Some(total) {
            bad.push(format!(
                "{id:?} holds {:?} for {total}",
                node.get(b"Count").ok()
            ));
        }
        total
    }

    fn links(pdf: &[u8]) -> (Document, Vec<lopdf::Dictionary>) {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        let found = doc
            .objects
            .values()
            .filter_map(|o| o.as_dict().ok())
            .filter(|d| d.get(b"Subtype").and_then(Object::as_name).ok() == Some(b"Link"))
            .cloned()
            .collect();
        (doc, found)
    }

    #[test]
    fn links_and_bookmarks_are_written_as_weasyprint_writes_them() {
        for (edition_id, top) in [("903", 553.275_591), ("902", 565.275_591)] {
            let (doc, found) = links(&fixture_pdf(edition_id));
            let internal: Vec<f64> = found
                .iter()
                .filter_map(|d| {
                    d.get(b"Dest")
                        .or_else(|_| {
                            d.get(b"A")
                                .and_then(Object::as_dict)
                                .and_then(|a| a.get(b"D"))
                        })
                        .ok()
                        .and_then(|o| doc.dereference(o).ok())
                        .and_then(|(_, o)| o.as_array().ok())
                })
                .map(|dest| dest[3].as_float().expect("an XYZ top") as f64)
                .collect();
            assert!(internal.len() >= 3, "fixture {edition_id}: {internal:?}");
            assert!(
                internal.iter().all(|y| (y - top).abs() < 0.001),
                "fixture {edition_id} links to {internal:?}, not the piece top {top}"
            );
            for link in &found {
                assert_eq!(
                    (link.get(b"BS").ok(), link.has(b"Border"), link.has(b"F")),
                    (
                        Some(&Object::from(lopdf::dictionary! { "W" => 0 })),
                        false,
                        false
                    ),
                    "fixture {edition_id}: {link:?}"
                );
            }
            let root = doc
                .catalog()
                .and_then(|c| c.get(b"Outlines"))
                .and_then(Object::as_reference)
                .expect("an outline");
            let mut bad = vec![];
            assert!(descendants(&doc, root, &mut bad) >= 3);
            assert!(bad.is_empty(), "fixture {edition_id} collapses {bad:?}");
        }
        let (_, raw) = links(
            &typst_pdf::pdf(
                &document(&world(&fixture_tree("902"), roots().1).expect("the world builds"))
                    .expect("it compiles"),
                &PdfOptions::default(),
            )
            .expect("it exports"),
        );
        assert!(
            raw.iter().all(|l| l.has(b"Border")),
            "the unpatched export already writes WeasyPrint's links"
        );
    }

    fn chips(frame: &Frame, at: Point, out: &mut Vec<(f64, f64, Vec<CurveItem>)>) {
        for (pos, item) in frame.items() {
            match item {
                FrameItem::Group(group) => chips(&group.frame, at + *pos, out),
                FrameItem::Shape(shape, _) => {
                    if let Some(curve) = is_chip(shape) {
                        let x = (at + *pos).x.to_pt();
                        let w = curve.bbox(None).size().x.to_pt();
                        out.push((x, x + w, curve.0.clone()));
                    }
                }
                _ => {}
            }
        }
    }

    #[test]
    fn an_inline_code_chip_broken_across_lines_is_sliced_as_weasyprint_slices_it() {
        let tree = synthetic(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             Some words that run along the measure of the line until #inline-code[Mozilla/5.0 \
             (CVE-2026-66066 security verification)] breaks, and a #inline-code[short] one.\n]\n"
                .to_string(),
        );
        let doc =
            document(&world(&tree, roots().1).expect("the world builds")).expect("it compiles");
        let page = doc
            .pages()
            .iter()
            .find(|p| p.frame.items().next().is_some())
            .expect("a page carries the piece");
        let text = |frame: &Frame| {
            let mut found = vec![];
            marks(frame, Point::zero(), &mut found);
            found
        };
        let mut before = vec![];
        chips(&page.frame, Point::zero(), &mut before);
        let mut frame = page.frame.clone();
        weasyprint_chips(&mut frame);
        let mut after = vec![];
        chips(&frame, Point::zero(), &mut after);
        let words = text(&frame);
        let start = |t: &str| words.iter().find(|m| m.text.starts_with(t)).expect(t).x;
        let end = |t: &str| {
            let m = words.iter().find(|m| m.text.starts_with(t)).expect(t);
            m.x + m.width
        };
        let corners = |c: &[CurveItem]| -> Vec<f64> {
            c.iter()
                .filter_map(|i| match i {
                    CurveItem::Cubic(a, _, e) => {
                        Some((e.x - a.x).abs().max((e.y - a.y).abs()).to_pt())
                    }
                    _ => None,
                })
                .collect()
        };
        let handle = |c: &[CurveItem]| match (&c[0], &c[1]) {
            (CurveItem::Move(m), CurveItem::Cubic(a, _, _)) => (m.y - a.y).to_pt(),
            _ => f64::NAN,
        };
        assert_eq!(after.len(), 3, "{before:?}");
        let broken = [
            (after[0].0, before[0].0),
            (after[0].1, end("Mozilla/5.0")),
            (after[1].0, start("(CVE")),
            (after[1].1, before[1].1),
            (after[2].0, before[2].0),
            (after[2].1, before[2].1),
        ];
        assert!(
            broken.iter().all(|(a, b)| (a - b).abs() < 1e-3),
            "{broken:?}"
        );
        assert!(
            before[0].1 - after[0].1 > 2.9 && after[1].0 - before[1].0 > 2.9,
            "{before:?}"
        );
        let quarter = |c: f64| (c * 1e4).round() / 1e4;
        assert_eq!(
            corners(&after[0].2)
                .into_iter()
                .map(quarter)
                .collect::<Vec<_>>(),
            [2.0, 0.0, 0.0, 2.0]
        );
        assert_eq!(
            corners(&after[1].2)
                .into_iter()
                .map(quarter)
                .collect::<Vec<_>>(),
            [0.0, 2.0, 2.0, 0.0]
        );
        assert_eq!(
            corners(&after[2].2)
                .into_iter()
                .map(quarter)
                .collect::<Vec<_>>(),
            [2.0; 4]
        );
        assert!((handle(&after[2].2) - 1.1).abs() < 1e-9, "{:?}", after[2].2);
        assert!(
            (handle(&before[2].2) - 1.1).abs() > 0.004,
            "typst already draws WeasyPrint's arcs"
        );
    }

    fn sequence(frame: &Frame, out: &mut Vec<String>) {
        for (_, item) in frame.items() {
            match item {
                FrameItem::Group(group) => sequence(&group.frame, out),
                FrameItem::Text(text) if text.text.trim().len() > 2 => out.push(
                    text.text
                        .split_whitespace()
                        .next()
                        .unwrap_or("")
                        .to_string(),
                ),
                FrameItem::Shape(shape, _) => out.push(match &shape.fill {
                    Some(Paint::Solid(c)) => format!("fill {:?}", &c.to_vec4_u8()[..3]),
                    _ => "stroke".to_string(),
                }),
                _ => {}
            }
        }
    }

    #[test]
    fn a_page_paints_backdrops_first_and_positioned_boxes_after_its_flow_as_weasyprint_does() {
        let tree = synthetic(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             #doc-paragraph[Alpha opens the page.]\n\
             #doc-quote[#doc-paragraph[Quoted words sit in the rule.]]\n\
             #doc-list(ordered: false, start: 1, references: false)[\n\
             #doc-item[Bullet one reads here.]\n#doc-item[Bullet two reads here.]\n]\n\
             #doc-heading(level: 2)[Heading after the list]\n\
             #doc-paragraph[Omega closes the page.]\n]\n"
                .to_string(),
        );
        let doc =
            document(&world(&tree, roots().1).expect("the world builds")).expect("it compiles");
        let page = doc
            .pages()
            .iter()
            .find(|p| {
                let mut s = vec![];
                sequence(&p.frame, &mut s);
                s.iter().any(|w| w == "Alpha")
            })
            .expect("a page carries the piece");
        let order = |frame: &Frame| {
            let mut s = vec![];
            sequence(frame, &mut s);
            let keep = [
                "Alpha",
                "Quoted",
                "Bullet",
                "Heading",
                "Omega",
                "fill [64, 26, 110]",
            ];
            s.into_iter()
                .filter(|w| keep.contains(&w.as_str()))
                .collect::<Vec<_>>()
        };
        let mut frame = page.frame.clone();
        weasyprint_paint_order(&mut frame);
        let rule = "fill [64, 26, 110]";
        let want = [
            rule, "Alpha", "Quoted", "Omega", "Bullet", rule, "Bullet", rule, "Heading",
        ];
        assert_eq!(order(&frame), want);
        assert_ne!(
            order(&page.frame),
            want,
            "typst already paints in WeasyPrint's order"
        );
    }

    #[test]
    fn the_fixture_with_tail_art_settles_and_draws_the_end_tick_where_the_oracle_does() {
        let tree = fixture_tree("900");
        let compiled =
            typst::compile::<PagedDocument>(&world(&tree, roots().1).expect("the world builds"));
        let unsettled: Vec<_> = compiled
            .warnings
            .iter()
            .map(|w| w.message.to_string())
            .collect();
        assert!(unsettled.is_empty(), "{unsettled:?}");
        let doc = compiled.output.expect("it compiles");
        let ticks: Vec<f64> = doc
            .pages()
            .iter()
            .filter_map(|page| {
                let mut found = vec![];
                marks(&page.frame, Point::zero(), &mut found);
                let tick = found
                    .iter()
                    .find(|m| m.fill[..3] == [240, 87, 56] && (m.width - 17.0).abs() < 1e-6)?;
                let end = found.iter().find(|m| m.text.starts_with("END"))?;
                Some(end.y - tick.y)
            })
            .collect();
        assert!(!ticks.is_empty());
        assert!(ticks.iter().all(|d| (d - 2.55).abs() < 1e-6), "{ticks:?}");
    }

    fn clipped_images(frame: &Frame, clip: Option<Size>, out: &mut Vec<(Size, Option<Size>)>) {
        for (_, item) in frame.items() {
            match item {
                FrameItem::Group(group) => clipped_images(
                    &group.frame,
                    group.clip.as_ref().map(|c| c.bbox(None).size()).or(clip),
                    out,
                ),
                FrameItem::Image(_, size, _) => out.push((*size, clip)),
                _ => {}
            }
        }
    }

    #[test]
    fn every_body_image_is_clipped_to_its_own_box_as_weasyprint_clips_it() {
        let doc = document(&world(&fixture_tree("900"), roots().1).expect("the world builds"))
            .expect("it compiles");
        let mut found = vec![];
        for page in doc.pages() {
            clipped_images(&page.frame, None, &mut found);
        }
        assert!(found.len() >= 2, "{found:?}");
        assert!(
            found
                .iter()
                .all(|(image, clip)| clip.is_some_and(|c| (c.x - image.x).abs() < Abs::pt(1e-6))),
            "{found:?}"
        );
    }

    struct Mark {
        text: String,
        x: f64,
        y: f64,
        size: f64,
        width: f64,
        fill: [u8; 4],
    }

    fn marks(frame: &Frame, at: Point, out: &mut Vec<Mark>) {
        for (pos, item) in frame.items() {
            let origin = at + *pos;
            match item {
                FrameItem::Group(group) => {
                    let shift = Point::new(group.transform.tx, group.transform.ty);
                    marks(&group.frame, origin + shift, out)
                }
                FrameItem::Text(text) => out.push(Mark {
                    text: text.text.to_string(),
                    x: origin.x.to_pt(),
                    y: origin.y.to_pt(),
                    size: text.size.to_pt(),
                    width: text.width().to_pt(),
                    fill: match &text.fill {
                        Paint::Solid(color) => color.to_vec4_u8(),
                        _ => [0; 4],
                    },
                }),
                FrameItem::Shape(shape, _) => {
                    let size = shape.bbox(false).size();
                    if let Some(Paint::Solid(color)) = &shape.fill {
                        out.push(Mark {
                            text: format!("shape {:.2}x{:.2}", size.x.to_pt(), size.y.to_pt()),
                            x: origin.x.to_pt(),
                            y: origin.y.to_pt(),
                            size: 0.0,
                            width: size.x.to_pt(),
                            fill: color.to_vec4_u8(),
                        });
                    }
                }
                _ => {}
            }
        }
    }

    fn page_marks(tree: &Tree, keep: impl Fn(&[Mark]) -> bool) -> Vec<Vec<Mark>> {
        let (_, font_dir) = roots();
        let world = world(tree, font_dir).expect("the world builds");
        document(&world)
            .expect("the fixture compiles")
            .pages()
            .iter()
            .map(|page| {
                let mut out = vec![];
                marks(&page.frame, Point::zero(), &mut out);
                out
            })
            .filter(|out| keep(out))
            .collect()
    }

    fn inked_runs(marks: &[Mark]) -> Vec<(String, [u8; 3])> {
        let mut runs: Vec<(String, [u8; 3])> = vec![];
        for mark in marks.iter().filter(|m| (m.size - 7.5).abs() < 1e-6) {
            let fill = [mark.fill[0], mark.fill[1], mark.fill[2]];
            let text: String = mark.text.chars().filter(|c| !c.is_whitespace()).collect();
            match runs.last_mut() {
                _ if text.is_empty() => {}
                Some((run, ink)) if *ink == fill => run.push_str(&text),
                _ => runs.push((text, fill)),
            }
        }
        runs
    }

    #[test]
    fn a_fenced_code_block_takes_the_stylesheet_s_ink_per_token_class() {
        const INK: [u8; 3] = [14, 19, 22];
        const KEYWORD: [u8; 3] = [240, 87, 56];
        const NAME: [u8; 3] = [28, 56, 140];
        const TYPE: [u8; 3] = [64, 26, 110];
        const COMMENT: [u8; 3] = [117, 115, 122];
        const NUMBER: [u8; 3] = [115, 31, 41];
        const STRING: [u8; 3] = [23, 84, 51];
        let pages = page_marks(&fixture_tree("902"), |m| {
            m.iter()
                .any(|m| m.text.starts_with("fn") && (m.size - 7.5).abs() < 1e-6)
        });
        let runs = inked_runs(&pages[0]);
        let want: Vec<(&str, [u8; 3])> = vec![
            ("fn", KEYWORD),
            ("budget", NAME),
            ("(tokens:", INK),
            ("u32", TYPE),
            (")->", INK),
            ("u32", TYPE),
            ("{", INK),
            ("//fourcharacterspertoken", COMMENT),
            ("let", KEYWORD),
            ("spare=tokens.rem_euclid(", INK),
            ("4", NUMBER),
            (
                ");tokens.div_ceil(spare)}EXTRACT-BEGINletspent=budget(4096);\
                 assert!(spent<=1024,\"overbudget\");EXTRACT-END",
                INK,
            ),
        ];
        assert_eq!(
            runs[..want.len()]
                .iter()
                .map(|(t, i)| (t.as_str(), *i))
                .collect::<Vec<_>>(),
            want
        );
        assert!(
            runs.iter().any(|(t, i)| t == "`cap${" && *i == STRING),
            "{runs:?}"
        );
        let plain = TEMPLATE_TYP.replace(
            "if ink == none { run } else { text(fill: ink, run) }",
            "run",
        );
        let (_, font_dir) = roots();
        let world = Sources::new(&fixture_tree("902"), &plain, ROOT_TYP, font_dir)
            .expect("the world builds");
        let mut flat = vec![];
        for page in document(&world).expect("it compiles").pages() {
            marks(&page.frame, Point::zero(), &mut flat);
        }
        assert!(
            inked_runs(&flat).iter().all(|(_, ink)| *ink == INK),
            "the check cannot tell an inked code block from a plain one"
        );
    }

    #[test]
    fn a_reference_list_sets_on_its_own_leading_and_an_ordered_list_does_not() {
        let pages = page_marks(&fixture_tree("902"), |m| {
            m.iter().any(|m| m.text.starts_with("Ada"))
        });
        let page = &pages[0];
        let line = |start: &str| {
            page.iter()
                .find(|m| m.text.starts_with(start))
                .unwrap_or_else(|| panic!("no mark starts {start:?}"))
        };
        let first = line("Ada");
        let second = line("so");
        let third = line("runs");
        assert!((first.size - 7.2).abs() < 1e-6 && (second.size - 7.2).abs() < 1e-6);
        assert!(
            ((second.y - first.y) - 9.4).abs() < 1e-3,
            "pitch {}",
            second.y - first.y
        );
        assert!(
            ((third.y - second.y) - 9.4).abs() < 1e-3,
            "pitch {}",
            third.y - second.y
        );
        assert!(
            ((second.x - first.x) - 12.9744).abs() < 1e-3,
            "hang {}",
            second.x - first.x
        );
        let ordered = line("An");
        assert!(
            (ordered.size - 10.0).abs() < 1e-6,
            "the ordered entry set at {}",
            ordered.size
        );
    }

    #[test]
    fn a_plain_opener_places_its_source_code_off_the_byline_as_the_adapter_does() {
        let tree = fixture_tree("903");
        let with_code = |m: &[Mark]| m.iter().any(|m| m.text == "shape 55.50x55.50");
        let pages = page_marks(&tree, with_code);
        assert_eq!(pages.len(), 4, "every plain opener carries its code");
        let quiet = 4.0 * 55.5 / 29.0;
        let inset = 55.5 - 2.0 * quiet + 4.5 * 3.15;
        for page in &pages {
            let square = page
                .iter()
                .position(|m| m.text == "shape 55.50x55.50")
                .unwrap();
            assert_eq!(page[square].fill, [255, 255, 255, 255]);
            assert_eq!(
                page[square + 1].fill,
                [14, 19, 22, 255],
                "the ink follows the paper"
            );
            let byline = page
                .iter()
                .find(|m| m.text.starts_with("BY") && (m.size - 7.4).abs() < 1e-6)
                .expect("the byline is set at 7.4pt");
            let (x, y) = (page[square].x, page[square].y);
            assert!(
                (y - (byline.y - 7.4 * 1490.0 / 2048.0 - quiet)).abs() < 1e-3,
                "{y} {}",
                byline.y
            );
            assert!(
                (x - (byline.x - inset - quiet)).abs() < 1e-3,
                "{x} {}",
                byline.x
            );
        }
        let mut bare = tree.clone();
        for file in &mut bare.files {
            while let Some(start) = file.source.find("#byline(code: (") {
                let end = start + file.source[start..].find(")[").expect("the call closes");
                file.source.replace_range(start..end, "#byline(code: none");
            }
        }
        assert!(
            page_marks(&bare, with_code).is_empty(),
            "the control still draws a code"
        );
    }

    fn opener_page(tree: &Tree, title: &str) -> Vec<Mark> {
        page_marks(tree, |m| {
            m.iter().any(|m| m.text.starts_with(title) && m.size > 20.0)
        })
        .into_iter()
        .next()
        .expect("the opener page carries its title")
    }

    fn mark(page: &[Mark], keep: impl Fn(&Mark) -> bool) -> &Mark {
        page.iter()
            .find(|m| keep(m))
            .expect("the mark is on the page")
    }

    #[test]
    fn a_plain_opener_pins_its_label_title_credit_and_standfirst_as_the_adapter_does() {
        let page = opener_page(&fixture_tree("903"), "A Code Fixture Article");
        let top = 42.0004;
        let title = mark(&page, |m| {
            m.text == "A Code Fixture Article" && m.size > 20.0
        });
        assert!(
            (title.size - 35.0).abs() < 1e-9 && (title.y - (top + 47.0046 + 35.0)).abs() < 1e-3,
            "{} {}",
            title.size,
            title.y
        );
        let byline_y = top + 47.0046 + 35.0 * 1.96 + 10.0;
        let byline = mark(&page, |m| m.text.starts_with("BY"));
        assert!((byline.y - byline_y).abs() < 1e-3, "{}", byline.y);
        let note = mark(&page, |m| m.text.starts_with("A fixture author note"));
        assert!((note.y - (byline_y + 12.0)).abs() < 1e-3, "{}", note.y);
        let quiet = 4.0 * 55.5 / 29.0;
        let symbol = byline_y - top - 7.4 * 1490.0 / 2048.0 + 55.5 - 2.0 * quiet;
        let field = symbol + 305.2756 - 264.5208;
        let first = mark(&page, |m| m.text.starts_with("The standfirst"));
        assert!(
            (first.y - (top + field + 10.0046)).abs() < 1e-3,
            "{}",
            first.y
        );
        let second = mark(&page, |m| m.text.starts_with("names"));
        assert!(
            (second.y - first.y - 16.4).abs() < 1e-3,
            "inline code grows the standfirst line"
        );
        let setup = mark(&page, |m| m.text == "Setup");
        let code_descent = 0.3505 * 12.0 - 0.355 * 0.82 * 12.0;
        assert!(
            (setup.y - (second.y + 16.4 + code_descent + 28.0)).abs() < 1e-3,
            "{}",
            setup.y
        );
        let label: Vec<&Mark> = page
            .iter()
            .filter(|m| (m.size - 6.8).abs() < 1e-9 && m.y < top + 12.0)
            .collect();
        let texts: Vec<&str> = label.iter().map(|m| m.text.as_str()).collect();
        assert_eq!(texts, ["FEATURE 01", "ARTICLE", "/", "2026 08"]);
        let left = label[0].x;
        let tracked: Vec<(f64, f64)> = label
            .iter()
            .enumerate()
            .map(|(i, m)| (m.x - if i == 1 { 0.45 } else { 0.0 }, m.width + 0.45))
            .collect();
        let gaps: Vec<f64> = tracked
            .windows(2)
            .map(|w| w[1].0 - w[0].0 - w[0].1)
            .collect();
        assert!(gaps.iter().all(|g| (g - gaps[0]).abs() < 1e-3), "{gaps:?}");
        let (x, width) = tracked[3];
        assert!(
            (x + width - left - 325.0).abs() < 1e-3,
            "the date is flush with the column"
        );
    }

    #[test]
    fn a_byline_past_its_credit_column_is_tracked_in_as_the_adapter_does() {
        let tree = fixture_tree("905");
        let byline = |tree: &Tree| {
            let page = opener_page(tree, "The Compressed");
            let left = mark(&page, |m| m.text == "FEATURE 01").x;
            let marks: Vec<(f64, f64)> = page
                .iter()
                .filter(|m| (m.size - 7.4).abs() < 1e-9)
                .map(|m| (m.y, m.x + m.width - left))
                .collect();
            marks
        };
        let one_line = |marks: &[(f64, f64)]| marks.windows(2).all(|w| w[1].1 > w[0].1);
        let tracked = byline(&tree);
        assert!(one_line(&tracked), "{tracked:?}");
        let right = tracked.iter().map(|(_, r)| *r).fold(0.0, f64::max);
        assert!(
            right <= 325.025 && right > 315.0,
            "the tracked byline stays in its column: {right}"
        );
        let mut loose = tree.clone();
        for file in &mut loose.files {
            if let Some(start) = file.source.find("tracking: -") {
                let end = start + file.source[start..].find("pt").expect("a length");
                file.source.replace_range(start..end, "tracking: 0");
            }
        }
        let wrapped = byline(&loose);
        assert!(
            !one_line(&wrapped),
            "the control stays on one line: {wrapped:?}"
        );
    }

    #[test]
    fn a_heading_that_opens_the_body_after_an_illustrated_opener_keeps_its_margin() {
        let tree = fixture_tree("904");
        let notes = |tree: &Tree| {
            let pages = page_marks(tree, |m| {
                m.iter()
                    .any(|m| m.text == "Notes" && (m.size - 18.5).abs() < 1e-9)
            });
            mark(&pages[0], |m| m.text == "Notes").y
        };
        assert!(
            (notes(&tree) - (42.0004 + 20.4 + 10.0046)).abs() < 1e-3,
            "{}",
            notes(&tree)
        );
        let mut dropped = tree.clone();
        for file in &mut dropped.files {
            file.source = file.source.replace("lead: true", "lead: false");
        }
        assert!(
            (notes(&dropped) - (42.0004 + 10.0046)).abs() < 1e-3,
            "{}",
            notes(&dropped)
        );
    }

    #[test]
    fn a_four_entry_contents_divides_its_band_into_four_rows() {
        let page = opener_page(&fixture_tree("903"), "Contents");
        assert!(page.iter().any(|m| m.text == "Contents"));
        let titles: Vec<f64> = page
            .iter()
            .filter(|m| (m.size - 9.8).abs() < 1e-9)
            .map(|m| m.y)
            .collect();
        assert_eq!(titles.len(), 4);
        assert!(
            titles
                .windows(2)
                .all(|w| (w[1] - w[0] - 393.0 / 4.0).abs() < 1e-3),
            "{titles:?}"
        );
    }

    #[test]
    fn the_reader_declares_the_edition_locale_as_its_language() {
        let (_, font_dir) = roots();
        let lang = |tree: &Tree| {
            let pdf =
                compile(&world(tree, font_dir).expect("the world builds")).expect("it compiles");
            let doc = Document::load_mem(&pdf).expect("a PDF");
            match doc.catalog().and_then(|c| c.get(b"Lang")) {
                Ok(Object::String(bytes, _)) => String::from_utf8_lossy(bytes).into_owned(),
                other => panic!("no /Lang: {other:?}"),
            }
        };
        let tree = fixture_tree("900");
        assert_eq!(lang(&tree), "en");
        let mut spanish = tree.clone();
        let main = spanish
            .files
            .iter_mut()
            .find(|f| f.path == "main.typ")
            .unwrap();
        assert!(main.source.contains("#set text(lang: \"en\")"));
        main.source = main.source.replace(
            "#set text(lang: \"en\")",
            "#set text(lang: \"es\", region: \"AR\")",
        );
        assert_eq!(lang(&spanish), "es-AR");
    }
}
