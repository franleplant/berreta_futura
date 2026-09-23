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

    fn width(&self, face: &str, text: &str, size: f64) -> f64 {
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

    fn compact_title(&self, title: &str) -> Option<(f64, usize)> {
        let mut size = COMPACT_TITLE_MAX;
        while size >= TITLE_MIN {
            let lines = self.wrap(title, "serif-display", size, RAIL).len();
            if lines <= 2 && size + (lines as f64 - 1.0) * size * TITLE_LEADING <= TITLE_BOX {
                return Some((size, lines));
            }
            size -= 0.5;
        }
        None
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
