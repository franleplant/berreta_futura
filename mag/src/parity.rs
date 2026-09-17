mod display;
mod geometry;
mod raster;
mod report;
mod streams;
mod text;

use anyhow::{Context, Result};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use streams::Face;

#[allow(unused_imports)]
pub(crate) use display::trace_elements;
#[allow(unused_imports)]
pub(crate) use streams::{Color, Element, Face as TextFace};

#[allow(dead_code)]
pub(crate) fn text_font_map() -> Result<BTreeMap<String, Face>> {
    font_name_map(&spec()?)
}

const SPEC_PATH: &str = "meta/verification/parity.yaml";

#[derive(Serialize)]
struct Verdict {
    edition: String,
    mode: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    staged_input_digest: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    staleness: Option<Staleness>,
    #[serde(skip_serializing_if = "Option::is_none")]
    typst_leg: Option<LegFailure>,
    #[serde(skip_serializing_if = "Option::is_none")]
    page_sets: Option<BTreeMap<String, Vec<u32>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    scored_set: Option<ScoredSet>,
    inputs: BTreeMap<String, String>,
    domain: Domain,
    tier_s: TierS,
    tier_g: Option<geometry::GeomTier>,
    tier_v: Option<raster::RasterTier>,
    tier_e: TierE,
}

#[derive(Serialize)]
struct TierE {
    display_list: Option<display::DisplayClause>,
    glyph_positions: Option<display::GlyphClause>,
    raster: Option<raster::RasterGuard>,
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
    color: Option<display::SimpleClause>,
    navigation: Option<display::NavClause>,
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

#[derive(Serialize)]
struct Staleness {
    status: String,
    current: String,
    baseline: Option<String>,
}

#[derive(Serialize)]
struct LegFailure {
    status: String,
    engine: String,
    error: String,
}

#[derive(Serialize)]
struct ScoredSet {
    name: String,
    pages: Vec<u32>,
    clauses_differing: BTreeMap<String, Vec<u32>>,
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

const TRACER: &str = "lopdf-0.45.0";

fn assert_tracer(spec: &serde_yaml::Value) -> Result<()> {
    let recorded = spec
        .get("tools")
        .and_then(|t| t.get("display_tracer"))
        .and_then(|v| v.as_str())
        .context("parity.yaml tools.display_tracer missing")?;
    anyhow::ensure!(
        recorded == TRACER,
        "display tracer {TRACER} does not match recorded {recorded}"
    );
    Ok(())
}

fn font_name_map(spec: &serde_yaml::Value) -> Result<BTreeMap<String, Face>> {
    let entries = spec
        .get("normalization")
        .and_then(|n| n.get("font_name_map"))
        .and_then(|f| f.get("entries"))
        .and_then(|e| e.as_mapping())
        .context("parity.yaml normalization.font_name_map.entries missing")?;
    let mut map = BTreeMap::new();
    for (alias, entry) in entries {
        let alias = alias.as_str().context("font_name_map alias not a string")?;
        let face = entry
            .get("face")
            .and_then(|f| f.as_str())
            .with_context(|| format!("font_name_map {alias} missing face"))?;
        let file = entry
            .get("file")
            .and_then(|f| f.as_str())
            .with_context(|| format!("font_name_map {alias} missing file"))?;
        map.insert(
            alias.to_string(),
            Face {
                face: face.to_string(),
                file: file.to_string(),
            },
        );
    }
    Ok(map)
}

fn assert_poppler(spec: &serde_yaml::Value) -> Result<()> {
    let pinned = spec
        .get("tools")
        .and_then(|t| t.get("poppler"))
        .and_then(|v| v.as_str())
        .context("parity.yaml tools.poppler missing")?
        .to_string();
    for tool in ["pdfinfo", "pdftotext", "pdftoppm"] {
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

fn staged_digest(request: &Path) -> Result<String> {
    let raw =
        fs::read_to_string(request).with_context(|| format!("reading {}", request.display()))?;
    let doc: serde_json::Value =
        serde_json::from_str(&raw).with_context(|| format!("parsing {}", request.display()))?;
    let rows = doc
        .get("inputs")
        .and_then(|v| v.as_array())
        .with_context(|| format!("{} has no inputs array", request.display()))?;
    let mut entries = Vec::new();
    for row in rows {
        let target = row
            .get("targetPath")
            .and_then(|v| v.as_str())
            .context("input row missing targetPath")?;
        let source = row
            .get("sourcePath")
            .and_then(|v| v.as_str())
            .context("input row missing sourcePath")?;
        entries.push(format!("{target}\u{1f}{}", sha256_file(Path::new(source))?));
    }
    entries.sort();
    Ok(hex::encode(Sha256::digest(entries.join("\u{1e}"))))
}

fn render_dirs() -> Result<Vec<PathBuf>> {
    let editions = Path::new("editions");
    let mut dirs = Vec::new();
    for entry in fs::read_dir(editions).context("reading editions/")? {
        let edition = entry?.path();
        let Ok(children) = fs::read_dir(&edition) else {
            continue;
        };
        for child in children.filter_map(|c| c.ok()) {
            let path = child.path();
            if path
                .file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with("render-"))
            {
                dirs.push(path);
            }
        }
    }
    dirs.sort();
    Ok(dirs)
}

fn render_leg(edition: &str, run: Option<&str>, engine: &str) -> Result<PathBuf> {
    let before = render_dirs()?;
    let args = crate::render::RenderArgs {
        edition: edition.to_string(),
        operation: "render_edition".into(),
        article: None,
        langs: Some("en".into()),
        run: run.map(str::to_string),
        anchor_model: "haiku".into(),
        no_model: true,
        engine: Some(engine.to_string()),
    };
    crate::render::run(&args)?;
    let fresh: Vec<PathBuf> = render_dirs()?
        .into_iter()
        .filter(|p| !before.contains(p))
        .collect();
    match fresh.len() {
        1 => Ok(fresh.into_iter().next().expect("length checked")),
        n => anyhow::bail!("{engine} leg produced {n} new render directories, expected exactly 1"),
    }
}

fn manifest_pages(manifest: &serde_json::Value, key: &str) -> Result<BTreeMap<String, u32>> {
    let node = manifest
        .get("layout")
        .and_then(|l| l.get(key))
        .and_then(|v| v.as_object())
        .with_context(|| format!("edition-manifest.json layout.{key} missing or not an object"))?;
    node.iter()
        .map(|(k, v)| {
            let page = v
                .as_u64()
                .with_context(|| format!("layout.{key}.{k} is not an integer"))?;
            Ok((k.clone(), u32::try_from(page).context("page out of range")?))
        })
        .collect()
}

fn placement_pages(manifest: &serde_json::Value) -> Result<Vec<u32>> {
    let layout = manifest.get("layout").context("manifest missing layout")?;
    let mut pages: Vec<u32> = layout
        .get("figures")
        .and_then(|v| v.as_array())
        .map(|figs| {
            figs.iter()
                .filter_map(|f| f.get("page").and_then(|p| p.as_u64()))
                .filter_map(|p| u32::try_from(p).ok())
                .collect()
        })
        .unwrap_or_default();
    let toc = manifest_pages(manifest, "toc")?;
    let spans = manifest_pages(manifest, "article_pages")?;
    if let Some(tails) = layout.get("tail_arts").and_then(|v| v.as_array()) {
        for tail in tails {
            if tail.get("printed").and_then(|p| p.as_bool()) != Some(true) {
                continue;
            }
            let article = tail
                .get("article")
                .and_then(|a| a.as_str())
                .context("tail_arts entry missing article")?;
            let (start, span) = (toc.get(article), spans.get(article));
            if let (Some(start), Some(span)) = (start, span) {
                pages.push(start + span - 1);
            }
        }
    }
    pages.sort_unstable();
    pages.dedup();
    Ok(pages)
}

fn fenced_first_lines(request: &Path) -> Result<Vec<String>> {
    let raw = fs::read_to_string(request)?;
    let doc: serde_json::Value = serde_json::from_str(&raw)?;
    let rows = doc
        .get("inputs")
        .and_then(|v| v.as_array())
        .context("request.json has no inputs array")?;
    let mut lines = Vec::new();
    for row in rows {
        let target = row.get("targetPath").and_then(|v| v.as_str()).unwrap_or("");
        if !target.contains("/articles/") || !target.ends_with(".md") {
            continue;
        }
        let source = row
            .get("sourcePath")
            .and_then(|v| v.as_str())
            .context("input row missing sourcePath")?;
        let body = fs::read_to_string(source)
            .with_context(|| format!("reading staged manuscript {source}"))?;
        let mut fenced = false;
        for line in body.lines() {
            if line.trim_start().starts_with("```") {
                fenced = !fenced;
                continue;
            }
            if fenced && !line.trim().is_empty() {
                lines.push(line.trim().to_string());
                fenced = false;
            }
        }
    }
    Ok(lines)
}

fn code_pages(request: &Path, texts: &[String], first: u32) -> Result<Vec<u32>> {
    let needles = fenced_first_lines(request)?;
    let mut pages = Vec::new();
    for needle in needles {
        let collapsed = needle.split_whitespace().collect::<Vec<_>>().join(" ");
        if collapsed.is_empty() {
            continue;
        }
        if let Some(offset) = texts.iter().position(|t| t.contains(&collapsed)) {
            pages.push(first + u32::try_from(offset).context("page offset out of range")?);
        }
    }
    pages.sort_unstable();
    pages.dedup();
    Ok(pages)
}

fn page_sets(
    manifest: &Path,
    first: u32,
    last: u32,
    code: Vec<u32>,
) -> Result<BTreeMap<String, Vec<u32>>> {
    let raw =
        fs::read_to_string(manifest).with_context(|| format!("reading {}", manifest.display()))?;
    let doc: serde_json::Value =
        serde_json::from_str(&raw).with_context(|| format!("parsing {}", manifest.display()))?;
    let furniture: Vec<u32> = (first..=last).collect();
    let mut openers: Vec<u32> = manifest_pages(&doc, "toc")?.into_values().collect();
    openers.sort_unstable();
    openers.dedup();
    openers.retain(|p| furniture.contains(p));
    let mut placement = placement_pages(&doc)?;
    placement.retain(|p| furniture.contains(p));
    let body: Vec<u32> = furniture
        .iter()
        .filter(|p| !openers.contains(p) && !placement.contains(p))
        .copied()
        .collect();
    let mut sets = BTreeMap::new();
    sets.insert("body".to_string(), body);
    sets.insert("code".to_string(), code);
    sets.insert("furniture".to_string(), furniture);
    sets.insert("openers".to_string(), openers);
    sets.insert("placement".to_string(), placement);
    Ok(sets)
}

fn baseline_digest() -> Result<Option<String>> {
    let path = Path::new("meta/verification/baseline.json");
    if !path.exists() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path)?;
    let doc: serde_json::Value = serde_json::from_str(&raw)?;
    Ok(doc
        .get("staged_input_digest")
        .and_then(|v| v.as_str())
        .map(str::to_string))
}

fn staleness(current: &str) -> Result<Staleness> {
    let baseline = baseline_digest()?;
    let status = match &baseline {
        Some(recorded) if recorded != current => "stale",
        Some(_) => "fresh",
        None => "unseeded",
    };
    Ok(Staleness {
        status: status.into(),
        current: current.to_string(),
        baseline,
    })
}

fn clause_pages(v: &Verdict) -> BTreeMap<String, Vec<u32>> {
    let mut out = BTreeMap::new();
    if let Some(c) = &v.tier_s.text {
        out.insert("text".to_string(), c.pages_differing.clone());
    }
    if let Some(c) = &v.tier_s.color {
        out.insert("color".to_string(), c.pages_differing.clone());
    }
    if let Some(c) = &v.tier_e.display_list {
        let pages = c.pages_differing.iter().map(|d| d.page).collect();
        out.insert("display_list".to_string(), pages);
    }
    out
}

fn score_set(v: &Verdict, name: &str) -> Result<ScoredSet> {
    let sets = v
        .page_sets
        .as_ref()
        .context("--set needs page sets, which require a rendered oracle leg")?;
    let pages = sets
        .get(name)
        .with_context(|| {
            format!(
                "unknown page set '{name}': expected one of {}",
                sets.keys().cloned().collect::<Vec<_>>().join(", ")
            )
        })?
        .clone();
    let clauses_differing = clause_pages(v)
        .into_iter()
        .map(|(clause, differing)| {
            let hits: Vec<u32> = differing
                .into_iter()
                .filter(|p| pages.contains(p))
                .collect();
            (clause, hits)
        })
        .filter(|(_, hits)| !hits.is_empty())
        .collect();
    Ok(ScoredSet {
        name: name.to_string(),
        pages,
        clauses_differing,
    })
}

pub struct Options {
    pub pre_rendered: Option<(PathBuf, PathBuf)>,
    pub run_dir: Option<String>,
    pub oracle_only: bool,
    pub set: Option<String>,
}

struct Legs {
    dir_a: PathBuf,
    dir_b: PathBuf,
    mode: &'static str,
    digest: Option<String>,
    typst_leg: Option<LegFailure>,
}

fn oracle_cache_path(out_dir: &Path) -> PathBuf {
    out_dir.join("oracle-cache.json")
}

fn cached_oracle(out_dir: &Path) -> Option<(PathBuf, String)> {
    let raw = fs::read_to_string(oracle_cache_path(out_dir)).ok()?;
    let doc: serde_json::Value = serde_json::from_str(&raw).ok()?;
    let dir = PathBuf::from(doc.get("render_dir")?.as_str()?);
    let recorded = doc.get("staged_input_digest")?.as_str()?.to_string();
    let current = staged_digest(&dir.join("request.json")).ok()?;
    (current == recorded && dir.join("en/reader.pdf").exists()).then_some((dir, recorded))
}

fn store_oracle(out_dir: &Path, dir: &Path, digest: &str) -> Result<()> {
    let doc = serde_json::json!({
        "render_dir": dir.to_string_lossy(),
        "staged_input_digest": digest,
    });
    fs::write(
        oracle_cache_path(out_dir),
        serde_json::to_string_pretty(&doc)? + "\n",
    )?;
    Ok(())
}

fn stage_legs(edition: &str, opts: &Options, out_dir: &Path) -> Result<Legs> {
    if let Some((dir_a, dir_b)) = &opts.pre_rendered {
        return Ok(Legs {
            dir_a: dir_a.clone(),
            dir_b: dir_b.clone(),
            mode: "pre_rendered",
            digest: None,
            typst_leg: None,
        });
    }
    let run = opts.run_dir.as_deref();
    let (oracle, digest) = match cached_oracle(out_dir) {
        Some(hit) => {
            println!("oracle leg: cached {}", hit.0.display());
            hit
        }
        None => {
            let dir = render_leg(edition, run, "weasyprint")?;
            let digest = staged_digest(&dir.join("request.json"))?;
            store_oracle(out_dir, &dir, &digest)?;
            (dir, digest)
        }
    };
    if opts.oracle_only {
        return Ok(Legs {
            dir_a: oracle.clone(),
            dir_b: oracle,
            mode: "oracle_only",
            digest: Some(digest),
            typst_leg: None,
        });
    }
    match render_leg(edition, run, "typst") {
        Ok(typst) => {
            let after = staged_digest(&typst.join("request.json"))?;
            anyhow::ensure!(
                after == digest,
                "staged inputs changed between the two legs: {digest} then {after}; re-run"
            );
            Ok(Legs {
                dir_a: oracle,
                dir_b: typst,
                mode: "render",
                digest: Some(digest),
                typst_leg: None,
            })
        }
        Err(e) => Ok(Legs {
            dir_a: oracle.clone(),
            dir_b: oracle,
            mode: "typst_leg_failed",
            digest: Some(digest),
            typst_leg: Some(LegFailure {
                status: "fail".into(),
                engine: "typst".into(),
                error: format!("{e:#}"),
            }),
        }),
    }
}

pub fn run(edition: &str, opts: Options) -> Result<i32> {
    let spec = spec()?;
    assert_poppler(&spec)?;
    assert_tracer(&spec)?;
    let out_dir = PathBuf::from("output/parity").join(edition);
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    let legs = stage_legs(edition, &opts, &out_dir)?;
    let (dir_a, dir_b) = (legs.dir_a, legs.dir_b);
    let (pdf_a, pdf_b) = (dir_a.join("en/reader.pdf"), dir_b.join("en/reader.pdf"));
    if let Some(failure) = &legs.typst_leg {
        println!("typst leg: {} ({})", failure.status, failure.error);
    }
    let mut inputs = BTreeMap::new();
    inputs.insert("a_reader_sha256".into(), sha256_file(&pdf_a)?);
    inputs.insert("b_reader_sha256".into(), sha256_file(&pdf_b)?);
    let mut verdict = build_verdict(&spec, edition, inputs, &pdf_a, &pdf_b, &out_dir)?;
    verdict.mode = legs.mode.into();
    verdict.typst_leg = legs.typst_leg;
    if let Some(digest) = legs.digest {
        let guard = staleness(&digest)?;
        let fresh = guard.status != "stale";
        verdict.staged_input_digest = Some(digest);
        verdict.staleness = Some(guard);
        if fresh {
            let manifest = dir_a.join("en/edition-manifest.json");
            let texts =
                text::page_texts(&pdf_a, verdict.domain.first_page, verdict.domain.last_page)?;
            let code = code_pages(
                &dir_a.join("request.json"),
                &texts,
                verdict.domain.first_page,
            )?;
            verdict.page_sets = Some(page_sets(
                &manifest,
                verdict.domain.first_page,
                verdict.domain.last_page,
                code,
            )?);
            if let Some(name) = &opts.set {
                verdict.scored_set = Some(score_set(&verdict, name)?);
            }
        } else if opts.set.is_some() {
            anyhow::bail!(
                "staged inputs differ from the baseline digest: page-set scoring and ratchet comparison are refused until a verifier rebases baseline.json from a fresh run"
            );
        }
    }
    write_verdict(&out_dir, &verdict)?;
    summarize(&verdict);
    let value = serde_json::to_value(&verdict)?;
    let domain = verdict
        .tier_g
        .is_some()
        .then_some((verdict.domain.first_page, verdict.domain.last_page));
    let g2 = spec_f64(&spec, &["tiers", "g", "g2_pt"])?;
    let report = report::write(
        &out_dir,
        &value,
        domain.map(|_| (&*pdf_a, &*pdf_b)),
        domain,
        g2,
    )?;
    println!("report: {}", report.display());
    Ok(i32::from(!all_evaluated_pass(&verdict)))
}

fn build_verdict(
    spec: &serde_yaml::Value,
    edition: &str,
    inputs: BTreeMap<String, String>,
    pdf_a: &Path,
    pdf_b: &Path,
    out_dir: &Path,
) -> Result<Verdict> {
    let (na, nb) = (geometry::page_count(pdf_a)?, geometry::page_count(pdf_b)?);
    let counts_equal = na == nb && na >= 3;
    let (first, last) = (2, na.saturating_sub(1));
    let mut verdict = Verdict {
        edition: edition.into(),
        mode: "pre_rendered".into(),
        staged_input_digest: None,
        staleness: None,
        typst_leg: None,
        page_sets: None,
        scored_set: None,
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
            color: None,
            navigation: None,
            critic: not_evaluated("WP-2.0b oracle leg, WP-5.3g typst leg"),
        },
        tier_g: None,
        tier_v: None,
        tier_e: TierE {
            display_list: None,
            glyph_positions: None,
            raster: None,
        },
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
    let map = font_name_map(spec)?;
    let dump_a = display::extract(pdf_a, first, last, &map)?;
    let dump_b = display::extract(pdf_b, first, last, &map)?;
    verdict.tier_s.color = Some(display::compare_color(&dump_a, &dump_b, first));
    verdict.tier_s.navigation = Some(display::compare_navigation(&dump_a, &dump_b, first));
    verdict.tier_e.display_list = Some(display::compare_display(&dump_a, &dump_b, first)?);
    verdict.tier_e.glyph_positions = Some(display::compare_glyphs(&dump_a, &dump_b, first));
    let vspec = raster::VSpec {
        dpi: spec_f64(spec, &["tiers", "v", "dpi"])? as u32,
        channel_delta: spec_f64(spec, &["tiers", "v", "channel_delta"])? as u8,
        v1_page_fraction: spec_f64(spec, &["tiers", "v", "v1_page_fraction"])?,
        v2_page_fraction: spec_f64(spec, &["tiers", "v", "v2_page_fraction"])?,
    };
    let bound = raster_bound(spec)?;
    let heatmap_dir = out_dir.join("report");
    fs::create_dir_all(&heatmap_dir)?;
    let (tier_v, guard) = raster::compare(pdf_a, pdf_b, first, last, &vspec, bound, &heatmap_dir)?;
    verdict.tier_v = Some(tier_v);
    verdict.tier_e.raster = Some(guard);
    Ok(verdict)
}

fn raster_bound(spec: &serde_yaml::Value) -> Result<Option<u8>> {
    let node = spec
        .get("tiers")
        .and_then(|t| t.get("e"))
        .and_then(|e| e.get("raster_bound"))
        .context("parity.yaml tiers.e.raster_bound missing")?;
    match node.get("value") {
        None => Ok(None),
        Some(v) => Ok(Some(
            u8::try_from(v.as_u64().context("raster_bound.value not an integer")?)
                .context("raster_bound.value out of range")?,
        )),
    }
}

fn all_evaluated_pass(v: &Verdict) -> bool {
    v.typst_leg.is_none()
        && v.tier_s.page_count.status == "pass"
        && v.tier_s.boxes.as_ref().is_some_and(|c| c.status == "pass")
        && v.tier_s.text.as_ref().is_some_and(|c| c.status == "pass")
        && v.tier_s.color.as_ref().is_some_and(|c| c.status == "pass")
        && v.tier_s
            .navigation
            .as_ref()
            .is_some_and(|c| c.status == "pass")
        && v.tier_e
            .display_list
            .as_ref()
            .is_some_and(|c| c.status == "pass")
        && v.tier_e
            .glyph_positions
            .as_ref()
            .is_some_and(|c| c.status == "pass")
        && v.tier_v.as_ref().is_some_and(|r| r.status == "pass")
        && !matches!(
            v.tier_e.raster,
            Some(raster::RasterGuard::Evaluated { ref status, .. }) if status == "fail"
        )
}

fn write_verdict(dir: &Path, verdict: &Verdict) -> Result<()> {
    let path = dir.join("verdict.json");
    let json = serde_json::to_string_pretty(verdict)? + "\n";
    fs::write(&path, json).with_context(|| format!("writing {}", path.display()))?;
    println!("verdict: {}", path.display());
    Ok(())
}

fn summarize(v: &Verdict) {
    if let Some(s) = &v.staleness {
        println!("staged inputs: {} ({})", s.status, s.current);
    }
    if let Some(sets) = &v.page_sets {
        let counts: Vec<String> = sets
            .iter()
            .map(|(name, pages)| format!("{name} {}", pages.len()))
            .collect();
        println!("page sets: {}", counts.join(", "));
    }
    if let Some(scored) = &v.scored_set {
        println!(
            "scored set {}: {} pages, {} clauses differing",
            scored.name,
            scored.pages.len(),
            scored.clauses_differing.len()
        );
    }
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
    if let Some(c) = &v.tier_s.color {
        println!(
            "tier S color: {} ({} pages differ)",
            c.status,
            c.pages_differing.len()
        );
    }
    if let Some(n) = &v.tier_s.navigation {
        println!(
            "tier S navigation: {} ({} mismatches)",
            n.status,
            n.mismatches.len()
        );
    }
    if let Some(g) = &v.tier_e.glyph_positions {
        println!(
            "tier E glyph positions: {} ({} glyphs, {} shows, worst excess {:.6} pt, worst ratio {:.4}, {} violations)",
            g.status,
            g.glyphs,
            g.shows,
            g.worst_excess_pt,
            g.worst_ratio,
            g.violations.len()
        );
    }
    if let Some(d) = &v.tier_e.display_list {
        println!(
            "tier E display list: {} ({} pages differ)",
            d.status,
            d.pages_differing.len()
        );
    }
    if let Some(r) = &v.tier_v {
        println!(
            "tier V: dims {} (mismatches {}), V1 {}, V2 {}, worst page fraction {:.6}, max channel delta {}",
            r.status,
            r.dimension_mismatches.len(),
            r.v1,
            r.v2,
            r.worst_page_fraction,
            r.max_channel_delta
        );
    }
    match &v.tier_e.raster {
        Some(raster::RasterGuard::Evaluated {
            status,
            bound,
            pages_beyond,
        }) => println!(
            "tier E raster: {status} (bound {bound}, {} pages beyond)",
            pages_beyond.len()
        ),
        Some(raster::RasterGuard::NotEvaluated { owner, .. }) => {
            println!("tier E raster: not_evaluated ({owner})");
        }
        None => {}
    }
}
