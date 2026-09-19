#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;

use serde_yaml::{Mapping, Value};
use std::path::Path;

struct Case {
    name: String,
    python: String,
    known_divergence: String,
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
            Case {
                name: case["name"].as_str().expect("name").to_string(),
                python: case["python"].as_str().expect("python").to_string(),
                known_divergence: case["known_divergence"]
                    .as_str()
                    .expect("known_divergence")
                    .to_string(),
                mapping: parsed.as_mapping().expect("mapping").clone(),
                content_mode: case["content_mode"].as_str().expect("mode").to_string(),
            }
        })
        .collect()
}

fn observed(case: &Case) -> String {
    shared::content_label("en", &case.mapping, &case.content_mode)
}

#[test]
fn the_label_matches_python_on_every_case_this_wp_owns() {
    let mismatches: Vec<String> = cases()
        .iter()
        .filter(|case| case.known_divergence.is_empty())
        .filter_map(|case| {
            let rust = observed(case);
            (rust != case.python)
                .then(|| format!("{}: python {:?}, rust {:?}", case.name, case.python, rust))
        })
        .collect();
    assert!(mismatches.is_empty(), "{}", mismatches.join("\n"));
}

#[test]
fn the_disagreeing_labels_are_ones_rust_std_trim_gets_wrong() {
    let disagreeing = cases()
        .iter()
        .filter(|case| case.known_divergence.is_empty())
        .filter(|case| {
            let declared = case
                .mapping
                .get(Value::String("label".to_string()))
                .map(shared::py_str)
                .map(|value| value.trim().to_string())
                .unwrap_or_default();
            let with_std = if declared.is_empty() {
                shared::ui("en", &case.content_mode)
            } else {
                declared
            };
            with_std != case.python
        })
        .count();
    assert_eq!(
        disagreeing, 2,
        "two owned cases must expose std trim, else the fixtures prove nothing"
    );
}

#[test]
fn the_null_label_divergence_is_known_and_still_open() {
    let all = cases();
    let recorded: Vec<&Case> = all
        .iter()
        .filter(|case| !case.known_divergence.is_empty())
        .collect();
    assert_eq!(recorded.len(), 1, "one divergence is recorded");
    let case = recorded[0];
    assert_eq!(case.python, "ARTICLE", "{}: the python value", case.name);
    assert_eq!(
        observed(case),
        "None",
        "{}: if this changed, the divergence was fixed; clear known_divergence \
         in the fixture and delete this test",
        case.name
    );
}
