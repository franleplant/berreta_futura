use mag::sourcecodes;
use qrcodegen::{Mask, QrCode, QrCodeEcc, QrSegment, Version};

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
fn print_declines_above_106_characters_at_the_illustrated_room() {
    let fits = sourcecodes::fitted(&"a".repeat(106), 41.0).unwrap();
    assert_eq!(fits["modules"], 45);
    assert!(sourcecodes::fitted(&"a".repeat(107), 41.0)
        .unwrap()
        .is_null());
    assert!(!sourcecodes::fitted(&"a".repeat(107), 55.5)
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
    for payload in [
        "cursor.com/blog/third-era",
        "example.com/a/b?c=d",
        "berreta.franleplant.com/editions/012",
    ] {
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
        }
    }
}
