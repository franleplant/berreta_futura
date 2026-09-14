mod geometry;
mod text;

use anyhow::{Context, Result};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const SPEC_PATH: &str = "meta/verification/parity.yaml";

#[derive(Serialize)]
struct Verdict {
    edition: String,
    mode: String,
    inputs: BTreeMap<String, String>,
    domain: Domain,
    tier_s: TierS,
    tier_g: Option<geometry::GeomTier>,
    tier_v: NotEvaluated,
    tier_e: NotEvaluated,
}

#[derive(Serialize)]
struct Domain {
    description: String,
    first_page: u32,
    last_page: u32,
}

#[derive(Serialize)]
struct TierS {
    page_count: PageCount,
    boxes: Option<geometry::BoxClause>,
    text: Option<text::TextClause>,
    code_blocks: NotEvaluated,
    color: NotEvaluated,
    navigation: NotEvaluated,
    critic: NotEvaluated,
}

#[derive(Serialize)]
struct PageCount {
    status: String,
    a: u32,
    b: u32,
}

#[derive(Serialize)]
struct NotEvaluated {
    status: String,
    owner: String,
}

fn not_evaluated(owner: &str) -> NotEvaluated {
    NotEvaluated {
        status: "not_evaluated".into(),
        owner: owner.into(),
    }
}

fn spec() -> Result<serde_yaml::Value> {
    let raw = fs::read_to_string(SPEC_PATH).with_context(|| format!("reading {SPEC_PATH}"))?;
    serde_yaml::from_str(&raw).with_context(|| format!("parsing {SPEC_PATH}"))
}

fn spec_f64(spec: &serde_yaml::Value, path: &[&str]) -> Result<f64> {
    let mut node = spec;
    for key in path {
        node = node
            .get(key)
            .with_context(|| format!("{SPEC_PATH} missing {}", path.join(".")))?;
    }
    node.as_f64()
        .with_context(|| format!("{SPEC_PATH} {} is not a number", path.join(".")))
}

fn assert_poppler(spec: &serde_yaml::Value) -> Result<()> {
    let pinned = spec
        .get("tools")
        .and_then(|t| t.get("poppler"))
        .and_then(|v| v.as_str())
        .context("parity.yaml tools.poppler missing")?
        .to_string();
    for tool in ["pdfinfo", "pdftotext"] {
        let out = Command::new(tool)
            .arg("-v")
            .output()
            .with_context(|| format!("running {tool} -v"))?;
        let banner = String::from_utf8_lossy(&out.stderr).to_string()
            + &String::from_utf8_lossy(&out.stdout);
        let found = banner
            .lines()
            .next()
            .and_then(|l| l.split_whitespace().last())
            .unwrap_or_default()
            .to_string();
        anyhow::ensure!(
            found == pinned,
            "{tool} version {found} does not match pinned poppler {pinned}"
        );
    }
    Ok(())
}

fn sha256_file(path: &Path) -> Result<String> {
    let bytes = fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    Ok(hex::encode(Sha256::digest(bytes)))
}

pub fn run(edition: &str, pre_rendered: Option<(PathBuf, PathBuf)>) -> Result<i32> {
    let spec = spec()?;
    assert_poppler(&spec)?;
    let (dir_a, dir_b) = pre_rendered.context(
        "mag parity without --pre-rendered arrives with WP-2.0b; pass --pre-rendered <dirA> <dirB>",
    )?;
    let (pdf_a, pdf_b) = (dir_a.join("en/reader.pdf"), dir_b.join("en/reader.pdf"));
    let mut inputs = BTreeMap::new();
    inputs.insert("a_reader_sha256".into(), sha256_file(&pdf_a)?);
    inputs.insert("b_reader_sha256".into(), sha256_file(&pdf_b)?);
    let (na, nb) = (geometry::page_count(&pdf_a)?, geometry::page_count(&pdf_b)?);
    let verdict = build_verdict(&spec, edition, inputs, &pdf_a, &pdf_b, na, nb)?;
    write_verdict(edition, &verdict)?;
    summarize(&verdict);
    Ok(i32::from(!all_evaluated_pass(&verdict)))
}

fn build_verdict(
    spec: &serde_yaml::Value,
    edition: &str,
    inputs: BTreeMap<String, String>,
    pdf_a: &Path,
    pdf_b: &Path,
    na: u32,
    nb: u32,
) -> Result<Verdict> {
    let counts_equal = na == nb && na >= 3;
    let (first, last) = (2, na.saturating_sub(1));
    let mut verdict = Verdict {
        edition: edition.into(),
        mode: "pre_rendered".into(),
        inputs,
        domain: Domain {
            description: "interior: reader.pdf pages 2..n-1, n required equal".into(),
            first_page: first,
            last_page: last,
        },
        tier_s: TierS {
            page_count: PageCount {
                status: if counts_equal { "pass" } else { "fail" }.into(),
                a: na,
                b: nb,
            },
            boxes: None,
            text: None,
            code_blocks: not_evaluated("WP-0.2b input level, WP-3.3 fixture"),
            color: not_evaluated("WP-0.2b"),
            navigation: not_evaluated("WP-0.2b"),
            critic: not_evaluated("WP-2.0b oracle leg, WP-5.3g typst leg"),
        },
        tier_g: None,
        tier_v: not_evaluated("WP-0.2c"),
        tier_e: not_evaluated("WP-0.2b display list, WP-0.2c raster"),
    };
    if !counts_equal {
        return Ok(verdict);
    }
    let tolerance = spec_f64(spec, &["tiers", "s", "box_tolerance_pt"])?;
    let boxes_a = geometry::boxes(pdf_a, first, last)?;
    let boxes_b = geometry::boxes(pdf_b, first, last)?;
    verdict.tier_s.boxes = Some(geometry::compare_boxes(&boxes_a, &boxes_b, tolerance));
    let texts_a = text::page_texts(pdf_a, first, last)?;
    let texts_b = text::page_texts(pdf_b, first, last)?;
    verdict.tier_s.text = Some(text::compare(&texts_a, &texts_b, first));
    let (g1, g2) = (
        spec_f64(spec, &["tiers", "g", "g1_pt"])?,
        spec_f64(spec, &["tiers", "g", "g2_pt"])?,
    );
    let layout_a = geometry::layout_pages(pdf_a, first, last)?;
    let layout_b = geometry::layout_pages(pdf_b, first, last)?;
    verdict.tier_g = Some(geometry::compare_layout(
        &layout_a, &layout_b, first, g1, g2,
    ));
    Ok(verdict)
}

fn all_evaluated_pass(v: &Verdict) -> bool {
    v.tier_s.page_count.status == "pass"
        && v.tier_s.boxes.as_ref().is_some_and(|c| c.status == "pass")
        && v.tier_s.text.as_ref().is_some_and(|c| c.status == "pass")
}

fn write_verdict(edition: &str, verdict: &Verdict) -> Result<()> {
    let dir = PathBuf::from("output/parity").join(edition);
    fs::create_dir_all(&dir).with_context(|| format!("creating {}", dir.display()))?;
    let path = dir.join("verdict.json");
    let json = serde_json::to_string_pretty(verdict)? + "\n";
    fs::write(&path, json).with_context(|| format!("writing {}", path.display()))?;
    println!("verdict: {}", path.display());
    Ok(())
}

fn summarize(v: &Verdict) {
    println!(
        "tier S page_count: {} ({} vs {})",
        v.tier_s.page_count.status, v.tier_s.page_count.a, v.tier_s.page_count.b
    );
    if let Some(b) = &v.tier_s.boxes {
        println!(
            "tier S boxes: {} ({} mismatches)",
            b.status,
            b.mismatches.len()
        );
    }
    if let Some(t) = &v.tier_s.text {
        println!(
            "tier S text: {} ({} pages differ)",
            t.status,
            t.pages_differing.len()
        );
    }
    if let Some(g) = &v.tier_g {
        println!(
            "tier G: max dx {:.3} pt, max dy {:.3} pt, beyond G1 {}, beyond G2 {}, structure mismatches {}",
            g.max_dx_pt, g.max_dy_pt, g.lines_beyond_g1, g.lines_beyond_g2,
            g.block_or_line_count_mismatches
        );
    }
}
