#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/trace/exact.rs"]
#[allow(dead_code)]
pub mod exact;
#[path = "../src/trace/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

#[path = "../src/trace/elements.rs"]
#[allow(dead_code)]
pub mod elements;

mod trace {
    pub use super::elements::trace_elements;
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

#[path = "../src/critic/rules.rs"]
#[allow(dead_code)]
pub mod rules;

mod critic {
    pub use super::{inspect, metrics, rules, text};
}

#[path = "../src/package/preflight.rs"]
#[allow(dead_code)]
pub mod preflight;

#[path = "../src/package/contact.rs"]
#[allow(dead_code)]
pub mod contact;

#[path = "../src/package/release.rs"]
#[allow(dead_code)]
pub mod release;

#[path = "../src/package/archive.rs"]
#[allow(dead_code)]
pub mod archive;

mod package {
    pub use super::{contact, preflight};
}

use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

fn manifest_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

fn scratch(tag: &str) -> PathBuf {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("a clock after 1970")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("wp55c-{tag}-{stamp}"));
    std::fs::create_dir_all(&path).expect("the scratch directory is writable");
    path
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
    entries
        .iter()
        .map(|(alias, value)| {
            (
                alias.as_str().expect("an alias").to_string(),
                streams::Face {
                    face: value["face"].as_str().expect("a face").to_string(),
                    file: format!(
                        "{}/../{}",
                        env!("CARGO_MANIFEST_DIR"),
                        value["file"].as_str().expect("a file")
                    ),
                },
            )
        })
        .collect()
}

fn sums(path: &Path) -> Vec<(String, String)> {
    std::fs::read_to_string(path)
        .expect("SHA256SUMS is readable")
        .lines()
        .map(|line| {
            let (digest, name) = line.split_once("  ").expect("a digest line");
            (digest.to_string(), name.to_string())
        })
        .collect()
}

fn rasters(pdf: &Path) -> Vec<Vec<u8>> {
    let dir = scratch("raster");
    let status = std::process::Command::new("pdftoppm")
        .args(["-r", "110"])
        .arg(pdf)
        .arg(dir.join("page"))
        .status()
        .expect("pdftoppm runs");
    assert!(status.success(), "pdftoppm rasterized {}", pdf.display());
    let mut pages: Vec<PathBuf> = std::fs::read_dir(&dir)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .collect();
    pages.sort();
    pages
        .iter()
        .map(|page| std::fs::read(page).unwrap())
        .collect()
}

fn pdf_pages_match(ours: &Path, oracle: &Path) {
    let name = ours.file_name().unwrap().to_string_lossy();
    let pages = |pdf: &Path| lopdf::Document::load(pdf).unwrap().get_pages().len();
    assert_eq!(pages(ours), pages(oracle), "{name} page count");
    let (mine, theirs) = (rasters(ours), rasters(oracle));
    assert_eq!(
        (mine.len(), theirs.len()),
        (pages(ours), pages(oracle)),
        "{name} rasterized every page"
    );
    for (page, (a, b)) in mine.iter().zip(&theirs).enumerate() {
        assert!(a == b, "{name} page {} raster", page + 1);
    }
    println!("RASTER {name}: {} pages equal at 110 dpi", mine.len());
}

fn pixels(path: &Path) -> Vec<u8> {
    let image = metrics::decode_rgb(path).expect("a png");
    let mut out = vec![];
    out.extend(image.width.to_le_bytes());
    out.extend(image.height.to_le_bytes());
    out.extend(image.data);
    out
}

fn placements(spec: &Value) -> Vec<preflight::FigurePlacement> {
    spec["figures"]
        .as_array()
        .expect("figures")
        .iter()
        .map(|row| preflight::FigurePlacement {
            figure_id: row["figure_id"].as_str().unwrap().into(),
            article_id: row["article_id"].as_str().unwrap().into(),
            page: row["page"].as_i64().unwrap(),
            path: PathBuf::from(row["path"].as_str().unwrap()),
            pixel_dimensions: row["pixel_dimensions"].as_array().map(|pair| {
                (
                    pair[0].as_u64().unwrap() as u32,
                    pair[1].as_u64().unwrap() as u32,
                )
            }),
            box_points: row["box_points"]
                .as_array()
                .unwrap()
                .iter()
                .map(|value| value.as_f64().unwrap())
                .collect(),
            effective_ppi: row["effective_ppi"].as_f64(),
            caption: row["caption"].as_str().unwrap().into(),
            credit: row["credit"].as_str().unwrap().into(),
        })
        .collect()
}

fn counts(value: &Value) -> BTreeMap<String, usize> {
    serde_json::from_value(value.clone()).expect("a page map")
}

fn run_release(spec: &Value, destination: &Path) -> Vec<PathBuf> {
    let figures = placements(spec);
    let fonts = font_map();
    let (toc, article_pages) = (counts(&spec["toc"]), counts(&spec["article_pages"]));
    let cover_art = spec["cover_art"].as_str().map(PathBuf::from);
    release::package_release(release::Release {
        reader_pdf: Path::new(spec["reader_pdf"].as_str().unwrap()),
        destination,
        manifest: spec["manifest"].clone(),
        cover_art: cover_art.as_deref(),
        cover_art_size_points: None,
        figure_placements: &figures,
        language: spec["language"].as_str().unwrap(),
        toc: &toc,
        article_pages: &article_pages,
        editorial_pages: spec["editorial_pages"].as_i64(),
        edition_id: spec["edition_id"].as_str().unwrap(),
        recorded_review: None,
        fonts: &fonts,
    })
    .expect("the release packages")
}

fn leaf_differences(left: &Value, right: &Value, path: &str, out: &mut Vec<String>) {
    match (left, right) {
        (Value::Object(a), Value::Object(b)) if a.len() == b.len() && a.keys().eq(b.keys()) => {
            for (key, item) in a {
                leaf_differences(item, &b[key], &format!("{path}/{key}"), out);
            }
        }
        (Value::Array(a), Value::Array(b)) if a.len() == b.len() => {
            for (index, (one, other)) in a.iter().zip(b).enumerate() {
                leaf_differences(one, other, &format!("{path}[{index}]"), out);
            }
        }
        _ if left != right => out.push(path.to_string()),
        _ => {}
    }
}

fn read_json(path: &Path) -> Value {
    serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
}

fn live_env() -> Option<(Value, PathBuf, PathBuf)> {
    let names = [
        "MAG_PACKAGE_SPEC",
        "MAG_PACKAGE_ORACLE",
        "MAG_PACKAGE_TRACER_ORACLE",
    ];
    let values: Vec<Option<String>> = names.iter().map(|name| std::env::var(name).ok()).collect();
    if values.iter().all(Option::is_none) {
        println!("MODE skipped, env not set: {}", names.join(", "));
        return None;
    }
    assert!(
        values.iter().all(Option::is_some),
        "set all of {} or none",
        names.join(", ")
    );
    let values: Vec<String> = values.into_iter().flatten().collect();
    println!(
        "MODE compared the live edition: spec {} oracles {} {}",
        values[0], values[1], values[2]
    );
    Some((
        read_json(Path::new(&values[0])),
        PathBuf::from(&values[1]),
        PathBuf::from(&values[2]),
    ))
}

const PDFS: [&str; 3] = [
    "booklet-a4-cover.pdf",
    "booklet-a4-interior.pdf",
    "booklet-a4.pdf",
];

#[test]
fn edition_010_package_matches_python_per_entry() {
    let Some((spec, oracle, tracer_oracle)) = live_env() else {
        return;
    };
    let ours = scratch("live");
    let written = run_release(&spec, &ours);
    let python = sums(&oracle.join("SHA256SUMS"));
    let rust = sums(&ours.join("SHA256SUMS"));
    let names =
        |rows: &[(String, String)]| rows.iter().map(|row| row.1.clone()).collect::<Vec<_>>();
    assert_eq!(names(&rust), names(&python), "entry list and order");
    assert_eq!(written.len(), rust.len() + 1);
    let mut tally: BTreeMap<&str, usize> = BTreeMap::new();
    for ((digest, name), (python_digest, _)) in rust.iter().zip(&python) {
        assert_eq!(
            *digest,
            release::sha256(&ours.join(name)).unwrap(),
            "{name} self-digest"
        );
        let class = if digest == python_digest {
            "bytes"
        } else if name.ends_with(".png") {
            assert_eq!(
                pixels(&ours.join(name)),
                pixels(&oracle.join(name)),
                "{name} pixels"
            );
            "pixels"
        } else if PDFS.contains(&name.as_str()) {
            pdf_pages_match(&ours.join(name), &oracle.join(name));
            "pdf"
        } else {
            assert_eq!(
                name, "render-critic.json",
                "only the critic report may differ in bytes"
            );
            "report"
        };
        *tally.entry(class).or_default() += 1;
    }
    println!("CLASSES {tally:?}");
    assert_eq!(
        tally.get("bytes").copied().unwrap_or(0) + tally.get("pixels").copied().unwrap_or(0) + 4,
        rust.len()
    );

    let report = read_json(&ours.join("render-critic.json"));
    let booklet_digest = release::sha256(&ours.join("booklet-a4.pdf")).unwrap();
    assert_eq!(
        report["visual_review"]["booklet_sha256"],
        json!(booklet_digest)
    );
    let mut differences = vec![];
    leaf_differences(
        &read_json(&tracer_oracle.join("render-critic.json")),
        &report,
        "",
        &mut differences,
    );
    println!("REPORT vs tracer-text Python: {differences:?}");
    assert_eq!(differences, ["/visual_review/booklet_sha256"]);
    let mut differences = vec![];
    leaf_differences(
        &read_json(&oracle.join("render-critic.json")),
        &report,
        "",
        &mut differences,
    );
    let text_fields = differences
        .iter()
        .filter(|path| path.ends_with("/text_characters") || path.ends_with("/body_text_lines"))
        .count();
    println!(
        "REPORT vs pypdf-text Python: {} leaves, {text_fields} text fields",
        differences.len()
    );
    assert_eq!(text_fields + 1, differences.len(), "{differences:?}");

    let archive_path = archive::archive_tree(&ours, &ours.join("package.zip")).unwrap();
    let archived: Vec<String> = zip_entries(&archive_path)
        .into_iter()
        .map(|entry| entry.0[0].as_str().unwrap().to_string())
        .collect();
    let mut listed = names(&rust);
    listed.push("SHA256SUMS".into());
    listed.sort();
    assert_eq!(
        archived, listed,
        "the archive holds every packaged file and not itself"
    );
}

#[test]
fn a_failing_critic_writes_its_report_and_stops_before_preflight_and_sums() {
    let Some((mut spec, _, _)) = live_env() else {
        return;
    };
    spec["editorial_pages"] = json!(3);
    let ours = scratch("fail");
    let figures = placements(&spec);
    let fonts = font_map();
    let (toc, article_pages) = (counts(&spec["toc"]), counts(&spec["article_pages"]));
    let error = release::package_release(release::Release {
        reader_pdf: Path::new(spec["reader_pdf"].as_str().unwrap()),
        destination: &ours,
        manifest: spec["manifest"].clone(),
        cover_art: None,
        cover_art_size_points: None,
        figure_placements: &figures,
        language: "en",
        toc: &toc,
        article_pages: &article_pages,
        editorial_pages: Some(3),
        edition_id: "010",
        recorded_review: None,
        fonts: &fonts,
    })
    .unwrap_err();
    assert_eq!(
        error.to_string(),
        "Render critic rejected en reader: editorial-page-cap"
    );
    assert_eq!(
        read_json(&ours.join("render-critic.json"))["result"],
        "fail"
    );
    for absent in [
        "preflight.json",
        "SHA256SUMS",
        "booklet-a4-printing-instructions.md",
        "studio",
    ] {
        assert!(!ours.join(absent).exists(), "{absent} must not be written");
    }
}

fn review_pngs(dir: &Path) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(dir)
        .expect("a raster directory")
        .map(|entry| entry.expect("an entry").path())
        .collect();
    found.sort();
    found
}

#[test]
fn contact_sheets_match_pillow_pixels_over_the_oracle_rasters() {
    let Some((_, oracle, _)) = live_env() else {
        return;
    };
    let review = oracle.join("render-review");
    let ours = scratch("sheets");
    for (source, prefix) in [
        ("reader-pages", "reader-contact-sheet"),
        ("booklet-sides", "booklet-contact-sheet"),
    ] {
        let sheets =
            contact::write_contact_sheets(&review_pngs(&review.join(source)), &ours, prefix)
                .unwrap();
        for sheet in sheets {
            let name = sheet.file_name().unwrap();
            let (left, right) = (pixels(&sheet), pixels(&review.join(name)));
            let differing = left.iter().zip(&right).filter(|(a, b)| a != b).count();
            println!("SHEET {name:?} differing channel bytes {differing}");
            assert_eq!(differing, 0);
        }
    }
}

fn fixtures() -> PathBuf {
    manifest_dir().join("tests/package_fixtures")
}

fn expected() -> Value {
    serde_json::from_str(&std::fs::read_to_string(fixtures().join("expected.json")).unwrap())
        .unwrap()
}

fn pixel_digest(path: &Path) -> String {
    use sha2::{Digest, Sha256};
    hex::encode(Sha256::digest(pixels(path)))
}

#[test]
fn contact_sheets_match_pillow_on_equal_wide_tall_and_upscaled_pages() {
    let pages: Vec<PathBuf> = (0..17)
        .map(|index| fixtures().join(format!("pages/page-{:03}.png", index % 4 + 1)))
        .collect();
    let out = scratch("fixture-sheets");
    let sheets = contact::write_contact_sheets(&pages, &out, "fixture-sheet").unwrap();
    let names: Vec<String> = sheets
        .iter()
        .map(|path| path.file_name().unwrap().to_string_lossy().into_owned())
        .collect();
    let digests: Vec<String> = sheets.iter().map(|path| pixel_digest(path)).collect();
    assert_eq!(json!(names), expected()["sheet_names"]);
    assert_eq!(json!(digests), expected()["sheet_pixels"]);
    assert!(contact::write_contact_sheets(&[], &out, "none")
        .unwrap()
        .is_empty());
}

#[test]
fn json_writer_reproduces_python_dumps_with_indent_and_sorted_keys() {
    let expected = expected();
    assert_eq!(
        release::py_json(&expected["json_input"]),
        expected["json_text"].as_str().unwrap()
    );
}

#[test]
fn printing_instructions_and_studio_note_match_python_for_every_language_branch() {
    let expected = expected();
    for (language, text) in expected["instructions"].as_object().unwrap() {
        assert_eq!(
            release::printing_instructions(language, 56, 14, 13, 1),
            text.as_str().unwrap(),
            "{language}"
        );
        assert_eq!(
            release::studio_note(language),
            expected["studio"][language].as_str().unwrap(),
            "{language}"
        );
    }
}

#[test]
fn adopting_the_rendered_layout_moves_only_a_present_non_null_ledger() {
    let adopt =
        |mut manifest: Value| release::adopt_rendered_layout(&mut manifest).map(|()| manifest);
    let ledger = json!([{"article": "a", "art": "t1"}]);
    assert_eq!(
        adopt(json!({"edition": {"id": "010", "_rendered_tail_arts": ledger}})).unwrap(),
        json!({"edition": {"id": "010"}, "layout": {"tail_arts": ledger}})
    );
    assert_eq!(
        adopt(json!({"edition": {"_rendered_tail_arts": ledger}, "layout": {"toc": {}}})).unwrap(),
        json!({"edition": {}, "layout": {"toc": {}, "tail_arts": ledger}})
    );
    assert_eq!(
        adopt(json!({"edition": {"_rendered_tail_arts": null}})).unwrap(),
        json!({"edition": {}})
    );
    for untouched in [
        json!({"edition": "010"}),
        json!({"edition": {"id": 1}}),
        json!({"layout": 1}),
    ] {
        assert_eq!(adopt(untouched.clone()).unwrap(), untouched);
    }
    let error =
        adopt(json!({"edition": {"_rendered_tail_arts": ledger}, "layout": []})).unwrap_err();
    assert_eq!(
        error.to_string(),
        "manifest layout must be a mapping to adopt the rendered tail arts"
    );
}

#[test]
fn visual_review_status_covers_every_recorded_review_branch() {
    let dir = scratch("review");
    let (reader, booklet) = (dir.join("reader.pdf"), dir.join("booklet.pdf"));
    std::fs::write(&reader, b"reader").unwrap();
    std::fs::write(&booklet, b"booklet").unwrap();
    let (r, b) = (
        release::sha256(&reader).unwrap(),
        release::sha256(&booklet).unwrap(),
    );
    let status = |review: Option<Value>| {
        release::visual_review_status(review.as_ref(), "010", "en", &reader, &booklet)
    };
    let fresh = json!({"en": {"reader_sha256": r, "booklet_sha256": b}});
    let unrecorded = status(None).unwrap();
    assert_eq!(unrecorded["status"], "required_before_release");
    assert_eq!(unrecorded["findings"], json!([]));
    assert_eq!(unrecorded["reader_sha256"], json!(r));
    let approved = json!({"edition_id": "010", "languages": fresh, "result": "approved", "reviewer": "fran", "findings": ["ok"]});
    let row = status(Some(approved.clone())).unwrap();
    assert_eq!(
        (
            row["status"].clone(),
            row["reviewer"].clone(),
            row["findings"].clone()
        ),
        (json!("approved"), json!("fran"), json!(["ok"]))
    );
    let mut changes = approved.clone();
    changes["result"] = json!("changes_required_by_editor");
    assert_eq!(status(Some(changes)).unwrap()["status"], "changes_required");
    let mut other_edition = approved.clone();
    other_edition["edition_id"] = json!("009");
    let mut no_row = approved.clone();
    no_row["languages"] = json!({"es": fresh["en"]});
    let mut moved = approved.clone();
    moved["languages"]["en"]["booklet_sha256"] = json!("0");
    for stale in [other_edition, no_row, moved, json!({"edition_id": "010"})] {
        assert_eq!(status(Some(stale)).unwrap()["status"], "stale");
    }
    let mut spelled = approved.clone();
    spelled["findings"] = json!("ab");
    assert_eq!(
        status(Some(spelled)).unwrap()["findings"],
        json!(["a", "b"])
    );
    for (broken, message) in [
        (json!([1]), "a recorded visual review must be a mapping"),
        (
            json!({"languages": []}),
            "a recorded visual review's languages must be a mapping",
        ),
        (
            json!({"findings": null}),
            "a recorded visual review's findings must be iterable",
        ),
    ] {
        assert_eq!(status(Some(broken)).unwrap_err().to_string(), message);
    }
}

fn zip_entries(path: &Path) -> Vec<(Value, Vec<u8>)> {
    use std::io::Read;
    let bytes = std::fs::read(path).unwrap();
    let word = |at: usize| u32::from_le_bytes(bytes[at..at + 4].try_into().unwrap());
    let half = |at: usize| u16::from_le_bytes(bytes[at..at + 2].try_into().unwrap()) as usize;
    let end = bytes.len() - 22;
    assert_eq!(word(end), 0x0605_4b50);
    let mut at = word(end + 16) as usize;
    let mut entries = vec![];
    for _ in 0..half(end + 10) {
        assert_eq!(word(at), 0x0201_4b50);
        let (name_len, extra_len, comment_len) = (half(at + 28), half(at + 30), half(at + 32));
        let name = String::from_utf8(bytes[at + 46..at + 46 + name_len].to_vec()).unwrap();
        let (time, date) = (half(at + 12), half(at + 14));
        let date_time = json!([
            1980 + (date >> 9),
            (date >> 5) & 15,
            date & 31,
            time >> 11,
            (time >> 5) & 63,
            (time & 31) * 2
        ]);
        let local = word(at + 42) as usize;
        let start = local + 30 + half(local + 26) + half(local + 28);
        let packed = &bytes[start..start + word(at + 20) as usize];
        let mut data = vec![];
        flate2::read::DeflateDecoder::new(packed)
            .read_to_end(&mut data)
            .unwrap();
        entries.push((
            json!([
                name,
                date_time,
                word(at + 38),
                half(at + 10),
                word(at + 16),
                word(at + 24)
            ]),
            data,
        ));
        at += 46 + name_len + extra_len + comment_len;
    }
    entries
}

#[test]
fn archive_entries_match_python_zipfile_metadata_and_contents() {
    let tree = fixtures().join("tree");
    let out = scratch("archive").join("tree.zip");
    archive::archive_tree(&tree, &out).unwrap();
    let entries = zip_entries(&out);
    let metadata: Vec<Value> = entries.iter().map(|entry| entry.0.clone()).collect();
    assert_eq!(json!(metadata), expected()["archive_entries"]);
    for (row, data) in entries {
        assert_eq!(
            data,
            std::fs::read(tree.join(row[0].as_str().unwrap())).unwrap()
        );
    }
}
