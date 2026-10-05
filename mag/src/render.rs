use crate::model::kinds::RenderOperation;
use crate::model::manifest::art_slots;
use crate::model::shared::read_spec;
use crate::model::spec::{ArticleRow, EditionFile, TranslationFile};
use crate::typeset::layout::Outcome;
use crate::util::EditionId;
use anyhow::{bail, ensure, Context, Result};
use serde::Serialize;
use std::collections::HashSet;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

const SCHEMA_VERSION: u32 = 1;
const RENDERER_CONTRACT_VERSION: &str = "magazine-renderer/1";
const RENDERER: &str = "typst";
const DESIGN_TOML_PATH: &str = "design/covers/canto-vivo/design.toml";

#[derive(Default, Serialize)]
pub(crate) struct InputRow {
    #[serde(rename = "artifactId")]
    pub artifact_id: String,
    #[serde(rename = "sourcePath")]
    pub source_path: String,
    #[serde(rename = "targetPath")]
    pub target_path: String,
}

#[derive(Default, Serialize)]
pub(crate) struct Request {
    #[serde(rename = "schemaVersion")]
    pub schema_version: u32,
    #[serde(rename = "rendererContractVersion")]
    pub renderer_contract_version: String,
    pub operation: RenderOperation,
    #[serde(rename = "articleId", skip_serializing_if = "Option::is_none")]
    pub article_id: Option<String>,
    #[serde(rename = "editionId")]
    pub edition_id: String,
    #[serde(rename = "primaryLanguage")]
    pub primary_language: String,
    pub languages: Vec<String>,
    #[serde(rename = "publicationName")]
    pub publication_name: String,
    pub renderer: String,
    #[serde(rename = "artifactRoot")]
    pub artifact_root: String,
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

pub(crate) fn manuscript_headings(path: &Path) -> Vec<String> {
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
    let id = EditionId::resolve(Path::new("."), edition)?;
    Ok(Path::new("editions").join(id.as_str()))
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

fn print_summary(outcome: &Outcome, out_dir: &Path) {
    for info in &outcome.layouts {
        println!("  [{}] totalPages={}", info.language, info.total_pages);
        for (aid, pages) in &info.article_pages {
            println!("    articlePages.{aid} = {pages}");
        }
        println!("    criticResult: {:?}", info.critic_result);
    }
    println!("  files:");
    for f in &outcome.files {
        println!("    {}: {}", f.kind, f.path);
    }
    println!("  out dir: {}", out_dir.display());
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
        help = "Comma-separated languages to render (default: primary language plus every translations/<lang>/edition.yaml present)"
    )]
    pub langs: Option<String>,
    #[arg(
        long,
        help = "Run dir whose finals to render (default: newest complete run, else committed files)"
    )]
    pub run: Option<String>,
    #[arg(
        long = "no-legibility",
        help = "Render without the tesseract legibility check: figure layouts stay as declared"
    )]
    pub no_legibility: bool,
}

pub(crate) struct EditionInputs {
    pub(crate) dir: PathBuf,
    pub(crate) yaml_path: PathBuf,
    pub(crate) yaml: EditionFile,
    pub(crate) id: String,
    pub(crate) article_ids: Vec<String>,
}

pub(crate) fn load_edition(edition: &str) -> Result<EditionInputs> {
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
    let request = request(args, &repo_root)?;
    run_typst(&repo_root, &render_dir, &request, !args.no_legibility)
}

pub(crate) fn request(args: &RenderArgs, repo_root: &Path) -> Result<Request> {
    let operation = args.operation;
    let article = args.article.as_deref();
    let langs = args.langs.as_deref();
    let run_flag = args.run.as_deref();
    if operation == RenderOperation::MeasureArticle && article.is_none() {
        bail!("measure_article requires --article");
    }

    let repo_root = repo_root.to_path_buf();
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
    if let Some(run) = &content_run {
        refuse_unresolved_anchors(run, &edition_yaml, &args.edition)?;
    }
    staging.add(&edition_yaml_path);
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
    let primary_language = edition_yaml
        .language
        .clone()
        .unwrap_or_else(|| "en".to_string());
    let languages = translation_languages(&edition_dir, &primary_language, langs)?;
    stage_translation(&mut staging, &edition_dir, &repo_root, &languages)?;
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
        primary_language,
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
    let outcome = crate::typeset::run_request(repo_root, render_dir, request, legibility)?;
    let result = render_dir.join("result.json");
    fs::write(&result, serde_json::to_string_pretty(&outcome)? + "\n")
        .with_context(|| format!("writing {}", result.display()))?;
    let out_dir = render_dir.join(&request.primary_language);
    print_summary(&outcome, &out_dir);
    close_typst(
        &outcome.warnings,
        &out_dir,
        &mut std::io::stdout(),
        &mut std::io::stderr(),
    )?;
    Ok(0)
}

fn close_typst(
    warnings: &[String],
    out_dir: &Path,
    out: &mut dyn Write,
    err: &mut dyn Write,
) -> std::io::Result<()> {
    for warning in warnings {
        writeln!(err, "{warning}")?;
    }
    writeln!(out, "{}", next_step(out_dir))
}

pub(crate) fn pick_content_run(
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

fn refuse_unresolved_anchors(run: &Path, edition_yaml: &EditionFile, edition: &str) -> Result<()> {
    let stale = crate::anchors::unresolved(run, edition_yaml);
    ensure!(
        stale.is_empty(),
        "{} figure anchor(s) match no heading of {}:\n  {}\nfix them first: {}",
        stale.len(),
        run.display(),
        stale
            .iter()
            .map(|u| u.line.as_str())
            .collect::<Vec<_>>()
            .join("\n  "),
        crate::anchors::advice(&stale, edition, run)
    );
    Ok(())
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

fn translation_languages(
    edition_dir: &Path,
    primary: &str,
    langs: Option<&str>,
) -> Result<Vec<String>> {
    let present = |language: &str| {
        edition_dir
            .join("translations")
            .join(language)
            .join("edition.yaml")
            .exists()
    };
    let found = || {
        let mut names: Vec<String> = fs::read_dir(edition_dir.join("translations"))
            .into_iter()
            .flatten()
            .flatten()
            .filter(|e| e.path().join("edition.yaml").exists())
            .filter_map(|e| e.file_name().into_string().ok())
            .collect();
        names.sort();
        names
    };
    let others = match langs {
        Some(list) => list
            .split(',')
            .map(str::trim)
            .filter(|l| !l.is_empty() && *l != primary)
            .map(str::to_string)
            .collect(),
        None => found(),
    };
    if let Some(missing) = others.iter().find(|l| !present(l)) {
        bail!("--langs {missing}: no translations/{missing}/edition.yaml");
    }
    let mut languages = vec![primary.to_string()];
    for language in others {
        if !languages.contains(&language) {
            languages.push(language);
        }
    }
    Ok(languages)
}

fn stage_translation(
    staging: &mut Staging,
    edition_dir: &Path,
    repo_root: &Path,
    languages: &[String],
) -> Result<()> {
    for language in languages.iter().skip(1) {
        let translation_dir = edition_dir.join("translations").join(language);
        let translation_yaml_path = translation_dir.join("edition.yaml");
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
    }
    Ok(())
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
    use super::{close_typst, next_step, translation_languages, Staging};
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
        let warnings = ["WARNING: verbatim article past the page cap".to_string()];
        let (mut out, mut err) = (Vec::new(), Vec::new());
        close_typst(&warnings, Path::new("r/en"), &mut out, &mut err).unwrap();
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
    fn languages_come_from_the_translations_present_and_the_declared_primary() {
        let dir = std::env::temp_dir().join(format!("mag-langs-{}", std::process::id()));
        for language in ["fr", "es"] {
            std::fs::create_dir_all(dir.join("translations").join(language)).unwrap();
            std::fs::write(
                dir.join("translations").join(language).join("edition.yaml"),
                "",
            )
            .unwrap();
        }
        std::fs::create_dir_all(dir.join("translations/empty")).unwrap();
        assert_eq!(
            translation_languages(&dir, "en", None).unwrap(),
            ["en", "es", "fr"]
        );
        assert_eq!(
            translation_languages(&dir, "es", None).unwrap(),
            ["es", "fr"]
        );
        assert_eq!(
            translation_languages(&dir, "en", Some("fr")).unwrap(),
            ["en", "fr"]
        );
        assert_eq!(
            translation_languages(&dir, "en", Some("en")).unwrap(),
            ["en"]
        );
        assert_eq!(translation_languages(&dir, "en", Some("")).unwrap(), ["en"]);
        let err = translation_languages(&dir, "en", Some("fr,de")).unwrap_err();
        assert!(err.to_string().contains("de"), "{err}");
        std::fs::remove_dir_all(&dir).unwrap();
        assert_eq!(translation_languages(&dir, "en", None).unwrap(), ["en"]);
    }
}
