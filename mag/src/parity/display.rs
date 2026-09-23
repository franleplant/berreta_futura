use super::streams::{self, qc, Caches, Color, Element, Face};
use anyhow::{bail, Context, Result};
use lopdf::{Document, Object};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;

#[path = "canon.rs"]
mod canon;

#[derive(Serialize)]
pub struct PageDump {
    pub elements: Vec<Element>,
    pub annots: Vec<Annot>,
    pub boxes: BTreeMap<String, [i64; 4]>,
    #[serde(skip)]
    pub ink: Vec<Option<canon::Rect>>,
}

impl PageDump {
    fn canonical(&self) -> Vec<Element> {
        canon::canonical(&self.elements, &self.ink)
    }
}

#[derive(Serialize, PartialEq, Eq, PartialOrd, Ord, Clone)]
pub struct Annot {
    pub subtype: String,
    pub rect: [i64; 4],
    pub dest: String,
}

#[derive(Serialize, PartialEq, Eq)]
pub struct DocNav {
    pub title: Option<String>,
    pub lang: Option<String>,
    pub outlines: Vec<(String, u32)>,
}

pub struct Dump {
    pub pages: Vec<PageDump>,
    pub nav: DocNav,
}

#[allow(dead_code)]
pub fn trace_elements(
    pdf: &Path,
    first: u32,
    last: u32,
    font_map: &BTreeMap<String, Face>,
) -> Result<Vec<Vec<Element>>> {
    let doc = Document::load(pdf).with_context(|| format!("loading {}", pdf.display()))?;
    let page_ids = doc.get_pages();
    let mut caches = Caches::new();
    let mut pages = vec![];
    for number in first..=last {
        let id = *page_ids
            .get(&number)
            .with_context(|| format!("page {number} missing"))?;
        pages.push(
            streams::trace_page(&doc, id, font_map, &mut caches)
                .with_context(|| format!("tracing page {number} of {}", pdf.display()))?,
        );
    }
    Ok(pages)
}

pub fn extract(
    pdf: &Path,
    first: u32,
    last: u32,
    font_map: &BTreeMap<String, Face>,
) -> Result<Dump> {
    let doc = Document::load(pdf).with_context(|| format!("loading {}", pdf.display()))?;
    let page_ids = doc.get_pages();
    let mut caches = Caches::new();
    let mut inks = canon::Inks::new(font_map);
    let mut pages = vec![];
    for number in first..=last {
        let id = *page_ids
            .get(&number)
            .with_context(|| format!("page {number} missing"))?;
        let elements = streams::trace_page(&doc, id, font_map, &mut caches)
            .with_context(|| format!("tracing page {number} of {}", pdf.display()))?;
        let annots = page_annots(&doc, id, &page_ids)
            .with_context(|| format!("annotations page {number}"))?;
        let boxes = page_boxes(&doc, id)?;
        let ink = inks.page(&elements)?;
        pages.push(PageDump {
            elements,
            annots,
            boxes,
            ink,
        });
    }
    let nav = doc_nav(&doc, &page_ids, first, last)?;
    Ok(Dump { pages, nav })
}

fn qr(v: f64) -> i64 {
    (v * 2.0).round() as i64
}

fn link_rect(n: &[f64]) -> [i64; 4] {
    let (x, y) = ((qr(n[0]), qr(n[2])), (qr(n[1]), qr(n[3])));
    [x.0.min(x.1), y.0.min(y.1), x.0.max(x.1), y.0.max(y.1)]
}

fn text_string(bytes: &[u8]) -> String {
    match bytes.strip_prefix(&[0xFE, 0xFF]) {
        Some(rest) => {
            let units: Vec<u16> = rest
                .chunks(2)
                .map(|c| u16::from(c[0]) << 8 | u16::from(c.get(1).copied().unwrap_or(0)))
                .collect();
            String::from_utf16_lossy(&units)
        }
        None => bytes.iter().map(|&b| char::from(b)).collect(),
    }
}

fn page_annots(
    doc: &Document,
    page_id: lopdf::ObjectId,
    page_ids: &BTreeMap<u32, lopdf::ObjectId>,
) -> Result<Vec<Annot>> {
    let page = doc.get_dictionary(page_id)?;
    let mut out = vec![];
    let Ok(annots) = page.get(b"Annots") else {
        return Ok(out);
    };
    let annots = deref(doc, annots)?.as_array()?.clone();
    for a in &annots {
        let dict = deref(doc, a)?.as_dict()?;
        let subtype = match dict.get(b"Subtype") {
            Ok(Object::Name(n)) => String::from_utf8_lossy(n).into_owned(),
            _ => "unknown".into(),
        };
        anyhow::ensure!(
            dict.get(b"AP").is_err(),
            "annotation {subtype} carries an appearance stream, which the display list does not compare (fail loud per Tier E)"
        );
        let rect_arr = deref(doc, dict.get(b"Rect")?)?.as_array()?;
        let nums: Result<Vec<f64>> = rect_arr.iter().map(|o| number(doc, o)).collect();
        let rect = link_rect(&nums?);
        let dest = link_dest(doc, dict, page_ids)?;
        out.push(Annot {
            subtype,
            rect,
            dest,
        });
    }
    Ok(out)
}

fn link_dest(
    doc: &Document,
    dict: &lopdf::Dictionary,
    page_ids: &BTreeMap<u32, lopdf::ObjectId>,
) -> Result<String> {
    if let Ok(dest) = dict.get(b"Dest") {
        return dest_target(doc, deref(doc, dest)?, page_ids);
    }
    let Ok(action) = dict.get(b"A") else {
        return Ok("none".into());
    };
    let action = deref(doc, action)?.as_dict()?;
    match action.get(b"S") {
        Ok(Object::Name(s)) if s == b"URI" => {
            let uri = deref(doc, action.get(b"URI")?)?;
            match uri {
                Object::String(bytes, _) => Ok(format!("uri:{}", text_string(bytes))),
                other => bail!("URI action target {other:?}"),
            }
        }
        Ok(Object::Name(s)) if s == b"GoTo" => {
            dest_target(doc, deref(doc, action.get(b"D")?)?, page_ids)
        }
        other => bail!("annotation action {other:?} unsupported"),
    }
}

fn dest_target(
    doc: &Document,
    dest: &Object,
    page_ids: &BTreeMap<u32, lopdf::ObjectId>,
) -> Result<String> {
    let arr = match dest {
        Object::Array(a) => a.clone(),
        Object::String(name, _) | Object::Name(name) => {
            named_dest(doc, name).context("resolving named destination")?
        }
        other => bail!("destination {other:?} unsupported"),
    };
    let page_ref = arr.first().context("empty destination")?;
    let Object::Reference(id) = page_ref else {
        bail!("destination page not a reference");
    };
    let number = page_ids
        .iter()
        .find(|(_, pid)| *pid == id)
        .map(|(n, _)| *n)
        .context("destination page not in document")?;
    Ok(format!("page:{number}"))
}

fn named_dest(doc: &Document, name: &[u8]) -> Result<Vec<Object>> {
    let catalog = doc.catalog()?;
    let names = deref(doc, catalog.get(b"Names")?)?.as_dict()?;
    let dests = deref(doc, names.get(b"Dests")?)?.as_dict()?;
    let mut stack = vec![dests.clone()];
    while let Some(node) = stack.pop() {
        if let Ok(kids) = node.get(b"Kids") {
            for kid in deref(doc, kids)?.as_array()? {
                stack.push(deref(doc, kid)?.as_dict()?.clone());
            }
        }
        if let Ok(pairs) = node.get(b"Names") {
            let pairs = deref(doc, pairs)?.as_array()?;
            for pair in pairs.chunks(2) {
                if let Object::String(n, _) = deref(doc, &pair[0])? {
                    if n == name {
                        let target = deref(doc, &pair[1])?;
                        return match target {
                            Object::Array(a) => Ok(a.clone()),
                            Object::Dictionary(d) => {
                                Ok(deref(doc, d.get(b"D")?)?.as_array()?.clone())
                            }
                            other => bail!("named dest value {other:?}"),
                        };
                    }
                }
            }
        }
    }
    bail!(
        "named destination {} not found",
        String::from_utf8_lossy(name)
    )
}

fn page_boxes(doc: &Document, page_id: lopdf::ObjectId) -> Result<BTreeMap<String, [i64; 4]>> {
    let mut out = BTreeMap::new();
    let mut effective = None;
    for key in ["MediaBox", "CropBox", "TrimBox"] {
        if let Some(obj) = page_attr(doc, page_id, key.as_bytes())? {
            let arr = deref(doc, &obj)?.as_array()?.clone();
            let nums: Result<Vec<f64>> = arr.iter().map(|o| number(doc, o)).collect();
            let nums = nums?;
            effective = Some([qc(nums[0]), qc(nums[1]), qc(nums[2]), qc(nums[3])]);
        }
        let value = effective.with_context(|| format!("page has no {key} and no default"))?;
        out.insert(key.to_string(), value);
    }
    Ok(out)
}

fn page_attr(doc: &Document, page_id: lopdf::ObjectId, key: &[u8]) -> Result<Option<Object>> {
    let mut node = doc.get_dictionary(page_id)?.clone();
    loop {
        if let Ok(v) = node.get(key) {
            return Ok(Some(v.clone()));
        }
        match node.get(b"Parent") {
            Ok(Object::Reference(pid)) => node = doc.get_dictionary(*pid)?.clone(),
            _ => return Ok(None),
        }
    }
}

fn doc_nav(
    doc: &Document,
    page_ids: &BTreeMap<u32, lopdf::ObjectId>,
    first: u32,
    last: u32,
) -> Result<DocNav> {
    let title = doc
        .trailer
        .get(b"Info")
        .ok()
        .and_then(|info| deref(doc, info).ok())
        .and_then(|info| info.as_dict().ok())
        .and_then(|info| info.get(b"Title").ok())
        .and_then(|t| match t {
            Object::String(bytes, _) => Some(text_string(bytes)),
            _ => None,
        });
    let catalog = doc.catalog()?;
    let lang = catalog.get(b"Lang").ok().and_then(|l| match l {
        Object::String(bytes, _) => Some(text_string(bytes)),
        _ => None,
    });
    let mut outlines = vec![];
    if let Ok(root) = catalog.get(b"Outlines") {
        let root = deref(doc, root)?.as_dict()?.clone();
        collect_outlines(doc, &root, page_ids, first, last, &mut outlines)?;
    }
    Ok(DocNav {
        title,
        lang,
        outlines,
    })
}

fn collect_outlines(
    doc: &Document,
    node: &lopdf::Dictionary,
    page_ids: &BTreeMap<u32, lopdf::ObjectId>,
    first: u32,
    last: u32,
    out: &mut Vec<(String, u32)>,
) -> Result<()> {
    let mut child = node.get(b"First").ok().cloned();
    while let Some(Object::Reference(id)) = child {
        let entry = doc.get_dictionary(id)?.clone();
        let title = match entry.get(b"Title") {
            Ok(Object::String(bytes, _)) => text_string(bytes),
            _ => String::new(),
        };
        let target = link_dest(doc, &entry, page_ids)?;
        if let Some(page) = target
            .strip_prefix("page:")
            .and_then(|n| n.parse::<u32>().ok())
        {
            if page >= first && page <= last {
                out.push((title, page));
            }
        }
        collect_outlines(doc, &entry, page_ids, first, last, out)?;
        child = entry.get(b"Next").ok().cloned();
    }
    Ok(())
}

fn deref<'a>(doc: &'a Document, o: &'a Object) -> Result<&'a Object> {
    match o {
        Object::Reference(id) => Ok(doc.get_object(*id)?),
        other => Ok(other),
    }
}

fn number(doc: &Document, o: &Object) -> Result<f64> {
    match deref(doc, o)? {
        Object::Integer(i) => Ok(*i as f64),
        Object::Real(r) => Ok(f64::from(*r)),
        other => bail!("expected number, got {other:?}"),
    }
}

#[derive(Serialize)]
pub struct DisplayClause {
    pub status: String,
    pub elements_a: usize,
    pub elements_b: usize,
    pub pages_differing: Vec<PageDiff>,
}

#[derive(Serialize)]
pub struct PageDiff {
    pub page: u32,
    pub detail: String,
    pub classes: BTreeMap<String, usize>,
}

pub fn compare_display(a: &Dump, b: &Dump, first: u32) -> Result<DisplayClause> {
    let mut pages_differing = vec![];
    for (i, (pa, pb)) in a.pages.iter().zip(&b.pages).enumerate() {
        let page = first + i as u32;
        let (ea, eb) = (pa.canonical(), pb.canonical());
        if let Some(detail) = page_diff(pa, pb, &ea, &eb)? {
            let classes = differing_classes(pa, pb, &ea, &eb)?;
            pages_differing.push(PageDiff {
                page,
                detail,
                classes,
            });
        }
    }
    let count = |d: &Dump| d.pages.iter().map(|p| p.canonical().len()).sum();
    Ok(DisplayClause {
        status: status(pages_differing.is_empty()),
        elements_a: count(a),
        elements_b: count(b),
        pages_differing,
    })
}

fn page_diff(a: &PageDump, b: &PageDump, ea: &[Element], eb: &[Element]) -> Result<Option<String>> {
    if a.boxes != b.boxes {
        return Ok(Some("page boxes differ".into()));
    }
    if a.annots != b.annots {
        return Ok(Some(format!(
            "annotations differ ({} vs {})",
            a.annots.len(),
            b.annots.len()
        )));
    }
    for (i, (x, y)) in ea.iter().zip(eb).enumerate() {
        let (sa, sb) = (serde_json::to_string(x)?, serde_json::to_string(y)?);
        if sa != sb {
            return Ok(Some(format!(
                "element {i}: {} vs {}",
                clipped(&sa),
                clipped(&sb)
            )));
        }
    }
    Ok((ea.len() != eb.len()).then(|| format!("element count {} vs {}", ea.len(), eb.len())))
}

fn class_keys(elements: &[Element]) -> Result<Vec<(String, String)>> {
    elements
        .iter()
        .map(|e| {
            let mut v = serde_json::to_value(e)?;
            let clips: Vec<serde_json::Value> = v["clip"]
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(|k| elements.get(k.as_u64()? as usize))
                .map(|c| serde_json::to_value(c).map(|c| c["d"].clone()))
                .collect::<serde_json::Result<_>>()?;
            v["clip"] = clips.into();
            let kind = v["kind"].as_str().unwrap_or("element").to_lowercase();
            Ok((kind, v.to_string()))
        })
        .collect()
}

fn unmatched<T: Ord + Clone>(a: &[T], b: &[T]) -> usize {
    let mut left: BTreeMap<T, i64> = BTreeMap::new();
    a.iter()
        .for_each(|x| *left.entry(x.clone()).or_default() += 1);
    b.iter()
        .for_each(|x| *left.entry(x.clone()).or_default() -= 1);
    left.values().map(|n| n.unsigned_abs() as usize).sum()
}

fn differing_classes(
    a: &PageDump,
    b: &PageDump,
    ea: &[Element],
    eb: &[Element],
) -> Result<BTreeMap<String, usize>> {
    let (ka, kb) = (class_keys(ea)?, class_keys(eb)?);
    let mut out = BTreeMap::new();
    out.insert("boxes".to_string(), usize::from(a.boxes != b.boxes));
    out.insert("annotations".to_string(), unmatched(&a.annots, &b.annots));
    for kind in ["text", "path", "clip", "image"] {
        let of = |k: &[(String, String)]| -> Vec<String> {
            k.iter()
                .filter(|x| x.0 == kind)
                .map(|x| x.1.clone())
                .collect()
        };
        out.insert(kind.to_string(), unmatched(&of(&ka), &of(&kb)));
    }
    let same = out.values().all(|n| *n == 0);
    out.insert("order".to_string(), usize::from(same && ka != kb));
    out.retain(|_, n| *n > 0);
    Ok(out)
}

fn clipped(s: &str) -> String {
    if s.len() > 300 {
        format!("{}...", &s[..300])
    } else {
        s.to_string()
    }
}

#[derive(Serialize)]
pub struct SimpleClause {
    pub status: String,
    pub entries_compared: usize,
    pub pages_differing: Vec<u32>,
    pub details: Vec<String>,
}

#[derive(Serialize)]
pub struct GlyphClause {
    pub status: String,
    pub glyphs: usize,
    pub shows: usize,
    pub worst_excess_pt: f64,
    pub worst_ratio: f64,
    pub worst: Option<String>,
    pub violations: Vec<String>,
}

fn axis_shape(d: &[i64]) -> bool {
    let mut sign = 0i64;
    let mut prev = 0i64;
    for v in d {
        let s = v.signum();
        if s != 0 {
            if sign != 0 && s != sign {
                return false;
            }
            sign = s;
        }
        if v.abs() < prev {
            return false;
        }
        prev = v.abs();
    }
    true
}

pub fn compare_glyphs(a: &Dump, b: &Dump, first: u32) -> GlyphClause {
    let mut glyphs = 0;
    let mut shows = 0;
    let mut worst_excess = f64::NEG_INFINITY;
    let mut worst_ratio = 0.0f64;
    let mut worst = None;
    let mut violations = vec![];
    for (i, (pa, pb)) in a.pages.iter().zip(&b.pages).enumerate() {
        let page = first + i as u32;
        for (j, (ea, eb)) in pa.elements.iter().zip(&pb.elements).enumerate() {
            let (Element::Text { offs: oa, .. }, Element::Text { offs: ob, .. }) = (ea, eb) else {
                continue;
            };
            if oa.len() != ob.len() {
                violations.push(format!(
                    "page {page} element {j}: {} glyphs vs {}",
                    oa.len(),
                    ob.len()
                ));
                continue;
            }
            shows += 1;
            glyphs += oa.len();
            let dx: Vec<i64> = oa.iter().zip(ob).map(|(p, q)| p[0] - q[0]).collect();
            let dy: Vec<i64> = oa.iter().zip(ob).map(|(p, q)| p[1] - q[1]).collect();
            for (k, (x, y)) in dx.iter().zip(&dy).enumerate() {
                let mag = ((*x as f64).hypot(*y as f64)) * streams::GLYPH_QUANTUM;
                let bound = k as f64 * streams::GLYPH_DRIFT_PT;
                if bound > 0.0 {
                    worst_ratio = worst_ratio.max(mag / bound);
                }
                let excess = mag - bound;
                if excess > worst_excess {
                    worst_excess = excess;
                    worst = Some(format!("page {page} element {j} glyph {k}: {mag:.6} pt"));
                }
                if excess > 0.0 {
                    violations.push(format!(
                        "page {page} element {j} glyph {k}: {mag:.6} pt exceeds bound {:.6} pt",
                        k as f64 * streams::GLYPH_DRIFT_PT
                    ));
                }
            }
            if !axis_shape(&dx) || !axis_shape(&dy) {
                violations.push(format!(
                    "page {page} element {j}: difference sequence is not one-signed and monotone"
                ));
            }
        }
    }
    violations.truncate(40);
    GlyphClause {
        status: status(violations.is_empty()),
        glyphs,
        shows,
        worst_excess_pt: if worst_excess.is_finite() {
            worst_excess
        } else {
            0.0
        },
        worst_ratio,
        worst,
        violations,
    }
}

fn status(pass: bool) -> String {
    if pass { "pass" } else { "fail" }.into()
}

type Paint = (String, Option<Color>);

fn color_sequences(page: &PageDump) -> [Vec<Paint>; 2] {
    let mut glyphs = vec![];
    let mut paints = vec![];
    for e in &page.canonical() {
        match e {
            Element::Text {
                units,
                fill,
                tr,
                m,
                offs,
                gids,
                ..
            } => {
                for (k, (u, o)) in units.iter().zip(offs).enumerate() {
                    let inked = match gids.get(k) {
                        Some(&streams::BLANK_GID) => false,
                        Some(&streams::UNRESOLVED_GID) | None => !u.trim().is_empty(),
                        Some(_) => true,
                    };
                    let at = |i: usize| {
                        qc(m[i + 4] as f64 / 100.0 + o[i] as f64 * streams::GLYPH_QUANTUM)
                    };
                    if inked {
                        glyphs.push((
                            (-at(1), at(0)),
                            (u.clone(), (*tr != 3).then(|| fill.clone())),
                        ));
                    }
                }
            }
            Element::Path { fill, stroke, .. } => {
                paints.extend(fill.iter().map(|c| ("fill".into(), Some(c.clone()))));
                paints.extend(stroke.iter().map(|c| ("stroke".into(), Some(c.clone()))));
            }
            _ => {}
        }
    }
    glyphs.sort_by_key(|g| g.0);
    [glyphs.into_iter().map(|g| g.1).collect(), paints]
}

fn first_difference(kind: &str, a: &[Paint], b: &[Paint]) -> Option<String> {
    let show = |p: &Paint| match &p.1 {
        Some(c) => format!("{:?} {} {:?}", p.0, c.family, c.rgb),
        None => format!("{:?} invisible", p.0),
    };
    match a.iter().zip(b).position(|(x, y)| x != y) {
        Some(k) => {
            let near = |s: &[Paint]| {
                s[k..]
                    .iter()
                    .take(16)
                    .map(|p| p.0.as_str())
                    .collect::<String>()
            };
            Some(format!(
                "{kind} {k}: {} vs {} (from here {:?} vs {:?})",
                show(&a[k]),
                show(&b[k]),
                near(a),
                near(b)
            ))
        }
        None => (a.len() != b.len()).then(|| format!("{} {kind}s vs {}", a.len(), b.len())),
    }
}

pub fn compare_color(a: &Dump, b: &Dump, first: u32) -> SimpleClause {
    let mut pages_differing = vec![];
    let mut details = vec![];
    for (i, (pa, pb)) in a.pages.iter().zip(&b.pages).enumerate() {
        let ([ga, sa], [gb, sb]) = (color_sequences(pa), color_sequences(pb));
        let diff = first_difference("glyph", &ga, &gb).or(first_difference("paint", &sa, &sb));
        if let Some(d) = diff {
            pages_differing.push(first + i as u32);
            details.push(format!("page {}: {d}", first + i as u32));
        }
    }
    SimpleClause {
        status: status(pages_differing.is_empty()),
        entries_compared: a
            .pages
            .iter()
            .map(|p| color_sequences(p).iter().map(Vec::len).sum::<usize>())
            .sum(),
        pages_differing,
        details,
    }
}

#[derive(Serialize)]
pub struct NavClause {
    pub status: String,
    pub annots_compared: usize,
    pub links_compared: usize,
    pub outlines_compared: usize,
    pub title_compared: usize,
    pub lang_compared: usize,
    pub mismatches: Vec<String>,
}

pub fn compare_navigation(a: &Dump, b: &Dump, first: u32) -> NavClause {
    let mut mismatches = vec![];
    for (i, (pa, pb)) in a.pages.iter().zip(&b.pages).enumerate() {
        if pa.annots != pb.annots {
            mismatches.push(format!(
                "page {}: annotations {} vs {}",
                first + i as u32,
                pa.annots.len(),
                pb.annots.len()
            ));
        }
    }
    if a.nav != b.nav {
        mismatches.push("document title/lang/outlines differ".into());
    }
    let annots = || a.pages.iter().flat_map(|p| &p.annots);
    NavClause {
        status: status(mismatches.is_empty()),
        annots_compared: annots().count(),
        links_compared: annots().filter(|x| x.subtype == "Link").count(),
        outlines_compared: a.nav.outlines.len(),
        title_compared: usize::from(a.nav.title.is_some()),
        lang_compared: usize::from(a.nav.lang.is_some()),
        mismatches,
    }
}

#[cfg(test)]
mod box_tests {
    use super::*;
    use lopdf::dictionary;

    fn boxes(page: lopdf::Dictionary) -> Result<BTreeMap<String, [i64; 4]>> {
        let mut doc = Document::with_version("1.7");
        let id = doc.add_object(page);
        page_boxes(&doc, id)
    }

    fn a5(extra: &[(&str, [f64; 4])]) -> lopdf::Dictionary {
        let mut page =
            dictionary! { "MediaBox" => vec![0.into(), 0.into(), 419.53.into(), 595.28.into()] };
        for (key, b) in extra {
            page.set(
                *key,
                b.iter()
                    .map(|&v| Object::Real(v as f32))
                    .collect::<Vec<_>>(),
            );
        }
        page
    }

    #[test]
    fn a_missing_trim_or_crop_box_takes_its_pdf_default() {
        let media = [0.0, 0.0, 419.53, 595.28];
        let stated = boxes(a5(&[("CropBox", media), ("TrimBox", media)])).unwrap();
        assert_eq!(boxes(a5(&[])).unwrap(), stated);
        assert_eq!(boxes(a5(&[("TrimBox", media)])).unwrap(), stated);
        let crop = [10.0, 10.0, 409.53, 585.28];
        let cropped = boxes(a5(&[("CropBox", crop)])).unwrap();
        assert_eq!(cropped["TrimBox"], cropped["CropBox"]);
        assert_eq!(cropped["TrimBox"], [1000, 1000, 40953, 58528]);
    }

    #[test]
    fn a_genuinely_different_effective_box_still_differs() {
        let media = [0.0, 0.0, 419.53, 595.28];
        let plain = boxes(a5(&[])).unwrap();
        assert_ne!(
            boxes(a5(&[("TrimBox", [9.0, 9.0, 410.53, 586.28])])).unwrap(),
            plain
        );
        assert_ne!(
            boxes(a5(&[("CropBox", [0.0, 0.0, 419.53, 590.0])])).unwrap(),
            plain
        );
        assert_ne!(
            boxes(a5(&[("TrimBox", media)])).unwrap(),
            boxes(a5(&[("CropBox", [0.0, 0.0, 400.0, 595.28])])).unwrap()
        );
        let e = boxes(dictionary! {}).err().unwrap().to_string();
        assert!(e.contains("no MediaBox"), "{e}");
    }
}

#[cfg(test)]
mod colour_tests {
    use super::*;

    const INK: [i64; 3] = [14, 19, 22];
    const VIOLET: [i64; 3] = [49, 93, 140];

    fn run(text: &str, x: i64, y: i64, rgb: [i64; 3], tr: i64) -> Element {
        let units: Vec<String> = text.chars().map(String::from).collect();
        Element::Text {
            s: text.into(),
            font: "F".into(),
            size: 1000,
            fill: Color {
                family: "rgb".into(),
                rgb,
            },
            glyphs: units.len(),
            gids: vec![],
            m: [1000, 0, 0, 1000, x, y],
            tr,
            clip: vec![],
            offs: (0..units.len() as i64).map(|k| [k * 10_000, 0]).collect(),
            units,
        }
    }

    fn dump(elements: Vec<Element>) -> Dump {
        Dump {
            pages: vec![PageDump {
                elements,
                annots: vec![],
                boxes: BTreeMap::new(),
                ink: vec![],
            }],
            nav: DocNav {
                title: None,
                lang: None,
                outlines: vec![],
            },
        }
    }

    fn one_show() -> Dump {
        dump(vec![
            run("Hello world", 1000, 5000, INK, 0),
            run("Head", 1000, 9000, VIOLET, 0),
        ])
    }

    fn detail(b: Vec<Element>) -> Vec<String> {
        compare_color(&one_show(), &dump(b), 3).details
    }

    #[test]
    fn the_same_glyph_colours_pass_whatever_the_segmentation_or_paint_order() {
        let c = compare_color(
            &one_show(),
            &dump(vec![
                run("Head", 1000, 9000, VIOLET, 0),
                run("world", 1000 + 549, 5000, INK, 0),
                run("Hello", 1000, 5000, INK, 0),
            ]),
            3,
        );
        assert_eq!((c.status.as_str(), c.entries_compared), ("pass", 14));
    }

    #[test]
    fn one_glyph_in_another_colour_fails_and_names_it() {
        let d = detail(vec![
            run("Hel", 1000, 5000, INK, 0),
            run("l", 1000 + 275, 5000, VIOLET, 0),
            run("o world", 1000 + 366, 5000, INK, 0),
            run("Head", 1000, 9000, VIOLET, 0),
        ]);
        assert_eq!(d.len(), 1);
        assert!(
            d[0].starts_with("page 3: glyph 7: \"l\" rgb [14, 19, 22] vs \"l\" rgb [49, 93, 140]"),
            "{}",
            d[0]
        );
        let d = detail(vec![
            run("Hello world", 1000, 5000, INK, 3),
            run("Head", 1000, 9000, VIOLET, 0),
        ]);
        assert!(
            d[0].contains("\"H\" rgb [14, 19, 22] vs \"H\" invisible"),
            "{}",
            d[0]
        );
    }

    #[test]
    fn a_missing_or_extra_glyph_fails() {
        let d = detail(vec![
            run("Hello worl", 1000, 5000, INK, 0),
            run("Head", 1000, 9000, VIOLET, 0),
        ]);
        assert_eq!(d, ["page 3: 14 glyphs vs 13"]);
        let d = detail(vec![
            run("Hello world!", 1000, 5000, INK, 0),
            run("Head", 1000, 9000, VIOLET, 0),
        ]);
        assert_eq!(d, ["page 3: 14 glyphs vs 15"]);
    }

    #[test]
    fn only_a_glyph_without_an_outline_goes_uncompared() {
        let with_gids = |ids: Vec<u32>| {
            let mut e = run("a b", 1000, 5000, INK, 0);
            if let Element::Text { gids, .. } = &mut e {
                *gids = ids;
            }
            dump(vec![e])
        };
        let ab = dump(vec![run("ab", 1000, 5000, INK, 0)]);
        let blank = with_gids(vec![1, streams::BLANK_GID, 2]);
        assert_eq!(compare_color(&blank, &ab, 1).status, "pass");
        let inked = with_gids(vec![1, 7, 2]);
        let d = compare_color(&inked, &ab, 1).details;
        assert!(d[0].starts_with("page 1: glyph 1: \" \" rgb"), "{}", d[0]);
    }

    fn rule(rgb: [i64; 3]) -> Element {
        Element::Path {
            d: "re 0 0 100 0 100 10 0 10".into(),
            paint: "f".into(),
            fill: Some(Color {
                family: "rgb".into(),
                rgb,
            }),
            stroke: None,
            lw: None,
            cap: None,
            join: None,
            miter: None,
            dash: None,
            clip: vec![],
        }
    }

    #[test]
    fn a_leading_white_fill_is_not_paint_but_a_rule_after_it_is() {
        let a = dump(vec![rule([255; 3]), rule(INK)]);
        assert_eq!(compare_color(&a, &dump(vec![rule(INK)]), 1).status, "pass");
        let d = compare_color(&a, &dump(vec![rule(VIOLET)]), 1).details;
        assert!(
            d[0].starts_with("page 1: paint 0: \"fill\" rgb [14, 19, 22]"),
            "{}",
            d[0]
        );
    }

    #[test]
    fn a_link_rect_compares_by_its_corners_not_their_order() {
        assert_eq!(
            link_rect(&[44.0, 520.5, 100.0, 510.0]),
            link_rect(&[44.0, 510.0, 100.0, 520.5])
        );
        assert_eq!(
            link_rect(&[100.0, 520.5, 44.0, 510.0]),
            [88, 1020, 200, 1041]
        );
        assert_ne!(
            link_rect(&[44.0, 520.5, 100.0, 510.0]),
            link_rect(&[44.0, 510.0, 100.5, 520.5])
        );
    }

    #[test]
    fn every_differing_class_is_counted_beside_the_first_difference() {
        let a = dump(vec![rule(INK), run("Hello", 1000, 5000, INK, 0)]);
        let b = dump(vec![rule(VIOLET), run("Hellp", 1000, 5000, INK, 0)]);
        let c = compare_display(&a, &b, 4).unwrap();
        let p = &c.pages_differing[0];
        assert!(p.detail.starts_with("element 0: "), "{}", p.detail);
        let want = BTreeMap::from([("path".to_string(), 2), ("text".to_string(), 2)]);
        assert_eq!(p.classes, want);
        let swapped = dump(vec![run("Hello", 1000, 5000, INK, 0), rule(INK)]);
        let c = compare_display(&a, &swapped, 4).unwrap();
        let want = BTreeMap::from([("order".to_string(), 1)]);
        assert_eq!(c.pages_differing[0].classes, want);
        assert!(compare_display(&a, &a, 4)
            .unwrap()
            .pages_differing
            .is_empty());
    }

    #[test]
    fn a_rule_in_another_colour_still_fails() {
        let a = dump(vec![rule([224, 227, 229])]);
        assert_eq!(
            compare_color(&a, &dump(vec![rule([224, 227, 229])]), 1).status,
            "pass"
        );
        let d = compare_color(&a, &dump(vec![rule([224, 227, 230])]), 1).details;
        assert!(d[0].starts_with("page 1: paint 0: "), "{}", d[0]);
    }
}
