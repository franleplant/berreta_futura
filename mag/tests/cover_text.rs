use mag::cover::text;
use mag::model::manifest;

use mag::model::spec::Cover;
use manifest::{Article, Edition};
use std::path::PathBuf;

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
        content_mode: mag::model::kinds::ContentMode::Article,
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

fn edition(authors: &[&str], cover: Cover, language: &str, issue: &str, name: &str) -> Edition {
    Edition {
        id: "010".to_string(),
        publication_name: name.to_string(),
        issue_number: issue.to_string(),
        title: String::new(),
        publication_date: String::new(),
        language: language.to_string(),
        articles: authors.iter().map(|value| article(value)).collect(),
        cover,
        ..Edition::default()
    }
}

fn plain(authors: &[&str]) -> Edition {
    edition(authors, Cover::default(), "en", "010", "Berreta Futura")
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
fn contributors_are_deduplicated_trimmed_and_upper_cased() {
    let roster = text::cover_contributors(&plain(&[
        "Ada Lovelace",
        "  ADA LOVELACE ",
        "   ",
        "Grace Hopper",
    ]));
    assert_eq!(roster, "ADA LOVELACE / GRACE HOPPER");
}

#[test]
fn the_issue_tab_follows_the_language_and_pads_the_number() {
    let issue = |language, number| {
        text::cover_tab_issue(&edition(
            &[],
            Cover::default(),
            language,
            number,
            "Berreta Futura",
        ))
    };
    assert_eq!(issue("en", "010"), "ISSUE 010");
    assert_eq!(issue("es-AR", "7"), "N\u{da}MERO 007");
}

#[test]
fn the_identity_tab_upper_cases_the_publication_name() {
    let identity = text::cover_tab_identity(&edition(
        &[],
        Cover::default(),
        "en",
        "010",
        "berreta futura",
    ));
    assert_eq!(identity, "BERRETA FUTURA / BUENOS AIRES");
}
