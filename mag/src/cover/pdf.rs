use anyhow::{anyhow, Result};
use flate2::write::ZlibEncoder;
use flate2::Compression;
use lopdf::{dictionary, Dictionary, Document, Object, Stream, StringFormat};
use std::io::Write;

use super::svg::{PAGE_HEIGHT, PAGE_WIDTH};

pub struct Line {
    pub value: String,
    pub x: f64,
    pub y: f64,
    pub size: f64,
    pub horizontal_scale: f64,
    pub tracking: Option<f64>,
}

pub struct Fill {
    pub color: (f64, f64, f64),
    pub rect: (f64, f64, f64, f64),
}

pub struct Face {
    pub title: String,
    pub fills: Vec<Fill>,
    pub text: Vec<Line>,
}

pub fn fp(value: f64) -> String {
    let magnitude = value.abs();
    if magnitude <= 1e-7 {
        return "0".into();
    }
    let places = if magnitude <= 1.0 {
        6
    } else {
        (6 - magnitude.log10() as i32).clamp(0, 6) as usize
    };
    let mut text = format!("{value:.places$}");
    if places > 0 {
        while text.ends_with('0') {
            text.pop();
        }
        if text.ends_with('.') {
            text.pop();
        }
    }
    if let Some(rest) = text.strip_prefix("0.") {
        return format!(".{rest}");
    }
    if let Some(rest) = text.strip_prefix("-0.") {
        return format!("-.{rest}");
    }
    text
}

const WIN_ANSI_HIGH: [u32; 32] = [
    0x20ac, 0, 0x201a, 0x0192, 0x201e, 0x2026, 0x2020, 0x2021, 0x02c6, 0x2030, 0x0160, 0x2039,
    0x0152, 0, 0x017d, 0, 0, 0x2018, 0x2019, 0x201c, 0x201d, 0x2022, 0x2013, 0x2014, 0x02dc,
    0x2122, 0x0161, 0x203a, 0x0153, 0, 0x017e, 0x0178,
];

fn win_ansi_char(code: u8) -> Option<char> {
    match code {
        0x80..=0x9f => match WIN_ANSI_HIGH[usize::from(code - 0x80)] {
            0 => None,
            value => char::from_u32(value),
        },
        _ => Some(char::from(code)),
    }
}

fn win_ansi_code(value: char) -> Option<u8> {
    (32u8..=255).find(|code| win_ansi_char(*code) == Some(value))
}

fn escape_literal(value: &str) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    for ch in value.chars() {
        let code = win_ansi_code(ch).ok_or_else(|| {
            anyhow!("Cover text character {ch:?} is not representable in WinAnsiEncoding")
        })?;
        if matches!(code, b'(' | b')' | b'\\') {
            out.push(b'\\');
        }
        out.push(code);
    }
    Ok(out)
}

pub fn front_fills(
    tab_x: f64,
    tab_width: f64,
    overdraw: f64,
    orange: (f64, f64, f64),
) -> Vec<Fill> {
    vec![
        Fill {
            color: (1.0, 1.0, 1.0),
            rect: (0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT),
        },
        Fill {
            color: orange,
            rect: (tab_x, -overdraw, tab_width, PAGE_HEIGHT + overdraw * 2.0),
        },
    ]
}

pub fn back_fills(overdraw: f64, orange: (f64, f64, f64)) -> Vec<Fill> {
    vec![Fill {
        color: orange,
        rect: (
            -overdraw,
            -overdraw,
            PAGE_WIDTH + overdraw * 2.0,
            PAGE_HEIGHT + overdraw * 2.0,
        ),
    }]
}

fn content(face: &Face) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    for fill in &face.fills {
        let (r, g, b) = fill.color;
        let (x, y, w, h) = fill.rect;
        out.extend_from_slice(
            format!(
                "{} {} {} rg\nn {} {} {} {} re f*\n",
                fp(r),
                fp(g),
                fp(b),
                fp(x),
                fp(y),
                fp(w),
                fp(h)
            )
            .as_bytes(),
        );
    }
    out.extend_from_slice(
        format!(
            "q\n{} 0 0 {} 0 0 cm\n/Cover Do\nQ\nq\n",
            fp(PAGE_WIDTH),
            fp(PAGE_HEIGHT)
        )
        .as_bytes(),
    );
    for line in &face.text {
        out.extend_from_slice(b"BT 1 0 0 1 0 0 Tm 3 Tr 1 0 0 1 ");
        out.extend_from_slice(
            format!(
                "{} {} Tm {} Tz ",
                fp(line.x),
                fp(line.y),
                fp(line.horizontal_scale)
            )
            .as_bytes(),
        );
        if let Some(tracking) = line.tracking {
            out.extend_from_slice(format!("{} Tc ", fp(tracking)).as_bytes());
        }
        out.extend_from_slice(
            format!("/Inter {} Tf {} TL (", fp(line.size), fp(line.size * 1.2)).as_bytes(),
        );
        out.extend_from_slice(&escape_literal(&line.value)?);
        out.extend_from_slice(b") Tj T* ET\n");
    }
    out.extend_from_slice(b"Q\n");
    Ok(out)
}

fn real(value: f64) -> Object {
    Object::Real(fp(value).parse::<f32>().unwrap_or(value as f32))
}

fn deflate(bytes: &[u8]) -> Result<Vec<u8>> {
    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::default());
    encoder.write_all(bytes)?;
    Ok(encoder.finish()?)
}

fn split_pixels(pixmap: &tiny_skia::Pixmap) -> (Vec<u8>, Vec<u8>) {
    let mut rgb = Vec::with_capacity(pixmap.pixels().len() * 3);
    let mut alpha = Vec::with_capacity(pixmap.pixels().len());
    for pixel in pixmap.pixels() {
        let plain = pixel.demultiply();
        rgb.push(plain.red());
        rgb.push(plain.green());
        rgb.push(plain.blue());
        alpha.push(plain.alpha());
    }
    (rgb, alpha)
}

struct Metrics {
    widths: Vec<f64>,
    ascent: f64,
    descent: f64,
    cap_height: f64,
    bbox: [f64; 4],
}

fn font_metrics(program: &[u8]) -> Result<Metrics> {
    let face = ttf_parser::Face::parse(program, 0)
        .map_err(|error| anyhow!("Could not parse the cover text face: {error}"))?;
    let scale = 1000.0 / f64::from(face.units_per_em());
    let mut widths = Vec::with_capacity(224);
    for code in 32u8..=255 {
        let advance = win_ansi_char(code)
            .and_then(|value| face.glyph_index(value))
            .and_then(|glyph| face.glyph_hor_advance(glyph))
            .unwrap_or(0);
        widths.push(f64::from(advance) * scale);
    }
    let bbox = face.global_bounding_box();
    Ok(Metrics {
        widths,
        ascent: f64::from(face.ascender()) * scale,
        descent: f64::from(face.descender()) * scale,
        cap_height: f64::from(face.capital_height().unwrap_or(face.ascender())) * scale,
        bbox: [
            f64::from(bbox.x_min) * scale,
            f64::from(bbox.y_min) * scale,
            f64::from(bbox.x_max) * scale,
            f64::from(bbox.y_max) * scale,
        ],
    })
}

fn to_unicode() -> Vec<u8> {
    let mapped: Vec<(u8, char)> = (32u8..=255)
        .filter_map(|code| win_ansi_char(code).map(|value| (code, value)))
        .collect();
    let mut blocks = String::new();
    for chunk in mapped.chunks(100) {
        blocks.push_str(&format!("{} beginbfchar\n", chunk.len()));
        for (code, value) in chunk {
            blocks.push_str(&format!("<{:02X}> <{:04X}>\n", code, *value as u32));
        }
        blocks.push_str("endbfchar\n");
    }
    format!(
        "/CIDInit /ProcSet findresource begin\n\
         12 dict begin\nbegincmap\n\
         /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n\
         /CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n\
         1 begincodespacerange\n<00> <FF>\nendcodespacerange\n\
         {blocks}endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    )
    .into_bytes()
}

fn font_objects(document: &mut Document, program: &[u8]) -> Result<Object> {
    let Metrics {
        widths,
        ascent,
        descent,
        cap_height,
        bbox,
    } = font_metrics(program)?;
    let mut file = Stream::new(
        dictionary! { "Length1" => Object::Integer(program.len() as i64) },
        deflate(program)?,
    );
    file.dict
        .set("Filter", Object::Name(b"FlateDecode".to_vec()));
    let file_id = document.add_object(file);
    let descriptor = document.add_object(dictionary! {
        "Type" => "FontDescriptor",
        "FontName" => Object::Name(b"Inter-Regular".to_vec()),
        "Flags" => Object::Integer(4),
        "FontBBox" => Object::Array(bbox.iter().map(|v| real(*v)).collect()),
        "ItalicAngle" => Object::Integer(0),
        "Ascent" => real(ascent),
        "Descent" => real(descent),
        "CapHeight" => real(cap_height),
        "StemV" => Object::Integer(87),
        "FontFile2" => file_id,
    });
    let mut cmap = Stream::new(Dictionary::new(), deflate(&to_unicode())?);
    cmap.dict
        .set("Filter", Object::Name(b"FlateDecode".to_vec()));
    let cmap_id = document.add_object(cmap);
    Ok(document
        .add_object(dictionary! {
            "Type" => "Font",
            "Subtype" => "TrueType",
            "BaseFont" => Object::Name(b"Inter-Regular".to_vec()),
            "Encoding" => Object::Name(b"WinAnsiEncoding".to_vec()),
            "FirstChar" => Object::Integer(32),
            "LastChar" => Object::Integer(255),
            "Widths" => Object::Array(widths.iter().map(|v| real(*v)).collect()),
            "FontDescriptor" => descriptor,
            "ToUnicode" => cmap_id,
        })
        .into())
}

fn image_objects(document: &mut Document, pixmap: &tiny_skia::Pixmap) -> Result<Object> {
    let (rgb, alpha) = split_pixels(pixmap);
    let width = i64::from(pixmap.width());
    let height = i64::from(pixmap.height());
    let mut mask = Stream::new(
        dictionary! {
            "Type" => "XObject",
            "Subtype" => "Image",
            "Width" => Object::Integer(width),
            "Height" => Object::Integer(height),
            "ColorSpace" => Object::Name(b"DeviceGray".to_vec()),
            "BitsPerComponent" => Object::Integer(8),
        },
        deflate(&alpha)?,
    );
    mask.dict
        .set("Filter", Object::Name(b"FlateDecode".to_vec()));
    let mask_id = document.add_object(mask);
    let mut image = Stream::new(
        dictionary! {
            "Type" => "XObject",
            "Subtype" => "Image",
            "Width" => Object::Integer(width),
            "Height" => Object::Integer(height),
            "ColorSpace" => Object::Name(b"DeviceRGB".to_vec()),
            "BitsPerComponent" => Object::Integer(8),
            "SMask" => mask_id,
        },
        deflate(&rgb)?,
    );
    image
        .dict
        .set("Filter", Object::Name(b"FlateDecode".to_vec()));
    Ok(document.add_object(image).into())
}

pub fn write(face: &Face, pixmap: &tiny_skia::Pixmap, program: &[u8]) -> Result<Vec<u8>> {
    let mut document = Document::with_version("1.4");
    let image = image_objects(&mut document, pixmap)?;
    let font = font_objects(&mut document, program)?;
    let mut stream = Stream::new(Dictionary::new(), content(face)?);
    stream
        .compress()
        .map_err(|error| anyhow!("Could not compress the cover content stream: {error}"))?;
    let contents = document.add_object(stream);
    let pages_id = document.new_object_id();
    let page = document.add_object(dictionary! {
        "Type" => "Page",
        "Parent" => pages_id,
        "MediaBox" => Object::Array(vec![
            Object::Integer(0),
            Object::Integer(0),
            real(PAGE_WIDTH),
            real(PAGE_HEIGHT),
        ]),
        "Contents" => contents,
        "Resources" => dictionary! {
            "XObject" => dictionary! { "Cover" => image },
            "Font" => dictionary! { "Inter" => font },
            "ProcSet" => Object::Array(vec![
                Object::Name(b"PDF".to_vec()),
                Object::Name(b"Text".to_vec()),
                Object::Name(b"ImageC".to_vec()),
            ]),
        },
    });
    document.objects.insert(
        pages_id,
        Object::Dictionary(dictionary! {
            "Type" => "Pages",
            "Kids" => Object::Array(vec![page.into()]),
            "Count" => Object::Integer(1),
        }),
    );
    let info = document.add_object(dictionary! {
        "Title" => Object::String(face.title.clone().into_bytes(), StringFormat::Literal),
        "Creator" => Object::String(
            b"magazine-compiler cover pipeline".to_vec(),
            StringFormat::Literal,
        ),
    });
    let catalog = document.add_object(dictionary! {
        "Type" => "Catalog",
        "Pages" => pages_id,
    });
    document.trailer.set("Root", catalog);
    document.trailer.set("Info", info);
    let mut bytes = Vec::new();
    document
        .save_to(&mut bytes)
        .map_err(|error| anyhow!("Could not write the cover PDF: {error}"))?;
    Ok(bytes)
}
