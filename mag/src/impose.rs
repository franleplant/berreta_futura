use super::model::shared::quoted;
use super::pdf_text::page_resources;
use anyhow::{bail, Context, Result};
use lopdf::content::Content;
use lopdf::{Dictionary, Document, Object, ObjectId};
use std::path::{Path, PathBuf};

pub const A4_LANDSCAPE_POINTS: (f64, f64) = (841.8898, 595.2756);

pub const BOOKLET_SECTIONS: [&str; 3] = ["all", "interior", "cover"];

pub const MAX_UNSPLIT_INTERIOR_SHEETS: usize = 25;

pub(crate) const PAGE_TREE_DEPTH: usize = 64;
const MERGED_RESOURCES: [&[u8]; 7] = [
    b"ExtGState",
    b"ColorSpace",
    b"Pattern",
    b"Shading",
    b"XObject",
    b"Font",
    b"Properties",
];

fn section_title(section: &str) -> &'static str {
    match section {
        "interior" => "Home booklet interior",
        "cover" => "Home booklet cover",
        _ => "Home booklet",
    }
}

pub fn booklet_spreads(page_count: usize) -> Vec<(usize, usize)> {
    let total = page_count.div_ceil(4) * 4;
    let mut spreads = Vec::with_capacity(total / 2);
    for sheet in 0..total / 4 {
        spreads.push((total - 2 * sheet, 1 + 2 * sheet));
        spreads.push((2 + 2 * sheet, total - 1 - 2 * sheet));
    }
    spreads
}

pub fn section_reader_pages(page_count: usize, section: &str) -> Result<Vec<usize>> {
    if !BOOKLET_SECTIONS.contains(&section) {
        bail!(
            "Unknown booklet section {}; expected one of ('all', 'interior', 'cover').",
            quoted(section)
        );
    }
    if section == "all" {
        return Ok((1..=page_count).collect());
    }
    if page_count < 4 {
        bail!(
            "A {page_count}-page reader has no separable cover wrap; a cover sheet needs four pages."
        );
    }
    if section == "cover" {
        return Ok(vec![1, 2, page_count - 1, page_count]);
    }
    Ok(std::iter::once(2).chain(3..page_count - 1).collect())
}

pub fn section_plan(
    page_count: usize,
    section: &str,
) -> Result<Vec<(Option<usize>, Option<usize>)>> {
    let pages = section_reader_pages(page_count, section)?;
    Ok(match section {
        "cover" => cover_wrap_plan(page_count)?,
        "interior" => {
            let padded: Vec<Option<usize>> = [Some(2), None]
                .into_iter()
                .chain((3..page_count - 1).map(Some))
                .chain([None, None])
                .collect();
            booklet_spreads(padded.len())
                .into_iter()
                .map(|(left, right)| (padded[left - 1], padded[right - 1]))
                .collect()
        }
        _ => imposed_reader_page_plan(&pages),
    })
}

pub fn split_sheets(
    plan: &[(Option<usize>, Option<usize>)],
    weight: impl Fn(usize) -> usize,
) -> Vec<Vec<(Option<usize>, Option<usize>)>> {
    if plan.len() <= 2 * MAX_UNSPLIT_INTERIOR_SHEETS {
        return Vec::new();
    }
    let sheets: Vec<usize> = plan
        .chunks(2)
        .map(|sides| {
            sides
                .iter()
                .flat_map(|(l, r)| [*l, *r])
                .flatten()
                .map(&weight)
                .sum()
        })
        .collect();
    let total: usize = sheets.iter().sum();
    let first = (1..sheets.len())
        .min_by_key(|&k| (2 * sheets[..k].iter().sum::<usize>()).abs_diff(total))
        .unwrap_or(sheets.len());
    vec![plan[..2 * first].to_vec(), plan[2 * first..].to_vec()]
}

fn image_weights(doc: &Document) -> Vec<usize> {
    doc.get_pages()
        .into_values()
        .map(|id| {
            page_resources(doc, id)
                .ok()
                .and_then(|r| r.get(b"XObject").ok().cloned())
                .and_then(|x| match x {
                    Object::Dictionary(d) => Some(d),
                    Object::Reference(id) => doc.get_dictionary(id).ok().cloned(),
                    _ => None,
                })
                .map_or(0, |xobjects| {
                    xobjects
                        .iter()
                        .filter_map(|(_, v)| v.as_reference().ok())
                        .filter_map(|id| doc.get_object(id).ok()?.as_stream().ok())
                        .map(|stream| stream.content.len())
                        .sum()
                })
        })
        .collect()
}

pub fn imposed_reader_page_plan(reader_pages: &[usize]) -> Vec<(Option<usize>, Option<usize>)> {
    let mut padded: Vec<Option<usize>> = reader_pages.iter().copied().map(Some).collect();
    padded.resize(padded.len().div_ceil(4) * 4, None);
    booklet_spreads(padded.len())
        .into_iter()
        .map(|(left, right)| (padded[left - 1], padded[right - 1]))
        .collect()
}

pub fn cover_wrap_plan(page_count: usize) -> Result<Vec<(Option<usize>, Option<usize>)>> {
    let pages = section_reader_pages(page_count, "cover")?;
    Ok(imposed_reader_page_plan(&pages)
        .into_iter()
        .take(1)
        .collect())
}

struct SourcePage {
    content: Vec<u8>,
    resources: Dictionary,
    media: [f64; 4],
    crop: [f64; 4],
}

pub fn impose_a5_on_a4(reader_pdf: &Path, output: &Path, section: &str) -> Result<PathBuf> {
    let pages = Document::load(reader_pdf)
        .with_context(|| format!("reading {}", reader_pdf.display()))?
        .get_pages()
        .len();
    impose_plan(reader_pdf, output, section, &section_plan(pages, section)?)
}

pub fn impose_interior_parts(reader_pdf: &Path, stem: &Path) -> Result<Vec<PathBuf>> {
    let doc =
        Document::load(reader_pdf).with_context(|| format!("reading {}", reader_pdf.display()))?;
    let weights = image_weights(&doc);
    let plan = section_plan(weights.len(), "interior")?;
    let part = |n: usize| stem.with_file_name(format!("booklet-a4-interior-part-{n}.pdf"));
    split_sheets(&plan, |page| weights[page - 1] + 1)
        .iter()
        .zip(1..)
        .map(|(sheets, n)| impose_plan(reader_pdf, &part(n), "interior", sheets))
        .collect()
}

fn impose_plan(
    reader_pdf: &Path,
    output: &Path,
    section: &str,
    plan: &[(Option<usize>, Option<usize>)],
) -> Result<PathBuf> {
    let mut doc =
        Document::load(reader_pdf).with_context(|| format!("reading {}", reader_pdf.display()))?;
    let page_ids: Vec<ObjectId> = doc.get_pages().into_values().collect();
    let sources = page_ids
        .iter()
        .map(|id| source_page(&doc, *id))
        .collect::<Result<Vec<_>>>()?;
    let sheets = plan
        .iter()
        .map(|spread| sheet(&sources, *spread))
        .collect::<Result<Vec<_>>>()?;
    write_sheets(&mut doc, sheets, section, output)?;
    Ok(output.to_path_buf())
}

fn source_page(doc: &Document, id: ObjectId) -> Result<SourcePage> {
    let media = page_box(doc, id, b"MediaBox")?.context("page has no MediaBox")?;
    let crop = page_box(doc, id, b"CropBox")?.unwrap_or(media);
    Ok(SourcePage {
        content: doc.get_page_content(id),
        resources: page_resources(doc, id)?,
        media,
        crop,
    })
}

fn page_box(doc: &Document, id: ObjectId, key: &[u8]) -> Result<Option<[f64; 4]>> {
    let mut current = id;
    for _ in 0..PAGE_TREE_DEPTH {
        let dict = doc.get_dictionary(current)?;
        if let Ok(value) = dict.get(key) {
            let array = doc.dereference(value)?.1.as_array()?;
            let mut out = [0.0; 4];
            for (slot, item) in out.iter_mut().zip(array) {
                *slot = number(doc.dereference(item)?.1).with_context(|| {
                    format!("{} on object {current:?}", String::from_utf8_lossy(key))
                })?;
            }
            return Ok(Some(out));
        }
        match dict.get(b"Parent") {
            Ok(Object::Reference(parent)) => current = *parent,
            _ => return Ok(None),
        }
    }
    bail!("the page tree is deeper than {PAGE_TREE_DEPTH} levels or loops through /Parent")
}

fn number(object: &Object) -> Result<f64> {
    match object {
        Object::Integer(value) => Ok(*value as f64),
        Object::Real(value) => Ok(value.to_string().parse()?),
        other => bail!("expected a number, got {other:?}"),
    }
}

pub fn sheet_x(media: [f64; 4], left: bool) -> f64 {
    let half = A4_LANDSCAPE_POINTS.0 / 2.0;
    match left {
        true => half - (media[2] - media[0]) * page_scale(media),
        false => half,
    }
}

pub fn page_scale(media: [f64; 4]) -> f64 {
    let (width, height) = (media[2] - media[0], media[3] - media[1]);
    (A4_LANDSCAPE_POINTS.0 / 2.0 / width).min(A4_LANDSCAPE_POINTS.1 / height)
}

fn sheet(
    sources: &[SourcePage],
    spread: (Option<usize>, Option<usize>),
) -> Result<(Vec<u8>, Dictionary)> {
    let mut content: Option<Vec<u8>> = None;
    let mut resources = Dictionary::new();
    for (number, left) in [(spread.0, true), (spread.1, false)] {
        let Some(number) = number else { continue };
        let source = &sources[number - 1];
        let scale = page_scale(source.media);
        let x = sheet_x(source.media, left);
        let half = A4_LANDSCAPE_POINTS.0 / 2.0;
        let span = if left {
            (0.0, half)
        } else {
            (half, A4_LANDSCAPE_POINTS.0)
        };
        let clip = ((span.0 - x) / scale, (span.1 - x) / scale);
        let renames = merge_resources(&mut resources, &source.resources);
        let placed = place(source, scale, x, clip, &renames)?;
        content = Some(match content {
            None => placed,
            Some(previous) => isolate(&previous, &placed),
        });
    }
    Ok((content.unwrap_or_else(blank_side_mark), resources))
}

fn blank_side_mark() -> Vec<u8> {
    format!(
        "q\n0 g\n{} 24 0.5 6 re\nf\nQ\n",
        real(A4_LANDSCAPE_POINTS.0 / 2.0 - 0.25)
    )
    .into_bytes()
}

fn isolate(previous: &[u8], placed: &[u8]) -> Vec<u8> {
    let mut out = b"q\n".to_vec();
    out.extend_from_slice(previous);
    out.extend_from_slice(b"\nQ\n");
    out.extend_from_slice(placed);
    out
}

fn place(
    source: &SourcePage,
    scale: f64,
    x: f64,
    clip: (f64, f64),
    renames: &[(Vec<u8>, Vec<u8>)],
) -> Result<Vec<u8>> {
    let body = if renames.is_empty() {
        source.content.clone()
    } else {
        rename_names(&source.content, renames)?
    };
    let mut out = format!(
        "q\n{} 0 0 {} {} 0 cm\n{} {} {} {} re\nW\nn\n",
        real(scale),
        real(scale),
        real(x),
        real(clip.0),
        real(source.crop[1]),
        real(clip.1 - clip.0),
        real(source.crop[3] - source.crop[1]),
    )
    .into_bytes();
    out.extend_from_slice(&body);
    out.extend_from_slice(b"\nQ\n");
    Ok(out)
}

fn real(value: f64) -> String {
    if value == 0.0 {
        return "0.0".to_string();
    }
    let digits = (8 - value.abs().log10() as i32).max(1) as usize;
    let text = format!("{value:.digits$}");
    text.trim_end_matches('0').trim_end_matches('.').to_string()
}

fn rename_names(content: &[u8], renames: &[(Vec<u8>, Vec<u8>)]) -> Result<Vec<u8>> {
    let mut decoded = Content::decode_strict(content)
        .context("a page content stream holds a token lopdf cannot parse")?;
    for operation in &mut decoded.operations {
        for operand in &mut operation.operands {
            if let Object::Name(name) = operand {
                if let Some((_, replacement)) = renames.iter().find(|(from, _)| from == name) {
                    *name = replacement.clone();
                }
            }
        }
    }
    Ok(decoded.encode()?)
}

fn merge_resources(target: &mut Dictionary, source: &Dictionary) -> Vec<(Vec<u8>, Vec<u8>)> {
    let mut renames = Vec::new();
    for category in MERGED_RESOURCES {
        let Ok(entries) = source.get(category).and_then(Object::as_dict) else {
            continue;
        };
        let mut merged = target
            .get(category)
            .and_then(Object::as_dict)
            .cloned()
            .unwrap_or_default();
        for (key, value) in entries {
            let unique = unique_key(&merged, key, value);
            if unique != *key {
                renames.push((key.clone(), unique.clone()));
            }
            if merged.get(&unique).ok() != Some(value) {
                merged.set(unique, value.clone());
            }
        }
        target.set(category.to_vec(), Object::Dictionary(merged));
    }
    merge_proc_set(target, source);
    renames
}

fn unique_key(merged: &Dictionary, key: &[u8], value: &Object) -> Vec<u8> {
    if merged.get(key).is_err() {
        return key.to_vec();
    }
    if merged.get(key).ok() == Some(value) {
        return key.to_vec();
    }
    for index in 0.. {
        let candidate = format!("{}-{index}", String::from_utf8_lossy(key)).into_bytes();
        match merged.get(&candidate) {
            Err(_) => return candidate,
            Ok(existing) if existing == value => return candidate,
            Ok(_) => {}
        }
    }
    unreachable!()
}

fn merge_proc_set(target: &mut Dictionary, source: &Dictionary) {
    let mut names: Vec<Vec<u8>> = target
        .get(b"ProcSet")
        .and_then(Object::as_array)
        .map(|items| items.iter().filter_map(as_name).collect())
        .unwrap_or_default();
    if let Ok(items) = source.get(b"ProcSet").and_then(Object::as_array) {
        names.extend(items.iter().filter_map(as_name));
    }
    names.sort();
    names.dedup();
    if !names.is_empty() {
        let array = names.into_iter().map(Object::Name).collect();
        target.set(b"ProcSet".to_vec(), Object::Array(array));
    }
}

fn as_name(object: &Object) -> Option<Vec<u8>> {
    match object {
        Object::Name(name) => Some(name.clone()),
        _ => None,
    }
}

fn write_sheets(
    doc: &mut Document,
    sheets: Vec<(Vec<u8>, Dictionary)>,
    section: &str,
    output: &Path,
) -> Result<()> {
    let pages_id = doc.new_object_id();
    let kids: Vec<Object> = sheets
        .into_iter()
        .map(|(content, resources)| {
            let mut page = Dictionary::new();
            page.set("Type", Object::Name(b"Page".to_vec()));
            page.set("Parent", Object::Reference(pages_id));
            page.set("Resources", Object::Dictionary(resources));
            page.set(
                "MediaBox",
                Object::Array(
                    [0.0, 0.0, A4_LANDSCAPE_POINTS.0, A4_LANDSCAPE_POINTS.1]
                        .into_iter()
                        .map(|value| Object::Real(value as f32))
                        .collect(),
                ),
            );
            let stream = doc.add_object(lopdf::Stream::new(Dictionary::new(), content));
            page.set("Contents", Object::Reference(stream));
            Object::Reference(doc.add_object(page))
        })
        .collect();
    let mut pages = Dictionary::new();
    pages.set("Type", Object::Name(b"Pages".to_vec()));
    pages.set("Count", Object::Integer(kids.len() as i64));
    pages.set("Kids", Object::Array(kids));
    doc.objects.insert(pages_id, Object::Dictionary(pages));
    let root_id = doc
        .trailer
        .get(b"Root")
        .ok()
        .and_then(|value| match value {
            Object::Reference(id) => Some(*id),
            _ => None,
        })
        .context("trailer has no Root reference")?;
    let catalog = doc.get_dictionary_mut(root_id)?;
    catalog.set("Pages", Object::Reference(pages_id));
    for key in [
        b"Outlines".as_slice(),
        b"Names",
        b"Dests",
        b"StructTreeRoot",
        b"PageLabels",
        b"OpenAction",
    ] {
        catalog.remove(key);
    }
    let mut info = Dictionary::new();
    info.set(
        "Title",
        Object::string_literal(section_title(section).as_bytes().to_vec()),
    );
    info.set(
        "Creator",
        Object::string_literal(b"magazine-compiler".to_vec()),
    );
    let info_id = doc.add_object(info);
    doc.trailer.set("Info", Object::Reference(info_id));
    doc.prune_objects();
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    doc.save(output)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn looping_page() -> (Document, ObjectId) {
        let mut doc = Document::with_version("1.5");
        let (a, b) = (doc.new_object_id(), doc.new_object_id());
        for (id, parent) in [(a, b), (b, a)] {
            let mut node = lopdf::Dictionary::new();
            node.set("Parent", Object::Reference(parent));
            doc.objects.insert(id, Object::Dictionary(node));
        }
        (doc, a)
    }

    #[test]
    fn a_side_with_no_pages_still_carries_ink_so_printers_never_skip_it() {
        let (content, _) = sheet(&[], (None, None)).expect("an empty side imposes");
        assert!(content.windows(3).any(|w| w == b"re\n"), "no mark drawn");
    }

    #[test]
    fn a_parent_cycle_is_refused_instead_of_walked_forever() {
        let (doc, page) = looping_page();
        let error = page_box(&doc, page, b"MediaBox").expect_err("a cycle is refused");
        assert!(error.to_string().contains("/Parent"), "{error}");
    }
}
