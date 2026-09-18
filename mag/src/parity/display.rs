use super::streams::{self, qc, Caches, Color, Element, Face};
use anyhow::{bail, Context, Result};
use lopdf::{Document, Object};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Serialize)]
pub struct PageDump {
    pub elements: Vec<Element>,
    pub annots: Vec<Annot>,
    pub boxes: BTreeMap<String, [i64; 4]>,
}

#[derive(Serialize, PartialEq, Eq, Clone)]
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
        pages.push(PageDump {
            elements,
            annots,
            boxes,
        });
    }
    let nav = doc_nav(&doc, &page_ids, first, last)?;
    Ok(Dump { pages, nav })
}

fn qr(v: f64) -> i64 {
    (v * 2.0).round() as i64
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
        let nums = nums?;
        let rect = [qr(nums[0]), qr(nums[1]), qr(nums[2]), qr(nums[3])];
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
    for key in ["MediaBox", "CropBox", "TrimBox"] {
        if let Some(obj) = page_attr(doc, page_id, key.as_bytes())? {
            let arr = deref(doc, &obj)?.as_array()?.clone();
            let nums: Result<Vec<f64>> = arr.iter().map(|o| number(doc, o)).collect();
            let nums = nums?;
            out.insert(
                key.to_string(),
                [qc(nums[0]), qc(nums[1]), qc(nums[2]), qc(nums[3])],
            );
        }
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
}

pub fn compare_display(a: &Dump, b: &Dump, first: u32) -> Result<DisplayClause> {
    let mut pages_differing = vec![];
    for (i, (pa, pb)) in a.pages.iter().zip(&b.pages).enumerate() {
        let page = first + i as u32;
        if let Some(detail) = page_diff(pa, pb)? {
            pages_differing.push(PageDiff { page, detail });
        }
    }
    let count = |d: &Dump| d.pages.iter().map(|p| p.elements.len()).sum();
    Ok(DisplayClause {
        status: status(pages_differing.is_empty()),
        elements_a: count(a),
        elements_b: count(b),
        pages_differing,
    })
}

fn page_diff(a: &PageDump, b: &PageDump) -> Result<Option<String>> {
    if serde_json::to_string(a)? == serde_json::to_string(b)? {
        return Ok(None);
    }
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
    for (i, (ea, eb)) in a.elements.iter().zip(&b.elements).enumerate() {
        let (sa, sb) = (serde_json::to_string(ea)?, serde_json::to_string(eb)?);
        if sa != sb {
            return Ok(Some(format!(
                "element {i}: {} vs {}",
                clipped(&sa),
                clipped(&sb)
            )));
        }
    }
    Ok(Some(format!(
        "element count {} vs {}",
        a.elements.len(),
        b.elements.len()
    )))
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

fn color_sequence(page: &PageDump) -> Vec<(String, Color)> {
    let mut seq = vec![];
    for e in &page.elements {
        match e {
            Element::Text { s, fill, .. } => seq.push((format!("text:{s}"), fill.clone())),
            Element::Path { fill, stroke, .. } => {
                if let Some(c) = fill {
                    seq.push(("fill".into(), c.clone()));
                }
                if let Some(c) = stroke {
                    seq.push(("stroke".into(), c.clone()));
                }
            }
            _ => {}
        }
    }
    seq
}

pub fn compare_color(a: &Dump, b: &Dump, first: u32) -> SimpleClause {
    let pages_differing: Vec<u32> = a
        .pages
        .iter()
        .zip(&b.pages)
        .enumerate()
        .filter(|(_, (pa, pb))| {
            let (sa, sb) = (color_sequence(pa), color_sequence(pb));
            sa.iter()
                .map(|(t, c)| (t, &c.family, c.rgb))
                .ne(sb.iter().map(|(t, c)| (t, &c.family, c.rgb)))
        })
        .map(|(i, _)| first + i as u32)
        .collect();
    SimpleClause {
        status: status(pages_differing.is_empty()),
        entries_compared: a.pages.iter().map(|p| color_sequence(p).len()).sum(),
        pages_differing,
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
