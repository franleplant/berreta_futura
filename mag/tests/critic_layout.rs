use mag::critic::rules::{contents_issues, Contents, Leg, Recorder};
use mag::critic::text::{page_lines, Run};
use serde_json::json;
use std::collections::BTreeMap;

const A5: [f64; 4] = [0.0, 0.0, 419.53, 595.28];

fn run(text: &str, y: f64) -> Run {
    Run {
        text: text.into(),
        x: 40.0,
        y,
        width: 80.0,
        size: 10.0,
    }
}

fn leg(pages: &[Vec<Run>]) -> Leg {
    Leg {
        raw: pages
            .iter()
            .map(|page| page_lines(page).join("\n"))
            .collect(),
        normalized: vec![String::new(); pages.len()],
        media: vec![A5; pages.len()],
    }
}

fn codes(reader: &Leg, toc: &BTreeMap<String, usize>) -> Vec<String> {
    let mut recorder = Recorder::default();
    let article_pages = BTreeMap::new();
    contents_issues(
        &mut recorder,
        reader,
        &json!({}),
        &Contents {
            toc,
            article_pages: &article_pages,
            editorial_pages: None,
            actual_contents_pages: 1,
            maximum_contents_pages: 1,
        },
    );
    recorder.issues.into_iter().map(|row| row.code).collect()
}

fn pages(cover: &str) -> Vec<Vec<Run>> {
    vec![
        vec![run(cover, 500.0)],
        vec![],
        vec![run("Contents", 500.0)],
        vec![run("body", 400.0)],
    ]
}

#[test]
fn a_sound_layout_raises_nothing() {
    let toc = BTreeMap::from([("a".to_string(), 4)]);
    assert!(codes(&leg(&pages("BERRETA FUTURA")), &toc).is_empty());
}

#[test]
fn placeholder_cover_copy_in_the_layout_runs_fails_the_critic() {
    let toc = BTreeMap::from([("a".to_string(), 4)]);
    assert_eq!(
        codes(&leg(&pages("TODO headline")), &toc),
        ["cover-placeholder-copy"]
    );
}

#[test]
fn a_contents_folio_past_the_last_page_fails_the_critic() {
    let toc = BTreeMap::from([("a".to_string(), 9)]);
    assert_eq!(
        codes(&leg(&pages("BERRETA FUTURA")), &toc),
        ["contents-folio-range"]
    );
}

fn glyph(text: &str, x: f64, device_x: f64) -> mag::pdf_text::Glyph {
    mag::pdf_text::Glyph {
        device_x,
        x,
        y: 100.0,
        w: 6.0,
        size: 10.0,
        text: text.into(),
        mono: false,
        spaced: false,
        dir: 0,
    }
}

#[test]
fn spread_text_joins_glyphs_into_words_and_orders_halves() {
    let glyphs = [
        glyph("A", 500.0, 500.0),
        glyph("b", 10.0, 10.0),
        glyph("c", 16.0, 16.0),
        glyph("d", 40.0, 40.0),
    ];
    let media = [0.0, 0.0, 842.0, 595.0];
    assert_eq!(mag::critic::rules::spread_text(&glyphs, media), "bc d A");
}
