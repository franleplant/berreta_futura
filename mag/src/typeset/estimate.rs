use crate::model::shared::{Result, ValidationError};
use std::collections::BTreeMap;
use std::path::Path;

const FACES: [(&str, &str); 4] = [
    ("serif", "source-serif-4/SourceSerif4SmText-Regular.ttf"),
    (
        "serif-display",
        "source-serif-4/SourceSerif4Display-Semibold.ttf",
    ),
    ("sans-medium", "inter/Inter-Medium.ttf"),
    ("sans-semibold", "inter/Inter-SemiBold.ttf"),
];
const RAIL: f64 = 348.0;
const META_MEASURE: f64 = 293.0;
const PAGE: f64 = 595.2756 - 42.0004 - 54.9996;
const RESERVE: f64 = 13.2;
const TITLE_BOX: f64 = 64.0;
const TITLE_MIN: f64 = 22.0;
const COMPACT_TITLE_MAX: f64 = 30.0;
const TITLE_LEADING: f64 = 0.96;
const COMPACT_FIXED: f64 = 195.1 + 20.0 + 7.15 + 6.0 + 18.0 + 2.4 + 16.0 + 6.0;
const COMPACT_META_PAD: f64 = 7.0;
const STANDFIRST_SIZE: f64 = 9.6;
const STANDFIRST_LEADING: f64 = 13.2;

const PLAIN_MEASURE: f64 = 325.0;
const PLAIN_TITLE_TOP: f64 = 10.0046 + 25.0 + 12.0;
const PLAIN_FIELD_GAP: f64 = 305.2756 - 264.5208;
const CODE_SIDE: f64 = 55.5;
const CREDIT_GAP: f64 = 4.5 * 3.15;
const INTER_CAP: f64 = 1490.0 / 2048.0;
const FIGURE_FIELD_BASE: f64 = 25.0 + 12.0 + 10.0 + 12.0;

pub struct PlainOpener {
    pub size: f64,
    pub field: f64,
    pub tracking: f64,
    pub trim: f64,
}

pub struct Metrics(BTreeMap<&'static str, BTreeMap<char, f64>>);

pub struct Opener<'a> {
    pub title: &'a str,
    pub byline: &'a str,
    pub note: &'a str,
    pub intro: &'a str,
}

impl Metrics {
    pub fn load(fonts: &Path) -> Result<Metrics> {
        let mut faces = BTreeMap::new();
        for (name, file) in FACES {
            let path = fonts.join(file);
            let data = std::fs::read(&path)
                .map_err(|e| ValidationError::one(format!("{}: {e}", path.display())))?;
            let face = ttf_parser::Face::parse(&data, 0)
                .map_err(|e| ValidationError::one(format!("{}: {e}", path.display())))?;
            let units = f64::from(face.units_per_em());
            let mut widths = BTreeMap::new();
            for subtable in face.tables().cmap.iter().flat_map(|c| c.subtables) {
                subtable.codepoints(|codepoint| {
                    let advance = char::from_u32(codepoint)
                        .and_then(|c| face.glyph_index(c).map(|g| (c, g)))
                        .and_then(|(c, g)| face.glyph_hor_advance(g).map(|a| (c, a)));
                    if let Some((c, a)) = advance {
                        widths.insert(c, f64::from(a) / units);
                    }
                });
            }
            faces.insert(name, widths);
        }
        Ok(Metrics(faces))
    }

    pub fn width(&self, face: &str, text: &str, size: f64) -> f64 {
        let widths = &self.0[face];
        text.chars()
            .map(|c| widths.get(&c).unwrap_or(&0.0))
            .sum::<f64>()
            * size
    }

    pub fn wrap(&self, text: &str, face: &str, size: f64, width: f64) -> Vec<String> {
        let cleaned: String = text.chars().filter(|c| !matches!(c, '*' | '`')).collect();
        let mut words = Vec::new();
        for word in cleaned.split_whitespace() {
            if self.width(face, word, size) <= width {
                words.push(word.to_string());
                continue;
            }
            let mut chunk = String::new();
            for c in word.chars() {
                let proposed = format!("{chunk}{c}");
                if !chunk.is_empty() && self.width(face, &proposed, size) > width {
                    words.push(std::mem::replace(&mut chunk, c.to_string()));
                } else {
                    chunk = proposed;
                }
            }
            words.extend((!chunk.is_empty()).then_some(chunk));
        }
        let mut lines = Vec::new();
        let mut current = String::new();
        for word in words {
            let proposed = format!("{current} {word}").trim().to_string();
            if !current.is_empty() && self.width(face, &proposed, size) > width {
                lines.push(std::mem::replace(&mut current, word));
            } else {
                current = proposed;
            }
        }
        lines.push(current);
        lines
    }

    fn fitted(
        &self,
        title: &str,
        width: f64,
        box_height: f64,
        max: f64,
        min: f64,
        lines: usize,
    ) -> Option<(f64, usize)> {
        let mut size = max;
        while size >= min {
            let count = self.wrap(title, "serif-display", size, width).len();
            if count <= lines && size + (count as f64 - 1.0) * size * TITLE_LEADING <= box_height {
                return Some((size, count));
            }
            size -= 0.5;
        }
        None
    }

    fn compact_title(&self, title: &str) -> Option<(f64, usize)> {
        self.fitted(title, RAIL, TITLE_BOX, COMPACT_TITLE_MAX, TITLE_MIN, 2)
    }

    pub fn plain_opener(
        &self,
        title: &str,
        byline: &str,
        note: &str,
        code: Option<usize>,
        figure: bool,
    ) -> Result<PlainOpener> {
        let maximum = if figure { 30.0 } else { 35.0 };
        let (size, lines) = self
            .fitted(title, PLAIN_MEASURE, 165.0, maximum, 24.0, 4)
            .ok_or_else(|| {
                ValidationError::one(format!(
                    "Title cannot fit the Quiet Standard display box: {title}"
                ))
            })?;
        let flow = size * (1.0 + TITLE_LEADING * lines as f64);
        let baseline = PLAIN_TITLE_TOP + flow + 10.0;
        let (column, symbol) = match code {
            Some(rows) => {
                let quiet = 4.0 * CODE_SIDE / (rows as f64 + 8.0);
                let symbol = baseline - 7.4 * INTER_CAP + CODE_SIDE - 2.0 * quiet;
                (
                    PLAIN_MEASURE - (CODE_SIDE - 2.0 * quiet + CREDIT_GAP),
                    Some(symbol),
                )
            }
            None => (PLAIN_MEASURE, None),
        };
        let tracking = match code {
            Some(_) => self.byline_tracking(byline, column)?,
            None => 0.0,
        };
        let title_field = FIGURE_FIELD_BASE + flow;
        let floor = symbol.map_or(0.0, |bottom| bottom + 12.0);
        let (field, trim) = match figure {
            true => (title_field.max(floor), (floor - title_field).max(0.0)),
            false => {
                let foot = symbol.unwrap_or(baseline).max(baseline);
                (self.credit_foot(baseline, foot, note, column), 0.0)
            }
        };
        Ok(PlainOpener {
            size,
            field,
            tracking,
            trim,
        })
    }

    fn byline_tracking(&self, byline: &str, column: f64) -> Result<f64> {
        let text = byline.trim().to_uppercase();
        let width = self.width("sans-semibold", &text, 7.4);
        if width > 0.0 && column / width < 0.78 {
            return Err(ValidationError::one(format!(
                "Article byline {text:?} reaches past the {column:.2}pt credit column beside its \
                 own source code and would require excessive horizontal compression; shorten \
                 the captured byline or redesign the credit row."
            )));
        }
        Ok(match width > column {
            true => (column - width) / (text.chars().count().max(2) - 1) as f64,
            false => 0.0,
        })
    }

    fn credit_foot(&self, baseline: f64, foot: f64, note: &str, column: f64) -> f64 {
        let note_lines = self.wrap(note, "sans-medium", 6.8, column).len() as f64;
        let note_foot = baseline + 12.0 + (note_lines - 1.0) * 9.45 + 6.8 * 0.2412109375;
        (if note.trim().is_empty() {
            foot
        } else {
            foot.max(note_foot)
        }) + PLAIN_FIELD_GAP
    }

    pub fn standfirst_keep_words(&self, opener: &Opener) -> usize {
        let Some((size, lines)) = self.compact_title(opener.title) else {
            return 0;
        };
        let mut credit = self
            .wrap(opener.byline, "sans-semibold", 7.4, META_MEASURE)
            .len() as f64
            * 8.5;
        if !opener.note.is_empty() {
            credit += 3.2
                + self
                    .wrap(opener.note, "sans-medium", 6.8, META_MEASURE)
                    .len() as f64
                    * 9.4;
        }
        let fixed = COMPACT_FIXED
            + lines as f64 * size * TITLE_LEADING
            + credit.max(41.0)
            + 2.0 * COMPACT_META_PAD
            + 1.0;
        let budget = ((PAGE - RESERVE - fixed) / STANDFIRST_LEADING)
            .floor()
            .max(0.0) as usize;
        let intro = opener
            .intro
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ");
        let wrapped = self.wrap(&intro, "serif", STANDFIRST_SIZE, RAIL);
        if budget < 1 || wrapped.len() <= budget {
            return 0;
        }
        wrapped[..budget]
            .iter()
            .map(|line| line.split_whitespace().count())
            .sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::template::FONT_DIR;

    fn keep(words: usize) -> usize {
        let fonts = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join(FONT_DIR);
        let intro = vec!["standfirst"; words].join(" ");
        Metrics::load(&fonts)
            .expect("the faces load")
            .standfirst_keep_words(&Opener {
                title: "A Fixture Title",
                byline: "Ada",
                note: "A note on the author.",
                intro: &intro,
            })
    }

    #[test]
    fn the_standfirst_split_straddles_sixty_three_and_sixty_four_words() {
        assert_eq!(keep(63), 0);
        assert_eq!(keep(64), 63);
        assert_eq!(keep(400), 63);
    }
}
