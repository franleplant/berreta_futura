use anyhow::{Context, Result};
use image::codecs::jpeg::JpegEncoder;
use image::codecs::webp::WebPEncoder;
use image::imageops::FilterType;
use image::{ExtendedColorType, RgbImage};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{LazyLock, Mutex};

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

fn jpeg(image: &RgbImage, quality: u8) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    JpegEncoder::new_with_quality(&mut bytes, quality).encode_image(image)?;
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

static CODE_DIGEST: LazyLock<String> = LazyLock::new(|| {
    let mut code = include_bytes!("../../Cargo.lock").to_vec();
    code.extend_from_slice(include_bytes!("images.rs"));
    crate::util::sha256_hex(code)
});

#[derive(Serialize, Deserialize)]
struct Entry {
    width: u32,
    height: u32,
    variants: Vec<(String, u32, String)>,
}

struct Encoded {
    width: u32,
    height: u32,
    files: Vec<(String, u32, Vec<u8>)>,
}

fn cache_key(code: &str, source: &[u8], quality: u8, widths: &[u32]) -> String {
    crate::util::sha256_hex(format!(
        "{code}|{}|{quality}|jpg+webp|{widths:?}",
        crate::util::sha256_hex(source)
    ))
}

fn cached(dir: &Path) -> Option<Encoded> {
    let entry: Entry = serde_json::from_slice(&std::fs::read(dir.join("entry.json")).ok()?).ok()?;
    let files = entry
        .variants
        .into_iter()
        .map(|(name, width, sum)| {
            let bytes = std::fs::read(dir.join(name.replace('/', "_"))).ok()?;
            (crate::util::sha256_hex(&bytes) == sum).then_some((name, width, bytes))
        })
        .collect::<Option<Vec<_>>>()?;
    Some(Encoded {
        width: entry.width,
        height: entry.height,
        files,
    })
}

fn store(dir: &Path, encoded: &Encoded) -> Result<()> {
    static TEMPS: AtomicUsize = AtomicUsize::new(0);
    let tmp = dir.with_extension(format!(
        "tmp{}-{}",
        std::process::id(),
        TEMPS.fetch_add(1, Ordering::Relaxed)
    ));
    std::fs::remove_dir_all(&tmp).ok();
    std::fs::create_dir_all(&tmp)?;
    for (name, _, bytes) in &encoded.files {
        std::fs::write(tmp.join(name.replace('/', "_")), bytes)?;
    }
    let entry = Entry {
        width: encoded.width,
        height: encoded.height,
        variants: encoded
            .files
            .iter()
            .map(|(name, width, bytes)| (name.clone(), *width, crate::util::sha256_hex(bytes)))
            .collect(),
    };
    std::fs::write(tmp.join("entry.json"), serde_json::to_vec(&entry)?)?;
    std::fs::remove_dir_all(dir).ok();
    std::fs::rename(&tmp, dir).or_else(|error| {
        std::fs::remove_dir_all(&tmp).ok();
        cached(dir).map(|_| ()).ok_or(error)
    })?;
    Ok(())
}

fn encode_fresh(path: &Path, stem: &str, quality: u8) -> Result<Encoded> {
    let source = flatten(path)?;
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
    let first = (jpeg(&sized[0], quality)?, webp(&sized[0])?);
    let lossless = first.1.len() < first.0.len();
    let mut files = Vec::new();
    for (index, image) in sized.iter().enumerate() {
        let bytes = match (index, lossless) {
            (0, true) => first.1.clone(),
            (0, false) => first.0.clone(),
            (_, true) => webp(image)?,
            (_, false) => jpeg(image, quality)?,
        };
        let ext = if lossless { "webp" } else { "jpg" };
        files.push((
            format!("img/{stem}-{}.{ext}", image.width()),
            image.width(),
            bytes,
        ));
    }
    Ok(Encoded {
        width: sized[0].width(),
        height: sized[0].height(),
        files,
    })
}

fn encode(path: &Path, out: &Path, cache: &Path, quality: u8) -> Result<Image> {
    let bytes = std::fs::read(path)?;
    let stem = crate::util::sha256_hex(&bytes)[..16].to_string();
    let key = cache_key(
        &CODE_DIGEST,
        &bytes,
        quality,
        &[WIDTHS[0], WIDTHS[1], WIDTHS[2], FULL_MAX],
    );
    let dir = cache.join(&key);
    let encoded = match cached(&dir) {
        Some(hit) => hit,
        None => {
            let fresh = encode_fresh(path, &stem, quality)?;
            std::fs::create_dir_all(cache)?;
            store(&dir, &fresh).ok();
            fresh
        }
    };
    let mut variants = Vec::new();
    for (name, width, bytes) in encoded.files {
        std::fs::write(out.join(&name), bytes)?;
        variants.push((name, width));
    }
    Ok(Image {
        variants,
        width: encoded.width,
        height: encoded.height,
    })
}

pub fn encode_all(paths: &[PathBuf], out: &Path, cache: &Path) -> Result<BTreeMap<PathBuf, Image>> {
    std::fs::create_dir_all(out.join("img"))?;
    let next = AtomicUsize::new(0);
    let done = Mutex::new(Vec::new());
    let threads = std::thread::available_parallelism().map_or(4, usize::from);
    std::thread::scope(|scope| {
        for _ in 0..threads.min(paths.len()) {
            scope.spawn(|| loop {
                let index = next.fetch_add(1, Ordering::Relaxed);
                let Some(path) = paths.get(index) else { break };
                let image = encode(path, out, cache, QUALITY).map(|image| (path.clone(), image));
                done.lock().unwrap().push((index, image));
            });
        }
    });
    let mut done = done.into_inner().unwrap();
    done.sort_by_key(|(index, _)| *index);
    done.into_iter().map(|(_, image)| image).collect()
}

#[cfg(test)]
mod tests {
    use super::{cache_key, cached, encode, widths};
    use image::{Rgb, RgbImage};
    use std::path::{Path, PathBuf};

    fn scratch(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("mag-img-{name}-{}", std::process::id()));
        std::fs::remove_dir_all(&dir).ok();
        std::fs::create_dir_all(dir.join("out/img")).unwrap();
        dir
    }

    fn picture(path: &Path, seed: u8) {
        RgbImage::from_fn(1000, 700, |x, y| {
            Rgb([(x as u8).wrapping_add(seed), (y / 3) as u8, seed])
        })
        .save(path)
        .unwrap();
    }

    fn files(dir: &Path) -> Vec<(String, Vec<u8>)> {
        let mut rows: Vec<_> = std::fs::read_dir(dir)
            .unwrap()
            .map(|entry| {
                let path = entry.unwrap().path();
                (
                    path.file_name().unwrap().to_string_lossy().to_string(),
                    std::fs::read(path).unwrap(),
                )
            })
            .collect();
        rows.sort();
        rows
    }

    #[test]
    fn a_cache_hit_reproduces_a_fresh_encode_and_corruption_falls_back_to_encoding() {
        let dir = scratch("hit");
        let (source, cache, out) = (dir.join("a.png"), dir.join("cache"), dir.join("out"));
        picture(&source, 1);
        let fresh = encode(&source, &out, &cache, 76).unwrap();
        let first = files(&out.join("img"));
        let entries = || std::fs::read_dir(&cache).unwrap().count();
        assert_eq!(entries(), 1);
        std::fs::remove_dir_all(out.join("img")).unwrap();
        std::fs::create_dir_all(out.join("img")).unwrap();
        let hit = encode(&source, &out, &cache, 76).unwrap();
        assert_eq!(files(&out.join("img")), first);
        assert_eq!(hit.variants, fresh.variants);
        assert_eq!(entries(), 1);
        let entry = std::fs::read_dir(&cache)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        let victim = files(&entry)
            .into_iter()
            .find(|(n, _)| n.ends_with(".jpg") || n.ends_with(".webp"))
            .unwrap()
            .0;
        std::fs::write(entry.join(&victim), b"garbage").unwrap();
        assert!(cached(&entry).is_none());
        encode(&source, &out, &cache, 76).unwrap();
        assert_eq!(files(&out.join("img")), first);
        assert!(cached(&entry).is_some());
        std::fs::write(entry.join("entry.json"), b"{").unwrap();
        assert!(cached(&entry).is_none());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn changed_bytes_quality_or_widths_miss_the_cache() {
        let dir = scratch("miss");
        let (source, cache, out) = (dir.join("a.png"), dir.join("cache"), dir.join("out"));
        picture(&source, 1);
        encode(&source, &out, &cache, 76).unwrap();
        picture(&source, 2);
        encode(&source, &out, &cache, 76).unwrap();
        encode(&source, &out, &cache, 60).unwrap();
        assert_eq!(std::fs::read_dir(&cache).unwrap().count(), 3);
        let base = cache_key("c", b"x", 76, &[800, 1200]);
        assert_ne!(base, cache_key("c", b"y", 76, &[800, 1200]));
        assert_ne!(base, cache_key("c", b"x", 75, &[800, 1200]));
        assert_ne!(base, cache_key("c", b"x", 76, &[800, 1600]));
        assert_ne!(base, cache_key("d", b"x", 76, &[800, 1200]));
        assert_eq!(base, cache_key("c", b"x", 76, &[800, 1200]));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn small_images_keep_one_variant_and_large_ones_cap_at_the_full_width() {
        assert_eq!(widths(640), vec![640]);
        assert_eq!(widths(960), vec![960]);
        assert_eq!(widths(1100), vec![800, 1100]);
        assert_eq!(widths(1760), vec![800, 1200, 1760]);
        assert_eq!(widths(5000), vec![800, 1200, 1600, 3200]);
    }
}
