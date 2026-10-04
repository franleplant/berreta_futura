use mag::model::shared;
use mag::model::spec::EditionFile;
use serde_norway::{Mapping, Value};

fn yaml(text: &str) -> Value {
    serde_norway::from_str(text).expect("the case parses")
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
fn typed_spec_files_load_null_and_refuse_unknown_keys() {
    let dir = std::env::temp_dir().join(format!("mag-read-spec-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("the scratch directory is writable");
    let path = dir.join("case.yaml");
    let load = |text: &str| {
        std::fs::write(&path, text).expect("the case is writable");
        shared::read_spec::<EditionFile>(&path)
    };
    let data = load("subtitle: ~\ntitle: T\n").expect("a null subtitle loads");
    assert_eq!((data.subtitle, data.title), (None, "T".to_string()));
    let quoted = load("title: \"a !!null b\"\n").expect("a quoted tag is text");
    assert_eq!(quoted.title, "a !!null b");
    let stale = load("title: T\nstale_key: 1\n").expect_err("an unknown key is refused");
    assert!(
        stale.to_string().contains("unknown field `stale_key`"),
        "{stale}"
    );
    for text in [
        "subtitle: 5\n",
        "title: ~\n",
        "title: null\n",
        "id: 12\n",
        "sources: [3]\n",
    ] {
        let error = load(text).expect_err("a non-text scalar is refused");
        assert!(error.to_string().contains(": invalid type"), "{error}");
    }
    let path_error = load("subtitle: 5\n").unwrap_err();
    assert!(path_error.to_string().contains("subtitle"), "{path_error}");
    assert_eq!(load("issue_number: 13\n").unwrap().issue_number, "13");
}
