use super::streams::{self, qc, Caches, Color, Element, Face};
use anyhow::{bail, Context, Result};
use lopdf::{Document, Object};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

#[path = "canon.rs"]
mod canon;

#[derive(Serialize)]
pub struct PageDump {
    pub elements: Vec<Element>,
    pub annots: Vec<Annot>,
    pub boxes: BTreeMap<String, [i64; 4]>,
    #[serde(skip)]
    pub ink: Vec<canon::Ink>,
}

impl PageDump {
    fn canonical(&self) -> canon::Canon {
        canon::canonical(&self.elements, &self.ink)
    }
}

#[derive(Serialize, PartialEq, Eq, PartialOrd, Ord, Clone)]
pub struct Annot {
    pub subtype: String,
    pub rect: [i64; 4],
    pub dest: String,
    pub border: String,
    pub appearance: Option<String>,
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
    let raw = std::fs::read(pdf).with_context(|| format!("reading {}", pdf.display()))?;
    let doc = Document::load_mem(&raw).with_context(|| format!("loading {}", pdf.display()))?;
    let _exact = super::exact::authored(&doc, &raw)?;
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
    let raw = std::fs::read(pdf).with_context(|| format!("reading {}", pdf.display()))?;
    let doc = Document::load_mem(&raw).with_context(|| format!("loading {}", pdf.display()))?;
    let _exact = super::exact::authored(&doc, &raw)?;
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
    for a in deref(doc, annots)?.as_array()? {
        let dict = deref(doc, a)?.as_dict()?;
        let subtype = match dict.get(b"Subtype") {
            Ok(Object::Name(n)) => String::from_utf8_lossy(n).into_owned(),
            _ => "unknown".into(),
        };
        let appearance = match dict.get(b"AP") {
            Ok(ap) => Some(hex::encode(Sha256::digest(raw(doc, ap, 0)?))),
            Err(_) => None,
        };
        anyhow::ensure!(
            (subtype == "Link") == appearance.is_none(),
            "annotation {subtype} {} an appearance stream; only a Link without one or another subtype with one is compared (fail loud per Tier E)",
            if appearance.is_some() { "carries" } else { "lacks" }
        );
        let rect_arr = deref(doc, dict.get(b"Rect")?)?.as_array()?;
        let nums: Result<Vec<f64>> = rect_arr.iter().map(|o| number(doc, o)).collect();
        let rect = link_rect(&nums?);
        let dest = link_dest(doc, dict, page_ids)?;
        let border = link_border(doc, dict)?;
        out.push(Annot {
            subtype,
            rect,
            dest,
            border,
            appearance,
        });
    }
    Ok(out)
}

fn raw(doc: &Document, o: &Object, depth: usize) -> Result<String> {
    anyhow::ensure!(depth < 32, "annotation object nests past 32 levels");
    let all = |v: &mut dyn Iterator<Item = Result<String>>| -> Result<String> {
        Ok(v.collect::<Result<Vec<_>>>()?.join(" "))
    };
    Ok(match deref(doc, o)? {
        Object::Integer(_) | Object::Real(_) => qc(number(doc, o)?).to_string(),
        Object::Array(v) => format!("[{}]", all(&mut v.iter().map(|x| raw(doc, x, depth + 1)))?),
        Object::Dictionary(d) => format!("<<{}>>", dict_raw(doc, d, depth)?),
        Object::Stream(st) => format!(
            "<<{}>>stream {}",
            dict_raw(doc, &st.dict, depth)?,
            hex::encode(Sha256::digest(&st.content))
        ),
        other => format!("{other:?}"),
    })
}

fn dict_raw(doc: &Document, d: &lopdf::Dictionary, depth: usize) -> Result<String> {
    let mut keys: Vec<_> = d
        .iter()
        .filter(|(k, _)| k.as_slice() != b"Parent")
        .collect();
    keys.sort_by_key(|(k, _)| k.to_vec());
    let parts: Result<Vec<String>> = keys
        .into_iter()
        .map(|(k, v)| {
            Ok(format!(
                "/{} {}",
                String::from_utf8_lossy(k),
                raw(doc, v, depth + 1)?
            ))
        })
        .collect();
    Ok(parts?.join(" "))
}

fn link_border(doc: &Document, dict: &lopdf::Dictionary) -> Result<String> {
    let spec = Object::from(vec![0.into(), 0.into(), 1.into()]);
    let border = raw(doc, dict.get(b"Border").unwrap_or(&spec), 0)?;
    let key = |k: &[u8]| dict.get(k).map_or(Ok("absent".into()), |o| raw(doc, o, 0));
    let flags = dict.get(b"F").map_or(Ok(0.0), |f| number(doc, f))? as i64 & (2 | 4 | 32);
    Ok(format!(
        "border {border} bs {} colour {} flags {flags}",
        key(b"BS")?,
        key(b"C")?
    ))
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
            let arr = deref(doc, obj)?.as_array()?;
            let nums: Result<Vec<f64>> = arr.iter().map(|o| number(doc, o)).collect();
            let nums = nums?;
            effective = Some([qc(nums[0]), qc(nums[1]), qc(nums[2]), qc(nums[3])]);
        }
        let value = effective.with_context(|| format!("page has no {key} and no default"))?;
        out.insert(key.to_string(), value);
    }
    Ok(out)
}

fn page_attr<'a>(
    doc: &'a Document,
    page_id: lopdf::ObjectId,
    key: &[u8],
) -> Result<Option<&'a Object>> {
    let mut node = doc.get_dictionary(page_id)?;
    loop {
        if let Ok(v) = node.get(key) {
            return Ok(Some(v));
        }
        match node.get(b"Parent") {
            Ok(Object::Reference(pid)) => node = doc.get_dictionary(*pid)?,
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
    super::exact::num(deref(doc, o)?)
}

#[derive(Serialize)]
pub struct DisplayClause {
    pub status: String,
    pub elements_a: usize,
    pub elements_b: usize,
    pub text_runs_in_paint_order: usize,
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
        let others = |p: &PageDump| {
            p.annots
                .iter()
                .filter(|x| x.subtype != "Link")
                .cloned()
                .collect::<Vec<_>>()
        };
        anyhow::ensure!(
            others(pa) == others(pb),
            "page {page}: an annotation other than Link differs between legs; only byte-equal appearance streams are compared (fail loud per Tier E)"
        );
        let (ea, eb) = (pa.canonical().elements, pb.canonical().elements);
        if let Some(detail) = page_diff(pa, pb, &ea, &eb)? {
            let classes = differing_classes(pa, pb, &ea, &eb)?;
            pages_differing.push(PageDiff {
                page,
                detail,
                classes,
            });
        }
    }
    let count = |d: &Dump| d.pages.iter().map(|p| p.canonical().elements.len()).sum();
    let runs = |d: &Dump| -> usize { d.pages.iter().map(|p| p.canonical().paint_order_runs).sum() };
    Ok(DisplayClause {
        status: status(pages_differing.is_empty()),
        elements_a: count(a),
        elements_b: count(b),
        text_runs_in_paint_order: runs(a) + runs(b),
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

fn glyph_list(page: &PageDump) -> Vec<canon::Glyph> {
    page.canonical().glyphs.into_iter().flatten().collect()
}

fn drift(
    ga: &[canon::Glyph],
    gb: &[canon::Glyph],
    ks: &[usize],
    r: std::ops::Range<usize>,
) -> Vec<(usize, [i64; 2])> {
    r.map(|j| {
        let (a, b) = (&ga[j], &gb[j]);
        (
            ks[j],
            [0, 1].map(|i| (a.at[i] - a.start[i]) - (b.at[i] - b.start[i])),
        )
    })
    .collect()
}

const ADVANCE_QUANTA: f64 = 10.0;

pub const MIN_ADVANCE_PT: f64 = 0.5;

fn gap_step(a: &canon::Glyph, b: &canon::Glyph, pa: &canon::Glyph, pb: &canon::Glyph) -> usize {
    let moves = |v: [i64; 2]| v != [0, 0];
    if !a.opens && !b.opens && a.gap.len() == b.gap.len() {
        let pairs = a.gap.iter().zip(&b.gap);
        return pairs.filter(|(x, y)| moves(**x) || moves(**y)).count();
    }
    let travel = |g: &canon::Glyph, p: &canon::Glyph| [0, 1].map(|i| g.at[i] - p.at[i]);
    let blanks = |g: &canon::Glyph| g.gap.len() > usize::from(!g.opens);
    let moved = moves(travel(a, pa)) || moves(travel(b, pb));
    usize::from(moved) * (1 + usize::from(blanks(a) || blanks(b)))
}

fn advance_miss(a: &canon::Glyph, b: &canon::Glyph) -> Option<f64> {
    let paired = !a.opens && !b.opens && a.gap.len() == b.gap.len();
    let diff = |(x, y): (&[i64; 2], &[i64; 2])| ((x[0] - y[0]) as f64).hypot((x[1] - y[1]) as f64);
    let worst = a.gap.iter().zip(&b.gap).map(diff).fold(0.0, f64::max);
    (paired && worst > ADVANCE_QUANTA).then_some(worst * streams::GLYPH_QUANTUM)
}

fn steps(ga: &[canon::Glyph], gb: &[canon::Glyph]) -> Vec<usize> {
    let reach =
        |g: &canon::Glyph| ((g.at[0] - g.start[0]) as f64).hypot((g.at[1] - g.start[1]) as f64);
    let mut span: HashMap<(usize, usize), f64> = HashMap::new();
    for (a, b) in ga.iter().zip(gb) {
        let s = span.entry((a.line, b.line)).or_default();
        *s = s.max(reach(a)).max(reach(b));
    }
    let mut last: HashMap<(usize, usize), (usize, usize)> = HashMap::new();
    (0..ga.len())
        .map(|j| {
            let (a, b) = (&ga[j], &gb[j]);
            let prev = last.get(&(a.line, b.line));
            let k = prev.map_or(0, |&(k, i)| k + gap_step(a, b, &ga[i], &gb[i]));
            last.insert((a.line, b.line), (k, j));
            let held = span[&(a.line, b.line)] * streams::GLYPH_QUANTUM / MIN_ADVANCE_PT;
            k.min(held as usize + 1)
        })
        .collect()
}

fn paired_runs(ga: &[canon::Glyph], gb: &[canon::Glyph]) -> Vec<std::ops::Range<usize>> {
    let key = |g: &canon::Glyph| (g.line, g.show);
    let mut runs: Vec<std::ops::Range<usize>> = vec![];
    for j in 0..ga.len() {
        let same = j > 0 && key(&ga[j - 1]) == key(&ga[j]) && key(&gb[j - 1]) == key(&gb[j]);
        match runs.last_mut() {
            Some(r) if same => r.end = j + 1,
            _ => runs.push(j..j + 1),
        }
    }
    runs
}

#[derive(Default)]
struct GlyphTally {
    glyphs: usize,
    shows: usize,
    worst_excess: Option<f64>,
    worst_ratio: f64,
    worst: Option<String>,
    violations: Vec<String>,
}

impl GlyphTally {
    fn run(&mut self, at: &str, d: &[(usize, [i64; 2])]) {
        self.shows += 1;
        self.glyphs += d.len();
        for (k, [x, y]) in d {
            let mag = ((*x as f64).hypot(*y as f64)) * streams::GLYPH_QUANTUM;
            let bound = *k as f64 * streams::GLYPH_DRIFT_PT;
            if bound > 0.0 {
                self.worst_ratio = self.worst_ratio.max(mag / bound);
            }
            let excess = mag - bound;
            if self.worst_excess.is_none_or(|w| excess > w) {
                self.worst_excess = Some(excess);
                self.worst = Some(format!("{at} glyph {k}: {mag:.6} pt"));
            }
            if excess > 0.0 {
                self.violations.push(format!(
                    "{at} glyph {k}: {mag:.6} pt exceeds bound {bound:.6} pt"
                ));
            }
        }
        let axis = |i: usize| d.iter().map(|x| x.1[i]).collect::<Vec<_>>();
        if !axis_shape(&axis(0)) || !axis_shape(&axis(1)) {
            self.violations.push(format!(
                "{at}: difference sequence is not one-signed and monotone"
            ));
        }
    }
}

pub fn compare_glyphs(a: &Dump, b: &Dump, first: u32) -> GlyphClause {
    let mut t = GlyphTally::default();
    for (i, (pa, pb)) in a.pages.iter().zip(&b.pages).enumerate() {
        let page = first + i as u32;
        let (ga, gb) = (glyph_list(pa), glyph_list(pb));
        if ga.len() != gb.len() {
            t.violations
                .push(format!("page {page}: {} glyphs vs {}", ga.len(), gb.len()));
            continue;
        }
        for (j, miss) in (0..ga.len()).filter_map(|j| Some((j, advance_miss(&ga[j], &gb[j])?))) {
            t.violations.push(format!(
                "page {page} glyph {j}: an advance before it differs by {miss:.6} pt, beyond one tick"
            ));
        }
        let ks = steps(&ga, &gb);
        for r in paired_runs(&ga, &gb) {
            let at = format!("page {page} glyphs {}..{}", r.start, r.end);
            t.run(&at, &drift(&ga, &gb, &ks, r));
        }
    }
    t.violations.truncate(40);
    GlyphClause {
        status: status(t.violations.is_empty()),
        glyphs: t.glyphs,
        shows: t.shows,
        worst_excess_pt: t.worst_excess.unwrap_or(0.0),
        worst_ratio: t.worst_ratio,
        worst: t.worst,
        violations: t.violations,
    }
}

fn status(pass: bool) -> String {
    if pass { "pass" } else { "fail" }.into()
}

type Paint = (String, Option<Color>);

fn color_sequences(page: &PageDump) -> [Vec<Paint>; 2] {
    let mut glyphs = vec![];
    let mut paints = vec![];
    for e in &page.canonical().elements {
        match e {
            Element::Text { s, fill, tr, m, .. } => {
                glyphs.push(((-m[5], m[4]), (s.clone(), (*tr != 3).then(|| fill.clone()))));
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
        let mut raw = vec![];
        doc.save_to(&mut raw)?;
        let doc = Document::load_mem(&raw)?;
        let _exact = super::super::exact::authored(&doc, &raw)?;
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
            origin: [streams::qo(x as f64 / 100.0), streams::qo(y as f64 / 100.0)],
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
    fn a_link_border_compares_what_is_drawn_with_spec_defaults() {
        let doc = Document::with_version("1.7");
        let border = |text: &str| {
            let dict = super::super::exact::parsed(text).as_dict().unwrap();
            link_border(&doc, dict).unwrap()
        };
        let zero = border("<</Border [0.0 0.0 0.0]>>");
        assert_ne!(border("<<>>"), zero);
        assert_eq!(border("<<>>"), border("<</Border [0 0 1]>>"));
        assert_ne!(border("<</BS <</W 0>>>>"), zero);
        let drawn = border("<</C [1.0 0.0 0.0]>>");
        assert_eq!(border("<</C [1 0 0]>>"), drawn);
        assert_ne!(border("<</C [1.0 0.0 0.0] /BS <<>>>>"), drawn);
        assert_ne!(border("<</C [1.0 0.0 0.0] /Border [0.0 0.0 3.0]>>"), drawn);
        assert_ne!(border("<</C [0.0 0.0 1.0]>>"), drawn);
        assert_ne!(border("<</C [1.0 0.0 0.0] /BS <</S /D>>>>"), drawn);
    }

    #[test]
    fn a_link_border_follows_what_poppler_draws() {
        let doc = Document::with_version("1.7");
        let border = |d: lopdf::Dictionary| link_border(&doc, &d).unwrap();
        let wide = || Object::from(vec![0.into(), 0.into(), 3.into()]);
        let black = || Object::from(vec![0.into(), 0.into(), 0.into()]);
        let drawn = border(lopdf::dictionary! { "Border" => wide(), "C" => black() });
        let flagged =
            |f: i64| border(lopdf::dictionary! { "Border" => wide(), "C" => black(), "F" => f });
        let empty = lopdf::dictionary! { "Border" => wide(), "C" => Object::from(vec![]) };
        let zero = lopdf::dictionary! { "Border" => vec![0.into(), 0.into(), 0.into()] };
        assert_eq!(
            [
                border(lopdf::dictionary! { "Border" => wide() }) != drawn,
                border(lopdf::dictionary! { "Border" => wide() }) != border(empty),
                border(lopdf::dictionary! {}) != border(zero),
                flagged(2) != drawn,
                flagged(32) != drawn,
                flagged(4) != drawn,
                flagged(1) == drawn,
            ],
            [true; 7]
        );
    }

    fn annots(page: lopdf::Dictionary, doc: &mut Document) -> Result<Vec<Annot>> {
        let id = doc.add_object(page);
        page_annots(doc, id, &BTreeMap::new())
    }

    fn annot(subtype: &str, ap: Option<&[u8]>, doc: &mut Document) -> Object {
        let mut d = lopdf::dictionary! {
            "Type" => "Annot",
            "Subtype" => subtype,
            "Rect" => vec![0.into(), 0.into(), 10.into(), 10.into()]
        };
        if let Some(bytes) = ap {
            let n = doc.add_object(lopdf::Stream::new(lopdf::dictionary! {}, bytes.to_vec()));
            d.set("AP", lopdf::dictionary! { "N" => n });
        }
        Object::Reference(doc.add_object(d))
    }

    #[test]
    fn an_annotation_other_than_link_is_compared_only_by_byte_equal_appearance() {
        let mut doc = Document::with_version("1.7");
        let mut page = |subtype: &str, ap: Option<&[u8]>| {
            let a = annot(subtype, ap, &mut doc);
            annots(lopdf::dictionary! { "Annots" => vec![a] }, &mut doc)
        };
        assert!(page("Link", None).is_ok());
        assert!(page("Link", Some(b"0 0 m")).is_err());
        assert!(page("Square", None).is_err());
        assert!(page("FreeText", None).is_err());
        let square = page("Square", Some(b"1 0 0 rg 0 0 10 10 re f")).unwrap();
        let other = page("Square", Some(b"0 0 1 rg 0 0 10 10 re f")).unwrap();
        let same = page("Square", Some(b"1 0 0 rg 0 0 10 10 re f")).unwrap();
        let leg = |annots: Vec<Annot>| Dump {
            pages: vec![PageDump {
                elements: vec![],
                annots,
                boxes: BTreeMap::new(),
                ink: vec![],
            }],
            nav: DocNav {
                title: None,
                lang: None,
                outlines: vec![],
            },
        };
        assert!(compare_display(&leg(square.clone()), &leg(same), 1).is_ok());
        assert!(compare_display(&leg(square), &leg(other), 1).is_err());
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

    fn glyph_run(text: &str, at: [i64; 2], font: &str, gids: Vec<u32>) -> Element {
        let mut e = run(text, 0, 0, INK, 0);
        if let Element::Text {
            m,
            origin,
            font: f,
            gids: g,
            ..
        } = &mut e
        {
            *origin = at;
            m[4] = streams::qc(at[0] as f64 * streams::GLYPH_QUANTUM);
            m[5] = streams::qc(at[1] as f64 * streams::GLYPH_QUANTUM);
            *f = font.into();
            *g = gids;
        }
        e
    }

    const O: [i64; 2] = [109_227, 546_133];
    const IDS: [u32; 11] = [1, 2, 3, 3, 4, streams::BLANK_GID, 5, 4, 6, 3, 7];

    fn ids(r: std::ops::Range<usize>) -> Vec<u32> {
        IDS[r].to_vec()
    }

    fn whole() -> Dump {
        dump(vec![glyph_run("Hello world", O, "F", ids(0..11))])
    }

    fn halves(second: [i64; 2], font: &str, tail: Vec<u32>) -> Dump {
        dump(vec![
            glyph_run("world", second, font, tail),
            glyph_run("Hello ", O, "F", ids(0..6)),
        ])
    }

    fn display(b: &Dump) -> String {
        compare_display(&whole(), b, 1).unwrap().status
    }

    #[test]
    fn the_same_glyphs_pass_whatever_the_show_grouping_or_trailing_space() {
        let b = halves([O[0] + 60_000, O[1]], "F", ids(6..11));
        assert_eq!(display(&b), "pass");
        assert_eq!(compare_glyphs(&whole(), &b, 1).status, "pass");
        let c = compare_display(&whole(), &b, 1).unwrap();
        assert_eq!((c.elements_a, c.elements_b), (10, 10));
    }

    fn both(a: &Dump, b: &Dump) -> (String, String) {
        let d = compare_display(a, b, 1).unwrap().status;
        (d, compare_glyphs(a, b, 1).status)
    }

    fn pass_fail(d: &str, g: &str) -> (String, String) {
        (d.into(), g.into())
    }

    #[test]
    fn a_missing_glyph_another_glyph_id_face_or_a_moved_line_start_fails_the_display_list() {
        let at = [O[0] + 60_000, O[1]];
        let mut other = ids(6..11);
        other[2] = 9;
        assert_eq!(display(&halves(at, "F", other)), "fail");
        assert_eq!(display(&halves(at, "G", ids(6..11))), "fail");
        let short = dump(vec![
            glyph_run("worl", at, "F", ids(6..10)),
            glyph_run("Hello ", O, "F", ids(0..6)),
        ]);
        assert_eq!(display(&short), "fail");
        let quantum = streams::qo(0.01) + 1;
        for shift in [[quantum, 0], [-quantum, 0], [0, quantum]] {
            let moved = dump(vec![
                glyph_run(
                    "world",
                    [at[0] + shift[0], at[1] + shift[1]],
                    "F",
                    ids(6..11),
                ),
                glyph_run("Hello ", [O[0] + shift[0], O[1] + shift[1]], "F", ids(0..6)),
            ]);
            assert_eq!(display(&moved), "fail", "{shift:?}");
        }
    }

    #[test]
    fn drift_inside_a_line_passes_the_display_list_and_the_glyph_clause_judges_it() {
        let at = [O[0] + 60_000, O[1]];
        let near = halves([at[0] + 1, at[1]], "F", ids(6..11));
        let g = compare_glyphs(&whole(), &near, 1);
        assert_eq!((g.status.as_str(), g.glyphs, g.shows), ("pass", 10, 2));
        let quantum = halves([at[0] + streams::qo(0.01) + 1, at[1]], "F", ids(6..11));
        assert_eq!(both(&whole(), &quantum), pass_fail("pass", "fail"));
        let mut far = halves(at, "F", ids(6..11));
        if let Element::Text { offs, .. } = &mut far.pages[0].elements[0] {
            offs[2..].iter_mut().for_each(|o| o[0] += 8 * 8 + 1);
        }
        assert_eq!(both(&whole(), &far), pass_fail("pass", "fail"));
        for (by, verdict) in [(-55, "pass"), (1, "fail")] {
            if let Element::Text { offs, .. } = &mut far.pages[0].elements[0] {
                offs[2..].iter_mut().for_each(|o| o[0] += by);
            }
            assert_eq!(both(&whole(), &far), pass_fail("pass", verdict), "{by}");
        }
        let split = halves(at, "F", ids(6..11));
        let mut stairs = halves(at, "F", ids(6..11));
        for e in &mut stairs.pages[0].elements {
            if let Element::Text { offs, .. } = e {
                offs.iter_mut().zip(0..).for_each(|(o, k)| o[0] += 2 * k);
            }
        }
        assert_eq!(both(&split, &stairs), pass_fail("pass", "pass"));
    }

    #[test]
    fn blanks_on_one_leg_buy_no_drift_allowance() {
        assert_eq!(
            both(
                &whole(),
                &padded(7000, streams::qo(5.0), streams::BLANK_GID)
            ),
            pass_fail("pass", "fail")
        );
    }

    fn padded(blanks: usize, shift: i64, fill: u32) -> Dump {
        let mut e = run("Helloworld", 0, 0, INK, 0);
        if let Element::Text {
            origin,
            gids,
            offs,
            units,
            ..
        } = &mut e
        {
            *origin = O;
            let head = (0..5).map(|k| [k * 10_000, 0]);
            let pad = std::iter::repeat_n([50_000, 0], blanks);
            let tail = (6..11).map(|k| [k * 10_000 + shift, 0]);
            *offs = head.chain(pad).chain(tail).collect();
            *gids = [ids(0..5), vec![fill; blanks], ids(6..11)].concat();
            let chars = "Helloworld".chars().map(String::from);
            *units = chars.clone().take(5).collect();
            let unit = if fill == streams::BLANK_GID { " " } else { "." };
            units.extend(std::iter::repeat_n(unit.to_string(), blanks));
            units.extend(chars.skip(5));
        }
        dump(vec![e])
    }

    #[test]
    fn blanks_both_legs_carry_buy_no_visible_move() {
        let b = streams::BLANK_GID;
        let moved = [
            both(&padded(7000, 0, b), &padded(5000, streams::qo(3.0), b)),
            both(&padded(7000, 0, b), &padded(7000, streams::qo(5.0), b)),
            both(&padded(7000, 0, 3), &padded(7000, streams::qo(5.0), 3)),
            both(&padded(7000, 0, 3), &padded(7000, 0, 3)),
        ];
        assert_eq!(
            moved,
            [
                pass_fail("pass", "fail"),
                pass_fail("pass", "fail"),
                pass_fail("pass", "fail"),
                pass_fail("pass", "pass")
            ]
        );
    }

    #[test]
    fn a_step_counts_each_advance_both_legs_carry_that_moves_the_pen() {
        let line = |text: &str, at: &[i64]| {
            let mut e = glyph_run(text, O, "F", vec![]);
            if let Element::Text { offs, .. } = &mut e {
                *offs = at.iter().map(|&x| [x, 0]).collect();
            }
            dump(vec![e])
        };
        let spread = |gap: i64, tick: i64| (0..6).map(|k| k * (gap + tick)).collect::<Vec<_>>();
        let with_last = |mut v: Vec<i64>, by: i64| {
            *v.last_mut().unwrap() += by;
            v
        };
        let status = |a: &[i64], b: &str, at: &[i64]| {
            compare_glyphs(&line("a    b", a), &line(b, at), 1).status
        };
        let base = spread(10_000, 0);
        let cases = [
            ("a    b", spread(10_000, 8), "pass"),
            ("a    b", with_last(spread(10_000, 8), 1), "fail"),
            ("a    b", with_last(base.clone(), 10), "pass"),
            ("a    b", with_last(base.clone(), 11), "fail"),
            ("ab", vec![0, 50_000 + 2 * 8], "pass"),
            ("ab", vec![0, 50_000 + 2 * 8 + 1], "fail"),
        ];
        for (text, at, verdict) in cases {
            assert_eq!(status(&base, text, &at), verdict, "{text} {at:?}");
        }
        let stacked = [0, 10_000, 10_000, 10_000, 10_000, 20_000];
        let moved = |last: i64| {
            compare_glyphs(
                &line("a    b", &stacked),
                &line("a    b", &[0, 10_008, 10_008, 10_008, 10_008, last]),
                1,
            )
            .status
        };
        assert_eq!([moved(20_016), moved(20_017)], ["pass", "fail"]);
    }

    fn ladder(advances: &[i64]) -> Dump {
        let mut e = run("Helloworld", 0, 0, INK, 0);
        if let Element::Text {
            origin,
            gids,
            offs,
            units,
            ..
        } = &mut e
        {
            *origin = O;
            let pad: Vec<[i64; 2]> = advances
                .iter()
                .scan(40_000, |x, a| {
                    *x += a;
                    Some([*x, 0])
                })
                .collect();
            let x = pad.last().map_or(40_000, |p| p[0]);
            let tail = (1..6).map(|k| [x + k * 10_000, 0]);
            *offs = (0..5)
                .map(|k| [k * 10_000, 0])
                .chain(pad)
                .chain(tail)
                .collect();
            *gids = [ids(0..5), vec![3; advances.len()], ids(6..11)].concat();
            let chars = "Helloworld".chars().map(String::from);
            *units = chars.clone().take(5).collect();
            units.extend(std::iter::repeat_n(".".to_string(), advances.len()));
            units.extend(chars.skip(5));
        }
        dump(vec![e])
    }

    #[test]
    fn a_line_buys_no_more_steps_than_its_span_can_hold() {
        let status = |n: usize, step: f64, tick: i64| {
            let step = streams::qo(step);
            compare_glyphs(&ladder(&vec![step; n]), &ladder(&vec![step + tick; n]), 1).status
        };
        assert_eq!(
            status(7000, 0.0015, 8),
            "fail",
            "7000 ticks, 5.1 pt, on a 10 pt span"
        );
        assert_eq!(status(7000, 0.0015, 0), "pass");
        assert_eq!(status(400, MIN_ADVANCE_PT, 8), "pass");
        assert_eq!(status(400, MIN_ADVANCE_PT / 2.0, 8), "fail");
        assert_eq!(status(100, 1.25, 8), "pass");
    }

    #[test]
    fn a_line_is_one_baseline_within_a_quantum_split_at_a_gap_of_three_em() {
        let em = streams::qo(10.0);
        let q = streams::qo(0.01);
        let pair = |dx: i64, dy: i64, shift: i64| {
            dump(vec![
                glyph_run("ab", O, "F", vec![1, 2]),
                glyph_run("cd", [O[0] + dx + shift, O[1] + dy], "F", vec![3, 4]),
            ])
        };
        let lines = |d: &Dump| {
            glyph_list(&d.pages[0])
                .iter()
                .map(|g| g.line)
                .collect::<Vec<_>>()
        };
        let (near, far) = (10_000 + 3 * em - 200, 10_000 + 3 * em + 50);
        assert_eq!(lines(&pair(near, 0, 0)), [1, 1, 1, 1]);
        assert_eq!(lines(&pair(near, q, 0)), [1, 1, 1, 1]);
        assert_eq!(lines(&pair(far, 0, 0)), [1, 1, 2, 2]);
        assert_eq!(lines(&pair(near, q + 1, 0)), [1, 1, 2, 2]);
        assert_eq!(
            both(&pair(near, 0, 0), &pair(near, 0, q + 1)),
            pass_fail("pass", "fail")
        );
        assert_eq!(
            both(&pair(far, 0, 0), &pair(far, 0, q + 1)),
            pass_fail("fail", "pass")
        );
        let sup = |shift: i64| pair(20_000, 2 * q, shift);
        assert_eq!(both(&sup(0), &sup(q + 1)), pass_fail("fail", "pass"));
    }

    #[test]
    fn overlapping_glyphs_in_other_colours_keep_their_paint_order() {
        let glyph = |x: i64, rgb| run("a", x, 5000, rgb, 0);
        let page = |es: Vec<Element>, reach: i64| {
            let mut d = dump(es);
            d.pages[0].ink = d.pages[0]
                .elements
                .iter()
                .map(|e| match e {
                    Element::Text { m, .. } => Some(vec![Some([m[4], 5000, m[4] + reach, 5500])]),
                    _ => None,
                })
                .collect();
            d
        };
        for (reach, want, kept) in [(400, "pass", 0), (600, "fail", 1)] {
            let a = page(vec![glyph(1500, INK), glyph(1000, VIOLET)], reach);
            let b = page(vec![glyph(1000, VIOLET), glyph(1500, INK)], reach);
            let c = compare_display(&a, &b, 1).unwrap();
            assert_eq!(
                (c.status.as_str(), c.text_runs_in_paint_order),
                (want, kept)
            );
        }
    }
}
