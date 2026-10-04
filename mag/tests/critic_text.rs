use mag::critic::text::{self, Run};

fn text_show(s: &str, x: f64, y: f64, size: f64, advance: f64) -> Run {
    let glyphs = s.chars().count().max(2) as f64;
    let advance = advance / (glyphs - 1.0) * glyphs;
    Run {
        text: s.to_string(),
        x,
        y,
        width: advance,
        size,
    }
}

#[test]
fn a_real_word_gap_yields_a_space() {
    let first = text_show("Government", 91.0, 700.0, 23.0, 120.0);
    let second = text_show("Rails", 235.0, 700.0, 23.0, 55.0);
    let lines = text::page_lines(&[first, second]);
    assert_eq!(lines.len(), 1, "same y must be one line");
    assert_eq!(
        lines[0], "Government Rails",
        "a 10.7 pt gap against a 5.75 pt threshold must yield a space"
    );
}

#[test]
fn a_kerned_join_yields_no_space() {
    let first = text_show("soft", 91.0, 700.0, 23.0, 40.0);
    let second = text_show("ware", 137.5, 700.0, 23.0, 45.0);
    let lines = text::page_lines(&[first, second]);
    assert_eq!(lines.len(), 1);
    assert_eq!(
        lines[0], "software",
        "an adjoining run must not gain a space"
    );
}
