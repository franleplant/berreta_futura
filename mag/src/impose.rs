use super::model::shared::py_repr;
use super::parity::{authored, num};
use anyhow::{bail, Context, Result};
use lopdf::content::Content;
use lopdf::{Dictionary, Document, Object, ObjectId};
use std::path::{Path, PathBuf};

pub const A4_LANDSCAPE_POINTS: (f64, f64) = (841.8898, 595.2756);

pub const BOOKLET_SECTIONS: [&str; 3] = ["all", "interior", "cover"];

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
            py_repr(section)
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
    Ok((3..page_count - 1).collect())
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
    let raw =
        std::fs::read(reader_pdf).with_context(|| format!("reading {}", reader_pdf.display()))?;
    let mut doc =
        Document::load_mem(&raw).with_context(|| format!("reading {}", reader_pdf.display()))?;
    let page_ids: Vec<ObjectId> = doc.get_pages().into_values().collect();
    let plan = if section == "cover" {
        cover_wrap_plan(page_ids.len())?
    } else {
        imposed_reader_page_plan(&section_reader_pages(page_ids.len(), section)?)
    };
    let sources = {
        let _exact = authored(&doc, &raw)?;
        page_ids
            .iter()
            .map(|id| source_page(&doc, *id))
            .collect::<Result<Vec<_>>>()?
    };
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
    loop {
        let dict = doc.get_dictionary(current)?;
        if let Ok(value) = dict.get(key) {
            let array = doc.dereference(value)?.1.as_array()?;
            let mut out = [0.0; 4];
            for (slot, item) in out.iter_mut().zip(array) {
                *slot = num(doc.dereference(item)?.1).with_context(|| {
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
}

fn page_resources(doc: &Document, id: ObjectId) -> Result<Dictionary> {
    let (direct, inherited) = doc.get_page_resources(id)?;
    let mut merged = Dictionary::new();
    for source in inherited
        .iter()
        .filter_map(|id| doc.get_dictionary(*id).ok())
        .chain(direct)
    {
        for (key, value) in source {
            let resolved = doc.dereference(value).map(|(_, object)| object);
            merged.set(key.to_vec(), resolved.unwrap_or(value).clone());
        }
    }
    Ok(merged)
}

fn sheet(
    sources: &[SourcePage],
    spread: (Option<usize>, Option<usize>),
) -> Result<(Vec<u8>, Dictionary)> {
    let half = A4_LANDSCAPE_POINTS.0 / 2.0;
    let mut content: Option<Vec<u8>> = None;
    let mut resources = Dictionary::new();
    for (number, x) in [(spread.0, 0.0), (spread.1, half)] {
        let Some(number) = number else { continue };
        let source = &sources[number - 1];
        let width = source.media[2] - source.media[0];
        let height = source.media[3] - source.media[1];
        let scale = (half / width).min(A4_LANDSCAPE_POINTS.1 / height);
        let renames = merge_resources(&mut resources, &source.resources);
        let placed = place(source, scale, x, &renames)?;
        content = Some(match content {
            None => placed,
            Some(previous) => isolate(&previous, &placed),
        });
    }
    Ok((content.unwrap_or_default(), resources))
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
        real(source.crop[0]),
        real(source.crop[1]),
        real(source.crop[2] - source.crop[0]),
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
                renames.push((key.to_vec(), unique.clone()));
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
            if !content.is_empty() {
                let stream = doc.add_object(lopdf::Stream::new(Dictionary::new(), content));
                page.set("Contents", Object::Reference(stream));
            }
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
    doc.get_dictionary_mut(root_id)?
        .set("Pages", Object::Reference(pages_id));
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
