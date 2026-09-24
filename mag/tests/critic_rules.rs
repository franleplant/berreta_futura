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

#[path = "../src/parity/display.rs"]
#[allow(dead_code)]
pub mod display;

mod parity {
    pub use super::display::trace_elements;
    pub use super::exact::{authored, num};
    #[allow(unused_imports)]
    pub use super::streams::{Color, Element, Face as TextFace, GLYPH_QUANTUM};
}

#[path = "../src/impose.rs"]
#[allow(dead_code)]
pub mod impose;

#[path = "../src/critic/metrics.rs"]
#[allow(dead_code)]
pub mod metrics;

#[path = "../src/critic/text.rs"]
#[allow(dead_code)]
pub mod text;

#[path = "../src/critic/inspect.rs"]
#[allow(dead_code)]
pub mod inspect;

mod critic {
    #[allow(unused_imports)]
    pub use super::inspect;
    pub use super::{metrics, text};
}

#[path = "../src/critic/rules.rs"]
#[allow(dead_code)]
mod rules;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

fn canon(value: &Value) -> Value {
    match value {
        Value::Number(number) => Value::String(if number.is_f64() {
            format!("f{:016x}", number.as_f64().expect("a float").to_bits())
        } else {
            format!("i{number}")
        }),
        Value::Array(items) => Value::Array(items.iter().map(canon).collect()),
        Value::Object(map) => Value::Object(
            map.iter()
                .map(|(key, item)| (key.clone(), canon(item)))
                .collect(),
        ),
        other => other.clone(),
    }
}

fn manifest_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

fn fixtures() -> PathBuf {
    manifest_dir().join("tests/critic_rules_fixtures")
}

fn oracle(name: &str) -> Value {
    let path = manifest_dir().join("tests").join(name);
    serde_json::from_str(
        &std::fs::read_to_string(&path)
            .unwrap_or_else(|error| panic!("{} is readable: {error}", path.display())),
    )
    .expect("the oracle is json")
}

fn digest(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

fn scratch(tag: &str) -> PathBuf {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("a clock after 1970")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("wp53biii-{tag}-{stamp}"));
    std::fs::create_dir_all(&path).expect("the scratch directory is writable");
    path
}

fn poppler_pinned() -> bool {
    let output = std::process::Command::new("pdftoppm")
        .arg("-v")
        .output()
        .expect("poppler is installed");
    let banner = String::from_utf8_lossy(&output.stderr).to_string();
    assert!(
        banner.contains("25.08.0"),
        "the oracle needs the pinned poppler 25.08.0, found {banner}"
    );
    true
}

fn font_map() -> BTreeMap<String, streams::Face> {
    let spec: serde_yaml::Value = serde_yaml::from_str(
        &std::fs::read_to_string(manifest_dir().join("../meta/verification/parity.yaml"))
            .expect("parity.yaml is readable"),
    )
    .expect("parity.yaml is yaml");
    let entries = spec["normalization"]["font_name_map"]["entries"]
        .as_mapping()
        .expect("the font name map has entries");
    let mut map = BTreeMap::new();
    for (alias, value) in entries {
        map.insert(
            alias.as_str().expect("an alias").to_string(),
            streams::Face {
                face: value["face"].as_str().expect("a face").to_string(),
                file: format!(
                    "{}/../{}",
                    env!("CARGO_MANIFEST_DIR"),
                    value["file"].as_str().expect("a file")
                ),
            },
        );
    }
    map
}

const LEG_FILES: [(&str, &str); 4] = [
    ("reader", "reader.pdf"),
    ("booklet", "booklet-a4.pdf"),
    ("interior", "booklet-a4-interior.pdf"),
    ("cover", "booklet-a4-cover.pdf"),
];

fn stage(render: &Path, tag: &str) -> PathBuf {
    let destination = scratch(tag);
    for (_, name) in LEG_FILES {
        std::fs::copy(render.join(name), destination.join(name))
            .unwrap_or_else(|error| panic!("staging {name}: {error}"));
    }
    std::fs::copy(
        render.join("edition-manifest.json"),
        destination.join("edition-manifest.json"),
    )
    .expect("staging the manifest");
    destination
}

fn counts(layout: &Value, key: &str) -> BTreeMap<String, usize> {
    layout
        .get(key)
        .and_then(Value::as_object)
        .map(|map| {
            map.iter()
                .filter_map(|(slug, value)| Some((slug.clone(), value.as_u64()? as usize)))
                .collect()
        })
        .unwrap_or_default()
}

fn live_render() -> Option<PathBuf> {
    std::env::var("MAG_CRITIC_RENDER_DIR")
        .ok()
        .map(PathBuf::from)
}

fn critique(destination: &Path) -> rules::Critique {
    let layout = rules::manifest_layout(destination);
    let toc = counts(&layout, "toc");
    let article_pages = counts(&layout, "article_pages");
    let editorial_pages = layout.get("editorial_pages").and_then(Value::as_i64);
    rules::inspect_render(&rules::Inputs {
        reader_pdf: &destination.join("reader.pdf"),
        booklet_pdf: &destination.join("booklet-a4.pdf"),
        interior_booklet_pdf: &destination.join("booklet-a4-interior.pdf"),
        cover_booklet_pdf: &destination.join("booklet-a4-cover.pdf"),
        destination,
        toc: &toc,
        article_pages: &article_pages,
        editorial_pages,
        fonts: &font_map(),
    })
    .expect("the critic runs")
}

#[test]
fn dumps_the_tracer_text_the_python_oracle_needs() {
    let Some(render) = live_render() else {
        println!("MODE: skipped, MAG_CRITIC_RENDER_DIR unset");
        return;
    };
    let Ok(target) = std::env::var("MAG_CRITIC_RULES_TEXT") else {
        println!("MODE: skipped, MAG_CRITIC_RULES_TEXT unset");
        return;
    };
    println!("MODE: full, tracing {}", render.display());
    let fonts = font_map();
    let mut out = serde_json::Map::new();
    for (leg, name) in LEG_FILES {
        let read = rules::read_leg(&render.join(name), &fonts).expect("the leg traces");
        println!("TRACED: {leg} {} pages", read.pages());
        out.insert(
            leg.to_string(),
            json!({"raw": read.raw, "normalized": read.normalized}),
        );
    }
    std::fs::write(
        &target,
        serde_json::to_string_pretty(&Value::Object(out)).expect("the dump serializes"),
    )
    .expect("the dump is writable");
    println!("WROTE: {target}");
}

fn geometry_rows(critique: &rules::Critique) -> Value {
    canon(&Value::Array(
        critique
            .pages
            .iter()
            .map(|row| {
                json!({
                    "page": row.inspection.page,
                    "largest_void": row.largest_void.map(|void| void.as_row()),
                    "voids": row.voids.iter().map(rules::Void::as_row).collect::<Vec<Value>>(),
                    "tail_band": row.tail_band.map(|band| band.as_row()),
                })
            })
            .collect(),
    ))
}

fn spread_rows(spreads: &[rules::Spread]) -> Value {
    canon(&Value::Array(
        spreads.iter().map(rules::Spread::as_row).collect(),
    ))
}

#[test]
fn decides_edition_010_like_python() {
    let (Some(render), Ok(path)) = (live_render(), std::env::var("MAG_CRITIC_RULES_ORACLE")) else {
        println!("MODE: skipped, MAG_CRITIC_RENDER_DIR or MAG_CRITIC_RULES_ORACLE unset");
        assert!(
            live_render().is_none() && std::env::var("MAG_CRITIC_RULES_ORACLE").is_err(),
            "set both MAG_CRITIC_RENDER_DIR and MAG_CRITIC_RULES_ORACLE, or neither"
        );
        return;
    };
    assert!(poppler_pinned());
    let expected: Value =
        serde_json::from_str(&std::fs::read_to_string(&path).expect("the live oracle is readable"))
            .expect("the live oracle is json");
    let destination = stage(&render, "live");
    let produced = critique(&destination);
    println!("MODE: full, judging {}", destination.display());
    let tracer = &expected["tracer_text"];
    assert_eq!(
        canon(&produced.decisions()),
        tracer["decisions"],
        "decision set"
    );
    println!(
        "COMPARED: {} issues, result {}",
        produced.issues.len(),
        produced.result
    );
    assert_eq!(
        geometry_rows(&produced),
        tracer["geometry"],
        "void geometry"
    );
    assert_eq!(
        spread_rows(&produced.spreads),
        tracer["spreads"],
        "booklet spreads"
    );
    assert_eq!(
        spread_rows(&produced.interior_spreads),
        tracer["interior_spreads"],
        "interior spreads"
    );
    assert_eq!(
        spread_rows(&produced.cover_spreads),
        tracer["cover_spreads"],
        "cover spreads"
    );
    assert_eq!(
        canon(&json!(produced.live_area_points)),
        tracer["live_area_points"],
        "live area"
    );
    assert_eq!(canon(&json!(produced.crops)), tracer["crops"], "crop plan");
    assert_eq!(
        canon(&json!(produced.opener_crop_fidelity)),
        tracer["opener_crop_fidelity"],
        "opener crop fidelity"
    );
    assert_eq!(
        canon(&json!(produced.opener_offsets)),
        tracer["opener_offsets"],
        "opener offsets"
    );
    compare_crop_pixels(&produced, &render, tracer);
    report_text_source_swap(&produced, &expected);
}

fn compare_crop_pixels(produced: &rules::Critique, render: &Path, tracer: &Value) {
    let rows = tracer["crop_pixels"]
        .as_object()
        .expect("crop pixel digests");
    let mut compared = 0;
    for path in &produced.crop_paths {
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .expect("a crop name");
        let mine = metrics::decode_rgb(path).expect("the crop decodes");
        assert_eq!(
            digest(&mine.data),
            rows[name].as_str().unwrap_or_default(),
            "crop pixels for {name}"
        );
        let theirs = metrics::decode_rgb(&render.join("render-review/crops").join(name))
            .expect("python's crop decodes");
        assert_eq!(
            mine, theirs,
            "crop pixels against the shipped render for {name}"
        );
        compared += 1;
    }
    println!("COMPARED: {compared} crops pixel for pixel");
    assert_eq!(compared, rows.len(), "every oracle crop was compared");
}

fn report_text_source_swap(produced: &rules::Critique, expected: &Value) {
    let pypdf = &expected["pypdf_text"]["decisions"];
    let tracer = &expected["tracer_text"]["decisions"];
    println!(
        "TEXT SOURCE SWAP: python-with-pypdf {} python-with-tracer, rust equals tracer: {}",
        if pypdf == tracer {
            "EQUALS"
        } else {
            "DIFFERS from"
        },
        canon(&produced.decisions()) == *tracer
    );
    assert_eq!(
        pypdf, tracer,
        "the text-source swap moved a decision on 010; the port's oracle is the tracer leg but this must be reported"
    );
}

fn png(name: &str) -> metrics::Rgb {
    metrics::decode_rgb(&fixtures().join(name)).unwrap_or_else(|error| panic!("{name}: {error}"))
}

fn cases(group: &str) -> Vec<Value> {
    oracle("critic_rules_expected.json")[group]
        .as_array()
        .unwrap_or_else(|| panic!("the oracle carries {group}"))
        .clone()
}

fn label(case: &Value) -> String {
    case["name"].as_str().expect("a case name").to_string()
}

#[test]
fn opener_offset_matches_python_on_the_fixtures() {
    let rows = cases("opener_offset");
    assert!(rows.len() >= 8, "only {} offset cases", rows.len());
    let mut verdicts = vec![];
    for case in &rows {
        let produced =
            rules::inspect_opener_offset(&fixtures().join(case["png"].as_str().expect("png")))
                .expect("the fixture inspects");
        assert_eq!(
            canon(&produced),
            case["row"],
            "opener offset for {}",
            label(case)
        );
        verdicts.push(produced["pass"].as_bool().expect("a verdict"));
    }
    assert!(
        verdicts.contains(&true) && verdicts.contains(&false),
        "the offset fixtures must hold a passing and a failing case, found {verdicts:?}"
    );
}

#[test]
fn opener_frame_bbox_matches_python_and_the_tolerance_discriminates() {
    let rows = cases("frame_bbox");
    let mut found = (0, 0);
    for case in &rows {
        let tolerance = case["tolerance"].as_i64().expect("a tolerance") as i32;
        let produced =
            rules::opener_frame_bbox(&png(case["png"].as_str().expect("png")), tolerance);
        assert_eq!(
            canon(&json!(produced)),
            case["bbox"],
            "frame bbox for {}",
            label(case)
        );
        match produced {
            Some(_) => found.0 += 1,
            None => found.1 += 1,
        }
    }
    assert!(
        found.0 > 0 && found.1 > 0,
        "the frame fixtures must hold a located and an unlocated case, found {found:?}"
    );
    assert_eq!(
        rules::opener_frame_bbox(&png("opener_tolerant.png"), 0),
        None,
        "a near-black frame must be invisible at tolerance 0, else the tolerance is inert"
    );
    assert!(
        rules::opener_frame_bbox(&png("opener_tolerant.png"), 24).is_some(),
        "a near-black frame must be visible at tolerance 24"
    );
}

#[test]
fn opener_crop_fidelity_matches_python_on_the_fixtures() {
    let rows = cases("crop_fidelity");
    let mut seen = (0, 0);
    for case in &rows {
        let produced = rules::inspect_opener_crop_fidelity(
            &fixtures().join(case["crop"].as_str().expect("crop")),
            &fixtures().join(case["reference"].as_str().expect("reference")),
        )
        .expect("the fixture pair inspects");
        assert_eq!(
            canon(&produced),
            case["row"],
            "crop fidelity for {}",
            label(case)
        );
        if produced["pass"].as_bool().expect("a verdict") {
            seen.0 += 1;
        } else {
            seen.1 += 1;
        }
    }
    assert!(
        seen.0 > 0 && seen.1 > 0,
        "the fidelity fixtures must hold a passing and a failing case, found {seen:?}"
    );
    let single_leg: Vec<String> = rows
        .iter()
        .filter(|case| {
            let row = &case["row"];
            row["pass"] == json!(false)
                && bits_of(&row["rgb_mae"]) <= rules::OPENER_CROP_FIDELITY_MAX_RGB_MAE
        })
        .map(label)
        .collect();
    assert!(
        !single_leg.is_empty(),
        "a fixture must fail on the frame leg alone, else the frame budget is untested"
    );
}

#[test]
fn mask_reduction_matches_pil() {
    let rows = cases("masks");
    for case in &rows {
        let gray = inspect::grayscale(&png(case["png"].as_str().expect("png")));
        let presence = inspect::point_below(&gray, inspect::PAPER_WHITE);
        let numbers: Vec<i64> = case["box"]
            .as_array()
            .expect("a box")
            .iter()
            .map(|value| value.as_i64().expect("an edge"))
            .collect();
        let cells = rules::mask_cells(
            &rules::crop(&presence, [numbers[0], numbers[1], numbers[2], numbers[3]]),
            rules::VOID_DOWNSAMPLE,
        );
        assert_eq!(
            canon(&json!([cells.width, cells.height])),
            case["size"],
            "reduced size for {}",
            label(case)
        );
        let theirs: Vec<bool> = case["bytes"]
            .as_array()
            .expect("bytes")
            .iter()
            .map(|value| value.as_u64() != Some(0))
            .collect();
        let mine: Vec<bool> = cells.data.iter().map(|&cell| cell != 0).collect();
        assert_eq!(
            mine,
            theirs,
            "cell occupancy against PIL's reduce for {}",
            label(case)
        );
        assert_eq!(
            digest(&cells.data),
            digest(
                &theirs
                    .iter()
                    .map(|&cell| if cell { 255 } else { 0 })
                    .collect::<Vec<u8>>()
            ),
            "the occupancy grid for {} must be PIL's reduce thresholded at zero",
            label(case)
        );
    }
    let all_empty = rows.iter().all(|case| {
        case["bytes"]
            .as_array()
            .expect("bytes")
            .iter()
            .all(|v| v == &json!(0))
    });
    assert!(
        !all_empty,
        "a mask fixture must carry ink, else the reduction is untested"
    );
}

fn bytes_of(case: &Value, key: &str) -> Vec<u8> {
    case[key]
        .as_array()
        .expect("a byte array")
        .iter()
        .map(|value| value.as_u64().expect("a byte") as u8)
        .collect()
}

#[test]
fn largest_empty_rectangle_matches_python() {
    let rows = cases("rectangles");
    for case in &rows {
        let produced = rules::largest_empty_rectangle(
            &bytes_of(case, "data"),
            case["columns"].as_u64().expect("columns") as usize,
            case["rows"].as_u64().expect("rows") as usize,
        );
        assert_eq!(
            canon(&json!(produced)),
            case["best"],
            "rectangle for {}",
            label(case)
        );
    }
    let areas: Vec<String> = rows
        .iter()
        .map(|case| case["best"][0].as_str().expect("an area").to_string())
        .collect();
    assert!(
        areas.contains(&"i0".to_string()) && areas.iter().any(|area| area != "i0"),
        "the rectangle fixtures must hold an empty and a non-empty answer, found {areas:?}"
    );
}

#[test]
fn tail_band_location_matches_python() {
    let rows = cases("tail_bands");
    for case in &rows {
        let live: Vec<i64> = case["live"]
            .as_array()
            .expect("live")
            .iter()
            .map(|value| value.as_i64().expect("an edge"))
            .collect();
        let produced = rules::locate_tail_band(
            &bytes_of(case, "data"),
            case["columns"].as_u64().expect("columns") as usize,
            case["rows"].as_u64().expect("rows") as usize,
            [live[0], live[1], live[2], live[3]],
            case["scale"].as_f64().expect("a scale"),
            case["declared_height"].as_f64().expect("a height"),
        );
        assert_eq!(
            canon(&produced.map_or(Value::Null, |band| band.as_row())),
            case["band"],
            "tail band for {}",
            label(case)
        );
    }
    assert!(
        rows.iter().any(|case| case["band"] == Value::Null)
            && rows.iter().any(|case| case["band"] != Value::Null),
        "the tail-band fixtures must hold a match and a miss"
    );
}

#[test]
fn tail_band_adjacency_matches_python() {
    let rows = cases("abuts");
    for case in &rows {
        let void = rules::Void {
            x_points: 0.0,
            y_points: case["void"]["y_points"].as_f64().expect("y"),
            width_points: 0.0,
            height_points: case["void"]["height_points"].as_f64().expect("height"),
            width_fraction: 0.0,
            trailing: false,
        };
        let band = rules::TailBand {
            y_points: case["band"]["y_points"].as_f64().expect("y"),
            height_points: case["band"]["height_points"].as_f64().expect("height"),
            declared_height_points: 0.0,
            gap_above_points: 0.0,
            gap_below_points: 0.0,
            centered: false,
        };
        assert_eq!(
            rules::abuts_tail_band(&void, &band),
            case["abuts"].as_bool().expect("a verdict"),
            "adjacency for {}",
            label(case)
        );
    }
}

#[test]
fn editorial_cap_and_printed_bands_match_python() {
    for case in cases("editorial_caps") {
        assert_eq!(
            canon(&json!(rules::declared_editorial_cap(&case["layout"]))),
            case["cap"],
            "editorial cap for {}",
            label(&case)
        );
    }
    for case in cases("printed_tail_bands") {
        let lasts: BTreeMap<String, usize> = case["article_last_pages"]
            .as_object()
            .expect("last pages")
            .iter()
            .map(|(slug, page)| (slug.clone(), page.as_u64().expect("a page") as usize))
            .collect();
        let produced: BTreeMap<String, f64> = rules::printed_tail_bands(&case["layout"], &lasts)
            .into_iter()
            .map(|(page, height)| (page.to_string(), height))
            .collect();
        assert_eq!(
            canon(&json!(produced)),
            case["bands"],
            "printed bands for {}",
            label(&case)
        );
    }
}

fn void_of(value: &Value) -> rules::Void {
    rules::Void {
        x_points: value["x_points"].as_f64().expect("x"),
        y_points: value["y_points"].as_f64().expect("y"),
        width_points: value["width_points"].as_f64().expect("width"),
        height_points: value["height_points"].as_f64().expect("height"),
        width_fraction: value["width_fraction"].as_f64().expect("fraction"),
        trailing: value["trailing"].as_bool().expect("trailing"),
    }
}

fn band_of(value: &Value) -> Option<rules::TailBand> {
    value.as_object().map(|band| rules::TailBand {
        y_points: band["y_points"].as_f64().expect("y"),
        height_points: band["height_points"].as_f64().expect("height"),
        declared_height_points: band["declared_height_points"].as_f64().expect("declared"),
        gap_above_points: band["gap_above_points"].as_f64().expect("above"),
        gap_below_points: band["gap_below_points"].as_f64().expect("below"),
        centered: band["centered"].as_bool().expect("centered"),
    })
}

fn inspection_of(row: &Value) -> inspect::PageInspection {
    inspect::PageInspection {
        page: row["page"].as_u64().expect("page") as usize,
        pixel_dimensions: [0, 0],
        ink_ratio: row["ink_ratio"].as_f64().unwrap_or(0.0),
        ink_bbox: None,
        presence_ratio: 0.0,
        presence_bbox: None,
        body_text_lines: row["body_text_lines"].as_u64().unwrap_or(0) as usize,
        text_characters: 0,
        blank: row["blank"].as_bool().unwrap_or(false),
        ink_free: row["ink_free"].as_bool().unwrap_or(false),
        sparse: row["sparse"].as_bool().unwrap_or(false),
        standalone_punctuation_lines: row["standalone_punctuation_lines"]
            .as_array()
            .map(|lines| {
                lines
                    .iter()
                    .map(|line| line.as_str().expect("a line").to_string())
                    .collect()
            })
            .unwrap_or_default(),
    }
}

fn annotation_of(row: &Value) -> rules::PageAnnotation {
    rules::PageAnnotation {
        inspection: inspection_of(row),
        largest_void: None,
        voids: row["voids"]
            .as_array()
            .map(|voids| voids.iter().map(void_of).collect())
            .unwrap_or_default(),
        tail_band: band_of(&row["tail_band"]),
    }
}

fn annotations_of(rows: &Value) -> Vec<rules::PageAnnotation> {
    rows.as_array()
        .expect("rows")
        .iter()
        .map(annotation_of)
        .collect()
}

fn inspections_of(rows: &Value) -> Vec<inspect::PageInspection> {
    rows.as_array()
        .expect("rows")
        .iter()
        .map(inspection_of)
        .collect()
}

fn leg_of(spec: &Value) -> rules::Leg {
    let strings = |key: &str| -> Vec<String> {
        spec[key]
            .as_array()
            .expect("text rows")
            .iter()
            .map(|value| value.as_str().expect("a string").to_string())
            .collect()
    };
    rules::Leg {
        raw: strings("raw"),
        normalized: strings("normalized"),
        media: spec["media"]
            .as_array()
            .expect("media")
            .iter()
            .map(|size| {
                [
                    0.0,
                    0.0,
                    size[0].as_f64().expect("width"),
                    size[1].as_f64().expect("height"),
                ]
            })
            .collect(),
    }
}

fn spreads_of(value: &Value) -> Vec<rules::Spread> {
    value
        .as_array()
        .expect("spreads")
        .iter()
        .map(|row| rules::Spread {
            side: row["side"].as_u64().expect("side") as usize,
            sheet: row["sheet"].as_u64().expect("sheet") as usize,
            face: if row["face"] == json!("outside") {
                "outside"
            } else {
                "inside"
            },
            left_reader_page: row["left_reader_page"].as_u64().map(|page| page as usize),
            right_reader_page: row["right_reader_page"].as_u64().map(|page| page as usize),
            text_order_matches: row["text_order_matches"].as_bool().expect("matches"),
        })
        .collect()
}

fn numbers_of(value: &Value) -> Vec<usize> {
    value
        .as_array()
        .expect("numbers")
        .iter()
        .map(|item| item.as_u64().expect("a number") as usize)
        .collect()
}

fn slugs_of(value: &Value) -> BTreeMap<String, usize> {
    value
        .as_object()
        .expect("a mapping")
        .iter()
        .map(|(slug, page)| (slug.clone(), page.as_u64().expect("a page") as usize))
        .collect()
}

fn issue_rows(recorder: &rules::Recorder) -> Value {
    canon(&Value::Array(
        recorder.issues.iter().map(rules::Issue::as_row).collect(),
    ))
}

fn bits_of(value: &Value) -> f64 {
    let text = value.as_str().expect("a canonical float");
    f64::from_bits(u64::from_str_radix(&text[1..], 16).expect("a bit pattern"))
}

fn flag_rows(flags: &[rules::FlagCrop]) -> Value {
    canon(&Value::Array(
        flags
            .iter()
            .map(|flag| {
                json!({
                    "page": flag.page,
                    "kind": flag.kind,
                    "span": flag.span.map(|(from, to)| vec![from, to]),
                })
            })
            .collect(),
    ))
}

fn dummy_rasters(counts: &Value) -> inspect::ReviewRasters {
    let list = |index: usize| -> Vec<PathBuf> {
        (0..counts[index].as_u64().expect("a count"))
            .map(|number| PathBuf::from(format!("p{number}")))
            .collect()
    };
    inspect::ReviewRasters {
        reader: list(0),
        booklet: list(1),
        cover_booklet: list(2),
    }
}

#[test]
fn imposition_checks_match_python_on_the_fixtures() {
    for case in cases("imposition") {
        let legs = rules::Legs {
            reader: leg_of(&case["reader"]),
            booklet: leg_of(&case["booklet"]),
            interior: leg_of(&case["interior"]),
            cover: leg_of(&case["cover"]),
        };
        let mut recorder = rules::Recorder::default();
        let produced =
            rules::imposition_checks(&mut recorder, &legs, &dummy_rasters(&case["rendered"]))
                .expect("the fixture is judged");
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(
            spread_rows(&produced.spreads),
            case["spreads"],
            "spreads for {name}"
        );
        assert_eq!(
            spread_rows(&produced.interior_spreads),
            case["interior_spreads"],
            "interior spreads for {name}"
        );
        assert_eq!(
            spread_rows(&produced.cover_spreads),
            case["cover_spreads"],
            "cover spreads for {name}"
        );
        assert_eq!(
            canon(&json!(produced.interior_pages)),
            case["interior_pages"],
            "interior pages for {name}"
        );
        assert_eq!(
            canon(&json!(produced.cover_pages)),
            case["cover_pages"],
            "cover pages for {name}"
        );
    }
}

#[test]
fn page_row_issues_match_python_on_the_fixtures() {
    for case in cases("page_rows") {
        let rows = annotations_of(&case["rows"]);
        let inside: std::collections::BTreeSet<usize> = numbers_of(&case["inside_cover_pages"])
            .into_iter()
            .collect();
        let lasts: std::collections::BTreeSet<usize> =
            numbers_of(&case["last_page_numbers"]).into_iter().collect();
        let article_lasts = slugs_of(&case["article_last_pages"]);
        let live = case["live_area_points"].as_array().map(|edges| {
            let values: Vec<f64> = edges
                .iter()
                .map(|edge| edge.as_f64().expect("an edge"))
                .collect();
            [values[0], values[1], values[2], values[3]]
        });
        let mut recorder = rules::Recorder::default();
        let flags = rules::page_row_issues(
            &mut recorder,
            &rows,
            &rules::RowContext {
                inside_cover_pages: &inside,
                last_page_numbers: &lasts,
                live_area_points: live,
                article_last_pages: &article_lasts,
            },
        );
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(
            flag_rows(&flags),
            case["flag_crops"],
            "flag crops for {name}"
        );
    }
}

#[test]
fn stub_and_tail_issues_match_python_on_the_fixtures() {
    for case in cases("stub_and_tail") {
        let rows = annotations_of(&case["rows"]);
        let lasts = slugs_of(&case["article_last_pages"]);
        let mut recorder = rules::Recorder::default();
        let mut flags = vec![];
        rules::stub_and_tail_issues(&mut recorder, &lasts, &rows, &case["layout"], &mut flags);
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(
            flag_rows(&flags),
            case["flag_crops"],
            "flag crops for {name}"
        );
    }
}

#[test]
fn booklet_side_issues_match_python_on_the_fixtures() {
    for case in cases("booklet_sides") {
        let inside: std::collections::BTreeSet<usize> = numbers_of(&case["inside_cover_pages"])
            .into_iter()
            .collect();
        let mut recorder = rules::Recorder::default();
        rules::booklet_side_issues(
            &mut recorder,
            &spreads_of(&case["spreads"]),
            &inspections_of(&case["booklet_rows"]),
            &inside,
            ("inside-cover-booklet-not-blank", "blank-booklet-side"),
        );
        let cover_sides = rules::booklet_side_issues(
            &mut recorder,
            &spreads_of(&case["cover_spreads"]),
            &inspections_of(&case["cover_booklet_rows"]),
            &inside,
            ("cover-booklet-inside-not-blank", "blank-cover-booklet-side"),
        );
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(
            canon(&json!(cover_sides.into_iter().collect::<Vec<usize>>())),
            case["cover_inside_sides"],
            "cover inside sides for {name}"
        );
    }
}

#[test]
fn contents_issues_match_python_on_the_fixtures() {
    for case in cases("contents") {
        let page_count = case["page_count"].as_u64().expect("page count") as usize;
        let text = case["cover_text"].as_str().expect("cover text").to_string();
        let reader = rules::Leg {
            raw: vec![text.clone(); page_count],
            normalized: vec![text; page_count],
            media: vec![[0.0, 0.0, 419.5276, 595.2756]; page_count],
        };
        let toc = slugs_of(&case["toc"]);
        let article_pages = slugs_of(&case["article_pages"]);
        let mut recorder = rules::Recorder::default();
        let cap = rules::contents_issues(
            &mut recorder,
            &reader,
            &case["layout"],
            &rules::Contents {
                toc: &toc,
                article_pages: &article_pages,
                editorial_pages: case["editorial_pages"].as_i64(),
                actual_contents_pages: case["actual_contents_pages"].as_i64().expect("actual"),
                maximum_contents_pages: case["maximum_contents_pages"].as_i64().expect("maximum"),
            },
        );
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(
            canon(&json!(cap)),
            case["editorial_page_cap"],
            "editorial cap for {name}"
        );
    }
}

fn fixture_paths(value: &Value) -> Vec<PathBuf> {
    value
        .as_array()
        .expect("paths")
        .iter()
        .map(|name| fixtures().join(name.as_str().expect("a name")))
        .collect()
}

#[test]
fn opener_offset_checks_match_python_on_the_fixtures() {
    for case in cases("opener_offset_checks") {
        let illustrated: Vec<String> = case["illustrated"]
            .as_array()
            .expect("articles")
            .iter()
            .map(|name| name.as_str().expect("an id").to_string())
            .collect();
        let toc = slugs_of(&case["toc"]);
        let mut recorder = rules::Recorder::default();
        let checks = rules::opener_offset_checks(
            &mut recorder,
            &illustrated,
            &toc,
            &fixture_paths(&case["rendered"]),
        )
        .expect("the fixture is judged");
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(canon(&json!(checks)), case["checks"], "checks for {name}");
    }
}

#[test]
fn opener_crop_fidelity_checks_match_python_on_the_fixtures() {
    for case in cases("opener_crop_fidelity_checks") {
        let mut recorder = rules::Recorder::default();
        let checks = rules::opener_crop_fidelity_checks(
            &mut recorder,
            case["crops"].as_array().expect("crops"),
            &fixture_paths(&case["rendered"]),
            &fixtures(),
        )
        .expect("the fixture is judged");
        let name = label(&case);
        assert_eq!(issue_rows(&recorder), case["issues"], "issues for {name}");
        assert_eq!(canon(&json!(checks)), case["checks"], "checks for {name}");
    }
}

fn issue_sites(source: &str) -> Vec<String> {
    let mut found = vec![];
    for (at, _) in source.match_indices("issue(") {
        let tail = source[at + "issue(".len()..].trim_start();
        let Some(rest) = tail.strip_prefix('"') else {
            continue;
        };
        if let Some(end) = rest.find('"') {
            found.push(rest[..end].to_string());
        }
    }
    found
}

#[test]
fn every_issue_code_in_the_python_critic_is_exercised_by_a_fixture() {
    let expected = oracle("critic_rules_expected.json");
    let mut seen = std::collections::BTreeSet::new();
    for group in [
        "imposition",
        "page_rows",
        "stub_and_tail",
        "booklet_sides",
        "contents",
        "opener_offset_checks",
        "opener_crop_fidelity_checks",
    ] {
        for case in expected[group].as_array().expect("cases") {
            for issue in case["issues"].as_array().expect("issues") {
                seen.insert(issue["code"].as_str().expect("a code").to_string());
            }
        }
    }
    let source = std::fs::read_to_string(manifest_dir().join("../src/magazine/render_critic.py"))
        .expect("the python critic is readable");
    let sites = issue_sites(&source);
    let parsed = oracle("critic_rules_expected.json")["issue_sites"]
        .as_array()
        .expect("the oracle carries the ast-parsed issue sites")
        .clone();
    assert_eq!(
        sites,
        parsed
            .iter()
            .map(|row| row["code"].as_str().expect("a code").to_string())
            .collect::<Vec<String>>(),
        "the string scan disagrees with python's own ast parse of the issue sites"
    );
    let declared: std::collections::BTreeSet<String> = sites.iter().cloned().collect();
    assert_eq!(
        declared.len(),
        30,
        "found {} distinct codes in the python",
        declared.len()
    );
    assert_eq!(
        sites.len(),
        31,
        "the python critic must still have 31 issue sites"
    );
    assert_eq!(
        declared.difference(&seen).cloned().collect::<Vec<String>>(),
        Vec::<String>::new(),
        "python issue codes with no fixture"
    );
    assert_eq!(
        seen.difference(&declared).cloned().collect::<Vec<String>>(),
        Vec::<String>::new(),
        "fixture issue codes the python does not emit"
    );
}

fn spec_rows(specs: &[rules::CropSpec]) -> Value {
    canon(&Value::Array(
        specs
            .iter()
            .map(|spec| {
                json!({
                    "page": spec.page,
                    "kind": spec.kind,
                    "subject": spec.subject,
                    "region": spec.region,
                })
            })
            .collect(),
    ))
}

fn crop_kind(name: &str) -> &'static str {
    match name {
        "sparse" => "sparse",
        "stub" => "stub",
        "void" => "void",
        other => panic!("unknown flag kind {other}"),
    }
}

#[test]
fn crop_plans_match_python_on_the_fixtures() {
    for case in cases("crop_plan") {
        let reader = rules::Leg {
            raw: vec![],
            normalized: vec![],
            media: case["media"]
                .as_array()
                .expect("media")
                .iter()
                .map(|size| {
                    [
                        0.0,
                        0.0,
                        size[0].as_f64().expect("w"),
                        size[1].as_f64().expect("h"),
                    ]
                })
                .collect(),
        };
        let toc = slugs_of(&case["toc"]);
        let bands: BTreeMap<usize, f64> = case["printed_tail_bands"]
            .as_object()
            .expect("bands")
            .iter()
            .map(|(page, height)| {
                (
                    page.parse().expect("a page number"),
                    height.as_f64().expect("a height"),
                )
            })
            .collect();
        let rows: Vec<rules::PageAnnotation> = case["rows"]
            .as_array()
            .expect("rows")
            .iter()
            .map(|row| rules::PageAnnotation {
                inspection: inspection_of(row),
                largest_void: None,
                voids: vec![],
                tail_band: band_of(&row["tail_band"]),
            })
            .collect();
        let flags: Vec<rules::FlagCrop> = case["flag_crops"]
            .as_array()
            .expect("flags")
            .iter()
            .map(|flag| rules::FlagCrop {
                page: flag["page"].as_u64().expect("a page") as usize,
                kind: crop_kind(flag["kind"].as_str().expect("a kind")),
                span: flag["span"].as_array().map(|span| {
                    (
                        span[0].as_f64().expect("from"),
                        span[1].as_f64().expect("to"),
                    )
                }),
            })
            .collect();
        let produced =
            rules::review_crop_plan(&reader, &toc, &case["layout"], &bands, &rows, &flags);
        assert_eq!(
            spec_rows(&produced),
            case["specs"],
            "crop plan for {}",
            label(&case)
        );
    }
}

#[test]
fn crop_writing_matches_python_on_the_fixture_pdf() {
    assert!(poppler_pinned());
    let pdf = manifest_dir().join("tests/critic_inspect_fixtures/pages12.pdf");
    for case in cases("crop_writing") {
        let destination = scratch(&format!("crops-{}", label(&case)));
        let specs: Vec<rules::CropSpec> = case["specs"]
            .as_array()
            .expect("specs")
            .iter()
            .map(|spec| rules::CropSpec {
                page: spec["page"].as_u64().expect("a page") as usize,
                kind: spec["kind"].as_str().expect("a kind").to_string(),
                subject: spec["subject"].as_str().map(str::to_string),
                region: {
                    let edges: Vec<f64> = spec["region"]
                        .as_array()
                        .expect("a region")
                        .iter()
                        .map(|edge| edge.as_f64().expect("an edge"))
                        .collect();
                    [edges[0], edges[1], edges[2], edges[3]]
                },
            })
            .collect();
        let (paths, rows) =
            rules::write_review_crops(&pdf, &destination.join("crops"), &destination, &specs)
                .expect("the crops are written");
        let name = label(&case);
        assert_eq!(canon(&json!(rows)), case["rows"], "crop rows for {name}");
        let pixels = case["pixels"].as_object().expect("pixel digests");
        for path in &paths {
            let file = path
                .file_name()
                .and_then(|name| name.to_str())
                .expect("a name");
            assert_eq!(
                digest(&metrics::decode_rgb(path).expect("the crop decodes").data),
                pixels[file].as_str().expect("a digest"),
                "crop pixels for {file} in {name}"
            );
        }
        let mut left: Vec<String> = std::fs::read_dir(destination.join("crops"))
            .expect("the crop directory is readable")
            .map(|entry| {
                entry
                    .expect("an entry")
                    .file_name()
                    .to_string_lossy()
                    .to_string()
            })
            .collect();
        left.sort();
        assert_eq!(
            json!(left),
            case["left_over"],
            "the 300 dpi scratch must be gone and only crops left for {name}"
        );
    }
}

#[test]
fn void_geometry_matches_python_on_the_fixtures() {
    let rows_seen = cases("void_geometry");
    for case in &rows_seen {
        let rasters: Vec<PathBuf> = case["rasters"]
            .as_array()
            .expect("rasters")
            .iter()
            .map(|name| fixtures().join(name.as_str().expect("a name")))
            .collect();
        let mut rows: Vec<rules::PageAnnotation> = case["rows"]
            .as_array()
            .expect("rows")
            .iter()
            .map(|row| {
                let mut annotation = rules::PageAnnotation::new(inspection_of(row));
                annotation.inspection.presence_bbox =
                    row["presence_bbox"].as_array().map(|box_rect| {
                        let edges: Vec<u32> = box_rect
                            .iter()
                            .map(|edge| edge.as_u64().expect("an edge") as u32)
                            .collect();
                        [edges[0], edges[1], edges[2], edges[3]]
                    });
                annotation
            })
            .collect();
        let body: std::collections::BTreeSet<usize> =
            numbers_of(&case["body_pages"]).into_iter().collect();
        let bands: BTreeMap<usize, f64> = case["tail_bands"]
            .as_object()
            .expect("bands")
            .iter()
            .map(|(page, height)| {
                (
                    page.parse().expect("a page"),
                    height.as_f64().expect("a height"),
                )
            })
            .collect();
        let live = rules::annotate_void_geometry(&rasters, &mut rows, &body, &bands)
            .expect("the geometry is annotated");
        let name = label(case);
        assert_eq!(
            canon(&json!(live)),
            case["live_area_points"],
            "live area for {name}"
        );
        let annotated: Vec<Value> = rows
            .iter()
            .map(|row| {
                json!({
                    "page": row.inspection.page,
                    "largest_void": row.largest_void.map(|void| void.as_row()),
                    "voids": row.voids.iter().map(rules::Void::as_row).collect::<Vec<Value>>(),
                    "tail_band": row.tail_band.map(|band| band.as_row()),
                })
            })
            .collect();
        assert_eq!(
            canon(&Value::Array(annotated)),
            case["annotated"],
            "annotation for {name}"
        );
    }
    let void_counts: Vec<usize> = rows_seen
        .iter()
        .map(|case| {
            case["annotated"][0]["voids"]
                .as_array()
                .expect("voids")
                .len()
        })
        .collect();
    assert!(
        void_counts.contains(&0) && void_counts.contains(&3),
        "the void fixtures must hold an empty and a report-limited answer, found {void_counts:?}"
    );
}

#[test]
fn whitespace_normalisation_matches_python() {
    let rows = cases("normalized");
    let mut collapsed = 0;
    for case in &rows {
        let raw = case["raw"].as_str().expect("raw text");
        let produced = rules::normalized(raw);
        assert_eq!(
            canon(&json!(produced)),
            case["normalized"],
            "normalisation for {}",
            label(case)
        );
        if produced.len() < raw.len() {
            collapsed += 1;
        }
    }
    assert!(
        collapsed > 0,
        "a normalisation fixture must actually collapse whitespace"
    );
}

fn python_constants() -> BTreeMap<String, String> {
    let source = std::fs::read_to_string(manifest_dir().join("../src/magazine/render_critic.py"))
        .expect("the python critic is readable");
    source
        .lines()
        .filter_map(|line| line.split_once(" = "))
        .filter(|(name, _)| {
            !name.starts_with(' ') && name.chars().all(|c| c.is_ascii_uppercase() || c == '_')
        })
        .map(|(name, value)| (name.to_string(), value.trim().to_string()))
        .collect()
}

fn rust_constants() -> Vec<(&'static str, String)> {
    vec![
        (
            "GEOMETRY_TOLERANCE",
            format!("{:?}", rules::GEOMETRY_TOLERANCE),
        ),
        ("VOID_DOWNSAMPLE", rules::VOID_DOWNSAMPLE.to_string()),
        (
            "VOID_MIN_HEIGHT_POINTS",
            format!("{:?}", rules::VOID_MIN_HEIGHT_POINTS),
        ),
        (
            "VOID_MIN_WIDTH_FRACTION",
            format!("{:?}", rules::VOID_MIN_WIDTH_FRACTION),
        ),
        ("VOID_REPORT_LIMIT", rules::VOID_REPORT_LIMIT.to_string()),
        (
            "VOID_TRAILING_TOLERANCE_POINTS",
            format!("{:?}", rules::VOID_TRAILING_TOLERANCE_POINTS),
        ),
        (
            "TAIL_GAP_MIN_LIVE_FRACTION",
            format!("{:?}", rules::TAIL_GAP_MIN_LIVE_FRACTION),
        ),
        (
            "TAIL_BAND_HEIGHT_TOLERANCE_POINTS",
            format!("{:?}", rules::TAIL_BAND_HEIGHT_TOLERANCE_POINTS),
        ),
        (
            "TAIL_BAND_ADJACENCY_TOLERANCE_POINTS",
            format!("{:?}", rules::TAIL_BAND_ADJACENCY_TOLERANCE_POINTS),
        ),
        (
            "TAIL_BAND_SYMMETRY_TOLERANCE_POINTS",
            format!("{:?}", rules::TAIL_BAND_SYMMETRY_TOLERANCE_POINTS),
        ),
        (
            "STUB_BODY_LINE_MINIMUM",
            rules::STUB_BODY_LINE_MINIMUM.to_string(),
        ),
        (
            "DEFAULT_EDITORIAL_PAGE_CAP",
            rules::DEFAULT_EDITORIAL_PAGE_CAP.to_string(),
        ),
        ("CROP_DPI", rules::CROP_DPI.to_string()),
        (
            "OPENER_OFFSET_POINTS",
            format!("{:?}", rules::OPENER_OFFSET_POINTS),
        ),
        (
            "OPENER_OFFSET_TOLERANCE_PIXELS",
            format!("{:?}", rules::OPENER_OFFSET_TOLERANCE_PIXELS),
        ),
        (
            "OPENER_FRAME_MIN_RUN_FRACTION",
            format!("{:?}", rules::OPENER_FRAME_MIN_RUN_FRACTION),
        ),
        (
            "OPENER_CROP_FIDELITY_MAX_RGB_MAE",
            format!("{:?}", rules::OPENER_CROP_FIDELITY_MAX_RGB_MAE),
        ),
        (
            "OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES",
            format!("{:?}", rules::OPENER_CROP_FRAME_MAX_EDGE_DELTA_INCHES),
        ),
        (
            "CROP_MARGIN_POINTS",
            format!("{:?}", rules::CROP_MARGIN_POINTS),
        ),
        (
            "CROP_CAPTION_ALLOWANCE_POINTS",
            format!("{:?}", rules::CROP_CAPTION_ALLOWANCE_POINTS),
        ),
        (
            "STUB_CROP_HEIGHT_POINTS",
            format!("{:?}", rules::STUB_CROP_HEIGHT_POINTS),
        ),
        (
            "TAIL_FALLBACK_CROP_HEIGHT_POINTS",
            format!("{:?}", rules::TAIL_FALLBACK_CROP_HEIGHT_POINTS),
        ),
        (
            "OPENER_FRAME_RGB",
            format!(
                "({}, {}, {})",
                rules::OPENER_FRAME_RGB[0],
                rules::OPENER_FRAME_RGB[1],
                rules::OPENER_FRAME_RGB[2]
            ),
        ),
        (
            "OPENER_OFFSET_RGB",
            format!(
                "({}, {}, {})",
                rules::OPENER_OFFSET_RGB[0],
                rules::OPENER_OFFSET_RGB[1],
                rules::OPENER_OFFSET_RGB[2]
            ),
        ),
    ]
}

#[test]
fn every_threshold_is_read_from_the_python_source_not_from_an_oracle() {
    let python = python_constants();
    let mine = rust_constants();
    assert_eq!(mine.len(), 24, "the constant list must not shrink silently");
    for (name, value) in &mine {
        let theirs = python
            .get(*name)
            .unwrap_or_else(|| panic!("{name} is no longer declared in render_critic.py"));
        let normalised = theirs.trim_end_matches(".0");
        assert!(
            theirs == value || normalised == value.trim_end_matches(".0"),
            "{name}: python says {theirs}, rust says {value}"
        );
    }
    let source = std::fs::read_to_string(manifest_dir().join("../src/magazine/render_critic.py"))
        .expect("the python critic is readable");
    assert!(
        source.contains(&format!(
            "page_caps.get(slug, {})",
            rules::DEFAULT_ARTICLE_PAGE_CAP
        )),
        "the default article page cap is no longer {} in the python",
        rules::DEFAULT_ARTICLE_PAGE_CAP
    );
}

fn case_named<'a>(rows: &'a [Value], name: &str) -> &'a Value {
    rows.iter()
        .find(|case| case["name"] == json!(name))
        .unwrap_or_else(|| panic!("the oracle carries a case named {name}"))
}

#[test]
fn straddle_pairs_differ_from_each_other_and_from_the_fallback() {
    let pairs: [(&str, &str, &str, &str); 9] = [
        (
            "void_geometry",
            "annotated",
            "height_at_threshold",
            "height_below_threshold",
        ),
        (
            "void_geometry",
            "annotated",
            "width_at_threshold",
            "width_below_threshold",
        ),
        (
            "void_geometry",
            "annotated",
            "trailing_at_tolerance",
            "trailing_past_tolerance",
        ),
        (
            "tail_bands",
            "band",
            "height_at_tolerance",
            "height_past_tolerance",
        ),
        (
            "tail_bands",
            "band",
            "symmetry_at_tolerance",
            "symmetry_past_tolerance",
        ),
        ("abuts", "abuts", "edge_of_tolerance", "just_past_tolerance"),
        (
            "crop_fidelity",
            "row",
            "mae_at_budget",
            "mae_one_over_budget",
        ),
        (
            "crop_fidelity",
            "row",
            "frame_delta_one_pixel",
            "frame_delta_two_pixels",
        ),
        ("contents", "issues", "cap_boundary", "cap_just_over"),
    ];
    for (group, key, fitting, refusing) in pairs {
        let rows = cases(group);
        let one = &case_named(&rows, fitting)[key];
        let other = &case_named(&rows, refusing)[key];
        assert_ne!(
            one, other,
            "{group} straddle {fitting}/{refusing} has two identical sides"
        );
    }
    let offsets = cases("opener_offset");
    let inside = &case_named(&offsets, "offset_inside_tolerance")["row"];
    let outside = &case_named(&offsets, "offset_outside_tolerance")["row"];
    assert_ne!(
        inside["pass"], outside["pass"],
        "the offset straddle does not flip"
    );
    assert!(
        outside["offset_pixels"].is_array(),
        "the refusing offset case must still measure, not fall back to the no-frame refusal"
    );
    let frames = cases("frame_bbox");
    assert!(
        case_named(&frames, "opener_run_130.png@0")["bbox"].is_array()
            && case_named(&frames, "opener_run_129.png@0")["bbox"].is_null(),
        "the minimum-run straddle does not flip"
    );
}

#[test]
fn no_fixture_group_expects_only_the_fallback() {
    let empty_issue_groups = [
        "imposition",
        "page_rows",
        "stub_and_tail",
        "booklet_sides",
        "contents",
        "opener_offset_checks",
        "opener_crop_fidelity_checks",
    ];
    for group in empty_issue_groups {
        let rows = cases(group);
        let quiet = rows
            .iter()
            .filter(|case| case["issues"].as_array().expect("issues").is_empty())
            .count();
        assert!(
            quiet > 0 && quiet < rows.len(),
            "{group} must hold both a silent and a faulting case, {quiet} of {} are silent",
            rows.len()
        );
    }
    let plans = cases("crop_plan");
    assert!(
        plans
            .iter()
            .any(|case| case["specs"].as_array().expect("specs").is_empty())
            && plans
                .iter()
                .any(|case| !case["specs"].as_array().expect("specs").is_empty()),
        "the crop plan fixtures must hold an empty and a non-empty plan"
    );
    let normalised = cases("normalized");
    let unchanged = normalised
        .iter()
        .filter(|case| canon(&case["raw"]) == case["normalized"])
        .count();
    assert!(
        unchanged > 0 && unchanged < normalised.len(),
        "normalisation must hold a row equal to its input and a row that is not, found {unchanged} of {}",
        normalised.len()
    );
    let caps = cases("editorial_caps");
    let default = canon(&json!(rules::DEFAULT_EDITORIAL_PAGE_CAP));
    assert_ne!(
        case_named(&caps, "one")["cap"],
        default,
        "a declared cap of one must not be reported as the default"
    );
    assert_eq!(
        case_named(&caps, "many")["cap"],
        default,
        "a declared cap of nine must clamp to the default rather than echo its input"
    );
    let voids = cases("void_geometry");
    assert_ne!(
        case_named(&voids, "fully_inked")["annotated"],
        case_named(&voids, "height_at_threshold")["annotated"],
        "an inked page and a voided page must not annotate identically, else the skip path passes too"
    );
    assert!(
        voids.iter().any(|case| case["live_area_points"].is_null())
            && voids.iter().any(|case| !case["live_area_points"].is_null()),
        "the void fixtures must hold a live area and its absence"
    );
}
