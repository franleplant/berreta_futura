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
#[path = "../src/cover/raster.rs"]
mod raster;
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
    oracle::pinned(
        "cover_modes",
        "editions/010/art/rounds/2026-09-13T01-40-20/cover-wildcard-sign-punched-v3.png",
    )
}

fn raster_hash(document: &str) -> String {
    let prepared = raster::raster_svg(document, 300);
    let pixmap = raster::render(&prepared).expect("cover rasterizes");
    let mut hasher = Sha256::new();
    hasher.update(pixmap.data());
    format!("{:x}", hasher.finalize())
}

fn build(layout: &str) -> String {
    let assets = repository().join("mag/assets");
    let mut fonts = Fonts::load(&assets).expect("vendored cover faces load");
    let design = design();
    let mut builder = Builder {
        design: &design,
        fonts: &mut fonts,
    };
    builder
        .materialize(layout, &edition_010_text(), &cover_art())
        .unwrap_or_else(|error| panic!("{layout} builds: {error}"))
}

#[test]
fn framed_raster_matches_the_python_compiler() {
    assert_eq!(
        raster_hash(&build("framed")),
        "ece03e915b38e0d3fc36cf68499c4f63c3bad698992210119ba07035fcb11aca",
        "framed cover raster diverged from the Python compiler"
    );
}

#[test]
fn honored_plate_raster_matches_the_python_compiler() {
    assert_eq!(
        raster_hash(&build("honored_plate")),
        "c46b2db485d6bcba195cbda9e37ad9ecbcfca6baa0dc2561af1e4522322a02e9",
        "honored_plate cover raster diverged from the Python compiler"
    );
}

#[test]
fn footer_caption_still_dispatches_through_materialize() {
    let svg = build("footer_caption");
    assert!(svg.contains("data-slot=\"headline\"") && svg.contains("url(#cap-b)"));
}

#[test]
fn an_unknown_layout_is_refused_as_python_refuses_it() {
    let assets = repository().join("mag/assets");
    let mut fonts = Fonts::load(&assets).expect("vendored cover faces load");
    let design = design();
    let mut builder = Builder {
        design: &design,
        fonts: &mut fonts,
    };
    let error = builder
        .materialize("spread", &edition_010_text(), &cover_art())
        .expect_err("an unknown layout is refused");
    assert_eq!(
        error.to_string(),
        "Unknown cover layout 'spread': expected framed, footer_caption, or honored_plate"
    );
}

#[test]
fn missing_cover_art_is_refused_by_every_mode_that_places_it() {
    let assets = repository().join("mag/assets");
    let absent = repository().join("editions/010/art/does-not-exist.png");
    for layout in ["framed", "honored_plate"] {
        let mut fonts = Fonts::load(&assets).expect("vendored cover faces load");
        let design = design();
        let mut builder = Builder {
            design: &design,
            fonts: &mut fonts,
        };
        let error = builder
            .materialize(layout, &edition_010_text(), &absent)
            .expect_err("missing cover art is refused");
        assert_eq!(
            error.to_string(),
            format!("Cover art is missing: {}", absent.display()),
            "{layout} refused with the wrong message"
        );
    }
}

fn compile(layout: &str, mutate: impl FnOnce(&mut CoverText)) -> Result<String, String> {
    let assets = repository().join("mag/assets");
    let mut fonts = Fonts::load(&assets).expect("vendored cover faces load");
    let design = design();
    let mut builder = Builder {
        design: &design,
        fonts: &mut fonts,
    };
    let mut text = edition_010_text();
    mutate(&mut text);
    builder
        .materialize(layout, &text, &cover_art())
        .map_err(|error| error.to_string())
}

fn refusal(layout: &str, mutate: impl FnOnce(&mut CoverText)) -> String {
    compile(layout, mutate).expect_err("the input is refused")
}

fn accepted(layout: &str, mutate: impl FnOnce(&mut CoverText)) {
    compile(layout, mutate).expect("the input fits");
}

const WORDMARK_STEM: &str = "Berreta Incomprehensibilitie";

#[test]
fn a_publication_wordmark_at_the_size_floor_still_fits() {
    let name = format!("{WORDMARK_STEM}l");
    accepted("framed", |text| text.publication_name = name);
}

#[test]
fn a_publication_wordmark_that_cannot_fit_is_refused() {
    let name = format!("{WORDMARK_STEM}s");
    assert_eq!(
        refusal("framed", |text| text.publication_name = name.clone()),
        format!("Publication wordmark cannot fit: {name}")
    );
}

const TITLE_STEM: &str = "The Speed Limit And Its Apostle";

#[test]
fn a_title_of_one_line_at_the_size_floor_still_fits() {
    let title = format!("{TITLE_STEM}l");
    accepted("honored_plate", |text| text.headline = title);
}

#[test]
fn a_title_that_cannot_fit_on_one_line_is_refused() {
    assert_eq!(
        refusal("honored_plate", |text| {
            text.headline = format!("{TITLE_STEM}s")
        }),
        "Cover title cannot fit on one line: THE SPEED LIMIT AND ITS APOSTLES"
    );
}

fn deck_of(count: usize) -> String {
    (0..count)
        .map(|i| format!("CONTRIBUTOR NAME NUMBER {i} WITH EXTRA WORDS"))
        .collect::<Vec<String>>()
        .join(" / ")
}

#[test]
fn a_deck_of_five_wrapped_lines_still_fits() {
    let joined = deck_of(6);
    accepted("framed", |text| text.contributors = joined);
}

#[test]
fn a_deck_that_cannot_fit_is_refused() {
    let joined = deck_of(7);
    assert_eq!(
        refusal("framed", |text| text.contributors = joined.clone()),
        format!("Cover deck cannot fit: {joined}")
    );
}

const HEADLINE_STEM: &str =
    "Antidisestablishmentarianism Floccinaucinihilipilification Pneumonoultramicroscopic";

#[test]
fn a_headline_of_three_lines_at_the_size_floor_still_fits() {
    let headline = format!("{HEADLINE_STEM} Is");
    accepted("framed", |text| text.headline = headline);
}

#[test]
fn a_headline_that_cannot_fit_is_refused() {
    let headline = format!("{HEADLINE_STEM} As");
    assert_eq!(
        refusal("framed", |text| text.headline = headline.clone()),
        format!("Cover headline cannot fit: {headline}")
    );
}
