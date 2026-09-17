#[path = "../src/web/markup.rs"]
mod markup;

use serde_json::Value;

fn cases() -> Vec<Value> {
    let raw = include_str!("web_markup_expected.json");
    serde_json::from_str(raw).unwrap()
}

fn line_for(name: &str) -> String {
    let raw = include_str!("web_markup_cases.json");
    let all: Vec<Value> = serde_json::from_str(raw).unwrap();
    all.iter()
        .find(|c| c["name"] == name)
        .unwrap_or_else(|| panic!("no case {name}"))
        .get("line")
        .unwrap()
        .as_str()
        .unwrap()
        .to_string()
}

#[test]
fn corpus_shapes_match_the_python_matchers() {
    let mut compared = 0;
    for case in cases() {
        if !case["corpus"].as_bool().unwrap() {
            continue;
        }
        let name = case["name"].as_str().unwrap();
        let line = line_for(name);

        assert_eq!(
            markup::is_print_only(&line),
            case["print_only"].as_bool().unwrap(),
            "print_only disagrees on {name}"
        );
        let got = markup::source_link(&line);
        match &case["source_link"] {
            Value::Null => assert!(got.is_none(), "source_link should be None on {name}"),
            want => {
                let got = got.unwrap_or_else(|| panic!("source_link should match on {name}"));
                assert_eq!(
                    got.indent,
                    want["indent"].as_str().unwrap(),
                    "indent {name}"
                );
                assert_eq!(
                    got.source_id,
                    want["source_id"].as_str().unwrap(),
                    "source_id {name}"
                );
                assert_eq!(got.href, want["href"].as_str().unwrap(), "href {name}");
            }
        }
        let got = markup::piece_opening(&line);
        match &case["piece_opening"] {
            Value::Null => assert!(got.is_none(), "piece_opening should be None on {name}"),
            want => {
                let got = got.unwrap_or_else(|| panic!("piece_opening should match on {name}"));
                assert_eq!(got.kind, want["kind"].as_str().unwrap(), "kind {name}");
                assert_eq!(got.id, want["id"].as_str().unwrap(), "id {name}");
            }
        }
        assert_eq!(
            markup::is_illustrated_opener_header(&line),
            case["illustrated_opener_header"].as_bool().unwrap(),
            "opener header disagrees on {name}"
        );
        compared += 1;
    }
    assert_eq!(compared, 12, "expected every corpus case to be compared");
}

#[test]
fn opener_source_links_survive_the_print_only_drop() {
    assert!(markup::is_print_only(&line_for("plain_source_link")));
    assert!(!markup::is_print_only(&line_for(
        "opener_source_link_after_install"
    )));
}

#[test]
fn added_attributes_no_longer_drop_web_content() {
    for name in [
        "tail_figure_extra_class",
        "tail_figure_attr_before_class",
        "tail_figure_bare",
        "closing_plate_extra_class",
    ] {
        assert!(
            markup::is_print_only(&line_for(name)),
            "{name} must still be recognised as print-only"
        );
    }

    for name in [
        "source_link_extra_attr_first",
        "source_link_reordered_attrs",
    ] {
        let line = line_for(name);
        let link = markup::source_link(&line)
            .unwrap_or_else(|| panic!("{name} must still be recognised as a source link"));
        assert_eq!(link.source_id, "s1");
        assert_eq!(link.href, "https://example.com/a");
    }

    for name in ["opener_header_extra_class", "opener_header_class_last"] {
        assert!(
            markup::is_illustrated_opener_header(&line_for(name)),
            "{name} must still be recognised as an illustrated opener"
        );
    }

    for name in [
        "piece_article_attr_before_id",
        "piece_article_deeper_indent",
    ] {
        let line = line_for(name);
        let piece = markup::piece_opening(&line)
            .unwrap_or_else(|| panic!("{name} must still be recognised as a piece"));
        assert_eq!(piece.kind, "article");
        assert_eq!(piece.id, "a1");
    }
}

#[test]
fn the_python_matchers_mishandle_those_same_shapes() {
    let mut mishandled = 0;
    for case in cases() {
        if case["corpus"].as_bool().unwrap() {
            continue;
        }
        let name = case["name"].as_str().unwrap();
        let line = line_for(name);
        let python_saw_it = case["print_only"].as_bool().unwrap()
            || !case["source_link"].is_null()
            || !case["piece_opening"].is_null()
            || case["illustrated_opener_header"].as_bool().unwrap();
        let rust_sees_it = markup::is_print_only(&line)
            || markup::source_link(&line).is_some()
            || markup::piece_opening(&line).is_some()
            || markup::is_illustrated_opener_header(&line);
        assert!(rust_sees_it, "{name} must be recognised by the port");
        if !python_saw_it {
            mishandled += 1;
        }
    }
    assert_eq!(
        mishandled, 8,
        "the recorded Python behaviour must still show eight shapes it fails to recognise"
    );
}

#[test]
fn reordered_source_link_was_worse_than_unrecognised_in_python() {
    let case = cases()
        .into_iter()
        .find(|c| c["name"] == "source_link_reordered_attrs")
        .unwrap();
    assert!(
        case["print_only"].as_bool().unwrap() && case["source_link"].is_null(),
        "python classified the reordered link as print-only and not as a source link, \
         so it was deleted from the web tree rather than merely missing its QR"
    );
    let line = line_for("source_link_reordered_attrs");
    assert!(
        markup::source_link(&line).is_some(),
        "the port recognises it at install time, which is the step that runs first \
         and rewrites it into the opener form that survives the drop"
    );
}
