use mag::model::shared;
use serde_norway::Value;

fn label(frontmatter: &str) -> String {
    let parsed: Value = serde_norway::from_str(frontmatter).expect("frontmatter parses");
    shared::content_label("en", parsed.as_mapping().expect("mapping"), "article")
}

#[test]
fn the_null_label_straddles_the_string_none() {
    assert_eq!(
        label("label:"),
        "ARTICLE",
        "a null label declares nothing, so the UI label applies"
    );
    assert_eq!(
        label("label: None"),
        "None",
        "YAML has no None literal, so this label is the string None"
    );
    assert_ne!(
        label("label:"),
        label("label: None"),
        "a null label and a label of the string None must not render alike; \
         they did before the guard existed, which is what made the defect invisible"
    );
}

#[test]
fn every_spelling_of_null_declares_nothing() {
    for frontmatter in ["label:", "label: ~", "label: null", "label: NULL"] {
        assert_eq!(label(frontmatter), "ARTICLE", "{frontmatter}");
    }
    assert_eq!(
        label("label: \"\""),
        "ARTICLE",
        "an empty string declares nothing either, by a different route"
    );
}

#[test]
fn a_padded_label_proves_the_declared_branch_was_taken() {
    assert_eq!(
        label("label: \"  Dispatch  \""),
        "Dispatch",
        "the padding is stripped and the declared text survives"
    );
    assert_ne!(
        label("label: \"  Dispatch  \""),
        shared::ui("en", "article"),
        "this value must differ from the fallback, or the case cannot tell \
         the declared branch from the fallback branch"
    );
}
