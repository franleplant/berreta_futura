use super::doc::{block_signature, parse_publication_document, Block};
use super::records::{
    localize_extracts, localize_figures, resolve_extracts, resolve_figures, Extract,
    ExtractRequest, Figure, FigureRequest, SourceRecord,
};
use super::shared::{
    load_structured, normalize, py_repr, py_repr_value, py_str, safe_project_path, Result,
    ValidationError,
};
use regex::Regex;
use serde_yaml::{Mapping, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

pub const CONTENT_MODES: [&str; 3] = ["article", "in_a_nutshell", "verbatim"];

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
    pub content_mode: String,
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

#[derive(Debug, Clone, PartialEq)]
pub struct Edition {
    pub id: String,
    pub publication_name: String,
    pub issue_number: String,
    pub title: String,
    pub publication_date: String,
    pub language: String,
    pub locale: String,
    pub editorial: Option<Editorial>,
    pub articles: Vec<Article>,
    pub sections: Vec<Section>,
    pub cover: Mapping,
    pub cover_art: Option<PathBuf>,
    pub closing_plates: Vec<ClosingPlate>,
    pub raw: Value,
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
    let data = load_structured(&manifest_path)?;
    let mut errors: Vec<String> = Vec::new();
    check_edition_header(&data, edition_id, known_sources, &mut errors);
    let illustrated = edition_opener_format(&data, &mut errors);
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
    let articles = load_articles(&context, &data, &mut errors);
    let editorial = load_edition_editorial(root, &edition_dir, &data, &mut errors);
    let sections = load_sections(root, &edition_dir, &data, &mut errors);
    let (cover, cover_art) = load_cover(root, &edition_dir, &data, &mut errors);
    let closing_plates = load_closing_plates(
        root,
        &edition_dir,
        &data,
        &mut errors,
        options.allow_missing_art,
    );
    check_unique_art(&data, &mut errors);
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    let language = or_default(data.get("language"), "en");
    Ok(Edition {
        id: py_str(data.get("id").unwrap_or(&Value::Null)),
        publication_name: options.publication_name.to_string(),
        issue_number: py_str(data.get("issue_number").unwrap_or(&Value::Null)),
        title: py_str(data.get("title").unwrap_or(&Value::Null)),
        publication_date: py_str(data.get("publication_date").unwrap_or(&Value::Null)),
        locale: if truthy(data.get("locale")) {
            py_str(data.get("locale").unwrap_or(&Value::Null))
        } else {
            language.clone()
        },
        language,
        editorial,
        articles,
        sections,
        cover,
        cover_art,
        closing_plates,
        raw: data,
    })
}

fn or_default(value: Option<&Value>, fallback: &str) -> String {
    if truthy(value) {
        py_str(value.expect("a truthy value is present"))
    } else {
        fallback.to_string()
    }
}

fn check_edition_header(
    data: &Value,
    edition_id: &str,
    known_sources: &BTreeSet<String>,
    errors: &mut Vec<String>,
) {
    for key in ["id", "issue_number", "title", "publication_date"] {
        if blank_header_field(data.get(key)) {
            errors.push(format!("Edition missing required field: {key}"));
        }
    }
    if !matches!(data.get("id"), Some(Value::String(text)) if text == edition_id) {
        errors.push(format!(
            "Edition id {} does not match directory {}",
            repr_option(data.get("id")),
            py_repr(edition_id)
        ));
    }
    check_declared_sources(data.get("sources"), known_sources, errors);
    if !truthy(data.get("sections")) && !truthy(data.get("articles")) {
        errors.push("Edition requires either sections or articles".to_string());
    }
}

fn check_declared_sources(
    declared: Option<&Value>,
    known_sources: &BTreeSet<String>,
    errors: &mut Vec<String>,
) {
    let rows = match declared {
        None => &Vec::new(),
        Some(Value::Sequence(items)) => items,
        Some(_) => {
            errors.push("Edition sources must be a list".to_string());
            return;
        }
    };
    if rows
        .iter()
        .any(|value| !matches!(value, Value::String(text) if !text.trim().is_empty()))
    {
        errors.push("Edition sources must contain non-empty source id strings".to_string());
        return;
    }
    let unknown: Vec<String> = rows
        .iter()
        .filter_map(|value| value.as_str())
        .filter(|value| !known_sources.contains(*value))
        .map(str::to_string)
        .collect::<BTreeSet<String>>()
        .into_iter()
        .collect();
    if !unknown.is_empty() {
        errors.push(format!(
            "Edition references unknown sources: {}",
            unknown.join(", ")
        ));
    }
}

fn edition_opener_format(data: &Value, errors: &mut Vec<String>) -> bool {
    let edition_format = match data.get("format") {
        None | Some(Value::Null) => Value::Mapping(Mapping::new()),
        Some(value @ Value::Mapping(_)) => value.clone(),
        Some(_) => {
            errors.push("Edition format must be a mapping".to_string());
            Value::Mapping(Mapping::new())
        }
    };
    let article_opener = or_empty(edition_format.get("article_opener"));
    let article_opener = article_opener.trim();
    if !article_opener.is_empty() && article_opener != ILLUSTRATED_OPENER {
        errors.push(format!(
            "Edition has invalid format.article_opener: {article_opener}"
        ));
    }
    let illustrated = article_opener == ILLUSTRATED_OPENER;
    if illustrated && or_empty(data.get("art_direction_path")).trim().is_empty() {
        errors.push(format!(
            "Edition format.article_opener {ILLUSTRATED_OPENER} requires art_direction_path"
        ));
    }
    illustrated
}

fn load_articles(context: &ArticleContext, data: &Value, errors: &mut Vec<String>) -> Vec<Article> {
    let empty = Vec::new();
    let rows = match data.get("articles") {
        None => &empty,
        Some(Value::Sequence(items)) => items,
        Some(_) => {
            errors.push("Edition articles must be a list".to_string());
            &empty
        }
    };
    let mut ids: BTreeSet<String> = BTreeSet::new();
    let mut articles: Vec<Article> = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        if let Some(article) = load_article(context, index, row, &mut ids, errors) {
            articles.push(article);
        }
    }
    articles
}

fn article_identity(
    index: usize,
    row: &Value,
    errors: &mut Vec<String>,
) -> Option<(String, String, Vec<String>)> {
    if !matches!(row, Value::Mapping(_)) {
        errors.push(format!("Article {} must be a mapping", index + 1));
        return None;
    }
    let label = match row.get("id") {
        Some(value) if !matches!(value, Value::Null) => format!("Article {}", py_str(value)),
        _ => format!("Article {}", index + 1),
    };
    let missing: Vec<&str> = [
        "id",
        "title",
        "short_title",
        "opener_variant",
        "author",
        "source_ids",
        "manuscript",
    ]
    .into_iter()
    .filter(|key| !truthy(row.get(*key)))
    .collect();
    if !missing.is_empty() {
        errors.push(format!("{label} missing: {}", missing.join(", ")));
        return None;
    }
    let Some(Value::String(article_id)) = row.get("id") else {
        errors.push(format!(
            "Article {} id must be a non-empty string",
            index + 1
        ));
        return None;
    };
    if article_id.trim().is_empty() {
        errors.push(format!(
            "Article {} id must be a non-empty string",
            index + 1
        ));
        return None;
    }
    let source_ids = article_source_ids(row.get("source_ids"))?;
    if source_ids.is_empty() {
        errors.push(format!(
            "{label} source_ids must be a non-empty list of strings"
        ));
        return None;
    }
    Some((label, article_id.clone(), source_ids))
}

fn article_source_ids(declared: Option<&Value>) -> Option<Vec<String>> {
    let Some(Value::Sequence(items)) = declared else {
        return Some(Vec::new());
    };
    if items.is_empty()
        || items
            .iter()
            .any(|value| !matches!(value, Value::String(text) if !text.trim().is_empty()))
    {
        return Some(Vec::new());
    }
    Some(
        items
            .iter()
            .filter_map(|value| value.as_str().map(str::to_string))
            .collect(),
    )
}

fn article_author_note(label: &str, row: &Value, errors: &mut Vec<String>) -> (String, bool) {
    let author_note = or_empty(row.get("author_note")).trim().to_string();
    if author_note.contains('\n') || author_note.chars().count() > 160 {
        errors.push(format!(
            "{label} author_note must be a single line of at most 160 characters"
        ));
    }
    let author = py_str(row.get("author").unwrap_or(&Value::Null));
    let house_byline = HOUSE_BYLINES.contains(&casefold(author.trim()).as_str());
    if !author_note.is_empty() && house_byline {
        errors.push(format!(
            "{label} must omit author_note for the self-explanatory house byline {}",
            py_repr(&author)
        ));
    }
    (author_note, house_byline)
}

fn article_paths(
    root: &Path,
    edition_dir: &Path,
    row: &Value,
    errors: &mut Vec<String>,
    allow_missing_art: bool,
) -> Option<(PathBuf, Option<PathBuf>)> {
    let manuscript = match edition_path(root, edition_dir, row.get("manuscript"), true) {
        Ok(path) => path,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            return None;
        }
    };
    if !truthy(row.get("tail_art_path")) {
        return Some((manuscript, None));
    }
    match edition_path(
        root,
        edition_dir,
        row.get("tail_art_path"),
        !allow_missing_art,
    ) {
        Ok(path) => Some((manuscript, Some(path))),
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            None
        }
    }
}

fn article_opener_art(
    root: &Path,
    edition_dir: &Path,
    label: &str,
    row: &Value,
    errors: &mut Vec<String>,
    allow_missing_art: bool,
) -> Option<ArticleOpenerArt> {
    let raw = row.get("opener_art");
    let Some(Value::Mapping(mapping)) = raw else {
        errors.push(format!(
            "{label} requires a non-empty opener_art mapping for format.article_opener {ILLUSTRATED_OPENER}"
        ));
        return None;
    };
    if mapping.is_empty() {
        errors.push(format!(
            "{label} requires a non-empty opener_art mapping for format.article_opener {ILLUSTRATED_OPENER}"
        ));
        return None;
    }
    let missing: Vec<&str> = ["path", "alt_text", "credit"]
        .into_iter()
        .filter(|key| {
            !matches!(raw.and_then(|value| value.get(*key)), Some(Value::String(text)) if !text.trim().is_empty())
        })
        .collect();
    if !missing.is_empty() {
        errors.push(format!(
            "{label} opener_art requires non-empty {}",
            missing.join(", ")
        ));
        return None;
    }
    let path = match edition_path(
        root,
        edition_dir,
        raw.and_then(|value| value.get("path")),
        !allow_missing_art,
    ) {
        Ok(path) => path,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            return None;
        }
    };
    Some(ArticleOpenerArt {
        path,
        alt_text: or_empty(raw.and_then(|value| value.get("alt_text")))
            .trim()
            .to_string(),
        credit: or_empty(raw.and_then(|value| value.get("credit")))
            .trim()
            .to_string(),
    })
}

fn check_illustrated_opener(label: &str, manuscript: &Path, errors: &mut Vec<String>) {
    let text = match std::fs::read_to_string(manuscript) {
        Ok(text) => text,
        Err(error) => {
            errors.push(format!(
                "{label} manuscript cannot be parsed as a publication document: {error}"
            ));
            return;
        }
    };
    match parse_publication_document(&text) {
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

fn article_key_ideas(
    label: &str,
    row: &Value,
    tail_art: Option<&PathBuf>,
    errors: &mut Vec<String>,
) -> Vec<String> {
    let ideas = match key_ideas(label, row.get("key_ideas")) {
        Ok(ideas) => ideas,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            Vec::new()
        }
    };
    if !ideas.is_empty() && tail_art.is_some() {
        errors.push(format!(
            "{label} declares both key_ideas and tail_art_path; an article closes with one object, not two -- drop whichever the piece needs less"
        ));
    }
    ideas
}

struct Display {
    content_mode: String,
    minimum_reader_pages: i64,
    display_emphasis: String,
    short_title: String,
    opener_variant: String,
}

fn article_display(label: &str, row: &Value, errors: &mut Vec<String>) -> Display {
    let content_mode = match row.get("content_mode") {
        None => "faithful_edit".to_string(),
        Some(value) => py_str(value),
    };
    if !CONTENT_MODES.contains(&content_mode.as_str()) {
        errors.push(format!("{label} has invalid content_mode: {content_mode}"));
    }
    let minimum_reader_pages = to_int(row.get("minimum_reader_pages"));
    if !(1..=7).contains(&minimum_reader_pages) {
        errors.push(format!(
            "{label} minimum_reader_pages must be an integer from 1 to 7"
        ));
    }
    let title = casefold(&py_str(row.get("title").unwrap_or(&Value::Null)));
    let display_emphasis = or_empty(row.get("display_emphasis")).trim().to_string();
    if !display_emphasis.is_empty() && !title.contains(&casefold(&display_emphasis)) {
        errors.push(format!(
            "{label} display_emphasis must occur in its localized title"
        ));
    }
    let short_title = or_empty(row.get("short_title")).trim().to_string();
    if short_title.contains('\n') || short_title.chars().count() > 40 {
        errors.push(format!(
            "{label} short_title must be a single line of at most 40 characters"
        ));
    } else if !title.contains(&casefold(&short_title)) {
        errors.push(format!(
            "{label} short_title must occur in its localized title"
        ));
    }
    let opener_variant = or_empty(row.get("opener_variant")).trim().to_string();
    if !OPENER_VARIANTS.contains(&opener_variant.as_str()) {
        errors.push(format!(
            "{label} has invalid opener_variant: {opener_variant}"
        ));
    }
    Display {
        content_mode,
        minimum_reader_pages,
        display_emphasis,
        short_title,
        opener_variant,
    }
}

fn article_media(
    root: &Path,
    article_id: &str,
    source_ids: &[String],
    manuscript: &Path,
    row: &Value,
    errors: &mut Vec<String>,
    allow_unanchored: bool,
) -> (Vec<Figure>, Vec<Extract>) {
    let figures = match resolve_figures(
        &FigureRequest {
            root,
            article_id,
            article_source_ids: source_ids,
            manuscript,
            allow_unanchored,
        },
        row.get("figures"),
    ) {
        Ok(figures) => figures,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            Vec::new()
        }
    };
    let extracts = match resolve_extracts(
        &ExtractRequest {
            root,
            article_id,
            article_source_ids: source_ids,
            manuscript,
            allow_unanchored,
        },
        row.get("extracts"),
    ) {
        Ok(extracts) => extracts,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            Vec::new()
        }
    };
    (figures, extracts)
}

fn load_article(
    context: &ArticleContext,
    index: usize,
    row: &Value,
    ids: &mut BTreeSet<String>,
    errors: &mut Vec<String>,
) -> Option<Article> {
    let (label, article_id, source_ids) = article_identity(index, row, errors)?;
    let (author_note, house_byline) = article_author_note(&label, row, errors);
    if ids.contains(&article_id) {
        errors.push(format!("Duplicate article id: {article_id}"));
    }
    ids.insert(article_id.clone());
    let unknown: Vec<String> = source_ids
        .iter()
        .filter(|value| !context.known_sources.contains(*value))
        .cloned()
        .collect::<BTreeSet<String>>()
        .into_iter()
        .collect();
    if !unknown.is_empty() {
        errors.push(format!(
            "{label} references unknown sources: {}",
            unknown.join(", ")
        ));
    }
    let (manuscript, tail_art) = article_paths(
        context.root,
        context.edition_dir,
        row,
        errors,
        context.options.allow_missing_art,
    )?;
    let opener_art = load_opener_art(
        context,
        &label,
        row,
        &manuscript,
        &author_note,
        house_byline,
        errors,
    );
    let ideas = article_key_ideas(&label, row, tail_art.as_ref(), errors);
    let display = article_display(&label, row, errors);
    check_verbatim_title(
        &label,
        row,
        &source_ids,
        &display.content_mode,
        context.options.source_records,
        errors,
    );
    let (figures, extracts) = article_media(
        context.root,
        &article_id,
        &source_ids,
        &manuscript,
        row,
        errors,
        context.options.allow_unanchored_figures,
    );
    Some(Article {
        id: article_id,
        title: py_str(row.get("title").unwrap_or(&Value::Null)),
        short_title: display.short_title,
        display_emphasis: display.display_emphasis,
        opener_variant: display.opener_variant,
        author: py_str(row.get("author").unwrap_or(&Value::Null)),
        author_note,
        source_url: primary_source_url(&source_ids, context.options.source_records),
        dateline: representative_dateline(&source_ids, context.options.source_records),
        source_ids,
        manuscript,
        content_mode: display.content_mode,
        figures,
        minimum_reader_pages: display.minimum_reader_pages,
        tail_art,
        opener_art,
        key_ideas: ideas,
        extracts,
    })
}

fn load_opener_art(
    context: &ArticleContext,
    label: &str,
    row: &Value,
    manuscript: &Path,
    author_note: &str,
    house_byline: bool,
    errors: &mut Vec<String>,
) -> Option<ArticleOpenerArt> {
    if !context.illustrated {
        return None;
    }
    if author_note.is_empty() && !house_byline {
        errors.push(format!(
            "{label} requires author_note for format.article_opener {ILLUSTRATED_OPENER}"
        ));
    }
    let opener_art = article_opener_art(
        context.root,
        context.edition_dir,
        label,
        row,
        errors,
        context.options.allow_missing_art,
    );
    check_illustrated_opener(label, manuscript, errors);
    opener_art
}

fn check_verbatim_title(
    label: &str,
    row: &Value,
    source_ids: &[String],
    content_mode: &str,
    source_records: Option<&Records>,
    errors: &mut Vec<String>,
) {
    if content_mode != "verbatim" {
        return;
    }
    if source_ids.len() != 1 {
        errors.push(format!(
            "{label} verbatim articles carry exactly one source"
        ));
        return;
    }
    let Some(record) = source_records.and_then(|records| records.get(&source_ids[0])) else {
        return;
    };
    let title = py_str(row.get("title").unwrap_or(&Value::Null));
    if title.trim() != record.title.trim() {
        errors.push(format!(
            "{label} verbatim title must stay the captured source title {}",
            py_repr(&record.title)
        ));
    }
}

fn load_edition_editorial(
    root: &Path,
    edition_dir: &Path,
    data: &Value,
    errors: &mut Vec<String>,
) -> Option<Editorial> {
    if !truthy(data.get("editorial")) {
        return None;
    }
    let outcome = edition_path(root, edition_dir, data.get("editorial"), true)
        .and_then(|path| load_editorial(&path));
    match outcome {
        Ok(editorial) => Some(editorial),
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            None
        }
    }
}

fn load_sections(
    root: &Path,
    edition_dir: &Path,
    data: &Value,
    errors: &mut Vec<String>,
) -> Vec<Section> {
    let empty = Vec::new();
    let rows = match data.get("sections") {
        None | Some(Value::Null) => &empty,
        Some(Value::Sequence(items)) => items,
        Some(_) => {
            errors.push("Edition sections must be a list".to_string());
            &empty
        }
    };
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
    row: &Value,
    errors: &mut Vec<String>,
) -> Option<Section> {
    if !matches!(row, Value::Mapping(_)) || !truthy(row.get("kind")) || !truthy(row.get("path")) {
        errors.push(format!("Section {} requires kind and path", index + 1));
        return None;
    }
    let kind = py_str(row.get("kind").expect("the kind is present"));
    if casefold(kind.trim()) == "colophon" {
        errors.push("Colophon sections are no longer supported".to_string());
        return None;
    }
    if !SECTION_KINDS.contains(&kind.as_str()) {
        errors.push(format!(
            "Section {} has unknown kind {}; the known kinds are {}",
            index + 1,
            py_repr(&kind),
            SECTION_KINDS.join(", ")
        ));
        return None;
    }
    match edition_path(root, edition_dir, row.get("path"), true) {
        Ok(path) => Some(Section {
            title: if truthy(row.get("title")) {
                py_str(row.get("title").expect("the title is present"))
            } else {
                section_title(&kind)
            },
            kind,
            path,
        }),
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            None
        }
    }
}

fn load_cover(
    root: &Path,
    edition_dir: &Path,
    data: &Value,
    errors: &mut Vec<String>,
) -> (Mapping, Option<PathBuf>) {
    let cover = match data.get("cover") {
        None | Some(Value::Null) => Mapping::new(),
        Some(Value::Mapping(mapping)) => mapping.clone(),
        Some(_) => {
            errors.push("Edition cover must be a mapping".to_string());
            Mapping::new()
        }
    };
    let tail_art_fit = or_default(data.get("tail_art_fit"), "cover");
    if !["cover", "contain"].contains(&tail_art_fit.trim()) {
        errors.push("Edition tail_art_fit must be cover or contain".to_string());
    }
    let art_path = cover.get(Value::String("art_path".to_string()));
    if !truthy(art_path) {
        return (cover, None);
    }
    match edition_path(root, edition_dir, art_path, true) {
        Ok(path) => (cover, Some(path)),
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            (cover, None)
        }
    }
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

fn art_slots(data: &Value) -> Vec<(String, String)> {
    let mut slots: Vec<(String, String)> = Vec::new();
    if let Some(Value::String(path)) = data.get("cover").and_then(|cover| cover.get("art_path")) {
        if !path.trim().is_empty() {
            slots.push(("cover".to_string(), path.clone()));
        }
    }
    if let Some(Value::Sequence(rows)) = data.get("articles") {
        for row in rows {
            if !matches!(row, Value::Mapping(_)) {
                continue;
            }
            let id = py_str(row.get("id").unwrap_or(&Value::Null));
            if let Some(Value::String(path)) = row.get("opener_art").and_then(|art| art.get("path"))
            {
                if !path.trim().is_empty() {
                    slots.push((format!("article {id} opener"), path.clone()));
                }
            }
            if let Some(Value::String(path)) = row.get("tail_art_path") {
                if !path.trim().is_empty() {
                    slots.push((format!("article {id} tail"), path.clone()));
                }
            }
        }
    }
    if let Some(Value::Sequence(plates)) = data.get("closing_plates") {
        for plate in plates {
            if let (Value::Mapping(_), Some(Value::String(path))) = (plate, plate.get("art_path")) {
                slots.push((
                    format!(
                        "closing plate {}",
                        repr_option(plate.get("title").filter(|value| !value.is_null()))
                    ),
                    path.clone(),
                ));
            }
        }
    }
    slots
}

fn check_unique_art(data: &Value, errors: &mut Vec<String>) {
    let mut seen: BTreeMap<String, String> = BTreeMap::new();
    for (label, path) in art_slots(data) {
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
    root: &Path,
    edition_dir: &Path,
    data: &Value,
    errors: &mut Vec<String>,
    allow_missing_art: bool,
) -> Vec<ClosingPlate> {
    let empty = Vec::new();
    let rows = match data.get("closing_plates") {
        None | Some(Value::Null) => &empty,
        Some(Value::Sequence(items)) => items,
        Some(_) => {
            errors.push("Edition closing_plates must be a list".to_string());
            &empty
        }
    };
    let mut plates: Vec<ClosingPlate> = Vec::new();
    let mut titles: BTreeSet<String> = BTreeSet::new();
    let mut paths: BTreeSet<PathBuf> = BTreeSet::new();
    for (index, row) in rows.iter().enumerate() {
        closing_plate(
            root,
            edition_dir,
            index + 1,
            row,
            allow_missing_art,
            &mut titles,
            &mut paths,
            &mut plates,
            errors,
        );
    }
    if !rows.is_empty() && rows.len() < 3 {
        errors.push(
            "Edition closing_plates must define at least three unique padding plates".to_string(),
        );
    }
    plates
}

#[allow(clippy::too_many_arguments)]
fn closing_plate(
    root: &Path,
    edition_dir: &Path,
    number: usize,
    row: &Value,
    allow_missing_art: bool,
    titles: &mut BTreeSet<String>,
    paths: &mut BTreeSet<PathBuf>,
    plates: &mut Vec<ClosingPlate>,
    errors: &mut Vec<String>,
) {
    if !matches!(row, Value::Mapping(_))
        || !truthy(row.get("title"))
        || !truthy(row.get("art_path"))
    {
        errors.push(format!(
            "Closing plate {number} requires title and art_path"
        ));
        return;
    }
    let title = py_str(row.get("title").expect("the title is present"))
        .trim()
        .to_string();
    let art_path = match edition_path(root, edition_dir, row.get("art_path"), !allow_missing_art) {
        Ok(path) => path,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            return;
        }
    };
    if titles.contains(&casefold(&title)) {
        errors.push(format!("Closing plate title must be unique: {title}"));
    }
    if paths.contains(&art_path) {
        errors.push(format!(
            "Closing plate art_path must be unique: {}",
            py_str(row.get("art_path").expect("the art path is present"))
        ));
    }
    titles.insert(casefold(&title));
    paths.insert(art_path.clone());
    plates.push(ClosingPlate { title, art_path });
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
            py_repr(language),
            relative_display(&manifest_path, root)
        )]));
    }
    let data = load_structured(&manifest_path)?;
    let mut errors: Vec<String> = Vec::new();
    let cover = translation_header(&data, base, language, &mut errors);
    let editorial =
        translation_editorial(root, &translation_dir, &data, base, language, &mut errors);
    let articles = translation_articles(root, &translation_dir, &data, base, language, &mut errors);
    let closing_plates = translation_closing_plates(&data, base, language, &mut errors);
    let sections = translation_sections(root, &translation_dir, &data, base, language, &mut errors);
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    let raw = translation_raw(
        root,
        &data,
        base,
        language,
        &cover,
        editorial.as_ref(),
        &articles,
        &closing_plates,
        &sections,
    );
    Ok(Edition {
        id: base.id.clone(),
        publication_name: base.publication_name.clone(),
        issue_number: base.issue_number.clone(),
        title: or_default(data.get("title"), &base.title),
        publication_date: base.publication_date.clone(),
        language: language.to_string(),
        locale: or_default(data.get("locale"), language),
        editorial,
        articles,
        sections,
        cover,
        cover_art: base.cover_art.clone(),
        closing_plates,
        raw,
    })
}

fn translation_header(
    data: &Value,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Mapping {
    if or_empty(data.get("language")) != language {
        errors.push(format!(
            "Translation language {} does not match directory {}",
            repr_option(data.get("language").filter(|value| !value.is_null())),
            py_repr(language)
        ));
    }
    if or_empty(data.get("source_language")) != base.language {
        errors.push(format!(
            "Translation source_language must be {}",
            py_repr(&base.language)
        ));
    }
    let cover = match data.get("cover") {
        Some(Value::Mapping(mapping)) => mapping.clone(),
        _ => {
            errors.push(format!(
                "Translation {} requires translated cover copy",
                py_repr(language)
            ));
            Mapping::new()
        }
    };
    for key in ["headline", "deck", "edition_label", "back_text"] {
        let declared = base.cover.get(Value::String(key.to_string()));
        if truthy(declared) && !truthy(cover.get(Value::String(key.to_string()))) {
            errors.push(format!(
                "Translation {} cover is missing {key}",
                py_repr(language)
            ));
        }
    }
    cover
}

fn translation_editorial(
    root: &Path,
    translation_dir: &Path,
    data: &Value,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Option<Editorial> {
    let source = base.editorial.as_ref()?;
    let row = data.get("editorial");
    if !matches!(row, Some(Value::Mapping(_))) || !truthy(row.and_then(|row| row.get("path"))) {
        errors.push(format!(
            "Translation {} requires an editorial path",
            py_repr(language)
        ));
        return None;
    }
    let path = match edition_path(
        root,
        translation_dir,
        row.and_then(|row| row.get("path")),
        true,
    ) {
        Ok(path) => path,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            return None;
        }
    };
    validate_translation_file(
        &source.path,
        &path,
        &format!("Translation {} editorial", py_repr(language)),
        errors,
    );
    match load_editorial(&path) {
        Ok(editorial) => Some(editorial),
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            None
        }
    }
}

fn translation_articles(
    root: &Path,
    translation_dir: &Path,
    data: &Value,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Vec<Article> {
    let empty = Vec::new();
    let rows = match data.get("articles") {
        Some(Value::Sequence(items)) => items,
        _ => {
            errors.push(format!(
                "Translation {} articles must be a list",
                py_repr(language)
            ));
            &empty
        }
    };
    let mut translated_by_id: BTreeMap<String, &Value> = BTreeMap::new();
    for row in rows {
        if matches!(row, Value::Mapping(_)) && truthy(row.get("id")) {
            translated_by_id
                .entry(py_str(row.get("id").expect("the id is present")))
                .or_insert(row);
        }
    }
    let base_ids: BTreeSet<String> = base.articles.iter().map(|item| item.id.clone()).collect();
    let translated_ids: BTreeSet<String> = translated_by_id.keys().cloned().collect();
    let missing: Vec<String> = base_ids.difference(&translated_ids).cloned().collect();
    let extra: Vec<String> = translated_ids.difference(&base_ids).cloned().collect();
    if !missing.is_empty() {
        errors.push(format!(
            "Translation {} is missing articles: {}",
            py_repr(language),
            missing.join(", ")
        ));
    }
    if !extra.is_empty() {
        errors.push(format!(
            "Translation {} has unknown articles: {}",
            py_repr(language),
            extra.join(", ")
        ));
    }
    base.articles
        .iter()
        .filter_map(|article| {
            translated_by_id.get(&article.id).and_then(|row| {
                translation_article(root, translation_dir, article, row, language, errors)
            })
        })
        .collect()
}

fn translation_author_note(
    article: &Article,
    row: &Value,
    prefix: &str,
    errors: &mut Vec<String>,
) -> String {
    let author_note = or_empty(row.get("author_note")).trim().to_string();
    if !article.author_note.is_empty() && author_note.is_empty() {
        errors.push(format!(
            "{prefix} requires author_note because the source article has one"
        ));
    } else if article.author_note.is_empty() && !author_note.is_empty() {
        errors.push(format!(
            "{prefix} must omit author_note because the source article omits it"
        ));
    }
    if author_note.contains('\n') || author_note.chars().count() > 160 {
        errors.push(format!(
            "{prefix} author_note must be a single line of at most 160 characters"
        ));
    }
    author_note
}

fn translation_titles(row: &Value, prefix: &str, errors: &mut Vec<String>) -> (String, String) {
    let title = casefold(&py_str(row.get("title").unwrap_or(&Value::Null)));
    let display_emphasis = or_empty(row.get("display_emphasis")).trim().to_string();
    if !display_emphasis.is_empty() && !title.contains(&casefold(&display_emphasis)) {
        errors.push(format!(
            "{prefix} display_emphasis must occur in its localized title"
        ));
    }
    let short_title = or_empty(row.get("short_title")).trim().to_string();
    if short_title.contains('\n') || short_title.chars().count() > 40 {
        errors.push(format!(
            "{prefix} short_title must be a single line of at most 40 characters"
        ));
    } else if !title.contains(&casefold(&short_title)) {
        errors.push(format!(
            "{prefix} short_title must occur in its localized title"
        ));
    }
    (display_emphasis, short_title)
}

fn translation_key_ideas(
    article: &Article,
    row: &Value,
    prefix: &str,
    errors: &mut Vec<String>,
) -> Vec<String> {
    if article.key_ideas.is_empty() && row.get("key_ideas").is_none() {
        return Vec::new();
    }
    let ideas = match key_ideas(prefix, row.get("key_ideas")) {
        Ok(ideas) => ideas,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            Vec::new()
        }
    };
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

fn translation_media(
    article: &Article,
    row: &Value,
    manuscript: &Path,
    language: &str,
    errors: &mut Vec<String>,
) -> (Vec<Figure>, Vec<Extract>) {
    let figures = match localize_figures(
        &article.figures,
        row.get("figures"),
        &article.id,
        manuscript,
        language,
    ) {
        Ok(figures) => figures,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            Vec::new()
        }
    };
    let extracts = match localize_extracts(
        &article.extracts,
        row.get("extracts"),
        &article.id,
        manuscript,
        language,
    ) {
        Ok(extracts) => extracts,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            Vec::new()
        }
    };
    (figures, extracts)
}

fn translation_article(
    root: &Path,
    translation_dir: &Path,
    article: &Article,
    row: &Value,
    language: &str,
    errors: &mut Vec<String>,
) -> Option<Article> {
    let prefix = format!("Translation {} article {}", py_repr(language), article.id);
    if !truthy(row.get("title"))
        || !truthy(row.get("short_title"))
        || !truthy(row.get("manuscript"))
    {
        errors.push(format!(
            "{prefix} requires title, short_title, and manuscript"
        ));
        return None;
    }
    let author_note = translation_author_note(article, row, &prefix, errors);
    let author = match row.get("author") {
        None => article.author.clone(),
        Some(value) => {
            let author = if truthy(Some(value)) {
                py_str(value).trim().to_string()
            } else {
                String::new()
            };
            if author.is_empty() {
                errors.push(format!("{prefix} author cannot be blank"));
            }
            author
        }
    };
    let (display_emphasis, short_title) = translation_titles(row, &prefix, errors);
    let ideas = translation_key_ideas(article, row, &prefix, errors);
    let manuscript = match edition_path(root, translation_dir, row.get("manuscript"), true) {
        Ok(path) => path,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            return None;
        }
    };
    validate_translation_file(&article.manuscript, &manuscript, &prefix, errors);
    let (figures, extracts) = translation_media(article, row, &manuscript, language, errors);
    Some(Article {
        id: article.id.clone(),
        title: py_str(row.get("title").expect("the title is present")),
        short_title,
        display_emphasis,
        opener_variant: article.opener_variant.clone(),
        author,
        author_note,
        source_ids: article.source_ids.clone(),
        manuscript,
        content_mode: article.content_mode.clone(),
        figures,
        minimum_reader_pages: article.minimum_reader_pages,
        tail_art: article.tail_art.clone(),
        source_url: article.source_url.clone(),
        opener_art: article.opener_art.clone(),
        key_ideas: ideas,
        dateline: None,
        extracts,
    })
}

fn translation_closing_plates(
    data: &Value,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Vec<ClosingPlate> {
    if base.closing_plates.is_empty() {
        return Vec::new();
    }
    let rows = match data.get("closing_plate_titles") {
        Some(Value::Sequence(items)) if items.len() == base.closing_plates.len() => items,
        _ => {
            errors.push(format!(
                "Translation {} requires exactly {} closing_plate_titles",
                py_repr(language),
                base.closing_plates.len()
            ));
            return Vec::new();
        }
    };
    let titles: Vec<String> = rows
        .iter()
        .map(|value| py_str(value).trim().to_string())
        .collect();
    if titles.iter().any(String::is_empty) {
        errors.push(format!(
            "Translation {} closing_plate_titles cannot be blank",
            py_repr(language)
        ));
        return Vec::new();
    }
    let folded: BTreeSet<String> = titles.iter().map(|title| casefold(title)).collect();
    if folded.len() != titles.len() {
        errors.push(format!(
            "Translation {} closing_plate_titles must be unique",
            py_repr(language)
        ));
        return Vec::new();
    }
    titles
        .into_iter()
        .zip(base.closing_plates.iter())
        .map(|(title, plate)| ClosingPlate {
            title,
            art_path: plate.art_path.clone(),
        })
        .collect()
}

fn translation_sections(
    root: &Path,
    translation_dir: &Path,
    data: &Value,
    base: &Edition,
    language: &str,
    errors: &mut Vec<String>,
) -> Vec<Section> {
    let empty = Vec::new();
    let rows = match data.get("sections") {
        Some(Value::Sequence(items)) => items,
        _ => {
            errors.push(format!(
                "Translation {} sections must be a list",
                py_repr(language)
            ));
            &empty
        }
    };
    if rows.len() != base.sections.len() {
        errors.push(format!(
            "Translation {} must contain exactly {} sections",
            py_repr(language),
            base.sections.len()
        ));
    }
    let mut sections: Vec<Section> = Vec::new();
    for (index, section) in base.sections.iter().enumerate() {
        let Some(row) = rows
            .get(index)
            .filter(|row| matches!(row, Value::Mapping(_)))
        else {
            continue;
        };
        if let Some(translated) =
            translation_section(root, translation_dir, index, section, row, language, errors)
        {
            sections.push(translated);
        }
    }
    sections
}

fn translation_section(
    root: &Path,
    translation_dir: &Path,
    index: usize,
    section: &Section,
    row: &Value,
    language: &str,
    errors: &mut Vec<String>,
) -> Option<Section> {
    let kind_matches =
        matches!(row.get("kind"), Some(Value::String(kind)) if kind == &section.kind);
    if !kind_matches || !truthy(row.get("title")) || !truthy(row.get("path")) {
        errors.push(format!(
            "Translation {} section {} must preserve kind {} and provide title and path",
            py_repr(language),
            index + 1,
            py_repr(&section.kind)
        ));
        return None;
    }
    let path = match edition_path(root, translation_dir, row.get("path"), true) {
        Ok(path) => path,
        Err(ValidationError(messages)) => {
            errors.extend(messages);
            return None;
        }
    };
    validate_translation_file(
        &section.path,
        &path,
        &format!("Translation {} section {}", py_repr(language), index + 1),
        errors,
    );
    Some(Section {
        kind: section.kind.clone(),
        title: py_str(row.get("title").expect("the title is present")),
        path,
    })
}

fn relative_posix(path: &Path, root: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
}

fn translation_article_raw(root: &Path, article: &Article) -> Value {
    let mut row = Mapping::new();
    insert(&mut row, "id", Value::String(article.id.clone()));
    insert(&mut row, "title", Value::String(article.title.clone()));
    insert(
        &mut row,
        "short_title",
        Value::String(article.short_title.clone()),
    );
    insert(
        &mut row,
        "display_emphasis",
        Value::String(article.display_emphasis.clone()),
    );
    insert(
        &mut row,
        "opener_variant",
        Value::String(article.opener_variant.clone()),
    );
    insert(&mut row, "author", Value::String(article.author.clone()));
    insert(
        &mut row,
        "author_note",
        Value::String(article.author_note.clone()),
    );
    insert(
        &mut row,
        "content_mode",
        Value::String(article.content_mode.clone()),
    );
    insert(
        &mut row,
        "source_ids",
        Value::Sequence(
            article
                .source_ids
                .iter()
                .map(|id| Value::String(id.clone()))
                .collect(),
        ),
    );
    insert(
        &mut row,
        "manuscript",
        Value::String(relative_posix(&article.manuscript, root)),
    );
    insert(
        &mut row,
        "tail_art_path",
        match article.tail_art.as_ref() {
            Some(path) => Value::String(relative_posix(path, root)),
            None => Value::Null,
        },
    );
    if !article.key_ideas.is_empty() {
        insert(
            &mut row,
            "key_ideas",
            Value::Sequence(
                article
                    .key_ideas
                    .iter()
                    .map(|idea| Value::String(idea.clone()))
                    .collect(),
            ),
        );
    }
    if let Some(art) = article.opener_art.as_ref() {
        let mut opener = Mapping::new();
        insert(
            &mut opener,
            "path",
            Value::String(relative_posix(&art.path, root)),
        );
        insert(&mut opener, "alt_text", Value::String(art.alt_text.clone()));
        insert(&mut opener, "credit", Value::String(art.credit.clone()));
        insert(&mut row, "opener_art", Value::Mapping(opener));
    }
    insert(
        &mut row,
        "figures",
        Value::Sequence(article.figures.iter().map(figure_raw).collect()),
    );
    if !article.extracts.is_empty() {
        insert(
            &mut row,
            "extracts",
            Value::Sequence(article.extracts.iter().map(extract_raw).collect()),
        );
    }
    Value::Mapping(row)
}

fn figure_raw(figure: &Figure) -> Value {
    let mut row = Mapping::new();
    insert(&mut row, "id", Value::String(figure.id.clone()));
    insert(
        &mut row,
        "source_id",
        Value::String(figure.source_id.clone()),
    );
    insert(
        &mut row,
        "path",
        Value::String(figure.path.to_string_lossy().replace('\\', "/")),
    );
    insert(&mut row, "caption", Value::String(figure.caption.clone()));
    insert(&mut row, "credit", Value::String(figure.credit.clone()));
    insert(&mut row, "alt_text", Value::String(figure.alt_text.clone()));
    insert(&mut row, "anchor", Value::String(figure.anchor.clone()));
    insert(&mut row, "layout", Value::String(figure.layout.clone()));
    Value::Mapping(row)
}

fn extract_raw(extract: &Extract) -> Value {
    let mut row = Mapping::new();
    insert(&mut row, "id", Value::String(extract.id.clone()));
    insert(
        &mut row,
        "source_id",
        Value::String(extract.source_id.clone()),
    );
    insert(&mut row, "style", Value::String(extract.style.clone()));
    insert(&mut row, "caption", Value::String(extract.caption.clone()));
    insert(&mut row, "anchor", Value::String(extract.anchor.clone()));
    Value::Mapping(row)
}

fn insert(mapping: &mut Mapping, key: &str, value: Value) {
    mapping.insert(Value::String(key.to_string()), value);
}

#[allow(clippy::too_many_arguments)]
fn translation_raw(
    root: &Path,
    data: &Value,
    base: &Edition,
    language: &str,
    cover: &Mapping,
    editorial: Option<&Editorial>,
    articles: &[Article],
    closing_plates: &[ClosingPlate],
    sections: &[Section],
) -> Value {
    let Value::Mapping(mut raw) = base.raw.clone() else {
        return base.raw.clone();
    };
    insert(
        &mut raw,
        "title",
        Value::String(or_default(data.get("title"), &base.title)),
    );
    insert(
        &mut raw,
        "subtitle",
        Value::String(or_default(data.get("subtitle"), "")),
    );
    insert(&mut raw, "language", Value::String(language.to_string()));
    insert(
        &mut raw,
        "locale",
        Value::String(or_default(data.get("locale"), language)),
    );
    let mut translation = Mapping::new();
    insert(
        &mut translation,
        "source_language",
        Value::String(base.language.clone()),
    );
    insert(
        &mut translation,
        "fallback_locale",
        data.get("fallback_locale").cloned().unwrap_or(Value::Null),
    );
    insert(
        &mut translation,
        "policy",
        data.get("policy").cloned().unwrap_or(Value::Null),
    );
    insert(&mut raw, "translation", Value::Mapping(translation));
    insert(&mut raw, "cover", Value::Mapping(cover.clone()));
    insert(
        &mut raw,
        "closing_plates",
        Value::Sequence(
            closing_plates
                .iter()
                .map(|plate| {
                    let mut row = Mapping::new();
                    insert(&mut row, "title", Value::String(plate.title.clone()));
                    insert(
                        &mut row,
                        "art_path",
                        Value::String(relative_posix(&plate.art_path, root)),
                    );
                    Value::Mapping(row)
                })
                .collect(),
        ),
    );
    insert(
        &mut raw,
        "editorial",
        match editorial {
            Some(editorial) => Value::String(relative_posix(&editorial.path, root)),
            None => Value::Null,
        },
    );
    insert(
        &mut raw,
        "articles",
        Value::Sequence(
            articles
                .iter()
                .map(|article| translation_article_raw(root, article))
                .collect(),
        ),
    );
    insert(
        &mut raw,
        "sections",
        Value::Sequence(
            sections
                .iter()
                .map(|section| {
                    let mut row = Mapping::new();
                    insert(&mut row, "kind", Value::String(section.kind.clone()));
                    insert(&mut row, "title", Value::String(section.title.clone()));
                    insert(
                        &mut row,
                        "path",
                        Value::String(relative_posix(&section.path, root)),
                    );
                    Value::Mapping(row)
                })
                .collect(),
        ),
    );
    Value::Mapping(raw)
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

fn markdown_invariants(path: &Path) -> (Vec<String>, Vec<String>, Vec<String>) {
    static LINKS: OnceLock<Regex> = OnceLock::new();
    static FENCED: OnceLock<Regex> = OnceLock::new();
    static INLINE: OnceLock<Regex> = OnceLock::new();
    let links = LINKS.get_or_init(|| Regex::new(r"\[[^\]]+\]\(([^)]+)\)").expect("a valid regex"));
    let fenced =
        FENCED.get_or_init(|| Regex::new(r"(?s)```[^\n]*\n(.*?)\n```").expect("a valid regex"));
    let inline = INLINE.get_or_init(|| Regex::new(r"`([^`\n]+)`").expect("a valid regex"));
    let text = std::fs::read_to_string(path).unwrap_or_default();
    let link_targets = links
        .captures_iter(&text)
        .map(|found| found[1].to_string())
        .collect();
    let fenced_blocks: Vec<String> = fenced
        .captures_iter(&text)
        .map(|found| found[1].to_string())
        .collect();
    let without_fences = fenced.replace_all(&text, "");
    let inline_code = inline
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

fn edition_path(
    root: &Path,
    edition_dir: &Path,
    value: Option<&Value>,
    must_exist: bool,
) -> Result<PathBuf> {
    let text = match value {
        Some(Value::String(text)) if !text.trim().is_empty() => text.clone(),
        other => {
            return Err(ValidationError(vec![format!(
                "Referenced path must be a non-empty string, got {}",
                repr_option(other)
            )]))
        }
    };
    let path = Path::new(&text);
    if path.components().next() == Some(Component::Normal("editions".as_ref())) {
        return safe_project_path(root, &text, must_exist);
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

fn key_ideas(label: &str, value: Option<&Value>) -> Result<Vec<String>> {
    let items = match value {
        None | Some(Value::Null) => return Ok(Vec::new()),
        Some(Value::Sequence(items)) => items,
        Some(_) => {
            return Err(ValidationError(vec![format!(
                "{label} key_ideas must be a non-empty list of single-line strings"
            )]))
        }
    };
    let invalid = items.iter().any(|item| {
        !matches!(item, Value::String(text) if !text.trim().is_empty() && !text.contains('\n'))
    });
    if items.is_empty() || invalid {
        return Err(ValidationError(vec![format!(
            "{label} key_ideas must be a non-empty list of single-line strings"
        )]));
    }
    let ideas: Vec<String> = items
        .iter()
        .filter_map(|item| item.as_str().map(|text| text.trim().to_string()))
        .collect();
    let words: usize = ideas
        .iter()
        .map(|idea| idea.split_whitespace().count())
        .sum();
    if words > KEY_IDEAS_WORD_BUDGET {
        return Err(ValidationError(vec![format!(
            "{label} key_ideas run to {words} words; the budget is {KEY_IDEAS_WORD_BUDGET}. State the claims a reader needs to use the thing, not a summary of the piece"
        )]));
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
    let metadata: Value = serde_yaml::from_str(header).map_err(|error| {
        ValidationError(vec![format!(
            "Cannot parse editorial frontmatter {}: {error}",
            path.display()
        )])
    })?;
    let title = match metadata.get("title") {
        Some(value) if !py_str(value).trim().is_empty() => py_str(value).trim().to_string(),
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
        byline: or_default(metadata.get("byline"), "The editors")
            .trim()
            .to_string(),
        label: or_default(metadata.get("label"), "ORIGINAL EDITORIAL")
            .trim()
            .to_string(),
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

fn blank_header_field(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => true,
        Some(Value::String(text)) => text.is_empty(),
        Some(Value::Sequence(items)) => items.is_empty(),
        _ => false,
    }
}

fn truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(flag)) => *flag,
        Some(Value::Number(number)) => number.as_f64().is_some_and(|value| value != 0.0),
        Some(Value::String(text)) => !text.is_empty(),
        Some(Value::Sequence(items)) => !items.is_empty(),
        Some(Value::Mapping(mapping)) => !mapping.is_empty(),
        Some(Value::Tagged(tagged)) => truthy(Some(&tagged.value)),
    }
}

fn or_empty(value: Option<&Value>) -> String {
    if truthy(value) {
        py_str(value.expect("a truthy value is present"))
    } else {
        String::new()
    }
}

fn to_int(value: Option<&Value>) -> i64 {
    match value {
        None => 1,
        Some(Value::Bool(flag)) => i64::from(*flag),
        Some(Value::Number(number)) => number
            .as_i64()
            .or_else(|| number.as_f64().map(|value| value.trunc() as i64))
            .unwrap_or(0),
        Some(Value::String(text)) => text.trim().parse::<i64>().unwrap_or(0),
        Some(_) => 0,
    }
}

fn casefold(text: &str) -> String {
    text.to_lowercase()
}

fn repr_option(value: Option<&Value>) -> String {
    match value {
        None => "None".to_string(),
        Some(value) => py_repr_value(value),
    }
}
