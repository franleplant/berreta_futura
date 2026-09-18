#[path = "../src/critic/metrics.rs"]
pub mod metrics;

mod critic {
    pub use super::metrics;
}

#[path = "../src/cover/art.rs"]
mod art;
#[path = "../src/cover/outline.rs"]
mod outline;
#[path = "../src/cover/raster.rs"]
mod raster;
#[allow(dead_code)]
#[path = "../src/cover/svg.rs"]
mod svg;

use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

use svg::{
    Art, Builder, CoverText, Deck, Design, Fonts, Footer, FooterCaption, Headline, HonoredPlate,
    Palette, Tab, Wordmark,
};

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

fn cover_art() -> PathBuf {
    repository()
        .join("editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png")
}

fn build_svg() -> String {
    let assets = repository().join("src/magazine/assets");
    let mut fonts = Fonts::load(&assets).expect("vendored cover faces load");
    let design = design();
    let mut builder = Builder {
        design: &design,
        fonts: &mut fonts,
    };
    builder
        .footer_caption(&edition_010_text(), &cover_art())
        .expect("edition 010 front cover builds")
}

#[test]
fn zone_statistics_match_the_python_compiler() {
    let expected: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/cover_zone_expected.json"),
        )
        .expect("the committed zone oracle is readable"),
    )
    .expect("the zone oracle is json");
    let (top, bottom) = art::art_zones(&cover_art(), svg::PAGE_WIDTH - 21.0, svg::PAGE_HEIGHT)
        .expect("edition 010 cover art has zone statistics");
    for (label, observed) in [
        ("top_mean", top.mean),
        ("top_stddev", top.stddev),
        ("bottom_mean", bottom.mean),
        ("bottom_stddev", bottom.stddev),
    ] {
        let want = expected[label].as_f64().expect("oracle carries the field");
        assert!(
            (observed - want).abs() < 1e-9,
            "{label} diverged from PIL: {observed} against {want}"
        );
    }
}

#[test]
fn footer_caption_raster_matches_the_python_compiler() {
    let document = build_svg();
    if let Ok(path) = std::env::var("MAG_COVER_SVG_OUT") {
        std::fs::write(path, &document).expect("svg written");
    }
    let raster = raster::raster_svg(&document, 300);
    let pixmap = raster::render(&raster).expect("cover rasterizes");
    let mut hasher = Sha256::new();
    hasher.update(pixmap.data());
    let observed = format!("{:x}", hasher.finalize());
    if let Ok(path) = std::env::var("MAG_COVER_PNG_OUT") {
        std::fs::write(path, pixmap.encode_png().expect("png encodes")).expect("png written");
    }
    let expected = std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/cover_footer_caption_expected.txt"),
    )
    .expect("the committed oracle is readable");
    assert_eq!(
        observed,
        expected.trim(),
        "front cover raster diverged from the Python compiler"
    );
}
