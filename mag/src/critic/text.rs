use anyhow::Result;
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::OnceLock;

use crate::model::shared::py_strip;
use crate::trace::{trace_elements, Element, TextFace, GLYPH_QUANTUM};

const SAME_LINE_TOLERANCE: i64 = 100;
const WORD_GAP_FRACTION: f64 = 0.15;

const LOWERCASE_RANGES: &str = "61-7a;aa;b5;ba;df-f6;f8-ff;101;103;105;107;109;10b;10d;10f;111;113;115;117;119;11b;11d;11f;121;123;125;127;129;12b;12d;12f;131;133;135;137-138;13a;13c;13e;140;142;144;146;148-149;14b;14d;14f;151;153;155;157;159;15b;15d;15f;161;163;165;167;169;16b;16d;16f;171;173;175;177;17a;17c;17e-180;183;185;188;18c-18d;192;195;199-19b;19e;1a1;1a3;1a5;1a8;1aa-1ab;1ad;1b0;1b4;1b6;1b9-1ba;1bd-1bf;1c6;1c9;1cc;1ce;1d0;1d2;1d4;1d6;1d8;1da;1dc-1dd;1df;1e1;1e3;1e5;1e7;1e9;1eb;1ed;1ef-1f0;1f3;1f5;1f9;1fb;1fd;1ff;201;203;205;207;209;20b;20d;20f;211;213;215;217;219;21b;21d;21f;221;223;225;227;229;22b;22d;22f;231;233-239;23c;23f-240;242;247;249;24b;24d;24f-293;295-2b8;2c0-2c1;2e0-2e4;345;371;373;377;37a-37d;390;3ac-3ce;3d0-3d1;3d5-3d7;3d9;3db;3dd;3df;3e1;3e3;3e5;3e7;3e9;3eb;3ed;3ef-3f3;3f5;3f8;3fb-3fc;430-45f;461;463;465;467;469;46b;46d;46f;471;473;475;477;479;47b;47d;47f;481;48b;48d;48f;491;493;495;497;499;49b;49d;49f;4a1;4a3;4a5;4a7;4a9;4ab;4ad;4af;4b1;4b3;4b5;4b7;4b9;4bb;4bd;4bf;4c2;4c4;4c6;4c8;4ca;4cc;4ce-4cf;4d1;4d3;4d5;4d7;4d9;4db;4dd;4df;4e1;4e3;4e5;4e7;4e9;4eb;4ed;4ef;4f1;4f3;4f5;4f7;4f9;4fb;4fd;4ff;501;503;505;507;509;50b;50d;50f;511;513;515;517;519;51b;51d;51f;521;523;525;527;529;52b;52d;52f;560-588;10d0-10fa;10fc-10ff;13f8-13fd;1c80-1c88;1d00-1dbf;1e01;1e03;1e05;1e07;1e09;1e0b;1e0d;1e0f;1e11;1e13;1e15;1e17;1e19;1e1b;1e1d;1e1f;1e21;1e23;1e25;1e27;1e29;1e2b;1e2d;1e2f;1e31;1e33;1e35;1e37;1e39;1e3b;1e3d;1e3f;1e41;1e43;1e45;1e47;1e49;1e4b;1e4d;1e4f;1e51;1e53;1e55;1e57;1e59;1e5b;1e5d;1e5f;1e61;1e63;1e65;1e67;1e69;1e6b;1e6d;1e6f;1e71;1e73;1e75;1e77;1e79;1e7b;1e7d;1e7f;1e81;1e83;1e85;1e87;1e89;1e8b;1e8d;1e8f;1e91;1e93;1e95-1e9d;1e9f;1ea1;1ea3;1ea5;1ea7;1ea9;1eab;1ead;1eaf;1eb1;1eb3;1eb5;1eb7;1eb9;1ebb;1ebd;1ebf;1ec1;1ec3;1ec5;1ec7;1ec9;1ecb;1ecd;1ecf;1ed1;1ed3;1ed5;1ed7;1ed9;1edb;1edd;1edf;1ee1;1ee3;1ee5;1ee7;1ee9;1eeb;1eed;1eef;1ef1;1ef3;1ef5;1ef7;1ef9;1efb;1efd;1eff-1f07;1f10-1f15;1f20-1f27;1f30-1f37;1f40-1f45;1f50-1f57;1f60-1f67;1f70-1f7d;1f80-1f87;1f90-1f97;1fa0-1fa7;1fb0-1fb4;1fb6-1fb7;1fbe;1fc2-1fc4;1fc6-1fc7;1fd0-1fd3;1fd6-1fd7;1fe0-1fe7;1ff2-1ff4;1ff6-1ff7;2071;207f;2090-209c;210a;210e-210f;2113;212f;2134;2139;213c-213d;2146-2149;214e;2170-217f;2184;24d0-24e9;2c30-2c5f;2c61;2c65-2c66;2c68;2c6a;2c6c;2c71;2c73-2c74;2c76-2c7d;2c81;2c83;2c85;2c87;2c89;2c8b;2c8d;2c8f;2c91;2c93;2c95;2c97;2c99;2c9b;2c9d;2c9f;2ca1;2ca3;2ca5;2ca7;2ca9;2cab;2cad;2caf;2cb1;2cb3;2cb5;2cb7;2cb9;2cbb;2cbd;2cbf;2cc1;2cc3;2cc5;2cc7;2cc9;2ccb;2ccd;2ccf;2cd1;2cd3;2cd5;2cd7;2cd9;2cdb;2cdd;2cdf;2ce1;2ce3-2ce4;2cec;2cee;2cf3;2d00-2d25;2d27;2d2d;a641;a643;a645;a647;a649;a64b;a64d;a64f;a651;a653;a655;a657;a659;a65b;a65d;a65f;a661;a663;a665;a667;a669;a66b;a66d;a681;a683;a685;a687;a689;a68b;a68d;a68f;a691;a693;a695;a697;a699;a69b-a69d;a723;a725;a727;a729;a72b;a72d;a72f-a731;a733;a735;a737;a739;a73b;a73d;a73f;a741;a743;a745;a747;a749;a74b;a74d;a74f;a751;a753;a755;a757;a759;a75b;a75d;a75f;a761;a763;a765;a767;a769;a76b;a76d;a76f-a778;a77a;a77c;a77f;a781;a783;a785;a787;a78c;a78e;a791;a793-a795;a797;a799;a79b;a79d;a79f;a7a1;a7a3;a7a5;a7a7;a7a9;a7af;a7b5;a7b7;a7b9;a7bb;a7bd;a7bf;a7c1;a7c3;a7c8;a7ca;a7d1;a7d3;a7d5;a7d7;a7d9;a7f2-a7f4;a7f6;a7f8-a7fa;ab30-ab5a;ab5c-ab69;ab70-abbf;fb00-fb06;fb13-fb17;ff41-ff5a;10428-1044f;104d8-104fb;10597-105a1;105a3-105b1;105b3-105b9;105bb-105bc;10780;10783-10785;10787-107b0;107b2-107ba;10cc0-10cf2;118c0-118df;16e60-16e7f;1d41a-1d433;1d44e-1d454;1d456-1d467;1d482-1d49b;1d4b6-1d4b9;1d4bb;1d4bd-1d4c3;1d4c5-1d4cf;1d4ea-1d503;1d51e-1d537;1d552-1d56b;1d586-1d59f;1d5ba-1d5d3;1d5ee-1d607;1d622-1d63b;1d656-1d66f;1d68a-1d6a5;1d6c2-1d6da;1d6dc-1d6e1;1d6fc-1d714;1d716-1d71b;1d736-1d74e;1d750-1d755;1d770-1d788;1d78a-1d78f;1d7aa-1d7c2;1d7c4-1d7c9;1d7cb;1df00-1df09;1df0b-1df1e;1df25-1df2a;1e030-1e06d;1e922-1e943";

fn lowercase_table() -> &'static Vec<(u32, u32)> {
    static TABLE: OnceLock<Vec<(u32, u32)>> = OnceLock::new();
    TABLE.get_or_init(|| {
        LOWERCASE_RANGES
            .split(';')
            .map(|entry| match entry.split_once('-') {
                Some((first, last)) => (
                    u32::from_str_radix(first, 16).expect("range start"),
                    u32::from_str_radix(last, 16).expect("range end"),
                ),
                None => {
                    let only = u32::from_str_radix(entry, 16).expect("codepoint");
                    (only, only)
                }
            })
            .collect()
    })
}

pub(crate) fn py_islower(c: char) -> bool {
    let cp = c as u32;
    lowercase_table()
        .binary_search_by(|(first, last)| {
            if cp < *first {
                std::cmp::Ordering::Greater
            } else if cp > *last {
                std::cmp::Ordering::Less
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

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

pub(crate) fn page_lines(elements: &[Element]) -> Vec<String> {
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
        .map(py_strip)
        .filter(|line| !line.is_empty() && line.chars().any(py_islower))
        .count()
}

pub(crate) fn trace_text(
    pdf: &Path,
    first: u32,
    last: u32,
    fonts: &BTreeMap<String, TextFace>,
) -> Result<Vec<String>> {
    Ok(trace_elements(pdf, first, last, fonts)?
        .iter()
        .map(|page| page_text(page))
        .collect())
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
