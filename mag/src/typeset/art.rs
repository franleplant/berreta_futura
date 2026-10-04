use crate::model::manifest::Edition;
use anyhow::{Context, Result};
use image::codecs::jpeg::JpegEncoder;
use std::path::{Path, PathBuf};

const QUALITY: u8 = 90;

pub fn print_art(mut edition: Edition, staged: &Path) -> Result<Edition> {
    let articles = edition.articles.iter_mut().flat_map(|a| {
        a.opener_art
            .as_mut()
            .map(|o| &mut o.path)
            .into_iter()
            .chain(a.tail_art.as_mut())
    });
    let plates = edition.closing_plates.iter_mut().map(|p| &mut p.art_path);
    for path in edition.cover_art.iter_mut().chain(articles).chain(plates) {
        *path = jpeg_copy(path, staged)?;
    }
    Ok(edition)
}

fn jpeg_copy(path: &Path, staged: &Path) -> Result<PathBuf> {
    if path.extension().is_some_and(|e| e == "jpg" || e == "jpeg") {
        return Ok(path.to_path_buf());
    }
    let relative = path.strip_prefix(staged).unwrap_or(path);
    let out = staged
        .join("print")
        .join(format!("{}.jpg", relative.display()));
    if !out.is_file() {
        write_jpeg(path, &out)?;
    }
    Ok(out)
}

pub fn jpeg_bytes(path: &Path) -> Result<Vec<u8>> {
    let image = image::open(path)
        .with_context(|| format!("decoding {}", path.display()))?
        .to_rgb8();
    let mut bytes = Vec::new();
    JpegEncoder::new_with_quality(&mut bytes, QUALITY).encode_image(&image)?;
    Ok(bytes)
}

pub fn write_jpeg(path: &Path, out: &Path) -> Result<()> {
    let bytes = jpeg_bytes(path)?;
    std::fs::create_dir_all(out.parent().context("an art copy has no parent")?)?;
    Ok(std::fs::write(out, bytes)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_png_illustration_becomes_a_smaller_jpeg_and_a_jpeg_is_left_alone() {
        let dir = std::env::temp_dir().join(format!("mag-art-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let png = dir.join("plate.png");
        image::RgbImage::from_fn(400, 300, |x, y| {
            image::Rgb([(x % 256) as u8, (y % 256) as u8, ((x * y) % 256) as u8])
        })
        .save(&png)
        .unwrap();
        let out = jpeg_copy(&png, &dir).unwrap();
        assert_eq!(out, dir.join("print/plate.png.jpg"));
        assert!(std::fs::metadata(&out).unwrap().len() < std::fs::metadata(&png).unwrap().len());
        assert_eq!(
            image::open(&out).unwrap().to_rgb8().dimensions(),
            (400, 300)
        );
        assert_eq!(jpeg_copy(&out, &dir).unwrap(), out);
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
