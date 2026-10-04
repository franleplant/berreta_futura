use crate::typeset::content::Tree;
use crate::typeset::geometry::geometry;
use crate::typeset::runt::Edit;
use crate::typeset::world::id;
use anyhow::Result;
use std::collections::{BTreeSet, HashMap};
use typst::foundations::Value;
use typst::introspection::{Location, MetadataElem, Tag};
use typst::layout::{Frame, FrameItem, Point};
use typst::visualize::Geometry;
use typst::{World, WorldExt};
use typst_layout::PagedDocument;
use typst_syntax::{FileId, Span};

const BLOCKS: [&str; 2] = ["mag-prose", "mag-backdrop"];
const CONTAINERS: [&str; 3] = ["#doc-item[", "#doc-quote[", "#doc-list("];
const CUT: &str = "#colbreak()\n";
const FLOAT: &str = "\n  float: true,";
const KEPT: &str = "\n  float: false,";
const HEAD_ROOM_LINES: f64 = 2.0;
const HEADING_ABOVE: f64 = 20.4;

struct Mark {
    value: Value,
    page: usize,
    y: f64,
}

impl Mark {
    fn text(&self, key: &str) -> Option<String> {
        match field(&self.value, key) {
            Some(Value::Str(s)) => Some(s.to_string()),
            _ => None,
        }
    }

    fn flag(&self, key: &str) -> Option<bool> {
        match field(&self.value, key) {
            Some(Value::Bool(b)) => Some(b),
            _ => None,
        }
    }
}

struct Page {
    top: f64,
    bottom: f64,
    datum: f64,
    epsilon: f64,
    above: f64,
    lines: f64,
}

fn field(value: &Value, key: &str) -> Option<Value> {
    match value {
        Value::Dict(d) => d.get(key).ok().cloned(),
        _ => None,
    }
}

fn marks(doc: &PagedDocument, label: &str) -> Vec<Mark> {
    let introspector = doc.introspector();
    introspector
        .elements()
        .all()
        .filter(|c| c.label().is_some_and(|l| l.resolve().as_str() == label))
        .filter_map(|c| {
            let at = introspector.position(c.location()?)?;
            Some(Mark {
                value: c.to_packed::<MetadataElem>()?.value.clone(),
                page: at.page.get(),
                y: at.point.y.to_pt(),
            })
        })
        .collect()
}

fn flows(doc: &PagedDocument) -> Vec<Mark> {
    let mut out = marks(doc, "mag-flow");
    out.sort_by_key(|m| match field(&m.value, "index") {
        Some(Value::Int(index)) => index,
        _ => i64::MAX,
    });
    out
}

fn ink_bottom(frame: &Frame, at: Point, top: f64, bottom: f64) -> f64 {
    frame.items().fold(top, |low, (pos, item)| {
        let here = at + *pos;
        let y = here.y.to_pt();
        let reach = match item {
            FrameItem::Group(group) => {
                let shift = Point::new(group.transform.tx, group.transform.ty);
                ink_bottom(&group.frame, here + shift, top, bottom)
            }
            FrameItem::Text(text) => y - text.font.metrics().descender.at(text.size).to_pt(),
            FrameItem::Image(_, size, _) => y + size.y.to_pt(),
            FrameItem::Shape(shape, _) => match &shape.geometry {
                Geometry::Rect(size) => y + size.y.to_pt(),
                _ => top,
            },
            _ => top,
        };
        match (top..=bottom + 1.0).contains(&y) {
            true => low.max(reach.min(bottom)),
            false => low,
        }
    })
}

fn occurrences(world: &dyn World, tree: &Tree, needle: &str) -> Vec<(FileId, usize)> {
    tree.files
        .iter()
        .filter_map(|file| id(&format!("/{}", file.path)).ok())
        .filter_map(|file| Some((file, world.source(file).ok()?)))
        .flat_map(|(file, source)| {
            let found: Vec<usize> = source
                .text()
                .match_indices(needle)
                .map(|(at, _)| at)
                .collect();
            found.into_iter().map(move |at| (file, at))
        })
        .collect()
}

fn floats(doc: &PagedDocument, world: &dyn World, tree: &Tree, g: &Page) -> Vec<Edit> {
    let mut boxes: HashMap<String, Vec<Mark>> = HashMap::new();
    for mark in marks(doc, "mag-figure-box") {
        boxes
            .entry(mark.text("id").unwrap_or_default())
            .or_default()
            .push(mark);
    }
    let heads: Vec<usize> = marks(doc, "mag-piece").iter().map(|m| m.page).collect();
    let openers: Vec<usize> = marks(doc, "mag-standfirst")
        .iter()
        .map(|m| m.page + 1)
        .collect();
    let fresh = |page: usize| heads.contains(&page) || openers.contains(&page);
    let ends: Vec<usize> = marks(doc, "mag-piece-end").iter().map(|m| m.page).collect();
    let end = |page: usize| ends.iter().copied().find(|e| *e >= page).unwrap_or(page);
    let flows = flows(doc);
    let mut seen: HashMap<String, usize> = HashMap::new();
    let mut edits = Vec::new();
    for (index, figure) in flows.iter().enumerate() {
        if figure.text("kind").as_deref() != Some("figure") {
            continue;
        }
        let id = figure.text("id").unwrap_or_default();
        let nth = *seen.entry(id.clone()).and_modify(|n| *n += 1).or_default();
        let needle = format!("id: \"{id}\",");
        let head = index.checked_sub(1).map(|i| &flows[i]);
        let placed = boxes.get(&id).and_then(|b| b.get(nth));
        let source = occurrences(world, tree, &needle).get(nth).copied();
        let (Some(head), Some(placed), Some((file, at))) = (head, placed, source) else {
            continue;
        };
        if head.text("kind").as_deref() != Some("heading") || placed.flag("turned") == Some(true) {
            continue;
        }
        match figure.flag("float") {
            None => {
                let moved = placed.page == head.page && head.y <= g.top + g.epsilon;
                let page = &doc.pages()[head.page.saturating_sub(2)].frame;
                let room = g.bottom - ink_bottom(page, Point::zero(), g.top, g.bottom);
                let need = g.above + (placed.y - g.datum - head.y) + g.lines * HEAD_ROOM_LINES;
                if moved && head.page > 1 && !fresh(head.page) && room >= need {
                    let after = at + needle.len();
                    edits.push((file, after, after, FLOAT));
                }
            }
            Some(true) if placed.page != head.page + 1 || placed.page > end(head.page) => {
                let from = at + needle.len();
                edits.push((file, from, from + FLOAT.len(), KEPT));
            }
            _ => {}
        }
    }
    edits
}

type Spread = HashMap<Location, (BTreeSet<usize>, (usize, Span, usize))>;

fn spread(
    items: &[(Point, FrameItem)],
    at: Point,
    page: usize,
    open: &mut Vec<Location>,
    out: &mut Spread,
) {
    for (pos, item) in items {
        let here = at + *pos;
        match item {
            FrameItem::Tag(Tag::Start(content, _)) => {
                let block = content
                    .label()
                    .is_some_and(|l| BLOCKS.contains(&l.resolve().as_str()));
                if let (true, Some(loc)) = (block, content.location()) {
                    open.push(loc);
                }
            }
            FrameItem::Tag(Tag::End(loc, ..)) => open.retain(|l| l != loc),
            FrameItem::Group(group) => {
                let shift = Point::new(group.transform.tx, group.transform.ty);
                spread(
                    group.frame.items().as_slice(),
                    here + shift,
                    page,
                    open,
                    out,
                );
            }
            FrameItem::Text(text) => {
                let Some(glyph) = text.glyphs.first().filter(|g| g.span.0.id().is_some()) else {
                    continue;
                };
                let first = (out.len(), glyph.span.0, usize::from(glyph.span.1));
                for loc in open.iter() {
                    let entry = out.entry(*loc).or_insert((BTreeSet::new(), first));
                    entry.0.insert(page);
                }
            }
            _ => {}
        }
    }
}

fn body(frame: &Frame) -> &[(Point, FrameItem)] {
    let items = frame.items().as_slice();
    let foreground = items
        .iter()
        .rposition(|(_, i)| matches!(i, FrameItem::Group(_)));
    &items[..foreground.unwrap_or(items.len())]
}

fn line_start(text: &str, at: usize) -> usize {
    text[..at].rfind('\n').map_or(0, |i| i + 1)
}

fn previous_line(text: &str, start: usize) -> Option<usize> {
    let mut at = start;
    while at > 0 {
        at = line_start(text, at - 1);
        if !text[at..start].trim().is_empty() {
            return Some(at);
        }
    }
    None
}

fn block_start(text: &str, at: usize) -> usize {
    let mut start = line_start(text, at);
    while start > 0 && !text[start..].trim_start().starts_with("#doc-") {
        start = line_start(text, start - 1);
    }
    while let Some(prev) = previous_line(text, start) {
        let line = text[prev..start].trim();
        let container = CONTAINERS.iter().any(|c| line.starts_with(c)) && line.ends_with('[');
        if !container && !line.starts_with("#doc-heading(") {
            break;
        }
        start = prev;
        if !container {
            break;
        }
    }
    start
}

fn plate_cuts(doc: &PagedDocument, world: &dyn World) -> Result<Vec<Edit>> {
    let plates: Vec<usize> = marks(doc, "mag-figure-box")
        .iter()
        .filter(|b| b.flag("turned") == Some(true))
        .map(|b| b.page)
        .collect();
    let (mut open, mut out) = (Vec::new(), Spread::new());
    for (page, p) in doc.pages().iter().enumerate() {
        spread(body(&p.frame), Point::zero(), page + 1, &mut open, &mut out);
    }
    let mut edits = Vec::new();
    for &plate in plates
        .iter()
        .filter(|p| **p > 1 && !plates.contains(&(**p - 1)))
    {
        let after = (plate + 1..)
            .find(|p| !plates.contains(p))
            .unwrap_or(plate + 1);
        let straddler = out
            .values()
            .filter(|(pages, _)| pages.contains(&(plate - 1)) && pages.contains(&after))
            .map(|(_, first)| *first)
            .min_by_key(|(order, ..)| *order);
        let Some((_, span, offset)) = straddler else {
            continue;
        };
        let (Some(file), Some(range)) = (span.id(), world.range(span)) else {
            continue;
        };
        let text = world.source(file)?.text().to_string();
        let start = block_start(&text, range.start + offset);
        if text[start..].trim_start().starts_with("#doc-") && !text[..start].ends_with(CUT) {
            edits.push((file, start, start, CUT));
        }
    }
    Ok(edits)
}

pub fn edits(doc: &PagedDocument, world: &dyn World, tree: &Tree) -> Result<Vec<Edit>> {
    let d = geometry();
    let g = Page {
        top: d.margin_top,
        bottom: doc
            .pages()
            .first()
            .map_or(0.0, |p| p.frame.height().to_pt())
            - d.margin_bottom,
        datum: d.datum,
        epsilon: d.epsilon,
        above: HEADING_ABOVE + d.paragraph_after,
        lines: d.body_leading,
    };
    Ok([floats(doc, world, tree, &g), plate_cuts(doc, world)?].concat())
}
