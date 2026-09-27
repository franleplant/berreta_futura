use crate::model::manifest::Edition;
use crate::typeset::layout::declared_pt;
use crate::typeset::media::pixels;
use anyhow::{Context, Result};
use sha2::{Digest, Sha256};
use std::path::Path;
use std::process::Command;

pub const LEGIBLE_TEXT_PT: f64 = 4.0;
pub const ENLARGED_MIN_PPI: f64 = 200.0;
pub const ENLARGED: [&str; 2] = ["full_band", "rotated_plate"];
const MIN_WORDS: usize = 8;
const MIN_CONFIDENCE: f64 = 60.0;
const CACHE: &str = ".magazine/legibility";
const PAGE_WIDTH_PT: f64 = 148.0 / 25.4 * 72.0;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Geometry {
    live: f64,
    measure: f64,
    inset: f64,
    cap: f64,
    compact_cap: f64,
    full_cap: f64,
    plate_length: f64,
    plate_depth: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Change {
    pub layout: &'static str,
    pub before: f64,
    pub after: f64,
}

impl Geometry {
    pub fn from_template() -> Result<Self> {
        Ok(Self {
            live: PAGE_WIDTH_PT - declared_pt("MARGIN-INNER")? - declared_pt("MARGIN-OUTER")?,
            measure: declared_pt("MEASURE")?,
            inset: declared_pt("COMPACT-BAND-INSET")?,
            cap: declared_pt("FIGURE-MAX-HEIGHT")?,
            compact_cap: declared_pt("COMPACT-FIGURE-MAX-HEIGHT")?,
            full_cap: declared_pt("FULL-FIGURE-MAX-HEIGHT")?,
            plate_length: declared_pt("ROTATED-PLATE-LENGTH")?,
            plate_depth: declared_pt("ROTATED-PLATE-DEPTH")?,
        })
    }

    pub fn width(&self, layout: &str, (w, h): (u32, u32)) -> f64 {
        let (column, cap) = match layout {
            "rotated_plate" => (self.plate_length, self.plate_depth),
            "full_band" => (self.live, self.full_cap),
            "evidence_band" | "evidence_band_prose" | "adaptive_band" => (self.live, self.cap),
            "compact_band" => (self.measure - 2.0 * self.inset, self.compact_cap),
            _ => (self.measure, self.cap),
        };
        column.min(cap * f64::from(w) / f64::from(h))
    }
}

pub fn decide(heights: &[f64], pixels: (u32, u32), layout: &str, g: &Geometry) -> Option<Change> {
    if heights.len() < MIN_WORDS {
        return None;
    }
    let mut sorted = heights.to_vec();
    sorted.sort_by(f64::total_cmp);
    let size = |width: f64| sorted[sorted.len() / 2] * width / f64::from(pixels.0);
    let before = size(g.width(layout, pixels));
    let options: Vec<(&'static str, f64)> = ENLARGED
        .into_iter()
        .map(|option| (option, g.width(option, pixels)))
        .filter(|(_, width)| f64::from(pixels.0) * 72.0 / width >= ENLARGED_MIN_PPI)
        .map(|(option, width)| (option, size(width)))
        .filter(|(_, after)| *after > before)
        .collect();
    let best = options.iter().max_by(|a, b| a.1.total_cmp(&b.1));
    let pick = options.iter().find(|(_, after)| *after >= LEGIBLE_TEXT_PT);
    (before < LEGIBLE_TEXT_PT)
        .then_some(pick.or(best))
        .flatten()
        .map(|&(layout, after)| Change {
            layout,
            before,
            after,
        })
}

pub fn enlarge(mut edition: Edition, repo_root: &Path) -> Result<Edition> {
    let geometry = Geometry::from_template()?;
    for article in &mut edition.articles {
        for figure in &mut article.figures {
            let fixed = figure.fit == "keep"
                || figure.layout == "rotated_plate"
                || figure.anchor == "__opener__";
            if fixed {
                continue;
            }
            let Some(heights) = word_heights(&figure.path, repo_root)? else {
                return Ok(edition);
            };
            let size = pixels(&figure.path)?;
            let Some(change) = decide(&heights, size, &figure.layout, &geometry) else {
                continue;
            };
            println!(
                "legibility: {}/{}: {} -> {}, printed text {:.1}pt -> {:.1}pt",
                article.id, figure.id, figure.layout, change.layout, change.before, change.after
            );
            if change.after < LEGIBLE_TEXT_PT {
                println!(
                    "warning: legibility: {}/{} reaches only {:.1}pt at its largest layout; \
                     the floor is {LEGIBLE_TEXT_PT}pt",
                    article.id, figure.id, change.after
                );
            }
            figure.layout = change.layout.to_string();
        }
    }
    Ok(edition)
}

fn word_heights(path: &Path, repo_root: &Path) -> Result<Option<Vec<f64>>> {
    let bytes = std::fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    let cached = repo_root
        .join(CACHE)
        .join(hex::encode(Sha256::digest(&bytes)));
    if let Ok(text) = std::fs::read_to_string(&cached) {
        return Ok(Some(text.lines().filter_map(|l| l.parse().ok()).collect()));
    }
    let Ok(out) = Command::new("tesseract")
        .arg(path)
        .args(["-", "--psm", "11", "tsv"])
        .output()
    else {
        println!(
            "warning: legibility: tesseract is not installed; figure layouts stay as declared \
             and small diagram text is not checked (brew install tesseract)"
        );
        return Ok(None);
    };
    anyhow::ensure!(
        out.status.success(),
        "tesseract failed on {}: {}",
        path.display(),
        String::from_utf8_lossy(&out.stderr)
    );
    let heights = words(&String::from_utf8_lossy(&out.stdout));
    std::fs::create_dir_all(
        cached
            .parent()
            .context("the legibility cache has no parent")?,
    )?;
    let lines: String = heights.iter().map(|h| format!("{h}\n")).collect();
    std::fs::write(&cached, lines)?;
    Ok(Some(heights))
}

fn words(tsv: &str) -> Vec<f64> {
    tsv.lines()
        .skip(1)
        .filter_map(|line| {
            let cells: Vec<&str> = line.split('\t').collect();
            let confidence: f64 = cells.get(10)?.parse().ok()?;
            let word = cells.get(11)?.trim();
            (confidence > MIN_CONFIDENCE && word.chars().count() > 2)
                .then(|| cells.get(9)?.parse().ok())
                .flatten()
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn g() -> Geometry {
        Geometry::from_template().expect("the template declares the figure geometry")
    }

    fn at(height: f64) -> Vec<f64> {
        vec![height; 20]
    }

    #[test]
    fn a_wide_diagram_already_at_full_width_becomes_a_rotated_plate() {
        let change = decide(&at(27.0), (2842, 1357), "evidence_band", &g()).expect("it changes");
        assert_eq!(change.layout, "rotated_plate");
        assert!((3.1..3.2).contains(&change.before), "{change:?}");
        assert!(change.after >= LEGIBLE_TEXT_PT, "{change:?}");
    }

    #[test]
    fn a_height_capped_screenshot_grows_to_full_width_before_it_rotates() {
        let change = decide(&at(15.0), (1080, 857), "evidence_band_prose", &g()).expect("it grows");
        assert_eq!(change.layout, "full_band");
        assert!(change.before < 3.7 && change.after > 4.5, "{change:?}");
    }

    #[test]
    fn a_near_square_image_never_rotates_and_warns_through_its_best_size() {
        let change = decide(&at(9.0), (1053, 1027), "evidence_band", &g()).expect("it grows");
        assert_eq!(change.layout, "full_band");
        assert!(change.after < LEGIBLE_TEXT_PT, "{change:?}");
        assert!(g().width("rotated_plate", (1053, 1027)) < g().width("full_band", (1053, 1027)));
    }

    #[test]
    fn too_few_words_or_legible_text_leave_the_figure_alone() {
        assert_eq!(decide(&[3.0; 7], (2842, 1357), "evidence_band", &g()), None);
        assert_eq!(decide(&at(60.0), (2842, 1357), "evidence_band", &g()), None);
    }

    #[test]
    fn an_option_below_the_enlarged_ppi_floor_is_not_offered() {
        assert_eq!(decide(&at(5.0), (600, 500), "column_plate", &g()), None);
    }

    #[test]
    fn tesseract_rows_keep_confident_words_longer_than_two_characters() {
        let head = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext";
        let tsv = format!(
            "{head}\n5\t1\t1\t1\t1\t1\t0\t0\t9\t27\t91.5\tAgent\n5\t1\t1\t1\t1\t2\t0\t0\t9\t30\t40\tNoise\n\
             5\t1\t1\t1\t1\t3\t0\t0\t9\t12\t95\tof\n4\t1\t1\t1\t1\t0\t0\t0\t9\t80\t-1\t\n"
        );
        assert_eq!(words(&tsv), vec![27.0]);
    }
}
