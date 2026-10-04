use mag::model::records::{load_records, resolve_extracts, Extract, ExtractRequest};
use mag::model::shared::ValidationError;
use mag::model::spec::ExtractRow;
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/model_records_fixtures/root")
}

fn resolve(manuscript: &str, begin: &str, end: &str, style: &str) -> Result<Vec<Extract>, String> {
    let rows: Vec<ExtractRow> = serde_norway::from_str(&format!(
        "[{{id: x1, source_id: src-a, begin: '{begin}', end: '{end}', style: {style}, caption: c, anchor: Beta Heading}}]"
    ))
    .map_err(|error| error.to_string())?;
    let root = root();
    let request = ExtractRequest {
        root: &root,
        article_id: "a1",
        article_source_ids: &["src-a".to_string()],
        manuscript: &root.join("manuscripts").join(manuscript),
        allow_unanchored: false,
    };
    resolve_extracts(&request, &rows).map_err(|ValidationError(errors)| errors.join("|"))
}

#[test]
fn an_extract_is_pulled_from_the_source_between_unique_markers() {
    let extracts = resolve("en.md", "QUOTE-START", "QUOTE-END", "quote").expect("resolves");
    assert_eq!(extracts.len(), 1);
    assert_eq!(extracts[0].text, "QUOTE-START some quoted words QUOTE-END");
}

#[test]
fn an_ambiguous_begin_marker_is_refused() {
    let error = resolve("en.md", "twice-marker", "QUOTE-END", "quote").expect_err("refused");
    assert!(error.contains("must occur exactly once"), "{error}");
}

#[test]
fn an_ambiguous_end_marker_is_refused() {
    let error = resolve("en.md", "# Source", "twice-marker", "quote").expect_err("refused");
    assert!(error.contains("must occur exactly once"), "{error}");
}

#[test]
fn an_absent_marker_is_refused() {
    let error = resolve("en.md", "NO-SUCH-MARKER", "QUOTE-END", "quote").expect_err("refused");
    assert!(error.contains("must occur exactly once"), "{error}");
}

#[test]
fn a_run_the_manuscript_already_carries_is_refused() {
    let error = resolve("dup.md", "QUOTE-START", "QUOTE-END", "quote").expect_err("refused");
    assert!(
        error.contains("already appears verbatim in the manuscript"),
        "{error}"
    );
}

#[test]
fn an_invalid_style_is_refused_with_its_field_path() {
    let error = resolve("dup.md", "QUOTE-START", "QUOTE-END", "poster").expect_err("refused");
    assert!(
        error.contains("[0].style: unknown variant `poster`"),
        "{error}"
    );
}

#[test]
fn a_code_run_with_layout_significant_whitespace_is_refused() {
    let error = resolve("en.md", "let x = 1;", "}", "code").expect_err("refused");
    assert!(error.contains("layout-significant whitespace"), "{error}");
}

#[test]
fn the_fixture_corpus_loads_every_record_with_its_directory_name_as_id() {
    let sources =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/typeset_fixtures/corpus/library/sources");
    let records = load_records(&sources).expect("the corpus loads");
    assert!(!records.is_empty());
    for record in &records {
        assert!(sources.join(&record.id).is_dir(), "{}", record.id);
    }
}
