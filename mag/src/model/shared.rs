use serde_norway::{Mapping, Value};
use std::fmt;
use std::path::{Component, Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationError(pub Vec<String>);

impl ValidationError {
    pub(crate) fn one(message: impl Into<String>) -> Self {
        Self(vec![message.into()])
    }
}

impl fmt::Display for ValidationError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}", self.0.join("\n"))
    }
}

impl std::error::Error for ValidationError {}

pub type Result<T> = std::result::Result<T, ValidationError>;

pub(crate) fn normalize(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

pub(crate) fn safe_project_path(root: &Path, value: &str, must_exist: bool) -> Result<PathBuf> {
    let candidate = normalize(&root.join(value));
    if candidate.strip_prefix(normalize(root)).is_err() {
        return Err(ValidationError(vec![format!(
            "Path escapes project root: {value}"
        )]));
    }
    if must_exist && !candidate.is_file() {
        return Err(ValidationError(vec![format!(
            "Referenced file does not exist: {value}"
        )]));
    }
    Ok(candidate)
}

pub(crate) fn load_yaml(text: &str) -> std::result::Result<Value, String> {
    serde_norway::from_str(text).map_err(|error| error.to_string())
}

pub(crate) fn text(value: Option<&Value>) -> &str {
    value.and_then(Value::as_str).unwrap_or_default()
}

pub(crate) fn quoted(value: &str) -> String {
    format!("{value:?}")
}

pub(crate) fn show(value: &Value) -> String {
    serde_json::to_string(value).unwrap_or_default()
}

pub fn read_spec<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T> {
    let unreadable = |error: &dyn fmt::Display| {
        ValidationError::one(format!("Cannot read {}: {error}", path.display()))
    };
    let text = std::fs::read_to_string(path).map_err(|error| unreadable(&error))?;
    parse_yaml(&text).map_err(|error| unreadable(&error))
}

pub fn parse_yaml<T: serde::de::DeserializeOwned>(text: &str) -> anyhow::Result<T> {
    let value: serde_norway::Value = serde_norway::from_str(text)?;
    Ok(serde_path_to_error::deserialize(value)?)
}

pub const ROSTER_CLAMP_LIMIT: usize = 54;
pub const ROSTER_CLAMP_HEAD: usize = 47;
pub const ROSTER_MIN_NAMES: usize = 3;
pub const ROSTER_MAX_NAME_WORDS: usize = 6;

pub fn is_name_roster(text: &str) -> bool {
    let names: Vec<&str> = text.split('\u{2022}').map(str::trim).collect();
    names.len() >= ROSTER_MIN_NAMES
        && names.iter().all(|name| {
            !name.is_empty()
                && name
                    .split(char::is_whitespace)
                    .filter(|word| !word.is_empty())
                    .count()
                    <= ROSTER_MAX_NAME_WORDS
        })
}

pub fn clamp_roster(author: &str) -> String {
    if author.chars().count() <= ROSTER_CLAMP_LIMIT {
        return author.to_string();
    }
    let head: String = author.chars().take(ROSTER_CLAMP_HEAD).collect();
    let kept = match head.rfind(", ") {
        Some(cut) if cut > 0 => head[..cut].to_string(),
        _ => head,
    };
    format!("{kept} et al.")
}

pub fn ui(language: &str, key: &str) -> String {
    const ENGLISH: [(&str, &str); 20] = [
        ("issue", "Issue"),
        ("contents", "Contents"),
        ("sources", "Sources"),
        ("editorial", "Editorial"),
        ("feature", "Feature"),
        ("figure", "Figure"),
        ("end", "End"),
        ("by", "By"),
        ("original_argument", "An original argument"),
        ("article", "ARTICLE"),
        ("in_a_nutshell", "IN A NUTSHELL"),
        ("original_editorial", "ORIGINAL EDITORIAL"),
        ("source_introduction", "THE SOURCE"),
        ("source_record", "SOURCE RECORD"),
        ("production_note", "PRODUCTION NOTE"),
        ("glossary", "GLOSSARY"),
        ("try_it", "TRY IT"),
        ("cheat_sheet", "CHEAT SHEET"),
        ("key_ideas", "KEY IDEAS"),
        ("verbatim", "VERBATIM"),
    ];
    const SPANISH: [(&str, &str); 20] = [
        ("issue", "Número"),
        ("contents", "Índice"),
        ("sources", "Fuentes"),
        ("editorial", "Editorial"),
        ("feature", "Artículo"),
        ("figure", "Figura"),
        ("end", "Fin"),
        ("by", "Por"),
        ("original_argument", "Un argumento original"),
        ("article", "ARTÍCULO"),
        ("in_a_nutshell", "EN POCAS PALABRAS"),
        ("original_editorial", "EDITORIAL ORIGINAL"),
        ("source_introduction", "LA FUENTE"),
        ("source_record", "REGISTRO DE FUENTE"),
        ("production_note", "NOTA DE PRODUCCIÓN"),
        ("glossary", "GLOSARIO"),
        ("try_it", "PRUÉBALO"),
        ("cheat_sheet", "HOJA DE REFERENCIA"),
        ("key_ideas", "IDEAS CLAVE"),
        ("verbatim", "TEXTUAL"),
    ];
    let table = if language == "es" { SPANISH } else { ENGLISH };
    table.iter().find(|(name, _)| *name == key).map_or_else(
        || key.replace(['_', '-'], " ").to_uppercase(),
        |(_, value)| (*value).to_string(),
    )
}

pub fn anchor_key(value: &str) -> String {
    value.trim().to_lowercase()
}

pub fn is_reference_heading(text: &str) -> bool {
    matches!(anchor_key(text).as_str(), "references" | "referencias")
}

pub fn scalar_label(metadata: &Mapping) -> Result<()> {
    match metadata.get("label") {
        Some(value) if !matches!(value, Value::Null | Value::String(_)) => {
            Err(ValidationError::one(format!(
                "Frontmatter label must be text, not {}",
                show(value)
            )))
        }
        _ => Ok(()),
    }
}

pub fn content_label(language: &str, metadata: &Mapping, content_mode: &str) -> String {
    let declared = text(metadata.get("label")).trim();
    if declared.is_empty() {
        ui(language, content_mode)
    } else {
        declared.to_string()
    }
}
