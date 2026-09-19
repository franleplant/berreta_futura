mod display;
mod geometry;
mod raster;
mod report;
mod streams;
mod text;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use streams::Face;

pub(crate) use display::trace_elements;
#[allow(unused_imports)]
pub(crate) use streams::Color;
pub(crate) use streams::{Element, Face as TextFace, GLYPH_QUANTUM};

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
    staleness: Staleness,
    #[serde(skip_serializing_if = "Option::is_none")]
    typst_leg: Option<LegFailure>,
    #[serde(skip_serializing_if = "Option::is_none")]
    page_sets: Option<BTreeMap<String, Vec<u32>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    scored_set: Option<ScoredSet>,
    ratchet: Ratchet,
    self_comparison: bool,
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
    current: Option<String>,
    baseline: Option<String>,
}

fn not_staged() -> Staleness {
    Staleness {
        status: "not_staged".into(),
        current: None,
        baseline: None,
    }
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

#[derive(Serialize)]
struct Ratchet {
    status: String,
    committed_check: String,
    pages_committed: usize,
    pages_recorded: usize,
    pages_measured: usize,
    regressions: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, PartialEq, Eq, Debug)]
struct PageEntry {
    tier: String,
    s_clauses_passing: Vec<String>,
}

const BASELINE_PATH: &str = "meta/verification/baseline.json";
const TIER_LADDER: [&str; 6] = ["none", "G1", "G2", "V1", "V2", "E"];
const S_CLAUSES: [&str; 7] = [
    "page_count",
    "boxes",
    "text",
    "code_blocks",
    "color",
    "navigation",
    "critic",
];

fn baseline_path() -> PathBuf {
    std::env::var_os("MAG_PARITY_BASELINE")
        .map_or_else(|| PathBuf::from(BASELINE_PATH), PathBuf::from)
}

fn tier_rank(tier: &str) -> Result<usize> {
    TIER_LADDER
        .iter()
        .position(|t| *t == tier)
        .with_context(|| format!("unknown baseline tier '{tier}': expected one of {TIER_LADDER:?}"))
}

fn parse_entries(raw: &str, origin: &str) -> Result<BTreeMap<u32, PageEntry>> {
    let doc: serde_json::Value =
        serde_json::from_str(raw).with_context(|| format!("parsing {origin}"))?;
    let pages = doc
        .get("pages")
        .and_then(|p| p.as_object())
        .with_context(|| format!("{origin} has no pages object"))?;
    let mut out = BTreeMap::new();
    for (key, value) in pages {
        let page: u32 = key
            .parse()
            .with_context(|| format!("{origin} page key '{key}' is not a page number"))?;
        let entry: PageEntry = serde_json::from_value(value.clone())
            .with_context(|| format!("{origin} page {page} does not match page_entry_shape"))?;
        tier_rank(&entry.tier).with_context(|| format!("{origin} page {page}"))?;
        for clause in &entry.s_clauses_passing {
            anyhow::ensure!(
                S_CLAUSES.contains(&clause.as_str()),
                "{origin} page {page} names unknown Tier S clause '{clause}': expected one of {S_CLAUSES:?}"
            );
        }
        out.insert(page, entry);
    }
    Ok(out)
}

fn read_entries(path: &Path) -> Result<BTreeMap<u32, PageEntry>> {
    if !path.exists() {
        return Ok(BTreeMap::new());
    }
    let raw = fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
    parse_entries(&raw, &path.display().to_string())
}

fn committed_entries() -> (Option<BTreeMap<u32, PageEntry>>, String) {
    let out = Command::new("git")
        .args(["show", &format!("HEAD:{BASELINE_PATH}")])
        .output();
    match out {
        Ok(o) if o.status.success() => {
            match parse_entries(&String::from_utf8_lossy(&o.stdout), "HEAD:baseline.json") {
                Ok(entries) => (Some(entries), "checked".into()),
                Err(e) => (None, format!("unavailable: {e}")),
            }
        }
        _ => (
            None,
            "unavailable: git show HEAD:baseline.json failed".into(),
        ),
    }
}

fn regressions(
    have: &BTreeMap<u32, PageEntry>,
    want: &BTreeMap<u32, PageEntry>,
) -> Result<Vec<String>> {
    let mut out = Vec::new();
    for (page, wanted) in want {
        let Some(held) = have.get(page) else {
            out.push(format!("page {page}: entry removed (was {})", wanted.tier));
            continue;
        };
        if tier_rank(&held.tier)? < tier_rank(&wanted.tier)? {
            out.push(format!(
                "page {page}: tier lowered from {} to {}",
                wanted.tier, held.tier
            ));
        }
        let lost: Vec<&str> = wanted
            .s_clauses_passing
            .iter()
            .filter(|c| !held.s_clauses_passing.contains(c))
            .map(String::as_str)
            .collect();
        if !lost.is_empty() {
            out.push(format!(
                "page {page}: Tier S clauses dropped: {}",
                lost.join(", ")
            ));
        }
    }
    Ok(out)
}

fn raised(
    have: &BTreeMap<u32, PageEntry>,
    want: &BTreeMap<u32, PageEntry>,
) -> BTreeMap<u32, PageEntry> {
    let mut merged = want.clone();
    for (page, held) in have {
        let entry = merged.entry(*page).or_insert_with(|| held.clone());
        if tier_rank(&held.tier).unwrap_or(0) > tier_rank(&entry.tier).unwrap_or(0) {
            entry.tier.clone_from(&held.tier);
        }
        for clause in &held.s_clauses_passing {
            if !entry.s_clauses_passing.contains(clause) {
                entry.s_clauses_passing.push(clause.clone());
            }
        }
        entry.s_clauses_passing.sort_by_key(|c| {
            S_CLAUSES
                .iter()
                .position(|s| s == c)
                .unwrap_or(S_CLAUSES.len())
        });
    }
    merged
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
    let path = baseline_path();
    if !path.exists() {
        return Ok(None);
    }
    let raw = fs::read_to_string(&path)?;
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
        current: Some(current.to_string()),
        baseline,
    })
}

fn page_clauses(v: &Verdict, page: u32) -> Vec<String> {
    let mut out = vec!["page_count".to_string()];
    let boxes = v.tier_s.boxes.as_ref().is_some_and(|c| {
        !c.mismatches.iter().any(|m| m.page == page)
            && !c.rotation_mismatches.iter().any(|m| m.page == page)
    });
    let text = v
        .tier_s
        .text
        .as_ref()
        .is_some_and(|c| !c.pages_differing.contains(&page));
    let color = v
        .tier_s
        .color
        .as_ref()
        .is_some_and(|c| !c.pages_differing.contains(&page));
    let nav = v
        .tier_s
        .navigation
        .as_ref()
        .is_some_and(|c| c.status == "pass");
    for (name, pass) in [
        ("boxes", boxes),
        ("text", text),
        ("color", color),
        ("navigation", nav),
    ] {
        if pass {
            out.push(name.to_string());
        }
    }
    out.sort_by_key(|c| {
        S_CLAUSES
            .iter()
            .position(|s| s == c)
            .unwrap_or(S_CLAUSES.len())
    });
    out
}

fn page_tier(v: &Verdict, page: u32, g1: f64, g2: f64, v1: f64, v2: f64) -> &'static str {
    let geom = v.tier_g.as_ref().and_then(|t| t.pages.get(&page));
    let within = |limit: f64| {
        geom.is_some_and(|g| {
            g.blocks_a == g.blocks_b
                && g.line_count_mismatches == 0
                && g.max_dx_pt <= limit
                && g.max_dy_pt <= limit
        })
    };
    let raster = v.tier_v.as_ref().and_then(|t| t.pages.get(&page));
    let under = |limit: f64| raster.is_some_and(|r| r.differing_fraction < limit);
    let exact = v
        .tier_e
        .display_list
        .as_ref()
        .is_some_and(|c| !c.pages_differing.iter().any(|d| d.page == page))
        && v.tier_e
            .glyph_positions
            .as_ref()
            .is_some_and(|c| c.status == "pass");
    ladder([within(g1), within(g2), under(v1), under(v2), exact])
}

fn ladder(rungs: [bool; 5]) -> &'static str {
    TIER_LADDER[rungs.iter().take_while(|r| **r).count()]
}

fn measure_pages(
    v: &Verdict,
    spec: &serde_yaml::Value,
) -> Result<Option<BTreeMap<u32, PageEntry>>> {
    if v.self_comparison
        || v.tier_s.page_count.status != "pass"
        || v.tier_g.is_none()
        || v.tier_v.is_none()
    {
        return Ok(None);
    }
    let (g1, g2) = (
        spec_f64(spec, &["tiers", "g", "g1_pt"])?,
        spec_f64(spec, &["tiers", "g", "g2_pt"])?,
    );
    let (v1, v2) = (
        spec_f64(spec, &["tiers", "v", "v1_page_fraction"])?,
        spec_f64(spec, &["tiers", "v", "v2_page_fraction"])?,
    );
    let entries = (v.domain.first_page..=v.domain.last_page)
        .map(|page| {
            (
                page,
                PageEntry {
                    tier: page_tier(v, page, g1, g2, v1, v2).to_string(),
                    s_clauses_passing: page_clauses(v, page),
                },
            )
        })
        .collect();
    Ok(Some(entries))
}

fn write_proposal(
    out_dir: &Path,
    entries: &BTreeMap<u32, PageEntry>,
    digest: &str,
) -> Result<PathBuf> {
    let path = out_dir.join("baseline-proposed.json");
    let mut doc: serde_json::Value = match fs::read_to_string(baseline_path()) {
        Ok(raw) => serde_json::from_str(&raw)?,
        Err(_) => serde_json::json!({}),
    };
    let pages: serde_json::Map<String, serde_json::Value> = entries
        .iter()
        .map(|(page, entry)| Ok((page.to_string(), serde_json::to_value(entry)?)))
        .collect::<Result<_>>()?;
    doc["staged_input_digest"] = serde_json::Value::String(digest.to_string());
    doc["pages"] = serde_json::Value::Object(pages);
    fs::write(&path, serde_json::to_string_pretty(&doc)? + "\n")
        .with_context(|| format!("writing {}", path.display()))?;
    Ok(path)
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

fn out_dir(edition: &str) -> PathBuf {
    std::env::var_os("MAG_PARITY_OUT_DIR").map_or_else(
        || PathBuf::from("output/parity").join(edition),
        PathBuf::from,
    )
}

fn hold(out_dir: &Path) -> Result<PathBuf> {
    let path = out_dir.join("run.lock");
    match fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&path)
    {
        Ok(_) => Ok(path),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => anyhow::bail!(
            "another mag parity run holds {}; concurrent runs sharing one output directory overwrite each other's verdict.json. Give this run its own directory with MAG_PARITY_OUT_DIR, or delete the lock file if no such run is alive",
            path.display()
        ),
        Err(e) => Err(e).with_context(|| format!("creating {}", path.display())),
    }
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

fn guard_baseline() -> Result<(BTreeMap<u32, PageEntry>, Ratchet)> {
    let working = read_entries(&baseline_path())?;
    let (committed, committed_check) = committed_entries();
    let pages_committed = committed.as_ref().map_or(0, BTreeMap::len);
    if let Some(committed) = &committed {
        let lowered = regressions(&working, committed)?;
        anyhow::ensure!(
            lowered.is_empty(),
            "{} lowers {} committed baseline entries, which only a verifier may change:\n  {}",
            baseline_path().display(),
            lowered.len(),
            lowered.join("\n  ")
        );
    }
    Ok((
        working.clone(),
        Ratchet {
            status: "not_evaluated".into(),
            committed_check,
            pages_committed,
            pages_recorded: working.len(),
            pages_measured: 0,
            regressions: vec![],
        },
    ))
}

pub fn run(edition: &str, opts: Options) -> Result<i32> {
    let spec = spec()?;
    assert_poppler(&spec)?;
    assert_tracer(&spec)?;
    let (recorded, ratchet) = guard_baseline()?;
    let out_dir = out_dir(edition);
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    let lock = hold(&out_dir)?;
    let outcome = compare(edition, &opts, &spec, &out_dir, &recorded, ratchet);
    fs::remove_file(&lock).with_context(|| format!("releasing {}", lock.display()))?;
    outcome
}

fn compare(
    edition: &str,
    opts: &Options,
    spec: &serde_yaml::Value,
    out_dir: &Path,
    recorded: &BTreeMap<u32, PageEntry>,
    ratchet: Ratchet,
) -> Result<i32> {
    let legs = stage_legs(edition, opts, out_dir)?;
    if let Some(digest) = &legs.digest {
        let guard = staleness(digest)?;
        anyhow::ensure!(
            guard.status != "stale",
            "staged inputs differ from the baseline digest (run {}, baseline {}): the comparator refuses to run on a corpus the baseline cannot vouch for. A verifier rebases baseline.json from a fresh run",
            guard.current.unwrap_or_default(),
            guard.baseline.unwrap_or_default()
        );
    }
    let (dir_a, dir_b) = (legs.dir_a, legs.dir_b);
    let (pdf_a, pdf_b) = (dir_a.join("en/reader.pdf"), dir_b.join("en/reader.pdf"));
    if let Some(failure) = &legs.typst_leg {
        println!("typst leg: {} ({})", failure.status, failure.error);
    }
    let mut inputs = BTreeMap::new();
    inputs.insert("a_reader_sha256".into(), sha256_file(&pdf_a)?);
    inputs.insert("b_reader_sha256".into(), sha256_file(&pdf_b)?);
    let mut verdict = build_verdict(spec, edition, inputs, &pdf_a, &pdf_b, out_dir)?;
    verdict.mode = legs.mode.into();
    verdict.typst_leg = legs.typst_leg;
    verdict.ratchet = ratchet;
    if let Some(digest) = legs.digest {
        let guard = staleness(&digest)?;
        let unseeded = guard.status == "unseeded";
        verdict.staged_input_digest = Some(digest.clone());
        verdict.staleness = guard;
        let manifest = dir_a.join("en/edition-manifest.json");
        let texts = text::page_texts(&pdf_a, verdict.domain.first_page, verdict.domain.last_page)?;
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
        let measured = measure_pages(&verdict, spec)?;
        if let Some(measured) = &measured {
            verdict.ratchet.pages_measured = measured.len();
            verdict.ratchet.regressions = regressions(measured, recorded)?;
            let proposal = write_proposal(out_dir, &raised(measured, recorded), &digest)?;
            println!("proposed baseline: {}", proposal.display());
        }
        verdict.ratchet.status = match (&measured, unseeded) {
            (_, true) => "unseeded",
            (None, _) if verdict.self_comparison => "self_comparison",
            (None, _) => "not_measured",
            (Some(_), _) if verdict.ratchet.regressions.is_empty() => "pass",
            (Some(_), _) => "fail",
        }
        .into();
    }
    write_verdict(out_dir, &verdict)?;
    summarize(&verdict);
    let value = serde_json::to_value(&verdict)?;
    let domain = verdict
        .tier_g
        .is_some()
        .then_some((verdict.domain.first_page, verdict.domain.last_page));
    let g2 = spec_f64(spec, &["tiers", "g", "g2_pt"])?;
    let report = report::write(
        out_dir,
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
        staleness: not_staged(),
        typst_leg: None,
        page_sets: None,
        scored_set: None,
        ratchet: Ratchet {
            status: "not_evaluated".into(),
            committed_check: "not_evaluated".into(),
            pages_committed: 0,
            pages_recorded: 0,
            pages_measured: 0,
            regressions: vec![],
        },
        self_comparison: inputs.get("a_reader_sha256") == inputs.get("b_reader_sha256"),
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
    let Some(node) = spec
        .get("tiers")
        .and_then(|t| t.get("e"))
        .and_then(|e| e.get("raster_bound"))
    else {
        return Ok(None);
    };
    match node.get("value") {
        None => Ok(None),
        Some(v) => Ok(Some(
            u8::try_from(v.as_u64().context("raster_bound.value not an integer")?)
                .context("raster_bound.value out of range")?,
        )),
    }
}

fn all_evaluated_pass(v: &Verdict) -> bool {
    matches!(
        v.ratchet.status.as_str(),
        "pass" | "not_evaluated" | "self_comparison"
    ) && v.typst_leg.is_none()
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

fn summarize_run(v: &Verdict) {
    println!("mode: {}", v.mode);
    if v.self_comparison {
        let note = if v.mode == "oracle_only" {
            "deliberate for this mode"
        } else {
            "WARNING: both sides are the same bytes, so no engine comparison happened"
        };
        println!("self-comparison: both legs hash identically ({note})");
    }
    println!(
        "staged inputs: {} ({})",
        v.staleness.status,
        v.staleness.current.as_deref().unwrap_or(
            "the comparator did not stage these inputs, so no digest exists and the baseline vouches for nothing"
        )
    );
    if let Some(sets) = &v.page_sets {
        let counts: Vec<String> = sets
            .iter()
            .map(|(name, pages)| format!("{name} {}", pages.len()))
            .collect();
        println!("page sets: {}", counts.join(", "));
    }
    let r = &v.ratchet;
    println!(
        "ratchet: {} ({} committed entries {}, {} recorded, {} measured, {} regressions)",
        r.status,
        r.pages_committed,
        r.committed_check,
        r.pages_recorded,
        r.pages_measured,
        r.regressions.len()
    );
    for line in &r.regressions {
        println!("  regression: {line}");
    }
    if let Some(scored) = &v.scored_set {
        println!(
            "scored set {}: {} pages, {} clauses differing",
            scored.name,
            scored.pages.len(),
            scored.clauses_differing.len()
        );
    }
}

fn summarize(v: &Verdict) {
    summarize_run(v);
    println!(
        "tier S page_count: {} ({} vs {})",
        v.tier_s.page_count.status, v.tier_s.page_count.a, v.tier_s.page_count.b
    );
    if let Some(b) = &v.tier_s.boxes {
        println!(
            "tier S boxes: {} ({} boxes, {} rotations compared; {} box, {} rotation mismatches)",
            b.status,
            b.boxes_compared,
            b.rotations_compared,
            b.mismatches.len(),
            b.rotation_mismatches.len()
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
            "tier S color: {} ({} entries compared, {} pages differ)",
            c.status,
            c.entries_compared,
            c.pages_differing.len()
        );
    }
    if let Some(n) = &v.tier_s.navigation {
        println!(
            "tier S navigation: {} ({} annotations of which {} links, {} outlines, {} title, {} lang compared; {} mismatches)",
            n.status,
            n.annots_compared,
            n.links_compared,
            n.outlines_compared,
            n.title_compared,
            n.lang_compared,
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

#[cfg(test)]
mod measured_pages {
    use super::*;

    fn thresholds() -> serde_yaml::Value {
        serde_yaml::from_str(
            "tiers:\n  g:\n    g1_pt: 2.0\n    g2_pt: 0.5\n  v:\n    v1_page_fraction: 0.01\n    v2_page_fraction: 0.001\n",
        )
        .expect("thresholds")
    }

    fn tier_s() -> TierS {
        TierS {
            page_count: PageCount {
                status: "pass".into(),
                a: 4,
                b: 4,
            },
            boxes: Some(geometry::BoxClause {
                status: "pass".into(),
                tolerance_pt: 0.05,
                boxes_compared: 6,
                rotations_compared: 2,
                mismatches: vec![],
                rotation_mismatches: vec![],
            }),
            text: Some(text::TextClause {
                status: "pass".into(),
                pages_differing: vec![],
            }),
            code_blocks: not_evaluated("test"),
            color: Some(display::SimpleClause {
                status: "pass".into(),
                entries_compared: 10,
                pages_differing: vec![],
            }),
            navigation: Some(display::NavClause {
                status: "pass".into(),
                annots_compared: 0,
                links_compared: 0,
                outlines_compared: 0,
                title_compared: 0,
                lang_compared: 0,
                mismatches: vec![],
            }),
            critic: not_evaluated("test"),
        }
    }

    fn meters() -> (geometry::GeomTier, raster::RasterTier) {
        let mut pages = BTreeMap::new();
        let mut rasters = BTreeMap::new();
        for page in 2..=3 {
            pages.insert(
                page,
                geometry::PageGeom {
                    blocks_a: 4,
                    blocks_b: 4,
                    line_count_mismatches: 0,
                    max_dx_pt: 0.0,
                    max_dy_pt: 0.0,
                },
            );
            rasters.insert(
                page,
                raster::PageRaster {
                    differing_fraction: 0.0,
                    max_channel_delta: 0,
                },
            );
        }
        (
            geometry::GeomTier {
                g1_pt: 2.0,
                g2_pt: 0.5,
                pages,
                max_dx_pt: 0.0,
                max_dy_pt: 0.0,
                lines_beyond_g1: 0,
                lines_beyond_g2: 0,
                block_or_line_count_mismatches: 0,
            },
            raster::RasterTier {
                status: "pass".into(),
                dpi: 300,
                channel_delta: 24,
                v1: "pass".into(),
                v2: "pass".into(),
                worst_page_fraction: 0.0,
                max_channel_delta: 0,
                dimension_mismatches: vec![],
                pages: rasters,
            },
        )
    }

    fn verdict() -> Verdict {
        let (tier_g, tier_v) = meters();
        Verdict {
            edition: "010".into(),
            mode: "render".into(),
            staged_input_digest: None,
            staleness: not_staged(),
            typst_leg: None,
            page_sets: None,
            scored_set: None,
            ratchet: Ratchet {
                status: "not_evaluated".into(),
                committed_check: "not_evaluated".into(),
                pages_committed: 0,
                pages_recorded: 0,
                pages_measured: 0,
                regressions: vec![],
            },
            self_comparison: false,
            inputs: BTreeMap::new(),
            domain: Domain {
                description: "test".into(),
                first_page: 2,
                last_page: 3,
            },
            tier_s: tier_s(),
            tier_g: Some(tier_g),
            tier_v: Some(tier_v),
            tier_e: TierE {
                display_list: Some(display::DisplayClause {
                    status: "pass".into(),
                    elements_a: 10,
                    elements_b: 10,
                    pages_differing: vec![],
                }),
                glyph_positions: Some(display::GlyphClause {
                    status: "pass".into(),
                    glyphs: 100,
                    shows: 4,
                    worst_excess_pt: 0.0,
                    worst_ratio: 0.0,
                    worst: None,
                    violations: vec![],
                }),
                raster: None,
            },
        }
    }

    fn measured(v: &Verdict) -> BTreeMap<u32, PageEntry> {
        measure_pages(v, &thresholds())
            .expect("thresholds")
            .expect("measurable")
    }

    #[test]
    fn an_equal_pair_records_every_page_at_tier_e_with_every_evaluated_clause() {
        let entries = measured(&verdict());
        assert_eq!(entries.len(), 2);
        for page in [2, 3] {
            assert_eq!(entries[&page].tier, "E");
            assert_eq!(
                entries[&page].s_clauses_passing,
                vec![
                    "page_count".to_string(),
                    "boxes".into(),
                    "text".into(),
                    "color".into(),
                    "navigation".into()
                ]
            );
        }
    }

    #[test]
    fn each_perturbation_lands_on_the_page_it_touches_and_lowers_only_what_it_should() {
        let mut v = verdict();
        v.tier_e
            .display_list
            .as_mut()
            .expect("clause")
            .pages_differing = vec![display::PageDiff {
            page: 3,
            detail: "seeded".into(),
        }];
        let entries = measured(&v);
        assert_eq!(
            (entries[&2].tier.as_str(), entries[&3].tier.as_str()),
            ("E", "V2")
        );

        let mut v = verdict();
        v.tier_s.text.as_mut().expect("clause").pages_differing = vec![3];
        let entries = measured(&v);
        assert!(entries[&2].s_clauses_passing.contains(&"text".to_string()));
        assert!(!entries[&3].s_clauses_passing.contains(&"text".to_string()));
        assert_eq!(entries[&3].tier, "E");

        let mut v = verdict();
        v.tier_v
            .as_mut()
            .expect("tier")
            .pages
            .get_mut(&3)
            .expect("page")
            .differing_fraction = 0.005;
        let entries = measured(&v);
        assert_eq!(
            (entries[&2].tier.as_str(), entries[&3].tier.as_str()),
            ("E", "V1")
        );

        let mut v = verdict();
        v.tier_g
            .as_mut()
            .expect("tier")
            .pages
            .get_mut(&3)
            .expect("page")
            .max_dy_pt = 1.0;
        let entries = measured(&v);
        assert_eq!(
            (entries[&2].tier.as_str(), entries[&3].tier.as_str()),
            ("E", "G1")
        );

        let mut v = verdict();
        v.tier_g
            .as_mut()
            .expect("tier")
            .pages
            .get_mut(&3)
            .expect("page")
            .line_count_mismatches = 1;
        let entries = measured(&v);
        assert_eq!(
            (entries[&2].tier.as_str(), entries[&3].tier.as_str()),
            ("E", "none")
        );

        let mut v = verdict();
        v.tier_s.navigation.as_mut().expect("clause").status = "fail".into();
        let entries = measured(&v);
        for page in [2, 3] {
            assert!(!entries[&page]
                .s_clauses_passing
                .contains(&"navigation".to_string()));
        }

        let mut v = verdict();
        v.tier_e.glyph_positions.as_mut().expect("clause").status = "fail".into();
        let entries = measured(&v);
        for page in [2, 3] {
            assert_eq!(entries[&page].tier, "V2");
        }
    }

    #[test]
    fn a_self_comparison_measures_nothing_so_no_baseline_can_be_seeded_from_one() {
        let mut v = verdict();
        v.self_comparison = true;
        assert!(measure_pages(&v, &thresholds())
            .expect("thresholds")
            .is_none());
        v.self_comparison = false;
        v.tier_s.page_count.status = "fail".into();
        assert!(measure_pages(&v, &thresholds())
            .expect("thresholds")
            .is_none());
    }
}

#[cfg(test)]
mod ratchet_rules {
    use super::*;

    fn entry(tier: &str, clauses: &[&str]) -> PageEntry {
        PageEntry {
            tier: tier.into(),
            s_clauses_passing: clauses.iter().map(|c| (*c).to_string()).collect(),
        }
    }

    fn entries(rows: &[(u32, &str, &[&str])]) -> BTreeMap<u32, PageEntry> {
        rows.iter().map(|(p, t, c)| (*p, entry(t, c))).collect()
    }

    #[test]
    fn the_ladder_is_cumulative_so_a_skipped_rung_caps_the_tier() {
        assert_eq!(ladder([false, false, false, false, false]), "none");
        assert_eq!(ladder([true, false, false, false, false]), "G1");
        assert_eq!(ladder([true, true, false, false, false]), "G2");
        assert_eq!(ladder([true, true, true, false, false]), "V1");
        assert_eq!(ladder([true, true, true, true, false]), "V2");
        assert_eq!(ladder([true, true, true, true, true]), "E");
        assert_eq!(ladder([true, true, false, true, true]), "G2");
        assert_eq!(ladder([false, true, true, true, true]), "none");
    }

    #[test]
    fn an_unknown_tier_or_clause_name_fails_loud() {
        assert!(tier_rank("G3").is_err());
        assert!(tier_rank("E").is_ok());
        let bad_tier = r#"{"pages":{"2":{"tier":"G3","s_clauses_passing":[]}}}"#;
        assert!(parse_entries(bad_tier, "t").is_err());
        let bad_clause = r#"{"pages":{"2":{"tier":"E","s_clauses_passing":["glyphs"]}}}"#;
        let err = format!(
            "{:#}",
            parse_entries(bad_clause, "t").expect_err("must fail")
        );
        assert!(err.contains("unknown Tier S clause 'glyphs'"), "{err}");
        let bad_page = r#"{"pages":{"cover":{"tier":"E","s_clauses_passing":[]}}}"#;
        assert!(parse_entries(bad_page, "t").is_err());
        assert!(parse_entries(r#"{"staged_input_digest":null}"#, "t").is_err());
    }

    #[test]
    fn a_lower_tier_or_a_dropped_clause_is_a_regression_and_a_raise_is_not() {
        let committed = entries(&[(2, "E", &["page_count", "text"]), (3, "G2", &["text"])]);
        assert!(regressions(&committed, &committed)
            .expect("ranks")
            .is_empty());
        let raise = entries(&[
            (2, "E", &["page_count", "text", "color"]),
            (3, "V2", &["text"]),
        ]);
        assert!(regressions(&raise, &committed).expect("ranks").is_empty());
        let lower = entries(&[(2, "V2", &["page_count", "text"]), (3, "G2", &["text"])]);
        assert_eq!(
            regressions(&lower, &committed).expect("ranks"),
            vec!["page 2: tier lowered from E to V2".to_string()]
        );
        let dropped = entries(&[(2, "E", &["page_count"]), (3, "G2", &["text"])]);
        assert_eq!(
            regressions(&dropped, &committed).expect("ranks"),
            vec!["page 2: Tier S clauses dropped: text".to_string()]
        );
        let removed = entries(&[(3, "G2", &["text"])]);
        assert_eq!(
            regressions(&removed, &committed).expect("ranks"),
            vec!["page 2: entry removed (was E)".to_string()]
        );
    }

    #[test]
    fn a_proposal_merges_upward_only_and_keeps_pages_neither_side_has_alone() {
        let committed = entries(&[(2, "E", &["page_count", "text"]), (3, "G2", &["text"])]);
        let measured = entries(&[(2, "G1", &["color"]), (4, "V1", &["boxes"])]);
        let merged = raised(&measured, &committed);
        assert_eq!(merged[&2].tier, "E");
        assert_eq!(
            merged[&2].s_clauses_passing,
            vec!["page_count".to_string(), "text".into(), "color".into()]
        );
        assert_eq!(merged[&3].tier, "G2");
        assert_eq!(merged[&4].tier, "V1");
        assert!(regressions(&merged, &committed).expect("ranks").is_empty());
    }
}
