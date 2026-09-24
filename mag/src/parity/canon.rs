use super::streams::{self, Element, Face};
use anyhow::{Context, Result};
use std::collections::{BTreeMap, HashMap};

pub type Rect = [i64; 4];
pub type Ink = Option<Vec<Option<Rect>>>;
type P = (i64, i64);

pub struct Glyph {
    pub show: usize,
    pub line: usize,
    pub at: [i64; 2],
    pub start: [i64; 2],
    pub step: usize,
}

pub const GAP_EM: f64 = 3.0;

pub struct Canon {
    pub elements: Vec<Element>,
    pub glyphs: Vec<Option<Glyph>>,
    pub paint_order_runs: usize,
}

#[derive(Clone, PartialEq)]
enum Seg {
    Line(P),
    Curve(P, P, P),
}

impl Seg {
    fn end(&self) -> P {
        match self {
            Seg::Line(e) | Seg::Curve(_, _, e) => *e,
        }
    }
}

#[derive(Clone)]
struct Sub {
    start: P,
    segs: Vec<Seg>,
    closed: bool,
}

fn parse(d: &str) -> Vec<Sub> {
    let t: Vec<&str> = d.split_whitespace().collect();
    let n = |i: usize| t.get(i).and_then(|v| v.parse::<i64>().ok()).unwrap_or(0);
    let pt = |i: usize| (n(i), n(i + 1));
    let mut subs: Vec<Sub> = vec![];
    let mut i = 0;
    while i < t.len() {
        let op = t[i];
        let open = |subs: &mut Vec<Sub>| {
            if subs.last().is_none_or(|s| s.closed) {
                let start = subs.last().map_or((0, 0), |s| s.start);
                subs.push(Sub {
                    start,
                    segs: vec![],
                    closed: false,
                });
            }
        };
        match op {
            "m" | "re" => {
                let segs = match op {
                    "re" => vec![
                        Seg::Line(pt(i + 3)),
                        Seg::Line(pt(i + 5)),
                        Seg::Line(pt(i + 7)),
                    ],
                    _ => vec![],
                };
                subs.push(Sub {
                    start: pt(i + 1),
                    segs,
                    closed: op == "re",
                });
            }
            "l" => {
                open(&mut subs);
                subs.last_mut().unwrap().segs.push(Seg::Line(pt(i + 1)));
            }
            "c" => {
                open(&mut subs);
                let s = Seg::Curve(pt(i + 1), pt(i + 3), pt(i + 5));
                subs.last_mut().unwrap().segs.push(s);
            }
            _ => subs.last_mut().into_iter().for_each(|s| s.closed = true),
        }
        i += 1 + 2 * match op {
            "m" | "l" => 1,
            "c" => 3,
            "re" => 4,
            _ => 0,
        };
    }
    subs
}

fn render(subs: &[Sub]) -> String {
    let mut out = vec![];
    let p = |q: P| format!("{} {}", q.0, q.1);
    for s in subs {
        out.push(format!("m {}", p(s.start)));
        for seg in &s.segs {
            out.push(match seg {
                Seg::Line(e) => format!("l {}", p(*e)),
                Seg::Curve(a, b, e) => format!("c {} {} {}", p(*a), p(*b), p(*e)),
            });
        }
        if s.closed {
            out.push("h".into());
        }
    }
    out.join(" ")
}

pub fn expand_rects(d: &str) -> String {
    render(&parse(d))
}

fn loop_of(s: &Sub) -> Option<Sub> {
    if s.segs.is_empty() {
        return s.closed.then(|| s.clone());
    }
    let mut segs = s.segs.clone();
    if segs.last().map(Seg::end) != Some(s.start) {
        segs.push(Seg::Line(s.start));
    }
    let mut cur = s.start;
    let kept: Vec<Seg> = segs
        .into_iter()
        .filter(|g| {
            let keep = *g != Seg::Line(cur);
            cur = g.end();
            keep
        })
        .collect();
    if kept.is_empty() {
        return Some(s.clone());
    }
    let n = kept.len();
    let vertex = |j: usize| if j == 0 { s.start } else { kept[j - 1].end() };
    let from = |j: usize| Sub {
        start: vertex(j),
        segs: (0..n).map(|k| kept[(j + k) % n].clone()).collect(),
        closed: false,
    };
    let low = (0..n).map(vertex).min()?;
    (0..n)
        .filter(|&j| vertex(j) == low)
        .map(from)
        .min_by_key(|r| render(std::slice::from_ref(r)))
}

fn reversed(s: &Sub) -> Sub {
    let vertex = |j: usize| if j == 0 { s.start } else { s.segs[j - 1].end() };
    let segs = (0..s.segs.len())
        .rev()
        .map(|j| match &s.segs[j] {
            Seg::Line(_) => Seg::Line(vertex(j)),
            Seg::Curve(a, b, _) => Seg::Curve(*b, *a, vertex(j)),
        })
        .collect();
    Sub {
        start: s.start,
        segs,
        closed: s.closed,
    }
}

pub fn fill_region(d: &str) -> String {
    let loops: Vec<Sub> = parse(d).iter().filter_map(loop_of).collect();
    match loops.as_slice() {
        [one] => [Some(one.clone()), loop_of(&reversed(one))]
            .into_iter()
            .flatten()
            .map(|l| render(&[l]))
            .min()
            .unwrap_or_default(),
        _ => render(&loops),
    }
}

pub fn rect(d: &str) -> Option<Rect> {
    let subs = parse(d);
    let [s] = subs.as_slice() else { return None };
    let mut pts = vec![s.start];
    for g in &s.segs {
        let Seg::Line(e) = g else { return None };
        pts.push(*e);
    }
    let r = bounds(&pts)?;
    let axis = pts.windows(2).all(|w| w[0].0 == w[1].0 || w[0].1 == w[1].1);
    let corners = pts
        .iter()
        .all(|p| [r[0], r[2]].contains(&p.0) && [r[1], r[3]].contains(&p.1));
    (pts.len() == 5 && pts[0] == pts[4] && axis && corners).then_some(r)
}

fn bounds(pts: &[P]) -> Option<Rect> {
    let xs = pts.iter().map(|p| p.0);
    let ys = pts.iter().map(|p| p.1);
    Some([xs.clone().min()?, ys.clone().min()?, xs.max()?, ys.max()?])
}

fn control_box(d: &str) -> Option<Rect> {
    let mut pts = vec![];
    for s in parse(d) {
        pts.push(s.start);
        for g in s.segs {
            match g {
                Seg::Line(e) => pts.push(e),
                Seg::Curve(a, b, e) => pts.extend([a, b, e]),
            }
        }
    }
    bounds(&pts)
}

fn inside(inner: Rect, outer: Rect) -> bool {
    inner[0] >= outer[0] && inner[1] >= outer[1] && inner[2] <= outer[2] && inner[3] <= outer[3]
}

fn grow(r: Rect, by: i64) -> Rect {
    [r[0] - by, r[1] - by, r[2] + by, r[3] + by]
}

fn painted_box(e: &Element, text: Option<Rect>) -> Option<Rect> {
    match e {
        Element::Path {
            d,
            stroke,
            lw,
            join,
            miter,
            ..
        } => {
            let b = control_box(d)?;
            let reach = match (stroke, lw) {
                (Some(_), Some(w)) => {
                    let square = rect(&fill_region(d)).is_some();
                    let spike = match join {
                        Some(0) if !square => miter.unwrap_or(0),
                        _ => 0,
                    };
                    (w * spike.max(142) + 199) / 200 + 1
                }
                _ => 0,
            };
            Some(grow(b, reach))
        }
        Element::Image { m, .. } => {
            let corner = |u: i64, v: i64| (m[0] * u + m[2] * v + m[4], m[1] * u + m[3] * v + m[5]);
            bounds(&[corner(0, 0), corner(1, 0), corner(0, 1), corner(1, 1)]).map(|r| grow(r, 1))
        }
        Element::Text { .. } => text,
        Element::Clip { .. } => None,
    }
}

fn stack_of(e: &Element) -> &Vec<u32> {
    match e {
        Element::Text { clip, .. }
        | Element::Path { clip, .. }
        | Element::Clip { clip, .. }
        | Element::Image { clip, .. } => clip,
    }
}

fn stack(e: &mut Element) -> &mut Vec<u32> {
    match e {
        Element::Text { clip, .. }
        | Element::Path { clip, .. }
        | Element::Clip { clip, .. }
        | Element::Image { clip, .. } => clip,
    }
}

fn paints(e: &Element) -> bool {
    !matches!(e, Element::Clip { .. })
}

fn fill_only(e: &Element) -> bool {
    matches!(
        e,
        Element::Path {
            fill: Some(_),
            stroke: None,
            ..
        }
    )
}

fn canon_paths(elements: &mut [Element]) {
    for e in elements.iter_mut() {
        let only = fill_only(e);
        match e {
            Element::Path { d, .. } if !only => *d = expand_rects(d),
            Element::Path { d, .. } | Element::Clip { d, .. } => *d = fill_region(d),
            _ => {}
        }
    }
}

fn union(ink: Option<&Ink>) -> Option<Rect> {
    let mut boxes = ink?.as_ref()?.iter().flatten();
    let first = *boxes.next()?;
    Some(boxes.fold(first, |u, b| {
        [
            u[0].min(b[0]),
            u[1].min(b[1]),
            u[2].max(b[2]),
            u[3].max(b[3]),
        ]
    }))
}

fn contained_clips(elements: &mut [Element], text_ink: &[Ink]) {
    let boxes: Vec<Option<Rect>> = elements
        .iter()
        .enumerate()
        .map(|(i, e)| painted_box(e, union(text_ink.get(i))))
        .collect();
    for c in 0..elements.len() {
        let Element::Clip { d, .. } = &elements[c] else {
            continue;
        };
        let Some(r) = rect(d) else { continue };
        let ci = c as u32;
        let contains = elements.iter().zip(&boxes).all(|(e, b)| match e {
            Element::Clip { .. } => true,
            _ if !stack_of(e).contains(&ci) => true,
            _ => b.is_some_and(|b| inside(b, r)),
        });
        if contains {
            elements
                .iter_mut()
                .for_each(|e| stack(e).retain(|&k| k != ci));
        }
    }
}

fn fill_the_clip(elements: &mut [Element]) {
    let clips: HashMap<u32, (String, bool)> = elements
        .iter()
        .enumerate()
        .filter_map(|(i, e)| match e {
            Element::Clip { d, evenodd, .. } => Some((i as u32, (d.clone(), *evenodd))),
            _ => None,
        })
        .collect();
    for e in elements.iter_mut().filter(|e| fill_only(e)) {
        let Element::Path { d, paint, clip, .. } = e else {
            continue;
        };
        let Some(r) = rect(d) else { continue };
        let found = clip.iter().position(|k| {
            clips
                .get(k)
                .and_then(|(cd, _)| control_box(cd))
                .is_some_and(|b| inside(b, r))
        });
        if let Some(at) = found {
            let (cd, evenodd) = clips[&clip.remove(at)].clone();
            *d = cd;
            *paint = if evenodd { "eofill" } else { "fill" }.into();
        }
    }
}

fn meet(a: Rect, b: Rect) -> Option<Rect> {
    let k = [
        a[0].max(b[0]),
        a[1].max(b[1]),
        a[2].min(b[2]),
        a[3].min(b[3]),
    ];
    (k[0] < k[2] && k[1] < k[3]).then_some(k)
}

fn cut(r: Rect, hole: Rect) -> Option<Rect> {
    let Some(k) = meet(r, hole) else {
        return Some(r);
    };
    let (full_x, full_y) = (k[0] == r[0] && k[2] == r[2], k[1] == r[1] && k[3] == r[3]);
    match (full_x, full_y) {
        (false, true) if k[0] == r[0] => Some([k[2], r[1], r[2], r[3]]),
        (false, true) if k[2] == r[2] => Some([r[0], r[1], k[0], r[3]]),
        (true, false) if k[1] == r[1] => Some([r[0], k[3], r[2], r[3]]),
        (true, false) if k[3] == r[3] => Some([r[0], r[1], r[2], k[1]]),
        _ => None,
    }
}

fn frame(d: &str) -> Option<(Rect, Rect)> {
    let rects: Vec<Rect> = parse(d)
        .iter()
        .map(|s| rect(&render(std::slice::from_ref(s))))
        .collect::<Option<_>>()?;
    match rects[..] {
        [a, b] if inside(b, a) => Some((a, b)),
        [a, b] if inside(a, b) => Some((b, a)),
        _ => None,
    }
}

fn strip_fill(elements: &mut [Element]) {
    let clips: HashMap<u32, Rect> = elements
        .iter()
        .enumerate()
        .filter_map(|(i, e)| match e {
            Element::Clip { d, .. } => Some((i as u32, rect(d)?)),
            _ => None,
        })
        .collect();
    for e in elements.iter_mut().filter(|e| fill_only(e)) {
        let Element::Path { d, paint, clip, .. } = e else {
            continue;
        };
        let Some((outer, inner)) = frame(d).filter(|_| paint == "eofill") else {
            continue;
        };
        let Some(at) = clip.iter().position(|k| clips.contains_key(k)) else {
            continue;
        };
        let Some(r) = meet(outer, clips[&clip[at]]).and_then(|r| cut(r, inner)) else {
            continue;
        };
        let [x0, y0, x1, y1] = r;
        *d = fill_region(&format!("re {x0} {y0} {x1} {y0} {x1} {y1} {x0} {y1}"));
        *paint = "fill".into();
        clip.remove(at);
    }
}

fn leading_white(elements: &[Element]) -> Vec<bool> {
    let mut drop = vec![false; elements.len()];
    for (i, e) in elements.iter().enumerate() {
        match e {
            Element::Clip { .. } => {}
            Element::Path { fill: Some(f), .. } if fill_only(e) && f.rgb == [255; 3] => {
                drop[i] = true;
            }
            _ => break,
        }
    }
    drop
}

pub fn canonical(elements: &[Element], text_ink: &[Ink]) -> Canon {
    let mut out = elements.to_vec();
    canon_paths(&mut out);
    contained_clips(&mut out, text_ink);
    fill_the_clip(&mut out);
    strip_fill(&mut out);
    let mut drop = leading_white(&out);
    let mut used = vec![false; out.len()];
    for (i, e) in out.iter().enumerate() {
        if paints(e) && !drop[i] {
            stack_of(e).iter().for_each(|&k| used[k as usize] = true);
        }
    }
    for (i, e) in out.iter().enumerate() {
        drop[i] |= !paints(e) && !used[i];
    }
    let mut index = HashMap::new();
    let kept: Vec<(usize, Element)> = out
        .into_iter()
        .enumerate()
        .filter(|(i, _)| !drop[*i])
        .map(|(i, mut e)| {
            let s = stack(&mut e);
            *s = s.iter().filter_map(|k| index.get(k).copied()).collect();
            let n = index.len() as u32;
            index.insert(i as u32, n);
            (i, e)
        })
        .collect();
    ordered(split(kept, text_ink))
}

struct Item {
    e: Element,
    glyph: Option<Glyph>,
    ink: Option<Rect>,
    id: u32,
}

fn inked(gid: Option<u32>, unit: &str) -> bool {
    match gid {
        Some(streams::BLANK_GID) => false,
        Some(streams::UNRESOLVED_GID) | None => !unit.trim().is_empty(),
        Some(_) => true,
    }
}

fn split(kept: Vec<(usize, Element)>, text_ink: &[Ink]) -> Vec<Item> {
    let mut items = vec![];
    for (show, (orig, e)) in kept.into_iter().enumerate() {
        let id = show as u32;
        let Element::Text {
            font,
            size,
            fill,
            gids,
            m,
            tr,
            clip,
            origin,
            offs,
            units,
            ..
        } = &e
        else {
            items.push(Item {
                e,
                glyph: None,
                ink: None,
                id,
            });
            continue;
        };
        let ink = text_ink.get(orig).and_then(Option::as_ref);
        let mut last = None;
        for (k, (unit, off)) in units.iter().zip(offs).enumerate() {
            let gid = gids.get(k).copied();
            if !inked(gid, unit) {
                continue;
            }
            let at = [0, 1].map(|i| origin[i] + off[i]);
            let e = Element::Text {
                s: unit.clone(),
                font: font.clone(),
                size: *size,
                fill: fill.clone(),
                glyphs: 1,
                gids: gid.into_iter().collect(),
                m: *m,
                tr: *tr,
                clip: clip.clone(),
                origin: at,
                offs: vec![[0, 0]],
                units: vec![unit.clone()],
            };
            let step = last.map_or(k + 1, |j| k - j);
            last = Some(k);
            items.push(Item {
                e,
                glyph: Some(Glyph {
                    show,
                    line: 0,
                    at,
                    start: at,
                    step,
                }),
                ink: ink.and_then(|v| v.get(k).copied().flatten()),
                id,
            });
        }
    }
    items
}

fn gap(e: &Element) -> i64 {
    let Element::Text { m, .. } = e else {
        return 0;
    };
    let em = (m[0] as f64).hypot(m[1] as f64) / 100.0;
    (GAP_EM * em / streams::GLYPH_QUANTUM) as i64
}

fn lines(run: &mut [Item], next: &mut usize) -> Vec<usize> {
    let at = |r: &[Item], i: usize| r[i].glyph.as_ref().map_or([0, 0], |g| g.at);
    let baseline = streams::qo(0.01);
    let mut order: Vec<usize> = (0..run.len()).collect();
    order.sort_by_key(|&i| (-at(run, i)[1], at(run, i)[0]));
    let mut bands: Vec<Vec<usize>> = vec![];
    for i in order {
        match bands.last_mut() {
            Some(b) if at(run, b[b.len() - 1])[1] - at(run, i)[1] <= baseline => b.push(i),
            _ => bands.push(vec![i]),
        }
    }
    let mut order = vec![];
    for mut band in bands {
        band.sort_by_key(|&i| at(run, i)[0]);
        let (mut start, mut step, mut prev) = ([0, 0], 0, None);
        for i in band {
            let p = at(run, i);
            match prev {
                Some(j) if p[0] - at(run, j)[0] <= gap(&run[j].e) => {
                    step += run[i].glyph.as_ref().map_or(0, |g| g.step)
                }
                _ => (start, step, *next) = (p, 0, *next + 1),
            }
            prev = Some(i);
            if let Some(g) = run[i].glyph.as_mut() {
                (g.line, g.start, g.step) = (*next, start, step);
            }
            if let Element::Text { m, .. } = &mut run[i].e {
                (m[4], m[5]) = (
                    streams::qc(start[0] as f64 * streams::GLYPH_QUANTUM),
                    streams::qc(start[1] as f64 * streams::GLYPH_QUANTUM),
                );
            }
            order.push(i);
        }
    }
    order
}

fn look(e: &Element) -> (String, i64) {
    match e {
        Element::Text { fill, tr, .. } => (format!("{fill:?}"), *tr),
        _ => (String::new(), 0),
    }
}

fn clash(run: &[Item], rank: &[usize]) -> bool {
    let touch = |a: Option<Rect>, b: Option<Rect>| match (a, b) {
        (Some(a), Some(b)) => meet(a, b).is_some(),
        _ => true,
    };
    (0..run.len()).any(|i| {
        (i + 1..run.len()).any(|j| {
            rank[i] > rank[j] && look(&run[i].e) != look(&run[j].e) && touch(run[i].ink, run[j].ink)
        })
    })
}

fn ordered(items: Vec<Item>) -> Canon {
    let mut out: Vec<Item> = vec![];
    let (mut paint_order_runs, mut line) = (0, 0);
    let mut rest = items.into_iter().peekable();
    while let Some(first) = rest.next() {
        if first.glyph.is_none() {
            out.push(first);
            continue;
        }
        let mut run = vec![first];
        while let Some(next) = rest.next_if(|x| x.glyph.is_some()) {
            run.push(next);
        }
        let order = lines(&mut run, &mut line);
        let mut rank = vec![0; run.len()];
        order.iter().enumerate().for_each(|(r, &i)| rank[i] = r);
        if clash(&run, &rank) {
            paint_order_runs += 1;
            out.extend(run);
            continue;
        }
        let mut slots: Vec<Option<Item>> = run.into_iter().map(Some).collect();
        out.extend(order.iter().filter_map(|&i| slots[i].take()));
    }
    let at: HashMap<u32, u32> = out
        .iter()
        .enumerate()
        .filter(|(_, x)| x.glyph.is_none())
        .map(|(n, x)| (x.id, n as u32))
        .collect();
    let (mut elements, mut glyphs) = (vec![], vec![]);
    for Item { mut e, glyph, .. } in out {
        let s = stack(&mut e);
        *s = s.iter().filter_map(|k| at.get(k).copied()).collect();
        elements.push(e);
        glyphs.push(glyph);
    }
    Canon {
        elements,
        glyphs,
        paint_order_runs,
    }
}

struct Glyphs {
    upem: f64,
    boxes: Vec<Option<ttf_parser::Rect>>,
}

fn load_glyphs(file: &str) -> Result<Glyphs> {
    let data = std::fs::read(file).with_context(|| format!("reading vendored face {file}"))?;
    let face = ttf_parser::Face::parse(&data, 0)
        .with_context(|| format!("parsing vendored face {file}"))?;
    Ok(Glyphs {
        upem: f64::from(face.units_per_em()),
        boxes: (0..face.number_of_glyphs())
            .map(|g| face.glyph_bounding_box(ttf_parser::GlyphId(g)))
            .collect(),
    })
}

pub struct Inks<'a> {
    map: &'a BTreeMap<String, Face>,
    faces: HashMap<String, Option<Glyphs>>,
}

impl<'a> Inks<'a> {
    pub fn new(map: &'a BTreeMap<String, Face>) -> Self {
        Inks {
            map,
            faces: HashMap::new(),
        }
    }

    pub fn page(&mut self, elements: &[Element]) -> Result<Vec<Ink>> {
        elements.iter().map(|e| self.text(e)).collect()
    }

    fn text(&mut self, e: &Element) -> Result<Ink> {
        let Element::Text {
            font,
            gids,
            m,
            origin,
            offs,
            ..
        } = e
        else {
            return Ok(None);
        };
        if !self.faces.contains_key(font) {
            let file = self
                .map
                .values()
                .find(|f| &f.face == font)
                .map(|f| f.file.clone());
            let glyphs = file.map(|f| load_glyphs(&f)).transpose()?;
            self.faces.insert(font.clone(), glyphs);
        }
        let Some(g) = &self.faces[font] else {
            return Ok(None);
        };
        let lin = |i: usize| m[i] as f64 / 100.0 / g.upem;
        let lo = |v: f64| (v * 100.0).floor() as i64 - 1;
        let hi = |v: f64| (v * 100.0).ceil() as i64 + 1;
        let mut out = vec![];
        for (k, o) in offs.iter().enumerate() {
            let id = gids.get(k).copied().unwrap_or(streams::UNRESOLVED_GID);
            if id == streams::BLANK_GID {
                out.push(None);
                continue;
            }
            let Some(b) = g.boxes.get(id as usize).copied().flatten() else {
                return Ok(None);
            };
            let [ox, oy] = [0, 1].map(|i| (origin[i] + o[i]) as f64 * streams::GLYPH_QUANTUM);
            let pts = [
                (b.x_min, b.y_min),
                (b.x_max, b.y_min),
                (b.x_min, b.y_max),
                (b.x_max, b.y_max),
            ]
            .map(|(x, y)| {
                let (x, y) = (f64::from(x), f64::from(y));
                (ox + lin(0) * x + lin(2) * y, oy + lin(1) * x + lin(3) * y)
            });
            let (xs, ys) = (pts.map(|p| p.0), pts.map(|p| p.1));
            let min = |v: [f64; 4]| v.into_iter().fold(f64::INFINITY, f64::min);
            let max = |v: [f64; 4]| v.into_iter().fold(f64::NEG_INFINITY, f64::max);
            out.push(Some([lo(min(xs)), lo(min(ys)), hi(max(xs)), hi(max(ys))]));
        }
        Ok(Some(out))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn color(rgb: [i64; 3]) -> streams::Color {
        streams::Color {
            family: "rgb".into(),
            rgb,
        }
    }

    const INK: [i64; 3] = [14, 19, 22];
    const PAGE: &str = "re 0 0 41953 0 41953 59528 0 59528";
    const RULE: &str = "re 4400 56755 37701 56755 37701 56700 4400 56700";

    fn fill(d: &str, rgb: [i64; 3], clip: &[u32]) -> Element {
        Element::Path {
            d: d.into(),
            paint: "fill".into(),
            fill: Some(color(rgb)),
            stroke: None,
            lw: None,
            cap: None,
            join: None,
            miter: None,
            dash: None,
            clip: clip.to_vec(),
        }
    }

    fn stroke(d: &str, clip: &[u32]) -> Element {
        Element::Path {
            d: d.into(),
            paint: "stroke".into(),
            fill: None,
            stroke: Some(color(INK)),
            lw: Some(55),
            cap: Some(0),
            join: Some(0),
            miter: Some(400),
            dash: Some((vec![], 0)),
            clip: clip.to_vec(),
        }
    }

    fn clip(d: &str, clip: &[u32]) -> Element {
        Element::Clip {
            d: d.into(),
            evenodd: false,
            clip: clip.to_vec(),
        }
    }

    fn text(clip: &[u32]) -> Element {
        Element::Text {
            s: "a".into(),
            font: "F".into(),
            size: 1000,
            fill: color(INK),
            glyphs: 1,
            gids: vec![],
            m: [1000, 0, 0, 1000, 5000, 5000],
            tr: 0,
            clip: clip.to_vec(),
            origin: [streams::qo(50.0); 2],
            offs: vec![[0, 0]],
            units: vec!["a".into()],
        }
    }

    fn json(e: &[Element], ink: &[Ink]) -> String {
        serde_json::to_string(&canonical(e, ink).elements).unwrap()
    }

    fn same(a: &[Element], b: &[Element]) -> bool {
        json(a, &[]) == json(b, &[])
    }

    fn same_ink(a: &[Element], ink: Option<Rect>, b: &[Element]) -> bool {
        let ink: Vec<Ink> = a.iter().map(|_| ink.map(|r| vec![Some(r)])).collect();
        json(a, &ink) == json(b, &[])
    }

    #[test]
    fn a_leading_white_fill_goes_but_a_tinted_or_covering_one_stays() {
        let rule = fill(RULE, INK, &[]);
        let white = |rgb| vec![clip(PAGE, &[]), fill(PAGE, rgb, &[0]), rule.clone()];
        assert!(same(&white([255; 3]), std::slice::from_ref(&rule)));
        assert!(!same(&white([254, 255, 255]), std::slice::from_ref(&rule)));
        let over = [rule.clone(), fill(PAGE, [255; 3], &[])];
        assert!(!same(&over, std::slice::from_ref(&rule)));
    }

    #[test]
    fn a_rect_clip_holding_its_paint_goes_but_one_that_cuts_it_stays() {
        let r = "re 100 100 200 100 200 200 100 200";
        let cut = "re 100 100 199 100 199 200 100 200";
        assert!(same(
            &[clip(r, &[]), fill(r, INK, &[0])],
            &[fill(r, INK, &[])]
        ));
        assert!(!same(
            &[clip(cut, &[]), fill(r, INK, &[0])],
            &[fill(r, INK, &[])]
        ));
        let frame = "re 1000 1000 2000 1000 2000 2000 1000 2000";
        let room = "re 900 900 2100 900 2100 2100 900 2100";
        let tight = "re 1010 1010 1990 1010 1990 1990 1010 1990";
        let tight = [clip(tight, &[]), stroke(frame, &[0])];
        assert!(same(
            &[clip(room, &[]), stroke(frame, &[0])],
            &[stroke(frame, &[])]
        ));
        assert!(!same(&tight, &[stroke(frame, &[])]));
        let clipped = [clip(r, &[]), text(&[0])];
        assert!(same_ink(&clipped, Some([120, 120, 180, 180]), &[text(&[])]));
        assert!(!same_ink(
            &clipped,
            Some([120, 120, 201, 180]),
            &[text(&[])]
        ));
        assert!(!same_ink(&clipped, None, &[text(&[])]));
        let round = "m 100 150 c 100 200 200 200 200 150 c 200 100 100 100 100 150";
        assert!(!same(&[clip(round, &[]), text(&[0])], &[text(&[])]));
    }

    #[test]
    fn re_and_its_closed_four_line_path_compare_equal() {
        let lines = "m 4400 56755 l 37701 56755 l 37701 56700 l 4400 56700 h";
        assert!(same(&[stroke(RULE, &[])], &[stroke(lines, &[])]));
        assert!(same(&[fill(RULE, INK, &[])], &[fill(lines, INK, &[])]));
        let moved = "m 4400 56755 l 37702 56755 l 37701 56700 l 4400 56700 h";
        assert!(!same(&[stroke(RULE, &[])], &[stroke(moved, &[])]));
        assert!(!same(&[fill(RULE, INK, &[])], &[fill(moved, INK, &[])]));
        let later = "m 37701 56755 l 37701 56700 l 4400 56700 l 4400 56755 h";
        assert!(same(&[fill(RULE, INK, &[])], &[fill(later, INK, &[])]));
        assert!(!same(&[stroke(RULE, &[])], &[stroke(later, &[])]));
        let back = "m 4400 56755 l 4400 56700 l 37701 56700 l 37701 56755 h";
        assert!(same(&[fill(RULE, INK, &[])], &[fill(back, INK, &[])]));
        assert!(!same(&[stroke(RULE, &[])], &[stroke(back, &[])]));
        let two = format!("{RULE} {PAGE}");
        let two_back = format!("{back} {PAGE}");
        assert!(!same(&[fill(&two, INK, &[])], &[fill(&two_back, INK, &[])]));
    }

    fn weasy_bullet(bottom: i64, left: i64) -> Vec<Element> {
        let circle = format!(
            "m 4902 46637 l 4902 46637 c 5040 46637 5152 46525 5152 46387 l 5152 46387 \
             c 5152 {bottom} 5040 46137 4902 46137 l 4902 46137 c {left} 46137 4652 {bottom} \
             4652 46387 l 4652 46387 c 4652 46525 {left} 46637 4902 46637"
        );
        let square = "re 4652 46637 5152 46637 5152 46137 4652 46137";
        vec![
            clip(&circle, &[]),
            clip(square, &[0]),
            fill(square, [64, 26, 110], &[0, 1]),
        ]
    }

    fn typst_bullet() -> Vec<Element> {
        let d = "m 4652 46387 c 4652 46525 4764 46637 4902 46637 c 5040 46637 5152 46525 \
                 5152 46387 c 5152 46249 5040 46137 4902 46137 c 4764 46137 4652 46249 4652 46387";
        vec![fill(d, [64, 26, 110], &[])]
    }

    #[test]
    fn a_square_clipped_by_its_circle_is_that_circle_but_a_moved_point_is_not() {
        assert!(same(&weasy_bullet(46249, 4764), &typst_bullet()));
        assert!(!same(&weasy_bullet(46250, 4765), &typst_bullet()));
        assert!(!same(&weasy_bullet(46249, 4765), &typst_bullet()));
        let mut small = weasy_bullet(46249, 4764);
        small[2] = fill(
            "re 4700 46637 5152 46637 5152 46137 4700 46137",
            [64, 26, 110],
            &[0, 1],
        );
        assert!(!same(&small, &typst_bullet()));
    }

    fn accent(clip_d: &str) -> Vec<Element> {
        let mut bar = fill(
            "m 4950 7974 l 4950 10574 l 37300 10574 l 37300 7974 l 4950 7974 \
             m 4800 7974 l 4800 10574 l 37300 10574 l 37300 7974 l 4800 7974",
            [64, 26, 110],
            &[0],
        );
        if let Element::Path { paint, .. } = &mut bar {
            *paint = "eofill".into();
        }
        vec![clip(clip_d, &[]), bar]
    }

    #[test]
    fn a_frame_clipped_to_its_strip_is_that_strip_but_a_moved_edge_is_not() {
        let strip = "re 4800 7974 4950 7974 4950 10574 4800 10574";
        let typst = [fill(strip, [64, 26, 110], &[])];
        assert!(same(&accent(strip), &typst));
        let wide = "re 4800 7974 4951 7974 4951 10574 4800 10574";
        assert!(!same(&accent(strip), &[fill(wide, [64, 26, 110], &[])]));
        let short = "re 4800 7974 4949 7974 4949 10574 4800 10574";
        assert!(!same(&accent(short), &typst));
        let across = "re 4800 7974 5000 7974 5000 10574 4800 10574";
        assert!(same(&accent(across), &typst));
        let inset = "re 4801 7974 4950 7974 4950 10574 4801 10574";
        assert!(!same(&accent(inset), &typst));
        let hole = "re 4800 8000 4950 8000 4950 9000 4800 9000";
        let inner = "m 4900 8500 l 4900 8600 l 5000 8600 l 5000 8500 h";
        let mut ring = accent(hole);
        if let Element::Path { d, .. } = &mut ring[1] {
            *d = format!("{} {inner}", expand_rects(hole));
        }
        assert_eq!(canonical(&ring, &[]).elements.len(), 2);
    }

    #[test]
    #[ignore = "WP-0.2m-r.verify.md: rect() accepts a zero-area out-and-back loop (WP-0.2p, WP-0.2q rejected)"]
    fn a_zero_area_loop_with_rect_corners_is_not_a_rect_region() {
        let flat = "m 100 100 l 300 100 l 300 200 l 300 100 l 100 100";
        let hidden = [clip(flat, &[]), text(&[0])];
        let round = "m 100 150 c 100 200 200 200 200 150 c 200 100 100 100 100 150";
        let cover = "m 50 50 l 250 50 l 250 250 l 250 50 l 50 50";
        let nothing = [clip(round, &[]), fill(cover, INK, &[0])];
        let mut bar = fill(
            "m 100 100 l 300 100 l 300 120 l 100 120 l 100 100 \
             m 100 100 l 200 100 l 200 120 l 200 100 l 100 100",
            INK,
            &[0],
        );
        if let Element::Path { paint, .. } = &mut bar {
            *paint = "eofill".into();
        }
        let whole = [clip("re 100 105 300 105 300 115 100 115", &[]), bar];
        let half = [fill("re 200 105 300 105 300 115 200 115", INK, &[])];
        let equal = [
            same_ink(&hidden, Some([120, 120, 180, 180]), &[text(&[])]),
            same(&nothing, &[fill(round, INK, &[])]),
            same(&whole, &half),
        ];
        assert_eq!(equal, [false; 3]);
    }
}
