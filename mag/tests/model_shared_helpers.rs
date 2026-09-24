#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;

use serde_yaml::{Mapping, Value};

fn yaml(text: &str) -> Value {
    serde_yaml::from_str(text).expect("the case parses")
}

fn mapping(text: &str) -> Mapping {
    yaml(text).as_mapping().expect("a mapping").clone()
}

#[test]
fn a_container_label_is_refused_rather_than_printed_as_brackets() {
    for (frontmatter, shown) in [
        ("label: []", "[]"),
        ("label: {}", "{}"),
        ("label: [a, 1]", "['a', 1]"),
        ("label: {a: 1}", "{'a': 1}"),
    ] {
        let error = shared::scalar_label(&mapping(frontmatter)).expect_err(frontmatter);
        assert_eq!(
            error.to_string(),
            format!("Frontmatter label must be text, not {shown}")
        );
    }
    for frontmatter in [
        "label: Essay",
        "label:",
        "label: 1.5",
        "title: x",
        "label: ''",
    ] {
        shared::scalar_label(&mapping(frontmatter)).expect(frontmatter);
    }
}

#[test]
fn anchor_keys_strip_like_python_and_fold_case() {
    assert_eq!(shared::anchor_key("\u{1c} References \u{1f}"), "references");
    assert_eq!(shared::anchor_key("Straße"), "strasse");
    assert!(shared::is_reference_heading("  REFERENCIAS\u{1e}"));
    assert!(shared::is_reference_heading("References"));
    assert!(!shared::is_reference_heading("Further references"));
}

#[test]
fn the_article_opener_format_is_empty_unless_declared_as_text() {
    let format = |text: &str| shared::article_opener_format(&yaml(text));
    assert_eq!(
        format("format: {article_opener: ' illustrated_paper_spots_v1 '}"),
        "illustrated_paper_spots_v1"
    );
    assert_eq!(format("format: {article_opener: null}"), "");
    assert_eq!(format("format: {article_opener: ''}"), "");
    assert_eq!(format("format: {}"), "");
    assert_eq!(format("format: illustrated_paper_spots_v1"), "");
    assert_eq!(format("title: x"), "");
}

#[test]
fn raw_or_falls_back_on_every_python_falsy_value() {
    for falsy in ["~", "false", "0", "0.0", "''", "[]", "{}"] {
        assert_eq!(shared::raw_or(Some(&yaml(falsy)), "fallback"), "fallback");
    }
    assert_eq!(shared::raw_or(None, "fallback"), "fallback");
    assert_eq!(shared::raw_or(Some(&yaml("true")), "fallback"), "True");
    assert_eq!(shared::raw_or(Some(&yaml("Cover")), "fallback"), "Cover");
}

#[test]
fn structured_files_load_null_tags_like_python_and_refuse_them_on_collections() {
    let dir = std::env::temp_dir().join(format!("mag-load-structured-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("the scratch directory is writable");
    let path = dir.join("case.yaml");
    let load = |text: &str| {
        std::fs::write(&path, text).expect("the case is writable");
        shared::load_structured(&path)
    };
    for spelling in [
        "~",
        "!!null",
        "!!null ''",
        "!!null foo",
        "!<tag:yaml.org,2002:null> x",
    ] {
        let data = load(&format!("label: {spelling}\ntitle: T\n")).expect(spelling);
        assert_eq!(data.get("label"), Some(&Value::Null), "{spelling}");
        assert_eq!(data.get("title"), Some(&Value::from("T")), "{spelling}");
    }
    let quoted = load("title: \"a !!null b\"\n").expect("a quoted tag is text");
    assert_eq!(quoted.get("title"), Some(&Value::from("a !!null b")));
    for header in [
        "label: !!null [a]",
        "label: !!null {a: 1}",
        "x: !!null\ny: !!null [a]",
    ] {
        let error = load(header).expect_err(header).to_string();
        assert!(
            error.starts_with("Cannot read ")
                && error.contains("expected a scalar node for !!null"),
            "{header}: {error}"
        );
    }
    assert!(
        load("label: !custom x\n").is_err(),
        "other tags stay refused"
    );
}
