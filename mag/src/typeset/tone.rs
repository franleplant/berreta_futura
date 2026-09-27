use crate::critic::metrics::{decode_rgb, luma601, Rgb};
use crate::model::manifest::Edition;
use anyhow::{Context, Result};
use std::path::Path;

const DARK_BORDER: u8 = 64;
const NEAR_BORDER: i32 = 24;
const FLAT_SHARE: f64 = 0.7;
const INK: u8 = 255 - 24;
const MARGIN: usize = 12;
const WHITE: [f64; 3] = [0.95047, 1.0, 1.08883];
const TO_XYZ: [[f64; 3]; 3] = [
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
];
const TO_RGB: [[f64; 3]; 3] = [
    [3.2404542, -1.5371385, -0.4985314],
    [-0.9692660, 1.8760108, 0.0415560],
    [0.0556434, -0.2040259, 1.0572252],
];

pub fn print_figures(mut edition: Edition, staged: &Path) -> Result<Edition> {
    for figure in edition
        .articles
        .iter_mut()
        .flat_map(|a| a.figures.iter_mut())
    {
        let relative = figure.path.strip_prefix(staged).unwrap_or(&figure.path);
        let out = staged
            .join("print")
            .join(format!("{}.png", relative.display()));
        if out.is_file() || print_copy(&figure.path, &figure.tone, &out)? {
            println!("print tone: inverted {} -> {}", figure.id, out.display());
            figure.path = out;
        }
    }
    Ok(edition)
}

pub fn print_copy(path: &Path, tone: &str, out: &Path) -> Result<bool> {
    if tone == "keep" {
        return Ok(false);
    }
    let image = decode(path)?;
    if tone != "invert" && !dark_flat(&image) {
        return Ok(false);
    }
    let image = trim(&invert(&image));
    std::fs::create_dir_all(out.parent().context("a print copy has no parent")?)?;
    let file = std::io::BufWriter::new(std::fs::File::create(out)?);
    let mut encoder = png::Encoder::new(file, image.width, image.height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    encoder.write_header()?.write_image_data(&image.data)?;
    Ok(true)
}

fn decode(path: &Path) -> Result<Rgb> {
    let bytes = std::fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    if !bytes.starts_with(b"\x89PNG") {
        return decode_rgb(path);
    }
    let mut decoder = png::Decoder::new(std::io::Cursor::new(&bytes));
    decoder.set_transformations(png::Transformations::normalize_to_color8());
    let mut reader = decoder.read_info()?;
    let mut buffer = vec![0; reader.output_buffer_size().unwrap_or(0)];
    let frame = reader.next_frame(&mut buffer)?;
    let channels = frame.color_type.samples();
    let over_white = |p: &[u8]| {
        let (color, alpha) = match channels {
            1 => ([p[0]; 3], 255),
            2 => ([p[0]; 3], p[1]),
            3 => ([p[0], p[1], p[2]], 255),
            _ => ([p[0], p[1], p[2]], p[3]),
        };
        let a = u32::from(alpha);
        color.map(|c| ((u32::from(c) * a + 255 * (255 - a) + 127) / 255) as u8)
    };
    Ok(Rgb {
        width: frame.width,
        height: frame.height,
        data: buffer[..frame.buffer_size()]
            .chunks_exact(channels)
            .flat_map(over_white)
            .collect(),
    })
}

fn pixel(image: &Rgb, x: u32, y: u32) -> [u8; 3] {
    let at = 3 * (y as usize * image.width as usize + x as usize);
    [image.data[at], image.data[at + 1], image.data[at + 2]]
}

fn border(image: &Rgb) -> [u8; 3] {
    let (w, h) = (image.width, image.height);
    let mut ring: Vec<[u8; 3]> = (0..w)
        .step_by(4)
        .flat_map(|x| [pixel(image, x, 0), pixel(image, x, h - 1)])
        .chain(
            (0..h)
                .step_by(4)
                .flat_map(|y| [pixel(image, 0, y), pixel(image, w - 1, y)]),
        )
        .collect();
    [0, 1, 2].map(|c| {
        ring.sort_unstable_by_key(|p| p[c]);
        ring[ring.len() / 2][c]
    })
}

pub fn dark_flat(image: &Rgb) -> bool {
    let background = i32::from(luma601(&border(image)));
    let near = image
        .data
        .chunks_exact(3)
        .filter(|p| (i32::from(luma601(p)) - background).abs() < NEAR_BORDER)
        .count();
    background < i32::from(DARK_BORDER) && near as f64 >= FLAT_SHARE * (image.data.len() / 3) as f64
}

fn linear(c: u8) -> f64 {
    let c = f64::from(c) / 255.0;
    match c <= 0.04045 {
        true => c / 12.92,
        false => ((c + 0.055) / 1.055).powf(2.4),
    }
}

fn encoded(l: f64) -> u8 {
    let l = l.clamp(0.0, 1.0);
    let c = match l <= 0.0031308 {
        true => 12.92 * l,
        false => 1.055 * l.powf(1.0 / 2.4) - 0.055,
    };
    (c * 255.0).round() as u8
}

fn times(m: &[[f64; 3]; 3], v: [f64; 3]) -> [f64; 3] {
    m.map(|row| row[0] * v[0] + row[1] * v[1] + row[2] * v[2])
}

pub fn lab(p: [u8; 3]) -> [f64; 3] {
    let xyz = times(&TO_XYZ, p.map(linear));
    let [fx, fy, fz] = [0, 1, 2].map(|i| {
        let t = xyz[i] / WHITE[i];
        match t > 216.0 / 24389.0 {
            true => t.cbrt(),
            false => (24389.0 / 27.0 * t + 16.0) / 116.0,
        }
    });
    [116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)]
}

fn inverted_linear(p: [u8; 3]) -> [f64; 3] {
    let [l, a, b] = lab(p);
    let fy = (100.0 - l + 16.0) / 116.0;
    let f = [fy + a / 500.0, fy, fy - b / 200.0];
    let xyz = [0, 1, 2].map(|i| {
        let t = f[i].powi(3);
        WHITE[i]
            * match t > 216.0 / 24389.0 {
                true => t,
                false => (116.0 * f[i] - 16.0) * 27.0 / 24389.0,
            }
    });
    times(&TO_RGB, xyz).map(|v| v.clamp(0.0, 1.0))
}

pub fn invert(image: &Rgb) -> Rgb {
    let paper = inverted_linear(border(image)).map(|v| v.max(1e-6));
    let data = image
        .data
        .chunks_exact(3)
        .flat_map(|p| {
            let v = inverted_linear([p[0], p[1], p[2]]);
            [0, 1, 2].map(|c| encoded(v[c] / paper[c]))
        })
        .collect();
    Rgb { data, ..*image }
}

pub fn trim(image: &Rgb) -> Rgb {
    let (w, h) = (image.width as usize, image.height as usize);
    let inked = |x: usize, y: usize| pixel(image, x as u32, y as u32).iter().any(|&c| c < INK);
    let rows: Vec<usize> = (0..h).filter(|&y| (0..w).any(|x| inked(x, y))).collect();
    let cols: Vec<usize> = (0..w)
        .filter(|&x| rows.iter().any(|&y| inked(x, y)))
        .collect();
    let (Some(top), Some(bottom), Some(left), Some(right)) =
        (rows.first(), rows.last(), cols.first(), cols.last())
    else {
        return Rgb {
            data: image.data.clone(),
            ..*image
        };
    };
    let (x0, y0) = (left.saturating_sub(MARGIN), top.saturating_sub(MARGIN));
    let (x1, y1) = ((right + MARGIN + 1).min(w), (bottom + MARGIN + 1).min(h));
    let data = (y0..y1)
        .flat_map(|y| {
            image.data[3 * (y * w + x0)..3 * (y * w + x1)]
                .iter()
                .copied()
        })
        .collect();
    Rgb {
        width: (x1 - x0) as u32,
        height: (y1 - y0) as u32,
        data,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn source_media(relative: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../library/sources")
            .join(relative)
    }

    fn dark(relative: &str) -> bool {
        dark_flat(&decode(&source_media(relative)).expect("the source decodes"))
    }

    #[test]
    fn dark_screenshots_are_detected_and_light_diagrams_and_dark_photos_are_not() {
        for positive in [
            "mega-megadevhq-on-x-b8963c9d/media/001.jpg",
            "how-we-built-safety-into-muse-512c3f7f/media/001.png",
        ] {
            assert!(dark(positive), "{positive}");
        }
        for negative in [
            "ureview-scalable-trustworthy-genai-for-code-revi-296c0ee8/media/002.jpg",
            "staff-archetypes-c22d800c/media/001.png",
            "introduction-to-the-actor-model-using-real-actor-2d2aad66/media/005.jpg",
            "introduction-to-the-actor-model-using-real-actor-2d2aad66/media/008.jpg",
        ] {
            assert!(!dark(negative), "{negative}");
        }
    }

    #[test]
    fn inversion_whitens_the_ground_darkens_the_text_and_keeps_hue_signs() {
        let colours = [[10, 10, 12], [230, 230, 230], [200, 40, 40], [40, 80, 220]];
        let mut data: Vec<u8> = [10, 10, 12].repeat(400);
        for (i, colour) in colours.iter().enumerate() {
            data[3 * (210 + i)..3 * (211 + i)].copy_from_slice(colour);
        }
        let out = invert(&Rgb {
            width: 20,
            height: 20,
            data,
        });
        let at = |i: usize| [out.data[3 * i], out.data[3 * i + 1], out.data[3 * i + 2]];
        assert_eq!(at(0), [255, 255, 255]);
        assert!(luma601(&at(211)) < 60, "{:?}", at(211));
        for i in [212, 213] {
            let (before, after) = (lab(colours[i - 210]), lab(at(i)));
            assert!(
                before[1].signum() == after[1].signum() && before[2].signum() == after[2].signum()
            );
        }
    }

    #[test]
    fn the_mega_screenshot_prints_light_and_trimmed_to_its_content() {
        let source = decode(&source_media("mega-megadevhq-on-x-b8963c9d/media/001.jpg")).unwrap();
        let out = trim(&invert(&source));
        assert_eq!((source.width, source.height), (1200, 1005));
        assert!(
            (1050..1110).contains(&out.width) && (820..890).contains(&out.height),
            "{}x{}",
            out.width,
            out.height
        );
        assert!(luma601(&border(&out)) > 250);
    }
}
