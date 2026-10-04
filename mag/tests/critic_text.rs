use mag::critic::text;
use mag::trace::streams;
fn text_show(s: &str, x_pt: f64, y_pt: f64, size_pt: f64, advance_pt: f64) -> streams::Element {
    let glyphs = s.chars().count().max(2);
    let step = advance_pt / (glyphs as f64 - 1.0);
    let offs = (0..glyphs)
        .map(|i| [streams::qo(step * i as f64), 0])
        .collect();
    streams::Element::Text {
        s: s.to_string(),
        font: "Test".into(),
        size: streams::qc(size_pt),
        fill: streams::Color {
            family: "DeviceGray".into(),
            rgb: [0, 0, 0],
        },
        glyphs,
        gids: vec![],
        m: [
            streams::qc(size_pt),
            0,
            0,
            streams::qc(size_pt),
            streams::qc(x_pt),
            streams::qc(y_pt),
        ],
        tr: 0,
        clip: vec![],
        origin: [streams::qo(x_pt), streams::qo(y_pt)],
        offs,
        units: s.chars().map(String::from).collect(),
        pen: [streams::qo(step * glyphs as f64), 0],
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
