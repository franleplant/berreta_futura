#[path = "../src/model/doc.rs"]
#[allow(dead_code)]
mod doc;
#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
mod shared;

mod model {
    pub(crate) use super::doc;
}

#[path = "../src/web/text.rs"]
#[allow(dead_code)]
mod text;

use serde_json::Value;
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn settable() -> BTreeSet<u32> {
    doc::settable_codepoints(&repository().join("src/magazine/assets/fonts"))
        .expect("the vendored faces are readable")
}

fn cases() -> Value {
    serde_json::from_str(include_str!("web_text_cases.json")).expect("the case file parses")
}

fn expected() -> Value {
    serde_json::from_str(include_str!("web_text_expected.json")).expect("the oracle file parses")
}

#[test]
fn escape_matches_the_spec_authored_expectations() {
    let cases = cases();
    let rows = cases["escape"].as_array().expect("escape rows");
    assert!(rows.len() >= 10, "only {} escape rows", rows.len());
    for row in rows {
        let name = row["name"].as_str().expect("name");
        let input = row["input"].as_str().expect("input");
        for (flag, key) in [(false, "unquoted"), (true, "quoted")] {
            let want = row[key].as_str().expect("expectation");
            assert_eq!(
                text::escape(input, flag),
                want,
                "escape({input:?}, quote={flag}) for case {name}"
            );
        }
    }
}

#[test]
fn escape_replaces_the_ampersand_before_the_angle_brackets() {
    assert_eq!(text::escape("&lt;", false), "&amp;lt;");
    assert_ne!(text::escape("&lt;", false), "&lt;");
}

#[test]
fn the_quote_flag_actually_changes_the_result() {
    for input in ["say \"hi\"", "it's"] {
        assert_ne!(
            text::escape(input, false),
            text::escape(input, true),
            "the quote flag must change {input:?}, or the flag is dead"
        );
    }
    assert_eq!(text::escape("a & b", false), text::escape("a & b", true));
}

#[test]
fn composed_helpers_match_the_python_oracle() {
    let settable = settable();
    let cases = cases();
    let expected = expected();
    let rows = cases["composed"].as_array().expect("composed rows");
    assert!(rows.len() >= 10, "only {} composed rows", rows.len());
    for row in rows {
        let name = row["name"].as_str().expect("name");
        let input = row["input"].as_str().expect("input");
        let want = &expected[name];
        assert_eq!(
            text::text(input, &settable),
            want["text"].as_str().expect("text"),
            "text({input:?}) for case {name}"
        );
        assert_eq!(
            text::verbatim(input, &settable),
            want["verbatim"].as_str().expect("verbatim"),
            "verbatim({input:?}) for case {name}"
        );
        assert_eq!(
            text::attr(input, &settable),
            want["attr"].as_str().expect("attr"),
            "attr({input:?}) for case {name}"
        );
    }
}

#[test]
fn the_three_helpers_are_not_interchangeable() {
    let settable = settable();
    let quoted = "he said \"no\" today";
    assert_ne!(
        text::text(quoted, &settable),
        text::verbatim(quoted, &settable),
        "text must educate quotes where verbatim does not"
    );
    assert_ne!(
        text::verbatim(quoted, &settable),
        text::attr(quoted, &settable),
        "attr must escape the double quote where verbatim does not"
    );
}

#[test]
fn folding_discriminates_between_settable_and_unsettable() {
    let settable = settable();
    assert_eq!(text::verbatim("café", &settable), "café");
    assert_eq!(text::verbatim("a 中 b", &settable), "a ? b");
}
