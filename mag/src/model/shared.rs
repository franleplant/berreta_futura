use regex::Regex;
use serde_yaml::Value;
use std::fmt;
use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

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

pub(crate) fn py_repr(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::new();
    out.push(quote);
    for character in text.chars() {
        match character {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            other if other == quote => {
                out.push('\\');
                out.push(other);
            }
            other if printable(other) => out.push(other),
            other => out.push_str(&escape(other)),
        }
    }
    out.push(quote);
    out
}

fn printable(character: char) -> bool {
    character == ' ' || !nonprintable().is_match(character.encode_utf8(&mut [0; 4]))
}

fn nonprintable() -> &'static Regex {
    static PATTERN: OnceLock<Regex> = OnceLock::new();
    PATTERN.get_or_init(|| Regex::new(r"^[\p{C}\p{Z}]$").expect("the pattern compiles"))
}

fn escape(character: char) -> String {
    let point = character as u32;
    if point < 0x100 {
        format!("\\x{point:02x}")
    } else if point < 0x10000 {
        format!("\\u{point:04x}")
    } else {
        format!("\\U{point:08x}")
    }
}

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

pub(crate) fn load_structured(path: &Path) -> Result<Value> {
    let text = std::fs::read_to_string(path).map_err(|error| {
        ValidationError(vec![format!("Cannot read {}: {error}", path.display())])
    })?;
    let data: Value = if path.extension().is_some_and(|suffix| suffix == "json") {
        serde_json::from_str(&text).map_err(|error| {
            ValidationError(vec![format!("Cannot read {}: {error}", path.display())])
        })?
    } else {
        serde_yaml::from_str(&text).map_err(|error| {
            ValidationError(vec![format!("Cannot read {}: {error}", path.display())])
        })?
    };
    if !matches!(data, Value::Mapping(_)) {
        return Err(ValidationError(vec![format!(
            "{} must contain a mapping",
            path.display()
        )]));
    }
    Ok(data)
}
