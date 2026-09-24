mod engine;
mod json;

use anyhow::{anyhow, bail, Result};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::OnceLock;

pub type Span = (String, String);

struct Tables {
    aliases: Vec<String>,
    names: HashMap<String, String>,
    mimetypes: HashMap<String, String>,
    lexers: HashMap<String, engine::Lexer>,
    classes: HashMap<String, String>,
}

fn tables() -> Result<&'static Tables> {
    static TABLES: OnceLock<std::result::Result<Tables, String>> = OnceLock::new();
    TABLES
        .get_or_init(|| load(include_str!("tables.json")).map_err(|e| format!("{e:#}")))
        .as_ref()
        .map_err(|e| anyhow!("highlight tables: {e}"))
}

fn load(raw: &str) -> Result<Tables> {
    let data: Value = serde_json::from_str(raw)?;
    let strings = |key: &str| -> HashMap<String, String> {
        data[key]
            .as_object()
            .into_iter()
            .flatten()
            .map(|(k, v)| (k.clone(), v.as_str().unwrap_or_default().to_owned()))
            .collect()
    };
    let lexers = data["lexers"]
        .as_object()
        .ok_or_else(|| anyhow!("no lexers"))?
        .iter()
        .map(|(name, table)| Ok((name.clone(), engine::Lexer::new(table)?)))
        .collect::<Result<_>>()?;
    Ok(Tables {
        aliases: serde_json::from_value(data["aliases"].clone())?,
        names: strings("names"),
        mimetypes: strings("mimetypes"),
        lexers,
        classes: strings("classes"),
    })
}

pub fn spans(code: &str, language: &str) -> Result<Option<Vec<Span>>> {
    let tables = tables()?;
    let alias = language.to_lowercase();
    if language.is_empty() || tables.aliases.binary_search(&alias).is_err() {
        return Ok(None);
    }
    let Some(name) = tables.names.get(&alias) else {
        bail!("pygments highlights {language:?} with a lexer mag does not implement");
    };
    let text = code
        .strip_prefix('\u{feff}')
        .unwrap_or(code)
        .replace("\r\n", "\n")
        .replace('\r', "\n");
    Ok(Some(merge(lex(tables, name, &text)?)))
}

fn lex(tables: &Tables, name: &str, text: &str) -> Result<Vec<(String, String)>> {
    Ok(match name {
        "json" => json::tokens(text, &tables.classes),
        "text" => vec![(String::new(), text.to_owned())],
        lexer => tables.lexers[lexer].tokens(text)?,
    })
}

fn by_mime(mimetype: &str, text: &str) -> Result<Option<Vec<(String, String)>>> {
    let tables = tables()?;
    match tables.mimetypes.get(mimetype).map(String::as_str) {
        None => Ok(None),
        Some("") => bail!("pygments highlights {mimetype:?} with a lexer mag does not implement"),
        Some(name) => lex(tables, name, text).map(Some),
    }
}

fn merge(tokens: Vec<(String, String)>) -> Vec<Span> {
    let mut out: Vec<Span> = Vec::new();
    for (class, text) in tokens.into_iter().filter(|(_, t)| !t.is_empty()) {
        match out.last_mut() {
            Some(last) if last.1 == class => last.0.push_str(&text),
            _ => out.push((text, class)),
        }
    }
    out
}

pub fn html(code: &str, language: &str) -> Result<String> {
    let Some(spans) = spans(code, language)? else {
        return Ok(escape(code));
    };
    let mut out = String::new();
    for (index, line) in lines(&spans).iter().enumerate() {
        if index > 0 {
            out.push('\n');
        }
        for (text, class) in line {
            match class.is_empty() {
                true => out.push_str(&escape(text)),
                false => out.push_str(&format!("<span class=\"{class}\">{}</span>", escape(text))),
            }
        }
    }
    Ok(out.trim_end_matches('\n').to_owned())
}

fn lines(spans: &[Span]) -> Vec<Vec<(&str, &str)>> {
    let mut lines = vec![Vec::new()];
    for (text, class) in spans {
        for (index, part) in text.split('\n').enumerate() {
            if index > 0 {
                lines.push(Vec::new());
            }
            if !part.is_empty() {
                lines.last_mut().unwrap().push((part, class.as_str()));
            }
        }
    }
    lines
}

fn escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}
