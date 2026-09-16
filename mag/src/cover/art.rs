use std::path::Path;

use anyhow::Result;

use crate::critic::metrics::{decode_rgb, round_half_even, Rgb};

pub struct Zone {
    pub mean: f64,
    pub stddev: f64,
}

fn grey(pixel: &[u8]) -> u8 {
    let value = u32::from(pixel[0]) * 299 + u32::from(pixel[1]) * 587 + u32::from(pixel[2]) * 114;
    ((value + 500) / 1000).min(255) as u8
}

fn crop(image: &Rgb, x0: u32, y0: u32, x1: u32, y1: u32) -> Rgb {
    let width = x1 - x0;
    let height = y1 - y0;
    let row_bytes = width as usize * 3;
    let mut data = Vec::with_capacity(row_bytes * height as usize);
    for row in y0..y1 {
        let start = (row as usize * image.width as usize + x0 as usize) * 3;
        data.extend_from_slice(&image.data[start..start + row_bytes]);
    }
    Rgb {
        width,
        height,
        data,
    }
}

fn zone(image: &Rgb, y0: u32, y1: u32) -> Zone {
    let patch = crop(image, 0, y0, image.width, y1);
    let count = patch.width as usize * patch.height as usize;
    if count == 0 {
        return Zone {
            mean: 0.0,
            stddev: 0.0,
        };
    }
    let mut sum = 0u64;
    let mut sum_squares = 0u64;
    for pixel in patch.data.chunks_exact(3) {
        let value = u64::from(grey(pixel));
        sum += value;
        sum_squares += value * value;
    }
    let total = count as f64;
    let mean = sum as f64 / total;
    let variance = (sum_squares as f64 / total) - mean * mean;
    Zone {
        mean,
        stddev: variance.max(0.0).sqrt(),
    }
}

pub fn art_zones(path: &Path, band_x: f64, page_height: f64) -> Result<(Zone, Zone)> {
    let image = decode_rgb(path)?;
    let ratio = (band_x / f64::from(image.width)).max(page_height / f64::from(image.height));
    let width = (band_x / ratio) as u32;
    let height = (page_height / ratio) as u32;
    let ox = (image.width - width) / 2;
    let oy = (image.height - height) / 2;
    let framed = crop(&image, ox, oy, ox + width, oy + height);
    let top_end = (f64::from(framed.height) * 0.24) as u32;
    let bottom_start = (f64::from(framed.height) * 0.72) as u32;
    Ok((
        zone(&framed, 0, top_end),
        zone(&framed, bottom_start, framed.height),
    ))
}

pub fn graded_art(path: &Path) -> Result<Vec<u8>> {
    let image = decode_rgb(path)?;
    let mut graded = Vec::with_capacity(image.data.len());
    for pixel in image.data.chunks_exact(3) {
        let (red, green, blue) = (
            f64::from(pixel[0]),
            f64::from(pixel[1]),
            f64::from(pixel[2]),
        );
        if blue > 120.0 && blue > red * 1.7 && blue > green * 1.7 {
            graded.push(round_half_even(red * 0.96) as u8);
            graded.push(round_half_even(green * 1.12).min(255) as u8);
            graded.push(round_half_even(blue * 0.953) as u8);
        } else if red > 170.0 && red > green * 1.8 && green > blue * 1.5 {
            graded.push(round_half_even(red * 0.916) as u8);
            graded.push(round_half_even(green * 1.146).min(255) as u8);
            graded.push((u32::from(pixel[2]) + 45).min(255) as u8);
        } else {
            graded.extend_from_slice(pixel);
        }
    }
    encode_png(&Rgb {
        width: image.width,
        height: image.height,
        data: graded,
    })
}

fn encode_png(image: &Rgb) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut out, image.width, image.height);
        encoder.set_color(png::ColorType::Rgb);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header()?;
        writer.write_image_data(&image.data)?;
    }
    Ok(out)
}
