use mag::model::shared;
use serde_yaml::{Mapping, Value};
use std::path::Path;

struct Case {
    name: String,
    frontmatter: String,
    expected: String,
    mapping: Mapping,
    content_mode: String,
}

fn cases() -> Vec<Case> {
    let raw = std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/model_shared_label_expected.json"),
    )
    .expect("model_shared_label_expected.json is committed");
    let oracle: serde_json::Value = serde_json::from_str(&raw).expect("json");
    oracle["cases"]
        .as_array()
        .expect("cases")
        .iter()
        .map(|case| {
            let frontmatter = case["frontmatter"].as_str().expect("frontmatter");
            let parsed: Value = serde_yaml::from_str(frontmatter).expect("frontmatter parses");
            assert!(
                !case["why"].as_str().expect("why").is_empty(),
                "every case states why its value is what it is"
            );
            Case {
                name: case["name"].as_str().expect("name").to_string(),
                frontmatter: frontmatter.to_string(),
                expected: case["expected"].as_str().expect("expected").to_string(),
                mapping: parsed.as_mapping().expect("mapping").clone(),
                content_mode: case["content_mode"].as_str().expect("mode").to_string(),
            }
        })
        .collect()
}

fn label(frontmatter: &str) -> String {
    let case = cases()
        .into_iter()
        .find(|case| case.frontmatter == frontmatter)
        .unwrap_or_else(|| panic!("{frontmatter} is a committed case"));
    shared::content_label("en", &case.mapping, &case.content_mode)
}

#[test]
fn the_label_is_the_value_each_case_says_it_should_be() {
    let mismatches: Vec<String> = cases()
        .iter()
        .filter_map(|case| {
            let rust = shared::content_label("en", &case.mapping, &case.content_mode);
            (rust != case.expected).then(|| {
                format!(
                    "{}: expected {:?}, got {:?}",
                    case.name, case.expected, rust
                )
            })
        })
        .collect();
    assert!(mismatches.is_empty(), "{}", mismatches.join("\n"));
}

#[test]
fn the_null_label_straddles_the_string_none() {
    assert_eq!(
        label("label:"),
        "ARTICLE",
        "a null label declares nothing, so the UI label applies"
    );
    assert_eq!(
        label("label: None"),
        "None",
        "YAML has no None literal, so this label is the string None"
    );
    assert_ne!(
        label("label:"),
        label("label: None"),
        "a null label and a label of the string None must not render alike; \
         they did before the guard existed, which is what made the defect invisible"
    );
}

#[test]
fn every_spelling_of_null_declares_nothing() {
    for frontmatter in ["label:", "label: ~", "label: null", "label: NULL"] {
        assert_eq!(label(frontmatter), "ARTICLE", "{frontmatter}");
    }
    assert_eq!(
        label("label: \"\""),
        "ARTICLE",
        "an empty string declares nothing either, by a different route"
    );
}

#[test]
fn a_padded_label_proves_the_declared_branch_was_taken() {
    assert_eq!(
        label("label: \"\\u001EDispatch\\u001E\""),
        "Dispatch",
        "the padding is stripped and the declared text survives"
    );
    assert_ne!(
        label("label: \"\\u001EDispatch\\u001E\""),
        shared::ui("en", "article"),
        "this value must differ from the fallback, or the case cannot tell \
         the declared branch from the fallback branch"
    );
}
