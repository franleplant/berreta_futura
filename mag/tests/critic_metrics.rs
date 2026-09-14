#[path = "../src/critic/metrics.rs"]
mod metrics;

use serde_json::Value;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn expected() -> Value {
    let raw = std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/critic_metrics_expected.json"),
    )
    .expect("the committed oracle is readable");
    serde_json::from_str(&raw).expect("the oracle is json")
}

fn digest(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

fn number(value: &Value, key: &str) -> f64 {
    value[key]
        .as_f64()
        .unwrap_or_else(|| panic!("{key} is a number"))
}

fn check(row: &Value) -> Vec<String> {
    let path = row["path"].as_str().expect("path is a string");
    let source = metrics::decode_rgb(&repository().join(path))
        .unwrap_or_else(|error| panic!("{path} decodes: {error}"));
    let mut failures = Vec::new();
    let expected_source = row["source_sha256"].as_str().expect("sha is a string");
    if digest(&source.data) != expected_source {
        failures.push(format!(
            "{path}: decoded pixels differ from PIL convert(RGB)"
        ));
    }
    let thumb = metrics::thumbnail(&source);
    let expected_size = (
        row["thumb_size"][0].as_u64().expect("width") as u32,
        row["thumb_size"][1].as_u64().expect("height") as u32,
    );
    if (thumb.width, thumb.height) != expected_size {
        failures.push(format!(
            "{path}: thumbnail size {:?} expected {:?}",
            (thumb.width, thumb.height),
            expected_size
        ));
    }
    if digest(&thumb.data) != row["thumb_sha256"].as_str().expect("sha is a string") {
        failures.push(format!("{path}: thumbnail pixels differ from PIL LANCZOS"));
    }
    let analysis = metrics::analyze_print_contrast(&source);
    let oracle = &row["analysis"];
    for (label, actual, wanted) in [
        (
            "paper_pixel_ratio",
            analysis.paper_pixel_ratio,
            number(oracle, "paper_pixel_ratio"),
        ),
        (
            "mark_pixel_ratio",
            analysis.mark_pixel_ratio,
            number(oracle, "mark_pixel_ratio"),
        ),
        (
            "minimum_mark_contrast_ratio",
            analysis.minimum_mark_contrast_ratio,
            number(oracle, "minimum_mark_contrast_ratio"),
        ),
    ] {
        if actual != wanted {
            failures.push(format!("{path}: {label} {actual} expected {wanted}"));
        }
    }
    if analysis.needs_treatment != oracle["needs_treatment"].as_bool().expect("bool") {
        failures.push(format!("{path}: needs_treatment differs"));
    }
    let prepared = metrics::prepare_print_image(&repository().join(path))
        .unwrap_or_else(|error| panic!("{path} prepares: {error}"));
    if prepared.adjusted != row["adjusted"].as_bool().expect("bool") {
        failures.push(format!(
            "{path}: adjusted {} expected {}",
            prepared.adjusted, row["adjusted"]
        ));
    }
    let after = &row["after"];
    if prepared.after.minimum_mark_contrast_ratio != number(after, "minimum_mark_contrast_ratio")
        || prepared.after.mark_pixel_ratio != number(after, "mark_pixel_ratio")
        || prepared.after.paper_pixel_ratio != number(after, "paper_pixel_ratio")
        || prepared.after.needs_treatment != after["needs_treatment"].as_bool().expect("bool")
    {
        failures.push(format!("{path}: post-treatment analysis differs"));
    }
    if prepared.unresolved() != row["unresolved"].as_bool().expect("bool") {
        failures.push(format!("{path}: unresolved differs"));
    }
    if prepared.before != analysis {
        failures.push(format!("{path}: prepared before analysis differs"));
    }
    match (&prepared.image, prepared.adjusted) {
        (Some(enhanced), true) => {
            if (enhanced.width, enhanced.height) != (source.width, source.height) {
                failures.push(format!("{path}: enhanced image changed dimensions"));
            }
            if analysis_of(enhanced) != prepared.after {
                failures.push(format!(
                    "{path}: enhanced pixels disagree with the after analysis"
                ));
            }
        }
        (None, false) => {}
        _ => failures.push(format!("{path}: adjusted flag disagrees with the payload")),
    }
    failures
}

fn analysis_of(image: &metrics::Rgb) -> metrics::PrintContrastAnalysis {
    metrics::analyze_print_contrast(image)
}

fn run(group: &str) {
    let oracle = expected();
    let rows = oracle[group].as_array().expect("group is an array");
    assert!(!rows.is_empty(), "{group} is not empty");
    let failures: Vec<String> = rows.iter().flat_map(check).collect();
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}

#[test]
fn edition_010_figures_match_the_python_metrics() {
    run("figures");
}

#[test]
fn fixtures_match_the_python_metrics() {
    run("fixtures");
}

#[test]
fn rounding_matches_python_round() {
    let raw = std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/critic_metrics_rounding_expected.json"),
    )
    .expect("the committed rounding oracle is readable");
    let oracle: Value = serde_json::from_str(&raw).expect("the oracle is json");
    for case in oracle["half_even"].as_array().expect("array") {
        let value = case["value"].as_f64().expect("value");
        let expected = case["expected"].as_i64().expect("expected");
        assert_eq!(
            metrics::round_half_even(value),
            expected,
            "round({value}) should be {expected}"
        );
    }
    for case in oracle["places"].as_array().expect("array") {
        let value = case["value"].as_f64().expect("value");
        let places = case["places"].as_u64().expect("places") as usize;
        let expected = case["expected"].as_f64().expect("expected");
        assert_eq!(
            metrics::round_places(value, places),
            expected,
            "round({value}, {places}) should be {expected}"
        );
    }
}

#[test]
fn worker_count_matches_the_python_bounds() {
    assert_eq!(metrics::worker_count(0, None), 1);
    assert_eq!(metrics::worker_count(5, Some(3)), 3);
    assert_eq!(metrics::worker_count(2, Some(9)), 2);
    assert_eq!(metrics::worker_count(9, Some(0)), 1);
    assert!(metrics::worker_count(100, None) <= metrics::MAX_WORKERS);
}

#[test]
fn ordered_map_preserves_order_and_reports_the_first_failure() {
    let items: Vec<usize> = (0..25).collect();
    let doubled = metrics::ordered_map(|value| Ok(value * 2), &items, None).expect("no item fails");
    assert_eq!(
        doubled,
        items.iter().map(|value| value * 2).collect::<Vec<_>>()
    );
    let failed = metrics::ordered_map(
        |value| {
            if *value == 7 || *value == 19 {
                anyhow::bail!("item {value}")
            } else {
                Ok(*value)
            }
        },
        &items,
        None,
    );
    let error = failed.expect_err("two items fail");
    assert_eq!(error.to_string(), "item 7");
}
