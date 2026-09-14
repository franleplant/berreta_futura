#[path = "../src/model/doc.rs"]
#[allow(dead_code)]
mod doc;
#[path = "../src/model/manifest.rs"]
#[allow(dead_code)]
mod manifest;
#[path = "../src/model/records.rs"]
#[allow(dead_code)]
mod records;

use manifest::{load_edition, load_translation, Edition, LoadOptions, Records};
use records::{SourceRecord, ValidationError};
use serde_json::{json, Map, Value as Json};
use serde_yaml::Value;
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/model_manifest_fixtures")
}

fn committed(name: &str) -> Json {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join(name);
    serde_json::from_str(&std::fs::read_to_string(&path).expect("the oracle dump is readable"))
        .expect("the oracle dump is JSON")
}

fn yaml_to_json(value: &Value) -> Json {
    match value {
        Value::Null => Json::Null,
        Value::Bool(flag) => Json::Bool(*flag),
        Value::Number(number) => number
            .as_i64()
            .map(Json::from)
            .or_else(|| number.as_f64().map(Json::from))
            .unwrap_or(Json::Null),
        Value::String(text) => Json::String(text.clone()),
        Value::Sequence(items) => Json::Array(items.iter().map(yaml_to_json).collect()),
        Value::Mapping(mapping) => Json::Object(
            mapping
                .iter()
                .map(|(key, item)| {
                    let key = match key {
                        Value::String(text) => text.clone(),
                        other => serde_yaml::to_string(other)
                            .unwrap_or_default()
                            .trim()
                            .to_string(),
                    };
                    (key, yaml_to_json(item))
                })
                .collect::<Map<String, Json>>(),
        ),
        Value::Tagged(tagged) => yaml_to_json(&tagged.value),
    }
}

fn relative(path: &Path, root: &Path) -> String {
    match path.strip_prefix(root) {
        Ok(rest) => rest.to_string_lossy().replace('\\', "/"),
        Err(_) => path
            .to_string_lossy()
            .replace(&root.to_string_lossy().to_string(), "<ROOT>"),
    }
}

fn dump(edition: &Edition, root: &Path) -> Json {
    json!({
        "id": edition.id,
        "publication_name": edition.publication_name,
        "issue_number": edition.issue_number,
        "title": edition.title,
        "publication_date": edition.publication_date,
        "language": edition.language,
        "locale": edition.locale,
        "editorial": edition.editorial.as_ref().map(|editorial| json!({
            "path": relative(&editorial.path, root),
            "title": editorial.title,
            "byline": editorial.byline,
            "label": editorial.label,
        })),
        "articles": edition.articles.iter().map(|article| json!({
            "id": article.id,
            "title": article.title,
            "short_title": article.short_title,
            "display_emphasis": article.display_emphasis,
            "opener_variant": article.opener_variant,
            "author": article.author,
            "author_note": article.author_note,
            "source_ids": article.source_ids,
            "manuscript": relative(&article.manuscript, root),
            "content_mode": article.content_mode,
            "minimum_reader_pages": article.minimum_reader_pages,
            "tail_art": article.tail_art.as_ref().map(|path| relative(path, root)),
            "source_url": article.source_url,
            "opener_art": article.opener_art.as_ref().map(|art| json!({
                "path": relative(&art.path, root),
                "alt_text": art.alt_text,
                "credit": art.credit,
            })),
            "key_ideas": article.key_ideas,
            "dateline": article.dateline,
            "figures": article.figures.iter().map(|figure| json!({
                "id": figure.id,
                "source_id": figure.source_id,
                "path": figure.path.to_string_lossy().replace('\\', "/"),
                "caption": figure.caption,
                "credit": figure.credit,
                "alt_text": figure.alt_text,
                "anchor": figure.anchor,
                "layout": figure.layout,
            })).collect::<Vec<Json>>(),
            "extracts": article.extracts.iter().map(|extract| json!({
                "id": extract.id,
                "source_id": extract.source_id,
                "style": extract.style,
                "caption": extract.caption,
                "anchor": extract.anchor,
            })).collect::<Vec<Json>>(),
        })).collect::<Vec<Json>>(),
        "sections": edition.sections.iter().map(|section| json!({
            "kind": section.kind,
            "title": section.title,
            "path": relative(&section.path, root),
        })).collect::<Vec<Json>>(),
        "cover": yaml_to_json(&Value::Mapping(edition.cover.clone())),
        "cover_art": edition.cover_art.as_ref().map(|path| relative(path, root)),
        "closing_plates": edition.closing_plates.iter().map(|plate| json!({
            "title": plate.title,
            "art_path": relative(&plate.art_path, root),
        })).collect::<Vec<Json>>(),
        "raw": yaml_to_json(&edition.raw),
    })
}

fn case_records(case: &Value) -> Records {
    let mut records = Records::new();
    let Some(Value::Mapping(declared)) = case.get("records") else {
        return records;
    };
    for (key, fields) in declared {
        let id = key.as_str().expect("a record id is a string").to_string();
        records.insert(
            id.clone(),
            SourceRecord {
                id,
                url: fields
                    .get("url")
                    .and_then(|value| value.as_str())
                    .unwrap_or_default()
                    .to_string(),
                title: fields
                    .get("title")
                    .and_then(|value| value.as_str())
                    .unwrap_or_default()
                    .to_string(),
                captured_at: "2026-01-01T00:00:00Z".to_string(),
                author: None,
                published_at: fields
                    .get("published_at")
                    .and_then(|value| value.as_str())
                    .map(str::to_string),
                tags: Some(Vec::new()),
                synopsis: Some(String::new()),
                notes: Some(String::new()),
            },
        );
    }
    records
}

fn flag(case: &Value, key: &str) -> bool {
    case.get(key)
        .and_then(|value| value.as_bool())
        .unwrap_or(false)
}

fn build_root(case: &Value, name: &str) -> PathBuf {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("target/tmp/model_manifest")
        .join(name);
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(&root).expect("the case root is creatable");
    if let Some(Value::Mapping(files)) = case.get("files") {
        for (path, content) in files {
            let target = root.join(path.as_str().expect("a fixture path is a string"));
            std::fs::create_dir_all(target.parent().expect("the file sits in a directory"))
                .expect("the fixture directory is creatable");
            std::fs::write(
                &target,
                content.as_str().expect("fixture content is a string"),
            )
            .expect("the fixture file is writable");
        }
    }
    root.canonicalize().expect("the case root resolves")
}

fn run_case(case: &Value, name: &str) -> Json {
    let root = build_root(case, name);
    let known: BTreeSet<String> = match case.get("known_sources") {
        Some(Value::Sequence(items)) => items
            .iter()
            .filter_map(|value| value.as_str().map(str::to_string))
            .collect(),
        _ => BTreeSet::new(),
    };
    let records = case_records(case);
    let options = LoadOptions {
        publication_name: "Magazine",
        source_records: Some(&records),
        allow_missing_art: flag(case, "allow_missing_art"),
        allow_unanchored_figures: flag(case, "allow_unanchored_figures"),
    };
    let edition_id = case
        .get("edition_id")
        .and_then(|value| value.as_str())
        .expect("a case names its edition");
    let loaded = load_edition(&root, edition_id, &known, &options).and_then(|edition| {
        match case.get("translation").and_then(|value| value.as_str()) {
            Some(language) => load_translation(&root, &edition, language),
            None => Ok(edition),
        }
    });
    match loaded {
        Ok(edition) => json!({ "ok": dump(&edition, &root) }),
        Err(ValidationError(errors)) => json!({
            "errors": errors
                .iter()
                .map(|line| Json::String(line.replace(&root.to_string_lossy().to_string(), "<ROOT>")))
                .collect::<Vec<Json>>()
        }),
    }
}

fn cases() -> Vec<Value> {
    let text =
        std::fs::read_to_string(fixtures().join("cases.yaml")).expect("the cases are readable");
    serde_yaml::from_str(&text).expect("the cases are YAML")
}

const PARSER_DIAGNOSTIC_CASES: [&str; 2] =
    ["editorial_frontmatter_unparseable", "manifest_unparseable"];

fn shared_prefix(left: &str, right: &str) -> String {
    let take = left
        .char_indices()
        .zip(right.chars())
        .take_while(|((_, a), b)| a == b)
        .count();
    left.chars().take(take).collect()
}

const PYTHON_CRASHES: [&str; 3] = [
    "closing_plates_not_a_list",
    "cover_not_a_mapping",
    "opener_art_not_a_mapping",
];

#[test]
fn cases_match_the_python_loader() {
    let expected = committed("model_manifest_cases_expected.json");
    let expected = expected.as_object().expect("the oracle is an object");
    let mut compared = 0;
    let mut mismatches: Vec<String> = Vec::new();
    for case in cases() {
        let name = case
            .get("name")
            .and_then(|value| value.as_str())
            .expect("a case is named")
            .to_string();
        let want = expected
            .get(&name)
            .unwrap_or_else(|| panic!("the oracle covers {name}"));
        if PYTHON_CRASHES.contains(&name.as_str()) {
            continue;
        }
        let got = run_case(&case, &name);
        if PARSER_DIAGNOSTIC_CASES.contains(&name.as_str()) {
            compare_parser_diagnostics(&got, want, &name, &mut mismatches);
            compared += 1;
            continue;
        }
        if &got != want {
            mismatches.push(format!("{name}\n  rust: {got}\n  python: {want}"));
        }
        compared += 1;
    }
    assert!(
        mismatches.is_empty(),
        "{} cases diverge:\n{}",
        mismatches.len(),
        mismatches.join("\n")
    );
    assert_eq!(compared + PYTHON_CRASHES.len(), expected.len());
}

#[test]
fn python_crashes_are_reported_as_validation_errors() {
    let expected = committed("model_manifest_cases_expected.json");
    for case in cases() {
        let name = case
            .get("name")
            .and_then(|value| value.as_str())
            .expect("a case is named")
            .to_string();
        if !PYTHON_CRASHES.contains(&name.as_str()) {
            continue;
        }
        let crash = expected[&name]["crash"]
            .as_str()
            .unwrap_or_else(|| panic!("{name} is recorded as a Python crash"));
        assert!(
            crash.starts_with("AttributeError") || crash.starts_with("TypeError"),
            "{name} records the unguarded-shape crash, got {crash}"
        );
        let got = run_case(&case, &name);
        let errors = got["errors"]
            .as_array()
            .unwrap_or_else(|| panic!("{name} reports validation errors rather than panicking"));
        assert_eq!(
            errors,
            recovered_diagnoses(&name),
            "{name} surfaces the diagnoses the Python crash discards"
        );
    }
}

#[test]
fn the_oracle_is_not_vacuous() {
    let mut expected = committed("model_manifest_cases_expected.json");
    expected["valid_minimum"]["ok"]["articles"][0]["title"] = json!("Altered");
    let case = cases()
        .into_iter()
        .find(|case| case.get("name").and_then(|value| value.as_str()) == Some("valid_minimum"))
        .expect("the valid case exists");
    let got = run_case(&case, "valid_minimum_negative");
    assert_ne!(got, expected["valid_minimum"]);
}

#[test]
fn edition_010_matches_the_python_loader() {
    let (Ok(root), Ok(oracle)) = (
        std::env::var("MAG_MANIFEST_ROOT"),
        std::env::var("MAG_MANIFEST_ORACLE"),
    ) else {
        assert!(
            std::env::var("MAG_MANIFEST_ROOT").is_err()
                && std::env::var("MAG_MANIFEST_ORACLE").is_err(),
            "set both MAG_MANIFEST_ROOT and MAG_MANIFEST_ORACLE or neither"
        );
        return;
    };
    let root = PathBuf::from(root)
        .canonicalize()
        .expect("the staged root exists");
    let expected: Json =
        serde_json::from_str(&std::fs::read_to_string(&oracle).expect("the oracle is readable"))
            .expect("the oracle is JSON");
    let records: Records = records::load_records(&root.join("library").join("sources"))
        .expect("the staged records load")
        .into_iter()
        .map(|record| (record.id.clone(), record))
        .collect();
    let known: BTreeSet<String> = records.keys().cloned().collect();
    let edition = load_edition(
        &root,
        "010",
        &known,
        &LoadOptions {
            publication_name: "Magazine",
            source_records: Some(&records),
            ..LoadOptions::default()
        },
    )
    .expect("edition 010 loads from the staged root");
    let caps: Map<String, Json> = edition
        .articles
        .iter()
        .map(|article| {
            let cap = if article.content_mode == "verbatim" {
                10
            } else {
                7
            };
            (article.id.clone(), json!(cap))
        })
        .collect();
    let modes: Map<String, Json> = edition
        .articles
        .iter()
        .map(|article| (article.id.clone(), json!(article.content_mode)))
        .collect();
    let format = edition.raw.get("format");
    let maximum_article_pages = format
        .and_then(|format| format.get("max_article_pages"))
        .and_then(|value| value.as_i64())
        .unwrap_or(7);
    let maximum_editorial_pages = format
        .and_then(|format| format.get("max_editorial_pages"))
        .and_then(|value| value.as_i64())
        .unwrap_or(2);
    let got = json!({
        "edition": yaml_to_json(&edition.raw),
        "layout": {
            "maximum_article_pages": maximum_article_pages,
            "article_page_caps": caps,
            "article_content_modes": modes,
            "maximum_editorial_pages": maximum_editorial_pages,
        },
    });
    assert_eq!(got, expected, "edition 010 diverges from the Python loader");
}

fn compare_parser_diagnostics(got: &Json, want: &Json, name: &str, mismatches: &mut Vec<String>) {
    let ours = got["errors"].as_array().expect("rust reports errors");
    let theirs = want["errors"].as_array().expect("python reports errors");
    if ours.len() != theirs.len() {
        mismatches.push(format!(
            "{name} error count {} vs {}",
            ours.len(),
            theirs.len()
        ));
        return;
    }
    for (ours, theirs) in ours.iter().zip(theirs) {
        let ours = ours.as_str().expect("an error is text");
        let theirs = theirs.as_str().expect("an error is text");
        if ours == theirs {
            continue;
        }
        let prefix = shared_prefix(ours, theirs);
        if !prefix.ends_with(": ") || !prefix.contains("<ROOT>") {
            mismatches.push(format!(
                "{name} diverges before the parser diagnostic: {prefix:?}"
            ));
        }
    }
}

fn recovered_diagnoses(name: &str) -> &'static Vec<Json> {
    use std::sync::OnceLock;
    static TABLE: OnceLock<Vec<(&str, Vec<Json>)>> = OnceLock::new();
    let table = TABLE.get_or_init(|| {
        vec![
            (
                "cover_not_a_mapping",
                vec![
                    json!("Edition requires either sections or articles"),
                    json!("Edition cover must be a mapping"),
                    json!("Edition tail_art_fit must be cover or contain"),
                ],
            ),
            (
                "closing_plates_not_a_list",
                vec![
                    json!("Edition requires either sections or articles"),
                    json!("Edition closing_plates must be a list"),
                ],
            ),
            (
                "opener_art_not_a_mapping",
                vec![json!(
                    "Article a1 requires a non-empty opener_art mapping for format.article_opener illustrated_paper_spots_v1"
                )],
            ),
        ]
    });
    table
        .iter()
        .find(|(key, _)| *key == name)
        .map(|(_, value)| value)
        .unwrap_or_else(|| panic!("{name} has recorded diagnoses"))
}
