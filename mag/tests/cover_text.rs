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
fn the_issue_number_drops_leading_zeros_and_carries_no_label() {
    let issue = |number| {
        text::cover_issue(&edition(
            &[],
            Cover::default(),
            "es-AR",
            number,
            "Berreta Futura",
        ))
    };
    assert_eq!(issue("010"), "10");
    assert_eq!(issue("7"), "7");
    assert_eq!(issue("000"), "0");
}
