use anyhow::{bail, ensure, Context, Result};
use serde::Serialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Serialize)]
pub struct RasterTier {
    pub status: String,
    pub dpi: u32,
    pub channel_delta: u8,
    pub v1: String,
    pub v2: String,
    pub worst_page_fraction: f64,
    pub max_channel_delta: u8,
    pub dimension_mismatches: Vec<u32>,
    pub pages: BTreeMap<u32, PageRaster>,
}

#[derive(Serialize)]
pub struct PageRaster {
    pub differing_fraction: f64,
    pub max_channel_delta: u8,
}

#[derive(Serialize)]
#[serde(untagged)]
pub enum RasterGuard {
    NotEvaluated {
        status: String,
        owner: String,
    },
    Evaluated {
        status: String,
        bound: u8,
        pages_beyond: Vec<u32>,
    },
}

pub struct VSpec {
    pub dpi: u32,
    pub channel_delta: u8,
    pub v1_page_fraction: f64,
    pub v2_page_fraction: f64,
}

pub fn compare(
    pdf_a: &Path,
    pdf_b: &Path,
    first: u32,
    last: u32,
    spec: &VSpec,
    bound: Option<u8>,
    heatmap_dir: &Path,
) -> Result<(RasterTier, RasterGuard)> {
    let scratch = scratch_dir()?;
    let pages_a = rasterize(pdf_a, first, last, spec.dpi, &scratch, "a")?;
    let pages_b = rasterize(pdf_b, first, last, spec.dpi, &scratch, "b")?;
    let mut tier = RasterTier {
        status: "pass".into(),
        dpi: spec.dpi,
        channel_delta: spec.channel_delta,
        v1: "pass".into(),
        v2: "pass".into(),
        worst_page_fraction: 0.0,
        max_channel_delta: 0,
        dimension_mismatches: vec![],
        pages: BTreeMap::new(),
    };
    let mut pages_beyond = vec![];
    for page in first..=last {
        let (pa, pb) = (page_file(&pages_a, page)?, page_file(&pages_b, page)?);
        let (img_a, img_b) = (read_ppm(pa)?, read_ppm(pb)?);
        if img_a.width != img_b.width || img_a.height != img_b.height {
            tier.dimension_mismatches.push(page);
            tier.status = "fail".into();
            continue;
        }
        let stats = diff_page(&img_a, &img_b, spec.channel_delta, bound, page, heatmap_dir)?;
        tier.max_channel_delta = tier.max_channel_delta.max(stats.max_delta);
        tier.worst_page_fraction = tier.worst_page_fraction.max(stats.fraction);
        if stats.beyond_bound {
            pages_beyond.push(page);
        }
        tier.pages.insert(
            page,
            PageRaster {
                differing_fraction: stats.fraction,
                max_channel_delta: stats.max_delta,
            },
        );
        fs::remove_file(pa).ok();
        fs::remove_file(pb).ok();
    }
    if tier.worst_page_fraction >= spec.v1_page_fraction {
        tier.v1 = "fail".into();
    }
    if tier.worst_page_fraction >= spec.v2_page_fraction {
        tier.v2 = "fail".into();
    }
    fs::remove_dir_all(&scratch).ok();
    let guard = match bound {
        None => RasterGuard::NotEvaluated {
            status: "not_evaluated".into(),
            owner: "WP-0.2d raster_bound derivation".into(),
        },
        Some(bound) => RasterGuard::Evaluated {
            status: if pages_beyond.is_empty() && tier.dimension_mismatches.is_empty() {
                "pass"
            } else {
                "fail"
            }
            .into(),
            bound,
            pages_beyond,
        },
    };
    Ok((tier, guard))
}

struct PageStats {
    fraction: f64,
    max_delta: u8,
    beyond_bound: bool,
}

struct Ppm {
    width: usize,
    height: usize,
    rgb: Vec<u8>,
}

const HEATMAP_CELL: usize = 8;

fn diff_page(
    a: &Ppm,
    b: &Ppm,
    channel_delta: u8,
    bound: Option<u8>,
    page: u32,
    heatmap_dir: &Path,
) -> Result<PageStats> {
    let cells_w = a.width.div_ceil(HEATMAP_CELL);
    let cells_h = a.height.div_ceil(HEATMAP_CELL);
    let mut cells = vec![0u32; cells_w * cells_h];
    let mut differing = 0u64;
    let mut max_delta = 0u8;
    for (i, (ca, cb)) in a.rgb.chunks_exact(3).zip(b.rgb.chunks_exact(3)).enumerate() {
        let delta = ca
            .iter()
            .zip(cb)
            .map(|(x, y)| x.abs_diff(*y))
            .max()
            .unwrap_or(0);
        max_delta = max_delta.max(delta);
        if delta > channel_delta {
            differing += 1;
            let (x, y) = (i % a.width, i / a.width);
            cells[y / HEATMAP_CELL * cells_w + x / HEATMAP_CELL] += 1;
        }
    }
    if differing > 0 {
        let path = heatmap_dir.join(format!("heatmap-{page:03}.bmp"));
        write_heatmap(&path, &cells, cells_w, cells_h)?;
    }
    let total = (a.width * a.height) as f64;
    Ok(PageStats {
        fraction: differing as f64 / total,
        max_delta,
        beyond_bound: bound.is_some_and(|b| max_delta > b),
    })
}

fn write_heatmap(path: &Path, cells: &[u32], w: usize, h: usize) -> Result<()> {
    let peak = cells.iter().copied().max().unwrap_or(1).max(1);
    let row_bytes = (w * 3).next_multiple_of(4);
    let mut bmp = Vec::with_capacity(54 + row_bytes * h);
    let size = 54 + row_bytes * h;
    bmp.extend(*b"BM");
    bmp.extend((size as u32).to_le_bytes());
    bmp.extend([0u8; 4]);
    bmp.extend(54u32.to_le_bytes());
    bmp.extend(40u32.to_le_bytes());
    bmp.extend((w as i32).to_le_bytes());
    bmp.extend((h as i32).to_le_bytes());
    bmp.extend(1u16.to_le_bytes());
    bmp.extend(24u16.to_le_bytes());
    bmp.extend([0u8; 24]);
    for y in (0..h).rev() {
        let start = bmp.len();
        for x in 0..w {
            let heat = cells[y * w + x];
            let level = if heat == 0 {
                255
            } else {
                (200 - heat * 200 / peak) as u8
            };
            bmp.extend([level, level, 255]);
        }
        bmp.resize(start + row_bytes, 0);
    }
    fs::write(path, bmp).with_context(|| format!("writing {}", path.display()))
}

fn scratch_dir() -> Result<PathBuf> {
    let dir = std::env::temp_dir().join(format!("mag-parity-raster-{}", std::process::id()));
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn rasterize(
    pdf: &Path,
    first: u32,
    last: u32,
    dpi: u32,
    scratch: &Path,
    tag: &str,
) -> Result<BTreeMap<u32, PathBuf>> {
    let dir = scratch.join(tag);
    fs::create_dir_all(&dir)?;
    let status = Command::new("pdftoppm")
        .args([
            "-r",
            &dpi.to_string(),
            "-f",
            &first.to_string(),
            "-l",
            &last.to_string(),
        ])
        .arg(pdf)
        .arg(dir.join("p"))
        .status()
        .context("running pdftoppm")?;
    ensure!(status.success(), "pdftoppm failed on {}", pdf.display());
    let mut pages = BTreeMap::new();
    for entry in fs::read_dir(&dir)? {
        let path = entry?.path();
        let name = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
        if let Some(num) = name.strip_prefix("p-").and_then(|n| n.parse::<u32>().ok()) {
            pages.insert(num, path);
        }
    }
    Ok(pages)
}

fn page_file(pages: &BTreeMap<u32, PathBuf>, page: u32) -> Result<&PathBuf> {
    pages
        .get(&page)
        .with_context(|| format!("pdftoppm produced no page {page}"))
}

fn read_ppm(path: &Path) -> Result<Ppm> {
    let bytes = fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    let mut fields = vec![];
    let mut pos = 0;
    while fields.len() < 4 {
        while pos < bytes.len() && bytes[pos].is_ascii_whitespace() {
            pos += 1;
        }
        if bytes.get(pos) == Some(&b'#') {
            while pos < bytes.len() && bytes[pos] != b'\n' {
                pos += 1;
            }
            continue;
        }
        let start = pos;
        while pos < bytes.len() && !bytes[pos].is_ascii_whitespace() {
            pos += 1;
        }
        fields.push(std::str::from_utf8(&bytes[start..pos])?.to_string());
    }
    pos += 1;
    ensure!(fields[0] == "P6", "{} is not a P6 ppm", path.display());
    ensure!(
        fields[3] == "255",
        "{} maxval {} unsupported",
        path.display(),
        fields[3]
    );
    let (width, height) = (fields[1].parse::<usize>()?, fields[2].parse::<usize>()?);
    let rgb = bytes[pos..].to_vec();
    if rgb.len() != width * height * 3 {
        bail!("{} pixel data truncated", path.display());
    }
    Ok(Ppm { width, height, rgb })
}
