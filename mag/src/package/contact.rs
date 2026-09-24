use std::path::{Path, PathBuf};

use anyhow::Result;

use crate::critic::metrics::{decode_rgb, round_half_even, Rgb};
use crate::critic::rules::write_png;

const CONTACT_COLUMNS: u32 = 4;
const CONTACT_ROWS: u32 = 4;
const THUMBNAIL_WIDTH: u32 = 260;
const LABEL_HEIGHT: u32 = 24;
const BACKGROUND: [u8; 3] = [0xe8, 0xe7, 0xe2];
const INK: [u8; 3] = [0x27, 0x25, 0x28];
const PRECISION_BITS: u32 = 32 - 8 - 2;
const BICUBIC_SUPPORT: f64 = 2.0;
const GLYPH_TOP: u32 = 2;
const DIGIT_START: u32 = 27;
const DIGIT_ADVANCE: u32 = 6;
const GLYPHS: &str = include_str!("label_glyphs.txt");

fn bicubic(x: f64) -> f64 {
    let a = -0.5;
    let x = x.abs();
    if x < 1.0 {
        ((a + 2.0) * x - (a + 3.0)) * x * x + 1.0
    } else if x < 2.0 {
        (((x - 5.0) * x + 8.0) * x - 4.0) * a
    } else {
        0.0
    }
}

struct Coeffs {
    ksize: usize,
    bounds: Vec<(usize, usize)>,
    kk: Vec<i32>,
}

fn coeffs(in_size: u32, in0: f32, in1: f32, out_size: u32) -> Coeffs {
    let scale = f64::from(in1 - in0) / f64::from(out_size);
    let in0 = f64::from(in0);
    let filterscale = scale.max(1.0);
    let support = BICUBIC_SUPPORT * filterscale;
    let ksize = support.ceil() as usize * 2 + 1;
    let mut bounds = vec![];
    let mut kk = vec![0i32; out_size as usize * ksize];
    let step = 1.0 / filterscale;
    for xx in 0..out_size as usize {
        let center = in0 + (xx as f64 + 0.5) * scale;
        let xmin = ((center - support + 0.5) as i32).max(0);
        let xmax = ((center + support + 0.5) as i32).min(in_size as i32) - xmin;
        let weights: Vec<f64> = (0..xmax)
            .map(|x| bicubic((f64::from(x + xmin) - center + 0.5) * step))
            .collect();
        let total: f64 = weights.iter().sum();
        for (slot, weight) in kk[xx * ksize..].iter_mut().zip(&weights) {
            let normal = if total == 0.0 {
                *weight
            } else {
                weight / total
            };
            let scaled = normal * f64::from(1u32 << PRECISION_BITS);
            *slot = if normal < 0.0 {
                (-0.5 + scaled) as i32
            } else {
                (0.5 + scaled) as i32
            };
        }
        bounds.push((xmin as usize, xmax as usize));
    }
    Coeffs { ksize, bounds, kk }
}

fn convolve(
    source: &Rgb,
    coeffs: &Coeffs,
    horizontal: bool,
    offset: usize,
    out: (u32, u32),
) -> Rgb {
    let mut data = Vec::with_capacity(out.0 as usize * out.1 as usize * 3);
    for yy in 0..out.1 as usize {
        for xx in 0..out.0 as usize {
            let (along, fixed) = if horizontal {
                (xx, yy + offset)
            } else {
                (yy, xx)
            };
            let (start, count) = coeffs.bounds[along];
            let weights = &coeffs.kk[along * coeffs.ksize..along * coeffs.ksize + count];
            let mut acc = [1i32 << (PRECISION_BITS - 1); 3];
            for (step, weight) in weights.iter().enumerate() {
                let (x, y) = if horizontal {
                    (start + step, fixed)
                } else {
                    (fixed, start + step)
                };
                let pixel = (y * source.width as usize + x) * 3;
                for (channel, slot) in acc.iter_mut().enumerate() {
                    *slot += i32::from(source.data[pixel + channel]) * weight;
                }
            }
            data.extend(acc.map(|value| (value >> PRECISION_BITS).clamp(0, 255) as u8));
        }
    }
    Rgb {
        width: out.0,
        height: out.1,
        data,
    }
}

fn resize(source: &Rgb, size: (u32, u32), area: [f32; 4]) -> Rgb {
    let horizontal = coeffs(source.width, area[0], area[2], size.0);
    let mut vertical = coeffs(source.height, area[1], area[3], size.1);
    let mut current = source.clone();
    if size.0 != source.width || area[0] != 0.0 || area[2] != size.0 as f32 {
        let first = vertical.bounds[0].0;
        let last = vertical.bounds[size.1 as usize - 1];
        vertical
            .bounds
            .iter_mut()
            .for_each(|bound| bound.0 -= first);
        let rows = (last.0 + last.1 - first) as u32;
        current = convolve(source, &horizontal, true, first, (size.0, rows));
    }
    if size.1 != source.height || area[1] != 0.0 || area[3] != size.1 as f32 {
        current = convolve(&current, &vertical, false, 0, (current.width, size.1));
    }
    current
}

fn fit(image: &Rgb, size: (u32, u32)) -> Rgb {
    let (width, height) = (f64::from(image.width), f64::from(image.height));
    let output_ratio = f64::from(size.0) / f64::from(size.1);
    let (crop_width, crop_height) = if width / height == output_ratio {
        (width, height)
    } else if width / height >= output_ratio {
        (output_ratio * height, height)
    } else {
        (width, width / output_ratio)
    };
    let left = (width - crop_width) * 0.5;
    let top = (height - crop_height) * 0.5;
    resize(
        image,
        size,
        [left, top, left + crop_width, top + crop_height].map(|value| value as f32),
    )
}

fn glyph(key: &str) -> (u32, Vec<u8>) {
    GLYPHS
        .lines()
        .find_map(|line| {
            let mut fields = line.split(' ');
            (fields.next() == Some(key)).then(|| {
                let width = fields.next().and_then(|w| w.parse().ok()).unwrap_or(0);
                let hex = fields.next().unwrap_or("");
                let bytes = (0..hex.len() / 2)
                    .map(|i| u8::from_str_radix(&hex[i * 2..i * 2 + 2], 16).unwrap_or(0))
                    .collect();
                (width, bytes)
            })
        })
        .unwrap_or_default()
}

fn draw_mask(sheet: &mut Rgb, origin: (u32, u32), mask: &(u32, Vec<u8>)) {
    for (index, alpha) in mask.1.iter().enumerate() {
        let x = origin.0 + index as u32 % mask.0;
        let y = origin.1 + GLYPH_TOP + index as u32 / mask.0;
        if x >= sheet.width || y >= sheet.height {
            continue;
        }
        let pixel = (y as usize * sheet.width as usize + x as usize) * 3;
        for (channel, ink) in INK.iter().enumerate() {
            let blended = u32::from(sheet.data[pixel + channel]) * (255 - u32::from(*alpha))
                + u32::from(*ink) * u32::from(*alpha)
                + 128;
            sheet.data[pixel + channel] = (((blended >> 8) + blended) >> 8) as u8;
        }
    }
}

fn label(sheet: &mut Rgb, origin: (u32, u32), page: usize) {
    draw_mask(sheet, origin, &glyph("prefix"));
    for (index, digit) in format!("{page:03}").chars().enumerate() {
        let x = origin.0 + DIGIT_START + DIGIT_ADVANCE * index as u32;
        let mask = glyph(&digit.to_string());
        draw_mask(sheet, (x, origin.1), &mask);
    }
}

fn paste(sheet: &mut Rgb, tile: &Rgb, origin: (u32, u32)) {
    for y in 0..tile.height {
        let from = (y * tile.width * 3) as usize;
        let to = (((origin.1 + y) * sheet.width + origin.0) * 3) as usize;
        sheet.data[to..to + tile.width as usize * 3]
            .copy_from_slice(&tile.data[from..from + tile.width as usize * 3]);
    }
}

pub fn write_contact_sheets(
    pages: &[PathBuf],
    destination: &Path,
    prefix: &str,
) -> Result<Vec<PathBuf>> {
    let Some(first) = pages.first() else {
        return Ok(vec![]);
    };
    let first = decode_rgb(first)?;
    let ratio = f64::from(first.height) / f64::from(first.width);
    let thumb_height = round_half_even(f64::from(THUMBNAIL_WIDTH) * ratio) as u32;
    let cell_height = thumb_height + LABEL_HEIGHT;
    let per_sheet = (CONTACT_COLUMNS * CONTACT_ROWS) as usize;
    let mut outputs = vec![];
    for (sheet_index, chunk) in pages.chunks(per_sheet).enumerate() {
        let (width, height) = (
            CONTACT_COLUMNS * THUMBNAIL_WIDTH,
            CONTACT_ROWS * cell_height,
        );
        let mut sheet = Rgb {
            width,
            height,
            data: BACKGROUND.repeat(width as usize * height as usize),
        };
        for (offset, page) in chunk.iter().enumerate() {
            let x = offset as u32 % CONTACT_COLUMNS * THUMBNAIL_WIDTH;
            let y = offset as u32 / CONTACT_COLUMNS * cell_height;
            paste(
                &mut sheet,
                &fit(&decode_rgb(page)?, (THUMBNAIL_WIDTH, thumb_height)),
                (x, y),
            );
            label(
                &mut sheet,
                (x + 7, y + thumb_height + 5),
                sheet_index * per_sheet + offset + 1,
            );
        }
        let output = destination.join(format!("{prefix}-{:02}.png", sheet_index + 1));
        write_png(&output, &sheet)?;
        outputs.push(output);
    }
    Ok(outputs)
}
