use anyhow::{Context, Result};
use image::codecs::jpeg::JpegEncoder;
use image::codecs::webp::WebPEncoder;
use image::imageops::FilterType;
use image::{ExtendedColorType, RgbImage};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub const WIDTHS: [u32; 3] = [800, 1200, 1600];
const FULL_MAX: u32 = 3200;
const QUALITY: u8 = 76;

#[derive(Debug, Clone)]
pub struct Image {
    pub variants: Vec<(String, u32)>,
    pub width: u32,
    pub height: u32,
}

impl Image {
    pub fn src(&self) -> &str {
        &self.variants[0].0
    }

    pub fn full(&self) -> &str {
        &self.variants[self.variants.len() - 1].0
    }

    pub fn large(&self) -> &str {
        &self.variants[self.variants.len().min(3) - 1].0
    }
}

pub fn flatten(path: &Path) -> Result<RgbImage> {
    let rgba = image::open(path)
        .with_context(|| format!("decoding {}", path.display()))?
        .to_rgba8();
    let mut rgb = RgbImage::new(rgba.width(), rgba.height());
    for (out, pixel) in rgb.pixels_mut().zip(rgba.pixels()) {
        let alpha = u32::from(pixel[3]);
        out.0 =
            [0, 1, 2].map(|c| ((u32::from(pixel[c]) * alpha + 255 * (255 - alpha)) / 255) as u8);
    }
    Ok(rgb)
}

fn jpeg(image: &RgbImage) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    JpegEncoder::new_with_quality(&mut bytes, QUALITY).encode_image(image)?;
    Ok(bytes)
}

fn webp(image: &RgbImage) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    WebPEncoder::new_lossless(&mut bytes).encode(
        image.as_raw(),
        image.width(),
        image.height(),
        ExtendedColorType::Rgb8,
    )?;
    Ok(bytes)
}

fn widths(width: u32) -> Vec<u32> {
    let full = width.min(FULL_MAX);
    let mut out: Vec<u32> = WIDTHS.into_iter().filter(|w| w * 5 < full * 4).collect();
    out.push(full);
    out
}

fn encode(path: &Path, out: &Path) -> Result<Image> {
    let source = flatten(path)?;
    let stem = hex::encode(&Sha256::digest(std::fs::read(path)?)[..8]);
    let (w, h) = source.dimensions();
    let sized: Vec<RgbImage> = widths(w)
        .into_iter()
        .map(|width| match width == w {
            true => source.clone(),
            false => {
                let height = (u64::from(h) * u64::from(width) / u64::from(w)).max(1) as u32;
                image::imageops::resize(&source, width, height, FilterType::Lanczos3)
            }
        })
        .collect();
    let first = (jpeg(&sized[0])?, webp(&sized[0])?);
    let lossless = first.1.len() < first.0.len();
    let mut variants = Vec::new();
    for (index, image) in sized.iter().enumerate() {
        let bytes = match (index, lossless) {
            (0, true) => first.1.clone(),
            (0, false) => first.0.clone(),
            (_, true) => webp(image)?,
            (_, false) => jpeg(image)?,
        };
        let name = format!(
            "img/{stem}-{}.{}",
            image.width(),
            if lossless { "webp" } else { "jpg" }
        );
        std::fs::write(out.join(&name), bytes)?;
        variants.push((name, image.width()));
    }
    Ok(Image {
        variants,
        width: sized[0].width(),
        height: sized[0].height(),
    })
}

pub fn encode_all(paths: Vec<PathBuf>, out: &Path) -> Result<BTreeMap<PathBuf, Image>> {
    std::fs::create_dir_all(out.join("img"))?;
    let threads = std::thread::available_parallelism().map_or(4, usize::from);
    let chunk = paths.len().div_ceil(threads).max(1);
    std::thread::scope(|scope| {
        let handles: Vec<_> = paths
            .chunks(chunk)
            .map(|part| {
                scope.spawn(move || {
                    part.iter()
                        .map(|path| Ok((path.clone(), encode(path, out)?)))
                        .collect::<Result<Vec<_>>>()
                })
            })
            .collect();
        let mut map = BTreeMap::new();
        for handle in handles {
            map.extend(handle.join().expect("an image thread panicked")?);
        }
        Ok(map)
    })
}

#[cfg(test)]
mod tests {
    use super::widths;

    #[test]
    fn small_images_keep_one_variant_and_large_ones_cap_at_the_full_width() {
        assert_eq!(widths(640), vec![640]);
        assert_eq!(widths(960), vec![960]);
        assert_eq!(widths(1100), vec![800, 1100]);
        assert_eq!(widths(1760), vec![800, 1200, 1760]);
        assert_eq!(widths(5000), vec![800, 1200, 1600, 3200]);
    }
}
