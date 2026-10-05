use crate::model::shared::{Result, ValidationError};
use image::{ImageDecoder, ImageReader};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

static SIZES: OnceLock<Mutex<HashMap<PathBuf, (u32, u32)>>> = OnceLock::new();

fn refuse(path: &Path, why: &str) -> ValidationError {
    ValidationError::one(format!("Cannot read the size of {}: {why}", path.display()))
}

fn read_size(path: &Path) -> Result<(u32, u32)> {
    let reader = ImageReader::open(path)
        .and_then(ImageReader::with_guessed_format)
        .map_err(|error| refuse(path, &error.to_string()))?;
    if reader.format().is_none() {
        return Err(refuse(
            path,
            "its format is not one the figure reader decodes (png, jpg, gif, webp); convert it before building",
        ));
    }
    let mut decoder = reader
        .into_decoder()
        .map_err(|error| refuse(path, &error.to_string()))?;
    let (width, height) = decoder.dimensions();
    let orientation = decoder
        .orientation()
        .map_or(1, image::metadata::Orientation::to_exif);
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

pub fn pixels(path: &Path) -> Result<(u32, u32)> {
    let cache = SIZES.get_or_init(Mutex::default);
    if let Some(size) = cache
        .lock()
        .expect("the size cache is not poisoned")
        .get(path)
    {
        return Ok(*size);
    }
    let size = read_size(path)?;
    cache
        .lock()
        .expect("the size cache is not poisoned")
        .insert(path.to_path_buf(), size);
    Ok(size)
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
    fn webp_reads_and_an_unknown_format_or_missing_file_is_refused_by_name() {
        let webp = pixels(&media_fixtures().join("figure.webp")).expect("webp reads");
        assert_eq!(webp, (11, 13));
        let text = std::env::temp_dir().join("media-not-an-image.txt");
        std::fs::write(&text, "plain text").expect("the scratch file writes");
        let error = pixels(&text).expect_err("text is refused");
        assert!(error.to_string().contains("png, jpg, gif, webp"), "{error}");
        let missing =
            pixels(&media_fixtures().join("absent.png")).expect_err("a missing file is refused");
        assert!(missing.to_string().contains("absent.png"), "{missing}");
    }
}
