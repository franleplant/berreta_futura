use mag::model::shared;
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
        ("label: [a, 1]", "[\"a\",1]"),
        ("label: {a: 1}", "{\"a\":1}"),
        ("label: 1.5", "1.5"),
    ] {
        let error = shared::scalar_label(&mapping(frontmatter)).expect_err(frontmatter);
        assert_eq!(
            error.to_string(),
            format!("Frontmatter label must be text, not {shown}")
        );
    }
    for frontmatter in ["label: Essay", "label:", "title: x", "label: ''"] {
        shared::scalar_label(&mapping(frontmatter)).expect(frontmatter);
    }
}

#[test]
fn anchor_keys_trim_and_lowercase() {
    assert_eq!(shared::anchor_key("  References \t"), "references");
    assert_eq!(shared::anchor_key("Straße"), "straße");
    assert!(shared::is_reference_heading("  REFERENCIAS\n"));
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
fn structured_files_load_null_and_refuse_every_tag() {
    let dir = std::env::temp_dir().join(format!("mag-load-structured-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("the scratch directory is writable");
    let path = dir.join("case.yaml");
    let load = |text: &str| {
        std::fs::write(&path, text).expect("the case is writable");
        shared::load_structured(&path)
    };
    let data = load("label: ~\ntitle: T\n").expect("a null label loads");
    assert_eq!(data.get("label"), Some(&Value::Null));
    assert_eq!(data.get("title"), Some(&Value::from("T")));
    let quoted = load("title: \"a !!null b\"\n").expect("a quoted tag is text");
    assert_eq!(quoted.get("title"), Some(&Value::from("a !!null b")));
    for header in ["label: !!null\n", "label: !custom x\n"] {
        assert!(load(header).is_err(), "{header}");
    }
}
