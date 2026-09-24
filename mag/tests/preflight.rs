#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/parity/exact.rs"]
#[allow(dead_code)]
pub mod exact;
#[path = "../src/parity/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

mod parity {
    pub use super::exact::{authored, num};
}

#[path = "../src/impose.rs"]
#[allow(dead_code)]
mod impose;

#[path = "../src/critic/metrics.rs"]
#[allow(dead_code)]
pub mod metrics_source;

mod critic {
    pub use super::metrics_source as metrics;
}

#[path = "../src/package/preflight.rs"]
#[allow(dead_code)]
mod preflight;

use lopdf::dictionary;
use preflight::{inspect_package, FigurePlacement};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

fn scratch() -> PathBuf {
    let dir = std::env::temp_dir().join(format!("wp55b-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("scratch directory");
    dir
}

fn write_pdf(path: &Path, pages: &[(f64, f64)]) {
    let mut document = lopdf::Document::with_version("1.7");
    let pages_id = document.new_object_id();
    let kids: Vec<lopdf::Object> = pages
        .iter()
        .map(|(width, height)| {
            let contents =
                document.add_object(lopdf::Stream::new(lopdf::Dictionary::new(), b"".to_vec()));
            let page = document.add_object(dictionary! {
                "Type" => "Page",
                "Parent" => pages_id,
                "MediaBox" => vec![0.into(), 0.into(), (*width).into(), (*height).into()],
                "Contents" => contents,
                "Resources" => dictionary! {},
            });
            page.into()
        })
        .collect();
    let count = kids.len() as i64;
    document.objects.insert(
        pages_id,
        lopdf::Object::Dictionary(dictionary! {
            "Type" => "Pages",
            "Kids" => kids,
            "Count" => count,
        }),
    );
    let catalog = document.add_object(dictionary! {
        "Type" => "Catalog",
        "Pages" => pages_id,
    });
    document.trailer.set("Root", catalog);
    document.save(path).expect("pdf writes");
}

fn write_png(path: &Path, width: u32, height: u32, pixel: impl Fn(u32, u32) -> [u8; 3]) {
    let file = std::fs::File::create(path).expect("png file");
    let mut encoder = png::Encoder::new(std::io::BufWriter::new(file), width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header().expect("png header");
    let mut data = Vec::with_capacity((width * height * 3) as usize);
    for y in 0..height {
        for x in 0..width {
            data.extend_from_slice(&pixel(x, y));
        }
    }
    writer.write_image_data(&data).expect("png data");
}

fn a5_pages(count: usize) -> Vec<(f64, f64)> {
    vec![(419.5276, 595.2756); count]
}

fn a4_pages(count: usize) -> Vec<(f64, f64)> {
    vec![(841.8898, 595.2756); count]
}

struct Bundle {
    reader: PathBuf,
    booklet: PathBuf,
    interior: PathBuf,
    cover: PathBuf,
}

fn bundle(tag: &str, reader_pages: Vec<(f64, f64)>) -> Bundle {
    let dir = scratch().join(tag);
    std::fs::create_dir_all(&dir).expect("bundle directory");
    let page_count = reader_pages.len();
    let sheets = page_count.div_ceil(4);
    let bundle = Bundle {
        reader: dir.join("reader.pdf"),
        booklet: dir.join("booklet.pdf"),
        interior: dir.join("interior.pdf"),
        cover: dir.join("cover.pdf"),
    };
    write_pdf(&bundle.reader, &reader_pages);
    write_pdf(&bundle.booklet, &a4_pages(sheets * 2));
    write_pdf(&bundle.interior, &a4_pages(sheets.saturating_sub(1) * 2));
    write_pdf(&bundle.cover, &a4_pages(1));
    bundle
}

fn figure(id: &str, page: i64, path: &Path, box_points: Vec<f64>) -> FigurePlacement {
    FigurePlacement {
        figure_id: id.into(),
        article_id: "article".into(),
        page,
        path: path.to_path_buf(),
        pixel_dimensions: Some((2000, 1418)),
        box_points,
        effective_ppi: Some(498.0),
        caption: "caption".into(),
        credit: "credit".into(),
    }
}

fn inspect(bundle: &Bundle, figures: &[FigurePlacement], language: &str) -> Value {
    inspect_package(
        &bundle.reader,
        &bundle.booklet,
        &bundle.interior,
        &bundle.cover,
        None,
        None,
        figures,
        language,
    )
    .expect("inspection succeeds")
}

fn blockers(report: &Value) -> Vec<String> {
    report["studio"]["blockers"]
        .as_array()
        .expect("blockers is an array")
        .iter()
        .map(|entry| entry.as_str().expect("blocker is a string").to_string())
        .collect()
}

#[test]
fn reader_shape_branches_edition_010_cannot_reach() {
    let square = bundle("square", vec![(400.0, 400.0); 6]);
    let report = inspect(&square, &[], "en");
    assert_eq!(report["reader"]["page_count"], json!(6));
    assert_eq!(
        report["reader"]["page_count_multiple_of_four"],
        json!(false)
    );
    assert_eq!(report["reader"]["all_pages_a5"], json!(false));

    let tiny = bundle("tiny", a5_pages(2));
    let report = inspect(&tiny, &[], "en");
    assert_eq!(
        report["home_booklet_interior"]["reader_pages"],
        json!([]),
        "a reader under four pages yields no section pages"
    );
    assert_eq!(report["home_booklet_interior"]["expected_sheets"], json!(0));
    assert_eq!(
        report["home_booklet_cover"]["expected_sheets"],
        json!(1),
        "the cover section is single sided and always one sheet"
    );
}

#[test]
fn language_selection_covers_both_tables_and_the_fallback() {
    let deck = bundle("language", a5_pages(8));
    let english = blockers(&inspect(&deck, &[], "en"));
    let spanish = blockers(&inspect(&deck, &[], "es"));
    let regional = blockers(&inspect(&deck, &[], "es-AR"));
    let unknown = blockers(&inspect(&deck, &[], "de"));

    assert!(english[0].starts_with("PDF/X-4"));
    assert!(spanish[0].starts_with("No están"));
    assert_eq!(spanish, regional, "a region suffix selects the base table");
    assert_eq!(
        unknown, english,
        "an unknown language falls back to English"
    );
}

#[test]
fn cover_art_absence_and_unreadable_paths_yield_no_measurements() {
    let deck = bundle("cover", a5_pages(8));
    let report = inspect(&deck, &[], "en");
    assert_eq!(report["cover_art"]["path"], Value::Null);
    assert_eq!(report["cover_art"]["pixel_dimensions"], Value::Null);
    assert!(
        report["cover_art"].get("effective_ppi_at_a5").is_none(),
        "no dimensions means the ppi keys are absent entirely"
    );

    let missing = scratch().join("absent.png");
    let report = inspect_package(
        &deck.reader,
        &deck.booklet,
        &deck.interior,
        &deck.cover,
        Some(&missing),
        None,
        &[],
        "en",
    )
    .expect("inspection succeeds");
    assert_eq!(report["cover_art"]["pixel_dimensions"], Value::Null);
    assert_ne!(report["cover_art"]["path"], Value::Null);

    let wrong_suffix = scratch().join("cover.tiff");
    std::fs::write(&wrong_suffix, b"not an image").expect("file writes");
    let report = inspect_package(
        &deck.reader,
        &deck.booklet,
        &deck.interior,
        &deck.cover,
        Some(&wrong_suffix),
        None,
        &[],
        "en",
    )
    .expect("inspection succeeds");
    assert_eq!(report["cover_art"]["pixel_dimensions"], Value::Null);
}

#[test]
fn cover_resolution_target_decides_the_studio_blocker() {
    let deck = bundle("resolution", a5_pages(8));
    let low = scratch().join("low.png");
    write_png(&low, 100, 150, |_, _| [255, 255, 255]);
    let high = scratch().join("high.png");
    write_png(&high, 2400, 3400, |_, _| [255, 255, 255]);

    let report = inspect_package(
        &deck.reader,
        &deck.booklet,
        &deck.interior,
        &deck.cover,
        Some(&low),
        None,
        &[],
        "en",
    )
    .expect("inspection succeeds");
    assert_eq!(
        report["cover_art"]["studio_300ppi_target_met"],
        json!(false)
    );
    assert!(blockers(&report)
        .iter()
        .any(|entry| entry.contains("Cover artwork")));

    let report = inspect_package(
        &deck.reader,
        &deck.booklet,
        &deck.interior,
        &deck.cover,
        Some(&high),
        None,
        &[],
        "en",
    )
    .expect("inspection succeeds");
    assert_eq!(report["cover_art"]["studio_300ppi_target_met"], json!(true));
    assert!(!blockers(&report)
        .iter()
        .any(|entry| entry.contains("Cover artwork")));
}

#[test]
fn placement_points_default_to_a5_and_honour_an_override() {
    let deck = bundle("placement", a5_pages(8));
    let art = scratch().join("art.png");
    write_png(&art, 1440, 2160, |_, _| [255, 255, 255]);

    let defaulted = inspect_package(
        &deck.reader,
        &deck.booklet,
        &deck.interior,
        &deck.cover,
        Some(&art),
        None,
        &[],
        "en",
    )
    .expect("inspection succeeds");
    assert_eq!(
        defaulted["cover_art"]["placement_points"],
        json!([419.528, 595.276])
    );
    assert_eq!(
        defaulted["cover_art"]["effective_ppi_at_a5"],
        defaulted["cover_art"]["effective_ppi_at_placement"],
        "the default placement is A5, so both figures agree"
    );

    let overridden = inspect_package(
        &deck.reader,
        &deck.booklet,
        &deck.interior,
        &deck.cover,
        Some(&art),
        Some((200.0, 300.0)),
        &[],
        "en",
    )
    .expect("inspection succeeds");
    assert_eq!(
        overridden["cover_art"]["placement_points"],
        json!([200.0, 300.0])
    );
    assert_ne!(
        overridden["cover_art"]["effective_ppi_at_a5"],
        overridden["cover_art"]["effective_ppi_at_placement"],
        "a smaller placement raises the effective resolution"
    );
}

#[test]
fn every_box_invalidity_condition_is_detected() {
    let deck = bundle("boxes", a5_pages(8));
    let art = scratch().join("box.png");
    write_png(&art, 40, 40, |_, _| [255, 255, 255]);
    let cases: Vec<(&str, i64, Vec<f64>)> = vec![
        ("page_below_one", 0, vec![10.0, 10.0, 100.0, 100.0]),
        ("page_above_count", 99, vec![10.0, 10.0, 100.0, 100.0]),
        ("width_zero", 1, vec![10.0, 10.0, 0.0, 100.0]),
        ("height_zero", 1, vec![10.0, 10.0, 100.0, 0.0]),
        ("negative_x", 1, vec![-1.0, 10.0, 100.0, 100.0]),
        ("negative_y", 1, vec![10.0, -1.0, 100.0, 100.0]),
        ("overflows_width", 1, vec![400.0, 10.0, 100.0, 100.0]),
        ("overflows_height", 1, vec![10.0, 580.0, 100.0, 100.0]),
        ("not_four_values", 1, vec![10.0, 10.0, 100.0]),
    ];
    for (name, page, box_points) in cases {
        let placement = figure(name, page, &art, box_points);
        let report = inspect(&deck, std::slice::from_ref(&placement), "en");
        let invalid = report["invalid_figure_boxes"]
            .as_array()
            .expect("array")
            .len();
        assert_eq!(invalid, 1, "{name} must be rejected as an invalid box");
        assert!(
            blockers(&report)
                .iter()
                .any(|entry| entry.contains("invalid or collide")),
            "{name} must raise the geometry blocker"
        );
    }
}

#[test]
fn overlapping_figures_on_one_page_collide_and_neighbours_do_not() {
    let deck = bundle("collision", a5_pages(8));
    let art = scratch().join("collide.png");
    write_png(&art, 40, 40, |_, _| [255, 255, 255]);

    let overlapping = vec![
        figure("first", 3, &art, vec![10.0, 10.0, 100.0, 100.0]),
        figure("second", 3, &art, vec![50.0, 50.0, 100.0, 100.0]),
    ];
    let report = inspect(&deck, &overlapping, "en");
    assert_eq!(
        report["figure_collisions"].as_array().expect("array").len(),
        1
    );
    assert_eq!(
        report["figure_collisions"][0]["figure_ids"],
        json!(["first", "second"])
    );

    let apart = vec![
        figure("first", 3, &art, vec![10.0, 10.0, 100.0, 100.0]),
        figure("second", 3, &art, vec![200.0, 200.0, 100.0, 100.0]),
        figure("third", 4, &art, vec![10.0, 10.0, 100.0, 100.0]),
    ];
    let report = inspect(&deck, &apart, "en");
    assert_eq!(
        report["figure_collisions"].as_array().expect("array").len(),
        0,
        "boxes that do not overlap, and boxes on different pages, do not collide"
    );
}

#[test]
fn low_resolution_figures_raise_their_own_blocker() {
    let deck = bundle("lowres", a5_pages(8));
    let art = scratch().join("lowres.png");
    write_png(&art, 40, 40, |_, _| [255, 255, 255]);
    let mut placement = figure("faint", 3, &art, vec![10.0, 10.0, 100.0, 100.0]);
    placement.effective_ppi = Some(120.0);
    let report = inspect(&deck, std::slice::from_ref(&placement), "en");
    assert_eq!(
        report["low_resolution_figures"][0]["effective_ppi"],
        json!(120.0)
    );
    assert!(blockers(&report)
        .iter()
        .any(|entry| entry.contains("below 300 ppi")));
}

#[test]
fn effective_ppi_and_dimensions_are_derived_when_absent() {
    let deck = bundle("derive", a5_pages(8));
    let art = scratch().join("derive.png");
    write_png(&art, 1200, 900, |_, _| [255, 255, 255]);
    let mut placement = figure("derived", 3, &art, vec![10.0, 10.0, 144.0, 108.0]);
    placement.pixel_dimensions = None;
    placement.effective_ppi = None;
    let report = inspect(&deck, std::slice::from_ref(&placement), "en");
    assert_eq!(
        report["figures"][0]["pixel_dimensions"],
        json!([1200, 900]),
        "dimensions come from the file when the placement omits them"
    );
    assert_eq!(
        report["figures"][0]["effective_ppi"],
        json!(600.0),
        "1200 px over 144 pt is 600 ppi"
    );
}

#[test]
fn a_figure_that_stays_faint_after_treatment_raises_the_contrast_blocker() {
    let deck = bundle("contrast", a5_pages(8));
    let art = scratch().join("faint.png");
    write_png(&art, 200, 200, |_, y| {
        if y < 20 {
            [208, 208, 208]
        } else {
            [255, 255, 255]
        }
    });
    let placement = figure("faint", 3, &art, vec![10.0, 10.0, 100.0, 100.0]);
    let report = inspect(&deck, std::slice::from_ref(&placement), "en");
    let contrast = &report["figures"][0]["print_contrast"];
    assert_ne!(*contrast, Value::Null, "a readable image is analysed");
    if !report["unresolved_low_contrast_figures"]
        .as_array()
        .expect("array")
        .is_empty()
    {
        assert!(blockers(&report)
            .iter()
            .any(|entry| entry.contains("too faint")));
    }
}

#[test]
fn the_result_field_is_constant_because_two_blockers_are_unconditional() {
    let deck = bundle("constant", a5_pages(8));
    let report = inspect(&deck, &[], "en");
    assert_eq!(report["result"], json!("home_ready_studio_blocked"));
    assert_eq!(report["studio"]["ready"], json!(false));
    assert!(
        blockers(&report).len() >= 2,
        "pdfx and bleed are appended unconditionally, so the ready branch is unreachable"
    );
}

#[test]
fn edition_010_matches_the_python_oracle() {
    let spec = std::env::var("MAG_PREFLIGHT_SPEC").ok();
    let oracle = std::env::var("MAG_PREFLIGHT_ORACLE").ok();
    match (spec, oracle) {
        (None, None) => {
            eprintln!(
                "SKIPPED edition_010_matches_the_python_oracle: set MAG_PREFLIGHT_SPEC and \
                 MAG_PREFLIGHT_ORACLE to run the edition oracle. cargo test alone does NOT \
                 prove edition 010."
            );
        }
        (Some(spec), Some(oracle)) => {
            let spec: Value = serde_json::from_slice(&std::fs::read(&spec).expect("spec reads"))
                .expect("spec parses");
            let placements: Vec<FigurePlacement> = spec["figures"]
                .as_array()
                .expect("figures array")
                .iter()
                .map(|entry| FigurePlacement {
                    figure_id: entry["figure_id"].as_str().unwrap_or_default().into(),
                    article_id: entry["article_id"].as_str().unwrap_or_default().into(),
                    page: entry["page"].as_i64().unwrap_or_default(),
                    path: PathBuf::from(entry["path"].as_str().unwrap_or_default()),
                    pixel_dimensions: entry["pixel_dimensions"].as_array().map(|pair| {
                        (
                            pair[0].as_u64().unwrap_or_default() as u32,
                            pair[1].as_u64().unwrap_or_default() as u32,
                        )
                    }),
                    box_points: entry["box_points"]
                        .as_array()
                        .expect("box_points")
                        .iter()
                        .map(|value| value.as_f64().unwrap_or_default())
                        .collect(),
                    effective_ppi: entry["effective_ppi"].as_f64(),
                    caption: entry["caption"].as_str().unwrap_or_default().into(),
                    credit: entry["credit"].as_str().unwrap_or_default().into(),
                })
                .collect();
            let cover = spec["cover_art"].as_str().map(PathBuf::from);
            let produced = inspect_package(
                Path::new(spec["reader_pdf"].as_str().expect("reader_pdf")),
                Path::new(spec["booklet_pdf"].as_str().expect("booklet_pdf")),
                Path::new(spec["interior_booklet_pdf"].as_str().expect("interior")),
                Path::new(spec["cover_booklet_pdf"].as_str().expect("cover")),
                cover.as_deref(),
                spec["cover_art_size_points"].as_array().map(|pair| {
                    (
                        pair[0].as_f64().unwrap_or_default(),
                        pair[1].as_f64().unwrap_or_default(),
                    )
                }),
                &placements,
                spec["language"].as_str().unwrap_or("en"),
            )
            .expect("inspection succeeds");
            let expected: Value =
                serde_json::from_slice(&std::fs::read(&oracle).expect("oracle reads"))
                    .expect("oracle parses");
            assert_eq!(
                serde_json::to_string_pretty(&produced).expect("serialises"),
                serde_json::to_string_pretty(&expected).expect("serialises"),
                "the Rust report must equal the Python oracle"
            );
        }
        _ => panic!("set both MAG_PREFLIGHT_SPEC and MAG_PREFLIGHT_ORACLE, or neither"),
    }
}
