#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;

use serde_yaml::{Mapping, Value};
use std::path::Path;

struct Case {
    name: String,
    frontmatter: String,
    expected: String,
    status: String,
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
                status: case["status"].as_str().expect("status").to_string(),
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

fn without_null_guard(case: &Case) -> String {
    let declared = case
        .mapping
        .get(Value::String("label".to_string()))
        .map(shared::py_str)
        .map(|value| shared::py_strip(&value).to_string())
        .unwrap_or_default();
    non_empty_or_ui(case, declared)
}

fn with_std_trim(case: &Case) -> String {
    let declared = case
        .mapping
        .get(Value::String("label".to_string()))
        .filter(|value| !value.is_null())
        .map(shared::py_str)
        .map(|value| value.trim().to_string())
        .unwrap_or_default();
    non_empty_or_ui(case, declared)
}

fn non_empty_or_ui(case: &Case, declared: String) -> String {
    if declared.is_empty() {
        shared::ui("en", &case.content_mode)
    } else {
        declared
    }
}

fn names_disagreeing(variant: fn(&Case) -> String) -> Vec<String> {
    cases()
        .iter()
        .filter(|case| variant(case) != case.expected)
        .map(|case| case.name.clone())
        .collect()
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

#[test]
fn the_null_cases_are_ones_the_missing_guard_got_wrong() {
    let disagreeing = names_disagreeing(without_null_guard);
    assert_eq!(
        disagreeing.len(),
        4,
        "every null spelling must expose the missing guard, else the fixtures \
         prove nothing; disagreeing: {disagreeing:?}"
    );
    assert!(
        disagreeing.iter().all(|name| name.contains("null")),
        "only the null cases may depend on the guard: {disagreeing:?}"
    );
}

#[test]
fn the_whitespace_cases_are_ones_rust_std_trim_got_wrong() {
    let disagreeing = names_disagreeing(with_std_trim);
    assert_eq!(
        disagreeing.len(),
        3,
        "three cases must expose std trim, else the fixtures prove nothing; \
         disagreeing: {disagreeing:?}"
    );
    assert!(
        disagreeing.iter().all(|name| name.contains("U+001E")),
        "only the U+001E cases may depend on the strip: {disagreeing:?}"
    );
}

#[test]
fn the_class_c_case_is_flagged_rather_than_asserted_correct() {
    let all = cases();
    let suspect: Vec<&Case> = all
        .iter()
        .filter(|case| case.status == "agreed_but_suspect")
        .collect();
    assert_eq!(suspect.len(), 1, "one class C case is recorded");
    assert_eq!(
        shared::content_label("en", &suspect[0].mapping, &suspect[0].content_mode),
        "False",
        "pinned as current behaviour, not endorsed; if this changed, the \
         plan-level decision was taken and this case needs rewriting"
    );
    assert!(
        all.iter()
            .all(|case| case.status == "correct" || case.status == "agreed_but_suspect"),
        "every case declares one of the two statuses"
    );
}
