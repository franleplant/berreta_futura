#[path = "../src/cover/text.rs"]
#[allow(dead_code)]
mod cover_text;
#[path = "../src/model/doc.rs"]
#[allow(dead_code)]
mod doc;
#[path = "../src/web/edition.rs"]
#[allow(dead_code)]
mod edition;
#[path = "../src/highlight/mod.rs"]
#[allow(dead_code)]
mod highlight;
#[path = "../src/model/manifest.rs"]
#[allow(dead_code)]
mod manifest;
#[path = "../src/web/markup.rs"]
#[allow(dead_code)]
mod markup;
#[path = "../src/typeset/media.rs"]
#[allow(dead_code)]
mod media;
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

#[allow(dead_code)]
mod oracle;

mod model {
    pub(crate) use super::{doc, manifest, records, shared};
}

mod typeset {
    pub(crate) use super::media;
}

mod cover {
    pub(crate) use super::cover_text as text;
}

use edition::{write_web_edition, WebOptions};
use manifest::{load_edition, Edition, LoadOptions, Records};
use semantic::{file_uri, render_html_edition, HtmlAsset};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const PUBLICATION: &str = "Berreta Futura";

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
    let stage = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("web-port-stage");
    if stage.exists() {
        std::fs::remove_dir_all(&stage).expect("the previous stage is removable");
    }
    link_tree(&oracle::snapshot(), &stage);
    link_tree(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/web_port_fixtures/wfx"),
        &stage.join("editions/wfx"),
    );
    for path in oracle::pinned_paths().filter(|path| path.starts_with("editions/010/art/")) {
        let target = stage.join(path);
        std::fs::create_dir_all(target.parent().expect("a parent")).expect("mkdir");
        std::fs::hard_link(oracle::pinned("web_port", path), target).expect("the art stages");
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
        {"name": "plate_jpeg", "edition": "wfx", "plate": "editions/wfx/plate-baseline.jpg"},
        {"name": "plate_progressive", "edition": "wfx", "plate": "editions/wfx/plate-progressive.jpg"},
        {"name": "plate_sliver", "edition": "wfx", "plate": "editions/wfx/plate-sliver.jpg"},
    ])
}

fn portable(text: &str) -> String {
    text.replace(&*stage().to_string_lossy(), "$STAGE")
}

fn bless(file: &str, name: &str, value: &Value) {
    static LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    if std::env::var_os("MAG_BLESS").is_none() {
        return;
    }
    let _held = LOCK.lock().expect("the bless lock");
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join(file);
    let mut all: BTreeMap<String, Value> =
        serde_json::from_str(&std::fs::read_to_string(&path).expect("reads")).expect("parses");
    all.insert(name.to_string(), value.clone());
    std::fs::write(
        &path,
        serde_json::to_string_pretty(&all).expect("json") + "\n",
    )
    .expect("writes");
}

fn compact(entry: &Value) -> Value {
    let mut entry: Value = serde_json::from_str(&portable(&entry.to_string())).expect("json");
    if let Some(html) = entry["html"].as_str() {
        entry["html"] = json!(oracle::sha256(html.as_bytes()));
    }
    entry
}

fn html_expected() -> &'static Value {
    static EXPECTED: OnceLock<Value> = OnceLock::new();
    EXPECTED.get_or_init(|| {
        let text = oracle::expectation("web_port_html_expected.json");
        serde_json::from_str(&text).expect("the expectation parses")
    })
}

fn settable() -> BTreeSet<u32> {
    doc::settable_codepoints(&repository().join("mag/assets/fonts"))
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

fn compare(name: &str) -> Value {
    let spec = specs()
        .as_array()
        .expect("specs")
        .iter()
        .find(|spec| spec["name"] == name)
        .expect("the spec exists")
        .clone();
    let got = rust(&spec);
    bless("web_port_html_expected.json", name, &compact(&got));
    if std::env::var_os("MAG_BLESS").is_some() {
        return got;
    }
    assert_eq!(
        compact(&got),
        html_expected()[name],
        "{name} differs from the committed html_edition expectation"
    );
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
        "<ol start=\"0\"><li><p>Zeroth.",
        "<ul data-reference-list=\"true\">",
        "<p class=\"standfirst\" data-name-roster=\"true\">",
        "<p data-name-roster=\"true\">",
        "<pre><code>plain fenced &lt;code&gt; &amp; \"quotes\"",
        "<pre><code class=\"language-python\"><span class=\"nd\">@dataclass</span>",
        "<pre><code class=\"language-c\"><span class=\"cp\">#include</span>",
        "<span class=\"kt\">size_t</span>",
        "<pre><code class=\"language-http\"><span class=\"nf\">POST</span>",
        "<span class=\"nt\">\"jsonrpc\"</span>",
        "<pre><code class=\"language-ts\"><span class=\"kd\">const</span>",
        "<pre><code class=\"language-YAML\"><span class=\"nt\">steps</span>",
        "<pre><code class=\"language-jsonc\">{ \"a\": 1 /* unknown",
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
    assert!(compare("plate_jpeg").get("html").is_some());
    assert!(compare("plate_progressive").get("html").is_some());
    let sliver = compare("plate_sliver");
    assert!(sliver["error"]
        .as_str()
        .is_some_and(|message| message.contains("has aspect 0.40")));
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
fn fenced_code_in_an_unported_lexer_refuses_rather_than_diverging() {
    let mut edition = load("wfx");
    let editorial = edition
        .editorial
        .as_mut()
        .expect("the fixture has an editorial");
    let path = stage().join("editions/wfx/editorial-rust.md");
    std::fs::write(&path, "---\ntitle: T\n---\n\n```go\nx := 1\n```\n").expect("write");
    editorial.path = path;
    let error = render_html_edition(&edition, &settable()).expect_err("go is not ported");
    assert!(error.to_string().contains("\"go\""), "{error}");
}

const WORDMARK: &str =
    "editions/010/source-codes/source-code-an-alignment-assessment-of-recent-cybersecurity-415f8f1a.svg";
const FAVICON: &str =
    "editions/010/source-codes/source-code-countering-misuse-of-ai-september-2026-anthropic-d957d6c9.svg";

fn web_specs() -> Value {
    json!([
        {"name": "010", "edition": "010"},
        {"name": "wfx", "edition": "wfx"},
        {"name": "chrome", "edition": "wfx", "wordmark": WORDMARK, "favicon": FAVICON,
         "headline": ["The Fixture", "Issue"],
         "alternates": [["es", "../../es/web/"], ["pt", "../../pt/web/"]]},
        {"name": "mismatch", "edition": "wfx", "wordmark": WORDMARK, "headline": ["Wrong"]},
        {"name": "010_chrome", "edition": "010", "wordmark": WORDMARK, "favicon": FAVICON},
        {"name": "010_mixed", "edition": "010", "strip_opener": 1},
        {"name": "dup_keyed", "edition": "wfx", "duplicate": 0},
        {"name": "dup_tailed", "edition": "wfx", "duplicate": 1},
        {"name": "nourl", "edition": "wfx", "drop_urls": ["claude-of-duty-prompt-md-at-main-dd93105d"]},
    ])
}

fn digests(files: &BTreeMap<String, Vec<u8>>) -> BTreeMap<String, String> {
    let digest = |bytes: &Vec<u8>| match std::str::from_utf8(bytes) {
        Ok(text) => oracle::sha256(portable(text).as_bytes()),
        Err(_) => oracle::sha256(bytes),
    };
    files
        .iter()
        .map(|(path, bytes)| (path.clone(), digest(bytes)))
        .collect()
}

fn web_expected() -> &'static Value {
    static EXPECTED: OnceLock<Value> = OnceLock::new();
    EXPECTED.get_or_init(|| {
        let text = oracle::expectation("web_port_web_expected.json");
        serde_json::from_str(&text).expect("the expectation parses")
    })
}

fn tree(root: &Path) -> BTreeMap<String, Vec<u8>> {
    fn walk(root: &Path, directory: &Path, into: &mut BTreeMap<String, Vec<u8>>) {
        for entry in std::fs::read_dir(directory).expect("the tree is readable") {
            let path = entry.expect("an entry").path();
            if path.is_dir() {
                walk(root, &path, into);
            } else {
                let relative = path.strip_prefix(root).expect("inside the root");
                into.insert(
                    relative.to_string_lossy().into_owned(),
                    std::fs::read(&path).expect("the file reads"),
                );
            }
        }
    }
    let mut files = BTreeMap::new();
    walk(root, root, &mut files);
    files
}

fn rust_web(name: &str) -> Result<PathBuf, String> {
    let spec = web_specs()
        .as_array()
        .expect("specs")
        .iter()
        .find(|spec| spec["name"] == name)
        .expect("the spec exists")
        .clone();
    let root = stage();
    let urls: BTreeMap<String, String> = records::load_records(&root.join("library/sources"))
        .expect("records")
        .into_iter()
        .filter(|record| !record.url.is_empty())
        .filter(|record| {
            !spec["drop_urls"]
                .as_array()
                .into_iter()
                .flatten()
                .any(|dropped| dropped == record.id.as_str())
        })
        .map(|record| (record.id, record.url))
        .collect();
    let wordmark = spec["wordmark"].as_str().map(|path| root.join(path));
    let favicon = spec["favicon"].as_str().map(|path| root.join(path));
    let options = WebOptions {
        wordmark: wordmark.as_deref(),
        favicon: favicon.as_deref(),
        source_urls: urls,
        headline_lines: spec["headline"].as_array().map(|lines| {
            lines
                .iter()
                .map(|line| line.as_str().expect("a line").to_string())
                .collect()
        }),
        alternates: spec["alternates"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|pair| {
                (
                    pair[0].as_str().expect("code").to_string(),
                    pair[1].as_str().expect("prefix").to_string(),
                )
            })
            .collect(),
    };
    let destination = root.join("rust-web").join(name);
    let mut edition = load(spec["edition"].as_str().expect("an edition"));
    if let Some(index) = spec["strip_opener"].as_u64() {
        edition.articles[index as usize].opener_art = None;
    }
    if let Some(index) = spec["duplicate"].as_u64() {
        let copy = edition.articles[index as usize].clone();
        edition.articles.push(copy);
    }
    write_web_edition(
        &edition,
        &settable(),
        &repository().join("mag/assets"),
        &destination,
        &options,
    )
    .map(|_| destination)
    .map_err(|error| error.to_string())
}

fn compare_tree(name: &str) -> BTreeMap<String, Vec<u8>> {
    let got = tree(&rust_web(name).unwrap_or_else(|error| panic!("{name} writes: {error}")));
    bless(
        "web_port_web_expected.json",
        name,
        &json!({"files": digests(&got)}),
    );
    if std::env::var_os("MAG_BLESS").is_some() {
        return got;
    }
    assert_eq!(
        json!({"files": digests(&got)}),
        web_expected()[name],
        "{name} differs from the committed web_edition expectation"
    );
    got
}

fn page(files: &BTreeMap<String, Vec<u8>>, path: &str) -> String {
    String::from_utf8(files[path].clone()).expect("pages are UTF-8")
}

#[test]
fn edition_010_web_tree_is_byte_identical() {
    let files = compare_tree("010");
    let pages = files
        .keys()
        .filter(|path| path.starts_with("article-"))
        .count();
    assert_eq!(pages, 9);
    let codes = files
        .keys()
        .filter(|path| path.starts_with("assets/source-code-"))
        .count();
    assert_eq!(codes, 9);
    let index = page(&files, "index.html");
    assert!(index.contains("<nav id=\"contents\" "));
    let edition = page(&files, "edition.html");
    assert_eq!(
        edition
            .matches("class=\"source-link opener-source-link\"")
            .count(),
        9
    );
    assert!(!edition.contains("class=\"article-tail\""));
    assert!(!edition.contains("class=\"closing-plate\""));
    assert!(!edition.contains("data-provenance"));
    assert!(edition.contains("<a class=\"figure-link\" href=\"assets/"));
}

#[test]
fn fixture_web_tree_is_byte_identical() {
    let files = compare_tree("wfx");
    for page_name in [
        "editorial.html",
        "section-0.html",
        "section-1.html",
        "article-keyed.html",
        "article-tailed.html",
    ] {
        assert!(files.contains_key(page_name), "no page {page_name}");
    }
    let keyed = page(&files, "article-keyed.html");
    assert!(keyed.contains("<a class=\"provenance-source\" data-source-id=\"an-alignment"));
    assert!(keyed.contains(">02</a></p>"));
    assert!(keyed.contains("rel=\"prev\" href=\"editorial.html\""));
    assert!(keyed.contains("rel=\"next\" href=\"article-tailed.html\""));
    assert!(!page(&files, "editorial.html").contains("rel=\"prev\""));
    assert!(!page(&files, "section-1.html").contains("rel=\"next\""));
    let try_it = page(&files, "section-1.html");
    assert!(try_it.contains("<span class=\"kt\">size_t</span>"));
    assert!(try_it.contains("<span class=\"sa\">f</span><span class=\"s2\">\"</span>"));
}

#[test]
fn chrome_options_are_byte_identical() {
    let files = compare_tree("chrome");
    let index = page(&files, "index.html");
    assert!(index.contains("<span class=\"cover-headline-line\">The Fixture</span>"));
    assert!(index.contains("<a class=\"cover-cue\" href=\"#contents\">"));
    assert!(index.contains("hreflang=\"pt\""));
    assert!(index.contains("rel=\"icon\""));
    assert!(files.contains_key("assets/wordmark.svg") && files.contains_key("assets/favicon.svg"));
    let mismatch = compare_tree("mismatch");
    assert!(!page(&mismatch, "index.html").contains("cover-headline-line"));
    compare_tree("010_chrome");
}

#[test]
fn an_unillustrated_article_in_an_illustrated_edition_keeps_its_link_print_only() {
    let files = compare_tree("010_mixed");
    let page = page(
        &files,
        "article-countering-misuse-of-ai-september-2026-anthropic.html",
    );
    assert!(!page.contains("class=\"article-opener\""));
    assert!(!page.contains("source-link"));
    assert!(page.contains("data-provenance"));
    let codes = files
        .keys()
        .filter(|path| path.starts_with("assets/source-code-"))
        .count();
    assert_eq!(codes, 8);
}

#[test]
fn a_source_without_an_address_is_numbered_but_not_linked() {
    let files = compare_tree("nourl");
    let keyed = page(&files, "article-keyed.html");
    assert!(keyed.contains("<span class=\"provenance-source\" data-source-id=\"claude-of-duty"));
    assert!(keyed.contains(">02</span></p>"));
}

fn compare_refusal(name: &str) -> String {
    let want = web_expected()[name]["error"]
        .as_str()
        .unwrap_or_else(|| panic!("{name}: Python did not refuse"));
    let got = rust_web(name).expect_err("the port refuses too");
    assert_eq!(portable(&got), want, "{name}: the refusals differ");
    got
}

#[test]
fn filename_collisions_refuse_like_web_edition() {
    let asset = compare_refusal("dup_keyed");
    assert!(
        asset.starts_with("web asset filename collision: 'figure-keyed-opener-figure'"),
        "{asset}"
    );
    let page = compare_refusal("dup_tailed");
    assert!(
        page.starts_with("web page filename collision: piece ids 'article-tailed'"),
        "{page}"
    );
}

#[test]
fn a_container_label_refuses_the_web_edition_instead_of_printing_brackets() {
    let mut edition = load("wfx");
    edition.articles[0].manuscript = stage().join("editions/wfx/articles/container-label.md");
    let error = write_web_edition(
        &edition,
        &settable(),
        &repository().join("mag/assets"),
        &stage().join("rust-web/container-label"),
        &WebOptions::default(),
    )
    .expect_err("a list label is not text");
    assert_eq!(error.to_string(), "Frontmatter label must be text, not []");
}
