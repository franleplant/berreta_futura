#[path = "../src/model/doc.rs"]
#[allow(dead_code)]
mod doc;
#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;

use serde_json::{json, Map, Value};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn settable() -> BTreeSet<u32> {
    doc::settable_codepoints(&repository().join("mag/assets/fonts"))
        .expect("the vendored faces are readable")
}

fn projection(markdown: &str, settable: &BTreeSet<u32>) -> Value {
    let document = doc::parse_publication_document(markdown).expect("the manuscript parses");
    let visible = doc::visible_blocks(&document.blocks);
    let text: Vec<&str> = visible.iter().map(|(_, body)| body.as_str()).collect();
    let educated = doc::educate_reader_quotes(&text.join("\n"));
    let folded = doc::fold_reader_characters(&educated, settable);
    let keys: Vec<String> = document
        .metadata
        .keys()
        .filter_map(|key| key.as_str().map(str::to_string))
        .collect();
    let mut sorted = keys;
    sorted.sort();
    json!({
        "metadata_keys": sorted,
        "visible_blocks": visible
            .iter()
            .map(|(kind, body)| json!([kind, body]))
            .collect::<Vec<Value>>(),
        "block_signature": doc::block_signature(&document.blocks),
        "educated": educated,
        "folded": folded,
    })
}

fn dump(directory: &Path, pattern: &str, settable: &BTreeSet<u32>) -> Map<String, Value> {
    let mut entries: Vec<PathBuf> = std::fs::read_dir(directory)
        .expect("the manuscript directory is readable")
        .map(|entry| entry.expect("the entry is readable").path())
        .collect();
    entries.sort();
    let mut dumped = Map::new();
    for entry in entries {
        let (name, markdown) = match pattern {
            "*.md" if entry.extension().is_some_and(|kind| kind == "md") => (
                entry
                    .file_stem()
                    .expect("the fixture has a stem")
                    .to_string_lossy()
                    .to_string(),
                std::fs::read_to_string(&entry).expect("the fixture is readable"),
            ),
            "final.md" if entry.join("final.md").is_file() => (
                entry
                    .file_name()
                    .expect("the article has a name")
                    .to_string_lossy()
                    .to_string(),
                std::fs::read_to_string(entry.join("final.md"))
                    .expect("the manuscript is readable"),
            ),
            _ => continue,
        };
        dumped.insert(name, projection(&markdown, settable));
    }
    dumped
}

#[test]
fn fixtures_match_the_python_projection() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let expected: Value = serde_json::from_str(
        &std::fs::read_to_string(root.join("tests/model_doc_expected.json"))
            .expect("the committed expectation is readable"),
    )
    .expect("the committed expectation is JSON");
    let produced = dump(&root.join("tests/model_doc_fixtures"), "*.md", &settable());
    assert_eq!(
        Value::Object(produced),
        expected,
        "the Rust projection diverged from the committed Python projection"
    );
}

#[test]
fn settable_codepoints_match_the_python_intersection() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let expected = std::fs::read_to_string(root.join("tests/model_doc_settable.txt"))
        .expect("the committed codepoints are readable");
    let produced: Vec<String> = settable()
        .iter()
        .map(|codepoint| format!("{codepoint:04X}"))
        .collect();
    assert_eq!(
        produced.join("\n"),
        expected.trim_end_matches('\n'),
        "the Rust cmap intersection diverged from fontTools"
    );
}

#[test]
fn edition_manuscripts_match_the_python_projection() {
    let articles = std::env::var("MAG_MODEL_ARTICLES").ok();
    let oracle = std::env::var("MAG_MODEL_ORACLE").ok();
    let (articles, oracle) = match (articles, oracle) {
        (None, None) => return,
        (Some(articles), Some(oracle)) => (articles, oracle),
        _ => panic!("MAG_MODEL_ARTICLES and MAG_MODEL_ORACLE must be set together"),
    };
    let expected: Value = serde_json::from_str(
        &std::fs::read_to_string(&oracle).expect("the oracle dump is readable"),
    )
    .expect("the oracle dump is JSON");
    let produced = dump(Path::new(&articles), "final.md", &settable());
    assert_eq!(
        Value::Object(produced),
        expected,
        "the Rust projection diverged from the Python projection of the edition"
    );
}
