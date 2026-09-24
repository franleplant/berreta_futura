#[path = "../src/critic/metrics.rs"]
mod metrics;
#[allow(dead_code)]
mod oracle;

use serde_json::Value;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

const JPEG_PIXEL_FLIPS: f64 = 100.0;
const JPEG_CONTRAST_TOLERANCE: f64 = 0.01;

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn input(path: &str) -> PathBuf {
    match oracle::snapshot().join(path) {
        copy if copy.exists() => copy,
        _ if path.starts_with("library/") => oracle::pinned("critic_metrics", path),
        _ => repository().join(path),
    }
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

fn check(row: &Value, pixel_exact: bool) -> Vec<String> {
    let path = row["path"].as_str().expect("path is a string");
    let source =
        metrics::decode_rgb(&input(path)).unwrap_or_else(|error| panic!("{path} decodes: {error}"));
    let mut failures = Vec::new();
    let expected_source = row["source_sha256"].as_str().expect("sha is a string");
    if pixel_exact && digest(&source.data) != expected_source {
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
    if pixel_exact && digest(&thumb.data) != row["thumb_sha256"].as_str().expect("sha is a string")
    {
        failures.push(format!("{path}: thumbnail pixels differ from PIL LANCZOS"));
    }
    let (ratio_tolerance, contrast_tolerance) = if pixel_exact {
        (0.0, 0.0)
    } else {
        (
            JPEG_PIXEL_FLIPS / f64::from(expected_size.0 * expected_size.1),
            JPEG_CONTRAST_TOLERANCE,
        )
    };
    let analysis = metrics::analyze_print_contrast(&source);
    let prepared = metrics::prepare_print_image(&input(path))
        .unwrap_or_else(|error| panic!("{path} prepares: {error}"));
    for (stage, measured) in [("analysis", analysis), ("after", prepared.after)] {
        let oracle = &row[stage];
        for (label, actual, tolerance) in [
            (
                "paper_pixel_ratio",
                measured.paper_pixel_ratio,
                ratio_tolerance,
            ),
            (
                "mark_pixel_ratio",
                measured.mark_pixel_ratio,
                ratio_tolerance,
            ),
            (
                "minimum_mark_contrast_ratio",
                measured.minimum_mark_contrast_ratio,
                contrast_tolerance,
            ),
        ] {
            let wanted = number(oracle, label);
            if (actual - wanted).abs() > tolerance {
                failures.push(format!(
                    "{path}: {stage} {label} {actual} expected {wanted}"
                ));
            }
        }
        if measured.needs_treatment != oracle["needs_treatment"].as_bool().expect("bool") {
            failures.push(format!("{path}: {stage} needs_treatment differs"));
        }
    }
    if prepared.adjusted != row["adjusted"].as_bool().expect("bool") {
        failures.push(format!(
            "{path}: adjusted {} expected {}",
            prepared.adjusted, row["adjusted"]
        ));
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

fn run(group: &str, pixel_exact: bool) {
    let oracle = expected();
    let rows = oracle[group].as_array().expect("group is an array");
    assert!(!rows.is_empty(), "{group} is not empty");
    let failures: Vec<String> = rows
        .iter()
        .flat_map(|row| check(row, pixel_exact))
        .collect();
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}

#[test]
fn edition_010_figures_match_the_python_metrics() {
    run("figures", true);
}

#[test]
fn fixtures_match_the_python_metrics() {
    run("fixtures", true);
}

#[test]
fn library_jpegs_match_the_python_metrics() {
    run("jpeg_figures", false);
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
