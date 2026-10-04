use super::doc::{block_signature, parse_publication_document, Block};
use super::kinds::{ContentMode, TailArtFit};
use super::records::{
    blanks, localize_extracts, localize_figures, resolve_extracts, resolve_figures, Extract,
    ExtractRequest, Figure, FigureRequest,
};
use super::shared::{normalize, quoted, read_spec, safe_project_path, Result, ValidationError};
use super::spec::{
    ArticleRow, Cover, EditionFile, Format, OpenerArtRow, SectionRow, SourceRecord,
    TranslatedArticleRow, TranslationFile,
};
use regex::Regex;
use serde_norway::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Component, Path, PathBuf};
use std::sync::LazyLock;

pub const SECTION_KINDS: [&str; 8] = [
    "original_editorial",
    "source_introduction",
    "original_synthesis",
    "source_record",
    "production_note",
    "glossary",
    "try_it",
    "cheat_sheet",
];

const HOUSE_BYLINES: [&str; 4] = [
    "editors",
    "the editors",
    "editorial team",
    "the editorial team",
];

const OPENER_VARIANTS: [&str; 3] = ["edge_medallion", "split_axis", "stepped_title"];

const ILLUSTRATED_OPENER: &str = "illustrated_paper_spots_v1";

const KEY_IDEAS_WORD_BUDGET: usize = 90;

pub type Records = BTreeMap<String, SourceRecord>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArticleOpenerArt {
    pub path: PathBuf,
    pub alt_text: String,
    pub credit: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Article {
    pub id: String,
    pub title: String,
    pub short_title: String,
    pub display_emphasis: String,
    pub opener_variant: String,
    pub author: String,
    pub author_note: String,
    pub source_ids: Vec<String>,
    pub manuscript: PathBuf,
    pub content_mode: ContentMode,
    pub figures: Vec<Figure>,
    pub minimum_reader_pages: i64,
    pub tail_art: Option<PathBuf>,
    pub source_url: Option<String>,
    pub opener_art: Option<ArticleOpenerArt>,
    pub key_ideas: Vec<String>,
    pub dateline: Option<String>,
    pub extracts: Vec<Extract>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Section {
    pub kind: String,
    pub title: String,
    pub path: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Editorial {
    pub path: PathBuf,
    pub title: String,
    pub byline: String,
    pub label: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClosingPlate {
    pub title: String,
    pub art_path: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Edition {
    pub id: String,
    pub publication_name: String,
    pub issue_number: String,
    pub title: String,
    pub subtitle: String,
    pub publication_date: String,
    pub language: String,
    pub locale: String,
    pub editorial: Option<Editorial>,
    pub articles: Vec<Article>,
    pub sections: Vec<Section>,
    pub cover: Cover,
    pub cover_art: Option<PathBuf>,
    pub closing_plates: Vec<ClosingPlate>,
    pub format: Format,
    pub tail_art_fit: TailArtFit,
}

pub struct LoadOptions<'a> {
    pub publication_name: &'a str,
    pub source_records: Option<&'a Records>,
    pub allow_missing_art: bool,
    pub allow_unanchored_figures: bool,
}

impl Default for LoadOptions<'_> {
    fn default() -> Self {
        Self {
            publication_name: "Magazine",
            source_records: None,
            allow_missing_art: false,
            allow_unanchored_figures: false,
        }
    }
}

struct ArticleContext<'a> {
    root: &'a Path,
    edition_dir: &'a Path,
    known_sources: &'a BTreeSet<String>,
    illustrated: bool,
    options: &'a LoadOptions<'a>,
}

fn gather<T>(result: Result<T>, errors: &mut Vec<String>) -> Option<T> {
    result
        .map_err(|ValidationError(messages)| errors.extend(messages))
        .ok()
}

fn clean(value: Option<&str>) -> String {
    value.unwrap_or_default().trim().to_string()
}

fn unknown_sources(ids: &[String], known: &BTreeSet<String>) -> Vec<String> {
    let unknown: BTreeSet<&String> = ids.iter().filter(|id| !known.contains(*id)).collect();
    unknown.into_iter().cloned().collect()
}

pub fn load_edition(
    root: &Path,
    edition_id: &str,
    known_sources: &BTreeSet<String>,
    options: &LoadOptions,
) -> Result<Edition> {
    let manifest_path = root.join("editions").join(edition_id).join("edition.yaml");
    if !manifest_path.is_file() {
        return Err(ValidationError(vec![format!(
            "Edition manifest not found: {}",
            manifest_path.display()
        )]));
    }
    let spec: EditionFile = read_spec(&manifest_path)?;
    let mut errors: Vec<String> = Vec::new();
    let illustrated = check_edition_header(&spec, edition_id, known_sources, &mut errors);
    let edition_dir = manifest_path
        .parent()
        .expect("the manifest sits inside the edition directory")
        .to_path_buf();
    let context = ArticleContext {
        root,
        edition_dir: &edition_dir,
        known_sources,
        illustrated,
        options,
    };
    let articles = load_articles(&context, &spec.articles, &mut errors);
    let editorial = load_edition_editorial(root, &edition_dir, &spec, &mut errors);
    let sections = load_sections(root, &edition_dir, &spec.sections, &mut errors);
    let cover_art = load_cover_art(root, &edition_dir, &spec.cover, &mut errors);
    let closing_plates = load_closing_plates(&context, &spec.closing_plates, &mut errors);
    check_unique_art(&spec, &mut errors);
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    let language = spec.language.filter(|text| !text.is_empty());
    let language = language.unwrap_or_else(|| "en".to_string());
    Ok(Edition {
        id: spec.id,
        publication_name: options.publication_name.to_string(),
        issue_number: spec.issue_number,
        title: spec.title,
        subtitle: clean(spec.subtitle.as_deref()),
        publication_date: spec.publication_date,
        locale: spec
            .locale
            .filter(|text| !text.is_empty())
            .unwrap_or_else(|| language.clone()),
        language,
        editorial,
        articles,
        sections,
        cover: spec.cover,
        cover_art,
        closing_plates,
        format: spec.format,
        tail_art_fit: spec.tail_art_fit.unwrap_or_default(),
    })
}

fn check_edition_header(
    spec: &EditionFile,
    edition_id: &str,
    known_sources: &BTreeSet<String>,
    errors: &mut Vec<String>,
) -> bool {
    let missing = blanks(&[
        ("id", spec.id.is_empty()),
        ("issue_number", spec.issue_number.is_empty()),
        ("title", spec.title.is_empty()),
        ("publication_date", spec.publication_date.is_empty()),
    ]);
    errors.extend(
        missing
            .iter()
            .map(|key| format!("Edition missing required field: {key}")),
    );
    if spec.id != edition_id {
        errors.push(format!(
            "Edition id {} does not match directory {}",
            quoted(&spec.id),
            quoted(edition_id)
        ));
    }
    if spec.sources.iter().any(|id| id.trim().is_empty()) {
        errors.push("Edition sources must contain non-empty source id strings".to_string());
    } else {
        let unknown = unknown_sources(&spec.sources, known_sources);
        if !unknown.is_empty() {
            errors.push(format!(
                "Edition references unknown sources: {}",
                unknown.join(", ")
            ));
        }
    }
    if spec.sections.is_empty() && spec.articles.is_empty() {
        errors.push("Edition requires either sections or articles".to_string());
    }
    let opener = clean(spec.format.article_opener.as_deref());
    if !opener.is_empty() && opener != ILLUSTRATED_OPENER {
        errors.push(format!(
            "Edition has invalid format.article_opener: {opener}"
        ));
    }
    let illustrated = opener == ILLUSTRATED_OPENER;
    if illustrated && clean(spec.art_direction_path.as_deref()).is_empty() {
        errors.push(format!(
            "Edition format.article_opener {ILLUSTRATED_OPENER} requires art_direction_path"
        ));
    }
    illustrated
}

fn load_articles(
    context: &ArticleContext,
    rows: &[ArticleRow],
    errors: &mut Vec<String>,
) -> Vec<Article> {
    let mut ids: BTreeSet<&str> = BTreeSet::new();
    let mut articles: Vec<Article> = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        if let Some(article) = load_article(context, index, row, &mut ids, errors) {
            articles.push(article);
        }
    }
    articles
}

fn article_label(index: usize, row: &ArticleRow) -> String {
    match row.id.is_empty() {
        true => format!("Article {}", index + 1),
        false => format!("Article {}", row.id),
    }
}

fn article_identity(index: usize, row: &ArticleRow, errors: &mut Vec<String>) -> Option<String> {
    let label = article_label(index, row);
    let missing = blanks(&[
        ("id", row.id.is_empty()),
        ("title", row.title.is_empty()),
        ("short_title", row.short_title.is_empty()),
        ("opener_variant", row.opener_variant.is_empty()),
        ("author", row.author.is_empty()),
        ("source_ids", row.source_ids.is_empty()),
        ("manuscript", row.manuscript.is_empty()),
    ]);
    if !missing.is_empty() {
        errors.push(format!("{label} missing: {}", missing.join(", ")));
        return None;
    }
    if row.id.trim().is_empty() {
        errors.push(format!(
            "Article {} id must be a non-empty string",
            index + 1
        ));
        return None;
    }
    if row.source_ids.iter().any(|id| id.trim().is_empty()) {
        errors.push(format!(
            "{label} source_ids must be a non-empty list of strings"
        ));
        return None;
    }
    Some(label)
}

fn check_note_length(label: &str, note: &str, errors: &mut Vec<String>) {
    if note.contains('\n') || note.chars().count() > 160 {
        errors.push(format!(
            "{label} author_note must be a single line of at most 160 characters"
        ));
    }
}

fn article_author_note(label: &str, row: &ArticleRow, errors: &mut Vec<String>) -> (String, bool) {
    let author_note = clean(row.author_note.as_deref());
    check_note_length(label, &author_note, errors);
    let house_byline = HOUSE_BYLINES.contains(&row.author.trim().to_lowercase().as_str());
    if !author_note.is_empty() && house_byline {
        errors.push(format!(
            "{label} must omit author_note for the self-explanatory house byline {}",
            quoted(&row.author)
        ));
    }
    (author_note, house_byline)
}

fn article_paths(
    context: &ArticleContext,
    row: &ArticleRow,
    errors: &mut Vec<String>,
) -> Option<(PathBuf, Option<PathBuf>)> {
    let (root, dir) = (context.root, context.edition_dir);
    let manuscript = gather(edition_path(root, dir, &row.manuscript, true), errors)?;
    let tail_art = match row.tail_art_path.as_deref().filter(|path| !path.is_empty()) {
        Some(path) => {
            let must_exist = !context.options.allow_missing_art;
            Some(gather(edition_path(root, dir, path, must_exist), errors)?)
        }
        None => None,
    };
    Some((manuscript, tail_art))
}

fn article_opener_art(
    context: &ArticleContext,
    label: &str,
    row: &ArticleRow,
    errors: &mut Vec<String>,
) -> Option<ArticleOpenerArt> {
    let Some(art) = row
        .opener_art
        .as_ref()
        .filter(|art| **art != OpenerArtRow::default())
    else {
        errors.push(format!(
            "{label} requires a non-empty opener_art mapping for format.article_opener {ILLUSTRATED_OPENER}"
        ));
        return None;
    };
    let missing = blanks(&[
        ("path", art.path.trim().is_empty()),
        ("alt_text", art.alt_text.trim().is_empty()),
        ("credit", art.credit.trim().is_empty()),
    ]);
    if !missing.is_empty() {
        errors.push(format!(
            "{label} opener_art requires non-empty {}",
            missing.join(", ")
        ));
        return None;
    }
    let must_exist = !context.options.allow_missing_art;
    let path = edition_path(context.root, context.edition_dir, &art.path, must_exist);
    Some(ArticleOpenerArt {
        path: gather(path, errors)?,
        alt_text: art.alt_text.trim().to_string(),
        credit: art.credit.trim().to_string(),
    })
}

fn check_illustrated_opener(label: &str, manuscript: &Path, errors: &mut Vec<String>) {
    let text = std::fs::read_to_string(manuscript).map_err(|error| error.to_string());
    let document =
        text.and_then(|text| parse_publication_document(&text).map_err(|error| error.to_string()));
    match document {
        Err(error) => errors.push(format!(
            "{label} manuscript cannot be parsed as a publication document: {error}"
        )),
        Ok(document) => {
            if !matches!(document.blocks.first(), Some(Block::Paragraph(_))) {
                errors.push(format!(
                    "{label} first manuscript block must be a paragraph for format.article_opener {ILLUSTRATED_OPENER}"
                ));
            }
        }
    }
}

fn check_titles(
    label: &str,
    title: &str,
    short_title: &str,
    display_emphasis: &str,
    errors: &mut Vec<String>,
) {
    let title = title.to_lowercase();
    if !display_emphasis.is_empty() && !title.contains(&display_emphasis.to_lowercase()) {
        errors.push(format!(
            "{label} display_emphasis must occur in its localized title"
        ));
    }
    if short_title.contains('\n') || short_title.chars().count() > 40 {
        errors.push(format!(
            "{label} short_title must be a single line of at most 40 characters"
        ));
    } else if !title.contains(&short_title.to_lowercase()) {
        errors.push(format!(
            "{label} short_title must occur in its localized title"
        ));
    }
}

fn article_display(
    label: &str,
    row: &ArticleRow,
    errors: &mut Vec<String>,
) -> (ContentMode, i64, String, String) {
    let content_mode = row.content_mode.unwrap_or_else(|| {
        errors.push(format!(
            "{label} has invalid content_mode: missing, expected one of {}",
            ContentMode::names()
        ));
        ContentMode::Article
    });
    let pages = row.minimum_reader_pages.unwrap_or(1);
    if !(1..=7).contains(&pages) {
        errors.push(format!(
            "{label} minimum_reader_pages must be an integer from 1 to 7"
        ));
    }
    let display_emphasis = clean(row.display_emphasis.as_deref());
    let short_title = row.short_title.trim().to_string();
    check_titles(label, &row.title, &short_title, &display_emphasis, errors);
    if !OPENER_VARIANTS.contains(&row.opener_variant.trim()) {
        errors.push(format!(
            "{label} has invalid opener_variant: {}",
            row.opener_variant.trim()
        ));
    }
    (content_mode, pages, display_emphasis, short_title)
}

fn load_article<'a>(
    context: &ArticleContext,
    index: usize,
    row: &'a ArticleRow,
    ids: &mut BTreeSet<&'a str>,
    errors: &mut Vec<String>,
) -> Option<Article> {
    let label = article_identity(index, row, errors)?;
    let (author_note, house_byline) = article_author_note(&label, row, errors);
    if !ids.insert(&row.id) {
        errors.push(format!("Duplicate article id: {}", row.id));
    }
    let unknown = unknown_sources(&row.source_ids, context.known_sources);
    if !unknown.is_empty() {
        errors.push(format!(
            "{label} references unknown sources: {}",
            unknown.join(", ")
        ));
    }
    let (manuscript, tail_art) = article_paths(context, row, errors)?;
    let mut opener_art = None;
    if context.illustrated {
        if author_note.is_empty() && !house_byline {
            errors.push(format!(
                "{label} requires author_note for format.article_opener {ILLUSTRATED_OPENER}"
            ));
        }
        opener_art = article_opener_art(context, &label, row, errors);
        check_illustrated_opener(&label, &manuscript, errors);
    }
    let key_ideas = gather(key_ideas(&label, row.key_ideas.as_deref()), errors).unwrap_or_default();
    if !key_ideas.is_empty() && tail_art.is_some() {
        errors.push(format!(
            "{label} declares both key_ideas and tail_art_path; an article closes with one object, not two -- drop whichever the piece needs less"
        ));
    }
    let (content_mode, minimum_reader_pages, display_emphasis, short_title) =
        article_display(&label, row, errors);
    check_verbatim_title(
        &label,
        row,
        content_mode,
        context.options.source_records,
        errors,
    );
    let allow_unanchored = context.options.allow_unanchored_figures;
    let figures = FigureRequest {
        root: context.root,
        article_id: &row.id,
        article_source_ids: &row.source_ids,
        manuscript: &manuscript,
        allow_unanchored,
        verbatim: content_mode == ContentMode::Verbatim,
    };
    let extracts = ExtractRequest {
        root: context.root,
        article_id: &row.id,
        article_source_ids: &row.source_ids,
        manuscript: &manuscript,
        allow_unanchored,
    };
    let figures = gather(resolve_figures(&figures, &row.figures), errors).unwrap_or_default();
    let extracts = gather(resolve_extracts(&extracts, &row.extracts), errors).unwrap_or_default();
    let records = context.options.source_records;
    Some(Article {
        id: row.id.clone(),
        title: row.title.clone(),
        short_title,
        display_emphasis,
        opener_variant: row.opener_variant.trim().to_string(),
        author: row.author.clone(),
        author_note,
        source_url: primary_source_url(&row.source_ids, records),
        dateline: representative_dateline(&row.source_ids, records),
        source_ids: row.source_ids.clone(),
        manuscript,
        content_mode,
        figures,
        minimum_reader_pages,
        tail_art,
        opener_art,
        key_ideas,
        extracts,
    })
}

fn check_verbatim_title(
    label: &str,
    row: &ArticleRow,
    content_mode: ContentMode,
    source_records: Option<&Records>,
    errors: &mut Vec<String>,
) {
    if content_mode != ContentMode::Verbatim {
        return;
    }
    let [source_id] = row.source_ids.as_slice() else {
        errors.push(format!(
            "{label} verbatim articles carry exactly one source"
        ));
        return;
    };
    let Some(record) = source_records.and_then(|records| records.get(source_id)) else {
        return;
    };
    if row.title.trim() != record.title.trim() {
        errors.push(format!(
            "{label} verbatim title must stay the captured source title {}",
            quoted(&record.title)
        ));
    }
}

fn load_edition_editorial(
    root: &Path,
    edition_dir: &Path,
    spec: &EditionFile,
    errors: &mut Vec<String>,
) -> Option<Editorial> {
    let declared = spec.editorial.as_deref().filter(|path| !path.is_empty())?;
    let path =
        edition_path(root, edition_dir, declared, true).and_then(|path| load_editorial(&path));
    gather(path, errors)
}

fn load_sections(
    root: &Path,
    edition_dir: &Path,
    rows: &[SectionRow],
    errors: &mut Vec<String>,
) -> Vec<Section> {
    let mut sections: Vec<Section> = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        if let Some(section) = load_section(root, edition_dir, index, row, errors) {
            sections.push(section);
        }
    }
    sections
}

fn load_section(
    root: &Path,
    edition_dir: &Path,
    index: usize,
    row: &SectionRow,
    errors: &mut Vec<String>,
) -> Option<Section> {
    if row.kind.is_empty() || row.path.is_empty() {
        errors.push(format!("Section {} requires kind and path", index + 1));
        return None;
    }
    if row.kind.trim().to_lowercase() == "colophon" {
        errors.push("Colophon sections are no longer supported".to_string());
        return None;
    }
    if !SECTION_KINDS.contains(&row.kind.as_str()) {
        errors.push(format!(
            "Section {} has unknown kind {}; the known kinds are {}",
            index + 1,
            quoted(&row.kind),
            SECTION_KINDS.join(", ")
        ));
        return None;
    }
    let path = gather(edition_path(root, edition_dir, &row.path, true), errors)?;
    let title = match row.title.as_deref().filter(|title| !title.is_empty()) {
        Some(title) => title.to_string(),
        None => section_title(&row.kind),
    };
    Some(Section {
        kind: row.kind.clone(),
        title,
        path,
    })
}

fn load_cover_art(
    root: &Path,
    edition_dir: &Path,
    cover: &Cover,
    errors: &mut Vec<String>,
) -> Option<PathBuf> {
    let art_path = cover.art_path.as_deref().filter(|path| !path.is_empty())?;
    gather(edition_path(root, edition_dir, art_path, true), errors)
}

fn art_variant_stem(path: &str) -> String {
    let stem = path.rsplit('/').next().unwrap_or(path);
    let stem = match stem.rsplit_once('.') {
        Some((head, _)) => head,
        None => stem,
    };
    match stem.rsplit_once("-v") {
        Some((head, tail))
            if !tail.is_empty() && tail.chars().all(|item| item.is_ascii_digit()) =>
        {
            head.to_string()
        }
        _ => stem.to_string(),
    }
}

pub fn art_slots(spec: &EditionFile) -> Vec<(String, String)> {
    let mut slots: Vec<(String, String)> = Vec::new();
    let mut push = |label: String, path: Option<&str>| {
        if let Some(path) = path.filter(|path| !path.trim().is_empty()) {
            slots.push((label, path.to_string()));
        }
    };
    push("cover".to_string(), spec.cover.art_path.as_deref());
    for row in &spec.articles {
        let opener = row.opener_art.as_ref().map(|art| art.path.as_str());
        push(format!("article {} opener", row.id), opener);
        push(
            format!("article {} tail", row.id),
            row.tail_art_path.as_deref(),
        );
    }
    for plate in &spec.closing_plates {
        let label = format!("closing plate {}", quoted(&plate.title));
        push(label, Some(&plate.art_path));
    }
    slots
}

fn check_unique_art(spec: &EditionFile, errors: &mut Vec<String>) {
    let mut seen: BTreeMap<String, String> = BTreeMap::new();
    for (label, path) in art_slots(spec) {
        for key in [path.clone(), art_variant_stem(&path)] {
            if let Some(owner) = seen.get(&key) {
                if owner != &label {
                    errors.push(format!(
                        "{label} repeats the art of {owner} ({key}); every filler image appears once per edition; generate more with mag art <edition> --only closing"
                    ));
                    break;
                }
            }
            seen.entry(key).or_insert_with(|| label.clone());
        }
    }
}

fn load_closing_plates(
    context: &ArticleContext,
    rows: &[super::spec::PlateRow],
    errors: &mut Vec<String>,
) -> Vec<ClosingPlate> {
    let mut plates: Vec<ClosingPlate> = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        let number = index + 1;
        if row.title.is_empty() || row.art_path.is_empty() {
            errors.push(format!(
                "Closing plate {number} requires title and art_path"
            ));
            continue;
        }
        let must_exist = !context.options.allow_missing_art;
        let path = edition_path(context.root, context.edition_dir, &row.art_path, must_exist);
        let Some(art_path) = gather(path, errors) else {
            continue;
        };
        let title = row.title.trim().to_string();
        if plates
            .iter()
            .any(|plate| plate.title.to_lowercase() == title.to_lowercase())
        {
            errors.push(format!("Closing plate title must be unique: {title}"));
        }
        if plates.iter().any(|plate| plate.art_path == art_path) {
            errors.push(format!(
                "Closing plate art_path must be unique: {}",
                row.art_path
            ));
        }
        plates.push(ClosingPlate { title, art_path });
    }
    if !rows.is_empty() && rows.len() < 3 {
        errors.push(
            "Edition closing_plates must define at least three unique padding plates".to_string(),
        );
    }
    plates
}

pub fn load_translation(root: &Path, base: &Edition, language: &str) -> Result<Edition> {
    let translation_dir = root
        .join("editions")
        .join(&base.id)
        .join("translations")
        .join(language);
    let manifest_path = translation_dir.join("edition.yaml");
    if !manifest_path.is_file() {
        return Err(ValidationError(vec![format!(
            "Required {} translation manifest not found: {}",
            quoted(language),
            relative_display(&manifest_path, root)
        )]));
    }
    let spec: TranslationFile = read_spec(&manifest_path)?;
    let mut errors: Vec<String> = Vec::new();
    translation_header(&spec, base, language, &mut errors);
    let editorial =
        translation_editorial(root, &translation_dir, &spec, base, language, &mut errors);
    let articles = translation_articles(root, &translation_dir, &spec, base, language, &mut errors);
    let closing_plates = translation_closing_plates(&spec, base, language, &mut errors);
    let sections = translation_sections(root, &translation_dir, &spec, base, language, &mut errors);
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    let filled = |text: Option<String>| text.filter(|text| !text.is_empty());
    Ok(Edition {
        title: filled(spec.title).unwrap_or_else(|| base.title.clone()),
        subtitle: clean(spec.subtitle.as_deref()),
        language: language.to_string(),
        locale: filled(spec.locale).unwrap_or_else(|| language.to_string()),
        editorial,
        articles,
        sections,
        cover: spec.cover,
        closing_plates,
        ..base.clone()
    })
}

fn translation_header(
    spec: &TranslationFile,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) {
    if spec.language != language {
        errors.push(format!(
            "Translation {} does not match directory {}",
            quoted(&spec.language),
            quoted(language)
        ));
    }
    if spec.source_language != base.language {
        errors.push(format!(
            "Translation source_language must be {}",
            quoted(&base.language)
        ));
    }
    if spec.cover == Cover::default() {
        errors.push(format!(
            "Translation {} requires translated cover copy",
            quoted(language)
        ));
    }
    let declared = |text: &Option<String>| text.as_deref().is_some_and(|text| !text.is_empty());
    for (key, base_text, text) in [
        ("headline", &base.cover.headline, &spec.cover.headline),
        ("deck", &base.cover.deck, &spec.cover.deck),
        (
            "edition_label",
            &base.cover.edition_label,
            &spec.cover.edition_label,
        ),
        ("back_text", &base.cover.back_text, &spec.cover.back_text),
    ] {
        if declared(base_text) && !declared(text) {
            errors.push(format!(
                "Translation {} cover is missing {key}",
                quoted(language)
            ));
        }
    }
}

fn translation_editorial(
    root: &Path,
    translation_dir: &Path,
    spec: &TranslationFile,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Option<Editorial> {
    let source = base.editorial.as_ref()?;
    let Some(row) = spec.editorial.as_ref().filter(|row| !row.path.is_empty()) else {
        errors.push(format!(
            "Translation {} requires an editorial path",
            quoted(language)
        ));
        return None;
    };
    let path = gather(edition_path(root, translation_dir, &row.path, true), errors)?;
    validate_translation_file(
        &source.path,
        &path,
        &format!("Translation {} editorial", quoted(language)),
        errors,
    );
    gather(load_editorial(&path), errors)
}

fn translation_articles(
    root: &Path,
    translation_dir: &Path,
    spec: &TranslationFile,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Vec<Article> {
    let Some(rows) = spec.articles.as_ref() else {
        errors.push(format!(
            "Translation {} articles must be a list",
            quoted(language)
        ));
        return Vec::new();
    };
    let mut translated_by_id: BTreeMap<&str, &TranslatedArticleRow> = BTreeMap::new();
    for row in rows.iter().filter(|row| !row.id.is_empty()) {
        translated_by_id.entry(&row.id).or_insert(row);
    }
    let base_ids: BTreeSet<&str> = base.articles.iter().map(|item| item.id.as_str()).collect();
    let translated_ids: BTreeSet<&str> = translated_by_id.keys().copied().collect();
    for (state, ids) in [
        ("is missing", base_ids.difference(&translated_ids)),
        ("has unknown", translated_ids.difference(&base_ids)),
    ] {
        let ids: Vec<&str> = ids.copied().collect();
        if !ids.is_empty() {
            errors.push(format!(
                "Translation {} {state} articles: {}",
                quoted(language),
                ids.join(", ")
            ));
        }
    }
    base.articles
        .iter()
        .filter_map(|article| {
            translated_by_id.get(article.id.as_str()).and_then(|row| {
                translation_article(root, translation_dir, article, row, language, errors)
            })
        })
        .collect()
}

fn translation_author_note(
    article: &Article,
    row: &TranslatedArticleRow,
    prefix: &str,
    errors: &mut Vec<String>,
) -> String {
    let author_note = clean(row.author_note.as_deref());
    if !article.author_note.is_empty() && author_note.is_empty() {
        errors.push(format!(
            "{prefix} requires author_note because the source article has one"
        ));
    } else if article.author_note.is_empty() && !author_note.is_empty() {
        errors.push(format!(
            "{prefix} must omit author_note because the source article omits it"
        ));
    }
    check_note_length(prefix, &author_note, errors);
    author_note
}

fn translation_key_ideas(
    article: &Article,
    row: &TranslatedArticleRow,
    prefix: &str,
    errors: &mut Vec<String>,
) -> Vec<String> {
    if article.key_ideas.is_empty() && row.key_ideas.is_none() {
        return Vec::new();
    }
    let ideas = gather(key_ideas(prefix, row.key_ideas.as_deref()), errors).unwrap_or_default();
    if article.key_ideas.is_empty() {
        errors.push(format!(
            "{prefix} must omit key_ideas because the source article omits them"
        ));
    } else if ideas.is_empty() {
        errors.push(format!(
            "{prefix} requires key_ideas because the source article has them"
        ));
    } else if ideas.len() != article.key_ideas.len() {
        errors.push(format!(
            "{prefix} must translate all {} key_ideas lines, not {}",
            article.key_ideas.len(),
            ideas.len()
        ));
    }
    ideas
}

fn translation_article(
    root: &Path,
    translation_dir: &Path,
    article: &Article,
    row: &TranslatedArticleRow,
    language: &str,
    errors: &mut Vec<String>,
) -> Option<Article> {
    let prefix = format!("Translation {} article {}", quoted(language), article.id);
    let missing = blanks(&[
        ("title", row.title.is_empty()),
        ("short_title", row.short_title.is_empty()),
        ("manuscript", row.manuscript.is_empty()),
    ]);
    if !missing.is_empty() {
        errors.push(format!(
            "{prefix} requires title, short_title, and manuscript"
        ));
        return None;
    }
    let author_note = translation_author_note(article, row, &prefix, errors);
    let author = match row.author.as_deref() {
        None => article.author.clone(),
        Some(author) if author.trim().is_empty() => {
            errors.push(format!("{prefix} author cannot be blank"));
            String::new()
        }
        Some(author) => author.trim().to_string(),
    };
    let display_emphasis = clean(row.display_emphasis.as_deref());
    let short_title = row.short_title.trim().to_string();
    check_titles(&prefix, &row.title, &short_title, &display_emphasis, errors);
    let key_ideas = translation_key_ideas(article, row, &prefix, errors);
    let manuscript = gather(
        edition_path(root, translation_dir, &row.manuscript, true),
        errors,
    )?;
    validate_translation_file(&article.manuscript, &manuscript, &prefix, errors);
    let figures = localize_figures(
        &article.figures,
        row.figures.as_deref(),
        &article.id,
        &manuscript,
        language,
    );
    let extracts = localize_extracts(
        &article.extracts,
        row.extracts.as_deref(),
        &article.id,
        &manuscript,
        language,
    );
    Some(Article {
        title: row.title.clone(),
        short_title,
        display_emphasis,
        author,
        author_note,
        manuscript,
        figures: gather(figures, errors).unwrap_or_default(),
        key_ideas,
        dateline: None,
        extracts: gather(extracts, errors).unwrap_or_default(),
        ..article.clone()
    })
}

fn translation_closing_plates(
    spec: &TranslationFile,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Vec<ClosingPlate> {
    if base.closing_plates.is_empty() {
        return Vec::new();
    }
    let titles: Vec<String> = spec
        .closing_plate_titles
        .iter()
        .map(|title| title.trim().to_string())
        .collect();
    let folded: BTreeSet<String> = titles.iter().map(|title| title.to_lowercase()).collect();
    let problem = if titles.len() != base.closing_plates.len() {
        format!(
            "requires exactly {} closing_plate_titles",
            base.closing_plates.len()
        )
    } else if titles.iter().any(String::is_empty) {
        "closing_plate_titles cannot be blank".to_string()
    } else if folded.len() != titles.len() {
        "closing_plate_titles must be unique".to_string()
    } else {
        return titles
            .into_iter()
            .zip(&base.closing_plates)
            .map(|(title, plate)| ClosingPlate {
                title,
                art_path: plate.art_path.clone(),
            })
            .collect();
    };
    errors.push(format!("Translation {} {problem}", quoted(language)));
    Vec::new()
}

fn translation_sections(
    root: &Path,
    translation_dir: &Path,
    spec: &TranslationFile,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Vec<Section> {
    let Some(rows) = spec.sections.as_ref() else {
        errors.push(format!(
            "Translation {} sections must be a list",
            quoted(language)
        ));
        return Vec::new();
    };
    if rows.len() != base.sections.len() {
        errors.push(format!(
            "Translation {} must contain exactly {} sections",
            quoted(language),
            base.sections.len()
        ));
    }
    let mut sections: Vec<Section> = Vec::new();
    for (index, (section, row)) in base.sections.iter().zip(rows).enumerate() {
        let title = row.title.as_deref().filter(|title| !title.is_empty());
        let (Some(title), true, false) = (title, row.kind == section.kind, row.path.is_empty())
        else {
            errors.push(format!(
                "Translation {} section {} must preserve kind {} and provide title and path",
                quoted(language),
                index + 1,
                quoted(&section.kind)
            ));
            continue;
        };
        let Some(path) = gather(edition_path(root, translation_dir, &row.path, true), errors)
        else {
            continue;
        };
        let label = format!("Translation {} section {}", quoted(language), index + 1);
        validate_translation_file(&section.path, &path, &label, errors);
        sections.push(Section {
            kind: section.kind.clone(),
            title: title.to_string(),
            path,
        });
    }
    sections
}

fn markdown_signature(path: &Path) -> std::result::Result<Vec<String>, String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    let document = parse_publication_document(&text).map_err(|error| error.to_string())?;
    Ok(block_signature(&document.blocks))
}

fn validate_translation_file(
    source: &Path,
    translation: &Path,
    label: &str,
    errors: &mut Vec<String>,
) {
    let source_signature = match markdown_signature(source) {
        Ok(signature) => Some(signature),
        Err(error) => {
            errors.push(format!(
                "{label} English source {} cannot be parsed as a publication document: {error}",
                source.display()
            ));
            None
        }
    };
    let translation_signature = match markdown_signature(translation) {
        Ok(signature) => Some(signature),
        Err(error) => {
            errors.push(format!(
                "{label} translation {} cannot be parsed as a publication document: {error}",
                translation.display()
            ));
            None
        }
    };
    if let (Some(source_signature), Some(translation_signature)) =
        (&source_signature, &translation_signature)
    {
        if source_signature != translation_signature {
            errors.push(format!(
                "{label} does not preserve the source Markdown block structure ({} source blocks, {} translated blocks)",
                source_signature.len(),
                translation_signature.len()
            ));
        }
    }
    compare_markdown_invariants(source, translation, label, errors);
}

fn compare_markdown_invariants(
    source: &Path,
    translation: &Path,
    label: &str,
    errors: &mut Vec<String>,
) {
    let source_invariants = markdown_invariants(source);
    let translated_invariants = markdown_invariants(translation);
    if source_invariants.0 != translated_invariants.0 {
        errors.push(format!("{label} does not preserve link targets and order"));
    }
    if source_invariants.1 != translated_invariants.1 {
        errors.push(format!(
            "{label} does not preserve inline code identifiers and order"
        ));
    }
    if source_invariants.2 != translated_invariants.2 {
        errors.push(format!("{label} does not preserve fenced code exactly"));
    }
}

static LINKS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\[[^\]]+\]\(([^)]+)\)").unwrap());
static FENCED: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)```[^\n]*\n(.*?)\n```").unwrap());
static INLINE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"`([^`\n]+)`").unwrap());

fn markdown_invariants(path: &Path) -> (Vec<String>, Vec<String>, Vec<String>) {
    let text = std::fs::read_to_string(path).unwrap_or_default();
    let link_targets = LINKS
        .captures_iter(&text)
        .map(|found| found[1].to_string())
        .collect();
    let fenced_blocks: Vec<String> = FENCED
        .captures_iter(&text)
        .map(|found| found[1].to_string())
        .collect();
    let without_fences = FENCED.replace_all(&text, "");
    let inline_code = INLINE
        .captures_iter(&without_fences)
        .filter(|found| {
            let whole = found.get(0).expect("the whole match exists");
            let before = without_fences[..whole.start()].chars().next_back();
            let after = without_fences[whole.end()..].chars().next();
            before != Some('`') && after != Some('`')
        })
        .map(|found| found[1].to_string())
        .collect();
    (link_targets, inline_code, fenced_blocks)
}

fn representative_dateline(source_ids: &[String], records: Option<&Records>) -> Option<String> {
    let records = records?;
    if source_ids.is_empty() {
        return None;
    }
    let newest = source_ids
        .iter()
        .filter_map(|id| records.get(id))
        .filter_map(|record| record.published_at.as_ref())
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .max()?;
    let parts: Vec<&str> = newest.split('-').collect();
    if parts.len() < 2 {
        return Some(parts[0].to_string());
    }
    Some(format!("{} {}", parts[0], parts[1]))
}

fn primary_source_url(source_ids: &[String], records: Option<&Records>) -> Option<String> {
    let records = records?;
    let record = records.get(source_ids.first()?)?;
    let url = record.url.trim();
    if url.is_empty() {
        None
    } else {
        Some(url.to_string())
    }
}

fn relative_display(path: &Path, root: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .to_string()
}

fn edition_path(root: &Path, edition_dir: &Path, text: &str, must_exist: bool) -> Result<PathBuf> {
    if text.trim().is_empty() {
        return Err(ValidationError::one(
            "Referenced path must be a non-empty string",
        ));
    }
    let path = Path::new(text);
    if path.components().next() == Some(Component::Normal("editions".as_ref())) {
        return safe_project_path(root, text, must_exist);
    }
    let candidate = normalize(&edition_dir.join(path));
    let root = normalize(root);
    let Ok(relative) = candidate.strip_prefix(&root) else {
        return Err(ValidationError(vec![format!(
            "Path escapes project root: {text}"
        )]));
    };
    if must_exist && !candidate.is_file() {
        return Err(ValidationError(vec![format!(
            "Referenced file does not exist: {}",
            relative.to_string_lossy()
        )]));
    }
    Ok(candidate)
}

fn key_ideas(label: &str, items: Option<&[String]>) -> Result<Vec<String>> {
    let Some(items) = items else {
        return Ok(Vec::new());
    };
    if items.is_empty()
        || items
            .iter()
            .any(|item| item.trim().is_empty() || item.contains('\n'))
    {
        return Err(ValidationError::one(format!(
            "{label} key_ideas must be a non-empty list of single-line strings"
        )));
    }
    let ideas: Vec<String> = items.iter().map(|item| item.trim().to_string()).collect();
    let words: usize = ideas
        .iter()
        .map(|idea| idea.split_whitespace().count())
        .sum();
    if words > KEY_IDEAS_WORD_BUDGET {
        return Err(ValidationError::one(format!(
            "{label} key_ideas run to {words} words; the budget is {KEY_IDEAS_WORD_BUDGET}. State the claims a reader needs to use the thing, not a summary of the piece"
        )));
    }
    Ok(ideas)
}

fn section_title(kind: &str) -> String {
    match kind {
        "original_editorial" => "Editorial".to_string(),
        "source_introduction" => "Introduction".to_string(),
        "original_synthesis" => "Reading Map".to_string(),
        "source_record" => "Source Record".to_string(),
        "production_note" => "Production Note".to_string(),
        "glossary" => "Glossary".to_string(),
        "try_it" => "Try It in Fifteen Minutes".to_string(),
        "cheat_sheet" => "Cheat Sheet".to_string(),
        other => title_case(&other.replace('_', " ")),
    }
}

fn title_case(text: &str) -> String {
    let mut out = String::new();
    let mut fresh = true;
    for character in text.chars() {
        if fresh {
            out.extend(character.to_uppercase());
        } else {
            out.extend(character.to_lowercase());
        }
        fresh = !character.is_alphanumeric();
    }
    out
}

fn load_editorial(path: &Path) -> Result<Editorial> {
    let text = std::fs::read_to_string(path).map_err(|error| {
        ValidationError(vec![format!("Cannot read {}: {error}", path.display())])
    })?;
    let Some(rest) = text.strip_prefix("---\n") else {
        return Err(ValidationError(vec![format!(
            "Editorial requires YAML frontmatter with a title: {}",
            path.display()
        )]));
    };
    let Some((header, _)) = rest.split_once("\n---\n") else {
        return Err(ValidationError(vec![format!(
            "Editorial requires YAML frontmatter with a title: {}",
            path.display()
        )]));
    };
    let metadata: Value = serde_norway::from_str(header).map_err(|error| {
        ValidationError(vec![format!(
            "Cannot parse editorial frontmatter {}: {error}",
            path.display()
        )])
    })?;
    let title = match metadata.get("title") {
        Some(Value::String(title)) if !title.trim().is_empty() => title.trim().to_string(),
        _ => {
            return Err(ValidationError(vec![format!(
                "Editorial requires a non-empty title: {}",
                path.display()
            )]))
        }
    };
    Ok(Editorial {
        path: path.to_path_buf(),
        title,
        byline: frontmatter_text(&metadata, "byline", "The editors"),
        label: frontmatter_text(&metadata, "label", "ORIGINAL EDITORIAL"),
    })
}

pub fn source_code_payload(url: &str) -> String {
    let mut payload = url.trim();
    for scheme in ["https://", "http://"] {
        if let Some(rest) = payload.strip_prefix(scheme) {
            payload = rest;
            break;
        }
    }
    payload.strip_prefix("www.").unwrap_or(payload).to_string()
}

fn frontmatter_text(metadata: &Value, key: &str, fallback: &str) -> String {
    match metadata.get(key).and_then(Value::as_str) {
        Some(text) if !text.is_empty() => text.trim().to_string(),
        _ => fallback.to_string(),
    }
}
