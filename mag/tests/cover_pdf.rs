#[path = "../src/critic/metrics.rs"]
pub mod metrics;
#[allow(dead_code)]
mod oracle;

mod critic {
    pub use super::metrics;
}

#[path = "../src/cover/art.rs"]
mod art;
#[path = "../src/cover/outline.rs"]
mod outline;
#[path = "../src/cover/pdf.rs"]
mod pdf;
#[path = "../src/cover/raster.rs"]
mod raster;
#[path = "../src/cover/svg.rs"]
mod svg;

use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

use pdf::{Face, Line};
use svg::{
    Art, Builder, CoverText, Deck, Design, Fonts, Footer, FooterCaption, Headline, HonoredPlate,
    Palette, Tab, Wordmark, PAGE_HEIGHT,
};

const ORANGE: (f64, f64, f64) = (240.0 / 255.0, 87.0 / 255.0, 56.0 / 255.0);

const REPORTLAB_PREAMBLE: &str = "1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET";

const BACK_OVERDRAW: f64 = 1.5;

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn design() -> Design {
    Design {
        id: "canto-vivo/1".into(),
        colors: Palette {
            paper: "#ffffff".into(),
            ink: "#0a0b0d".into(),
            orange: "#f05738".into(),
            violet: "#4b21c0".into(),
        },
        tab: Tab {
            width: 21.0,
            edge_reveal: 1.4,
            issue_top: 26.5,
            identity_top: 433.5,
            overdraw: 1.5,
        },
        wordmark: Wordmark {
            x: 38.0,
            top: 53.0,
            right_reserve: 78.0,
        },
        footer_caption: FooterCaption {
            margin: 25.0,
            wordmark_scale: 0.8,
            wordmark_dy: 6.0,
            title_size: 26.0,
        },
        headline: Headline {
            x: 44.0,
            top: 122.0,
            width: 302.0,
        },
        art: Art {
            x: 85.25,
            top: 221.85,
            width: 249.35,
            height: 248.65,
        },
        deck: Deck {
            top: 493.0,
            size: 5.5,
            wrap_size: 6.7,
            leading: 8.4,
            horizontal_scale: 108.0,
            tracking: 0.35,
        },
        footer: Footer {
            x: 44.0,
            bottom: 20.0,
            size: 7.0,
            tracking: 1.85,
        },
        honored_plate: HonoredPlate {
            margin: 17.0,
            footer: 64.0,
            wordmark_scale: 0.5,
            title_size: 19.0,
        },
    }
}

fn edition_010_text() -> CoverText {
    CoverText {
        publication_name: "Berreta Futura".into(),
        headline: "The Speed Limit".into(),
        date_line: "2026 09 13".into(),
        contributors: "FRANK RIETTA / ANTHROPIC / DARIO AMODEI / SANTI RUIZ / MICHAEL TRUELL / WILSON LIN / DEEPSEEK-AI / JON LEE, CHAOMIN YU, BEN RIES".into(),
        tab_issue: "ISSUE 010".into(),
        tab_identity: "BERRETA FUTURA / BUENOS AIRES".into(),
    }
}

fn deck_lines() -> Vec<String> {
    vec![
        "FRANK RIETTA / ANTHROPIC / DARIO AMODEI / SANTI RUIZ / MICHAEL".into(),
        "TRUELL / WILSON LIN / DEEPSEEK-AI / JON LEE, CHAOMIN YU, BEN RIES".into(),
    ]
}

fn cover_art() -> PathBuf {
    oracle::pinned(
        "cover_pdf",
        "editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png",
    )
}

fn inter() -> Vec<u8> {
    std::fs::read(repository().join("src/magazine/assets/fonts/inter/Inter-Regular.ttf"))
        .expect("the vendored Inter face is readable")
}

fn front_face(design: &Design, text: &CoverText) -> Face {
    let band_width = design.tab.width - design.tab.edge_reveal;
    let band_x = svg::PAGE_WIDTH - design.tab.width;
    let mut lines = vec![
        Line {
            value: text.publication_name.to_uppercase(),
            x: design.wordmark.x,
            y: PAGE_HEIGHT - 55.0,
            size: 22.0,
            horizontal_scale: 100.0,
            tracking: Some(0.0),
        },
        Line {
            value: text.headline.to_uppercase(),
            x: design.headline.x,
            y: PAGE_HEIGHT - 151.0,
            size: 16.0,
            horizontal_scale: 100.0,
            tracking: Some(0.0),
        },
    ];
    let baseline = design.deck.top + design.deck.size;
    for (index, line) in deck_lines().iter().enumerate() {
        lines.push(Line {
            value: line.clone(),
            x: design.art.x,
            y: PAGE_HEIGHT - (baseline + index as f64 * design.deck.leading),
            size: design.deck.size,
            horizontal_scale: design.deck.horizontal_scale,
            tracking: Some(design.deck.tracking),
        });
    }
    lines.push(Line {
        value: text.date_line.clone(),
        x: design.footer.x,
        y: design.footer.bottom,
        size: design.footer.size,
        horizontal_scale: 100.0,
        tracking: Some(design.footer.tracking),
    });
    Face {
        title: "Berreta Futura front cover".into(),
        fills: pdf::front_fills(band_x, band_width, design.tab.overdraw, ORANGE),
        text: lines,
    }
}

fn back_face() -> Face {
    let line = |value: &str, x: f64, y: f64, size: f64, horizontal_scale: f64| Line {
        value: value.into(),
        x,
        y,
        size,
        horizontal_scale,
        tracking: None,
    };
    Face {
        title: "Berreta Futura back cover".into(),
        fills: pdf::back_fills(BACK_OVERDRAW, ORANGE),
        text: vec![
            line("LOOP", 6.0, PAGE_HEIGHT - 90.0, 20.0, 100.0),
            line("CLOSED", 6.0, PAGE_HEIGHT - 170.0, 20.0, 100.0),
            line(
                "An independent anthology of writing worth keeping.",
                68.0,
                PAGE_HEIGHT - 300.0,
                10.0,
                100.0,
            ),
            line("END / 2026 09 13", 38.0, 26.0, 7.0, 100.0),
            line(
                "BERRETA FUTURA / ISSUE 010 / BUENOS AIRES",
                38.0,
                10.0,
                5.5,
                88.0,
            ),
        ],
    }
}

fn cover_pixmap(layout: &str) -> tiny_skia::Pixmap {
    let assets = repository().join("src/magazine/assets");
    let mut fonts = Fonts::load(&assets).expect("vendored cover faces load");
    let design = design();
    let document = {
        let mut builder = Builder {
            design: &design,
            fonts: &mut fonts,
        };
        builder
            .materialize(layout, &edition_010_text(), &cover_art())
            .unwrap_or_else(|error| panic!("{layout} builds: {error}"))
    };
    raster::render(&raster::raster_svg(&document, 300)).expect("cover rasterizes")
}

fn build(layout: &str) -> Vec<u8> {
    let design = design();
    pdf::write(
        &front_face(&design, &edition_010_text()),
        &cover_pixmap(layout),
        &inter(),
    )
    .expect("cover PDF writes")
}

fn page_hash(bytes: &[u8]) -> String {
    let directory = std::env::temp_dir().join(format!("wp54c-{}", std::process::id()));
    std::fs::create_dir_all(&directory).expect("scratch directory");
    let source = directory.join("cover.pdf");
    std::fs::write(&source, bytes).expect("cover PDF is written to disk");
    let status = std::process::Command::new("pdftoppm")
        .args(["-r", "72", "-png", "-singlefile"])
        .arg(&source)
        .arg(directory.join("page"))
        .status()
        .expect("pdftoppm runs");
    assert!(status.success(), "pdftoppm rasterized the cover PDF");
    let rendered = std::fs::read(directory.join("page.png")).expect("the raster exists");
    let decoder = png::Decoder::new(std::io::Cursor::new(rendered));
    let mut reader = decoder.read_info().expect("the raster is a PNG");
    let mut buffer = vec![0; reader.output_buffer_size().expect("bounded raster")];
    let info = reader.next_frame(&mut buffer).expect("the raster decodes");
    let mut hasher = Sha256::new();
    hasher.update(&buffer[..info.buffer_size()]);
    format!("{:x}", hasher.finalize())
}

fn normalize(stream: &str) -> String {
    let image = regex::Regex::new(r"/FormXob\.[0-9a-f]{32}|/Cover").expect("image name pattern");
    let font = regex::Regex::new(r"/F2\+0|/Inter").expect("font name pattern");
    let named = image.replace_all(stream, "/IMG");
    let mapped = font.replace_all(&named, "/FONT");
    let mut out = String::new();
    for line in mapped.lines() {
        let line = line.trim_end();
        if line.is_empty() || line == REPORTLAB_PREAMBLE {
            continue;
        }
        out.push_str(line);
        out.push('\n');
    }
    out
}

fn content_stream_bytes(bytes: &[u8]) -> Vec<u8> {
    let document = lopdf::Document::load_mem(bytes).expect("the cover PDF parses");
    let (_, page) = document
        .get_pages()
        .into_iter()
        .next()
        .expect("the cover PDF has a page");
    document.get_page_content(page)
}

fn content_stream(bytes: &[u8]) -> String {
    let document = lopdf::Document::load_mem(bytes).expect("the cover PDF parses");
    let (_, page) = document
        .get_pages()
        .into_iter()
        .next()
        .expect("the cover PDF has a page");
    String::from_utf8(document.get_page_content(page)).expect("the content stream is text")
}

fn metadata(bytes: &[u8], key: &str) -> String {
    let document = lopdf::Document::load_mem(bytes).expect("the cover PDF parses");
    let info = document
        .trailer
        .get(b"Info")
        .and_then(|value| document.dereference(value))
        .expect("the cover PDF carries an Info dictionary")
        .1
        .as_dict()
        .expect("Info is a dictionary")
        .get(key.as_bytes())
        .expect("the requested Info entry is present")
        .as_str()
        .expect("the Info entry is a string")
        .to_vec();
    String::from_utf8(info).expect("the Info entry is text")
}

#[test]
fn every_layout_renders_as_the_python_compiler_renders_it() {
    let mut differing = Vec::new();
    let mut compared = 0;
    for (layout, expected) in [
        (
            "framed",
            "330ae10cf0dcae7163d5389c502284d7aeb1818ed7a0503f37120adf2ef67120",
        ),
        (
            "honored_plate",
            "02d379d867f748b9efe45a98abcdd3546bb8b65e43d8b8cfbb75e2d1af82e453",
        ),
    ] {
        let actual = page_hash(&build(layout));
        compared += 1;
        if actual != expected {
            differing.push(format!("{layout}: expected {expected}, rendered {actual}"));
        }
    }
    assert_eq!(compared, 2, "every pinned layout was rendered and hashed");
    assert!(
        differing.is_empty(),
        "{} of {compared} layouts rendered differently from Python's: {}",
        differing.len(),
        differing.join("; ")
    );
}

#[test]
fn the_front_invisible_text_layer_matches_the_python_compiler() {
    let design = design();
    let bytes = pdf::write(
        &front_face(&design, &edition_010_text()),
        &cover_pixmap("footer_caption"),
        &inter(),
    )
    .expect("cover PDF writes");
    assert_eq!(
        normalize(&content_stream(&bytes)),
        include_str!("cover_pdf_front_stream_expected.txt"),
        "the front cover content stream diverged from the Python compiler's"
    );
    assert_eq!(metadata(&bytes, "Title"), "Berreta Futura front cover");
    assert_eq!(
        metadata(&bytes, "Creator"),
        "magazine-compiler cover pipeline"
    );
    let box_start = bytes
        .windows(10)
        .position(|window| window == b"/MediaBox[")
        .expect("the page carries a MediaBox");
    let box_end = box_start
        + bytes[box_start..]
            .iter()
            .position(|byte| *byte == b']')
            .expect("the MediaBox array closes");
    assert_eq!(
        std::str::from_utf8(&bytes[box_start..=box_end]).expect("the MediaBox is text"),
        "/MediaBox[0 0 419.5276 595.2756]",
        "the page box serialized differently from the Python compiler's A5 box"
    );
}

#[test]
fn the_back_invisible_text_layer_matches_the_python_compiler() {
    let bytes = pdf::write(&back_face(), &cover_pixmap("footer_caption"), &inter())
        .expect("cover PDF writes");
    assert_eq!(
        normalize(&content_stream(&bytes)),
        include_str!("cover_pdf_back_stream_expected.txt"),
        "the back cover content stream diverged from the Python compiler's"
    );
    assert_eq!(metadata(&bytes, "Title"), "Berreta Futura back cover");
}

#[test]
fn the_normalizer_only_loosens_the_python_side() {
    let design = design();
    let stream = content_stream(
        &pdf::write(
            &front_face(&design, &edition_010_text()),
            &cover_pixmap("footer_caption"),
            &inter(),
        )
        .expect("cover PDF writes"),
    );
    for reportlab_only in ["/FormXob.", "/F2+0", REPORTLAB_PREAMBLE] {
        assert!(
            !stream.contains(reportlab_only),
            "the writer emits {reportlab_only}, so normalizing it away could hide a divergence"
        );
    }
    assert_eq!(
        normalize(&stream)
            .replace("/IMG", "/Cover")
            .replace("/FONT", "/Inter"),
        format!("{}\n", stream.trim_end()),
        "normalization changed the writer's stream beyond the two resource names \
         and the trailing newline lopdf appends"
    );
}

fn font_dict(bytes: &[u8]) -> (lopdf::Document, lopdf::Dictionary) {
    let document = lopdf::Document::load_mem(bytes).expect("the cover PDF parses");
    let (_, page) = document
        .get_pages()
        .into_iter()
        .next()
        .expect("the cover PDF has a page");
    let resources = document
        .get_dictionary(page)
        .and_then(|dict| dict.get(b"Resources"))
        .and_then(|value| value.as_dict())
        .expect("the page carries resources")
        .clone();
    let font = resources
        .get(b"Font")
        .and_then(|value| value.as_dict())
        .and_then(|fonts| fonts.get(b"Inter"))
        .and_then(|value| document.dereference(value))
        .expect("the cover font is present")
        .1
        .as_dict()
        .expect("the font is a dictionary")
        .clone();
    (document, font)
}

#[test]
fn the_font_widths_serialize_as_the_python_compiler_serializes_them() {
    let bytes = build("footer_caption");
    let (_, font) = font_dict(&bytes);
    let first = font
        .get(b"FirstChar")
        .and_then(|value| value.as_i64())
        .expect("FirstChar");
    let marker = b"/Widths[";
    let start = bytes
        .windows(marker.len())
        .position(|window| window == marker)
        .expect("the font carries a serialized Widths array")
        + marker.len();
    let end = start
        + bytes[start..]
            .iter()
            .position(|byte| *byte == b']')
            .expect("the Widths array closes");
    let serialized: Vec<&str> = std::str::from_utf8(&bytes[start..end])
        .expect("the Widths array is text")
        .split_whitespace()
        .collect();
    let mut rows = String::new();
    for code in 32i64..=126 {
        rows.push_str(&format!("{code} {}\n", serialized[(code - first) as usize]));
    }
    assert_eq!(
        rows,
        include_str!("cover_pdf_widths_expected.txt"),
        "the font widths serialized differently from the Python compiler's"
    );
}

#[test]
fn every_win_ansi_code_round_trips_through_the_to_unicode_cmap() {
    let bytes = build("footer_caption");
    let (document, font) = font_dict(&bytes);
    let cmap = font
        .get(b"ToUnicode")
        .and_then(|value| document.dereference(value))
        .expect("the cover font carries a ToUnicode CMap")
        .1
        .as_stream()
        .expect("ToUnicode is a stream")
        .decompressed_content()
        .expect("the CMap decompresses");
    let text = String::from_utf8(cmap).expect("the CMap is text");
    let mut mapped = 0;
    for (code, value) in [
        (0x41u32, 0x0041u32),
        (0x2f, 0x002f),
        (0x97, 0x2014),
        (0x80, 0x20ac),
        (0xda, 0x00da),
        (0xed, 0x00ed),
    ] {
        let entry = format!("<{code:02X}> <{value:04X}>");
        assert!(
            text.contains(&entry),
            "the ToUnicode CMap is missing {entry}"
        );
        mapped += 1;
    }
    assert_eq!(mapped, 6, "every probed code was checked");
    for undefined in [0x81u32, 0x8d, 0x8f, 0x90, 0x9d] {
        assert!(
            !text.contains(&format!("<{undefined:02X}> <")),
            "the CMap maps code {undefined:#04x}, which WinAnsiEncoding leaves undefined"
        );
    }
    assert_eq!(
        text.matches("beginbfchar").count(),
        text.matches("endbfchar").count(),
        "every bfchar block closes"
    );
    let mut total = 0;
    for block in text.split("beginbfchar").skip(1) {
        let entries = block
            .split("endbfchar")
            .next()
            .expect("a bfchar block body")
            .lines()
            .filter(|line| line.starts_with('<'))
            .count();
        assert!(
            entries <= 100,
            "a bfchar block holds {entries} entries, above the 100 the PDF spec allows"
        );
        total += entries;
    }
    assert_eq!(
        total, 219,
        "the CMap maps every WinAnsi code in 32..255 except the five the encoding leaves undefined"
    );
}

#[test]
fn text_outside_win_ansi_is_refused_rather_than_written_wrong() {
    let mut face = back_face();
    face.text[0].value = "NÚMERO".into();
    let encoded = pdf::write(&face, &cover_pixmap("footer_caption"), &inter())
        .expect("accented latin text writes");
    let stream = content_stream_bytes(&encoded);
    assert!(
        stream
            .windows(7)
            .any(|window| window == [b'N', 0xda, b'M', b'E', b'R', b'O', b')']),
        "U+00DA was not written as the single WinAnsi byte 0xDA"
    );
    face.text[0].value = "\u{5915}".into();
    let error = pdf::write(&face, &cover_pixmap("footer_caption"), &inter())
        .expect_err("a character outside WinAnsiEncoding is refused");
    assert_eq!(
        error.to_string(),
        "Cover text character '夕' is not representable in WinAnsiEncoding"
    );
}
