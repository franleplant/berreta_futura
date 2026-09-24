#[allow(dead_code)]
mod oracle;
#[allow(dead_code)]
#[path = "../src/sourcecodes.rs"]
mod sourcecodes;

use qrcodegen::{Mask, QrCode, QrCodeEcc, QrSegment, Version};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::Command;

const CORPUS: &str = "tests/typeset_fixtures/corpus";
const SNAPSHOT: &str = "tests/repo_snapshot";
const EDITIONS: [(&str, &str); 9] = [
    (SNAPSHOT, "008"),
    (SNAPSHOT, "010"),
    (CORPUS, "900"),
    (CORPUS, "901"),
    (CORPUS, "902"),
    (CORPUS, "903"),
    (CORPUS, "904"),
    (CORPUS, "905"),
    (CORPUS, "906"),
];

fn expected(edition: &str) -> PathBuf {
    Path::new("tests/sourcecodes_expected").join(edition)
}

#[test]
fn rust_writes_every_committed_expected_file_byte_for_byte() {
    for (root, edition) in EDITIONS {
        let (files, declines) = sourcecodes::build(Path::new(root), edition).unwrap();
        let differences = sourcecodes::differences(&files, &expected(edition)).unwrap();
        assert!(differences.is_empty(), "{edition}: {differences:?}");
        assert_eq!(declines, 0, "{edition}");
    }
}

#[test]
fn committed_expected_files_are_what_the_python_tool_writes() {
    if !oracle::live() {
        return;
    }
    let scratch = std::env::temp_dir().join(format!("mag-sourcecodes-{}", std::process::id()));
    for (root, edition) in EDITIONS {
        let destination = scratch.join(edition);
        let status = Command::new("uv")
            .args([
                "run",
                "--quiet",
                "python",
                "mag/tests/sourcecodes_oracle.py",
            ])
            .arg(Path::new(root).canonicalize().unwrap())
            .arg(edition)
            .arg(&destination)
            .current_dir("..")
            .status()
            .expect("uv runs");
        assert!(status.success(), "{edition}: python oracle failed");
        let files: sourcecodes::Files = std::fs::read_dir(&destination)
            .unwrap()
            .map(|entry| {
                let path = entry.unwrap().path();
                (
                    path.file_name().unwrap().to_string_lossy().into_owned(),
                    std::fs::read(path).unwrap(),
                )
            })
            .collect();
        let differences = sourcecodes::differences(&files, &expected(edition)).unwrap();
        assert!(differences.is_empty(), "{edition}: {differences:?}");
    }
    std::fs::remove_dir_all(scratch).ok();
}

#[test]
fn segno_deviation_adds_a_zero_byte_at_a_codeword_boundary() {
    let (version, level, words) =
        sourcecodes::codewords("cursor.com/blog/third-era", QrCodeEcc::Low).unwrap();
    assert_eq!(words[..6], [0x41, 0x96, 0x37, 0x57, 0x27, 0x36]);
    assert_eq!(words[25..], [0x26, 0x10, 0x00]);
    let seg = QrSegment::make_bytes(b"cursor.com/blog/third-era");
    let iso = QrCode::encode_segments_advanced(
        &[seg],
        level,
        version,
        version,
        Some(Mask::new(0)),
        false,
    )
    .unwrap();
    let ours = QrCode::encode_codewords(version, level, &words, Some(Mask::new(0)));
    let size = iso.size();
    let differing = (0..size * size)
        .filter(|i| iso.get_module(i % size, i / size) != ours.get_module(i % size, i / size))
        .count();
    assert!(
        differing > 0,
        "the segno pad byte must change the matrix against ISO/IEC 18004 7.4.10"
    );
    assert_eq!((version, level), (Version::new(2), QrCodeEcc::Medium));
}

#[test]
fn print_declines_above_78_characters_at_the_illustrated_room() {
    let fits = sourcecodes::fitted(&"a".repeat(78), 41.0).unwrap();
    assert_eq!(fits["modules"], 41);
    assert!(sourcecodes::fitted(&"a".repeat(79), 41.0)
        .unwrap()
        .is_null());
    assert!(!sourcecodes::fitted(&"a".repeat(79), 55.5)
        .unwrap()
        .is_null());
}

#[test]
fn payload_strips_scheme_and_www_only() {
    assert_eq!(
        sourcecodes::payload(" https://www.example.com/a "),
        "example.com/a"
    );
    assert_eq!(
        sourcecodes::payload("http://example.com/www.b"),
        "example.com/www.b"
    );
    assert_eq!(
        sourcecodes::payload("ftp://www.example.com"),
        "ftp://www.example.com"
    );
    assert!(sourcecodes::matrix("example.com/\u{e9}", QrCodeEcc::Low).is_err());
}

fn decode(matrix: &[Vec<bool>]) -> String {
    let (scale, quiet) = (4, 4);
    let side = (matrix.len() + 2 * quiet) * scale;
    let mut image = rqrr::PreparedImage::prepare_from_greyscale(side, side, |x, y| {
        let (col, row) = (
            (x / scale).wrapping_sub(quiet),
            (y / scale).wrapping_sub(quiet),
        );
        let dark = matrix
            .get(row)
            .and_then(|cells| cells.get(col))
            .copied()
            .unwrap_or(false);
        if dark {
            0
        } else {
            255
        }
    });
    let grids = image.detect_grids();
    assert_eq!(grids.len(), 1);
    grids[0].decode().unwrap().1
}

#[test]
fn every_code_decodes_to_its_payload() {
    let mut decoded = 0;
    for (_, edition) in EDITIONS {
        let text = std::fs::read_to_string(expected(edition).join("codes.json")).unwrap();
        let index: Value = serde_json::from_str(&text).unwrap();
        for code in index["codes"].as_array().unwrap() {
            let payload = code["payload"].as_str().unwrap();
            for level in [
                QrCodeEcc::Low,
                QrCodeEcc::Medium,
                QrCodeEcc::Quartile,
                QrCodeEcc::High,
            ] {
                assert_eq!(
                    decode(&sourcecodes::matrix(payload, level).unwrap()),
                    payload
                );
                decoded += 1;
            }
        }
    }
    assert_eq!(decoded, 4 * 28);
}
