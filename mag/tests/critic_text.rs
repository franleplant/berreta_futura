#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/parity/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

#[path = "../src/parity/display.rs"]
#[allow(dead_code)]
pub mod display;

mod parity {
    pub use super::display::trace_elements;
    #[allow(unused_imports)]
    pub use super::streams::{Color, Element, Face as TextFace};
}

#[path = "../src/critic/text.rs"]
#[allow(dead_code)]
mod text;

use std::path::{Path, PathBuf};

fn expected_lowercase() -> Vec<u32> {
    let raw = std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/critic_text_islower_expected.txt"),
    )
    .expect("islower oracle");
    raw.lines().map(|l| l.parse().expect("codepoint")).collect()
}

#[test]
fn islower_matches_python_over_the_whole_plane() {
    let expected: Vec<u32> = expected_lowercase();
    let mut observed = vec![];
    for cp in 0u32..0x110000 {
        if (0xD800..=0xDFFF).contains(&cp) {
            continue;
        }
        if let Some(c) = char::from_u32(cp) {
            if text::py_islower(c) {
                observed.push(cp);
            }
        }
    }
    assert_eq!(observed.len(), expected.len(), "lowercase codepoint count");
    assert_eq!(observed, expected, "lowercase codepoint set");
}

#[test]
fn islower_differs_from_rust_std_on_the_recorded_codepoints() {
    let divergent: [(u32, bool); 4] = [
        (0x0295, true),
        (0x1C8A, false),
        (0xA7CD, false),
        (0x10D70, false),
    ];
    for (cp, python) in divergent {
        let c = char::from_u32(cp).expect("char");
        assert_eq!(text::py_islower(c), python, "python islower for U+{cp:04X}");
        assert_ne!(
            c.is_lowercase(),
            python,
            "std must disagree for U+{cp:04X}, else this test proves nothing"
        );
    }
}

fn reader_pdf() -> PathBuf {
    PathBuf::from(
        "/Users/franguijarro/code/magazine/editions/010/render-2026-09-14T01-47-59/en/reader.pdf",
    )
}

fn font_map() -> std::collections::BTreeMap<String, streams::Face> {
    let spec: serde_yaml::Value = serde_yaml::from_str(
        &std::fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("../meta/verification/parity.yaml"),
        )
        .expect("parity.yaml"),
    )
    .expect("yaml");
    let entries = spec["normalization"]["font_name_map"]["entries"]
        .as_mapping()
        .expect("entries");
    let mut map = std::collections::BTreeMap::new();
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

#[test]
fn reconstructs_edition_010_text() {
    let pdf = reader_pdf();
    if !pdf.exists() {
        println!("SKIPPED: render tree absent at {}", pdf.display());
        return;
    }
    println!("MODE: full, tracing {}", pdf.display());
    let pages = display::trace_elements(&pdf, 1, 56, &font_map()).expect("trace");
    let empty: Vec<usize> = pages
        .iter()
        .enumerate()
        .filter(|(_, els)| text::page_text(els).trim().is_empty())
        .map(|(i, _)| i + 1)
        .collect();
    assert_eq!(
        empty,
        vec![2, 10, 30, 35, 45, 54, 55],
        "empty pages must reproduce pypdf's partition"
    );
    let body: Vec<usize> = pages
        .iter()
        .map(|els| text::body_text_lines(&text::page_text(els)))
        .collect();
    assert_eq!(body[3], 10, "page 4 body lines");
    assert_eq!(body[35], 4, "page 36 body lines");
    assert_eq!(body.iter().sum::<usize>(), 1117, "total body lines");
}
