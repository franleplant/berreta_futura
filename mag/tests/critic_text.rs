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
    pub use super::streams::{Color, Element, Face as TextFace, GLYPH_QUANTUM};
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

fn reader_pdf() -> Option<PathBuf> {
    std::env::var("MAG_CRITIC_READER_PDF")
        .ok()
        .map(PathBuf::from)
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
    let Some(pdf) = reader_pdf() else {
        println!("MODE: skipped, MAG_CRITIC_READER_PDF unset");
        return;
    };
    assert!(
        pdf.exists(),
        "MAG_CRITIC_READER_PDF set but missing: {}",
        pdf.display()
    );
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

fn text_show(s: &str, x_pt: f64, y_pt: f64, size_pt: f64, advance_pt: f64) -> streams::Element {
    let glyphs = s.chars().count().max(2);
    let step = advance_pt / (glyphs as f64 - 1.0);
    let offs = (0..glyphs)
        .map(|i| [streams::qo(step * i as f64), 0])
        .collect();
    streams::Element::Text {
        s: s.to_string(),
        font: "Test".into(),
        size: streams::qc(size_pt),
        fill: streams::Color {
            family: "DeviceGray".into(),
            rgb: [0, 0, 0],
        },
        glyphs,
        gids: vec![],
        m: [
            streams::qc(size_pt),
            0,
            0,
            streams::qc(size_pt),
            streams::qc(x_pt),
            streams::qc(y_pt),
        ],
        tr: 0,
        clip: vec![],
        offs,
    }
}

#[test]
fn a_real_word_gap_yields_a_space() {
    let first = text_show("Government", 91.0, 700.0, 23.0, 120.0);
    let second = text_show("Rails", 235.0, 700.0, 23.0, 55.0);
    let lines = text::page_lines(&[first, second]);
    assert_eq!(lines.len(), 1, "same y must be one line");
    assert_eq!(
        lines[0], "Government Rails",
        "a 10.7 pt gap against a 5.75 pt threshold must yield a space"
    );
}

#[test]
fn a_kerned_join_yields_no_space() {
    let first = text_show("soft", 91.0, 700.0, 23.0, 40.0);
    let second = text_show("ware", 137.5, 700.0, 23.0, 45.0);
    let lines = text::page_lines(&[first, second]);
    assert_eq!(lines.len(), 1);
    assert_eq!(
        lines[0], "software",
        "an adjoining run must not gain a space"
    );
}
