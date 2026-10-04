#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;

use std::path::Path;

fn fixture(name: &str) -> String {
    std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("tests")
            .join(name),
    )
    .unwrap_or_else(|_| panic!("{name} is committed"))
}

#[test]
fn the_roster_test_matches_python_on_the_committed_cases() {
    let oracle: serde_json::Value =
        serde_json::from_str(&fixture("model_shared_roster_expected.json")).expect("json");
    let cases = oracle["cases"].as_array().expect("cases");
    assert_eq!(cases.len(), 3, "all three recorded cases are committed");
    let mismatches: Vec<String> = cases
        .iter()
        .filter_map(|case| {
            let text = case["text"].as_str().expect("text");
            let python = case["python"].as_bool().expect("verdict");
            let rust = shared::is_name_roster(text);
            (rust != python).then(|| {
                let name = case["name"].as_str().expect("name");
                format!("{name}: python {python}, rust {rust}, for {text:?}")
            })
        })
        .collect();
    assert!(mismatches.is_empty(), "{}", mismatches.join("\n"));
}
