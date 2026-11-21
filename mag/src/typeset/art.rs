use crate::model::manifest::Edition;
use anyhow::{Context, Result};
use image::codecs::jpeg::JpegEncoder;
use std::path::{Path, PathBuf};

const QUALITY: u8 = 90;
const PRINT_QUALITY: u8 = 80;
const PRINT_MAX_PX: u32 = 2480;

pub fn cap_print_pixels(path: &Path) -> Result<()> {
    let ext = path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();
    if !matches!(ext.as_str(), "png" | "jpg" | "jpeg") {
        return Ok(());
    }
    let (width, height) = image::image_dimensions(path)
        .with_context(|| format!("reading the size of {}", path.display()))?;
    if width.max(height) <= PRINT_MAX_PX {
        return Ok(());
    }
    let image = image::open(path)?.resize(
        PRINT_MAX_PX,
        PRINT_MAX_PX,
        image::imageops::FilterType::Lanczos3,
    );
    match ext.as_str() {
        "png" => image.save(path)?,
        _ => std::fs::write(path, {
            let mut bytes = Vec::new();
            JpegEncoder::new_with_quality(&mut bytes, QUALITY).encode_image(&image.to_rgb8())?;
            bytes
        })?,
    }
    Ok(())
}

pub fn print_art(mut edition: Edition, staged: &Path) -> Result<Edition> {
    let articles = edition.articles.iter_mut().flat_map(|a| {
        a.opener_art
            .as_mut()
            .map(|o| &mut o.path)
            .into_iter()
            .chain(a.tail_art.as_mut())
            .chain(a.cards.iter_mut().filter_map(|c| c.art.as_mut()))
    });
    let plates = edition.closing_plates.iter_mut().map(|p| &mut p.art_path);
    for path in edition.cover_art.iter_mut().chain(articles).chain(plates) {
        *path = jpeg_copy(path, staged)?;
    }
    Ok(edition)
}

fn jpeg_copy(path: &Path, staged: &Path) -> Result<PathBuf> {
    let print = staged.join("print");
    if path.starts_with(&print) {
        return Ok(path.to_path_buf());
    }
    let relative = path.strip_prefix(staged).unwrap_or(path);
    let out = print.join(format!("{}.jpg", relative.display()));
    if !out.is_file() {
        std::fs::create_dir_all(out.parent().context("an art copy has no parent")?)?;
        std::fs::write(&out, encoded(path, PRINT_QUALITY)?)?;
    }
    Ok(out)
}

fn encoded(path: &Path, quality: u8) -> Result<Vec<u8>> {
    let image = image::open(path)
        .with_context(|| format!("decoding {}", path.display()))?
        .to_rgb8();
    let mut bytes = Vec::new();
    JpegEncoder::new_with_quality(&mut bytes, quality).encode_image(&image)?;
    Ok(bytes)
}

pub fn jpeg_bytes(path: &Path) -> Result<Vec<u8>> {
    encoded(path, QUALITY)
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
    fn a_staged_image_past_full_page_print_size_shrinks_to_it() {
        let dir = std::env::temp_dir().join(format!("mag-cap-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let (big, small) = (dir.join("big.png"), dir.join("small.png"));
        image::RgbImage::new(3840, 2160).save(&big).unwrap();
        image::RgbImage::new(1200, 800).save(&small).unwrap();
        cap_print_pixels(&big).unwrap();
        cap_print_pixels(&small).unwrap();
        assert_eq!(image::image_dimensions(&big).unwrap(), (2480, 1395));
        assert_eq!(image::image_dimensions(&small).unwrap(), (1200, 800));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn art_gets_one_print_jpeg_copy() {
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
