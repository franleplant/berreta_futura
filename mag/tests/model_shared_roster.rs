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

fn expected_isspace() -> Vec<u32> {
    fixture("model_shared_isspace_expected.txt")
        .lines()
        .map(|line| line.parse().expect("codepoint"))
        .collect()
}

const FIELD_SEPARATORS: [u32; 4] = [0x1C, 0x1D, 0x1E, 0x1F];

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

#[test]
fn the_disagreeing_cases_are_ones_rust_std_whitespace_gets_wrong() {
    let oracle: serde_json::Value =
        serde_json::from_str(&fixture("model_shared_roster_expected.json")).expect("json");
    let mut disagreeing = 0;
    for case in oracle["cases"].as_array().expect("cases") {
        let text = case["text"].as_str().expect("text");
        let python = case["python"].as_bool().expect("verdict");
        let with_std: Vec<&str> = text.split('\u{2022}').map(str::trim).collect();
        let std_verdict = with_std.len() >= shared::ROSTER_MIN_NAMES
            && with_std.iter().all(|name| {
                !name.is_empty() && name.split_whitespace().count() <= shared::ROSTER_MAX_NAME_WORDS
            });
        if std_verdict != python {
            disagreeing += 1;
        }
    }
    assert_eq!(
        disagreeing, 2,
        "two cases must expose the std whitespace set, else the fixtures prove nothing"
    );
}

#[test]
fn is_python_space_matches_python_over_the_whole_plane() {
    let expected = expected_isspace();
    let observed: Vec<u32> = (0u32..0x110000)
        .filter_map(char::from_u32)
        .filter(|character| shared::is_python_space(*character))
        .map(u32::from)
        .collect();
    assert_eq!(observed.len(), expected.len(), "python space count");
    assert_eq!(observed, expected, "python space set");
}

#[test]
fn python_space_exceeds_rust_std_by_exactly_the_four_field_separators() {
    let expected = expected_isspace();
    let std_set: Vec<u32> = (0u32..0x110000)
        .filter_map(char::from_u32)
        .filter(|character| character.is_whitespace())
        .map(u32::from)
        .collect();
    let extra: Vec<u32> = expected
        .iter()
        .copied()
        .filter(|point| !std_set.contains(point))
        .collect();
    let missing: Vec<u32> = std_set
        .iter()
        .copied()
        .filter(|point| !expected.contains(point))
        .collect();
    assert_eq!(extra, FIELD_SEPARATORS, "python-only whitespace");
    assert!(missing.is_empty(), "std-only whitespace: {missing:?}");
    assert_eq!((expected.len(), std_set.len()), (29, 25), "sweep counts");
    for point in FIELD_SEPARATORS {
        let character = char::from_u32(point).expect("char");
        assert!(
            shared::is_python_space(character),
            "U+{point:04X} must be python whitespace"
        );
        assert!(
            !character.is_whitespace(),
            "std must not treat U+{point:04X} as whitespace, else this test proves nothing"
        );
    }
}
