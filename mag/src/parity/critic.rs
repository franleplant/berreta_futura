use anyhow::{Context, Result};
use regex::Regex;
use serde::Serialize;
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use super::streams::Face;
use crate::critic::inspect::standalone_punctuation_lines;
use crate::critic::rules::read_leg;
use crate::critic::text::body_text_lines;
use crate::model::shared::py_strip;

const REPORT: &str = "en/render-critic.json";
const PDFS: [&str; 4] = [
    "reader.pdf",
    "booklet-a4.pdf",
    "booklet-a4-interior.pdf",
    "booklet-a4-cover.pdf",
];

#[derive(Serialize)]
#[serde(untagged)]
pub enum CriticClause {
    NotEvaluated {
        status: String,
        reason: String,
    },
    Evaluated {
        status: String,
        result_a: String,
        result_b: String,
        issues: usize,
        leaves_compared: usize,
        leaves_excluded: usize,
        leaves_differing: Vec<String>,
        text_pages_compared: usize,
        text_fields_differing: Vec<String>,
        text_characters_differing: Vec<String>,
    },
}

impl CriticClause {
    pub fn status(&self) -> &str {
        match self {
            CriticClause::NotEvaluated { status, .. } | CriticClause::Evaluated { status, .. } => {
                status
            }
        }
    }
}

fn flatten(value: &Value, path: String, out: &mut BTreeMap<String, Value>) {
    match value {
        Value::Object(map) if !map.is_empty() => {
            for (key, child) in map {
                flatten(child, format!("{path}.{key}"), out);
            }
        }
        Value::Array(items) if !items.is_empty() => {
            for (index, child) in items.iter().enumerate() {
                flatten(child, format!("{path}[{index}]"), out);
            }
        }
        leaf => {
            out.insert(path, leaf.clone());
        }
    }
}

fn leaves(dir: &Path) -> Result<BTreeMap<String, Value>> {
    let path = dir.join(REPORT);
    let raw = fs::read_to_string(&path).with_context(|| format!("reading {}", path.display()))?;
    let doc: Value =
        serde_json::from_str(&raw).with_context(|| format!("parsing {}", path.display()))?;
    let mut out = BTreeMap::new();
    flatten(&doc, String::new(), &mut out);
    Ok(out)
}

fn text_fields(text: &str) -> (usize, Vec<String>, bool) {
    (
        body_text_lines(text),
        standalone_punctuation_lines(text),
        py_strip(text).is_empty(),
    )
}

fn compare_text(
    dir_a: &Path,
    dir_b: &Path,
    fonts: &BTreeMap<String, Face>,
) -> Result<(usize, Vec<String>, Vec<String>)> {
    let (mut compared, mut fields, mut characters) = (0, vec![], vec![]);
    for name in PDFS {
        let a = read_leg(&dir_a.join("en").join(name), fonts)?.raw;
        let b = read_leg(&dir_b.join("en").join(name), fonts)?.raw;
        if a.len() != b.len() {
            fields.push(format!("{name}: {} pages vs {}", a.len(), b.len()));
            continue;
        }
        for (index, (ta, tb)) in a.iter().zip(&b).enumerate() {
            compared += 1;
            if text_fields(ta) != text_fields(tb) {
                fields.push(format!(
                    "{name} p{}: {:?} vs {:?}",
                    index + 1,
                    text_fields(ta),
                    text_fields(tb)
                ));
            }
            let count = |t: &str| py_strip(t).chars().count();
            if count(ta) != count(tb) {
                characters.push(format!(
                    "{name} p{}: {} vs {}",
                    index + 1,
                    count(ta),
                    count(tb)
                ));
            }
        }
    }
    Ok((compared, fields, characters))
}

fn diff_leaves(
    a: &BTreeMap<String, Value>,
    b: &BTreeMap<String, Value>,
    excluded: &[String],
) -> Result<(usize, usize, Vec<String>)> {
    let index = Regex::new(r"\[\d+\]")?;
    let skip = |path: &str| {
        let general = index.replace_all(path, "[*]");
        excluded.iter().any(|e| {
            general
                .strip_prefix(e.as_str())
                .is_some_and(|rest| rest.is_empty() || rest.starts_with('['))
        })
    };
    let keys: BTreeSet<&String> = a.keys().chain(b.keys()).collect();
    let skipped = keys.iter().filter(|k| skip(k)).count();
    let differing = keys
        .iter()
        .filter(|k| !skip(k) && a.get(**k) != b.get(**k))
        .map(|k| format!("{k}: {:?} vs {:?}", a.get(*k), b.get(*k)))
        .collect();
    Ok((keys.len() - skipped, skipped, differing))
}

pub fn compare(
    dir_a: &Path,
    dir_b: &Path,
    excluded: &[String],
    fonts: &BTreeMap<String, Face>,
) -> Result<CriticClause> {
    let (has_a, has_b) = (dir_a.join(REPORT).exists(), dir_b.join(REPORT).exists());
    if !has_a && !has_b {
        return Ok(CriticClause::NotEvaluated {
            status: "not_evaluated".into(),
            reason: format!("neither leg carries {REPORT}"),
        });
    }
    let read = |dir: &Path, has: bool| {
        if has {
            leaves(dir)
        } else {
            Ok(BTreeMap::new())
        }
    };
    let (a, b) = (read(dir_a, has_a)?, read(dir_b, has_b)?);
    let (leaves_compared, leaves_excluded, differing) = diff_leaves(&a, &b, excluded)?;
    let leaves_differing: Vec<String> = [(has_a, "a"), (has_b, "b")]
        .into_iter()
        .filter(|(has, _)| !has)
        .map(|(_, leg)| format!("{REPORT} missing on leg {leg}"))
        .chain(differing)
        .collect();
    let (text_pages_compared, text_fields_differing, text_characters_differing) =
        compare_text(dir_a, dir_b, fonts)?;
    let result = |m: &BTreeMap<String, Value>| {
        m.get(".result")
            .and_then(Value::as_str)
            .unwrap_or("missing")
            .to_string()
    };
    let pass = leaves_differing.is_empty()
        && text_fields_differing.is_empty()
        && text_characters_differing.is_empty();
    Ok(CriticClause::Evaluated {
        status: if pass { "pass" } else { "fail" }.into(),
        result_a: result(&a),
        result_b: result(&b),
        issues: a
            .keys()
            .filter(|k| k.ends_with("].code") && k.starts_with(".issues["))
            .count(),
        leaves_compared,
        leaves_excluded,
        leaves_differing,
        text_pages_compared,
        text_fields_differing,
        text_characters_differing,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn flat(doc: &Value) -> BTreeMap<String, Value> {
        let mut out = BTreeMap::new();
        flatten(doc, String::new(), &mut out);
        out
    }

    fn report(ink: f64, bbox: [u32; 2], page: u32, extra: bool) -> Value {
        let mut doc = json!({
            "result": "pass",
            "issues": [{"code": "whitespace-void", "page": page}],
            "pages": [{"ink_ratio": 0.5, "ink_bbox": [0, 0]}, {"ink_ratio": ink, "ink_bbox": bbox, "sparse": false}],
        });
        if extra {
            doc["pages"][1]["ink_ratio_note"] = json!("x");
        }
        doc
    }

    fn excluded() -> Vec<String> {
        vec![".pages[*].ink_ratio".into(), ".pages[*].ink_bbox".into()]
    }

    #[test]
    fn excluded_leaves_skip_every_index_and_every_array_element_beneath_them() {
        let (a, b) = (
            flat(&report(0.1, [1, 2], 17, false)),
            flat(&report(0.2, [3, 4], 17, false)),
        );
        let (compared, skipped, differing) = diff_leaves(&a, &b, &excluded()).expect("diff");
        assert_eq!((compared, skipped), (4, 6));
        assert!(differing.is_empty(), "{differing:?}");
    }

    #[test]
    fn a_decision_leaf_or_a_one_sided_leaf_differs_and_a_prefix_is_not_a_match() {
        let (a, b) = (
            flat(&report(0.1, [1, 2], 17, false)),
            flat(&report(0.1, [1, 2], 18, true)),
        );
        let (_, _, differing) = diff_leaves(&a, &b, &excluded()).expect("diff");
        assert_eq!(differing.len(), 2, "{differing:?}");
        assert!(differing[0].starts_with(".issues[0].page:"));
        assert!(differing[1].starts_with(".pages[1].ink_ratio_note:"));
    }
}
