#[path = "../src/model/doc.rs"]
#[allow(dead_code)]
mod doc;
#[path = "../src/model/manifest.rs"]
#[allow(dead_code)]
mod manifest;
#[path = "../src/model/records.rs"]
#[allow(dead_code)]
mod records;
#[path = "../src/web/semantic.rs"]
#[allow(dead_code)]
mod semantic;
#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;
#[path = "../src/web/text.rs"]
#[allow(dead_code)]
mod text;

mod model {
    pub(crate) use super::{doc, manifest, records, shared};
}

use manifest::{load_edition, Edition, LoadOptions, Records};
use semantic::{file_uri, render_html_edition, HtmlAsset};
use serde_json::{json, Value};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;

const PUBLICATION: &str = "Berreta Futura";
const RUN: &str = "editions/010/run-2026-09-13T01-34-51";

const PYTHON: &str = r#"
import dataclasses, json, sys
from pathlib import Path
from magazine.manifest import load_edition
from magazine.records import load_records
from magazine.html_edition import render_html_edition
root = Path(sys.argv[1]).resolve()
records = {record.id: record for record in load_records(root / "library" / "sources")}
out = {}
for spec in json.loads(sys.argv[2]):
    try:
        edition = load_edition(root, spec["edition"], set(records), publication_name=sys.argv[3], source_records=records)
        if "title" in spec:
            first = dataclasses.replace(edition.articles[0], title=spec["title"])
            edition = dataclasses.replace(edition, articles=(first, *edition.articles[1:]))
        if "extra" in spec:
            edition = dataclasses.replace(edition, articles=(*edition.articles, *[edition.articles[-1]] * spec["extra"]))
        if "plate" in spec:
            plate = dataclasses.replace(edition.closing_plates[0], art_path=root / spec["plate"])
            edition = dataclasses.replace(edition, closing_plates=(plate,))
        semantic = render_html_edition(edition)
        assets = [{field.name: None if getattr(asset, field.name) is None else str(getattr(asset, field.name)) for field in dataclasses.fields(asset)} for asset in semantic.assets]
        out[spec["name"]] = {"html": semantic.html, "assets": assets}
    except Exception as error:
        out[spec["name"]] = {"error": str(error)}
print(json.dumps(out))
"#;

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn link_tree(source: &Path, target: &Path) {
    std::fs::create_dir_all(target).expect("the stage directory is writable");
    for entry in std::fs::read_dir(source).expect("the source tree is readable") {
        let path = entry.expect("a directory entry").path();
        let destination = target.join(path.file_name().expect("a file name"));
        if path.is_dir() {
            link_tree(&path, &destination);
        } else {
            std::fs::hard_link(&path, &destination).expect("the stage links the file");
        }
    }
}

fn write_png(path: &Path, width: u32, height: u32) {
    let file = std::fs::File::create(path).expect("the probe image is writable");
    let mut encoder = png::Encoder::new(file, width, height);
    encoder.set_color(png::ColorType::Grayscale);
    let mut writer = encoder.write_header().expect("the header encodes");
    writer
        .write_image_data(&vec![0u8; (width * height) as usize])
        .expect("the pixels encode");
}

fn build_stage() -> PathBuf {
    let repo = repository();
    let stage = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("web-semantic-stage");
    if stage.exists() {
        std::fs::remove_dir_all(&stage).expect("the previous stage is removable");
    }
    link_tree(
        &repo.join("library/sources"),
        &stage.join("library/sources"),
    );
    link_tree(
        &repo.join("editions/010/art"),
        &stage.join("editions/010/art"),
    );
    link_tree(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/web_semantic_fixtures/wfx"),
        &stage.join("editions/wfx"),
    );
    let manifest = repo.join("editions/010/edition.yaml");
    std::fs::copy(&manifest, stage.join("editions/010/edition.yaml")).expect("the manifest copies");
    let data: serde_yaml::Value =
        serde_yaml::from_str(&std::fs::read_to_string(&manifest).expect("the manifest reads"))
            .expect("the manifest parses");
    for article in data["articles"].as_sequence().expect("articles") {
        let target = stage.join(article["manuscript"].as_str().expect("a manuscript"));
        std::fs::create_dir_all(target.parent().expect("a parent")).expect("mkdir");
        let id = article["id"].as_str().expect("an id");
        std::fs::copy(
            repo.join(RUN).join("articles").join(id).join("final.md"),
            target,
        )
        .expect("the manuscript stages");
    }
    for (name, height) in [
        ("wide.png", 584),
        ("fits.png", 586),
        ("tall.png", 2345),
        ("narrow.png", 2343),
    ] {
        write_png(&stage.join(name), 1000, height);
    }
    stage.canonicalize().expect("the stage resolves")
}

fn stage() -> &'static PathBuf {
    static STAGE: OnceLock<PathBuf> = OnceLock::new();
    STAGE.get_or_init(build_stage)
}

fn specs() -> Value {
    let title62 = "T".repeat(62);
    let title63 = "T".repeat(63);
    json!([
        {"name": "010", "edition": "010"},
        {"name": "wfx", "edition": "wfx"},
        {"name": "title62", "edition": "wfx", "title": title62},
        {"name": "title63", "edition": "wfx", "title": title63},
        {"name": "eight", "edition": "wfx", "extra": 3},
        {"name": "nine", "edition": "wfx", "extra": 4},
        {"name": "plate_wide", "edition": "wfx", "plate": "wide.png"},
        {"name": "plate_fits", "edition": "wfx", "plate": "fits.png"},
        {"name": "plate_tall", "edition": "wfx", "plate": "tall.png"},
        {"name": "plate_narrow", "edition": "wfx", "plate": "narrow.png"},
        {"name": "plate_missing", "edition": "wfx", "plate": "absent.png"},
    ])
}

fn python() -> &'static Value {
    static ORACLE: OnceLock<Value> = OnceLock::new();
    ORACLE.get_or_init(|| {
        let output = Command::new("uv")
            .args(["run", "python", "-c", PYTHON])
            .arg(stage())
            .arg(specs().to_string())
            .arg(PUBLICATION)
            .current_dir(repository())
            .output()
            .expect("uv runs");
        assert!(
            output.status.success(),
            "the Python oracle failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        serde_json::from_slice(&output.stdout).expect("the oracle prints JSON")
    })
}

fn settable() -> BTreeSet<u32> {
    doc::settable_codepoints(&repository().join("src/magazine/assets/fonts"))
        .expect("the vendored faces are readable")
}

fn load(id: &str) -> Edition {
    let root = stage();
    let records: Records = records::load_records(&root.join("library/sources"))
        .expect("the staged records load")
        .into_iter()
        .map(|record| (record.id.clone(), record))
        .collect();
    let known: BTreeSet<String> = records.keys().cloned().collect();
    load_edition(
        root,
        id,
        &known,
        &LoadOptions {
            publication_name: PUBLICATION,
            source_records: Some(&records),
            ..LoadOptions::default()
        },
    )
    .unwrap_or_else(|error| panic!("edition {id} loads: {error}"))
}

fn asset_json(asset: &HtmlAsset) -> Value {
    json!({
        "id": asset.id,
        "role": asset.role,
        "path": asset.path.to_string_lossy(),
        "src": asset.src,
        "alt_text": asset.alt_text,
        "article_id": asset.article_id,
        "figure_id": asset.figure_id,
        "source_id": asset.source_id,
        "caption": asset.caption,
        "credit": asset.credit,
        "anchor": asset.anchor,
        "layout": asset.layout,
    })
}

fn rust(spec: &Value) -> Value {
    let mut edition = load(spec["edition"].as_str().expect("an edition"));
    if let Some(title) = spec["title"].as_str() {
        edition.articles[0].title = title.to_string();
    }
    for _ in 0..spec["extra"].as_u64().unwrap_or(0) {
        let last = edition.articles.last().expect("an article").clone();
        edition.articles.push(last);
    }
    if let Some(plate) = spec["plate"].as_str() {
        edition.closing_plates.truncate(1);
        edition.closing_plates[0].art_path = stage().join(plate);
    }
    match render_html_edition(&edition, &settable()) {
        Ok(semantic) => json!({
            "html": semantic.html,
            "assets": semantic.assets.iter().map(asset_json).collect::<Vec<Value>>(),
        }),
        Err(error) => json!({"error": error.to_string()}),
    }
}

fn first_difference(left: &str, right: &str) -> String {
    let at = left
        .char_indices()
        .zip(right.chars())
        .find(|((_, a), b)| a != b)
        .map_or(left.len().min(right.len()), |((index, _), _)| index);
    let start = left[..at].rfind('\n').map_or(0, |index| index + 1);
    format!(
        "rust: {:?}\npython: {:?}",
        &left[start..(at + 120).min(left.len())],
        right.get(start..(at + 120).min(right.len())).unwrap_or("")
    )
}

fn compare(name: &str) -> Value {
    let spec = specs()
        .as_array()
        .expect("specs")
        .iter()
        .find(|spec| spec["name"] == name)
        .expect("the spec exists")
        .clone();
    let got = rust(&spec);
    let want = &python()[name];
    if let (Some(left), Some(right)) = (got["html"].as_str(), want["html"].as_str()) {
        assert!(
            left == right,
            "{name} html differs\n{}",
            first_difference(left, right)
        );
    }
    assert_eq!(&got, want, "{name} differs from html_edition");
    got
}

#[test]
fn edition_010_matches_html_edition_byte_for_byte() {
    let got = compare("010");
    let html = got["html"].as_str().expect("html");
    assert_eq!(html.matches("<article ").count(), 9);
    assert_eq!(
        html.matches("data-article-opener=\"illustrated_paper_spots_v1\"")
            .count(),
        9
    );
    assert_eq!(html.matches("<figure class=\"closing-plate\"").count(), 5);
    assert!(html.contains("data-contents-density=\"tight\""));
    assert_eq!(
        got["assets"].as_array().expect("assets").len(),
        9 + 9 + 3 + 5 + 1
    );
}

#[test]
fn the_fixture_edition_matches_html_edition_byte_for_byte() {
    let got = compare("wfx");
    let html = got["html"].as_str().expect("html");
    for needle in [
        "<section id=\"editorial\"",
        "<section id=\"section-0\" data-section-kind=\"glossary\"",
        "<section id=\"section-1\" data-section-kind=\"try_it\"",
        "<aside class=\"key-ideas\" data-key-ideas=\"2\"",
        "data-extract-id=\"the-prompt\"",
        "<blockquote><p>This is the entire prompt",
        "<ol start=\"3\" data-reference-list=\"true\">",
        "<ol><li>",
        "<ul data-reference-list=\"true\">",
        "<p class=\"standfirst\" data-name-roster=\"true\">",
        "<p data-name-roster=\"true\">",
        "<pre><code>plain fenced &lt;code&gt; &amp; \"quotes\"",
        "title=\"Link title\"",
        "<br>",
        "<hr>",
        "<figure class=\"article-tail\" data-asset-role=\"article_tail\" data-fit=\"contain\">",
        "<a class=\"source-link\"",
        "<p class=\"subtitle\">Every branch the corpus cannot reach</p>",
        "<span class=\"entry-author\">Grace Hopper, Katherine Johnson et al.</span>",
        "A DECLARED LABEL",
    ] {
        assert!(
            html.contains(needle),
            "the fixture never reaches {needle:?}"
        );
    }
    assert!(!html.contains("data-contents-density"));
}

#[test]
fn the_contents_title_limit_straddles_at_sixty_two() {
    assert!(compare("title62").get("html").is_some());
    let refused = compare("title63");
    let message = refused["error"].as_str().expect("63 characters refuse");
    assert!(message.contains("(63 characters)"), "{message}");
}

#[test]
fn the_contents_density_straddles_at_eight_entries() {
    let tight = "data-contents-density=\"tight\"";
    assert!(!compare("eight")["html"]
        .as_str()
        .expect("html")
        .contains(tight));
    assert!(compare("nine")["html"]
        .as_str()
        .expect("html")
        .contains(tight));
}

#[test]
fn the_plate_aspect_window_straddles_both_bounds() {
    assert!(compare("plate_fits").get("html").is_some());
    assert!(compare("plate_narrow").get("html").is_some());
    for name in ["plate_wide", "plate_tall"] {
        let message = compare(name)["error"].as_str().map(str::to_string);
        assert!(
            message
                .as_deref()
                .is_some_and(|message| message.contains("0.85 plate window")),
            "{name}: {message:?}"
        );
    }
    let missing = compare("plate_missing");
    assert!(missing["error"]
        .as_str()
        .is_some_and(|message| message.contains("needs a readable raster source")));
}

#[test]
fn file_uris_percent_encode_like_pathlib() {
    assert_eq!(
        file_uri(Path::new("/a b/c~d_e.f-g")),
        "file:///a%20b/c~d_e.f-g"
    );
    assert_eq!(
        file_uri(Path::new("/x/caf\u{e9}#1")),
        "file:///x/caf%C3%A9%231"
    );
}

#[test]
fn fenced_code_with_a_language_refuses_rather_than_diverging() {
    let mut edition = load("wfx");
    let editorial = edition
        .editorial
        .as_mut()
        .expect("the fixture has an editorial");
    let path = stage().join("editions/wfx/editorial-rust.md");
    std::fs::write(&path, "---\ntitle: T\n---\n\n```python\nx = 1\n```\n").expect("write");
    editorial.path = path;
    let error = render_html_edition(&edition, &settable()).expect_err("pygments is not ported");
    assert!(error.to_string().contains("\"python\""), "{error}");
}
