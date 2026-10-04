#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/trace/exact.rs"]
#[allow(dead_code)]
pub mod exact;
#[path = "../src/trace/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

#[path = "../src/trace/elements.rs"]
#[allow(dead_code)]
pub mod elements;

mod trace {
    pub use super::elements::trace_elements;
    #[allow(unused_imports)]
    pub use super::streams::{Color, Element, Face as TextFace, GLYPH_QUANTUM};
}

#[path = "../src/critic/metrics.rs"]
#[allow(dead_code)]
pub mod metrics;

#[path = "../src/critic/text.rs"]
#[allow(dead_code)]
pub mod text;

mod critic {
    pub use super::{metrics, text};
}

#[path = "../src/critic/inspect.rs"]
#[allow(dead_code)]
mod inspect;

use serde_json::Value;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

fn manifest() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

fn fixtures() -> PathBuf {
    manifest().join("tests/critic_inspect_fixtures")
}

fn oracle(name: &str) -> Value {
    let path = manifest().join("tests").join(name);
    serde_json::from_str(
        &std::fs::read_to_string(&path)
            .unwrap_or_else(|error| panic!("{} is readable: {error}", path.display())),
    )
    .expect("the oracle is json")
}

fn digest(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

fn scratch(tag: &str) -> PathBuf {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("a clock after 1970")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("wp53bii-{tag}-{stamp}"));
    std::fs::create_dir_all(&path).expect("the scratch directory is writable");
    path
}

fn poppler_pinned() -> bool {
    let output = std::process::Command::new("pdftoppm")
        .arg("-v")
        .output()
        .expect("poppler is installed");
    let banner = String::from_utf8_lossy(&output.stderr).to_string();
    assert!(
        banner.contains("25.08.0"),
        "the oracle needs the pinned poppler 25.08.0, found {banner}"
    );
    true
}

fn exact(value: &Value) -> f64 {
    value
        .as_str()
        .expect("the oracle carries this float as text")
        .parse()
        .expect("the text is a float")
}

#[test]
fn grayscale_matches_pil() {
    let expected = oracle("critic_inspect_expected.json");
    let rows = expected["grayscale"].as_array().expect("grayscale rows");
    assert!(!rows.is_empty(), "the grayscale oracle is not empty");
    for row in rows {
        let name = row["png"].as_str().expect("png name");
        let source = metrics::decode_rgb(&fixtures().join(name)).expect("the fixture decodes");
        let gray = inspect::grayscale(&source);
        assert_eq!(
            digest(&gray.data),
            row["sha256"].as_str().expect("sha"),
            "grayscale bytes for {name}"
        );
        let histogram = inspect::histogram(&gray);
        assert_eq!(
            digest(
                serde_json::to_string(&histogram.to_vec())
                    .expect("histogram serializes")
                    .as_bytes()
            ),
            row["histogram_sha256"].as_str().expect("histogram sha"),
            "grayscale histogram for {name}"
        );
    }
}

#[test]
fn difference_and_rgb_histogram_match_pil() {
    let expected = oracle("critic_inspect_expected.json");
    let rows = expected["difference"].as_array().expect("difference rows");
    let mut seen = vec![];
    for row in rows {
        let first = metrics::decode_rgb(&fixtures().join(row["first"].as_str().expect("first")))
            .expect("the first fixture decodes");
        let second = metrics::decode_rgb(&fixtures().join(row["second"].as_str().expect("second")))
            .expect("the second fixture decodes");
        let histogram =
            inspect::rgb_histogram(&inspect::difference(&first, &second).expect("the sizes agree"));
        assert_eq!(
            digest(
                serde_json::to_string(&histogram.to_vec())
                    .expect("histogram serializes")
                    .as_bytes()
            ),
            row["histogram_sha256"].as_str().expect("histogram sha"),
            "difference histogram"
        );
        let channel_values = (first.width as u64) * (first.height as u64) * 3;
        let total: u64 = histogram
            .iter()
            .enumerate()
            .map(|(index, &count)| (index % 256) as u64 * count as u64)
            .sum();
        assert_eq!(
            total,
            row["histogram_total"].as_u64().expect("total"),
            "difference histogram total"
        );
        let mae = total as f64 / channel_values as f64;
        assert_eq!(mae.to_bits(), exact(&row["rgb_mae"]).to_bits(), "rgb mae");
        seen.push(mae);
    }
    assert!(
        seen.iter().any(|value| *value > 0.0) && seen.contains(&0.0),
        "the difference oracle must hold a zero and a non-zero case, found {seen:?}"
    );
    let square = metrics::decode_rgb(&fixtures().join("luma_pins.png")).expect("decodes");
    let strip = metrics::decode_rgb(&fixtures().join("threshold_bands.png")).expect("decodes");
    assert!(
        inspect::difference(&square, &strip).is_err(),
        "mismatched sizes must fail rather than truncate"
    );
}

#[test]
fn inspect_page_matches_python_on_the_fixtures() {
    let expected = oracle("critic_inspect_expected.json");
    let cases = expected["cases"].as_array().expect("cases");
    assert!(cases.len() >= 14, "only {} fixture cases", cases.len());
    for case in cases {
        let name = case["name"].as_str().expect("name");
        let produced = inspect::inspect_page(
            &fixtures().join(case["png"].as_str().expect("png")),
            case["page"].as_u64().expect("page") as usize,
            case["text"].as_str().expect("text"),
        )
        .unwrap_or_else(|error| panic!("{name} inspects: {error}"));
        assert_eq!(produced.row(), case["row"], "inspection row for {name}");
    }
}

fn rendered_digests(directory: &Path) -> Vec<(String, String)> {
    let mut entries: Vec<PathBuf> = std::fs::read_dir(directory)
        .expect("the render directory is readable")
        .map(|entry| entry.expect("an entry").path())
        .collect();
    entries.sort();
    entries
        .iter()
        .map(|path| {
            (
                path.file_name()
                    .and_then(|name| name.to_str())
                    .expect("a utf-8 name")
                    .to_string(),
                digest(&std::fs::read(path).expect("the raster is readable")),
            )
        })
        .collect()
}

#[test]
fn render_pages_matches_python_on_the_fixture_pdf() {
    assert!(poppler_pinned());
    let expected = oracle("critic_inspect_render_expected.json");
    let pdf = fixtures().join(expected["pdf"].as_str().expect("pdf name"));
    let directory = scratch("render");
    let produced = inspect::render_pages(&pdf, &directory, None).expect("rasterization succeeds");
    let rows = expected["pages"].as_array().expect("page rows");
    assert_eq!(produced.len(), rows.len(), "raster count");
    let observed = rendered_digests(&directory);
    assert_eq!(observed.len(), rows.len(), "files left in the output");
    for (row, (name, sha)) in rows.iter().zip(&observed) {
        assert_eq!(name, row["name"].as_str().expect("name"), "raster name");
        assert_eq!(sha, row["sha256"].as_str().expect("sha"), "raster {name}");
    }
}

#[test]
fn render_pages_output_does_not_depend_on_the_shard_count() {
    assert!(poppler_pinned());
    let pdf = fixtures().join("pages12.pdf");
    let mut seen = vec![];
    for shards in [Some(1), Some(3), Some(5), Some(12), None] {
        let directory = scratch(&format!("shards-{shards:?}"));
        inspect::render_pages(&pdf, &directory, shards).expect("rasterization succeeds");
        seen.push(rendered_digests(&directory));
    }
    for (index, run) in seen.iter().enumerate().skip(1) {
        assert_eq!(
            run, &seen[0],
            "shard configuration {index} changed the output"
        );
    }
    assert_eq!(seen[0].len(), 12, "the fixture rasterizes twelve pages");
}

#[test]
fn render_pages_reports_the_python_message_when_poppler_fails() {
    assert!(poppler_pinned());
    let directory = scratch("failure");
    let broken = directory.join("not-a.pdf");
    std::fs::write(&broken, b"this is not a pdf").expect("the decoy is writable");
    let error = inspect::render_pages(&broken, &directory.join("out"), None)
        .expect_err("poppler must reject the decoy");
    assert!(
        error
            .to_string()
            .starts_with("Could not rasterize reader PDF for criticism: "),
        "unexpected message: {error}"
    );
}
