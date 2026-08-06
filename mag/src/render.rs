// Render seam: stages every file the Python renderer bridge needs, writes a
// magazine-renderer/1 request, then shells out to `uv run mag-render-adapter
// <request.json> <out>`. The bridge copies inputs into its own stage root and
// does the actual typesetting; this module's only job is to discover and
// validate the input set (walking edition.yaml, translations, and source
// record.yamls) and to report back what came out.

use crate::caller::{Caller, ModelSpec};
use anyhow::{anyhow, bail, Context, Result};
use serde::Serialize;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const OPERATIONS: [&str; 3] = ["measure_article", "measure_edition", "render_edition"];
const SCHEMA_VERSION: u32 = 1;
const RENDERER_CONTRACT_VERSION: &str = "magazine-renderer/1";
const RENDERER: &str = "weasyprint";
const DESIGN_TOML_PATH: &str = "design/covers/canto-vivo/design.toml";

#[derive(Serialize)]
struct InputRow {
    #[serde(rename = "artifactId")]
    artifact_id: String,
    #[serde(rename = "sourcePath")]
    source_path: String,
    #[serde(rename = "targetPath")]
    target_path: String,
}

#[derive(Serialize)]
struct Request {
    #[serde(rename = "schemaVersion")]
    schema_version: u32,
    #[serde(rename = "rendererContractVersion")]
    renderer_contract_version: String,
    operation: String,
    #[serde(rename = "articleId", skip_serializing_if = "Option::is_none")]
    article_id: Option<String>,
    #[serde(rename = "editionId")]
    edition_id: String,
    #[serde(rename = "primaryLanguage")]
    primary_language: String,
    languages: Vec<String>,
    #[serde(rename = "publicationName")]
    publication_name: String,
    renderer: String,
    #[serde(rename = "artifactRoot")]
    artifact_root: String,
    inputs: Vec<InputRow>,
}

/// Accumulates the staged-file set: dedupes by target path, and defers the
/// existence check to one place so every missing path is collected before we
/// fail loud.
struct Staging {
    repo_root: PathBuf,
    seen: HashSet<String>,
    rows: Vec<InputRow>,
    missing: Vec<String>,
}

impl Staging {
    fn new(repo_root: PathBuf) -> Self {
        Self { repo_root, seen: HashSet::new(), rows: Vec::new(), missing: Vec::new() }
    }

    /// `rel` is repo-root-relative. Existing files are added to the input
    /// set; missing ones are recorded (not staged) so the caller can still
    /// report every missing path at once.
    fn add(&mut self, rel: &Path) {
        let target = rel.to_string_lossy().replace('\\', "/");
        if !self.seen.insert(target.clone()) {
            return;
        }
        let abs = self.repo_root.join(rel);
        if !abs.exists() {
            self.missing.push(target);
            return;
        }
        self.rows.push(InputRow {
            artifact_id: target.clone(),
            source_path: abs.to_string_lossy().to_string(),
            target_path: target,
        });
    }

    /// Stage `source` (repo-root-relative) at the tree position `target`
    /// declares — how a run's final.md lands on the path edition.yaml names.
    fn add_mapped(&mut self, source: &Path, target: &Path) {
        let target = target.to_string_lossy().replace('\\', "/");
        if !self.seen.insert(target.clone()) {
            return;
        }
        let abs = self.repo_root.join(source);
        if !abs.exists() {
            self.missing.push(format!("{} (for {})", source.display(), target));
            return;
        }
        self.rows.push(InputRow {
            artifact_id: target.clone(),
            source_path: abs.to_string_lossy().to_string(),
            target_path: target,
        });
    }
}

/// `## ` headings in a manuscript, which is what a figure anchor must match.
fn manuscript_headings(path: &Path) -> Vec<String> {
    fs::read_to_string(path)
        .map(|t| {
            t.lines()
                .filter_map(|l| l.strip_prefix("## ").map(|h| h.trim().to_string()))
                .collect()
        })
        .unwrap_or_default()
}

/// The newest run dir under the edition that ran fully: editorial/final.md
/// plus articles/<id>/final.md for every article edition.yaml declares.
fn latest_complete_run(edition_dir: &Path, article_ids: &[String]) -> Option<PathBuf> {
    let mut runs: Vec<PathBuf> = fs::read_dir(edition_dir)
        .ok()?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| {
            p.is_dir()
                && p.file_name()
                    .map(|n| n.to_string_lossy().starts_with("run-"))
                    .unwrap_or(false)
        })
        .collect();
    runs.sort();
    runs.into_iter().rev().find(|run| run_is_complete(run, article_ids))
}

fn run_is_complete(run: &Path, article_ids: &[String]) -> bool {
    run.join("editorial/final.md").exists()
        && article_ids
            .iter()
            .all(|id| run.join("articles").join(id).join("final.md").exists())
}

/// Field-value path-resolution rule: a value whose first segment is
/// `editions` is repo-root-relative; otherwise it is relative to the
/// declaring manifest's directory.
fn resolve_field(raw: &str, manifest_dir: &Path) -> PathBuf {
    if raw.split('/').next() == Some("editions") {
        PathBuf::from(raw)
    } else {
        manifest_dir.join(raw)
    }
}

fn read_yaml(path: &Path) -> Result<serde_yaml::Value> {
    let text = fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))?;
    serde_yaml::from_str(&text).with_context(|| format!("parsing {}", path.display()))
}

fn str_field<'a>(v: &'a serde_yaml::Value, key: &str) -> Option<&'a str> {
    v.get(key).and_then(|x| x.as_str())
}

fn resolve_edition_dir(edition: &str) -> Result<PathBuf> {
    let exact = PathBuf::from("editions").join(edition);
    if exact.is_dir() {
        return Ok(exact);
    }
    let mut matches = Vec::new();
    let dir = Path::new("editions");
    if dir.is_dir() {
        for entry in fs::read_dir(dir).with_context(|| format!("reading {}", dir.display()))? {
            let entry = entry?;
            if !entry.path().is_dir() {
                continue;
            }
            if entry.file_name().to_string_lossy().starts_with(edition) {
                matches.push(entry.path());
            }
        }
    }
    match matches.len() {
        0 => bail!("no edition directory found matching 'editions/{edition}' or 'editions/{edition}*'"),
        1 => Ok(matches.remove(0)),
        _ => {
            matches.sort();
            let names: Vec<String> = matches.iter().map(|p| p.display().to_string()).collect();
            bail!("ambiguous edition '{edition}': matches {}", names.join(", "))
        }
    }
}

/// `[publication]\nname = "..."` scan, no toml dependency. Falls back to
/// "Magazine" if the file, section, or field is absent.
fn publication_name(repo_root: &Path) -> String {
    let path = repo_root.join("magazine.toml");
    let Ok(text) = fs::read_to_string(&path) else {
        return "Magazine".to_string();
    };
    let mut in_publication = false;
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            in_publication = trimmed == "[publication]";
            continue;
        }
        if !in_publication {
            continue;
        }
        if let Some(rest) = trimmed.strip_prefix("name").map(str::trim_start) {
            if let Some(value) = rest.strip_prefix('=') {
                let value = value.trim().trim_matches('"');
                if !value.is_empty() {
                    return value.to_string();
                }
            }
        }
    }
    "Magazine".to_string()
}

/// Stage every figure (`decision: include`) belonging to one article, via
/// its source's already-parsed record.yaml: media_reviews[].assets[] whose
/// id matches the figure's asset_id gives capture_id + artifact_path.
fn stage_article_figures(
    staging: &mut Staging,
    article: &serde_yaml::Value,
    records: &HashMap<String, serde_yaml::Value>,
) -> Result<()> {
    let article_id = str_field(article, "id").unwrap_or("<unknown article>");
    let Some(figures) = article.get("figures").and_then(|v| v.as_sequence()) else {
        return Ok(());
    };
    for figure in figures {
        if str_field(figure, "decision") != Some("include") {
            continue;
        }
        let figure_id = str_field(figure, "id").unwrap_or("<unknown figure>");
        let sid = str_field(figure, "source_id")
            .ok_or_else(|| anyhow!("article '{article_id}' figure '{figure_id}' missing source_id"))?;
        let asset_id = str_field(figure, "asset_id")
            .ok_or_else(|| anyhow!("article '{article_id}' figure '{figure_id}' missing asset_id"))?;
        let Some(record) = records.get(sid) else {
            // That source's record.yaml is already reported missing; skip
            // deriving figure media from content we don't have.
            continue;
        };
        let reviews = record.get("media_reviews").and_then(|v| v.as_sequence()).ok_or_else(|| {
            anyhow!("source '{sid}' record.yaml has no media_reviews (needed for figure '{figure_id}')")
        })?;
        let mut found = None;
        for review in reviews {
            let Some(assets) = review.get("assets").and_then(|v| v.as_sequence()) else {
                continue;
            };
            for asset in assets {
                if str_field(asset, "id") == Some(asset_id) {
                    let capture_id = str_field(review, "capture_id").ok_or_else(|| {
                        anyhow!("source '{sid}' media_reviews entry for asset '{asset_id}' missing capture_id")
                    })?;
                    let artifact_path = str_field(asset, "artifact_path").ok_or_else(|| {
                        anyhow!("source '{sid}' asset '{asset_id}' missing artifact_path")
                    })?;
                    found = Some((capture_id.to_string(), artifact_path.to_string()));
                    break;
                }
            }
            if found.is_some() {
                break;
            }
        }
        let (capture_id, artifact_path) = found.ok_or_else(|| {
            anyhow!(
                "source '{sid}' record.yaml has no media_reviews asset '{asset_id}' \
                 (referenced by article '{article_id}' figure '{figure_id}')"
            )
        })?;
        let base = PathBuf::from("library/sources").join(sid).join("raw").join(&capture_id);
        staging.add(&base.join("manifest.json"));
        staging.add(&base.join("artifacts").join(&artifact_path));
    }
    Ok(())
}

fn print_summary(value: &serde_json::Value, out_dir: &Path) {
    if let Some(layouts) = value.get("layouts").and_then(|v| v.as_object()) {
        for (lang, info) in layouts {
            let total_pages = info.get("totalPages").map(|v| v.to_string()).unwrap_or_else(|| "?".to_string());
            println!("  [{lang}] totalPages={total_pages}");
            if let Some(article_pages) = info.get("articlePages").and_then(|v| v.as_object()) {
                for (aid, pages) in article_pages {
                    println!("    articlePages.{aid} = {pages}");
                }
            }
            if let Some(critic) = info.get("criticResult") {
                println!("    criticResult: {critic}");
            }
        }
    } else {
        println!("  (no 'layouts' field in adapter output)");
    }
    if let Some(files) = value.get("files").and_then(|v| v.as_array()) {
        println!("  files:");
        for f in files {
            let kind = f.get("kind").and_then(|v| v.as_str()).unwrap_or("?");
            let path = f.get("path").and_then(|v| v.as_str()).unwrap_or("?");
            println!("    {kind}: {path}");
        }
    }
    println!("  out dir: {}", out_dir.display());
}

struct AnchorOutcome {
    changed: bool,
    dropped: Vec<String>,
}

/// Re-anchor one article's figures against the current run's manuscript.
/// Anchors that already name a heading (or `__opener__`) are left alone; the
/// rest are matched to a heading by the anchor model, judging by the figure's
/// caption, alt text, rationale, and previous anchor. A figure the model
/// says no heading fits — or any figure when the manuscript has no headings —
/// is removed and reported in `dropped`.
fn resolve_article_anchors(
    caller: &Caller,
    anchor_model: &ModelSpec,
    article_id: &str,
    manuscript_path: &Path,
    article: &mut serde_yaml::Value,
) -> Result<AnchorOutcome> {
    let mut outcome = AnchorOutcome { changed: false, dropped: Vec::new() };
    let headings = manuscript_headings(manuscript_path);

    // Read pass: which figures need resolution, and what the model gets to see.
    let mut pending_idx: Vec<usize> = Vec::new();
    let mut pending_ids: Vec<String> = Vec::new();
    let mut pending_meta = String::new();
    {
        let Some(figs) = article.get("figures").and_then(|v| v.as_sequence()) else {
            return Ok(outcome);
        };
        for (i, fig) in figs.iter().enumerate() {
            let anchor = str_field(fig, "anchor").unwrap_or("");
            if anchor.is_empty()
                || anchor == "__opener__"
                || headings.iter().any(|h| h == anchor)
            {
                continue;
            }
            let fig_id = str_field(fig, "id").unwrap_or("<unknown-figure>").to_string();
            pending_meta += &format!("- id: {fig_id}\n");
            for key in ["caption", "alt_text", "rationale", "anchor"] {
                if let Some(v) = str_field(fig, key) {
                    let label = if key == "anchor" { "previous_section" } else { key };
                    pending_meta += &format!("  {label}: {v}\n");
                }
            }
            pending_idx.push(i);
            pending_ids.push(fig_id);
        }
    }
    if pending_idx.is_empty() {
        return Ok(outcome);
    }

    let resolutions: Vec<Option<String>> = if headings.is_empty() {
        vec![None; pending_idx.len()]
    } else {
        let manuscript = fs::read_to_string(manuscript_path)
            .with_context(|| format!("reading {}", manuscript_path.display()))?;
        let prompt = format!(
            "Below are a magazine article manuscript and the figures that must be placed in \
             it. For each figure, choose the manuscript section heading whose section \
             discusses what the figure shows. Reply with exactly one line per figure, in the \
             order given, formatted `<figure id> :: <heading text exactly as written, \
             without the leading ##>`. Use `<figure id> :: NONE` only if no section fits.\n\n\
             ========== manuscript ==========\n\n{manuscript}\n\n\
             ========== figures ==========\n\n{pending_meta}"
        );
        caller.call_with_parse(
            &format!("{article_id} figure anchors"),
            anchor_model,
            &prompt,
            |reply| parse_anchor_reply(reply, &pending_ids, &headings),
        )?
    };

    let figs = article
        .get_mut("figures")
        .and_then(|v| v.as_sequence_mut())
        .expect("figures existed in the read pass");
    let mut drop_idx: HashSet<usize> = HashSet::new();
    for ((&i, fig_id), resolution) in pending_idx.iter().zip(&pending_ids).zip(resolutions) {
        let old = str_field(&figs[i], "anchor").unwrap_or("?").to_string();
        match resolution {
            Some(heading) => {
                println!("  re-anchored {article_id}:{fig_id} '{old}' -> '{heading}'");
                if let Some(map) = figs[i].as_mapping_mut() {
                    map.insert(
                        serde_yaml::Value::String("anchor".to_string()),
                        serde_yaml::Value::String(heading),
                    );
                }
                outcome.changed = true;
            }
            None => {
                outcome.dropped.push(format!("{article_id}:{fig_id} (was '{old}')"));
                drop_idx.insert(i);
            }
        }
    }
    if !drop_idx.is_empty() {
        let mut i = 0;
        figs.retain(|_| {
            let keep = !drop_idx.contains(&i);
            i += 1;
            keep
        });
        outcome.changed = true;
    }
    Ok(outcome)
}

/// One `<figure id> :: <heading|NONE>` line per pending figure, matched
/// case-insensitively to the manuscript's headings; the returned anchor is
/// the heading exactly as the manuscript writes it, which is what the
/// renderer's exact-match validation requires.
fn parse_anchor_reply(
    reply: &str,
    ids: &[String],
    headings: &[String],
) -> Result<Vec<Option<String>>> {
    let mut out = Vec::with_capacity(ids.len());
    for id in ids {
        let line = reply
            .lines()
            .find(|l| l.split("::").next().map(|s| s.trim().trim_start_matches('-').trim() == id).unwrap_or(false))
            .ok_or_else(|| anyhow!("reply has no `{id} :: <heading>` line"))?;
        let value = line
            .split_once("::")
            .map(|(_, v)| v)
            .unwrap_or("")
            .trim()
            .trim_start_matches("##")
            .trim();
        if value.eq_ignore_ascii_case("none") {
            out.push(None);
            continue;
        }
        let matched = headings
            .iter()
            .find(|h| h.trim().eq_ignore_ascii_case(value))
            .ok_or_else(|| {
                anyhow!(
                    "'{value}' is not a heading of this manuscript; the headings are: {}",
                    headings.join(" | ")
                )
            })?;
        out.push(Some(matched.clone()));
    }
    Ok(out)
}

pub fn run(
    edition: &str,
    operation: &str,
    article: Option<&str>,
    langs: Option<&str>,
    run_flag: Option<&str>,
    anchor_model: &ModelSpec,
) -> Result<i32> {
    if !OPERATIONS.contains(&operation) {
        bail!("unknown operation '{operation}': expected one of {}", OPERATIONS.join(", "));
    }
    if operation == "measure_article" && article.is_none() {
        bail!("measure_article requires --article");
    }

    let repo_root = std::env::current_dir().context("resolving current directory")?;
    let repo_root = repo_root.canonicalize().context("canonicalizing repo root")?;

    let edition_dir = resolve_edition_dir(edition)?;
    let edition_yaml_path = edition_dir.join("edition.yaml");
    if !edition_yaml_path.exists() {
        bail!("{} not found", edition_yaml_path.display());
    }
    let edition_yaml = read_yaml(&edition_yaml_path)?;

    let edition_id = str_field(&edition_yaml, "id")
        .map(str::to_string)
        .unwrap_or_else(|| edition_dir.file_name().unwrap().to_string_lossy().to_string());
    let primary_language = str_field(&edition_yaml, "language").unwrap_or("en").to_string();

    let articles = edition_yaml
        .get("articles")
        .and_then(|v| v.as_sequence())
        .ok_or_else(|| anyhow!("edition.yaml missing 'articles' list"))?
        .clone();

    if operation == "measure_article" {
        let wanted = article.unwrap();
        let ids: Vec<String> =
            articles.iter().filter_map(|a| str_field(a, "id").map(str::to_string)).collect();
        if !ids.iter().any(|id| id == wanted) {
            bail!("article '{wanted}' not found in edition '{edition_id}'; available: {}", ids.join(", "));
        }
    }

    // Renders live beside the edition's runs: editions/<ed>/render-<ts>/
    let render_dir = edition_dir.join(format!("render-{}", crate::caller::now_stamp()));
    let mut staging = Staging::new(repo_root.clone());

    // Content comes from a run: --run <dir>, else the newest complete run,
    // else the files edition.yaml points at. Run finals are staged AT the
    // paths edition.yaml declares, so no promotion step exists.
    let article_ids: Vec<String> =
        articles.iter().filter_map(|a| str_field(a, "id").map(str::to_string)).collect();
    let content_run: Option<PathBuf> = match run_flag {
        Some(dir) => {
            let dir = PathBuf::from(dir);
            if !run_is_complete(&dir, &article_ids) {
                bail!(
                    "{} is not a complete run (needs editorial/final.md and articles/<id>/final.md for: {})",
                    dir.display(),
                    article_ids.join(", ")
                );
            }
            Some(dir)
        }
        None => latest_complete_run(&edition_dir, &article_ids),
    };
    match &content_run {
        Some(run) => println!("content: {}", run.display()),
        None => println!("content: committed edition files (no complete run found)"),
    }

    // A. Base edition manuscript + editorial + article manuscripts.
    // Figure anchors name a heading in the manuscript, and every run writes
    // its own headings — so an anchor pinned to a previous run's prose is
    // re-resolved against this run's manuscript by the cheap anchor model
    // (an anchor that still matches exactly never costs a call). Only a
    // figure no heading fits is dropped, loudly.
    let mut staged_edition_path = edition_yaml_path.clone();
    if let Some(run) = &content_run {
        fs::create_dir_all(&render_dir)?;
        let caller = Caller::new(&render_dir);
        let mut patched = edition_yaml.clone();
        let mut changed = false;
        let mut dropped: Vec<String> = Vec::new();
        if let Some(list) = patched.get_mut("articles").and_then(|v| v.as_sequence_mut()) {
            for article in list.iter_mut() {
                let Some(id) = str_field(article, "id").map(str::to_string) else { continue };
                let manuscript_path = run.join("articles").join(&id).join("final.md");
                let outcome =
                    resolve_article_anchors(&caller, anchor_model, &id, &manuscript_path, article)?;
                changed |= outcome.changed;
                dropped.extend(outcome.dropped);
            }
        }
        if !dropped.is_empty() {
            println!("  dropped {} figure(s) no heading of this run fits:", dropped.len());
            for d in &dropped {
                println!("    {d}");
            }
        }
        if changed {
            let patched_path = render_dir.join("edition.yaml");
            fs::write(&patched_path, serde_yaml::to_string(&patched)?)?;
            staged_edition_path = patched_path;
        }
    }
    staging.add_mapped(&staged_edition_path, &edition_yaml_path);
    if let Some(editorial) = str_field(&edition_yaml, "editorial") {
        let declared = resolve_field(editorial, &edition_dir);
        match &content_run {
            Some(run) => staging.add_mapped(&run.join("editorial/final.md"), &declared),
            None => staging.add(&declared),
        }
    }
    for article in &articles {
        if let (Some(id), Some(manuscript)) =
            (str_field(article, "id"), str_field(article, "manuscript"))
        {
            let declared = resolve_field(manuscript, &edition_dir);
            match &content_run {
                Some(run) => staging
                    .add_mapped(&run.join("articles").join(id).join("final.md"), &declared),
                None => staging.add(&declared),
            }
        }
    }

    // B. Art: cover, openers, tails, closing plates.
    if let Some(art_path) = edition_yaml.get("cover").and_then(|c| str_field(c, "art_path")) {
        staging.add(&resolve_field(art_path, &edition_dir));
    }
    for article in &articles {
        if let Some(opener_path) = article.get("opener_art").and_then(|o| str_field(o, "path")) {
            staging.add(&resolve_field(opener_path, &edition_dir));
        }
        if let Some(tail_path) = str_field(article, "tail_art_path") {
            staging.add(&resolve_field(tail_path, &edition_dir));
        }
    }
    if let Some(plates) = edition_yaml.get("closing_plates").and_then(|v| v.as_sequence()) {
        for plate in plates {
            if let Some(art_path) = str_field(plate, "art_path") {
                staging.add(&resolve_field(art_path, &edition_dir));
            }
        }
    }

    // C. Optional cover design defaults.
    let design_toml = PathBuf::from(DESIGN_TOML_PATH);
    if repo_root.join(&design_toml).exists() {
        staging.add(&design_toml);
    }

    // D. ES translation, if present (skipped when --langs excludes es).
    let translation_dir = edition_dir.join("translations/es");
    let translation_yaml_path = translation_dir.join("edition.yaml");
    let has_translation = translation_yaml_path.exists()
        && langs.map(|l| l.split(',').any(|x| x.trim() == "es")).unwrap_or(true);
    let languages: Vec<String> = if has_translation {
        vec!["en".to_string(), "es".to_string()]
    } else {
        vec!["en".to_string()]
    };
    if has_translation {
        let translation_yaml = read_yaml(&translation_yaml_path)?;
        staging.add(&translation_yaml_path);
        if let Some(editorial_path) = translation_yaml.get("editorial").and_then(|e| str_field(e, "path")) {
            staging.add(&resolve_field(editorial_path, &translation_dir));
        }
        if let Some(t_articles) = translation_yaml.get("articles").and_then(|v| v.as_sequence()) {
            for t_article in t_articles {
                if let Some(manuscript) = str_field(t_article, "manuscript") {
                    staging.add(&resolve_field(manuscript, &translation_dir));
                }
            }
        }
    }

    // E. Source record.yamls for every top-level source id and every
    // article's source_ids, parsing each so F can resolve figure media.
    let mut sids: Vec<String> = Vec::new();
    let mut sid_seen: HashSet<String> = HashSet::new();
    if let Some(top_sources) = edition_yaml.get("sources").and_then(|v| v.as_sequence()) {
        for s in top_sources {
            if let Some(sid) = s.as_str() {
                if sid_seen.insert(sid.to_string()) {
                    sids.push(sid.to_string());
                }
            }
        }
    }
    for article in &articles {
        if let Some(source_ids) = article.get("source_ids").and_then(|v| v.as_sequence()) {
            for s in source_ids {
                if let Some(sid) = s.as_str() {
                    if sid_seen.insert(sid.to_string()) {
                        sids.push(sid.to_string());
                    }
                }
            }
        }
    }

    let mut records: HashMap<String, serde_yaml::Value> = HashMap::new();
    for sid in &sids {
        let record_path = PathBuf::from("library/sources").join(sid).join("record.yaml");
        if !repo_root.join(&record_path).exists() {
            staging.missing.push(record_path.to_string_lossy().replace('\\', "/"));
            continue;
        }
        staging.add(&record_path);
        let record = read_yaml(&repo_root.join(&record_path))?;
        records.insert(sid.clone(), record);
    }

    // F. Figure media, resolved through each article's source records.
    for article in &articles {
        stage_article_figures(&mut staging, article, &records)?;
    }

    if !staging.missing.is_empty() {
        staging.missing.sort();
        staging.missing.dedup();
        bail!(
            "missing {} staged file(s) for edition '{edition_id}':\n  {}",
            staging.missing.len(),
            staging.missing.join("\n  ")
        );
    }

    let request = Request {
        schema_version: SCHEMA_VERSION,
        renderer_contract_version: RENDERER_CONTRACT_VERSION.to_string(),
        operation: operation.to_string(),
        article_id: if operation == "measure_article" { article.map(str::to_string) } else { None },
        edition_id: edition_id.clone(),
        primary_language,
        languages,
        publication_name: publication_name(&repo_root),
        renderer: RENDERER.to_string(),
        artifact_root: repo_root.to_string_lossy().to_string(),
        inputs: staging.rows,
    };

    let run_dir = render_dir;
    let out_dir = run_dir.join("out");
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    let request_path = run_dir.join("request.json");
    fs::write(&request_path, serde_json::to_string_pretty(&request)?)
        .with_context(|| format!("writing {}", request_path.display()))?;

    println!("request: {}", request_path.display());
    println!("out dir: {}", out_dir.display());

    // The bridge requires absolute request and destination paths.
    let mut child = Command::new("uv")
        .args(["run", "mag-render-adapter"])
        .arg(request_path.canonicalize()?)
        .arg(out_dir.canonicalize()?)
        .current_dir(&repo_root)
        .stdout(Stdio::piped())
        .spawn()
        .context("spawning `uv run mag-render-adapter`")?;

    let mut stdout_buf = String::new();
    child
        .stdout
        .take()
        .expect("piped stdout")
        .read_to_string(&mut stdout_buf)
        .context("reading mag-render-adapter stdout")?;
    let status = child.wait().context("waiting for mag-render-adapter")?;

    if !status.success() {
        bail!(
            "mag-render-adapter exited with {status} (request: {}, out: {}); see stderr above",
            request_path.display(),
            out_dir.display()
        );
    }

    let value: serde_json::Value = serde_json::from_str(&stdout_buf)
        .with_context(|| format!("parsing mag-render-adapter stdout as JSON: {stdout_buf}"))?;
    print_summary(&value, &out_dir);

    Ok(0)
}

#[cfg(test)]
mod tests {
    use super::parse_anchor_reply;

    #[test]
    fn anchor_reply_matches_headings_exactly_and_case_insensitively() {
        let ids = vec!["fig-a".to_string(), "fig-b".to_string()];
        let headings = vec!["The Escalation".to_string(), "How it talked".to_string()];
        let reply = "fig-a :: the escalation\nfig-b :: NONE\n";
        let out = parse_anchor_reply(reply, &ids, &headings).unwrap();
        assert_eq!(out, vec![Some("The Escalation".to_string()), None]);
        assert!(parse_anchor_reply("fig-a :: Not A Heading\nfig-b :: NONE", &ids, &headings).is_err());
        assert!(parse_anchor_reply("fig-a :: The Escalation", &ids, &headings).is_err());
    }
}
