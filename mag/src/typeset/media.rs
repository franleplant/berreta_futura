use crate::model::shared::{Result, ValidationError};
use std::path::Path;

const PNG_MAGIC: [u8; 8] = [0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A];
const JPEG_MAGIC: [u8; 2] = [0xFF, 0xD8];
const NOT_A_SIZE: [u8; 3] = [0xC4, 0xC8, 0xCC];

fn refuse(path: &Path, why: &str) -> ValidationError {
    ValidationError::one(format!("Cannot read the size of {}: {why}", path.display()))
}

fn be16(bytes: &[u8], at: usize) -> Option<u32> {
    Some(u32::from(u16::from_be_bytes([
        *bytes.get(at)?,
        *bytes.get(at + 1)?,
    ])))
}

fn be32(bytes: &[u8], at: usize) -> Option<u32> {
    Some(u32::from_be_bytes([
        *bytes.get(at)?,
        *bytes.get(at + 1)?,
        *bytes.get(at + 2)?,
        *bytes.get(at + 3)?,
    ]))
}

fn png_pixels(bytes: &[u8]) -> Option<(u32, u32)> {
    if &bytes.get(12..16)? != b"IHDR" {
        return None;
    }
    Some((be32(bytes, 16)?, be32(bytes, 20)?))
}

fn exif_orientation(segment: &[u8]) -> Option<u32> {
    let tiff = segment.strip_prefix(b"Exif\0\0")?;
    let big = match tiff.get(0..2)? {
        b"MM" => true,
        b"II" => false,
        _ => return None,
    };
    let read = |at: usize, width: usize| -> Option<u32> {
        let field = tiff.get(at..at + width)?;
        let fold = |sum: u32, byte: &u8| (sum << 8) | u32::from(*byte);
        Some(if big {
            field.iter().fold(0, fold)
        } else {
            field.iter().rev().fold(0, fold)
        })
    };
    let ifd = read(4, 4)? as usize;
    (0..read(ifd, 2)? as usize)
        .map(|entry| ifd + 2 + 12 * entry)
        .find(|&entry| read(entry, 2) == Some(0x0112))
        .and_then(|entry| read(entry + 8, 2))
}

fn jpeg_pixels(bytes: &[u8]) -> Option<(u32, u32, u32)> {
    let mut orientation = 1;
    let mut at = 2;
    while at + 4 <= bytes.len() {
        if bytes[at] != 0xFF {
            at += 1;
            continue;
        }
        let marker = bytes[at + 1];
        if (0xC0..=0xCF).contains(&marker) && !NOT_A_SIZE.contains(&marker) {
            return Some((be16(bytes, at + 7)?, be16(bytes, at + 5)?, orientation));
        }
        if marker == 0xE1 {
            let end = at + 2 + be16(bytes, at + 2)? as usize;
            orientation = exif_orientation(bytes.get(at + 4..end)?).unwrap_or(orientation);
        }
        if marker == 0xD8 || marker == 0x01 || (0xD0..=0xD7).contains(&marker) {
            at += 2;
        } else {
            at += 2 + be16(bytes, at + 2)? as usize;
        }
    }
    None
}

pub fn pixels(path: &Path) -> Result<(u32, u32)> {
    let bytes = std::fs::read(path).map_err(|error| refuse(path, &error.to_string()))?;
    let size = if bytes.starts_with(&PNG_MAGIC) {
        png_pixels(&bytes).map(|(width, height)| (width, height, 1))
    } else if bytes.starts_with(&JPEG_MAGIC) {
        jpeg_pixels(&bytes)
    } else {
        return Err(refuse(
            path,
            "a curated figure must be a PNG or a JPEG; convert it before building",
        ));
    };
    let (width, height, orientation) =
        size.ok_or_else(|| refuse(path, "its header carries no frame size"))?;
    if orientation != 1 {
        return Err(refuse(
            path,
            &format!("EXIF orientation {orientation} needs a re-encode to rotate; rotate the file losslessly (jpegtran) to orientation 1"),
        ));
    }
    if width == 0 || height == 0 {
        return Err(refuse(path, "its header states a zero dimension"));
    }
    Ok((width, height))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn media_fixtures() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/typeset_fixtures/media")
    }

    #[test]
    fn a_png_and_a_jpeg_report_the_two_different_sizes_their_headers_state() {
        let png = pixels(&media_fixtures().join("landscape.png")).expect("the png reads");
        let jpeg = pixels(&media_fixtures().join("portrait.jpg")).expect("the jpeg reads");
        assert_eq!(png, (40, 25));
        assert_eq!(jpeg, (17, 29));
        assert_ne!(png, jpeg);
        assert_ne!(png.0, png.1);
        assert_ne!(jpeg.0, jpeg.1);
    }

    #[test]
    fn a_jpeg_that_asks_to_be_rotated_is_refused_and_orientation_one_is_not() {
        let upright = pixels(&media_fixtures().join("exif.jpg")).expect("orientation 1 reads");
        assert_eq!(upright, (24, 16));
        for name in ["rotated.jpg", "rotated-mm.jpg"] {
            let error = pixels(&media_fixtures().join(name)).expect_err("orientation 6 is refused");
            assert!(
                error.to_string().contains("EXIF orientation 6"),
                "{name}: {error}"
            );
        }
    }

    #[test]
    fn a_format_with_no_reader_is_refused_by_name_rather_than_guessed() {
        let error = pixels(&media_fixtures().join("figure.webp")).expect_err("webp is refused");
        assert!(
            error.to_string().contains("must be a PNG or a JPEG"),
            "{error}"
        );
        let missing =
            pixels(&media_fixtures().join("absent.png")).expect_err("a missing file is refused");
        assert!(missing.to_string().contains("absent.png"), "{missing}");
    }
}
