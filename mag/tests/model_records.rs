#[path = "../src/model/records.rs"]
mod records;

use records::{
    canonicalize_url, load_records, localize_extracts, localize_figures, resolve_extracts,
    resolve_figures, source_id, Extract, ExtractRequest, Figure, FigureRequest, NewRecord,
    SourceRecord, ValidationError,
};
use serde_json::{json, Map, Value as Json};
use serde_yaml::Value;
use std::path::{Path, PathBuf};

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/model_records_fixtures")
}

fn committed(name: &str) -> Json {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join(name);
    serde_json::from_str(&std::fs::read_to_string(&path).expect("the oracle dump is readable"))
        .expect("the oracle dump is JSON")
}

fn outcome<T>(result: records::Result<T>, encode: impl Fn(T) -> Json, root: &str) -> Json {
    match result {
        Ok(value) => json!({ "ok": encode(value) }),
        Err(ValidationError(errors)) => json!({
            "errors": errors
                .iter()
                .map(|line| Json::String(line.replace(root, "<ROOT>")))
                .collect::<Vec<Json>>()
        }),
    }
}

fn figure_json(figure: &Figure, root: &Path) -> Json {
    json!({
        "id": figure.id,
        "source_id": figure.source_id,
        "path": figure
            .path
            .strip_prefix(root)
            .expect("the figure sits under the root")
            .to_string_lossy()
            .replace('\\', "/"),
        "caption": figure.caption,
        "credit": figure.credit,
        "alt_text": figure.alt_text,
        "anchor": figure.anchor,
        "layout": figure.layout,
    })
}

fn extract_json(extract: &Extract) -> Json {
    json!({
        "id": extract.id,
        "source_id": extract.source_id,
        "text": extract.text,
        "style": extract.style,
        "caption": extract.caption,
        "anchor": extract.anchor,
    })
}

fn case_field<'a>(case: &'a serde_yaml::Mapping, name: &str) -> Option<&'a Value> {
    case.get(Value::String(name.to_string()))
}

fn case_text(case: &serde_yaml::Mapping, name: &str) -> String {
    match case_field(case, name) {
        Some(Value::String(text)) => text.clone(),
        _ => String::new(),
    }
}

fn case_ids(case: &serde_yaml::Mapping) -> Vec<String> {
    match case_field(case, "source_ids") {
        Some(Value::Sequence(items)) => items
            .iter()
            .filter_map(|item| item.as_str().map(str::to_string))
            .collect(),
        _ => Vec::new(),
    }
}

fn seed_figures(case: &serde_yaml::Mapping, root: &Path) -> Vec<Figure> {
    let Some(Value::Sequence(items)) = case_field(case, "base") else {
        return Vec::new();
    };
    items
        .iter()
        .filter_map(|item| item.as_mapping())
        .map(|row| {
            let text = |name: &str| {
                row.get(Value::String(name.to_string()))
                    .and_then(|value| value.as_str())
                    .unwrap_or_default()
                    .to_string()
            };
            Figure {
                id: text("id"),
                source_id: text("source_id"),
                path: root
                    .join("library")
                    .join("sources")
                    .join(text("source_id"))
                    .join(text("path")),
                caption: text("caption"),
                credit: text("credit"),
                alt_text: text("alt_text"),
                anchor: text("anchor"),
                layout: text("layout"),
            }
        })
        .collect()
}

fn seed_extracts(case: &serde_yaml::Mapping, root: &Path) -> Vec<Extract> {
    let Some(Value::Sequence(items)) = case_field(case, "base") else {
        return Vec::new();
    };
    let manuscript = root.join("manuscripts/en.md");
    let mut seeded = Vec::new();
    for item in items {
        let source_id = item
            .as_mapping()
            .and_then(|row| row.get(Value::String("source_id".into())))
            .and_then(|value| value.as_str())
            .unwrap_or_default()
            .to_string();
        let request = ExtractRequest {
            root,
            article_id: "seed",
            article_source_ids: std::slice::from_ref(&source_id),
            manuscript: &manuscript,
            allow_unanchored: true,
        };
        let rows = Value::Sequence(vec![item.clone()]);
        let resolved = resolve_extracts(&request, Some(&rows)).expect("the seed extract resolves");
        seeded.extend(resolved);
    }
    seeded
}

fn run_case(case: &serde_yaml::Mapping, root: &Path) -> Json {
    let token = root.to_string_lossy().into_owned();
    let article_id = case_text(case, "article_id");
    let source_ids = case_ids(case);
    let manuscript = root.join("manuscripts").join(case_text(case, "manuscript"));
    let translated = match case_field(case, "translated_manuscript") {
        Some(Value::String(name)) => root.join("manuscripts").join(name),
        _ => manuscript.clone(),
    };
    let language = case_text(case, "language");
    let allow_unanchored = matches!(
        case_field(case, "allow_unanchored"),
        Some(Value::Bool(true))
    );
    let rows = case_field(case, "rows");
    let owned_root = root.to_path_buf();
    match case_text(case, "kind").as_str() {
        "figures" => {
            let request = FigureRequest {
                root,
                article_id: &article_id,
                article_source_ids: &source_ids,
                manuscript: &manuscript,
                allow_unanchored,
            };
            outcome(
                resolve_figures(&request, rows),
                |figures: Vec<Figure>| {
                    Json::Array(
                        figures
                            .iter()
                            .map(|figure| figure_json(figure, &owned_root))
                            .collect(),
                    )
                },
                &token,
            )
        }
        "extracts" => {
            let request = ExtractRequest {
                root,
                article_id: &article_id,
                article_source_ids: &source_ids,
                manuscript: &manuscript,
                allow_unanchored,
            };
            outcome(
                resolve_extracts(&request, rows),
                |extracts: Vec<Extract>| Json::Array(extracts.iter().map(extract_json).collect()),
                &token,
            )
        }
        "localize_figures" => {
            let base = seed_figures(case, root);
            outcome(
                localize_figures(&base, rows, &article_id, &translated, &language),
                |figures: Vec<Figure>| {
                    Json::Array(
                        figures
                            .iter()
                            .map(|figure| figure_json(figure, &owned_root))
                            .collect(),
                    )
                },
                &token,
            )
        }
        other => {
            assert_eq!(other, "localize_extracts", "unknown case kind");
            let base = seed_extracts(case, root);
            outcome(
                localize_extracts(&base, rows, &article_id, &translated, &language),
                |extracts: Vec<Extract>| Json::Array(extracts.iter().map(extract_json).collect()),
                &token,
            )
        }
    }
}

#[test]
fn library_sources_match_the_python_dump() {
    let produced: Vec<Json> = load_records(&repository().join("library/sources"))
        .expect("the corpus loads")
        .iter()
        .map(SourceRecord::to_json)
        .collect();
    assert_eq!(
        Json::Array(produced),
        committed("model_records_expected.json"),
        "the Rust records diverged from the Python dump of library/sources"
    );
}

#[test]
fn a_changed_field_fails_the_corpus_comparison() {
    let mut produced: Vec<Json> = load_records(&repository().join("library/sources"))
        .expect("the corpus loads")
        .iter()
        .map(SourceRecord::to_json)
        .collect();
    produced[0]["title"] = json!("a title the oracle never recorded");
    assert_ne!(
        Json::Array(produced),
        committed("model_records_expected.json"),
        "the corpus comparison is vacuous"
    );
}

#[test]
fn to_dict_key_order_matches_python() {
    let records = load_records(&repository().join("library/sources")).expect("the corpus loads");
    let plain = records
        .iter()
        .find(|record| record.notes.as_deref().unwrap_or_default().is_empty())
        .expect("a record without notes exists");
    assert_eq!(
        plain.key_order(),
        vec![
            "id",
            "title",
            "author",
            "url",
            "captured_at",
            "published_at",
            "tags",
            "synopsis"
        ]
    );
}

#[test]
fn record_fixtures_match_the_python_loader() {
    let directory = fixtures().join("records");
    let mut entries: Vec<PathBuf> = std::fs::read_dir(&directory)
        .expect("the fixtures are readable")
        .map(|entry| entry.expect("the entry is readable").path())
        .filter(|path| path.extension().is_some_and(|kind| kind == "yaml"))
        .collect();
    entries.sort();
    let mut produced = Map::new();
    for path in entries {
        let name = path
            .file_stem()
            .expect("the fixture has a stem")
            .to_string_lossy()
            .to_string();
        let text = std::fs::read_to_string(&path).expect("the fixture is readable");
        let data: Value = serde_yaml::from_str(&text).expect("the fixture is YAML");
        let value = match SourceRecord::from_value(&data, Some(&text)) {
            Ok(record) => json!({ "ok": record.to_json() }),
            Err(ValidationError(errors)) => json!({ "errors": errors }),
        };
        produced.insert(name, value);
    }
    assert_eq!(
        Json::Object(produced),
        committed("model_records_records_expected.json"),
        "the Rust loader diverged from the Python loader on the record fixtures"
    );
}

#[test]
fn canonical_urls_match_python() {
    let expected = committed("model_records_urls_expected.json");
    let mut produced = Map::new();
    for key in expected.as_object().expect("the table is an object").keys() {
        let value = match canonicalize_url(key) {
            Ok(url) => json!({ "ok": url }),
            Err(ValidationError(errors)) => json!({ "errors": errors }),
        };
        produced.insert(key.clone(), value);
    }
    assert_eq!(
        Json::Object(produced),
        expected,
        "the Rust canonicalizer diverged from urllib"
    );
}

#[test]
fn port_refusal_messages_match_python() {
    let expected = committed("model_records_ports_expected.json");
    for (url, entry) in expected.as_object().expect("the table is an object") {
        let message = entry
            .get("python_value_error")
            .and_then(Json::as_str)
            .expect("every port case raises ValueError in Python");
        match canonicalize_url(url) {
            Ok(value) => panic!("{url} canonicalized to {value}, Python raised {message}"),
            Err(ValidationError(errors)) => assert_eq!(
                errors,
                vec![message.to_string()],
                "the Rust port refusal diverged from urllib for {url}"
            ),
        }
    }
}

fn create_cases<'a>(
    plain_tags: &'a [String],
    unicode_tags: &'a [String],
) -> Vec<(&'a str, NewRecord<'a>)> {
    vec![
        (
            "plain",
            NewRecord {
                url: "https://Example.com/a/?utm_source=x",
                title: Some("A Fine Title"),
                author: Some("  Writer  "),
                published_at: Some("2026-01-02"),
                captured_at: "2026-03-04T05:06:07Z",
                tags: plain_tags,
                synopsis: "  S  ",
                notes: "  N  ",
            },
        ),
        (
            "no_title",
            NewRecord {
                url: "https://example.com/b",
                title: None,
                author: None,
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: &[],
                synopsis: "",
                notes: "",
            },
        ),
        (
            "blank_author",
            NewRecord {
                url: "https://example.com/c",
                title: Some("T"),
                author: Some("   "),
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: &[],
                synopsis: "",
                notes: "",
            },
        ),
        (
            "unicode_title",
            NewRecord {
                url: "https://example.com/d",
                title: Some("Ünïcode — Tïtle!!"),
                author: None,
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: unicode_tags,
                synopsis: "",
                notes: "",
            },
        ),
        (
            "bad_url",
            NewRecord {
                url: "ftp://example.com/e",
                title: Some("T"),
                author: None,
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: &[],
                synopsis: "",
                notes: "",
            },
        ),
    ]
}

fn falsy_create_cases<'a>() -> Vec<(&'a str, NewRecord<'a>)> {
    vec![
        (
            "empty_title",
            NewRecord {
                url: "https://example.com/f",
                title: Some(""),
                author: None,
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: &[],
                synopsis: "",
                notes: "",
            },
        ),
        (
            "whitespace_title",
            NewRecord {
                url: "https://example.com/g",
                title: Some("   "),
                author: None,
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: &[],
                synopsis: "",
                notes: "",
            },
        ),
        (
            "empty_author",
            NewRecord {
                url: "https://example.com/h",
                title: Some("T"),
                author: Some(""),
                published_at: None,
                captured_at: "2026-03-04T05:06:07Z",
                tags: &[],
                synopsis: "",
                notes: "",
            },
        ),
    ]
}

#[test]
fn create_and_source_id_match_python() {
    let expected = committed("model_records_create_expected.json");
    let tags = |items: &[&str]| {
        items
            .iter()
            .map(|item| item.to_string())
            .collect::<Vec<String>>()
    };
    let plain_tags = tags(&["  Beta ", "alpha", "ALPHA", "  "]);
    let unicode_tags = tags(&["x"]);
    let long_title = "x".repeat(60);
    let mut cases = create_cases(&plain_tags, &unicode_tags);
    cases.extend(falsy_create_cases());
    let mut created = Map::new();
    for (name, request) in &cases {
        let value = match SourceRecord::create(request) {
            Ok(record) => json!({ "ok": record.to_json() }),
            Err(ValidationError(errors)) => json!({ "errors": errors }),
        };
        created.insert((*name).to_string(), value);
    }
    let mut ids = Map::new();
    for (title, url) in [
        ("A Fine Title", "https://example.com/a"),
        ("!!!", "https://example.com/b"),
        (&long_title, "https://example.com/c"),
        ("Ünïcode", "https://example.com/d"),
    ] {
        ids.insert(format!("{title}|{url}"), json!(source_id(title, url)));
    }
    assert_eq!(
        json!({ "create": Json::Object(created), "source_id": Json::Object(ids) }),
        expected,
        "the Rust constructor diverged from records.py"
    );
}

#[test]
fn figure_and_extract_refusals_match_python() {
    let root = fixtures().join("root");
    let cases: Value = serde_yaml::from_str(
        &std::fs::read_to_string(fixtures().join("cases.yaml")).expect("the cases are readable"),
    )
    .expect("the cases are YAML");
    let Value::Sequence(items) = cases else {
        panic!("the case file holds a sequence");
    };
    let mut produced = Map::new();
    for item in &items {
        let case = item.as_mapping().expect("each case is a mapping");
        produced.insert(case_text(case, "name"), run_case(case, &root));
    }
    assert_eq!(
        Json::Object(produced),
        committed("model_records_cases_expected.json"),
        "the Rust refusals diverged from media_schema.py"
    );
}
