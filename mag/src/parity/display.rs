use super::streams::{self, qc, Caches, Color, Element};
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

pub fn extract(
    pdf: &Path,
    first: u32,
    last: u32,
    font_map: &BTreeMap<String, String>,
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
        let rect_arr = deref(doc, dict.get(b"Rect")?)?.as_array()?;
        let nums: Result<Vec<f64>> = rect_arr.iter().map(|o| number(doc, o)).collect();
        let nums = nums?;
        let rect = [qr(nums[0]), qr(nums[1]), qr(nums[2]), qr(nums[3])];
        let dest = annot_dest(doc, dict, page_ids)?;
        out.push(Annot {
            subtype,
            rect,
            dest,
        });
    }
    Ok(out)
}

fn annot_dest(
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
                Object::String(bytes, _) => Ok(format!("uri:{}", String::from_utf8_lossy(bytes))),
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
            Object::String(bytes, _) => Some(String::from_utf8_lossy(bytes).into_owned()),
            _ => None,
        });
    let catalog = doc.catalog()?;
    let lang = catalog.get(b"Lang").ok().and_then(|l| match l {
        Object::String(bytes, _) => Some(String::from_utf8_lossy(bytes).into_owned()),
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
            Ok(Object::String(bytes, _)) => String::from_utf8_lossy(bytes).into_owned(),
            _ => String::new(),
        };
        if let Ok(dest) = entry.get(b"Dest").or_else(|_| entry.get(b"A")) {
            if let Ok(target) = dest_target(doc, deref(doc, dest)?, page_ids) {
                if let Some(page) = target
                    .strip_prefix("page:")
                    .and_then(|n| n.parse::<u32>().ok())
                {
                    if page >= first && page <= last {
                        out.push((title, page));
                    }
                }
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
    pub pages_differing: Vec<u32>,
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
        pages_differing,
    }
}

#[derive(Serialize)]
pub struct NavClause {
    pub status: String,
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
    NavClause {
        status: status(mismatches.is_empty()),
        mismatches,
    }
}
