use super::kinds::{ExtractStyle, FigureFit, FigureLayout, FigureTone};
use super::shared::{quoted, read_spec, Result, ValidationError};
use super::spec::{ExtractRow, FigureRow, LocalizedExtractRow, LocalizedFigureRow, SourceRecord};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

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

fn record_glob(name: &str) -> bool {
    name.starts_with("record.y") && name.ends_with("ml") && name.len() >= "record.yml".len()
}

fn record_paths(sources_dir: &Path) -> Result<Vec<PathBuf>> {
    let unreadable = |path: &Path, error: std::io::Error| {
        ValidationError::one(format!("Cannot read {path:?}: {error}"))
    };
    let mut paths = Vec::new();
    for entry in std::fs::read_dir(sources_dir).map_err(|error| unreadable(sources_dir, error))? {
        let dir = entry
            .map_err(|error| unreadable(sources_dir, error))?
            .path();
        if !dir.is_dir() {
            continue;
        }
        for file in std::fs::read_dir(&dir).map_err(|error| unreadable(&dir, error))? {
            let file = file.map_err(|error| unreadable(&dir, error))?.path();
            let name = file
                .file_name()
                .map(|name| name.to_string_lossy().into_owned());
            if file.is_file() && name.is_some_and(|name| record_glob(&name)) {
                paths.push(file);
            }
        }
    }
    paths.sort();
    Ok(paths)
}

pub fn load_records(sources_dir: &Path) -> Result<Vec<SourceRecord>> {
    if !sources_dir.exists() {
        return Ok(Vec::new());
    }
    let mut records = Vec::new();
    for path in record_paths(sources_dir)? {
        let record: SourceRecord = read_spec(&path)?;
        let missing = blanks(&[
            ("id", record.id.is_empty()),
            ("url", record.url.is_empty()),
            ("title", record.title.is_empty()),
            ("captured_at", record.captured_at.is_empty()),
        ]);
        if !missing.is_empty() {
            return Err(ValidationError::one(format!(
                "Source record {path:?} missing: {}",
                missing.join(", ")
            )));
        }
        records.push(record);
    }
    let mut seen: BTreeMap<&str, &str> = BTreeMap::new();
    for record in &records {
        if let Some(first) = seen.insert(&record.url, &record.id) {
            return Err(ValidationError::one(format!(
                "Duplicate URL in {first} and {}",
                record.id
            )));
        }
    }
    records.sort_by(|left, right| {
        right
            .captured_at
            .cmp(&left.captured_at)
            .then_with(|| right.id.cmp(&left.id))
    });
    Ok(records)
}

pub(crate) fn blanks<'a>(fields: &[(&'a str, bool)]) -> Vec<&'a str> {
    fields
        .iter()
        .filter(|(_, blank)| *blank)
        .map(|(name, _)| *name)
        .collect()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Figure {
    pub id: String,
    pub source_id: String,
    pub path: PathBuf,
    pub caption: String,
    pub credit: String,
    pub alt_text: String,
    pub anchor: String,
    pub layout: FigureLayout,
    pub tone: FigureTone,
    pub fit: FigureFit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Extract {
    pub id: String,
    pub source_id: String,
    pub text: String,
    pub style: ExtractStyle,
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

fn check_anchor(
    label: &str,
    anchor: &str,
    headings: &BTreeSet<String>,
    allow_unanchored: bool,
    errors: &mut Vec<String>,
) {
    if anchor != "__opener__" && !headings.contains(anchor) && !allow_unanchored {
        errors.push(format!(
            "{label} anchor does not match an article heading: {}",
            quoted(anchor)
        ));
    }
}

pub struct FigureRequest<'a> {
    pub root: &'a Path,
    pub article_id: &'a str,
    pub article_source_ids: &'a [String],
    pub manuscript: &'a Path,
    pub allow_unanchored: bool,
    pub verbatim: bool,
}

pub fn resolve_figures(request: &FigureRequest, rows: &[FigureRow]) -> Result<Vec<Figure>> {
    if rows.is_empty() {
        return Ok(Vec::new());
    }
    if rows.len() > 3 && !request.verbatim {
        return Err(ValidationError::one(format!(
            "Article {} selects {} figures; maximum is 3",
            request.article_id,
            rows.len()
        )));
    }
    let mut errors: Vec<String> = Vec::new();
    let mut figures: Vec<Figure> = Vec::new();
    let mut seen: BTreeSet<&str> = BTreeSet::new();
    let headings = semantic_headings(request.manuscript)?;
    for (index, row) in rows.iter().enumerate() {
        let label = format!("Article {} figure {}", request.article_id, index + 1);
        let blank = |text: &str| text.trim().is_empty();
        let missing = blanks(&[
            ("id", blank(&row.id)),
            ("source_id", blank(&row.source_id)),
            ("path", blank(&row.path)),
            ("caption", blank(&row.caption)),
            ("alt_text", blank(&row.alt_text)),
            ("anchor", blank(&row.anchor)),
            ("layout", row.layout.is_none()),
        ]);
        if !missing.is_empty() {
            errors.push(format!("{label} missing: {}", missing.join(", ")));
            continue;
        }
        if !seen.insert(row.id.trim()) {
            errors.push(format!(
                "Article {} has duplicate figure id: {}",
                request.article_id,
                row.id.trim()
            ));
        }
        if let Some(figure) = resolve_figure(request, &label, row, &headings, &mut errors) {
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
    row: &FigureRow,
    headings: &BTreeSet<String>,
    errors: &mut Vec<String>,
) -> Option<Figure> {
    let source_id = row.source_id.trim();
    if !request.article_source_ids.iter().any(|id| id == source_id) {
        errors.push(format!(
            "{label} source_id must be one of the article source_ids"
        ));
    }
    let relative = row.path.trim();
    if unsafe_path(relative) {
        errors.push(format!("{label} has unsafe path: {}", quoted(relative)));
        return None;
    }
    let anchor = row.anchor.trim().to_string();
    check_anchor(label, &anchor, headings, request.allow_unanchored, errors);
    let mut path = request.root.join("library").join("sources").join(source_id);
    for part in path_parts(relative) {
        path = path.join(part);
    }
    if !path.is_file() {
        errors.push(format!("{label} image file is missing: {}", path.display()));
        return None;
    }
    Some(Figure {
        id: row.id.trim().to_string(),
        source_id: source_id.to_string(),
        path,
        caption: row.caption.trim().to_string(),
        credit: row.credit.trim().to_string(),
        alt_text: row.alt_text.trim().to_string(),
        anchor,
        layout: row.layout?,
        tone: row.tone.unwrap_or(FigureTone::Auto),
        fit: row.fit.unwrap_or(FigureFit::Auto),
    })
}

pub struct ExtractRequest<'a> {
    pub root: &'a Path,
    pub article_id: &'a str,
    pub article_source_ids: &'a [String],
    pub manuscript: &'a Path,
    pub allow_unanchored: bool,
}

pub fn resolve_extracts(request: &ExtractRequest, rows: &[ExtractRow]) -> Result<Vec<Extract>> {
    if rows.is_empty() {
        return Ok(Vec::new());
    }
    if rows.len() > 2 {
        return Err(ValidationError::one(format!(
            "Article {} selects {} extracts; maximum is 2",
            request.article_id,
            rows.len()
        )));
    }
    let mut errors: Vec<String> = Vec::new();
    let mut extracts: Vec<Extract> = Vec::new();
    let mut seen: BTreeSet<&str> = BTreeSet::new();
    let manuscript_text = std::fs::read_to_string(request.manuscript).map_err(|error| {
        ValidationError::one(format!("Cannot read {:?}: {error}", request.manuscript))
    })?;
    let headings = semantic_headings(request.manuscript)?;
    for (index, row) in rows.iter().enumerate() {
        let label = format!("Article {} extract {}", request.article_id, index + 1);
        let blank = |text: &str| text.trim().is_empty();
        let missing = blanks(&[
            ("id", blank(&row.id)),
            ("source_id", blank(&row.source_id)),
            ("begin", row.begin.is_empty()),
            ("end", row.end.is_empty()),
            ("style", row.style.is_none()),
            ("caption", blank(&row.caption)),
            ("anchor", blank(&row.anchor)),
        ]);
        let (Some(style), true) = (row.style, missing.is_empty()) else {
            errors.push(format!("{label} missing: {}", missing.join(", ")));
            continue;
        };
        if !seen.insert(row.id.trim()) {
            errors.push(format!(
                "Article {} has duplicate extract id: {}",
                request.article_id,
                row.id.trim()
            ));
        }
        let source_id = row.source_id.trim();
        if !request.article_source_ids.iter().any(|id| id == source_id) {
            errors.push(format!(
                "{label} source_id must be one of the article source_ids"
            ));
            continue;
        }
        let anchor = row.anchor.trim().to_string();
        check_anchor(
            &label,
            &anchor,
            &headings,
            request.allow_unanchored,
            &mut errors,
        );
        let Some(text) = extract_run(request.root, &label, row, &mut errors) else {
            continue;
        };
        check_extract_text(&label, style, &text, &manuscript_text, &mut errors);
        extracts.push(Extract {
            id: row.id.trim().to_string(),
            source_id: source_id.to_string(),
            text,
            style,
            caption: row.caption.trim().to_string(),
            anchor,
        });
    }
    if !errors.is_empty() {
        return Err(ValidationError(errors));
    }
    Ok(extracts)
}

fn extract_run(
    root: &Path,
    label: &str,
    row: &ExtractRow,
    errors: &mut Vec<String>,
) -> Option<String> {
    let source_path = root
        .join("library")
        .join("sources")
        .join(row.source_id.trim())
        .join(ARTICLE_FILENAME);
    if !source_path.is_file() {
        errors.push(format!(
            "{label} source article is missing: {}",
            source_path.display()
        ));
        return None;
    }
    let source_text = std::fs::read_to_string(&source_path).ok()?;
    let (begin, end) = (row.begin.as_str(), row.end.as_str());
    let begins = source_text.matches(begin).count();
    if begins != 1 {
        errors.push(format!(
            "{label} begin marker must occur exactly once in the source (found {begins}): {}",
            quoted(begin)
        ));
        return None;
    }
    let start = source_text.find(begin)?;
    let tail = &source_text[start..];
    let ends = tail.matches(end).count();
    if ends != 1 {
        errors.push(format!(
            "{label} end marker must occur exactly once at or after begin (found {ends}): {}",
            quoted(end)
        ));
        return None;
    }
    let stop = start + tail.find(end)? + end.len();
    Some(source_text[start..stop].to_string())
}

fn check_extract_text(
    label: &str,
    style: ExtractStyle,
    text: &str,
    manuscript_text: &str,
    errors: &mut Vec<String>,
) {
    if style == ExtractStyle::Code && (text.contains('\t') || text.contains("  ")) {
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

fn localized_rows<'a, T>(
    base_ids: Vec<&str>,
    rows: Option<&'a [T]>,
    id_of: impl Fn(&T) -> &str,
    article_id: &str,
    language: &str,
    noun: &str,
) -> Result<BTreeMap<&'a str, &'a T>> {
    if base_ids.is_empty() {
        return match rows.unwrap_or_default() {
            [] => Ok(BTreeMap::new()),
            _ => Err(ValidationError::one(format!(
                "Translation {language} article {article_id} has {noun} absent from English"
            ))),
        };
    }
    let Some(rows) = rows else {
        return Err(ValidationError::one(format!(
            "Translation {language} article {article_id} {noun} must be a list"
        )));
    };
    let by_id: BTreeMap<&str, &T> = rows
        .iter()
        .map(|row| (id_of(row), row))
        .filter(|(id, _)| !id.is_empty())
        .collect();
    let expected: BTreeSet<&str> = base_ids.into_iter().collect();
    let present: BTreeSet<&str> = by_id.keys().copied().collect();
    let mut errors = Vec::new();
    for (state, ids) in [
        ("is missing", expected.difference(&present)),
        ("has unknown", present.difference(&expected)),
    ] {
        let ids: Vec<&str> = ids.copied().collect();
        if !ids.is_empty() {
            errors.push(format!(
                "Translation {language} article {article_id} {state} {noun}: {}",
                ids.join(", ")
            ));
        }
    }
    match errors.is_empty() {
        true => Ok(by_id),
        false => Err(ValidationError(errors)),
    }
}

pub fn localize_figures(
    base: &[Figure],
    rows: Option<&[LocalizedFigureRow]>,
    article_id: &str,
    manuscript: &Path,
    language: &str,
) -> Result<Vec<Figure>> {
    let language = quoted(language);
    let ids = base.iter().map(|figure| figure.id.as_str()).collect();
    let by_id = localized_rows(ids, rows, |row| &row.id, article_id, &language, "figures")?;
    let headings = semantic_headings(manuscript)?;
    let mut errors: Vec<String> = Vec::new();
    let mut localized = Vec::new();
    for figure in base {
        let row = by_id[figure.id.as_str()];
        let (caption, alt_text, anchor) = (
            row.caption.trim().to_string(),
            row.alt_text.trim().to_string(),
            row.anchor.trim().to_string(),
        );
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
        let credit = match row.credit.trim() {
            "" => figure.credit.clone(),
            credit => credit.to_string(),
        };
        localized.push(Figure {
            caption,
            credit,
            alt_text,
            anchor,
            ..figure.clone()
        });
    }
    match errors.is_empty() {
        true => Ok(localized),
        false => Err(ValidationError(errors)),
    }
}

pub fn localize_extracts(
    base: &[Extract],
    rows: Option<&[LocalizedExtractRow]>,
    article_id: &str,
    manuscript: &Path,
    language: &str,
) -> Result<Vec<Extract>> {
    let language = quoted(language);
    let ids = base.iter().map(|extract| extract.id.as_str()).collect();
    let by_id = localized_rows(ids, rows, |row| &row.id, article_id, &language, "extracts")?;
    let headings = semantic_headings(manuscript)?;
    let mut errors: Vec<String> = Vec::new();
    let mut localized = Vec::new();
    for extract in base {
        let row = by_id[extract.id.as_str()];
        let (caption, anchor) = (
            row.caption.trim().to_string(),
            row.anchor.trim().to_string(),
        );
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
    match errors.is_empty() {
        true => Ok(localized),
        false => Err(ValidationError(errors)),
    }
}
