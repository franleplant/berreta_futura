use crate::typeset::content::Tree;
use crate::typeset::decisions::{cut_before, Choice};
use crate::typeset::geometry::geometry;
use crate::typeset::world::Sources;
use std::collections::{BTreeSet, HashMap};
use typst::foundations::Value;
use typst::introspection::{Location, MetadataElem, Tag};
use typst::layout::{Frame, FrameItem, Point};
use typst::visualize::Geometry;
use typst::WorldExt;
use typst_layout::PagedDocument;
use typst_syntax::Span;

const BLOCKS: [&str; 2] = ["mag-prose", "mag-backdrop"];
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

fn floats(doc: &PagedDocument, tree: &Tree, g: &Page) -> Vec<Choice> {
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
        let head = index.checked_sub(1).map(|i| &flows[i]);
        let placed = boxes.get(&id).and_then(|b| b.get(nth));
        let slot = tree.figures.iter().filter(|f| f.id == id).nth(nth);
        let (Some(head), Some(placed), Some(slot)) = (head, placed, slot) else {
            continue;
        };
        let kind = head.text("kind");
        if !matches!(kind.as_deref(), Some("heading" | "figure"))
            || placed.flag("turned") == Some(true)
        {
            continue;
        }
        match figure.flag("float") {
            None => {
                let (moved, need) = match kind.as_deref() {
                    Some("heading") => (
                        placed.page == head.page && head.y <= g.top + g.epsilon,
                        g.above + (placed.y - g.datum - head.y) + g.lines * HEAD_ROOM_LINES,
                    ),
                    _ => (placed.page == head.page + 1, g.lines * HEAD_ROOM_LINES),
                };
                let page = &doc.pages()[placed.page.saturating_sub(2)].frame;
                let room = g.bottom - ink_bottom(page, Point::zero(), g.top, g.bottom);
                if moved && placed.page > 1 && !fresh(placed.page) && room >= need {
                    edits.push(Choice::Float(slot.hole, true));
                }
            }
            Some(true) if placed.page != head.page + 1 || placed.page > end(head.page) => {
                edits.push(Choice::Float(slot.hole, false));
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

fn plate_cuts(doc: &PagedDocument, world: &Sources) -> Vec<Choice> {
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
        edits.extend(cut_before(world.marks(file), range.start + offset).map(Choice::Cut));
    }
    edits
}

pub fn choices(doc: &PagedDocument, world: &Sources, tree: &Tree) -> Vec<Choice> {
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
    [floats(doc, tree, &g), plate_cuts(doc, world)].concat()
}
