// Render seam: stages every file the Python renderer bridge needs, writes a
// magazine-renderer/1 request, then shells out to `uv run mag-render-adapter
// <request.json> <out>`. The bridge copies inputs into its own stage root and
// does the actual typesetting; this module's only job is to discover and
// validate the input set (walking edition.yaml, translations, and source
// record.yamls) and to report back what came out.

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

pub fn run(edition: &str, operation: &str, article: Option<&str>) -> Result<i32> {
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

    let mut staging = Staging::new(repo_root.clone());

    // A. Base edition manuscript + editorial + article manuscripts.
    staging.add(&edition_yaml_path);
    if let Some(editorial) = str_field(&edition_yaml, "editorial") {
        staging.add(&resolve_field(editorial, &edition_dir));
    }
    for article in &articles {
        if let Some(manuscript) = str_field(article, "manuscript") {
            staging.add(&resolve_field(manuscript, &edition_dir));
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

    // D. ES translation, if present.
    let translation_dir = edition_dir.join("translations/es");
    let translation_yaml_path = translation_dir.join("edition.yaml");
    let has_translation = translation_yaml_path.exists();
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

    let run_dir = PathBuf::from("runs").join(&edition_id).join(format!("render-{}", crate::caller::now_stamp()));
    let out_dir = run_dir.join("out");
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    let request_path = run_dir.join("request.json");
    fs::write(&request_path, serde_json::to_string_pretty(&request)?)
        .with_context(|| format!("writing {}", request_path.display()))?;

    println!("request: {}", request_path.display());
    println!("out dir: {}", out_dir.display());

    let mut child = Command::new("uv")
        .args(["run", "mag-render-adapter"])
        .arg(&request_path)
        .arg(&out_dir)
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
