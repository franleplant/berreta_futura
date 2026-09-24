use anyhow::{bail, Context, Result};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

use crate::critic::metrics::{decode_rgb, luma601, ordered_map, round_places, worker_count, Rgb};
use crate::critic::text::body_text_lines;
use crate::model::shared::py_strip;

pub const RASTER_DPI: u32 = 144;
pub const WHITE_THRESHOLD: u8 = 245;
pub const PAPER_WHITE: u8 = 255;
pub const SPARSE_INK_RATIO: f64 = 0.004;

const STANDALONE_PUNCTUATION: [char; 7] = [',', '.', ';', ':', '!', '?', '\u{2026}'];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Gray {
    pub width: u32,
    pub height: u32,
    pub data: Vec<u8>,
}

pub fn grayscale(image: &Rgb) -> Gray {
    Gray {
        width: image.width,
        height: image.height,
        data: image.data.chunks_exact(3).map(luma601).collect(),
    }
}

pub fn point_below(gray: &Gray, threshold: u8) -> Gray {
    Gray {
        width: gray.width,
        height: gray.height,
        data: gray
            .data
            .iter()
            .map(|&value| if value < threshold { 255 } else { 0 })
            .collect(),
    }
}

pub fn histogram(gray: &Gray) -> [u32; 256] {
    let mut counts = [0u32; 256];
    for &value in &gray.data {
        counts[value as usize] += 1;
    }
    counts
}

pub fn rgb_histogram(image: &Rgb) -> [u32; 768] {
    let mut counts = [0u32; 768];
    for pixel in image.data.chunks_exact(3) {
        for (band, &value) in pixel.iter().enumerate() {
            counts[band * 256 + value as usize] += 1;
        }
    }
    counts
}

pub fn getbbox(gray: &Gray) -> Option<[u32; 4]> {
    let (mut left, mut top, mut right, mut bottom) = (u32::MAX, u32::MAX, 0u32, 0u32);
    for (index, &value) in gray.data.iter().enumerate() {
        if value == 0 {
            continue;
        }
        let x = index as u32 % gray.width;
        let y = index as u32 / gray.width;
        left = left.min(x);
        top = top.min(y);
        right = right.max(x + 1);
        bottom = bottom.max(y + 1);
    }
    (right > 0).then_some([left, top, right, bottom])
}

pub fn extrema(gray: &Gray) -> Option<(u8, u8)> {
    Some((*gray.data.iter().min()?, *gray.data.iter().max()?))
}

pub fn difference(first: &Rgb, second: &Rgb) -> Result<Rgb> {
    if (first.width, first.height) != (second.width, second.height) {
        bail!(
            "images do not match in size: {}x{} against {}x{}",
            first.width,
            first.height,
            second.width,
            second.height
        );
    }
    Ok(Rgb {
        width: first.width,
        height: first.height,
        data: first
            .data
            .iter()
            .zip(&second.data)
            .map(|(one, other)| one.abs_diff(*other))
            .collect(),
    })
}

#[derive(Debug, Clone, PartialEq)]
pub struct PageInspection {
    pub page: usize,
    pub pixel_dimensions: [u32; 2],
    pub ink_ratio: f64,
    pub ink_bbox: Option<[u32; 4]>,
    pub presence_ratio: f64,
    pub presence_bbox: Option<[u32; 4]>,
    pub body_text_lines: usize,
    pub text_characters: usize,
    pub blank: bool,
    pub ink_free: bool,
    pub sparse: bool,
    pub standalone_punctuation_lines: Vec<String>,
}

impl PageInspection {
    pub fn row(&self) -> Value {
        json!({
            "page": self.page,
            "pixel_dimensions": self.pixel_dimensions,
            "ink_ratio": self.ink_ratio,
            "ink_bbox": self.ink_bbox,
            "presence_ratio": self.presence_ratio,
            "presence_bbox": self.presence_bbox,
            "body_text_lines": self.body_text_lines,
            "largest_void": Value::Null,
            "voids": Value::Array(vec![]),
            "tail_band": Value::Null,
            "text_characters": self.text_characters,
            "blank": self.blank,
            "ink_free": self.ink_free,
            "sparse": self.sparse,
            "standalone_punctuation_lines": self.standalone_punctuation_lines,
        })
    }
}

pub(crate) fn standalone_punctuation_lines(text: &str) -> Vec<String> {
    text.lines()
        .map(py_strip)
        .filter(|line| {
            !line.is_empty()
                && line
                    .chars()
                    .all(|character| STANDALONE_PUNCTUATION.contains(&character))
        })
        .map(str::to_string)
        .collect()
}

pub fn inspect_page(path: &Path, page_number: usize, text: &str) -> Result<PageInspection> {
    let gray = grayscale(&decode_rgb(path)?);
    let ink_mask = point_below(&gray, WHITE_THRESHOLD);
    let ink_pixels = histogram(&ink_mask)[255] as usize;
    let total_pixels = gray.width as usize * gray.height as usize;
    let ink_bbox = getbbox(&ink_mask);
    let presence_mask = point_below(&gray, PAPER_WHITE);
    let presence_pixels = histogram(&presence_mask)[255] as usize;
    let presence_bbox = getbbox(&presence_mask);
    let pure_white = extrema(&gray) == Some((255, 255));
    let stripped = py_strip(text);
    let ratio = match total_pixels {
        0 => 0.0,
        total => ink_pixels as f64 / total as f64,
    };
    let presence_ratio = match total_pixels {
        0 => 0.0,
        total => presence_pixels as f64 / total as f64,
    };
    Ok(PageInspection {
        page: page_number,
        pixel_dimensions: [gray.width, gray.height],
        ink_ratio: round_places(ratio, 6),
        ink_bbox,
        presence_ratio: round_places(presence_ratio, 6),
        presence_bbox,
        body_text_lines: body_text_lines(text),
        text_characters: stripped.chars().count(),
        blank: pure_white && stripped.is_empty(),
        ink_free: ink_pixels == 0 && stripped.is_empty(),
        sparse: ratio > 0.0 && ratio < SPARSE_INK_RATIO,
        standalone_punctuation_lines: standalone_punctuation_lines(text),
    })
}

fn executable(program: &str) -> Option<PathBuf> {
    std::env::split_paths(&std::env::var_os("PATH")?)
        .map(|directory| directory.join(program))
        .find(|candidate| candidate.is_file())
}

fn rasterize(tool: &Path, pdf: &Path, prefix: &Path, window: Option<(usize, usize)>) -> Result<()> {
    let mut command = std::process::Command::new(tool);
    command.args(["-png", "-r", &RASTER_DPI.to_string()]);
    if let Some((first, last)) = window {
        command.args(["-f", &first.to_string(), "-l", &last.to_string()]);
    }
    let completed = command
        .arg(pdf)
        .arg(prefix)
        .output()
        .with_context(|| format!("cannot run {}", tool.display()))?;
    if completed.status.success() {
        return Ok(());
    }
    let stderr = String::from_utf8_lossy(&completed.stderr);
    let stdout = String::from_utf8_lossy(&completed.stdout);
    let detail = [stderr.trim(), stdout.trim(), "unknown Poppler error"]
        .into_iter()
        .find(|candidate| !candidate.is_empty())
        .unwrap_or("unknown Poppler error");
    bail!("Could not rasterize reader PDF for criticism: {detail}")
}

fn page_number(path: &Path) -> usize {
    path.file_stem()
        .and_then(|stem| stem.to_str())
        .and_then(|stem| stem.rsplit_once('-'))
        .and_then(|(_, tail)| tail.parse().ok())
        .unwrap_or(0)
}

fn rendered_names(output_dir: &Path) -> Result<Vec<PathBuf>> {
    let mut found = vec![];
    for entry in std::fs::read_dir(output_dir)
        .with_context(|| format!("cannot list {}", output_dir.display()))?
    {
        let path = entry?.path();
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("");
        if name.starts_with("page-") && name.ends_with(".png") {
            found.push(path);
        }
    }
    found.sort_by(|one, other| {
        page_number(one)
            .cmp(&page_number(other))
            .then_with(|| one.cmp(other))
    });
    Ok(found)
}

pub fn render_pages(pdf: &Path, output_dir: &Path, shards: Option<usize>) -> Result<Vec<PathBuf>> {
    let tool = executable("pdftoppm")
        .context("Render criticism requires Poppler's pdftoppm executable.")?;
    std::fs::create_dir_all(output_dir)
        .with_context(|| format!("cannot create {}", output_dir.display()))?;
    let prefix = output_dir.join("page");
    let page_count = lopdf::Document::load(pdf)
        .map(|document| document.get_pages().len())
        .unwrap_or(0);
    let shard_count = shards.unwrap_or_else(|| worker_count(page_count / 2, None));
    if shard_count < 2 {
        rasterize(&tool, pdf, &prefix, None)?;
    } else {
        let cuts: Vec<usize> = (0..=shard_count)
            .map(|index| page_count * index / shard_count)
            .collect();
        let windows: Vec<(usize, usize)> = (0..shard_count)
            .map(|index| (cuts[index] + 1, cuts[index + 1]))
            .collect();
        ordered_map(
            |window: &(usize, usize)| rasterize(&tool, pdf, &prefix, Some(*window)),
            &windows,
            None,
        )?;
    }
    let mut normalized = vec![];
    for (index, path) in rendered_names(output_dir)?.iter().enumerate() {
        let target = output_dir.join(format!("page-{:03}.png", index + 1));
        if *path != target {
            std::fs::rename(path, &target)
                .with_context(|| format!("cannot rename {}", path.display()))?;
        }
        normalized.push(target);
    }
    Ok(normalized)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReviewRasters {
    pub reader: Vec<PathBuf>,
    pub booklet: Vec<PathBuf>,
    pub cover_booklet: Vec<PathBuf>,
}

pub fn render_review_pages(
    reader_pdf: &Path,
    booklet_pdf: &Path,
    cover_booklet_pdf: &Path,
    review_dir: &Path,
) -> Result<ReviewRasters> {
    Ok(ReviewRasters {
        reader: render_pages(reader_pdf, &review_dir.join("reader-pages"), None)?,
        booklet: render_pages(booklet_pdf, &review_dir.join("booklet-sides"), None)?,
        cover_booklet: render_pages(
            cover_booklet_pdf,
            &review_dir.join("cover-booklet-sides"),
            None,
        )?,
    })
}
