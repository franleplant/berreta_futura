use crate::caller::{Caller, ModelSpec};
use crate::model::kinds::RenderOperation;
use crate::model::manifest::art_slots;
use crate::model::shared::read_spec;
use crate::model::spec::{ArticleRow, EditionFile, TranslationFile};
use anyhow::{anyhow, bail, ensure, Context, Result};
use serde::Serialize;
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

const SCHEMA_VERSION: u32 = 1;
const RENDERER_CONTRACT_VERSION: &str = "magazine-renderer/1";
const RENDERER: &str = "typst";
const DESIGN_TOML_PATH: &str = "design/covers/canto-vivo/design.toml";

#[derive(Serialize)]
pub(crate) struct InputRow {
    #[serde(rename = "artifactId")]
    artifact_id: String,
    #[serde(rename = "sourcePath")]
    pub source_path: String,
    #[serde(rename = "targetPath")]
    pub target_path: String,
}

#[derive(Serialize)]
pub(crate) struct Request {
    #[serde(rename = "schemaVersion")]
    schema_version: u32,
    #[serde(rename = "rendererContractVersion")]
    renderer_contract_version: String,
    operation: RenderOperation,
    #[serde(rename = "articleId", skip_serializing_if = "Option::is_none")]
    article_id: Option<String>,
    #[serde(rename = "editionId")]
    pub edition_id: String,
    #[serde(rename = "primaryLanguage")]
    pub primary_language: String,
    pub languages: Vec<String>,
    #[serde(rename = "publicationName")]
    pub publication_name: String,
    renderer: String,
    #[serde(rename = "artifactRoot")]
    artifact_root: String,
    pub inputs: Vec<InputRow>,
}

struct Staging {
    repo_root: PathBuf,
    seen: HashSet<String>,
    rows: Vec<InputRow>,
    missing: Vec<String>,
    refused: Vec<String>,
}

impl Staging {
    fn new(repo_root: PathBuf) -> Self {
        Self {
            repo_root,
            seen: HashSet::new(),
            rows: Vec::new(),
            missing: Vec::new(),
            refused: Vec::new(),
        }
    }

    fn add(&mut self, rel: &Path) {
        let target = rel.to_string_lossy().replace('\\', "/");
        if !self.seen.insert(target.clone()) || self.refuse(rel) {
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

    fn refuse(&mut self, target: &Path) -> bool {
        let unsafe_path = !crate::typeset::contained(target);
        if unsafe_path {
            self.refused
                .push(target.to_string_lossy().replace('\\', "/"));
        }
        unsafe_path
    }

    fn add_mapped(&mut self, source: &Path, target: &Path) {
        let target_text = target.to_string_lossy().replace('\\', "/");
        if !self.seen.insert(target_text.clone()) || self.refuse(target) {
            return;
        }
        let target = target_text;
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
                    .is_some_and(|n| n.to_string_lossy().starts_with("run-"))
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

pub(crate) fn resolve_edition_dir(edition: &str) -> Result<PathBuf> {
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

pub(crate) fn magazine_toml(repo_root: &Path) -> Result<toml::Table> {
    let path = repo_root.join("magazine.toml");
    fs::read_to_string(&path)
        .with_context(|| format!("reading {}", path.display()))?
        .parse()
        .with_context(|| format!("parsing {}", path.display()))
}

pub(crate) fn publication_name(repo_root: &Path) -> Result<String> {
    magazine_toml(repo_root)?
        .get("publication")
        .and_then(|table| table.get("name"))
        .and_then(toml::Value::as_str)
        .map(str::to_string)
        .context("magazine.toml needs [publication] name")
}

fn stage_article_figures(staging: &mut Staging, article: &ArticleRow) -> Result<()> {
    for figure in &article.figures {
        for (field, value) in [("source_id", &figure.source_id), ("path", &figure.path)] {
            ensure!(
                !value.is_empty(),
                "article '{}' figure '{}' missing {field}",
                article.id,
                figure.id
            );
        }
        staging.add(
            &PathBuf::from("library/sources")
                .join(&figure.source_id)
                .join(&figure.path),
        );
    }
    Ok(())
}

fn stage_article_extracts(staging: &mut Staging, article: &ArticleRow) -> Result<()> {
    for extract in &article.extracts {
        ensure!(
            !extract.source_id.is_empty(),
            "article '{}' extract '{}' missing source_id",
            article.id,
            extract.id
        );
        staging.add(
            &PathBuf::from("library/sources")
                .join(&extract.source_id)
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
                .map_or_else(|| "?".to_string(), std::string::ToString::to_string);
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

fn pending_figures(article: &ArticleRow, headings: &[String]) -> PendingFigures {
    let mut pending = PendingFigures {
        idx: Vec::new(),
        ids: Vec::new(),
        anchors: Vec::new(),
        meta: String::new(),
    };
    for (i, figure) in article.figures.iter().enumerate() {
        let anchor = figure.anchor.as_str();
        if anchor.is_empty() || anchor == "__opener__" || headings.iter().any(|h| h == anchor) {
            continue;
        }
        pending.meta += &format!("- id: {}\n", figure.id);
        for (label, value) in [
            ("caption", &figure.caption),
            ("alt_text", &figure.alt_text),
            ("previous_section", &figure.anchor),
        ] {
            if !value.is_empty() {
                pending.meta += &format!("  {label}: {value}\n");
            }
        }
        pending.idx.push(i);
        pending.ids.push(figure.id.clone());
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
    article: &mut ArticleRow,
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

    let figs = &mut article.figures;
    let mut drop_idx: HashSet<usize> = HashSet::new();
    for ((&i, fig_id), resolution) in pending.idx.iter().zip(pending_ids).zip(resolutions) {
        let old = figs[i].anchor.clone();
        match resolution {
            Some(heading) => {
                println!("  re-anchored {article_id}:{fig_id} '{old}' -> '{heading}'");
                figs[i].anchor = heading;
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
                    .is_some_and(|s| s.trim().trim_start_matches('-').trim() == id)
            })
            .ok_or_else(|| anyhow!("reply has no `{id} :: <heading>` line"))?;
        let value = line
            .split_once("::")
            .map_or("", |(_, v)| v)
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
pub struct RenderArgs {
    pub edition: String,
    #[arg(
        long,
        value_enum,
        default_value_t = RenderOperation::RenderEdition,
        help = "What to run"
    )]
    pub operation: RenderOperation,
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
        long = "no-legibility",
        help = "Render without the tesseract legibility check: figure layouts stay as declared"
    )]
    pub no_legibility: bool,
}

struct EditionInputs {
    dir: PathBuf,
    yaml_path: PathBuf,
    yaml: EditionFile,
    id: String,
    article_ids: Vec<String>,
}

fn load_edition(edition: &str) -> Result<EditionInputs> {
    let dir = resolve_edition_dir(edition)?;
    let yaml_path = dir.join("edition.yaml");
    if !yaml_path.exists() {
        bail!("{} not found", yaml_path.display());
    }
    let yaml: EditionFile = read_spec(&yaml_path)?;
    ensure!(
        !yaml.articles.is_empty(),
        "edition.yaml missing 'articles' list"
    );
    let id = match yaml.id.as_str() {
        "" => dir.file_name().unwrap().to_string_lossy().to_string(),
        id => id.to_string(),
    };
    let article_ids = yaml
        .articles
        .iter()
        .filter(|article| !article.id.is_empty())
        .map(|article| article.id.clone())
        .collect();
    Ok(EditionInputs {
        dir,
        yaml_path,
        yaml,
        id,
        article_ids,
    })
}

pub fn run(args: &RenderArgs) -> Result<i32> {
    let repo_root = std::env::current_dir()
        .context("resolving current directory")?
        .canonicalize()
        .context("canonicalizing repo root")?;
    let edition_dir = resolve_edition_dir(&args.edition)?;
    let render_dir = edition_dir.join(format!("render-{}", crate::caller::now_stamp()));
    let request = request(args, &repo_root, &render_dir)?;
    run_typst(&repo_root, &render_dir, &request, !args.no_legibility)
}

pub(crate) fn request(args: &RenderArgs, repo_root: &Path, render_dir: &Path) -> Result<Request> {
    let operation = args.operation;
    let article = args.article.as_deref();
    let langs = args.langs.as_deref();
    let run_flag = args.run.as_deref();
    let no_model = args.no_model;
    if operation == RenderOperation::MeasureArticle && article.is_none() {
        bail!("measure_article requires --article");
    }

    let repo_root = repo_root.to_path_buf();
    let anchor_model = &ModelSpec::parse(&args.anchor_model)?;
    let EditionInputs {
        dir: edition_dir,
        yaml_path: edition_yaml_path,
        yaml: edition_yaml,
        id: edition_id,
        article_ids,
    } = load_edition(&args.edition)?;
    crate::picks::refuse_rounds(&edition_yaml, &args.edition)?;
    if let Some(wanted) = article.filter(|_| operation == RenderOperation::MeasureArticle) {
        if !article_ids.iter().any(|id| id == wanted) {
            bail!(
                "article '{wanted}' not found in edition '{edition_id}'; available: {}",
                article_ids.join(", ")
            );
        }
    }

    let content_run = pick_content_run(run_flag, &edition_dir, &article_ids, &edition_yaml)?;
    let mut staging = Staging::new(repo_root.clone());
    let staged_edition_path = match &content_run {
        Some(run) => patch_anchors(run, render_dir, &edition_yaml, anchor_model, no_model)?
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
    let languages = stage_translation(&mut staging, &edition_dir, &repo_root, langs)?;
    stage_source_records(&mut staging, &edition_yaml, &repo_root);
    for article in &edition_yaml.articles {
        stage_article_figures(&mut staging, article)?;
    }
    for article in &edition_yaml.articles {
        stage_article_extracts(&mut staging, article)?;
    }
    if !staging.refused.is_empty() {
        bail!(
            "edition '{edition_id}' names paths that are absolute or climb out with '..':\n  {}",
            staging.refused.join("\n  ")
        );
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

    Ok(Request {
        schema_version: SCHEMA_VERSION,
        renderer_contract_version: RENDERER_CONTRACT_VERSION.to_string(),
        operation,
        article_id: article
            .filter(|_| operation == RenderOperation::MeasureArticle)
            .map(str::to_string),
        edition_id,
        primary_language: edition_yaml
            .language
            .clone()
            .unwrap_or_else(|| "en".to_string()),
        languages,
        publication_name: publication_name(&repo_root)?,
        renderer: RENDERER.to_string(),
        artifact_root: repo_root.to_string_lossy().to_string(),
        inputs: staging.rows,
    })
}

fn run_typst(
    repo_root: &Path,
    render_dir: &Path,
    request: &Request,
    legibility: bool,
) -> Result<i32> {
    let json = serde_json::to_string(request)?;
    let value = crate::typeset::run_request(repo_root, render_dir, &json, legibility)?;
    let result = render_dir.join("result.json");
    fs::write(&result, serde_json::to_string_pretty(&value)? + "\n")
        .with_context(|| format!("writing {}", result.display()))?;
    let out_dir = render_dir.join(&request.primary_language);
    print_summary(&value, &out_dir);
    close_typst(
        &value,
        &out_dir,
        &mut std::io::stdout(),
        &mut std::io::stderr(),
    )?;
    Ok(0)
}

fn close_typst(
    value: &serde_json::Value,
    out_dir: &Path,
    out: &mut dyn Write,
    err: &mut dyn Write,
) -> std::io::Result<()> {
    for warning in value["warnings"].as_array().into_iter().flatten() {
        writeln!(err, "{}", warning.as_str().unwrap_or_default())?;
    }
    writeln!(out, "{}", next_step(out_dir))
}

fn pick_content_run(
    run_flag: Option<&str>,
    edition_dir: &Path,
    article_ids: &[String],
    edition_yaml: &EditionFile,
) -> Result<Option<PathBuf>> {
    let needs_editorial = edition_yaml.editorial.is_some();
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
    edition_yaml: &EditionFile,
    anchor_model: &ModelSpec,
    no_model: bool,
) -> Result<Option<PathBuf>> {
    let mut scans: HashMap<&str, (Vec<String>, PendingFigures)> = HashMap::new();
    let mut stale: Vec<String> = Vec::new();
    for article in edition_yaml.articles.iter().filter(|a| !a.id.is_empty()) {
        let id = article.id.as_str();
        let headings = manuscript_headings(&run.join("articles").join(id).join("final.md"));
        let pending = pending_figures(article, &headings);
        for (fig_id, anchor) in pending.ids.iter().zip(&pending.anchors) {
            stale.push(format!("{id}:{fig_id} (anchor '{anchor}')"));
        }
        scans.insert(id, (headings, pending));
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
    for article in &mut patched.articles {
        let id = article.id.clone();
        let Some((headings, pending)) = scans.get(id.as_str()) else {
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
    fs::write(&patched_path, serde_norway::to_string(&patched)?)?;
    Ok(Some(patched_path))
}

fn stage_manuscripts(
    staging: &mut Staging,
    edition_yaml: &EditionFile,
    edition_dir: &Path,
    content_run: Option<&Path>,
) {
    let mut stage = |declared: PathBuf, from_run: PathBuf| match content_run {
        Some(run) => staging.add_mapped(&run.join(from_run), &declared),
        None => staging.add(&declared),
    };
    if let Some(editorial) = &edition_yaml.editorial {
        stage(
            resolve_field(editorial, edition_dir),
            PathBuf::from("editorial/final.md"),
        );
    }
    for article in &edition_yaml.articles {
        if !article.id.is_empty() && !article.manuscript.is_empty() {
            stage(
                resolve_field(&article.manuscript, edition_dir),
                PathBuf::from("articles").join(&article.id).join("final.md"),
            );
        }
    }
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

fn stage_art(staging: &mut Staging, edition_yaml: &EditionFile, edition_dir: &Path) {
    for (_, path) in art_slots(edition_yaml) {
        staging.add(&resolve_field(&path, edition_dir));
    }
}

fn stage_translation(
    staging: &mut Staging,
    edition_dir: &Path,
    repo_root: &Path,
    langs: Option<&str>,
) -> Result<Vec<String>> {
    let translation_dir = edition_dir.join("translations/es");
    let translation_yaml_path = translation_dir.join("edition.yaml");
    let has_translation = translation_yaml_path.exists()
        && langs.is_none_or(|l| l.split(',').any(|x| x.trim() == "es"));
    if !has_translation {
        return Ok(vec!["en".to_string()]);
    }
    let translation_yaml: TranslationFile = read_spec(&translation_yaml_path)?;
    staging.add(&translation_yaml_path);
    stage_source_codes(staging, &translation_dir, repo_root);
    if let Some(editorial) = &translation_yaml.editorial {
        staging.add(&resolve_field(&editorial.path, &translation_dir));
    }
    for article in translation_yaml.articles.iter().flatten() {
        if !article.manuscript.is_empty() {
            staging.add(&resolve_field(&article.manuscript, &translation_dir));
        }
    }
    Ok(vec!["en".to_string(), "es".to_string()])
}

fn stage_source_records(staging: &mut Staging, edition_yaml: &EditionFile, repo_root: &Path) {
    let per_article = edition_yaml.articles.iter().flat_map(|a| &a.source_ids);
    let mut seen: HashSet<&String> = HashSet::new();
    for sid in edition_yaml.sources.iter().chain(per_article) {
        if !seen.insert(sid) {
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

fn next_step(pdf_dir: &Path) -> String {
    format!(
        "\nnext: read the PDF in {}; fix copy in the run finals or picks in edition.yaml and re-render; \
         `mag translate <run dir>` for the Spanish edition; `mag epub <edition>` packages the approved issue for Apple Books",
        pdf_dir.display()
    )
}

#[cfg(test)]
mod tests {
    use super::{close_typst, next_step, parse_anchor_reply, Staging};
    use std::path::{Path, PathBuf};

    #[test]
    fn staging_refuses_parent_and_absolute_targets_without_recording_them() {
        let mut staging = Staging::new(PathBuf::from("/repo"));
        staging.add(Path::new("library/../../etc/passwd"));
        staging.add(Path::new("/etc/passwd"));
        staging.add_mapped(Path::new("a"), Path::new("../b"));
        assert_eq!(staging.refused.len(), 3);
        assert!(staging.rows.is_empty() && staging.missing.is_empty());
    }

    #[test]
    fn next_step_points_to_translate() {
        let line = next_step(Path::new("editions/010/render-x/en"));
        assert!(line.contains("editions/010/render-x/en"));
        assert!(line.contains("`mag translate <run dir>`"));
    }

    #[test]
    fn the_typst_leg_prints_its_warnings_and_the_next_step() {
        let value =
            serde_json::json!({"warnings": ["WARNING: verbatim article past the page cap"]});
        let (mut out, mut err) = (Vec::new(), Vec::new());
        close_typst(&value, Path::new("r/en"), &mut out, &mut err).unwrap();
        assert_eq!(
            String::from_utf8(out).unwrap(),
            next_step(Path::new("r/en")) + "\n"
        );
        assert_eq!(
            String::from_utf8(err).unwrap(),
            "WARNING: verbatim article past the page cap\n"
        );
    }

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
