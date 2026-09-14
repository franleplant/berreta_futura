use anyhow::{Context, Result};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;
use std::process::Command;

const BOX_NAMES: [&str; 3] = ["MediaBox", "CropBox", "TrimBox"];

#[derive(Serialize)]
pub struct BoxClause {
    pub status: String,
    pub tolerance_pt: f64,
    pub mismatches: Vec<BoxMismatch>,
}

#[derive(Serialize)]
pub struct BoxMismatch {
    pub page: u32,
    pub name: String,
    pub a: [f64; 4],
    pub b: [f64; 4],
}

#[derive(Serialize)]
pub struct GeomTier {
    pub g1_pt: f64,
    pub g2_pt: f64,
    pub pages: BTreeMap<u32, PageGeom>,
    pub max_dx_pt: f64,
    pub max_dy_pt: f64,
    pub lines_beyond_g1: u32,
    pub lines_beyond_g2: u32,
    pub block_or_line_count_mismatches: u32,
}

#[derive(Serialize)]
pub struct PageGeom {
    pub blocks_a: u32,
    pub blocks_b: u32,
    pub line_count_mismatches: u32,
    pub max_dx_pt: f64,
    pub max_dy_pt: f64,
}

struct Line {
    y: f64,
    first_x: f64,
}

pub struct Page {
    blocks: Vec<Vec<Line>>,
}

fn pdfinfo(pdf: &Path, extra: &[&str]) -> Result<String> {
    let out = Command::new("pdfinfo")
        .args(extra)
        .arg(pdf)
        .output()
        .context("running pdfinfo")?;
    anyhow::ensure!(out.status.success(), "pdfinfo failed on {}", pdf.display());
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

pub fn page_count(pdf: &Path) -> Result<u32> {
    let info = pdfinfo(pdf, &[])?;
    info.lines()
        .find_map(|l| l.strip_prefix("Pages:"))
        .and_then(|v| v.trim().parse().ok())
        .with_context(|| format!("no Pages: line from pdfinfo for {}", pdf.display()))
}

type BoxMap = BTreeMap<(u32, String), [f64; 4]>;

pub fn boxes(pdf: &Path, first: u32, last: u32) -> Result<BoxMap> {
    let info = pdfinfo(
        pdf,
        &["-f", &first.to_string(), "-l", &last.to_string(), "-box"],
    )?;
    let mut map = BoxMap::new();
    for line in info.lines() {
        let Some(rest) = line.strip_prefix("Page ") else {
            continue;
        };
        let fields: Vec<&str> = rest.split_whitespace().collect();
        if fields.len() != 6 || !BOX_NAMES.contains(&fields[1].trim_end_matches(':')) {
            continue;
        }
        let page: u32 = fields[0].parse().context("pdfinfo page number")?;
        let name = fields[1].trim_end_matches(':').to_string();
        let mut coords = [0.0; 4];
        for (slot, raw) in coords.iter_mut().zip(&fields[2..]) {
            *slot = raw.parse().context("pdfinfo box coordinate")?;
        }
        map.insert((page, name), coords);
    }
    Ok(map)
}

pub fn compare_boxes(a: &BoxMap, b: &BoxMap, tolerance_pt: f64) -> BoxClause {
    let mut mismatches = Vec::new();
    for (key, ca) in a {
        let cb = b.get(key).copied().unwrap_or([f64::NAN; 4]);
        let off = ca.iter().zip(&cb).any(|(x, y)| {
            let d = (x - y).abs();
            d.is_nan() || d > tolerance_pt
        });
        if off {
            mismatches.push(BoxMismatch {
                page: key.0,
                name: key.1.clone(),
                a: *ca,
                b: cb,
            });
        }
    }
    BoxClause {
        status: if mismatches.is_empty() {
            "pass".into()
        } else {
            "fail".into()
        },
        tolerance_pt,
        mismatches,
    }
}

fn attr(line: &str, name: &str) -> Option<f64> {
    let key = format!("{name}=\"");
    let start = line.find(&key)? + key.len();
    let end = line[start..].find('"')? + start;
    line[start..end].parse().ok()
}

fn parse_layout(xml: &str) -> Vec<Page> {
    let mut pages = Vec::new();
    for raw in xml.lines() {
        let line = raw.trim_start();
        if line.starts_with("<page ") {
            pages.push(Page { blocks: Vec::new() });
        } else if line.starts_with("<block ") {
            if let Some(p) = pages.last_mut() {
                p.blocks.push(Vec::new());
            }
        } else if line.starts_with("<line ") {
            if let (Some(y), Some(b)) = (
                attr(line, "yMin"),
                pages.last_mut().and_then(|p| p.blocks.last_mut()),
            ) {
                b.push(Line {
                    y,
                    first_x: f64::NAN,
                });
            }
        } else if line.starts_with("<word ") {
            if let Some(l) = pages
                .last_mut()
                .and_then(|p| p.blocks.last_mut())
                .and_then(|b| b.last_mut())
            {
                if l.first_x.is_nan() {
                    l.first_x = attr(line, "xMin").unwrap_or(f64::NAN);
                }
            }
        }
    }
    pages
}

pub fn layout_pages(pdf: &Path, first: u32, last: u32) -> Result<Vec<Page>> {
    let out = Command::new("pdftotext")
        .args(["-f", &first.to_string(), "-l", &last.to_string()])
        .arg("-bbox-layout")
        .arg(pdf)
        .arg("-")
        .output()
        .context("running pdftotext -bbox-layout")?;
    anyhow::ensure!(
        out.status.success(),
        "pdftotext -bbox-layout failed on {}",
        pdf.display()
    );
    let pages = parse_layout(&String::from_utf8_lossy(&out.stdout));
    anyhow::ensure!(
        pages.len() == (last - first + 1) as usize,
        "bbox-layout parsed {} pages for {}..{} of {}",
        pages.len(),
        first,
        last,
        pdf.display()
    );
    Ok(pages)
}

pub fn compare_layout(a: &[Page], b: &[Page], first_page: u32, g1_pt: f64, g2_pt: f64) -> GeomTier {
    let mut tier = GeomTier {
        g1_pt,
        g2_pt,
        pages: BTreeMap::new(),
        max_dx_pt: 0.0,
        max_dy_pt: 0.0,
        lines_beyond_g1: 0,
        lines_beyond_g2: 0,
        block_or_line_count_mismatches: 0,
    };
    for (i, (pa, pb)) in a.iter().zip(b).enumerate() {
        let page = page_geom(pa, pb, &mut tier);
        tier.pages.insert(first_page + i as u32, page);
    }
    tier
}

fn page_geom(pa: &Page, pb: &Page, tier: &mut GeomTier) -> PageGeom {
    let mut geom = PageGeom {
        blocks_a: pa.blocks.len() as u32,
        blocks_b: pb.blocks.len() as u32,
        line_count_mismatches: 0,
        max_dx_pt: 0.0,
        max_dy_pt: 0.0,
    };
    if pa.blocks.len() != pb.blocks.len() {
        tier.block_or_line_count_mismatches += 1;
    }
    for (ba, bb) in pa.blocks.iter().zip(&pb.blocks) {
        if ba.len() != bb.len() {
            geom.line_count_mismatches += 1;
            tier.block_or_line_count_mismatches += 1;
            continue;
        }
        for (la, lb) in ba.iter().zip(bb) {
            let (dx, dy) = ((la.first_x - lb.first_x).abs(), (la.y - lb.y).abs());
            geom.max_dx_pt = geom.max_dx_pt.max(dx);
            geom.max_dy_pt = geom.max_dy_pt.max(dy);
            let d = dx.max(dy);
            tier.lines_beyond_g1 += u32::from(d > tier.g1_pt);
            tier.lines_beyond_g2 += u32::from(d > tier.g2_pt);
        }
    }
    tier.max_dx_pt = tier.max_dx_pt.max(geom.max_dx_pt);
    tier.max_dy_pt = tier.max_dy_pt.max(geom.max_dy_pt);
    geom
}
