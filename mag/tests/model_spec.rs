use mag::model::spec::{EditionFile, SourceRecord, TranslationFile};
use regex::Regex;
use serde::de::DeserializeOwned;
use std::path::{Path, PathBuf};

fn failures<T: DeserializeOwned>(files: Vec<PathBuf>) -> Vec<String> {
    let legacy = Regex::new(r"content_mode: (faithful_\w+|selected_extracts|original_synthesis)")
        .expect("the pattern compiles");
    files
        .into_iter()
        .filter_map(|path| {
            let text = std::fs::read_to_string(&path).expect("the file is readable");
            let text = legacy.replace_all(&text, "content_mode: article");
            mag::model::shared::parse_yaml::<T>(&text)
                .err()
                .map(|error| format!("{}: {error}", path.display()))
        })
        .collect()
}

fn children(dir: &Path) -> Vec<PathBuf> {
    let mut paths: Vec<PathBuf> = std::fs::read_dir(dir)
        .map(|entries| entries.flatten().map(|entry| entry.path()).collect())
        .unwrap_or_default();
    paths.sort();
    paths
}

fn corpora() -> Vec<PathBuf> {
    let crate_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    vec![
        crate_dir.join(".."),
        crate_dir.join("tests/typeset_fixtures/corpus"),
    ]
}

#[test]
fn every_committed_edition_translation_and_record_fits_its_strict_schema() {
    let mut editions = Vec::new();
    let mut translations = Vec::new();
    let mut records = Vec::new();
    for root in corpora() {
        for dir in children(&root.join("editions")) {
            editions.push(dir.join("edition.yaml"));
            for language in children(&dir.join("translations")) {
                translations.push(language.join("edition.yaml"));
            }
        }
        for dir in children(&root.join("library/sources")) {
            records.push(dir.join("record.yaml"));
        }
    }
    editions.retain(|path| path.is_file());
    records.retain(|path| path.is_file());
    assert!(editions.len() > 10 && !translations.is_empty() && records.len() > 100);
    let mut failed = failures::<EditionFile>(editions);
    failed.extend(failures::<TranslationFile>(translations));
    failed.extend(failures::<SourceRecord>(records));
    assert!(failed.is_empty(), "{}", failed.join("\n"));
}
