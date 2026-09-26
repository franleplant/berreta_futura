use super::exact;
use super::streams::{self, Element, Face};
use anyhow::{Context, Result};
use lopdf::Document;
use std::collections::BTreeMap;
use std::path::Path;

pub fn trace_elements(
    pdf: &Path,
    first: u32,
    last: u32,
    font_map: &BTreeMap<String, Face>,
) -> Result<Vec<Vec<Element>>> {
    let raw = std::fs::read(pdf).with_context(|| format!("reading {}", pdf.display()))?;
    let doc = Document::load_mem(&raw).with_context(|| format!("loading {}", pdf.display()))?;
    let _exact = exact::authored(&doc, &raw)?;
    let page_ids = doc.get_pages();
    let mut caches = streams::Caches::new();
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
