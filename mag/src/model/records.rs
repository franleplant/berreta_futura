use super::shared::{quoted, show, Result, ValidationError};
use regex::Regex;
use serde_yaml::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

pub const ARTICLE_FILENAME: &str = "article.md";

pub(crate) fn slug(text: &str) -> String {
    let mut collapsed = String::new();
    let mut pending = false;
    for character in text.to_lowercase().chars() {
        if character.is_ascii_lowercase() || character.is_ascii_digit() {
            if pending && !collapsed.is_empty() {
                collapsed.push('-');
            }
            pending = false;
            collapsed.push(character);
        } else {
            pending = true;
        }
    }
    let trimmed: String = collapsed.chars().take(48).collect();
    if trimmed.is_empty() {
        "source".to_string()
    } else {
        trimmed
    }
}

fn timestamp_detect() -> &'static Regex {
    static PATTERN: OnceLock<Regex> = OnceLock::new();
    PATTERN.get_or_init(|| {
        Regex::new(
            r"^(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt]|[ \t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]*)?(?:[ \t]*(?:Z|[-+][0-9]{1,2}(?::[0-9]{2})?))?)$",
        )
        .expect("the pattern compiles")
    })
}

fn timestamp_parse() -> &'static Regex {
    static PATTERN: OnceLock<Regex> = OnceLock::new();
    PATTERN.get_or_init(|| {
        Regex::new(
            r"^(?P<year>[0-9]{4})-(?P<month>[0-9]{1,2})-(?P<day>[0-9]{1,2})(?:(?:[Tt]|[ \t]+)(?P<hour>[0-9]{1,2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})(?:\.(?P<fraction>[0-9]*))?(?:[ \t]*(?:(?P<utc>Z)|(?P<sign>[-+])(?P<tzhour>[0-9]{1,2})(?::(?P<tzminute>[0-9]{2}))?))?)?$",
        )
        .expect("the pattern compiles")
    })
}

pub fn yaml_timestamp_isoformat(text: &str) -> Option<String> {
    if !timestamp_detect().is_match(text) {
        return None;
    }
    let captures = timestamp_parse().captures(text)?;
    let number = |name: &str| -> u32 {
        captures
            .name(name)
            .map(|found| found.as_str().parse().unwrap_or_default())
            .unwrap_or_default()
    };
    let year = number("year");
    let month = number("month");
    let day = number("day");
    let date = format!("{year:04}-{month:02}-{day:02}");
    if captures.name("hour").is_none() {
        return Some(date);
    }
    let mut rendered = format!(
        "{date}T{:02}:{:02}:{:02}",
        number("hour"),
        number("minute"),
        number("second")
    );
    if let Some(found) = captures.name("fraction") {
        let mut digits: String = found.as_str().chars().take(6).collect();
        while digits.len() < 6 {
            digits.push('0');
        }
        let micro: u32 = digits.parse().unwrap_or_default();
        if micro != 0 {
            rendered.push_str(&format!(".{micro:06}"));
        }
    }
    if captures.name("utc").is_some() {
        rendered.push_str("+00:00");
    } else if let Some(sign) = captures.name("sign") {
        rendered.push_str(&format!(
            "{}{:02}:{:02}",
            sign.as_str(),
            number("tzhour"),
            number("tzminute")
        ));
    }
    Some(rendered)
}

fn plain_scalar(text: &str, key: &str) -> Option<String> {
    for line in text.lines() {
        let Some(rest) = line.strip_prefix(key) else {
            continue;
        };
        let Some(rest) = rest.strip_prefix(':') else {
            continue;
        };
        if line.starts_with(char::is_whitespace) {
            continue;
        }
        let value = match rest.find(" #") {
            Some(mark) => &rest[..mark],
            None => rest,
        };
        let value = value.trim();
        if value.is_empty() || value.starts_with('\'') || value.starts_with('"') {
            return None;
        }
        return Some(value.to_string());
    }
    None
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceRecord {
    pub id: String,
    pub url: String,
    pub title: String,
    pub captured_at: String,
    pub author: Option<String>,
    pub published_at: Option<String>,
    pub tags: Option<Vec<String>>,
    pub synopsis: Option<String>,
    pub notes: Option<String>,
}

fn text_field(value: Option<&Value>, key: &str) -> Result<Option<String>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => Ok(Some(text.clone())),
        Some(other) => Err(ValidationError::one(format!(
            "Source record field {key} must be a string, got: {other:?}"
        ))),
    }
}

fn filled(value: Option<&String>) -> bool {
    value.is_some_and(|text| !text.is_empty())
}

impl SourceRecord {
    pub fn from_value(data: &Value, document: Option<&str>) -> Result<Self> {
        let Value::Mapping(mapping) = data else {
            return Err(ValidationError::one("Source record must be a mapping"));
        };
        let get = |key: &str| mapping.get(Value::String(key.to_string()));
        let url = resolve_url(mapping)?;
        let mut published_origin = "published_at";
        let mut published_at = text_field(get("published_at"), "published_at")?;
        if !filled(published_at.as_ref()) {
            published_origin = "publication_date";
            published_at = text_field(get("publication_date"), "publication_date")?;
        }
        let mut captured_at = text_field(get("captured_at"), "captured_at")?;
        coerce_timestamp(document, "captured_at", &mut captured_at);
        coerce_timestamp(document, published_origin, &mut published_at);
        let metadata = match get("metadata") {
            Some(Value::Mapping(inner)) => Some(inner),
            _ => None,
        };
        let tags = resolve_tags(mapping, metadata)?;
        let synopsis = resolve_synopsis(mapping, metadata)?;
        let notes = match get("notes") {
            None => Some(String::new()),
            Some(value) => text_field(Some(value), "notes")?,
        };
        let id = text_field(get("id"), "id")?;
        let title = text_field(get("title"), "title")?;
        let missing: Vec<&str> = [
            ("id", filled(id.as_ref())),
            ("url", filled(url.as_ref())),
            ("title", filled(title.as_ref())),
            ("captured_at", filled(captured_at.as_ref())),
        ]
        .into_iter()
        .filter(|(_, present)| !present)
        .map(|(name, _)| name)
        .collect();
        if !missing.is_empty() {
            return Err(ValidationError::one(format!(
                "Source record missing: {}",
                missing.join(", ")
            )));
        }
        Ok(Self {
            id: id.unwrap_or_default(),
            url: url.unwrap_or_default(),
            title: title.unwrap_or_default(),
            captured_at: captured_at.unwrap_or_default(),
            author: text_field(get("author"), "author")?,
            published_at,
            tags,
            synopsis,
            notes,
        })
    }
}

fn mapping_get<'a>(mapping: &'a serde_yaml::Mapping, key: &str) -> Option<&'a Value> {
    mapping.get(Value::String(key.to_string()))
}

fn resolve_url(mapping: &serde_yaml::Mapping) -> Result<Option<String>> {
    for key in ["url", "canonical_url", "submitted_url"] {
        let value = text_field(mapping_get(mapping, key), key)?;
        if filled(value.as_ref()) {
            return Ok(value);
        }
    }
    Ok(None)
}

fn coerce_timestamp(document: Option<&str>, key: &str, slot: &mut Option<String>) {
    let Some(text) = document else { return };
    let Some(current) = slot.clone() else { return };
    let Some(raw) = plain_scalar(text, key) else {
        return;
    };
    if raw == current {
        if let Some(coerced) = yaml_timestamp_isoformat(&raw) {
            *slot = Some(coerced);
        }
    }
}

fn resolve_tags(
    mapping: &serde_yaml::Mapping,
    metadata: Option<&serde_yaml::Mapping>,
) -> Result<Option<Vec<String>>> {
    let value = match mapping_get(mapping, "tags") {
        Some(value) => Some(value),
        None => metadata.and_then(|inner| mapping_get(inner, "tags")),
    };
    match value {
        Some(Value::Null) => Ok(None),
        Some(Value::Sequence(items)) => Ok(Some(string_list(items, "tags")?)),
        Some(other) => Err(ValidationError::one(format!(
            "Source record field tags must be a list, got: {other:?}"
        ))),
        None => Ok(Some(Vec::new())),
    }
}

fn resolve_synopsis(
    mapping: &serde_yaml::Mapping,
    metadata: Option<&serde_yaml::Mapping>,
) -> Result<Option<String>> {
    match mapping_get(mapping, "synopsis") {
        Some(value) => text_field(Some(value), "synopsis"),
        None => match metadata.and_then(|inner| mapping_get(inner, "synopsis")) {
            Some(value) => text_field(Some(value), "synopsis"),
            None => Ok(Some(String::new())),
        },
    }
}

fn string_list(items: &[Value], key: &str) -> Result<Vec<String>> {
    items
        .iter()
        .map(|item| match item {
            Value::String(text) => Ok(text.clone()),
            other => Err(ValidationError::one(format!(
                "Source record field {key} must hold strings, got: {other:?}"
            ))),
        })
        .collect()
}

fn record_glob(name: &str) -> bool {
    name.starts_with("record.y") && name.ends_with("ml") && name.len() >= "record.yml".len()
}

pub fn load_records(sources_dir: &Path) -> Result<Vec<SourceRecord>> {
    if !sources_dir.exists() {
        return Ok(Vec::new());
    }
    let mut paths: Vec<PathBuf> = Vec::new();
    let entries = std::fs::read_dir(sources_dir)
        .map_err(|error| ValidationError::one(format!("Cannot read {sources_dir:?}: {error}")))?;
    for entry in entries {
        let entry =
            entry.map_err(|error| ValidationError::one(format!("Cannot read entry: {error}")))?;
        if !entry.path().is_dir() {
            continue;
        }
        let inner = std::fs::read_dir(entry.path()).map_err(|error| {
            ValidationError::one(format!("Cannot read {:?}: {error}", entry.path()))
        })?;
        for candidate in inner {
            let candidate = candidate
                .map_err(|error| ValidationError::one(format!("Cannot read entry: {error}")))?;
            let name = candidate.file_name().to_string_lossy().into_owned();
            if record_glob(&name) && candidate.path().is_file() {
                paths.push(candidate.path());
            }
        }
    }
    paths.sort();
    let mut records = Vec::new();
    for path in &paths {
        let text = std::fs::read_to_string(path)
            .map_err(|error| ValidationError::one(format!("Cannot read {path:?}: {error}")))?;
        let data: Value = serde_yaml::from_str(&text)
            .map_err(|error| ValidationError::one(format!("Cannot read {path:?}: {error}")))?;
        if !matches!(data, Value::Mapping(_)) {
            return Err(ValidationError::one(format!(
                "{path:?} must contain a mapping"
            )));
        }
        records.push(SourceRecord::from_value(&data, Some(&text))?);
    }
    let mut seen: BTreeMap<String, String> = BTreeMap::new();
    for record in &records {
        if let Some(first) = seen.get(&record.url) {
            return Err(ValidationError::one(format!(
                "Duplicate URL in {first} and {}",
                record.id
            )));
        }
        seen.insert(record.url.clone(), record.id.clone());
    }
    records.sort_by(|left, right| {
        right
            .captured_at
            .cmp(&left.captured_at)
            .then_with(|| right.id.cmp(&left.id))
    });
    Ok(records)
}

pub const FIGURE_LAYOUTS: [&str; 9] = [
    "evidence_band",
    "evidence_band_prose",
    "adaptive_band",
    "compact_band",
    "column_plate",
    "landscape_plate",
    "landscape_plate_after",
    "full_band",
    "rotated_plate",
];

const FIGURE_TONES: [&str; 3] = ["auto", "keep", "invert"];
const FIGURE_FITS: [&str; 2] = ["auto", "keep"];

pub const EXTRACT_STYLES: [&str; 2] = ["code", "quote"];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Figure {
    pub id: String,
    pub source_id: String,
    pub path: PathBuf,
    pub caption: String,
    pub credit: String,
    pub alt_text: String,
    pub anchor: String,
    pub layout: String,
    pub tone: String,
    pub fit: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Extract {
    pub id: String,
    pub source_id: String,
    pub text: String,
    pub style: String,
    pub caption: String,
    pub anchor: String,
}

pub fn semantic_headings(path: &Path) -> Result<BTreeSet<String>> {
    let text = std::fs::read_to_string(path)
        .map_err(|error| ValidationError::one(format!("Cannot read {path:?}: {error}")))?;
    let mut headings = BTreeSet::new();
    for line in text.split(|c| {
        matches!(
            c,
            '\n' | '\r' | '\u{b}' | '\u{c}' | '\u{1c}'
                ..='\u{1e}' | '\u{85}' | '\u{2028}' | '\u{2029}'
        )
    }) {
        for prefix in ["## ", "### "] {
            if let Some(rest) = line.strip_prefix(prefix) {
                if !rest.trim().is_empty() {
                    headings.insert(rest.trim().to_string());
                }
            }
        }
    }
    Ok(headings)
}

fn row_text(name: &str, value: Option<&Value>) -> Result<String> {
    match value {
        None | Some(Value::Null) => Ok(String::new()),
        Some(Value::String(text)) => Ok(text.clone()),
        Some(other) => Err(ValidationError::one(format!(
            "Figure and extract field {name} must be text, not {}",
            show(other)
        ))),
    }
}

fn row_field(row: &serde_yaml::Mapping, name: &str) -> Result<String> {
    row_text(name, row.get(Value::String(name.to_string())))
}

fn rows_of(rows: Option<&Value>) -> Option<&Vec<Value>> {
    match rows {
        Some(Value::Sequence(items)) => Some(items),
        _ => None,
    }
}

fn is_absent(rows: Option<&Value>) -> bool {
    match rows {
        None | Some(Value::Null) => true,
        Some(Value::Sequence(items)) => items.is_empty(),
        _ => false,
    }
}

fn path_parts(value: &str) -> Vec<&str> {
    value
        .split('/')
        .filter(|part| !part.is_empty() && *part != ".")
        .collect()
}

fn unsafe_path(value: &str) -> bool {
    let parts = path_parts(value);
    parts.is_empty() || value.starts_with('/') || parts.contains(&"..")
}

pub struct FigureRequest<'a> {
    pub root: &'a Path,
    pub article_id: &'a str,
    pub article_source_ids: &'a [String],
    pub manuscript: &'a Path,
    pub allow_unanchored: bool,
    pub verbatim: bool,
}

pub fn resolve_figures(request: &FigureRequest, rows: Option<&Value>) -> Result<Vec<Figure>> {
    if is_absent(rows) {
        return Ok(Vec::new());
    }
    let Some(items) = rows_of(rows) else {
        return Err(ValidationError::one(format!(
            "Article {} figures must be a list",
            request.article_id
        )));
    };
    if items.len() > 3 && !request.verbatim {
        return Err(ValidationError::one(format!(
            "Article {} selects {} figures; maximum is 3",
            request.article_id,
            items.len()
        )));
    }
    let mut errors: Vec<String> = Vec::new();
    let mut figures: Vec<Figure> = Vec::new();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let headings = semantic_headings(request.manuscript)?;
    for (index, row) in items.iter().enumerate() {
        let label = format!("Article {} figure {}", request.article_id, index + 1);
        let Value::Mapping(mapping) = row else {
            errors.push(format!("{label} must be a mapping"));
            continue;
        };
        let names = [
            "id",
            "source_id",
            "path",
            "caption",
            "credit",
            "alt_text",
            "anchor",
            "layout",
            "tone",
            "fit",
        ];
        let mut fields: BTreeMap<&str, String> = BTreeMap::new();
        for name in names {
            fields.insert(name, row_field(mapping, name)?.trim().to_string());
        }
        let missing: Vec<&str> = names
            .into_iter()
            .filter(|name| !["credit", "tone", "fit"].contains(name) && fields[name].is_empty())
            .collect();
        if !missing.is_empty() {
            errors.push(format!("{label} missing: {}", missing.join(", ")));
            continue;
        }
        if seen.contains(&fields["id"]) {
            errors.push(format!(
                "Article {} has duplicate figure id: {}",
                request.article_id, fields["id"]
            ));
        }
        seen.insert(fields["id"].clone());
        if let Some(figure) = resolve_figure(request, &label, &fields, &headings, &mut errors) {
            figures.push(figure);
        }
    }
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    Ok(figures)
}

fn resolve_figure(
    request: &FigureRequest,
    label: &str,
    fields: &BTreeMap<&str, String>,
    headings: &BTreeSet<String>,
    errors: &mut Vec<String>,
) -> Option<Figure> {
    if !request
        .article_source_ids
        .iter()
        .any(|candidate| candidate == &fields["source_id"])
    {
        errors.push(format!(
            "{label} source_id must be one of the article source_ids"
        ));
    }
    let relative = fields["path"].clone();
    if unsafe_path(&relative) {
        errors.push(format!(
            "{label} has unsafe path: {}",
            quoted(&fields["path"])
        ));
        return None;
    }
    if !FIGURE_LAYOUTS.contains(&fields["layout"].as_str()) {
        let shown = if fields["layout"].is_empty() {
            "<missing>".to_string()
        } else {
            fields["layout"].clone()
        };
        errors.push(format!("{label} has invalid layout: {shown}"));
    }
    let tone = match fields["tone"].as_str() {
        "" => "auto".to_string(),
        tone => tone.to_string(),
    };
    if !FIGURE_TONES.contains(&tone.as_str()) {
        errors.push(format!(
            "{label} has invalid tone: {tone} (auto, keep, or invert)"
        ));
    }
    let fit = match fields["fit"].as_str() {
        "" => "auto".to_string(),
        fit => fit.to_string(),
    };
    if !FIGURE_FITS.contains(&fit.as_str()) {
        errors.push(format!("{label} has invalid fit: {fit} (auto or keep)"));
    }
    let anchor = fields["anchor"].clone();
    if anchor != "__opener__" && !headings.contains(&anchor) && !request.allow_unanchored {
        errors.push(format!(
            "{label} anchor does not match an article heading: {}",
            quoted(&anchor)
        ));
    }
    let mut path = request
        .root
        .join("library")
        .join("sources")
        .join(&fields["source_id"]);
    for part in path_parts(&relative) {
        path = path.join(part);
    }
    if !path.is_file() {
        errors.push(format!("{label} image file is missing: {}", path.display()));
        return None;
    }
    Some(Figure {
        id: fields["id"].clone(),
        source_id: fields["source_id"].clone(),
        path,
        caption: fields["caption"].clone(),
        credit: fields["credit"].clone(),
        alt_text: fields["alt_text"].clone(),
        anchor,
        layout: fields["layout"].clone(),
        tone,
        fit,
    })
}

pub struct ExtractRequest<'a> {
    pub root: &'a Path,
    pub article_id: &'a str,
    pub article_source_ids: &'a [String],
    pub manuscript: &'a Path,
    pub allow_unanchored: bool,
}

pub fn resolve_extracts(request: &ExtractRequest, rows: Option<&Value>) -> Result<Vec<Extract>> {
    if is_absent(rows) {
        return Ok(Vec::new());
    }
    let Some(items) = rows_of(rows) else {
        return Err(ValidationError::one(format!(
            "Article {} extracts must be a list",
            request.article_id
        )));
    };
    if items.len() > 2 {
        return Err(ValidationError::one(format!(
            "Article {} selects {} extracts; maximum is 2",
            request.article_id,
            items.len()
        )));
    }
    let mut errors: Vec<String> = Vec::new();
    let mut extracts: Vec<Extract> = Vec::new();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let manuscript_text = std::fs::read_to_string(request.manuscript).map_err(|error| {
        ValidationError::one(format!("Cannot read {:?}: {error}", request.manuscript))
    })?;
    let headings = semantic_headings(request.manuscript)?;
    for (index, row) in items.iter().enumerate() {
        let label = format!("Article {} extract {}", request.article_id, index + 1);
        let Value::Mapping(mapping) = row else {
            errors.push(format!("{label} must be a mapping"));
            continue;
        };
        let mut fields: BTreeMap<&str, String> = BTreeMap::new();
        for name in ["id", "source_id", "style", "caption", "anchor"] {
            fields.insert(name, row_field(mapping, name)?.trim().to_string());
        }
        for name in ["begin", "end"] {
            fields.insert(name, row_field(mapping, name)?);
        }
        let order = [
            "id",
            "source_id",
            "begin",
            "end",
            "style",
            "caption",
            "anchor",
        ];
        let missing: Vec<&str> = order
            .into_iter()
            .filter(|name| fields[name].is_empty())
            .collect();
        if !missing.is_empty() {
            errors.push(format!("{label} missing: {}", missing.join(", ")));
            continue;
        }
        if seen.contains(&fields["id"]) {
            errors.push(format!(
                "Article {} has duplicate extract id: {}",
                request.article_id, fields["id"]
            ));
        }
        seen.insert(fields["id"].clone());
        if !request
            .article_source_ids
            .iter()
            .any(|candidate| candidate == &fields["source_id"])
        {
            errors.push(format!(
                "{label} source_id must be one of the article source_ids"
            ));
            continue;
        }
        check_extract_style(
            &label,
            &fields,
            &headings,
            request.allow_unanchored,
            &mut errors,
        );
        let Some(text) = extract_run(request.root, &label, &fields, &mut errors) else {
            continue;
        };
        check_extract_text(
            &label,
            &fields["style"],
            &text,
            &manuscript_text,
            &mut errors,
        );
        extracts.push(Extract {
            id: fields["id"].clone(),
            source_id: fields["source_id"].clone(),
            text,
            style: fields["style"].clone(),
            caption: fields["caption"].clone(),
            anchor: fields["anchor"].clone(),
        });
    }
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    Ok(extracts)
}

fn check_extract_style(
    label: &str,
    fields: &BTreeMap<&str, String>,
    headings: &BTreeSet<String>,
    allow_unanchored: bool,
    errors: &mut Vec<String>,
) {
    let style = &fields["style"];
    let anchor = &fields["anchor"];
    if !EXTRACT_STYLES.contains(&style.as_str()) {
        errors.push(format!(
            "{label} has invalid style: {}; known: ['code', 'quote']",
            quoted(style)
        ));
    }
    if anchor != "__opener__" && !headings.contains(anchor) && !allow_unanchored {
        errors.push(format!(
            "{label} anchor does not match an article heading: {}",
            quoted(anchor)
        ));
    }
}

fn extract_run(
    root: &Path,
    label: &str,
    fields: &BTreeMap<&str, String>,
    errors: &mut Vec<String>,
) -> Option<String> {
    let source_path = root
        .join("library")
        .join("sources")
        .join(&fields["source_id"])
        .join(ARTICLE_FILENAME);
    if !source_path.is_file() {
        errors.push(format!(
            "{label} source article is missing: {}",
            source_path.display()
        ));
        return None;
    }
    let source_text = std::fs::read_to_string(&source_path).ok()?;
    let begin = &fields["begin"];
    let end = &fields["end"];
    let begins = source_text.matches(begin.as_str()).count();
    if begins != 1 {
        errors.push(format!(
            "{label} begin marker must occur exactly once in the source (found {begins}): {}",
            quoted(begin)
        ));
        return None;
    }
    let start = source_text.find(begin.as_str())?;
    let tail = &source_text[start..];
    let ends = tail.matches(end.as_str()).count();
    if ends != 1 {
        errors.push(format!(
            "{label} end marker must occur exactly once at or after begin (found {ends}): {}",
            quoted(end)
        ));
        return None;
    }
    let stop = start + tail.find(end.as_str())? + end.len();
    Some(source_text[start..stop].to_string())
}

fn check_extract_text(
    label: &str,
    style: &str,
    text: &str,
    manuscript_text: &str,
    errors: &mut Vec<String>,
) {
    if style == "code" && (text.contains('\t') || text.contains("  ")) {
        errors.push(format!(
            "{label} run carries layout-significant whitespace (tabs or space runs), which a wrapping code panel cannot preserve; use begin/end markers that avoid it or style: quote"
        ));
    }
    if manuscript_text.contains(text) {
        errors.push(format!(
            "{label} run already appears verbatim in the manuscript; drop the extract row or the manuscript's own copy"
        ));
    }
}

pub fn localize_figures(
    base: &[Figure],
    rows: Option<&Value>,
    article_id: &str,
    manuscript: &Path,
    language: &str,
) -> Result<Vec<Figure>> {
    let language = quoted(language);
    if base.is_empty() {
        if !is_absent(rows) {
            return Err(ValidationError::one(format!(
                "Translation {language} article {article_id} has figures absent from English"
            )));
        }
        return Ok(Vec::new());
    }
    let items = match rows {
        Some(Value::Sequence(items)) => items.clone(),
        _ => {
            return Err(ValidationError::one(format!(
                "Translation {language} article {article_id} figures must be a list"
            )))
        }
    };
    let mut errors: Vec<String> = Vec::new();
    let by_id = index_rows(&items);
    let expected: BTreeSet<String> = base.iter().map(|figure| figure.id.clone()).collect();
    compare_ids(
        &by_id,
        &expected,
        article_id,
        &language,
        "figures",
        &mut errors,
    );
    let headings = semantic_headings(manuscript)?;
    let mut localized = Vec::new();
    for figure in base {
        let Some(row) = by_id.get(&figure.id) else {
            continue;
        };
        let caption = row_field(row, "caption")?.trim().to_string();
        let credit = {
            let value = row_field(row, "credit")?.trim().to_string();
            if value.is_empty() {
                figure.credit.clone()
            } else {
                value
            }
        };
        let alt_text = row_field(row, "alt_text")?.trim().to_string();
        let anchor = row_field(row, "anchor")?.trim().to_string();
        if caption.is_empty() || alt_text.is_empty() || anchor.is_empty() {
            errors.push(format!(
                "Translation {language} figure {} requires caption, alt_text, and anchor",
                figure.id
            ));
        }
        if anchor != "__opener__" && !headings.contains(&anchor) {
            errors.push(format!(
                "Translation {language} figure {} anchor does not match a translated heading",
                figure.id
            ));
        }
        localized.push(Figure {
            caption,
            credit,
            alt_text,
            anchor,
            ..figure.clone()
        });
    }
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    Ok(localized)
}

pub fn localize_extracts(
    base: &[Extract],
    rows: Option<&Value>,
    article_id: &str,
    manuscript: &Path,
    language: &str,
) -> Result<Vec<Extract>> {
    let language = quoted(language);
    if base.is_empty() {
        if !is_absent(rows) {
            return Err(ValidationError::one(format!(
                "Translation {language} article {article_id} has extracts absent from English"
            )));
        }
        return Ok(Vec::new());
    }
    let items = match rows {
        Some(Value::Sequence(items)) => items.clone(),
        _ => {
            return Err(ValidationError::one(format!(
                "Translation {language} article {article_id} extracts must be a list"
            )))
        }
    };
    let mut errors: Vec<String> = Vec::new();
    let by_id = index_rows(&items);
    let expected: BTreeSet<String> = base.iter().map(|extract| extract.id.clone()).collect();
    compare_ids(
        &by_id,
        &expected,
        article_id,
        &language,
        "extracts",
        &mut errors,
    );
    let headings = semantic_headings(manuscript)?;
    let mut localized = Vec::new();
    for extract in base {
        let Some(row) = by_id.get(&extract.id) else {
            continue;
        };
        let caption = row_field(row, "caption")?.trim().to_string();
        let anchor = row_field(row, "anchor")?.trim().to_string();
        if caption.is_empty() || anchor.is_empty() {
            errors.push(format!(
                "Translation {language} extract {} requires caption and anchor",
                extract.id
            ));
        }
        if anchor != "__opener__" && !headings.contains(&anchor) {
            errors.push(format!(
                "Translation {language} extract {} anchor does not match a translated heading",
                extract.id
            ));
        }
        localized.push(Extract {
            caption,
            anchor,
            ..extract.clone()
        });
    }
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    Ok(localized)
}

fn index_rows(items: &[Value]) -> BTreeMap<String, serde_yaml::Mapping> {
    let mut by_id = BTreeMap::new();
    for item in items {
        let Value::Mapping(mapping) = item else {
            continue;
        };
        let Some(id) = mapping.get(Value::String("id".into())) else {
            continue;
        };
        let Ok(text) = row_text("id", Some(id)) else {
            continue;
        };
        if text.is_empty() {
            continue;
        }
        by_id.insert(text, mapping.clone());
    }
    by_id
}

fn compare_ids(
    by_id: &BTreeMap<String, serde_yaml::Mapping>,
    expected: &BTreeSet<String>,
    article_id: &str,
    language: &str,
    kind: &str,
    errors: &mut Vec<String>,
) {
    let present: BTreeSet<String> = by_id.keys().cloned().collect();
    if &present == expected {
        return;
    }
    let missing: Vec<String> = expected.difference(&present).cloned().collect();
    let extra: Vec<String> = present.difference(expected).cloned().collect();
    if !missing.is_empty() {
        errors.push(format!(
            "Translation {language} article {article_id} is missing {kind}: {}",
            missing.join(", ")
        ));
    }
    if !extra.is_empty() {
        errors.push(format!(
            "Translation {language} article {article_id} has unknown {kind}: {}",
            extra.join(", ")
        ));
    }
}
