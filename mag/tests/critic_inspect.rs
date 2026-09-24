#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/parity/exact.rs"]
#[allow(dead_code)]
pub mod exact;
#[path = "../src/parity/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

#[path = "../src/parity/display.rs"]
#[allow(dead_code)]
pub mod display;

mod parity {
    pub use super::display::trace_elements;
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
use std::collections::BTreeMap;
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

fn outside_strings(raw: &str) -> String {
    let (mut out, mut quoted, mut escaped) = (String::with_capacity(raw.len()), false, false);
    for character in raw.chars() {
        match (quoted, escaped, character) {
            (true, true, _) => escaped = false,
            (true, false, '\\') => escaped = true,
            (true, false, '"') => quoted = false,
            (true, false, _) => {}
            (false, _, '"') => quoted = true,
            (false, _, _) => out.push(character),
        }
    }
    out
}

#[test]
fn serde_json_parses_every_oracle_float_exactly() {
    let mut checked = 0;
    for name in [
        "critic_inspect_expected.json",
        "critic_inspect_render_expected.json",
    ] {
        let raw = outside_strings(
            &std::fs::read_to_string(manifest().join("tests").join(name)).expect("readable"),
        );
        for literal in raw.split(|c: char| !"0123456789.eE+-".contains(c)) {
            if !literal.contains('.') || literal.parse::<f64>().is_err() {
                continue;
            }
            let strict: f64 = literal.parse().expect("a float");
            let loose: f64 = serde_json::from_str::<Value>(literal)
                .expect("json number")
                .as_f64()
                .expect("a float");
            assert_eq!(
                strict.to_bits(),
                loose.to_bits(),
                "serde_json parses {literal} in {name} to a different double, so oracle comparison through as_f64 is unsound here"
            );
            checked += 1;
        }
    }
    assert!(checked > 0, "no float literals were checked");
    let known: f64 = "97.71500651041667".parse().expect("a float");
    let parsed: f64 = serde_json::from_str::<Value>("97.71500651041667")
        .expect("json number")
        .as_f64()
        .expect("a float");
    assert_ne!(
        known.to_bits(),
        parsed.to_bits(),
        "serde_json's inexact parser must still be inexact, else this guard proves nothing"
    );
}

fn naive_luma(pixel: &[u8]) -> u8 {
    (pixel[0] as f64 * 0.299 + pixel[1] as f64 * 0.587 + pixel[2] as f64 * 0.114).round() as u8
}

#[test]
fn grayscale_matches_pil_and_the_naive_formula_disagrees() {
    let expected = oracle("critic_inspect_expected.json");
    let mut divergent = 0;
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
        divergent += source
            .data
            .chunks_exact(3)
            .zip(&gray.data)
            .filter(|(pixel, &value)| naive_luma(pixel) != value)
            .count();
    }
    assert!(
        divergent > 0,
        "the float formula must disagree somewhere, else this test cannot see a luma defect"
    );
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

fn font_map() -> BTreeMap<String, streams::Face> {
    let spec: serde_yaml::Value = serde_yaml::from_str(
        &std::fs::read_to_string(manifest().join("../meta/verification/parity.yaml"))
            .expect("parity.yaml"),
    )
    .expect("yaml");
    let entries = spec["normalization"]["font_name_map"]["entries"]
        .as_mapping()
        .expect("entries");
    let mut map = BTreeMap::new();
    for (alias, value) in entries {
        map.insert(
            alias.as_str().expect("alias").to_string(),
            streams::Face {
                face: value["face"].as_str().expect("face").to_string(),
                file: format!(
                    "{}/../{}",
                    env!("CARGO_MANIFEST_DIR"),
                    value["file"].as_str().expect("file")
                ),
            },
        );
    }
    map
}

fn live_inputs() -> Option<(PathBuf, Value)> {
    let render = std::env::var("MAG_CRITIC_RENDER_DIR").ok();
    let path = std::env::var("MAG_CRITIC_INSPECT_ORACLE").ok();
    match (render, path) {
        (None, None) => None,
        (Some(render), Some(path)) => {
            let raw = std::fs::read_to_string(&path).expect("the live oracle is readable");
            Some((
                PathBuf::from(render),
                serde_json::from_str(&raw).expect("the live oracle is json"),
            ))
        }
        _ => panic!("set both MAG_CRITIC_RENDER_DIR and MAG_CRITIC_INSPECT_ORACLE, or neither"),
    }
}

#[test]
fn inspects_edition_010_like_python() {
    let Some((render, expected)) = live_inputs() else {
        println!("MODE: skipped, MAG_CRITIC_RENDER_DIR and MAG_CRITIC_INSPECT_ORACLE unset");
        return;
    };
    assert!(poppler_pinned());
    println!("MODE: full, inspecting {}", render.display());
    let mut compared = 0;
    let mut rasters = 0;
    for leg in ["reader", "booklet", "cover_booklet"] {
        let block = &expected[leg];
        let rows = block["rows"].as_array().expect("rows");
        let pdf = render.join(block["pdf"].as_str().expect("pdf"));
        let directory = scratch(&format!("live-{leg}"));
        let produced = inspect::render_pages(&pdf, &directory, None).expect("rasterization");
        assert_eq!(
            produced.len(),
            block["rasters"].as_u64().expect("rasters") as usize,
            "raster count for {leg}"
        );
        for (index, row) in rows.iter().enumerate() {
            let mine = &produced[index];
            assert_eq!(
                digest(&std::fs::read(mine).expect("the raster is readable")),
                row["png_sha256"].as_str().expect("png sha"),
                "raster bytes for {leg} page {}",
                row["page"]
            );
            rasters += 1;
            let theirs = render.join(row["png"].as_str().expect("png"));
            let inspection = inspect::inspect_page(
                &theirs,
                row["page"].as_u64().expect("page") as usize,
                row["text"].as_str().expect("text"),
            )
            .expect("inspection succeeds");
            assert_eq!(
                inspection.row(),
                row["row"],
                "inspection row for {leg} page {}",
                row["page"]
            );
            compared += 1;
        }
    }
    println!("COMPARED: {rasters} rasters, {compared} inspection rows");
    assert!(compared >= 85, "only {compared} rows compared");
    tracer_text_report(&render, &expected);
}

fn tracer_text_report(render: &Path, expected: &Value) {
    let block = &expected["reader"];
    let rows = block["rows"].as_array().expect("rows");
    let pages = block["pdf_pages"].as_u64().expect("pdf pages") as u32;
    let traced = display::trace_elements(
        &render.join(block["pdf"].as_str().expect("pdf")),
        1,
        pages,
        &font_map(),
    )
    .expect("the tracer runs");
    let (mut identical, mut raster_identical) = (0, 0);
    let raster_fields = [
        "pixel_dimensions",
        "ink_ratio",
        "ink_bbox",
        "presence_ratio",
        "presence_bbox",
        "sparse",
    ];
    let text_fields = [
        "body_text_lines",
        "text_characters",
        "blank",
        "ink_free",
        "standalone_punctuation_lines",
    ];
    let mut per_field = BTreeMap::new();
    for (row, elements) in rows.iter().zip(&traced) {
        let mine = inspect::inspect_page(
            &render.join(row["png"].as_str().expect("png")),
            row["page"].as_u64().expect("page") as usize,
            &text::page_text(elements),
        )
        .expect("inspection succeeds")
        .row();
        if mine == row["row"] {
            identical += 1;
        }
        if raster_fields
            .iter()
            .all(|field| mine[field] == row["row"][field])
        {
            raster_identical += 1;
        }
        for field in text_fields {
            *per_field.entry(field).or_insert(0) += usize::from(mine[field] == row["row"][field]);
        }
    }
    println!(
        "TRACER TEXT: {identical} of {} rows identical to python, {raster_identical} of {} agree on every raster field",
        rows.len(),
        rows.len()
    );
    for (field, agreed) in &per_field {
        println!("TRACER FIELD: {field} agrees on {agreed} of {}", rows.len());
    }
    assert_eq!(
        raster_identical,
        rows.len(),
        "the text source must not move a raster field"
    );
    assert!(
        identical < rows.len(),
        "the tracer text is known to differ from pypdf on this corpus, so an exact match means the comparison is not running"
    );
}
