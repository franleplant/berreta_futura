#[path = "../src/model/doc.rs"]
#[allow(dead_code)]
pub mod doc;
#[path = "../src/model/manifest.rs"]
#[allow(dead_code)]
pub mod manifest;
#[allow(dead_code)]
mod oracle;
#[path = "../src/model/records.rs"]
#[allow(dead_code)]
pub mod records;
#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::{manifest, shared};
}

#[path = "../src/cover/text.rs"]
#[allow(dead_code)]
mod text;

use manifest::{Article, Edition};
use serde_json::Value as Json;
use serde_yaml::{Mapping, Value};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

fn oracle(name: &str) -> Json {
    let path: PathBuf = Path::new(env!("CARGO_MANIFEST_DIR")).join(name);
    serde_json::from_str(&std::fs::read_to_string(&path).expect("oracle readable"))
        .expect("oracle parses")
}

fn section(data: &Json, name: &str) -> BTreeMap<String, String> {
    data[name]
        .as_object()
        .expect("section is an object")
        .iter()
        .map(|(key, value)| (key.clone(), value.as_str().expect("string").to_string()))
        .collect()
}

fn article(author: &str) -> Article {
    Article {
        id: "a1".to_string(),
        title: String::new(),
        short_title: String::new(),
        display_emphasis: String::new(),
        opener_variant: String::new(),
        author: author.to_string(),
        author_note: String::new(),
        source_ids: Vec::new(),
        manuscript: PathBuf::new(),
        content_mode: String::new(),
        figures: Vec::new(),
        minimum_reader_pages: 0,
        tail_art: None,
        source_url: None,
        opener_art: None,
        key_ideas: Vec::new(),
        dateline: None,
        extracts: Vec::new(),
    }
}

fn edition(authors: &[&str], cover: Mapping, language: &str, issue: &str, name: &str) -> Edition {
    Edition {
        id: "010".to_string(),
        publication_name: name.to_string(),
        issue_number: issue.to_string(),
        title: String::new(),
        publication_date: String::new(),
        language: language.to_string(),
        locale: String::new(),
        editorial: None,
        articles: authors.iter().map(|value| article(value)).collect(),
        sections: Vec::new(),
        cover,
        cover_art: None,
        closing_plates: Vec::new(),
        raw: Value::Null,
    }
}

fn plain(authors: &[&str]) -> Edition {
    edition(authors, Mapping::new(), "en", "010", "Berreta Futura")
}

fn with_deck(value: Option<Value>) -> Edition {
    let mut cover = Mapping::new();
    if let Some(value) = value {
        cover.insert(Value::String("deck".to_string()), value);
    }
    edition(&[], cover, "en", "010", "Berreta Futura")
}

fn live_010() -> Edition {
    let path = oracle::snapshot().join("editions/010/edition.yaml");
    let raw: Value = serde_yaml::from_str(&std::fs::read_to_string(&path).expect("edition.yaml"))
        .expect("edition.yaml parses");
    let authors: Vec<String> = raw["articles"]
        .as_sequence()
        .expect("articles")
        .iter()
        .map(|item| {
            item["author"]
                .as_str()
                .map(str::to_string)
                .unwrap_or_default()
        })
        .collect();
    let cover = raw["cover"].as_mapping().cloned().unwrap_or_default();
    let issue = raw["issue_number"]
        .as_i64()
        .map(|value| value.to_string())
        .expect("issue_number");
    let language = raw["language"].as_str().unwrap_or("en").to_string();
    let borrowed: Vec<&str> = authors.iter().map(String::as_str).collect();
    edition(&borrowed, cover, &language, &issue, "Berreta Futura")
}

fn contributor_cases() -> BTreeMap<String, Edition> {
    let mut cases: BTreeMap<String, Edition> = BTreeMap::new();
    let authored = [
        ("010_shape", vec!["Ada Lovelace", "Grace Hopper"]),
        ("single", vec!["Ada Lovelace"]),
        ("dup_exact", vec!["Ada Lovelace", "Ada Lovelace"]),
        ("dup_case", vec!["Ada Lovelace", "ADA LOVELACE"]),
        ("dup_casefold_sharp_s", vec!["Strasse", "STRA\u{df}E"]),
        ("strip_ascii", vec!["  Ada Lovelace  "]),
        ("strip_u001f", vec!["Ada\u{1f}", "Grace"]),
        ("blank_skipped", vec!["   ", "Ada"]),
        ("sharp_s_upper", vec!["Stra\u{df}e"]),
        ("ligature_upper", vec!["\u{fb01}re Ada"]),
    ];
    for (key, authors) in authored {
        cases.insert(key.to_string(), plain(&authors));
    }
    let decks = [
        ("deck_string", Some(Value::String("  A deck  ".to_string()))),
        ("deck_absent", None),
        ("deck_null", Some(Value::Null)),
        ("deck_int", Some(5.into())),
        ("deck_bool", Some(Value::Bool(true))),
        (
            "deck_list",
            Some(Value::Sequence(vec![
                Value::String("a".to_string()),
                Value::String("b".to_string()),
            ])),
        ),
        ("deck_empty", Some(Value::String("   ".to_string()))),
        (
            "deck_map",
            Some(serde_yaml::from_str::<Value>("{a: 1, b: x}").expect("mapping parses")),
        ),
    ];
    for (key, deck) in decks {
        cases.insert(key.to_string(), with_deck(deck));
    }
    cases.insert("edition_010".to_string(), live_010());
    cases
}

fn issue_cases() -> BTreeMap<String, Edition> {
    [
        ("en_010", "en", "010"),
        ("en_us", "en-US", "010"),
        ("es", "es", "010"),
        ("es_ar", "es-AR", "7"),
        ("pad_1", "en", "1"),
        ("wide", "en", "1234"),
        ("negative", "en", "-1"),
        ("empty_issue", "en", ""),
        ("empty_lang", "", "010"),
    ]
    .iter()
    .map(|(key, language, issue)| {
        (
            key.to_string(),
            edition(&[], Mapping::new(), language, issue, "Berreta Futura"),
        )
    })
    .chain(std::iter::once(("edition_010".to_string(), live_010())))
    .collect()
}

fn identity_cases() -> BTreeMap<String, Edition> {
    [
        ("plain", "Berreta Futura"),
        ("sharp_s", "Stra\u{df}e"),
        ("lower", "berreta futura"),
    ]
    .iter()
    .map(|(key, name)| {
        (
            key.to_string(),
            edition(&[], Mapping::new(), "en", "010", name),
        )
    })
    .chain(std::iter::once(("edition_010".to_string(), live_010())))
    .collect()
}

fn check(name: &str, cases: &BTreeMap<String, Edition>, apply: fn(&Edition) -> String) {
    let data = oracle("tests/cover_text_expected.json");
    let expected = section(&data, name);
    assert_eq!(expected.len(), cases.len(), "{name} case count");
    for (key, want) in &expected {
        let value = cases.get(key).unwrap_or_else(|| panic!("case {key} built"));
        assert_eq!(&apply(value), want, "{name} case {key}");
    }
}

#[test]
fn cover_date_matches_python() {
    let data = oracle("tests/cover_text_expected.json");
    let expected = section(&data, "cover_date");
    assert_eq!(expected.len(), 8, "case count");
    for (input, want) in &expected {
        assert_eq!(&text::cover_date(input), want, "cover_date({input:?})");
    }
}

#[test]
fn a_multi_author_article_collapses_to_its_lead_author() {
    let roster = text::cover_contributors(&plain(&[
        "Ann Lee, Bo Chen & Cy Dee",
        "Ann Lee and Dan",
        "Eve",
    ]));
    assert_eq!(roster, "ANN LEE ET AL. / EVE");
}

#[test]
fn cover_contributors_matches_python() {
    check(
        "cover_contributors",
        &contributor_cases(),
        text::cover_contributors,
    );
}

#[test]
fn cover_tab_issue_matches_python() {
    check("cover_tab_issue", &issue_cases(), text::cover_tab_issue);
}

#[test]
fn cover_tab_identity_matches_python() {
    check(
        "cover_tab_identity",
        &identity_cases(),
        text::cover_tab_identity,
    );
}

#[test]
fn casefold_matches_python_over_all_codepoints() {
    let data = oracle("tests/cover_text_unicode_expected.json");
    let expected = data["casefold"].as_object().expect("casefold map");
    assert_eq!(expected.len(), 1530, "oracle entry count");
    let mut checked = 0u32;
    for code in 0..0x110000u32 {
        let Some(character) = char::from_u32(code) else {
            continue;
        };
        let want = match expected.get(&code.to_string()) {
            Some(value) => value.as_str().expect("string").to_string(),
            None => character.to_string(),
        };
        assert_eq!(
            shared::py_casefold(&character.to_string()),
            want,
            "casefold U+{code:04X}"
        );
        checked += 1;
    }
    assert!(checked > 1_000_000, "swept the plane");
}

#[test]
fn uppercase_matches_python_over_all_codepoints() {
    let data = oracle("tests/cover_text_unicode_expected.json");
    let expected = data["upper"].as_object().expect("upper map");
    assert_eq!(expected.len(), 1525, "oracle entry count");
    for code in 0..0x110000u32 {
        let Some(character) = char::from_u32(code) else {
            continue;
        };
        let want = match expected.get(&code.to_string()) {
            Some(value) => value.as_str().expect("string").to_string(),
            None => character.to_string(),
        };
        assert_eq!(
            shared::py_upper(&character.to_string()),
            want,
            "upper U+{code:04X}"
        );
    }
}

#[test]
fn python_strip_matches_python_over_all_codepoints() {
    let data = oracle("tests/cover_text_unicode_expected.json");
    let spaces: Vec<u32> = data["python_space"]
        .as_array()
        .expect("space list")
        .iter()
        .map(|value| value.as_u64().expect("codepoint") as u32)
        .collect();
    assert_eq!(spaces.len(), 29, "oracle entry count");
    for code in 0..0x110000u32 {
        let Some(character) = char::from_u32(code) else {
            continue;
        };
        let padded = format!("{character}x{character}");
        assert_eq!(
            shared::py_strip(&padded) == "x",
            spaces.contains(&code),
            "strip U+{code:04X}"
        );
    }
}

#[test]
fn zfill_matches_python_on_sign_and_width() {
    let rows = [
        ("1", "001"),
        ("-1", "-01"),
        ("+1", "+01"),
        ("", "000"),
        ("1234", "1234"),
        ("010", "010"),
        ("-", "-00"),
        ("+", "+00"),
    ];
    for (input, want) in rows {
        assert_eq!(shared::py_zfill(input, 3), want, "zfill({input:?})");
    }
}

#[test]
fn tagged_arm_has_no_python_oracle_and_unwraps() {
    let tagged: Value = serde_yaml::from_str("!mytag x").expect("serde_yaml accepts a custom tag");
    assert!(matches!(tagged, Value::Tagged(_)), "fixture is Tagged");
    assert_eq!(shared::py_str(&tagged), "x");
    let nested: Value = serde_yaml::from_str("!outer !!int 7").unwrap_or(Value::Null);
    if matches!(nested, Value::Tagged(_)) {
        assert_eq!(shared::py_str(&nested), "7");
    }
}
