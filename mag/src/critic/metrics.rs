use anyhow::{bail, Context, Result};
use std::path::Path;

pub const MIN_PRINT_CONTRAST_RATIO: f64 = 2.0;
pub const MIN_MARK_PIXEL_RATIO: f64 = 0.001;
pub const MAX_PRINT_CONTRAST_ENHANCEMENT: f64 = 3.0;

const ANALYSIS_MAX_SIZE: (u32, u32) = (512, 512);
const CONTRAST_FACTORS: [f64; 5] = [1.4, 1.8, 2.2, 2.6, MAX_PRINT_CONTRAST_ENHANCEMENT];
const PAPER_CONTRAST_TOLERANCE: f64 = 1.08;
const MARK_CONTRAST_THRESHOLD: f64 = 1.30;
const MIN_BACKGROUND_LUMINANCE: f64 = 0.60;
const MIN_BACKGROUND_MODE_RATIO: f64 = 0.18;
const MAX_ENHANCEABLE_TINT_RATIO: f64 = 0.05;

const PRECISION_BITS: u32 = 32 - 8 - 2;
const LANCZOS_SUPPORT: f64 = 3.0;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PrintContrastAnalysis {
    pub paper_pixel_ratio: f64,
    pub mark_pixel_ratio: f64,
    pub minimum_mark_contrast_ratio: f64,
    pub needs_treatment: bool,
}

#[derive(Debug, Clone)]
pub struct PreparedPrintImage {
    pub adjusted: bool,
    pub before: PrintContrastAnalysis,
    pub after: PrintContrastAnalysis,
    pub image: Option<Rgb>,
}

impl PreparedPrintImage {
    pub fn unresolved(&self) -> bool {
        self.after.needs_treatment
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Rgb {
    pub width: u32,
    pub height: u32,
    pub data: Vec<u8>,
}

impl Rgb {
    fn pixels(&self) -> usize {
        (self.width as usize) * (self.height as usize)
    }
}

fn srgb_linear_table() -> [f64; 256] {
    let mut table = [0.0f64; 256];
    for (value, slot) in table.iter_mut().enumerate() {
        let channel = value as f64 / 255.0;
        *slot = if channel <= 0.04045 {
            channel / 12.92
        } else {
            ((channel + 0.055) / 1.055).powf(2.4)
        };
    }
    table
}

fn relative_luminance(table: &[f64; 256], pixel: &[u8]) -> f64 {
    0.2126 * table[pixel[0] as usize]
        + 0.7152 * table[pixel[1] as usize]
        + 0.0722 * table[pixel[2] as usize]
}

pub fn round_half_even(value: f64) -> i64 {
    let floor = value.floor();
    let diff = value - floor;
    let mut result = floor as i64;
    if diff > 0.5 || (diff == 0.5 && result % 2 != 0) {
        result += 1;
    }
    result
}

pub fn round_places(value: f64, places: usize) -> f64 {
    format!("{value:.places$}").parse().unwrap_or(value)
}

fn exif_orientation(blob: &[u8]) -> Option<u16> {
    let little = match blob.get(0..2)? {
        b"II" => true,
        b"MM" => false,
        _ => return None,
    };
    let short = |at: usize| -> Option<u16> {
        let bytes: [u8; 2] = blob.get(at..at + 2)?.try_into().ok()?;
        Some(if little {
            u16::from_le_bytes(bytes)
        } else {
            u16::from_be_bytes(bytes)
        })
    };
    let long = |at: usize| -> Option<u32> {
        let bytes: [u8; 4] = blob.get(at..at + 4)?.try_into().ok()?;
        Some(if little {
            u32::from_le_bytes(bytes)
        } else {
            u32::from_be_bytes(bytes)
        })
    };
    if short(2)? != 42 {
        return None;
    }
    let directory = long(4)? as usize;
    let entries = short(directory)? as usize;
    (0..entries).find_map(|index| {
        let entry = directory.checked_add(2 + index * 12)?;
        (short(entry)? == 274).then(|| short(entry + 8))?
    })
}

pub fn decode_rgb(path: &Path) -> Result<Rgb> {
    let file = std::fs::File::open(path)
        .with_context(|| format!("cannot open image {}", path.display()))?;
    let mut decoder = png::Decoder::new(std::io::BufReader::new(file));
    decoder.set_transformations(png::Transformations::EXPAND);
    let mut reader = decoder
        .read_info()
        .with_context(|| format!("cannot read png header {}", path.display()))?;
    if let Some(orientation) = reader
        .info()
        .exif_metadata
        .as_deref()
        .and_then(exif_orientation)
    {
        if orientation != 1 {
            bail!(
                "unsupported exif orientation {orientation} in {}: orientation handling not ported",
                path.display()
            );
        }
    }
    let mut buffer = vec![0; reader.output_buffer_size().unwrap_or(0)];
    let frame = reader
        .next_frame(&mut buffer)
        .with_context(|| format!("cannot decode png {}", path.display()))?;
    if frame.bit_depth != png::BitDepth::Eight {
        bail!(
            "unsupported png bit depth {:?} in {}",
            frame.bit_depth,
            path.display()
        );
    }
    let raw = &buffer[..frame.buffer_size()];
    let data = match frame.color_type {
        png::ColorType::Rgb => raw.to_vec(),
        png::ColorType::Rgba => raw
            .chunks_exact(4)
            .flat_map(|p| [p[0], p[1], p[2]])
            .collect(),
        png::ColorType::Grayscale => raw.iter().flat_map(|&g| [g, g, g]).collect(),
        png::ColorType::GrayscaleAlpha => raw
            .chunks_exact(2)
            .flat_map(|p| [p[0], p[0], p[0]])
            .collect(),
        other => bail!(
            "unsupported png color type {:?} in {}",
            other,
            path.display()
        ),
    };
    Ok(Rgb {
        width: frame.width,
        height: frame.height,
        data,
    })
}

fn round_aspect(number: f64, key: impl Fn(i64) -> f64) -> u32 {
    let low = number.floor() as i64;
    let high = number.ceil() as i64;
    let best = if key(low) <= key(high) { low } else { high };
    best.max(1) as u32
}

fn thumbnail_size(width: u32, height: u32) -> Option<(u32, u32)> {
    let (mut x, mut y) = ANALYSIS_MAX_SIZE;
    if x >= width && y >= height {
        return None;
    }
    let aspect = width as f64 / height as f64;
    if x as f64 / y as f64 >= aspect {
        x = round_aspect(y as f64 * aspect, |n| (aspect - n as f64 / y as f64).abs());
    } else {
        y = round_aspect(x as f64 / aspect, |n| {
            if n == 0 {
                0.0
            } else {
                (aspect - x as f64 / n as f64).abs()
            }
        });
    }
    Some((x, y))
}

struct Coeffs {
    ksize: usize,
    bounds: Vec<(i32, i32)>,
    kk: Vec<i32>,
}

fn sinc(x: f64) -> f64 {
    if x == 0.0 {
        return 1.0;
    }
    let scaled = x * std::f64::consts::PI;
    scaled.sin() / scaled
}

fn lanczos(x: f64) -> f64 {
    if (-LANCZOS_SUPPORT..LANCZOS_SUPPORT).contains(&x) {
        sinc(x) * sinc(x / LANCZOS_SUPPORT)
    } else {
        0.0
    }
}

fn precompute_coeffs(in_size: u32, in0: f64, in1: f64, out_size: u32) -> Coeffs {
    let scale = (in1 - in0) / out_size as f64;
    let filterscale = scale.max(1.0);
    let support = LANCZOS_SUPPORT * filterscale;
    let ksize = (support.ceil() as usize) * 2 + 1;
    let mut bounds = Vec::with_capacity(out_size as usize);
    let mut kk = vec![0i32; out_size as usize * ksize];
    let mut window = vec![0f64; ksize];
    for xx in 0..out_size {
        let center = in0 + (xx as f64 + 0.5) * scale;
        let step = 1.0 / filterscale;
        let mut xmin = (center - support + 0.5) as i32;
        if xmin < 0 {
            xmin = 0;
        }
        let mut xmax = (center + support + 0.5) as i32;
        if xmax > in_size as i32 {
            xmax = in_size as i32;
        }
        xmax -= xmin;
        let mut total = 0.0;
        for (x, slot) in window.iter_mut().enumerate().take(xmax as usize) {
            let weight = lanczos(((x as i32 + xmin) as f64 - center + 0.5) * step);
            *slot = weight;
            total += weight;
        }
        for slot in window.iter_mut().take(xmax as usize) {
            if total != 0.0 {
                *slot /= total;
            }
        }
        for slot in window.iter_mut().skip(xmax as usize) {
            *slot = 0.0;
        }
        let base = xx as usize * ksize;
        for (offset, &weight) in window.iter().enumerate() {
            let scaled = weight * (1i64 << PRECISION_BITS) as f64;
            kk[base + offset] = if weight < 0.0 {
                (-0.5 + scaled) as i32
            } else {
                (0.5 + scaled) as i32
            };
        }
        bounds.push((xmin, xmax));
    }
    Coeffs { ksize, bounds, kk }
}

fn clip8(value: i32) -> u8 {
    let shifted = value >> PRECISION_BITS;
    shifted.clamp(0, 255) as u8
}

fn resample_horizontal(
    source: &Rgb,
    out_width: u32,
    offset: u32,
    rows: u32,
    coeffs: &Coeffs,
) -> Rgb {
    let mut data = vec![0u8; out_width as usize * rows as usize * 3];
    for yy in 0..rows as usize {
        let row = (yy + offset as usize) * source.width as usize * 3;
        for xx in 0..out_width as usize {
            let (xmin, xmax) = coeffs.bounds[xx];
            let base = xx * coeffs.ksize;
            let mut acc = [1i32 << (PRECISION_BITS - 1); 3];
            for x in 0..xmax as usize {
                let weight = coeffs.kk[base + x];
                let pixel = row + (x + xmin as usize) * 3;
                for (channel, slot) in acc.iter_mut().enumerate() {
                    *slot += source.data[pixel + channel] as i32 * weight;
                }
            }
            let target = (yy * out_width as usize + xx) * 3;
            for channel in 0..3 {
                data[target + channel] = clip8(acc[channel]);
            }
        }
    }
    Rgb {
        width: out_width,
        height: rows,
        data,
    }
}

fn resample_vertical(source: &Rgb, out_height: u32, coeffs: &Coeffs) -> Rgb {
    let mut data = vec![0u8; source.width as usize * out_height as usize * 3];
    for yy in 0..out_height as usize {
        let (ymin, ymax) = coeffs.bounds[yy];
        let base = yy * coeffs.ksize;
        for xx in 0..source.width as usize {
            let mut acc = [1i32 << (PRECISION_BITS - 1); 3];
            for y in 0..ymax as usize {
                let weight = coeffs.kk[base + y];
                let pixel = ((y + ymin as usize) * source.width as usize + xx) * 3;
                for (channel, slot) in acc.iter_mut().enumerate() {
                    *slot += source.data[pixel + channel] as i32 * weight;
                }
            }
            let target = (yy * source.width as usize + xx) * 3;
            for channel in 0..3 {
                data[target + channel] = clip8(acc[channel]);
            }
        }
    }
    Rgb {
        width: source.width,
        height: out_height,
        data,
    }
}

fn division_multiplier(divider: u32) -> u32 {
    let max_dividend = (1u64 << 8) * divider as u64;
    let max_int = (1u64 << 30) as f32 * 4.0;
    (max_int / max_dividend as f32) as u32
}

fn block_average(source: &Rgb, origin: (u32, u32), span: (u32, u32)) -> [u8; 3] {
    let scale = span.0 * span.1;
    let multiplier = division_multiplier(scale) as u64;
    let mut acc = [(scale / 2) as u64; 3];
    for yy in origin.1..origin.1 + span.1 {
        for xx in origin.0..origin.0 + span.0 {
            let pixel = (yy as usize * source.width as usize + xx as usize) * 3;
            for (channel, slot) in acc.iter_mut().enumerate() {
                *slot += source.data[pixel + channel] as u64;
            }
        }
    }
    [
        ((acc[0] * multiplier) >> 24) as u8,
        ((acc[1] * multiplier) >> 24) as u8,
        ((acc[2] * multiplier) >> 24) as u8,
    ]
}

fn reduce(source: &Rgb, factor: (u32, u32)) -> Rgb {
    let (fx, fy) = factor;
    let width = source.width.div_ceil(fx);
    let height = source.height.div_ceil(fy);
    let (full_x, full_y) = (source.width / fx, source.height / fy);
    let (rest_x, rest_y) = (source.width % fx, source.height % fy);
    let mut data = vec![0u8; width as usize * height as usize * 3];
    let mut put = |x: u32, y: u32, value: [u8; 3]| {
        let target = (y as usize * width as usize + x as usize) * 3;
        data[target..target + 3].copy_from_slice(&value);
    };
    for y in 0..full_y {
        for x in 0..full_x {
            put(x, y, block_average(source, (x * fx, y * fy), (fx, fy)));
        }
        if rest_x > 0 {
            put(
                full_x,
                y,
                block_average(source, (full_x * fx, y * fy), (rest_x, fy)),
            );
        }
    }
    if rest_y > 0 {
        for x in 0..full_x {
            put(
                x,
                full_y,
                block_average(source, (x * fx, full_y * fy), (fx, rest_y)),
            );
        }
        if rest_x > 0 {
            put(
                full_x,
                full_y,
                block_average(source, (full_x * fx, full_y * fy), (rest_x, rest_y)),
            );
        }
    }
    Rgb {
        width,
        height,
        data,
    }
}

fn resize(source: &Rgb, size: (u32, u32), box_rect: (f64, f64, f64, f64)) -> Rgb {
    let (width, height) = size;
    let horizontal = precompute_coeffs(source.width, box_rect.0, box_rect.2, width);
    let mut vertical = precompute_coeffs(source.height, box_rect.1, box_rect.3, height);
    let first = vertical.bounds[0].0;
    let last = vertical.bounds[height as usize - 1];
    let rows = (last.0 + last.1 - first) as u32;
    let mut current = source.clone();
    if width != source.width {
        for bound in vertical.bounds.iter_mut() {
            bound.0 -= first;
        }
        current = resample_horizontal(source, width, first as u32, rows, &horizontal);
    }
    if height != current.height {
        current = resample_vertical(&current, height, &vertical);
    }
    current
}

fn reducing_factor(length: u32, target: u32) -> u32 {
    let factor = (length as f64 / target as f64 / 2.0) as u32;
    factor.max(1)
}

pub fn thumbnail(image: &Rgb) -> Rgb {
    let Some((width, height)) = thumbnail_size(image.width, image.height) else {
        return image.clone();
    };
    if (width, height) == (image.width, image.height) {
        return image.clone();
    }
    let mut current = image.clone();
    let mut box_rect = (0.0, 0.0, current.width as f64, current.height as f64);
    let factor = (
        reducing_factor(image.width, width),
        reducing_factor(image.height, height),
    );
    if factor.0 > 1 || factor.1 > 1 {
        current = reduce(&current, factor);
        box_rect = (
            0.0,
            0.0,
            image.width as f64 / factor.0 as f64,
            image.height as f64 / factor.1 as f64,
        );
    }
    resize(&current, (width, height), box_rect)
}

fn estimate_background_luminance(luminances: &[f64]) -> f64 {
    let total = luminances.len();
    let mut histogram = [0usize; 101];
    for &luminance in luminances {
        histogram[round_half_even(luminance * 100.0) as usize] += 1;
    }
    let neighborhood = |bin: usize| -> usize {
        let mut mass = histogram[bin];
        if bin > 0 {
            mass += histogram[bin - 1];
        }
        if bin < 100 {
            mass += histogram[bin + 1];
        }
        mass
    };
    let floor_bin = round_half_even(MIN_BACKGROUND_LUMINANCE * 100.0) as usize;
    let dominant = (floor_bin..=100).map(neighborhood).max().unwrap_or(0);
    if (dominant as f64) / (total as f64) < MIN_BACKGROUND_MODE_RATIO {
        return 1.0;
    }
    let required = (MIN_BACKGROUND_MODE_RATIO * total as f64).max(dominant as f64 / 2.0);
    for bin in (floor_bin..=100).rev() {
        if neighborhood(bin) as f64 >= required {
            let low = bin.saturating_sub(1);
            let high = (bin + 1).min(100);
            let weighted: f64 = (low..=high)
                .map(|b| histogram[b] as f64 * (b as f64 / 100.0))
                .sum();
            let mass: f64 = (low..=high).map(|b| histogram[b] as f64).sum();
            return weighted / mass;
        }
    }
    1.0
}

pub fn analyze_print_contrast(source: &Rgb) -> PrintContrastAnalysis {
    let image = thumbnail(source);
    let total = image.pixels();
    if total == 0 {
        return PrintContrastAnalysis {
            paper_pixel_ratio: 0.0,
            mark_pixel_ratio: 0.0,
            minimum_mark_contrast_ratio: 21.0,
            needs_treatment: false,
        };
    }
    let table = srgb_linear_table();
    let luminances: Vec<f64> = image
        .data
        .chunks_exact(3)
        .map(|pixel| relative_luminance(&table, pixel))
        .collect();
    let background = estimate_background_luminance(&luminances);
    let mut paper_pixels = 0usize;
    let mut mark_contrasts: Vec<f64> = Vec::new();
    for luminance in &luminances {
        let contrast = (background + 0.05) / (luminance + 0.05);
        if contrast <= PAPER_CONTRAST_TOLERANCE {
            paper_pixels += 1;
        } else if contrast >= MARK_CONTRAST_THRESHOLD {
            mark_contrasts.push(contrast);
        }
    }
    mark_contrasts.sort_by(|a, b| a.partial_cmp(b).expect("contrast ratios are finite"));
    let mark_ratio = mark_contrasts.len() as f64 / total as f64;
    let contrast = if mark_contrasts.is_empty() {
        21.0
    } else {
        mark_contrasts[mark_contrasts.len() / 2]
    };
    let paper_ratio = paper_pixels as f64 / total as f64;
    PrintContrastAnalysis {
        paper_pixel_ratio: round_places(paper_ratio, 6),
        mark_pixel_ratio: round_places(mark_ratio, 6),
        minimum_mark_contrast_ratio: round_places(contrast, 3),
        needs_treatment: mark_ratio >= MIN_MARK_PIXEL_RATIO && contrast < MIN_PRINT_CONTRAST_RATIO,
    }
}

pub(crate) fn luma601(pixel: &[u8]) -> u8 {
    ((pixel[0] as u32 * 19595 + pixel[1] as u32 * 38470 + pixel[2] as u32 * 7471 + 0x8000) >> 16)
        as u8
}

fn enhance_contrast(image: &Rgb, factor: f64) -> Rgb {
    let sum: u64 = image.data.chunks_exact(3).map(|p| luma601(p) as u64).sum();
    let mean = (sum as f64 / image.pixels() as f64 + 0.5) as i32;
    let data = image
        .data
        .iter()
        .map(|&channel| {
            let temp = (mean as f64 + factor * (channel as f64 - mean as f64)) as f32;
            if temp <= 0.0 {
                0
            } else if temp >= 255.0 {
                255
            } else {
                temp as u8
            }
        })
        .collect();
    Rgb {
        width: image.width,
        height: image.height,
        data,
    }
}

pub fn prepare_print_image(path: &Path) -> Result<PreparedPrintImage> {
    let image = decode_rgb(path)?;
    let before = analyze_print_contrast(&image);
    let unchanged = PreparedPrintImage {
        adjusted: false,
        before,
        after: before,
        image: None,
    };
    if !before.needs_treatment {
        return Ok(unchanged);
    }
    let tint_ratio = 1.0 - before.paper_pixel_ratio - before.mark_pixel_ratio;
    if tint_ratio >= MAX_ENHANCEABLE_TINT_RATIO {
        return Ok(unchanged);
    }
    let mut best_candidate: Option<Rgb> = None;
    let mut best_after = before;
    for factor in CONTRAST_FACTORS {
        let candidate = enhance_contrast(&image, factor);
        let candidate_after = analyze_print_contrast(&candidate);
        if candidate_after.mark_pixel_ratio < MIN_MARK_PIXEL_RATIO {
            continue;
        }
        if best_candidate.is_none()
            || candidate_after.minimum_mark_contrast_ratio > best_after.minimum_mark_contrast_ratio
        {
            best_candidate = Some(candidate);
            best_after = candidate_after;
        }
        if best_after.minimum_mark_contrast_ratio >= MIN_PRINT_CONTRAST_RATIO {
            break;
        }
    }
    if best_after.minimum_mark_contrast_ratio <= before.minimum_mark_contrast_ratio {
        return Ok(unchanged);
    }
    match best_candidate {
        None => Ok(unchanged),
        Some(candidate) => Ok(PreparedPrintImage {
            adjusted: true,
            before,
            after: best_after,
            image: Some(candidate),
        }),
    }
}

pub const MAX_WORKERS: usize = 8;

pub fn worker_count(items: usize, workers: Option<usize>) -> usize {
    match workers {
        Some(requested) => requested.min(items).max(1),
        None => items
            .min(
                std::thread::available_parallelism()
                    .map(|value| value.get())
                    .unwrap_or(1),
            )
            .clamp(1, MAX_WORKERS),
    }
}

pub fn ordered_map<T, R, F>(function: F, items: &[T], workers: Option<usize>) -> Result<Vec<R>>
where
    T: Sync,
    R: Send,
    F: Fn(&T) -> Result<R> + Sync,
{
    let count = worker_count(items.len(), workers);
    let mut slots: Vec<Option<Result<R>>> = items.iter().map(|_| None).collect();
    if count <= 1 || items.len() < 2 {
        for (slot, item) in slots.iter_mut().zip(items) {
            *slot = Some(function(item));
        }
    } else {
        let chunk = items.len().div_ceil(count);
        std::thread::scope(|scope| {
            for (index, group) in slots.chunks_mut(chunk).enumerate() {
                let source = &items[index * chunk..index * chunk + group.len()];
                let call = &function;
                scope.spawn(move || {
                    for (slot, item) in group.iter_mut().zip(source) {
                        *slot = Some(call(item));
                    }
                });
            }
        });
    }
    let mut results = Vec::with_capacity(slots.len());
    for slot in slots {
        results.push(slot.expect("every slot is filled")?);
    }
    Ok(results)
}

#[cfg(test)]
mod exif_tests {
    use super::exif_orientation;

    fn tiff(value: u16) -> Vec<u8> {
        let mut out = b"II".to_vec();
        out.extend_from_slice(&42u16.to_le_bytes());
        out.extend_from_slice(&8u32.to_le_bytes());
        out.extend_from_slice(&1u16.to_le_bytes());
        out.extend_from_slice(&274u16.to_le_bytes());
        out.extend_from_slice(&3u16.to_le_bytes());
        out.extend_from_slice(&1u32.to_le_bytes());
        out.extend_from_slice(&value.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u32.to_le_bytes());
        out
    }

    #[test]
    fn orientation_is_read_when_present_and_ignored_otherwise() {
        assert_eq!(exif_orientation(&tiff(6)), Some(6));
        assert_eq!(exif_orientation(&tiff(1)), Some(1));
        let mut offset_only = b"II".to_vec();
        offset_only.extend_from_slice(&42u16.to_le_bytes());
        offset_only.extend_from_slice(&8u32.to_le_bytes());
        offset_only.extend_from_slice(&1u16.to_le_bytes());
        offset_only.extend_from_slice(&34665u16.to_le_bytes());
        offset_only.extend_from_slice(&4u16.to_le_bytes());
        offset_only.extend_from_slice(&1u32.to_le_bytes());
        offset_only.extend_from_slice(&26u32.to_le_bytes());
        offset_only.extend_from_slice(&0u32.to_le_bytes());
        assert_eq!(exif_orientation(&offset_only), None);
        assert_eq!(exif_orientation(b"not exif"), None);
    }
}
