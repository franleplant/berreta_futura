use crate::trace::{Element, GLYPH_QUANTUM};

const SAME_LINE_TOLERANCE: i64 = 100;
const WORD_GAP_FRACTION: f64 = 0.15;

struct Show {
    y: i64,
    x: i64,
    width: i64,
    size: i64,
    text: String,
}

fn shows(elements: &[Element]) -> Vec<Show> {
    let mut out = vec![];
    for element in elements {
        if let Element::Text {
            s, m, size, pen, ..
        } = element
        {
            if s.trim().is_empty() {
                continue;
            }
            out.push(Show {
                y: m[5],
                x: m[4],
                width: (pen[0] as f64 * GLYPH_QUANTUM * 100.0).round() as i64,
                size: *size,
                text: s.clone(),
            });
        }
    }
    out.sort_by(|a, b| b.y.cmp(&a.y).then(a.x.cmp(&b.x)));
    out
}

fn separator(previous: &Show, next: &Show) -> &'static str {
    if previous.text.ends_with(char::is_whitespace) || next.text.starts_with(char::is_whitespace) {
        return "";
    }
    let gap = next.x - (previous.x + previous.width);
    let threshold = (previous.size.max(next.size) as f64 * WORD_GAP_FRACTION) as i64;
    if gap > threshold {
        " "
    } else {
        ""
    }
}

pub fn page_lines(elements: &[Element]) -> Vec<String> {
    let mut groups: Vec<Vec<Show>> = vec![];
    for show in shows(elements) {
        match groups.last_mut() {
            Some(group) if (group[0].y - show.y).abs() <= SAME_LINE_TOLERANCE => group.push(show),
            _ => groups.push(vec![show]),
        }
    }
    groups
        .into_iter()
        .map(|mut group| {
            group.sort_by_key(|show| show.x);
            let mut line = group[0].text.clone();
            for pair in group.windows(2) {
                line.push_str(separator(&pair[0], &pair[1]));
                line.push_str(&pair[1].text);
            }
            line.trim().to_string()
        })
        .collect()
}

pub(crate) fn page_text(elements: &[Element]) -> String {
    page_lines(elements).join("\n")
}

pub(crate) fn body_text_lines(text: &str) -> usize {
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && line.chars().any(char::is_lowercase))
        .count()
}

#[cfg(test)]
mod writer_independent {
    use super::page_text;
    use crate::trace::{Color, Element, GLYPH_QUANTUM};

    fn show(s: &str, x_pt: f64, y_pt: f64, advance_pt: f64) -> Element {
        let glyphs = s.chars().count();
        let step = advance_pt / glyphs.saturating_sub(1).max(1) as f64;
        let (x, y) = ((x_pt * 100.0).round() as i64, (y_pt * 100.0).round() as i64);
        Element::Text {
            s: s.into(),
            font: "t".into(),
            size: 1000,
            fill: Color {
                family: "DeviceGray".into(),
                rgb: [0, 0, 0],
            },
            glyphs,
            gids: vec![],
            m: [1000, 0, 0, 1000, x, y],
            tr: 0,
            clip: vec![],
            origin: [x, y],
            offs: (0..glyphs)
                .map(|i| [(step * i as f64 / GLYPH_QUANTUM).round() as i64, 0])
                .collect(),
            units: s.chars().map(String::from).collect(),
            pen: [(step * glyphs as f64 / GLYPH_QUANTUM).round() as i64, 0],
        }
    }

    #[test]
    fn invisible_space_glyphs_add_no_text() {
        let plain = [
            show("every client:", 0.0, 700.0, 60.0),
            show("code", 70.0, 700.0, 20.0),
            show("next line", 0.0, 680.0, 40.0),
        ];
        let spaced = [
            show("every client: ", 0.0, 700.0, 63.0),
            show("\u{a0}", 67.0, 700.0, 0.0),
            show("code", 70.0, 700.0, 20.0),
            show("next line ", 0.0, 680.0, 43.0),
        ];
        assert_eq!(page_text(&plain), "every client: code\nnext line");
        assert_eq!(page_text(&spaced), page_text(&plain));
    }

    #[test]
    fn a_gap_encoded_word_space_counts_from_the_pen_end() {
        let spaced = [
            show("us", 0.0, 700.0, 5.0),
            show("wisely.", 12.35, 700.0, 30.0),
        ];
        let drop_cap = [
            show("O", 0.0, 700.0, 7.0),
            show("n July", 7.54, 700.0, 25.0),
        ];
        assert_eq!(page_text(&spaced), "us wisely.");
        assert_eq!(page_text(&drop_cap), "On July");
    }

    #[test]
    fn one_line_reads_left_to_right_whatever_its_baselines_order() {
        let spread = [
            show("right half", 300.0, 700.3, 40.0),
            show("left half", 20.0, 700.0, 40.0),
        ];
        assert_eq!(page_text(&spread), "left half right half");
    }
}
