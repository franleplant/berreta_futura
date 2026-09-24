#[path = "../src/impose.rs"]
mod impose;

#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

use lopdf::{Document, Object, ObjectId};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/impose_fixtures")
}

fn oracle() -> Value {
    let raw = std::fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/impose_plan_expected.json"),
    )
    .expect("the committed oracle is readable");
    serde_json::from_str(&raw).expect("the oracle is json")
}

fn pairs(value: &Value) -> Vec<(Option<usize>, Option<usize>)> {
    value
        .as_array()
        .expect("a spread array")
        .iter()
        .map(|entry| {
            let items = entry.as_array().expect("a spread pair");
            (slot(&items[0]), slot(&items[1]))
        })
        .collect()
}

fn slot(value: &Value) -> Option<usize> {
    value.as_u64().map(|number| number as usize)
}

#[test]
fn plans_match_the_python_oracle() {
    let expected = oracle();
    let points = expected["a4_landscape_points"].as_array().expect("points");
    assert_eq!(
        points[0].as_f64().expect("x"),
        impose::A4_LANDSCAPE_POINTS.0
    );
    assert_eq!(
        points[1].as_f64().expect("y"),
        impose::A4_LANDSCAPE_POINTS.1
    );

    let mut checked = 0;
    for (key, value) in expected["spreads"].as_object().expect("spreads") {
        let count: usize = key.parse().expect("a page count");
        let want: Vec<(usize, usize)> = value
            .as_array()
            .expect("spreads")
            .iter()
            .map(|entry| {
                let items = entry.as_array().expect("a pair");
                (
                    items[0].as_u64().expect("left") as usize,
                    items[1].as_u64().expect("right") as usize,
                )
            })
            .collect();
        assert_eq!(impose::booklet_spreads(count), want, "spreads for {count}");
        checked += 1;
    }

    for (key, value) in expected["section_pages"].as_object().expect("sections") {
        let (count, section) = key.split_once('|').expect("count|section");
        let count: usize = count.parse().expect("a page count");
        match impose::section_reader_pages(count, section) {
            Ok(pages) => {
                let want: Vec<usize> = value["ok"]
                    .as_array()
                    .unwrap_or_else(|| panic!("{key} refuses in python but not in rust"))
                    .iter()
                    .map(|item| item.as_u64().expect("a page") as usize)
                    .collect();
                assert_eq!(pages, want, "section pages for {key}");
            }
            Err(error) => {
                let want = value["err"]
                    .as_str()
                    .unwrap_or_else(|| panic!("{key} refuses in rust but not in python"));
                assert_eq!(error.to_string(), want, "refusal for {key}");
            }
        }
        checked += 1;
    }

    for (key, value) in expected["plans"].as_object().expect("plans") {
        let pages: Vec<usize> = if let Some(length) = key.strip_prefix("seq") {
            (1..=length.parse::<usize>().expect("a length")).collect()
        } else {
            match key.as_str() {
                "gap" => vec![3, 4, 7, 8, 11],
                "single" => vec![5],
                "pair" => vec![2, 9],
                other => panic!("unknown plan fixture {other}"),
            }
        };
        assert_eq!(
            impose::imposed_reader_page_plan(&pages),
            pairs(value),
            "plan for {key}"
        );
        checked += 1;
    }

    for (key, value) in expected["cover_wrap"].as_object().expect("cover wrap") {
        let count: usize = key.parse().expect("a page count");
        match impose::cover_wrap_plan(count) {
            Ok(plan) => assert_eq!(plan, pairs(&value["ok"]), "cover wrap for {count}"),
            Err(error) => assert_eq!(
                error.to_string(),
                value["err"].as_str().expect("a refusal"),
                "cover wrap refusal for {count}"
            ),
        }
        checked += 1;
    }
    assert!(checked > 400, "the oracle shrank to {checked} cases");
}

fn normalized_display_list(path: &Path) -> Vec<String> {
    let doc = Document::load(path).expect("the pdf loads");
    let mut out = Vec::new();
    for (number, page_id) in doc.get_pages() {
        let resources = page_resource_hashes(&doc, page_id);
        let content = doc.get_page_content(page_id);
        out.push(format!("page {number}"));
        out.push(format!("mediabox {:?}", page_media(&doc, page_id)));
        if content.is_empty() {
            out.push("empty".to_string());
            continue;
        }
        let decoded = lopdf::content::Content::decode(&content).expect("the content decodes");
        for operation in decoded.operations {
            let operands: Vec<String> = operation
                .operands
                .iter()
                .map(|operand| operand_text(operand, &resources))
                .collect();
            out.push(format!("{} {}", operation.operator, operands.join(" ")));
        }
    }
    out
}

fn page_media(doc: &Document, page_id: ObjectId) -> Vec<String> {
    let mut current = page_id;
    loop {
        let Ok(dict) = doc.get_dictionary(current) else {
            return Vec::new();
        };
        if let Ok(value) = dict.get(b"MediaBox") {
            if let Ok((_, resolved)) = doc.dereference(value) {
                if let Ok(array) = resolved.as_array() {
                    return array.iter().map(|item| operand_text(item, &[])).collect();
                }
            }
        }
        match dict.get(b"Parent") {
            Ok(Object::Reference(parent)) => current = *parent,
            _ => return Vec::new(),
        }
    }
}

fn page_resource_hashes(doc: &Document, page_id: ObjectId) -> Vec<(Vec<u8>, String)> {
    let mut out = Vec::new();
    let Ok((direct, inherited)) = doc.get_page_resources(page_id) else {
        return out;
    };
    let mut dicts: Vec<&lopdf::Dictionary> = inherited
        .iter()
        .filter_map(|id| doc.get_dictionary(*id).ok())
        .collect();
    if let Some(dict) = direct {
        dicts.push(dict);
    }
    for dict in dicts {
        for (_, category) in dict {
            let Ok(entries) = category.as_dict() else {
                continue;
            };
            for (name, value) in entries {
                out.push((name.to_vec(), object_digest(doc, value, 0)));
            }
        }
    }
    out
}

fn object_digest(doc: &Document, object: &Object, depth: usize) -> String {
    if depth > 6 {
        return "deep".to_string();
    }
    let mut hasher = Sha256::new();
    match object {
        Object::Reference(id) => match doc.get_object(*id) {
            Ok(resolved) => return object_digest(doc, resolved, depth + 1),
            Err(_) => hasher.update(b"missing"),
        },
        Object::Stream(stream) => {
            hasher.update(b"stream");
            hasher.update(
                stream
                    .decompressed_content()
                    .unwrap_or(stream.content.clone()),
            );
            for (key, value) in &stream.dict {
                if key != b"Length" && key != b"Filter" && key != b"DecodeParms" {
                    hasher.update(key);
                    hasher.update(object_digest(doc, value, depth + 1));
                }
            }
        }
        Object::Dictionary(dict) => {
            hasher.update(b"dict");
            for (key, value) in dict {
                hasher.update(key);
                hasher.update(object_digest(doc, value, depth + 1));
            }
        }
        Object::Array(items) => {
            hasher.update(b"array");
            for item in items {
                hasher.update(object_digest(doc, item, depth + 1));
            }
        }
        other => hasher.update(format!("{other:?}")),
    }
    hex::encode(&hasher.finalize()[..8])
}

fn operand_text(operand: &Object, resources: &[(Vec<u8>, String)]) -> String {
    match operand {
        Object::Name(name) => resources
            .iter()
            .find(|(key, _)| key == name)
            .map(|(_, digest)| format!("res:{digest}"))
            .unwrap_or_else(|| format!("/{}", String::from_utf8_lossy(name))),
        Object::Integer(value) => format!("{:.6}", *value as f64),
        Object::Real(value) => format!("{:.6}", f64::from(*value)),
        Object::String(bytes, _) => format!("({})", hex::encode(bytes)),
        Object::Array(items) => {
            let inner: Vec<String> = items
                .iter()
                .map(|item| operand_text(item, resources))
                .collect();
            format!("[{}]", inner.join(" "))
        }
        other => format!("{other:?}"),
    }
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

fn rasterize(path: &Path, tag: &str) -> Vec<String> {
    let dir = std::env::temp_dir().join(format!("wp52-raster-{tag}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("the raster directory is writable");
    let status = std::process::Command::new("pdftoppm")
        .args(["-r", "150"])
        .arg(path)
        .arg(dir.join("page"))
        .status()
        .expect("pdftoppm runs");
    assert!(status.success(), "pdftoppm failed on {}", path.display());
    let mut pages: Vec<PathBuf> = std::fs::read_dir(&dir)
        .expect("the raster directory is readable")
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .collect();
    pages.sort();
    pages
        .iter()
        .map(|page| {
            let bytes = std::fs::read(page).expect("a raster page is readable");
            let mut hasher = Sha256::new();
            hasher.update(&bytes);
            format!(
                "{} bytes {}",
                bytes.len(),
                hex::encode(&hasher.finalize()[..8])
            )
        })
        .collect()
}

fn page_text(path: &Path, tag: &str) -> String {
    let out = std::env::temp_dir().join(format!("wp52-text-{tag}.txt"));
    let status = std::process::Command::new("pdftotext")
        .arg(path)
        .arg(&out)
        .status()
        .expect("pdftotext runs");
    assert!(status.success(), "pdftotext failed on {}", path.display());
    std::fs::read_to_string(&out).expect("the text dump is readable")
}

#[test]
fn rasters_and_text_match_the_python_oracle() {
    assert!(poppler_pinned());
    let dir = fixtures();
    let mut compared = 0;
    for entry in std::fs::read_dir(&dir).expect("the fixture directory exists") {
        let path = entry.expect("a fixture entry").path();
        let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
            continue;
        };
        let Some(stem) = name.strip_suffix(".src.pdf") else {
            continue;
        };
        for section in ["all", "interior", "cover"] {
            let expected = dir.join(format!("{stem}.{section}.pdf"));
            if !expected.exists() {
                continue;
            }
            let produced = std::env::temp_dir().join(format!("wp52-r-{stem}-{section}.pdf"));
            impose::impose_a5_on_a4(&path, &produced, section).expect("imposition succeeds");
            let tag = format!("{stem}-{section}");
            let mine = Document::load(&produced).expect("the port output loads");
            let theirs = Document::load(&expected).expect("the oracle loads");
            assert_eq!(
                mine.get_pages().len(),
                theirs.get_pages().len(),
                "sheet count for {tag}"
            );
            if theirs.get_pages().is_empty() {
                compared += 1;
                continue;
            }
            assert_eq!(
                rasterize(&produced, &format!("{tag}-mine")),
                rasterize(&expected, &format!("{tag}-theirs")),
                "rasters for {tag}"
            );
            assert_eq!(
                page_text(&produced, &format!("{tag}-mine")),
                page_text(&expected, &format!("{tag}-theirs")),
                "spread order text for {tag}"
            );
            compared += 1;
        }
    }
    assert!(compared >= 9, "only {compared} raster cases compared");
}

#[test]
fn imposition_matches_python_on_the_live_edition() {
    let reader = std::env::var("MAG_IMPOSE_READER").ok();
    let oracles = std::env::var("MAG_IMPOSE_ORACLE_DIR").ok();
    let (reader, oracles) = match (reader, oracles) {
        (None, None) => return,
        (Some(reader), Some(oracles)) => (PathBuf::from(reader), PathBuf::from(oracles)),
        _ => panic!("set both MAG_IMPOSE_READER and MAG_IMPOSE_ORACLE_DIR, or neither"),
    };
    assert!(poppler_pinned());
    for section in ["all", "interior", "cover"] {
        let expected = oracles.join(format!("py.{section}.pdf"));
        let produced = oracles.join(format!("rs.{section}.pdf"));
        impose::impose_a5_on_a4(&reader, &produced, section).expect("imposition succeeds");
        assert_eq!(
            normalized_display_list(&produced),
            normalized_display_list(&expected),
            "display list for edition {section}"
        );
        assert_eq!(
            page_text(&produced, &format!("live-{section}-mine")),
            page_text(&expected, &format!("live-{section}-theirs")),
            "spread order text for edition {section}"
        );
        let mine = Document::load(&produced).expect("the port output loads");
        let theirs = Document::load(&expected).expect("the oracle loads");
        assert_eq!(
            mine.get_pages().len(),
            theirs.get_pages().len(),
            "sheet count for {section}"
        );
        for sheet in 1..=theirs.get_pages().len() {
            assert_eq!(
                rasterize_page(&produced, sheet, "live-mine"),
                rasterize_page(&expected, sheet, "live-theirs"),
                "raster for edition {section} sheet {sheet}"
            );
        }
    }
}

fn rasterize_page(path: &Path, page: usize, tag: &str) -> String {
    let dir = std::env::temp_dir().join(format!("wp52-live-{tag}"));
    std::fs::create_dir_all(&dir).expect("the raster directory is writable");
    let prefix = dir.join("sheet");
    let status = std::process::Command::new("pdftoppm")
        .args([
            "-r",
            "150",
            "-f",
            &page.to_string(),
            "-l",
            &page.to_string(),
        ])
        .arg(path)
        .arg(&prefix)
        .status()
        .expect("pdftoppm runs");
    assert!(status.success(), "pdftoppm failed on {}", path.display());
    let mut found = Vec::new();
    for entry in std::fs::read_dir(&dir).expect("the raster directory is readable") {
        let file = entry.expect("a raster entry").path();
        let bytes = std::fs::read(&file).expect("a raster page is readable");
        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        found.push(format!(
            "{} bytes {}",
            bytes.len(),
            hex::encode(&hasher.finalize()[..8])
        ));
        std::fs::remove_file(&file).expect("the raster page is removable");
    }
    assert_eq!(found.len(), 1, "one raster page for sheet {page}");
    found.remove(0)
}

#[test]
fn imposition_matches_the_python_oracle() {
    let dir = fixtures();
    let mut compared = 0;
    for entry in std::fs::read_dir(&dir).expect("the fixture directory exists") {
        let path = entry.expect("a fixture entry").path();
        let Some(name) = path.file_name().and_then(|name| name.to_str()) else {
            continue;
        };
        let Some(stem) = name.strip_suffix(".src.pdf") else {
            continue;
        };
        for section in ["all", "interior", "cover"] {
            let expected = dir.join(format!("{stem}.{section}.pdf"));
            if !expected.exists() {
                continue;
            }
            let produced = std::env::temp_dir().join(format!("wp52-{stem}-{section}.pdf"));
            impose::impose_a5_on_a4(&path, &produced, section).expect("imposition succeeds");
            assert_eq!(
                normalized_display_list(&produced),
                normalized_display_list(&expected),
                "display list for {stem} {section}"
            );
            compared += 1;
        }
    }
    assert!(compared >= 9, "only {compared} imposition cases compared");
}

fn colliding_reader(junk: &str, tag: &str) -> PathBuf {
    use lopdf::{dictionary, Stream};
    let mut doc = Document::with_version("1.7");
    let pages_id = doc.new_object_id();
    let kids: Vec<Object> = (1..=4)
        .map(|page| {
            let font = doc.add_object(dictionary! {
                "Type" => "Font", "Subtype" => "Type1", "BaseFont" => format!("Face{page}"),
            });
            let content = format!(
                "BT /F1 12 Tf 72 500 Td (page {page}) Tj ET {junk} 0 0 0 rg 10 10 50 50 re f"
            );
            let content = doc.add_object(Stream::new(dictionary! {}, content.into_bytes()));
            let media: Vec<Object> = vec![0.into(), 0.into(), 420.into(), 595.into()];
            doc.add_object(dictionary! {
                "Type" => "Page", "Parent" => pages_id, "Contents" => content, "MediaBox" => media,
                "Resources" => dictionary! {"Font" => dictionary! {"F1" => font}},
            })
            .into()
        })
        .collect();
    doc.objects.insert(
        pages_id,
        Object::Dictionary(dictionary! {"Type" => "Pages", "Kids" => kids, "Count" => 4}),
    );
    let catalog = doc.add_object(dictionary! {"Type" => "Catalog", "Pages" => pages_id});
    doc.trailer.set("Root", catalog);
    let path = std::env::temp_dir().join(format!("wp51h-{tag}-{}.pdf", std::process::id()));
    doc.save(&path).expect("the reader saves");
    path
}

#[test]
fn a_stray_token_in_a_renamed_page_fails_loud_instead_of_truncating() {
    let clean = colliding_reader("", "clean");
    let produced = clean.with_extension("imposed.pdf");
    impose::impose_a5_on_a4(&clean, &produced, "all").expect("the clean reader imposes");
    let imposed = Document::load(&produced).expect("the sheet loads");
    let sheet = *imposed.get_pages().values().next().expect("one sheet");
    let content = String::from_utf8_lossy(&imposed.get_page_content(sheet)).into_owned();
    assert!(
        content.contains("/F1-0"),
        "the second page was renamed: {content}"
    );
    assert_eq!(content.matches(" re").count(), 4, "{content}");
    for junk in ["@", "]"] {
        let dirty = colliding_reader(junk, "dirty");
        let error = impose::impose_a5_on_a4(&dirty, &produced, "all")
            .expect_err("a stray token must not truncate a page");
        assert!(
            format!("{error:#}").contains("holds a token lopdf cannot parse"),
            "{error:#}"
        );
    }
}
