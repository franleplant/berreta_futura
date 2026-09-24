use typst::introspection::{Location, Tag};
use typst::layout::{Abs, Em, Frame, FrameItem, Point};
use typst::text::{Glyph, TextItem};

pub const WEASYPRINT_69: bool = true;
const TRACK: &str = "mag-track:";
const FLUSH_RIGHT: &str = "mag-flush-right";
const SPREAD: &str = "mag-spread";

#[derive(Clone, Copy, PartialEq)]
enum Flex {
    Flow(Option<Location>),
    FlushRight(Location),
    Spread(Location),
}

#[derive(Default)]
struct Open {
    tracks: Vec<(Location, f64)>,
    flex: Vec<(Location, Flex)>,
}

struct Placed {
    pos: Point,
    item: FrameItem,
    delta: Abs,
    flex: Flex,
    span: (Abs, Abs),
    width: Abs,
}

pub fn weasyprint_text(frame: &mut Frame) {
    walk(frame, &mut Open::default());
}

fn label_of(tag: &Tag) -> Option<(Location, String)> {
    match tag {
        Tag::Start(content, _) => Some((
            content.location()?,
            content.label().map_or_else(
                || content.elem().name().to_string(),
                |l| l.resolve().as_str().to_string(),
            ),
        )),
        Tag::End(..) => None,
    }
}

fn open(tag: &Tag, state: &mut Open) {
    if let Tag::End(loc, ..) = tag {
        state.tracks.retain(|(l, _)| l != loc);
        state.flex.retain(|(l, _)| l != loc);
        return;
    }
    let Some((loc, name)) = label_of(tag) else {
        return;
    };
    if let Some(pt) = name
        .strip_prefix(TRACK)
        .and_then(|v| v.replace('\u{2212}', "-").parse().ok())
    {
        state.tracks.push((loc, pt));
    }
    match name.as_str() {
        FLUSH_RIGHT => state.flex.push((loc, Flex::FlushRight(loc))),
        SPREAD => state.flex.push((loc, Flex::Spread(loc))),
        "place" => state.flex.push((loc, Flex::Flow(Some(loc)))),
        _ => {}
    }
}

fn measured(
    pos: Point,
    item: &mut FrameItem,
    state: &mut Open,
    flex: Flex,
) -> (Abs, (Abs, Abs), Abs) {
    let point = (Abs::zero(), (pos.y, pos.y), Abs::zero());
    match item {
        FrameItem::Tag(tag) => {
            open(tag, state);
            point
        }
        FrameItem::Text(text) => {
            soft_hyphens(text);
            let width = text.width();
            let flow = matches!(flex, Flex::Flow(_));
            let delta = written(text, state.tracks.last().map(|t| t.1), flow);
            (delta, (pos.y, pos.y), width)
        }
        FrameItem::Group(group) => {
            let size = group.frame.size();
            let delta = walk(&mut group.frame, state);
            (delta, (pos.y, pos.y + size.y), size.x)
        }
        FrameItem::Link(_, size) => (Abs::zero(), (pos.y, pos.y + size.y), size.x),
        FrameItem::Shape(shape, _) => {
            let bbox = shape.geometry.bbox(None);
            (
                Abs::zero(),
                (pos.y + bbox.min.y, pos.y + bbox.max.y),
                bbox.max.x,
            )
        }
        _ => point,
    }
}

fn hyphen_kern(word: &TextItem) -> Option<(usize, Em)> {
    let index = word
        .glyphs
        .iter()
        .rposition(|g| !word.text[g.range()].trim_matches('\u{ad}').is_empty())?;
    let c = word.text[word.glyphs[index].range()]
        .chars()
        .rfind(|c| *c != '\u{ad}')?;
    let face = word.font.rusty();
    let mut buffer = rustybuzz::UnicodeBuffer::new();
    buffer.push_str(&format!("{c}\u{2010}"));
    let shaped = rustybuzz::shape(face, &[], buffer);
    let (info, position) = (
        shaped.glyph_infos().first()?,
        shaped.glyph_positions().first()?,
    );
    let nominal = face.glyph_hor_advance(ttf_parser::GlyphId(info.glyph_id as u16))?;
    let kern = f64::from(position.x_advance) - f64::from(nominal);
    Some((index, Em::new(kern / f64::from(face.units_per_em()))))
}

fn merge_hyphens(items: Vec<(Point, FrameItem)>) -> Vec<(Point, FrameItem)> {
    let mut out: Vec<(Point, FrameItem)> = Vec::with_capacity(items.len());
    for (pos, item) in items {
        if let (Some((_, FrameItem::Text(word))), FrameItem::Text(hyphen)) = (out.last_mut(), &item)
        {
            if hyphen.text.as_str() == "\u{ad}" && word.font == hyphen.font {
                if let Some((index, kern)) = hyphen_kern(word) {
                    word.glyphs[index].x_advance += kern;
                    let at = word.text.len() as u16;
                    word.glyphs.extend(hyphen.glyphs.iter().map(|g| Glyph {
                        range: at + g.range.start..at + g.range.end,
                        ..g.clone()
                    }));
                    word.text.push_str(&hyphen.text);
                    continue;
                }
            }
        }
        out.push((pos, item));
    }
    out
}

fn walk(frame: &mut Frame, state: &mut Open) -> Abs {
    let items = merge_hyphens(frame.items().cloned().collect());
    frame.clear();
    let mut placed = Vec::with_capacity(items.len());
    for (pos, mut item) in items {
        let flex = state.flex.last().map_or(Flex::Flow(None), |f| f.1);
        let (delta, span, width) = measured(pos, &mut item, state, flex);
        placed.push(Placed {
            pos,
            item,
            delta,
            flex,
            span,
            width,
        });
    }
    let total = placed.iter().map(|p| p.delta).sum();
    for (pos, item) in shifted(placed) {
        frame.push(pos, item);
    }
    total
}

fn line_of(p: &Placed, lines: &[Abs]) -> Option<usize> {
    let eps = Abs::pt(1e-6);
    let mut on = lines
        .iter()
        .enumerate()
        .filter(|(_, y)| **y >= p.span.0 - eps && **y <= p.span.1 + eps);
    match (on.next(), on.next()) {
        (Some((i, _)), None) => Some(i),
        _ => None,
    }
}

fn shift(placed: &[Placed], at: &[Option<usize>], i: usize, x: Abs) -> Abs {
    let eps = Abs::pt(1e-6);
    let (line, flex) = (at[i], placed[i].flex);
    let members: Vec<&Placed> = (0..placed.len())
        .filter(|&j| at[j] == line && placed[j].flex == flex)
        .map(|j| &placed[j])
        .filter(|p| matches!(p.item, FrameItem::Text(_) | FrameItem::Group(_)))
        .collect();
    let ended = |p: &&&Placed| p.pos.x + p.width <= x + eps;
    let before: Abs = members.iter().filter(ended).map(|p| p.delta).sum();
    match flex {
        Flex::Flow(_) => before,
        Flex::FlushRight(_) => -members
            .iter()
            .filter(|p| p.pos.x >= x - eps)
            .map(|p| p.delta)
            .sum::<Abs>(),
        Flex::Spread(_) => {
            let all: Abs = members.iter().map(|p| p.delta).sum();
            let gaps = members.len().saturating_sub(1).max(1) as f64;
            before - all * (members.iter().filter(ended).count() as f64 / gaps)
        }
    }
}

fn shifted(mut placed: Vec<Placed>) -> Vec<(Point, FrameItem)> {
    let mut lines: Vec<Abs> = placed
        .iter()
        .filter(|p| matches!(p.item, FrameItem::Text(_)))
        .map(|p| p.pos.y)
        .collect();
    lines.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    lines.dedup_by(|a, b| (*a - *b).abs() < Abs::pt(1e-6));
    let at: Vec<_> = placed.iter().map(|p| line_of(p, &lines)).collect();
    let moves: Vec<_> = (0..placed.len())
        .map(|i| {
            let (x, w) = (placed[i].pos.x, placed[i].width);
            at[i].map_or((Abs::zero(), Abs::zero()), |_| {
                let left = shift(&placed, &at, i, x);
                (left, shift(&placed, &at, i, x + w) - left)
            })
        })
        .collect();
    for (p, (dx, grow)) in placed.iter_mut().zip(moves) {
        p.pos.x += dx;
        if let FrameItem::Link(_, size) = &mut p.item {
            size.x += grow;
        }
    }
    placed.into_iter().map(|p| (p.pos, p.item)).collect()
}

struct Pango {
    units: i64,
    upem: f64,
    px: f64,
}

impl Pango {
    fn scale(&self, font_units: f64) -> i64 {
        let mult = (self.units << 16) / self.upem as i64;
        (font_units.round() as i64 * mult + 32768) >> 16
    }

    fn per_mille(&self, units: i64) -> f64 {
        units as f64 * 1000.0 / 1024.0 / self.px
    }
}

fn spacing(ls: i64) -> (i64, i64) {
    let left = if ls & 1023 == 0 {
        (ls / 2 + 512) & !1023
    } else {
        ls / 2
    };
    (left, ls - left)
}

fn soft_hyphens(text: &mut TextItem) {
    if !text.text.contains('\u{ad}') {
        return;
    }
    let drawn: Vec<usize> = text
        .glyphs
        .iter()
        .filter(|g| &text.text[g.range()] == "\u{ad}")
        .map(|g| g.range().start)
        .collect();
    let mut map = vec![0u16; text.text.len() + 1];
    let mut out = String::with_capacity(text.text.len() + drawn.len());
    for (at, c) in text.text.char_indices() {
        map[at] = out.len() as u16;
        match c {
            '\u{ad}' if drawn.contains(&at) => out.push('\u{2010}'),
            '\u{ad}' => {}
            _ => out.push(c),
        }
    }
    map[text.text.len()] = out.len() as u16;
    for glyph in &mut text.glyphs {
        glyph.range = map[glyph.range().start]..map[glyph.range().end];
    }
    text.text = out.into();
}

fn written(text: &mut TextItem, tracking: Option<f64>, flow: bool) -> Abs {
    let size = text.size.to_pt();
    let units = (size * 4.0 / 3.0 * 1024.0) as i64;
    let pango = Pango {
        units,
        upem: text.font.units_per_em(),
        px: units as f64 / 1024.0,
    };
    let track = tracking.unwrap_or(0.0);
    let ls = (track * 4.0 / 3.0 * 1024.0) as i64;
    let (left, right) = spacing(ls);
    let track_units = track / size * pango.upem;
    let n = text.glyphs.len();
    let typst_width = text.width().to_pt();
    let (mut pango_width, mut sum, mut run_end) = (0i64, 0.0, false);
    for (i, glyph) in text.glyphs.iter_mut().enumerate() {
        let nominal = text.font.x_advance(glyph.id).unwrap_or(glyph.x_advance);
        let extra = (glyph.x_advance - nominal).get() * pango.upem;
        let untracked = extra - track_units;
        let tracked = ls != 0 && (i + 1 < n || (untracked - untracked.round()).abs() < 1e-6);
        run_end = ls != 0 && !tracked;
        let kern = extra - if tracked { track_units } else { 0.0 };
        let nominal = pango.scale(nominal.get() * pango.upem);
        let x_offset = if i > 0 { left } else { 0 };
        let trailing = if i + 1 < n || tracked { right } else { 0 };
        let width = nominal + pango.scale(kern) + x_offset + trailing;
        pango_width += width;
        let offset = x_offset as f64 / pango.px;
        let logical = pango.per_mille(nominal).round_ties_even();
        let kerning = logical + offset - pango.per_mille(width);
        let advance = logical - kerning.trunc() + offset;
        glyph.x_offset += Em::new(offset / 1000.0);
        glyph.x_advance = Em::new(advance / 1000.0);
        sum += advance;
    }
    let pango_pt = pango_width as f64 / 1024.0 * 0.75;
    text.size = Abs::pt(pango.px * 0.75);
    if let Some(last) = text.glyphs.last_mut() {
        let rest = sum - last.x_advance.get() * 1000.0;
        last.x_advance = Em::new(pango_pt / text.size.to_pt() - rest / 1000.0);
    }
    let trailing = if flow && run_end { track } else { 0.0 };
    Abs::pt(pango_pt - typst_width + trailing)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::{File, Tree};
    use crate::typeset::template::{document, world, FONT_DIR};
    use std::path::PathBuf;

    fn page(body: &str) -> Frame {
        let fonts = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("the crate sits inside the repository")
            .join(FONT_DIR);
        let source = format!("#import \"/template.typ\": *\n{body}\n");
        let tree = Tree {
            files: vec![File {
                path: "main.typ".into(),
                source,
            }],
        };
        let doc = document(&world(&tree, &fonts).expect("the world builds")).expect("it compiles");
        doc.pages()
            .iter()
            .map(|p| p.frame.clone())
            .find(|f| {
                let mut found = vec![];
                texts(f, Point::zero(), &mut found);
                !found.is_empty()
            })
            .expect("a page carries the text")
    }

    fn texts(frame: &Frame, at: Point, out: &mut Vec<(Point, TextItem)>) {
        for (pos, item) in frame.items() {
            match item {
                FrameItem::Group(group) => texts(&group.frame, at + *pos, out),
                FrameItem::Text(text) => out.push((at + *pos, text.clone())),
                _ => {}
            }
        }
    }

    type Texts = Vec<(Point, TextItem)>;

    fn shimmed(body: &str) -> (Texts, Texts) {
        let mut frame = page(body);
        let (mut before, mut after) = (vec![], vec![]);
        texts(&frame, Point::zero(), &mut before);
        weasyprint_text(&mut frame);
        texts(&frame, Point::zero(), &mut after);
        (before, after)
    }

    fn per_mille(em: Em) -> f64 {
        (em.get() * 1000.0 * 1e6).round() / 1e6
    }

    #[test]
    fn a_soft_hyphen_break_is_one_run_ending_in_a_kerned_u2010_as_pango_sets_it() {
        let body = "#set text(font: SERIF, size: 10pt, lang: \"es\")\n\
                    #block(width: 25pt)[#set par(linebreaks: \"simple\", justify: false)\n\
                    ser\u{ad}vicio servicio]";
        let (before, after) = shimmed(body);
        assert!(before.iter().any(|(_, t)| t.text.as_str() == "\u{ad}"));
        assert!(after.iter().all(|(_, t)| !t.text.contains('\u{ad}')));
        let (_, word) = after
            .iter()
            .find(|(_, t)| t.text.ends_with('\u{2010}'))
            .expect("the broken word carries its hyphen");
        assert_eq!(word.text.as_str(), "ser\u{2010}");
        let r = &word.glyphs[2];
        let nominal = word.font.x_advance(r.id).expect("r has an advance");
        let kerned = hyphen_kern(&TextItem {
            text: "r".into(),
            glyphs: vec![Glyph {
                range: 0..1,
                ..r.clone()
            }],
            ..word.clone()
        })
        .expect("r shapes before the hyphen")
        .1;
        assert!(
            kerned.get() < -0.01,
            "Source Serif kerns r against the hyphen"
        );
        let (drawn, expected) = (per_mille(r.x_advance), per_mille(nominal + kerned));
        assert!(
            (drawn - expected).abs() <= 1.0,
            "r is drawn {drawn}, kerned {expected}"
        );
        assert!(
            drawn < per_mille(nominal) - 20.0,
            "the kern reaches the drawn advance"
        );
    }

    #[test]
    fn a_kerned_pair_is_written_as_weasyprint_69_truncates_it() {
        let (before, after) = shimmed("#text(font: \"Source Serif 4 SmText\", size: 10pt)[nt]");
        let (n0, n1) = (&before[0].1.glyphs[0], &after[0].1.glyphs[0]);
        assert_eq!(
            per_mille(n0.x_advance),
            626.0,
            "harfbuzz's exact kerned advance"
        );
        assert_eq!(
            per_mille(n1.x_advance),
            627.0,
            "the kern truncated toward the nominal width"
        );
        assert_eq!(after[0].1.size.to_pt(), 13653.0 / 1024.0 * 0.75);
    }

    #[test]
    fn a_letter_spaced_run_carries_pangos_half_spacing_and_the_writers_offset() {
        let (before, after) = shimmed(
            "#text(font: \"Inter\", size: 6.8pt, weight: 500, tracking: 0.45pt)[#[FEATURE]#label(\"mag-track:0.45\")]",
        );
        let (f, e) = (&after[0].1.glyphs[0], &after[0].1.glyphs[1]);
        assert_eq!(per_mille(f.x_advance), 622.0);
        assert_eq!(
            per_mille(e.x_offset),
            (307.0 / 9.066_406_25 * 1e6_f64).round() / 1e6
        );
        assert_eq!(per_mille(before[0].1.glyphs[1].x_offset), 0.0);
    }

    #[test]
    fn an_item_after_a_run_starts_where_pangos_grid_ends_the_run() {
        let (before, after) = shimmed(
            "#set text(font: \"Source Serif 4 SmText\", size: 10pt)\ndramatically raise the quality of human life. #text(weight: 700)[bold]",
        );
        let start = |v: &[(Point, TextItem)]| v[1].0.x - v[0].0.x;
        assert!((start(&before).to_pt() - 206.5).abs() < 1e-9);
        assert!((start(&after).to_pt() - 206.492_431_640_625).abs() < 1e-9);
    }

    #[test]
    fn a_flush_right_item_keeps_its_right_edge() {
        let (before, after) = shimmed(
            "#place(top + right, [#text(font: \"Inter\", size: 6.8pt, weight: 500)[COUNTERING MISUSE]<mag-flush-right>])",
        );
        let right = |(p, t): &(Point, TextItem)| (p.x + t.width()).to_pt();
        assert!((right(&before[0]) - right(&after[0])).abs() < 1e-9);
        assert!((before[0].0.x - after[0].0.x).to_pt().abs() > 1e-4);
    }

    #[test]
    fn vertical_offsets_use_pangos_rounded_ascent_and_descent() {
        let probe = |expr: &str| {
            let (before, _) = shimmed(&format!(
                "#place(top + left, dy: {expr}, text(size: 10pt, top-edge: \"baseline\", \"x\"))\n\
                 #place(top + left, text(size: 10pt, top-edge: \"baseline\", \"y\"))"
            ));
            (before[0].0.y - before[1].0.y).to_pt()
        };
        let folio = (30421.0 - 7575.0) / 2048.0 * 0.75;
        assert!((probe("pango-center(HALF-SANS, 23pt)") - folio).abs() < 1e-9);
        assert!((probe("23pt * HALF-SANS") - folio).abs() > 2e-4);
        let drop = 0.7 * 18.7 / 2.0 + (26450.0 - 8553.0) / 2048.0 * 0.75;
        assert!((probe("OPENER-DROP-LEADING * OPENER-DROP-SIZE / 2 + pango-center(HALF-SERIF, OPENER-DROP-SIZE)") - drop).abs() < 1e-9);
    }

    #[test]
    fn a_contents_entry_label_is_set_without_the_kickers_tracking() {
        let advance = |body: &str| {
            let (before, _) = shimmed(body);
            let text = &before[0].1;
            let glyph = &text.glyphs[0];
            (glyph.x_advance - text.font.x_advance(glyph.id).unwrap())
                .at(text.size)
                .to_pt()
        };
        assert!(advance("#contents-caption[Feature]").abs() < 1e-9);
        assert!((advance("#contents-caption(tracking: 0.45pt)[Issue]") - 0.45).abs() < 1e-9);
    }
}
