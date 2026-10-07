const SAME_LINE_TOLERANCE: i64 = 100;
const WORD_GAP_FRACTION: f64 = 0.15;

#[derive(Debug, Clone, PartialEq)]
pub struct Run {
    pub text: String,
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub size: f64,
    pub mono: bool,
}

fn hundredths(value: f64) -> i64 {
    (value * 100.0).round() as i64
}

struct Show {
    y: i64,
    x: i64,
    width: i64,
    size: i64,
    text: String,
    mono: bool,
}

fn shows(runs: &[Run]) -> Vec<Show> {
    let mut out: Vec<Show> = runs
        .iter()
        .filter(|run| !run.text.trim().is_empty())
        .map(|run| Show {
            y: hundredths(run.y),
            x: hundredths(run.x),
            width: hundredths(run.width),
            size: hundredths(run.size),
            text: run.text.clone(),
            mono: run.mono,
        })
        .collect();
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

pub fn page_lines(runs: &[Run]) -> Vec<String> {
    marked_lines(runs)
        .into_iter()
        .map(|(line, _)| line)
        .collect()
}

fn marked_lines(runs: &[Run]) -> Vec<(String, bool)> {
    let mut groups: Vec<Vec<Show>> = vec![];
    for show in shows(runs) {
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
            (line.trim().to_string(), group.iter().all(|show| show.mono))
        })
        .collect()
}

pub(crate) fn page_text(runs: &[Run]) -> String {
    page_lines(runs).join("\n")
}

pub(crate) fn prose_text(runs: &[Run]) -> String {
    marked_lines(runs)
        .into_iter()
        .filter_map(|(line, code)| (!code).then_some(line))
        .collect::<Vec<_>>()
        .join("\n")
}

pub(crate) fn body_text_lines(text: &str) -> usize {
    text.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && line.chars().any(char::is_lowercase))
        .count()
}

#[cfg(test)]
mod writer_independent {
    use super::{page_text, prose_text, Run};

    fn show(text: &str, x: f64, y: f64, width: f64) -> Run {
        Run {
            text: text.into(),
            x,
            y,
            width,
            size: 10.0,
            mono: false,
        }
    }

    #[test]
    fn prose_text_leaves_out_code_lines() {
        let code = Run {
            mono: true,
            ..show("...", 0.0, 680.0, 12.0)
        };
        let inline = Run {
            mono: true,
            ..show("FINAL(x)", 0.0, 660.0, 40.0)
        };
        let runs = [
            show("a paragraph", 0.0, 700.0, 50.0),
            code,
            inline,
            show(".", 42.0, 660.0, 2.0),
        ];
        assert_eq!(page_text(&runs), "a paragraph\n...\nFINAL(x) .");
        assert_eq!(prose_text(&runs), "a paragraph\nFINAL(x) .");
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
