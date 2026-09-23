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

struct Staging {
    repo_root: PathBuf,
    seen: HashSet<String>,
    rows: Vec<InputRow>,
    missing: Vec<String>,
}

impl Staging {
    fn new(repo_root: PathBuf) -> Self {
        Self {
            repo_root,
            seen: HashSet::new(),
            rows: Vec::new(),
            missing: Vec::new(),
        }
    }

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

    fn add_mapped(&mut self, source: &Path, target: &Path) {
        let target = target.to_string_lossy().replace('\\', "/");
        if !self.seen.insert(target.clone()) {
            return;
        }
        let abs = self.repo_root.join(source);
        if !abs.exists() {
            self.missing
                .push(format!("{} (for {})", source.display(), target));
            return;
        }
        self.rows.push(InputRow {
            artifact_id: target.clone(),
            source_path: abs.to_string_lossy().to_string(),
            target_path: target,
        });
    }
}

fn manuscript_headings(path: &Path) -> Vec<String> {
    fs::read_to_string(path)
        .map(|t| {
            t.lines()
                .filter_map(|l| {
                    l.strip_prefix("## ")
                        .or_else(|| l.strip_prefix("### "))
                        .map(|h| h.trim().to_string())
                })
                .collect()
        })
        .unwrap_or_default()
}

fn latest_complete_run(
    edition_dir: &Path,
    article_ids: &[String],
    needs_editorial: bool,
) -> Option<PathBuf> {
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
    runs.into_iter()
        .rev()
        .find(|run| run_is_complete(run, article_ids, needs_editorial))
}

fn run_is_complete(run: &Path, article_ids: &[String], needs_editorial: bool) -> bool {
    (!needs_editorial || run.join("editorial/final.md").exists())
        && article_ids
            .iter()
            .all(|id| run.join("articles").join(id).join("final.md").exists())
}

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
        0 => bail!(
            "no edition directory found matching 'editions/{edition}' or 'editions/{edition}*'"
        ),
        1 => Ok(matches.remove(0)),
        _ => {
            matches.sort();
            let names: Vec<String> = matches.iter().map(|p| p.display().to_string()).collect();
            bail!(
                "ambiguous edition '{edition}': matches {}",
                names.join(", ")
            )
        }
    }
}

fn toml_value(repo_root: &Path, section: &str, key: &str) -> Option<String> {
    let text = fs::read_to_string(repo_root.join("magazine.toml")).ok()?;
    let header = format!("[{section}]");
    let mut inside = false;
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            inside = trimmed == header;
            continue;
        }
        if !inside {
            continue;
        }
        let Some(rest) = trimmed.strip_prefix(key).map(str::trim_start) else {
            continue;
        };
        if let Some(value) = rest.strip_prefix('=') {
            let value = value.trim().trim_matches('"');
            if !value.is_empty() {
                return Some(value.to_string());
            }
        }
    }
    None
}

pub(crate) fn publication_name(repo_root: &Path) -> String {
    toml_value(repo_root, "publication", "name").unwrap_or_else(|| "Magazine".to_string())
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum Engine {
    Weasyprint,
    Typst,
}

fn parse_engine(value: &str, origin: &str) -> Result<Engine> {
    match value {
        "weasyprint" => Ok(Engine::Weasyprint),
        "typst" => Ok(Engine::Typst),
        other => {
            bail!("unknown render engine '{other}' from {origin}: expected weasyprint or typst")
        }
    }
}

pub(crate) fn select_engine(repo_root: &Path, flag: Option<&str>) -> Result<Engine> {
    match flag {
        Some(value) => parse_engine(value, "--engine"),
        None => match toml_value(repo_root, "render", "engine") {
            Some(value) => parse_engine(&value, "magazine.toml [render] engine"),
            None => Ok(Engine::Weasyprint),
        },
    }
}

fn stage_article_figures(staging: &mut Staging, article: &serde_yaml::Value) -> Result<()> {
    let article_id = str_field(article, "id").unwrap_or("<unknown article>");
    let Some(figures) = article.get("figures").and_then(|v| v.as_sequence()) else {
        return Ok(());
    };
    for figure in figures {
        let figure_id = str_field(figure, "id").unwrap_or("<unknown figure>");
        let sid = str_field(figure, "source_id").ok_or_else(|| {
            anyhow!("article '{article_id}' figure '{figure_id}' missing source_id")
        })?;
        let path = str_field(figure, "path")
            .ok_or_else(|| anyhow!("article '{article_id}' figure '{figure_id}' missing path"))?;
        staging.add(&PathBuf::from("library/sources").join(sid).join(path));
    }
    Ok(())
}

fn stage_article_extracts(staging: &mut Staging, article: &serde_yaml::Value) -> Result<()> {
    let article_id = str_field(article, "id").unwrap_or("<unknown article>");
    let Some(extracts) = article.get("extracts").and_then(|v| v.as_sequence()) else {
        return Ok(());
    };
    for extract in extracts {
        let extract_id = str_field(extract, "id").unwrap_or("<unknown extract>");
        let sid = str_field(extract, "source_id").ok_or_else(|| {
            anyhow!("article '{article_id}' extract '{extract_id}' missing source_id")
        })?;
        staging.add(
            &PathBuf::from("library/sources")
                .join(sid)
                .join("article.md"),
        );
    }
    Ok(())
}

fn print_summary(value: &serde_json::Value, out_dir: &Path) {
    if let Some(layouts) = value.get("layouts").and_then(|v| v.as_array()) {
        for info in layouts {
            let lang = info.get("language").and_then(|v| v.as_str()).unwrap_or("?");
            let total_pages = info
                .get("totalPages")
                .map(|v| v.to_string())
                .unwrap_or_else(|| "?".to_string());
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

struct PendingFigures {
    idx: Vec<usize>,
    ids: Vec<String>,
    anchors: Vec<String>,
    meta: String,
}

fn pending_figures(article: &serde_yaml::Value, headings: &[String]) -> PendingFigures {
    let mut pending = PendingFigures {
        idx: Vec::new(),
        ids: Vec::new(),
        anchors: Vec::new(),
        meta: String::new(),
    };
    let figs = article
        .get("figures")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten();
    for (i, fig) in figs.enumerate() {
        let anchor = str_field(fig, "anchor").unwrap_or("");
        if anchor.is_empty() || anchor == "__opener__" || headings.iter().any(|h| h == anchor) {
            continue;
        }
        let fig_id = str_field(fig, "id")
            .unwrap_or("<unknown-figure>")
            .to_string();
        pending.meta += &format!("- id: {fig_id}\n");
        for key in ["caption", "alt_text", "rationale", "anchor"] {
            if let Some(v) = str_field(fig, key) {
                let label = if key == "anchor" {
                    "previous_section"
                } else {
                    key
                };
                pending.meta += &format!("  {label}: {v}\n");
            }
        }
        pending.idx.push(i);
        pending.ids.push(fig_id);
        pending.anchors.push(anchor.to_string());
    }
    pending
}

fn resolve_article_anchors(
    caller: &Caller,
    anchor_model: &ModelSpec,
    article_id: &str,
    manuscript_path: &Path,
    headings: &[String],
    pending: &PendingFigures,
    article: &mut serde_yaml::Value,
) -> Result<AnchorOutcome> {
    let mut outcome = AnchorOutcome {
        changed: false,
        dropped: Vec::new(),
    };
    if pending.idx.is_empty() {
        return Ok(outcome);
    }
    let pending_ids = &pending.ids;
    let pending_meta = &pending.meta;

    let resolutions: Vec<Option<String>> = if headings.is_empty() {
        vec![None; pending.idx.len()]
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
            |reply| parse_anchor_reply(reply, pending_ids, headings),
        )?
    };

    let figs = article
        .get_mut("figures")
        .and_then(|v| v.as_sequence_mut())
        .expect("figures existed in the pending scan");
    let mut drop_idx: HashSet<usize> = HashSet::new();
    for ((&i, fig_id), resolution) in pending.idx.iter().zip(pending_ids).zip(resolutions) {
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
                outcome
                    .dropped
                    .push(format!("{article_id}:{fig_id} (was '{old}')"));
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

fn parse_anchor_reply(
    reply: &str,
    ids: &[String],
    headings: &[String],
) -> Result<Vec<Option<String>>> {
    let mut out = Vec::with_capacity(ids.len());
    for id in ids {
        let line = reply
            .lines()
            .find(|l| {
                l.split("::")
                    .next()
                    .map(|s| s.trim().trim_start_matches('-').trim() == id)
                    .unwrap_or(false)
            })
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

#[derive(clap::Args)]
pub(crate) struct RenderArgs {
    pub edition: String,
    #[arg(
        long,
        default_value = "render_edition",
        help = "measure_article, measure_edition, or render_edition"
    )]
    pub operation: String,
    #[arg(long, help = "Article id, required for measure_article")]
    pub article: Option<String>,
    #[arg(
        long,
        help = "Comma-separated languages to render (default: en + es if translations exist)"
    )]
    pub langs: Option<String>,
    #[arg(
        long,
        help = "Run dir whose finals to render (default: newest complete run, else committed files)"
    )]
    pub run: Option<String>,
    #[arg(
        long = "anchor-model",
        default_value = "haiku",
        help = "Cheap model that re-anchors figures to this run's headings"
    )]
    pub anchor_model: String,
    #[arg(
        long = "no-model",
        help = "Refuse model calls: abort listing pending figure anchors instead of patching them"
    )]
    pub no_model: bool,
    #[arg(
        long,
        help = "Typesetting engine: weasyprint or typst (default: magazine.toml [render] engine)"
    )]
    pub engine: Option<String>,
}

struct EditionInputs {
    dir: PathBuf,
    yaml_path: PathBuf,
    yaml: serde_yaml::Value,
    id: String,
    articles: Vec<serde_yaml::Value>,
    article_ids: Vec<String>,
}

fn load_edition(edition: &str) -> Result<EditionInputs> {
    let dir = resolve_edition_dir(edition)?;
    let yaml_path = dir.join("edition.yaml");
    if !yaml_path.exists() {
        bail!("{} not found", yaml_path.display());
    }
    let yaml = read_yaml(&yaml_path)?;
    let id = str_field(&yaml, "id")
        .map(str::to_string)
        .unwrap_or_else(|| dir.file_name().unwrap().to_string_lossy().to_string());
    let articles = yaml
        .get("articles")
        .and_then(|v| v.as_sequence())
        .ok_or_else(|| anyhow!("edition.yaml missing 'articles' list"))?
        .clone();
    let article_ids = articles
        .iter()
        .filter_map(|a| str_field(a, "id").map(str::to_string))
        .collect();
    Ok(EditionInputs {
        dir,
        yaml_path,
        yaml,
        id,
        articles,
        article_ids,
    })
}

pub fn run(args: &RenderArgs) -> Result<i32> {
    let operation = args.operation.as_str();
    let article = args.article.as_deref();
    let langs = args.langs.as_deref();
    let run_flag = args.run.as_deref();
    let no_model = args.no_model;
    if !OPERATIONS.contains(&operation) {
        bail!(
            "unknown operation '{operation}': expected one of {}",
            OPERATIONS.join(", ")
        );
    }
    if operation == "measure_article" && article.is_none() {
        bail!("measure_article requires --article");
    }

    let repo_root = std::env::current_dir()
        .context("resolving current directory")?
        .canonicalize()
        .context("canonicalizing repo root")?;
    let engine = select_engine(&repo_root, args.engine.as_deref())?;
    let anchor_model = &ModelSpec::parse(&args.anchor_model)?;
    let EditionInputs {
        dir: edition_dir,
        yaml_path: edition_yaml_path,
        yaml: edition_yaml,
        id: edition_id,
        articles,
        article_ids,
    } = load_edition(&args.edition)?;
    if let Some(wanted) = article.filter(|_| operation == "measure_article") {
        if !article_ids.iter().any(|id| id == wanted) {
            bail!(
                "article '{wanted}' not found in edition '{edition_id}'; available: {}",
                article_ids.join(", ")
            );
        }
    }

    let render_dir = edition_dir.join(format!("render-{}", crate::caller::now_stamp()));
    let content_run = pick_content_run(run_flag, &edition_dir, &article_ids, &edition_yaml)?;
    let mut staging = Staging::new(repo_root.clone());
    let staged_edition_path = match &content_run {
        Some(run) => patch_anchors(run, &render_dir, &edition_yaml, anchor_model, no_model)?
            .unwrap_or_else(|| edition_yaml_path.clone()),
        None => edition_yaml_path.clone(),
    };
    staging.add_mapped(&staged_edition_path, &edition_yaml_path);
    stage_manuscripts(
        &mut staging,
        &edition_yaml,
        &edition_dir,
        content_run.as_deref(),
    );
    stage_art(&mut staging, &edition_yaml, &edition_dir);
    stage_source_codes(&mut staging, &edition_dir, &repo_root);
    let design_toml = PathBuf::from(DESIGN_TOML_PATH);
    if repo_root.join(&design_toml).exists() {
        staging.add(&design_toml);
    }
    let languages = stage_translation(&mut staging, &edition_dir, langs)?;
    stage_source_records(&mut staging, &edition_yaml, &repo_root);
    for article in &articles {
        stage_article_figures(&mut staging, article)?;
    }
    for article in &articles {
        stage_article_extracts(&mut staging, article)?;
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
        article_id: article
            .filter(|_| operation == "measure_article")
            .map(str::to_string),
        edition_id,
        primary_language: str_field(&edition_yaml, "language")
            .unwrap_or("en")
            .to_string(),
        languages,
        publication_name: publication_name(&repo_root),
        renderer: RENDERER.to_string(),
        artifact_root: repo_root.to_string_lossy().to_string(),
        inputs: staging.rows,
    };
    match engine {
        Engine::Weasyprint => run_adapter(&repo_root, &render_dir, &request),
        Engine::Typst => run_typst(&repo_root, &render_dir, &request),
    }
}

fn run_typst(repo_root: &Path, render_dir: &Path, request: &Request) -> Result<i32> {
    let value =
        crate::typeset::run_request(repo_root, render_dir, &serde_json::to_string(request)?)?;
    let result = render_dir.join("result.json");
    fs::write(&result, serde_json::to_string_pretty(&value)? + "\n")
        .with_context(|| format!("writing {}", result.display()))?;
    print_summary(&value, &render_dir.join(&request.primary_language));
    if request.operation == "render_edition" {
        println!(
            "\nnext: `mag parity {}` compares this leg against weasyprint",
            request.edition_id
        );
    } else {
        println!(
            "\nnext: `mag render {} --engine typst` renders the reader this measure describes",
            request.edition_id
        );
    }
    Ok(0)
}

fn pick_content_run(
    run_flag: Option<&str>,
    edition_dir: &Path,
    article_ids: &[String],
    edition_yaml: &serde_yaml::Value,
) -> Result<Option<PathBuf>> {
    let needs_editorial = str_field(edition_yaml, "editorial").is_some();
    let content_run = match run_flag {
        Some(dir) => {
            let dir = PathBuf::from(dir);
            if !run_is_complete(&dir, article_ids, needs_editorial) {
                bail!(
                    "{} is not a complete run (needs articles/<id>/final.md for: {}, plus editorial/final.md when the edition declares one)",
                    dir.display(),
                    article_ids.join(", ")
                );
            }
            Some(dir)
        }
        None => latest_complete_run(edition_dir, article_ids, needs_editorial),
    };
    match &content_run {
        Some(run) => println!("content: {}", run.display()),
        None => println!("content: committed edition files (no complete run found)"),
    }
    Ok(content_run)
}

fn patch_anchors(
    run: &Path,
    render_dir: &Path,
    edition_yaml: &serde_yaml::Value,
    anchor_model: &ModelSpec,
    no_model: bool,
) -> Result<Option<PathBuf>> {
    let mut scans: HashMap<String, (Vec<String>, PendingFigures)> = HashMap::new();
    let mut stale: Vec<String> = Vec::new();
    for article in articles_of(edition_yaml) {
        let Some(id) = str_field(article, "id") else {
            continue;
        };
        let headings = manuscript_headings(&run.join("articles").join(id).join("final.md"));
        let pending = pending_figures(article, &headings);
        for (fig_id, anchor) in pending.ids.iter().zip(&pending.anchors) {
            stale.push(format!("{id}:{fig_id} (anchor '{anchor}')"));
        }
        scans.insert(id.to_string(), (headings, pending));
    }
    println!("  pending anchors: {}", stale.len());
    if no_model && !stale.is_empty() {
        bail!(
            "--no-model: {} figure anchor(s) need model patching:\n  {}",
            stale.len(),
            stale.join("\n  ")
        );
    }
    fs::create_dir_all(render_dir)?;
    let caller = Caller::new(render_dir);
    let mut patched = edition_yaml.clone();
    let mut changed = false;
    let mut dropped: Vec<String> = Vec::new();
    if let Some(list) = patched
        .get_mut("articles")
        .and_then(|v| v.as_sequence_mut())
    {
        for article in list.iter_mut() {
            let Some(id) = str_field(article, "id").map(str::to_string) else {
                continue;
            };
            let Some((headings, pending)) = scans.get(&id) else {
                continue;
            };
            let manuscript_path = run.join("articles").join(&id).join("final.md");
            let outcome = resolve_article_anchors(
                &caller,
                anchor_model,
                &id,
                &manuscript_path,
                headings,
                pending,
                article,
            )?;
            changed |= outcome.changed;
            dropped.extend(outcome.dropped);
        }
    }
    if !dropped.is_empty() {
        println!(
            "  dropped {} figure(s) no heading of this run fits:",
            dropped.len()
        );
        for d in &dropped {
            println!("    {d}");
        }
    }
    if !changed {
        return Ok(None);
    }
    let patched_path = render_dir.join("edition.yaml");
    fs::write(&patched_path, serde_yaml::to_string(&patched)?)?;
    Ok(Some(patched_path))
}

fn stage_manuscripts(
    staging: &mut Staging,
    edition_yaml: &serde_yaml::Value,
    edition_dir: &Path,
    content_run: Option<&Path>,
) {
    let mut stage = |declared: PathBuf, from_run: PathBuf| match content_run {
        Some(run) => staging.add_mapped(&run.join(from_run), &declared),
        None => staging.add(&declared),
    };
    if let Some(editorial) = str_field(edition_yaml, "editorial") {
        stage(
            resolve_field(editorial, edition_dir),
            PathBuf::from("editorial/final.md"),
        );
    }
    for article in articles_of(edition_yaml) {
        if let (Some(id), Some(manuscript)) =
            (str_field(article, "id"), str_field(article, "manuscript"))
        {
            stage(
                resolve_field(manuscript, edition_dir),
                PathBuf::from("articles").join(id).join("final.md"),
            );
        }
    }
}

fn articles_of(edition_yaml: &serde_yaml::Value) -> impl Iterator<Item = &serde_yaml::Value> {
    edition_yaml
        .get("articles")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten()
}

fn stage_source_codes(staging: &mut Staging, edition_dir: &Path, repo_root: &Path) {
    let rel = edition_dir.join("source-codes");
    let Ok(entries) = fs::read_dir(repo_root.join(&rel)) else {
        return;
    };
    let mut names: Vec<_> = entries
        .flatten()
        .filter(|e| e.path().is_file())
        .map(|e| e.file_name())
        .collect();
    names.sort();
    for name in names {
        staging.add(&rel.join(name));
    }
}

fn stage_art(staging: &mut Staging, edition_yaml: &serde_yaml::Value, edition_dir: &Path) {
    let cover = edition_yaml
        .get("cover")
        .and_then(|c| str_field(c, "art_path"));
    let plates = edition_yaml
        .get("closing_plates")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten()
        .filter_map(|plate| str_field(plate, "art_path"));
    let article_art = articles_of(edition_yaml).flat_map(|article| {
        let opener = article.get("opener_art").and_then(|o| str_field(o, "path"));
        opener
            .into_iter()
            .chain(str_field(article, "tail_art_path"))
    });
    for path in cover.into_iter().chain(article_art).chain(plates) {
        staging.add(&resolve_field(path, edition_dir));
    }
}

fn stage_translation(
    staging: &mut Staging,
    edition_dir: &Path,
    langs: Option<&str>,
) -> Result<Vec<String>> {
    let translation_dir = edition_dir.join("translations/es");
    let translation_yaml_path = translation_dir.join("edition.yaml");
    let has_translation = translation_yaml_path.exists()
        && langs
            .map(|l| l.split(',').any(|x| x.trim() == "es"))
            .unwrap_or(true);
    if !has_translation {
        return Ok(vec!["en".to_string()]);
    }
    let translation_yaml = read_yaml(&translation_yaml_path)?;
    staging.add(&translation_yaml_path);
    if let Some(editorial_path) = translation_yaml
        .get("editorial")
        .and_then(|e| str_field(e, "path"))
    {
        staging.add(&resolve_field(editorial_path, &translation_dir));
    }
    for t_article in articles_of(&translation_yaml) {
        if let Some(manuscript) = str_field(t_article, "manuscript") {
            staging.add(&resolve_field(manuscript, &translation_dir));
        }
    }
    Ok(vec!["en".to_string(), "es".to_string()])
}

fn stage_source_records(staging: &mut Staging, edition_yaml: &serde_yaml::Value, repo_root: &Path) {
    let top = edition_yaml
        .get("sources")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten();
    let per_article = articles_of(edition_yaml).flat_map(|a| {
        a.get("source_ids")
            .and_then(|v| v.as_sequence())
            .into_iter()
            .flatten()
    });
    let mut seen: HashSet<String> = HashSet::new();
    for sid in top.chain(per_article).filter_map(|s| s.as_str()) {
        if !seen.insert(sid.to_string()) {
            continue;
        }
        let record_path = PathBuf::from("library/sources")
            .join(sid)
            .join("record.yaml");
        if repo_root.join(&record_path).exists() {
            staging.add(&record_path);
        } else {
            staging
                .missing
                .push(record_path.to_string_lossy().replace('\\', "/"));
        }
    }
}

fn run_adapter(repo_root: &Path, run_dir: &Path, request: &Request) -> Result<i32> {
    let out_dir = run_dir.to_path_buf();
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    let request_path = run_dir.join("request.json");
    fs::write(&request_path, serde_json::to_string_pretty(request)?)
        .with_context(|| format!("writing {}", request_path.display()))?;

    println!("request: {}", request_path.display());
    println!("out dir: {}", out_dir.display());

    let mut child = Command::new("uv")
        .args(["run", "mag-render-adapter"])
        .arg(request_path.canonicalize()?)
        .arg(out_dir.canonicalize()?)
        .current_dir(repo_root)
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
    println!(
        "\nnext: read the PDF in {}; fix copy in the run finals or picks in edition.yaml and re-render; \
         `mag translate <run dir>` for the Spanish edition",
        out_dir.display()
    );

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
        assert!(
            parse_anchor_reply("fig-a :: Not A Heading\nfig-b :: NONE", &ids, &headings).is_err()
        );
        assert!(parse_anchor_reply("fig-a :: The Escalation", &ids, &headings).is_err());
    }
}
