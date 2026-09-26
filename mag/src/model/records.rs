use super::shared::{py_repr, PyStrip, Result, ValidationError};
use regex::Regex;
use serde_json::{json, Map, Value as Json};
use serde_yaml::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const TRACKING: [&str; 6] = ["fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"];

pub const ARTICLE_FILENAME: &str = "article.md";

struct UrlParts {
    scheme: String,
    netloc: String,
    path: String,
    query: String,
}

fn scheme_char(value: char) -> bool {
    value.is_ascii_alphanumeric() || matches!(value, '+' | '-' | '.')
}

fn urlsplit(url: &str) -> UrlParts {
    let stripped: String = url
        .chars()
        .filter(|c| !matches!(c, '\t' | '\r' | '\n'))
        .collect();
    let mut rest = stripped.as_str();
    let mut scheme = String::new();
    if let Some(colon) = rest.find(':') {
        let candidate = &rest[..colon];
        let first = candidate.chars().next();
        if colon > 0
            && first.is_some_and(|c| c.is_ascii_alphabetic())
            && candidate.chars().all(scheme_char)
        {
            scheme = candidate.to_lowercase();
            rest = &rest[colon + 1..];
        }
    }
    let mut netloc = String::new();
    if let Some(after) = rest.strip_prefix("//") {
        let end = after.find(['/', '?', '#']).unwrap_or(after.len());
        netloc = after[..end].to_string();
        rest = &after[end..];
    }
    if let Some(hash) = rest.find('#') {
        rest = &rest[..hash];
    }
    let (path, query) = match rest.find('?') {
        Some(mark) => (&rest[..mark], &rest[mark + 1..]),
        None => (rest, ""),
    };
    UrlParts {
        scheme,
        netloc,
        path: path.to_string(),
        query: query.to_string(),
    }
}

fn host_and_port(netloc: &str) -> Result<(String, Option<u32>)> {
    let hostinfo = match netloc.rfind('@') {
        Some(at) => &netloc[at + 1..],
        None => netloc,
    };
    let (host, port) = match hostinfo.find('[') {
        Some(open) => {
            let bracketed = &hostinfo[open + 1..];
            let (inside, after) = match bracketed.find(']') {
                Some(close) => (&bracketed[..close], &bracketed[close + 1..]),
                None => (bracketed, ""),
            };
            let port = after.find(':').map(|mark| &after[mark + 1..]).unwrap_or("");
            (inside, port)
        }
        None => match hostinfo.find(':') {
            Some(mark) => (&hostinfo[..mark], &hostinfo[mark + 1..]),
            None => (hostinfo, ""),
        },
    };
    let parsed = if port.is_empty() {
        None
    } else if !port.chars().all(|character| character.is_ascii_digit()) {
        return Err(ValidationError::one(format!(
            "Port could not be cast to integer value as {}",
            py_repr(port)
        )));
    } else {
        let digits = port.trim_start_matches('0');
        let number: u32 = if digits.is_empty() {
            0
        } else {
            digits.parse().unwrap_or(u32::MAX)
        };
        if digits.len() > 5 || number > 65535 {
            return Err(ValidationError::one(
                "Port out of range 0-65535".to_string(),
            ));
        }
        Some(number)
    };
    Ok((host.to_lowercase(), parsed))
}

fn quote_plus(value: &str) -> String {
    let mut out = String::new();
    for byte in value.as_bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'_' | b'.' | b'-' | b'~' => {
                out.push(*byte as char)
            }
            b' ' => out.push('+'),
            _ => out.push_str(&format!("%{byte:02X}")),
        }
    }
    out
}

fn unquote_plus(value: &str) -> String {
    let source = value.replace('+', " ");
    let bytes = source.as_bytes();
    let mut out: Vec<u8> = Vec::new();
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            let pair = &source[index + 1..index + 3];
            if let Ok(decoded) = u8::from_str_radix(pair, 16) {
                out.push(decoded);
                index += 3;
                continue;
            }
        }
        out.push(bytes[index]);
        index += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn parse_qsl(query: &str) -> Vec<(String, String)> {
    let mut pairs = Vec::new();
    for item in query.split('&') {
        if item.is_empty() {
            continue;
        }
        let (name, value) = match item.find('=') {
            Some(mark) => (&item[..mark], &item[mark + 1..]),
            None => (item, ""),
        };
        pairs.push((unquote_plus(name), unquote_plus(value)));
    }
    pairs
}

pub fn canonicalize_url(url: &str) -> Result<String> {
    let parts = urlsplit(url.trim());
    if !matches!(parts.scheme.as_str(), "http" | "https") || parts.netloc.is_empty() {
        return Err(ValidationError::one(format!(
            "Expected an http(s) URL, got: {url}"
        )));
    }
    let mut query: Vec<(String, String)> = parse_qsl(&parts.query)
        .into_iter()
        .filter(|(key, _)| {
            let lowered = key.to_lowercase();
            !TRACKING.contains(&lowered.as_str()) && !lowered.starts_with("utm_")
        })
        .collect();
    query.sort();
    let (hostname, port) = host_and_port(&parts.netloc)?;
    let mut host = hostname;
    if let Some(number) = port.filter(|number| *number != 0) {
        let default =
            (parts.scheme == "http" && number == 80) || (parts.scheme == "https" && number == 443);
        if !default {
            host = format!("{host}:{number}");
        }
    }
    let collapsed = slashes().replace_all(&parts.path, "/").into_owned();
    let mut path = if collapsed.is_empty() {
        "/".to_string()
    } else {
        collapsed
    };
    if path != "/" {
        path = path.trim_end_matches('/').to_string();
    }
    let encoded = query
        .iter()
        .map(|(key, value)| format!("{}={}", quote_plus(key), quote_plus(value)))
        .collect::<Vec<String>>()
        .join("&");
    let mut result = format!("{}://{}", parts.scheme, host);
    if !path.is_empty() && !path.starts_with('/') {
        result.push('/');
    }
    result.push_str(&path);
    if !encoded.is_empty() {
        result.push('?');
        result.push_str(&encoded);
    }
    Ok(result)
}

fn slashes() -> &'static Regex {
    static PATTERN: OnceLock<Regex> = OnceLock::new();
    PATTERN.get_or_init(|| Regex::new(r"/{2,}").expect("the pattern compiles"))
}

fn slug(text: &str) -> String {
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

pub fn source_id(title: &str, canonical_url: &str) -> String {
    let digest = hex::encode(Sha256::digest(canonical_url.as_bytes()));
    format!("{}-{}", slug(title), &digest[..8])
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

pub struct NewRecord<'a> {
    pub url: &'a str,
    pub title: Option<&'a str>,
    pub author: Option<&'a str>,
    pub published_at: Option<&'a str>,
    pub captured_at: &'a str,
    pub tags: &'a [String],
    pub synopsis: &'a str,
    pub notes: &'a str,
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

fn truthy(value: Option<&String>) -> bool {
    value.is_some_and(|text| !text.is_empty())
}

impl SourceRecord {
    pub fn create(request: &NewRecord) -> Result<Self> {
        let canonical = canonicalize_url(request.url)?;
        let resolved = request
            .title
            .filter(|title| !title.is_empty())
            .unwrap_or(&canonical)
            .trim()
            .to_string();
        let mut unique: BTreeSet<String> = BTreeSet::new();
        for tag in request.tags {
            let cleaned = tag.trim();
            if !cleaned.is_empty() {
                unique.insert(cleaned.to_lowercase());
            }
        }
        Ok(Self {
            id: source_id(&resolved, &canonical),
            url: canonical,
            title: resolved,
            captured_at: request.captured_at.to_string(),
            author: request
                .author
                .filter(|value| !value.is_empty())
                .map(|value| value.trim().to_string()),
            published_at: request.published_at.map(str::to_string),
            tags: Some(unique.into_iter().collect()),
            synopsis: Some(request.synopsis.trim().to_string()),
            notes: Some(request.notes.trim().to_string()),
        })
    }

    pub fn from_value(data: &Value, document: Option<&str>) -> Result<Self> {
        let Value::Mapping(mapping) = data else {
            return Err(ValidationError::one("Source record must be a mapping"));
        };
        let get = |key: &str| mapping.get(Value::String(key.to_string()));
        let url = resolve_url(mapping)?;
        let mut published_origin = "published_at";
        let mut published_at = text_field(get("published_at"), "published_at")?;
        if !truthy(published_at.as_ref()) {
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
            ("id", truthy(id.as_ref())),
            ("url", truthy(url.as_ref())),
            ("title", truthy(title.as_ref())),
            ("captured_at", truthy(captured_at.as_ref())),
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

    pub fn to_json(&self) -> Json {
        let mut result = Map::new();
        result.insert("id".into(), json!(self.id));
        result.insert("title".into(), json!(self.title));
        result.insert("author".into(), json!(self.author));
        result.insert("url".into(), json!(self.url));
        result.insert("captured_at".into(), json!(self.captured_at));
        result.insert("published_at".into(), json!(self.published_at));
        result.insert("tags".into(), json!(self.tags));
        result.insert("synopsis".into(), json!(self.synopsis));
        if truthy(self.notes.as_ref()) {
            result.insert("notes".into(), json!(self.notes));
        }
        Json::Object(result)
    }

    pub fn key_order(&self) -> Vec<&'static str> {
        let mut keys = vec![
            "id",
            "title",
            "author",
            "url",
            "captured_at",
            "published_at",
            "tags",
            "synopsis",
        ];
        if truthy(self.notes.as_ref()) {
            keys.push("notes");
        }
        keys
    }
}

fn mapping_get<'a>(mapping: &'a serde_yaml::Mapping, key: &str) -> Option<&'a Value> {
    mapping.get(Value::String(key.to_string()))
}

fn resolve_url(mapping: &serde_yaml::Mapping) -> Result<Option<String>> {
    for key in ["url", "canonical_url", "submitted_url"] {
        let value = text_field(mapping_get(mapping, key), key)?;
        if truthy(value.as_ref()) {
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

pub const FIGURE_LAYOUTS: [&str; 7] = [
    "evidence_band",
    "evidence_band_prose",
    "adaptive_band",
    "compact_band",
    "column_plate",
    "landscape_plate",
    "landscape_plate_after",
];

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
                if !rest.py_trim().is_empty() {
                    headings.insert(rest.py_trim().to_string());
                }
            }
        }
    }
    Ok(headings)
}

fn python_text(value: Option<&Value>) -> Result<String> {
    Ok(match value {
        None | Some(Value::Null) => String::new(),
        Some(Value::Bool(false)) => String::new(),
        Some(Value::Bool(true)) => "True".to_string(),
        Some(Value::String(text)) => text.clone(),
        Some(Value::Number(number)) => {
            if number.is_f64() {
                let float = number.as_f64().unwrap_or_default();
                if float == 0.0 {
                    String::new()
                } else if float.fract() == 0.0 && float.is_finite() {
                    format!("{float:.1}")
                } else {
                    format!("{float}")
                }
            } else if number.as_i64() == Some(0) || number.as_u64() == Some(0) {
                String::new()
            } else {
                number.to_string()
            }
        }
        Some(Value::Sequence(items)) if items.is_empty() => String::new(),
        Some(Value::Mapping(items)) if items.is_empty() => String::new(),
        Some(other) => {
            return Err(ValidationError::one(format!(
                "Figure and extract fields must be scalars, got: {other:?}"
            )))
        }
    })
}

fn row_field(row: &serde_yaml::Mapping, name: &str) -> Result<String> {
    python_text(row.get(Value::String(name.to_string())))
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
        ];
        let mut fields: BTreeMap<&str, String> = BTreeMap::new();
        for name in names {
            fields.insert(name, row_field(mapping, name)?.py_trim().to_string());
        }
        let missing: Vec<&str> = names
            .into_iter()
            .filter(|name| *name != "credit" && fields[name].is_empty())
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
            py_repr(&fields["path"])
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
    let anchor = fields["anchor"].clone();
    if anchor != "__opener__" && !headings.contains(&anchor) && !request.allow_unanchored {
        errors.push(format!(
            "{label} anchor does not match an article heading: {}",
            py_repr(&anchor)
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
            fields.insert(name, row_field(mapping, name)?.py_trim().to_string());
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
            py_repr(style)
        ));
    }
    if anchor != "__opener__" && !headings.contains(anchor) && !allow_unanchored {
        errors.push(format!(
            "{label} anchor does not match an article heading: {}",
            py_repr(anchor)
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
            py_repr(begin)
        ));
        return None;
    }
    let start = source_text.find(begin.as_str())?;
    let tail = &source_text[start..];
    let ends = tail.matches(end.as_str()).count();
    if ends != 1 {
        errors.push(format!(
            "{label} end marker must occur exactly once at or after begin (found {ends}): {}",
            py_repr(end)
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
    let language = py_repr(language);
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
        let caption = row_field(row, "caption")?.py_trim().to_string();
        let credit = {
            let value = row_field(row, "credit")?.py_trim().to_string();
            if value.is_empty() {
                figure.credit.clone()
            } else {
                value
            }
        };
        let alt_text = row_field(row, "alt_text")?.py_trim().to_string();
        let anchor = row_field(row, "anchor")?.py_trim().to_string();
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
    let language = py_repr(language);
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
        let caption = row_field(row, "caption")?.py_trim().to_string();
        let anchor = row_field(row, "anchor")?.py_trim().to_string();
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
        let Ok(text) = python_text(Some(id)) else {
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
