use mag::model::manifest;
use mag::model::records;
use manifest::{load_edition, load_translation, Edition, LoadOptions, Records};
use std::collections::BTreeSet;
use std::path::Path;

#[test]
fn a_translated_figure_path_stays_source_relative_as_in_the_base_edition() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/typeset_fixtures/corpus");
    let records: Records = records::load_records(&root.join("library/sources"))
        .expect("the fixture records load")
        .into_iter()
        .map(|record| (record.id.clone(), record))
        .collect();
    let known: BTreeSet<String> = records.keys().cloned().collect();
    let options = LoadOptions {
        publication_name: "Magazine",
        source_records: Some(&records),
        allow_missing_art: false,
        allow_unanchored_figures: false,
    };
    let base = load_edition(&root, "906", &known, &options).expect("906 loads");
    let es = load_translation(&root, &base, "es").expect("906 es loads");
    let paths = |edition: &Edition| -> Vec<std::path::PathBuf> {
        edition
            .articles
            .iter()
            .flat_map(|a| &a.figures)
            .map(|f| f.path.clone())
            .collect()
    };
    assert_eq!(paths(&es), paths(&base));
    assert!(paths(&es)[0].ends_with("library/sources/fixture-source-a/media/diagram.png"));
    assert!(es
        .articles
        .iter()
        .flat_map(|a| &a.figures)
        .all(|f| f.path.is_absolute()));
}

#[test]
fn an_unknown_article_opener_is_a_load_error() {
    let root = std::env::temp_dir().join("mag-opener-format-test");
    let dir = root.join("editions/907");
    std::fs::create_dir_all(&dir).expect("temp edition dir");
    std::fs::write(
        dir.join("edition.yaml"),
        "format:\n  article_opener: bogus\n",
    )
    .expect("write");
    let options = LoadOptions {
        publication_name: "Magazine",
        source_records: None,
        allow_missing_art: false,
        allow_unanchored_figures: false,
    };
    let error = load_edition(&root, "907", &BTreeSet::new(), &options).expect_err("refused");
    assert!(error
        .0
        .iter()
        .any(|message| message == "Edition has invalid format.article_opener: bogus"));
}
