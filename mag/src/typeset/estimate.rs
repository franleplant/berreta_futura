use crate::model::shared::{Result, ValidationError};
use crate::typeset::geometry::geometry;
use crate::typeset::world::font_dir;
use std::collections::BTreeMap;
use std::sync::OnceLock;

const FACES: [(&str, &str); 4] = [
    ("serif", "source-serif-4/SourceSerif4SmText-Regular.ttf"),
    (
        "serif-display",
        "source-serif-4/SourceSerif4Display-Semibold.ttf",
    ),
    ("sans-medium", "inter/Inter-Medium.ttf"),
    ("sans-semibold", "inter/Inter-SemiBold.ttf"),
];
const TITLE_BOX: f64 = 64.0;
const TITLE_MIN: f64 = 22.0;
const TITLE_MAX: f64 = 32.5;
const COMPACT_TITLE_MAX: f64 = 30.0;
const TITLE_LEADING: f64 = 0.96;

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

static METRICS: OnceLock<Metrics> = OnceLock::new();

impl Metrics {
    pub fn load() -> Result<&'static Metrics> {
        if let Some(loaded) = METRICS.get() {
            return Ok(loaded);
        }
        let mut faces = BTreeMap::new();
        for (name, file) in FACES {
            let path = font_dir().join(file);
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
        Ok(METRICS.get_or_init(|| Metrics(faces)))
    }

    pub fn width(&self, face: &str, text: &str, size: f64) -> Result<f64> {
        let widths = self
            .0
            .get(face)
            .ok_or_else(|| ValidationError::one(format!("unknown font face {face:?}")))?;
        Ok(text
            .chars()
            .map(|c| widths.get(&c).unwrap_or(&0.0))
            .sum::<f64>()
            * size)
    }

    pub fn wrap(&self, text: &str, face: &str, size: f64, width: f64) -> Result<Vec<String>> {
        let cleaned: String = text.chars().filter(|c| !matches!(c, '*' | '`')).collect();
        let mut words = Vec::new();
        for word in cleaned.split_whitespace() {
            if self.width(face, word, size)? <= width {
                words.push(word.to_string());
                continue;
            }
            let mut chunk = String::new();
            for c in word.chars() {
                let proposed = format!("{chunk}{c}");
                if !chunk.is_empty() && self.width(face, &proposed, size)? > width {
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
            if !current.is_empty() && self.width(face, &proposed, size)? > width {
                lines.push(std::mem::replace(&mut current, word));
            } else {
                current = proposed;
            }
        }
        lines.push(current);
        Ok(lines)
    }

    fn fitted(
        &self,
        title: &str,
        width: f64,
        box_height: f64,
        max: f64,
        min: f64,
        lines: usize,
    ) -> Result<Option<(f64, usize)>> {
        let mut size = max;
        while size >= min {
            let count = self.wrap(title, "serif-display", size, width)?.len();
            if count <= lines && size + (count as f64 - 1.0) * size * TITLE_LEADING <= box_height {
                return Ok(Some((size, count)));
            }
            size -= 0.5;
        }
        Ok(None)
    }

    fn compact_title(&self, title: &str) -> Result<Option<(f64, usize)>> {
        self.fitted(
            title,
            geometry().opener_rail,
            TITLE_BOX,
            COMPACT_TITLE_MAX,
            TITLE_MIN,
            2,
        )
    }

    pub fn illustrated_titles(&self, title: &str) -> Result<[(f64, usize); 2]> {
        let standard = self.fitted(
            title,
            geometry().opener_rail,
            TITLE_BOX,
            TITLE_MAX,
            TITLE_MIN,
            2,
        )?;
        match (standard, self.compact_title(title)?) {
            (Some(standard), Some(compact)) => Ok([standard, compact]),
            _ => Err(ValidationError::one(format!(
                "Title cannot fit the Quiet Standard display box: {title}"
            ))),
        }
    }

    pub fn editorial_opener(&self, title: &str) -> Result<(f64, f64)> {
        let (size, lines) = self
            .fitted(title, geometry().live, 135.0, 35.0, 25.0, 4)?
            .ok_or_else(|| {
                ValidationError::one(format!(
                    "Title cannot fit the Quiet Standard display box: {title}"
                ))
            })?;
        let field = FIGURE_FIELD_BASE + 13.0 + size * (1.0 + TITLE_LEADING * lines as f64);
        Ok((size, field.max(geometry().page_height - 52.0 - 390.0)))
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
            .fitted(title, geometry().measure, 165.0, maximum, 24.0, 4)?
            .ok_or_else(|| {
                ValidationError::one(format!(
                    "Title cannot fit the Quiet Standard display box: {title}"
                ))
            })?;
        let flow = size * (1.0 + TITLE_LEADING * lines as f64);
        let baseline = (geometry().datum + 25.0 + 12.0) + flow + 10.0;
        let (column, symbol) = match code {
            Some(rows) => {
                let quiet = 4.0 * CODE_SIDE / (rows as f64 + 8.0);
                let symbol = baseline - 7.4 * INTER_CAP + CODE_SIDE - 2.0 * quiet;
                (
                    geometry().measure - (CODE_SIDE - 2.0 * quiet + CREDIT_GAP),
                    Some(symbol),
                )
            }
            None => (geometry().measure, None),
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
                (self.credit_foot(baseline, foot, note, column)?, 0.0)
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
        let width = self.width("sans-semibold", &text, 7.4)?;
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

    fn credit_foot(&self, baseline: f64, foot: f64, note: &str, column: f64) -> Result<f64> {
        let note_lines = self.wrap(note, "sans-medium", 6.8, column)?.len() as f64;
        let note_foot = baseline + 12.0 + (note_lines - 1.0) * 9.45 + 6.8 * 0.2412109375;
        Ok((if note.trim().is_empty() {
            foot
        } else {
            foot.max(note_foot)
        }) + PLAIN_FIELD_GAP)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn metrics() -> &'static Metrics {
        Metrics::load().expect("the faces load")
    }

    #[test]
    fn an_illustrated_title_is_fitted_on_advance_widths_as_the_adapter_fits_it() {
        let metrics = metrics();
        let title = "Automated Researchers Can Reliably Mitigate Alignment Failures";
        assert_eq!(
            metrics.illustrated_titles(title).expect("it fits"),
            [(22.5, 2), (22.5, 2)]
        );
        let [(size, lines), _] = metrics
            .illustrated_titles("The Pen")
            .expect("a short title fits");
        assert_eq!((size, lines), (32.5, 1));
        let long = ["Unbreakable"; 12].join(" ");
        assert!(metrics.illustrated_titles(&long).is_err());
    }

    #[test]
    fn an_editorial_title_is_fitted_on_the_live_width_over_a_clamped_field() {
        let metrics = metrics();
        let (size, field) = metrics
            .editorial_opener("The Pen Moves Faster Than Review")
            .expect("it fits");
        assert_eq!(size, 35.0);
        assert!((field - (72.0 + 35.0 * (1.0 + 0.96 * 2.0))).abs() < 1e-9);
        let upkeep = "Upkeep Scaled Quickly";
        let (size, field) = metrics.editorial_opener(upkeep).expect("one line");
        assert_eq!(size, 35.0);
        assert!((field - 153.2756).abs() < 1e-4);
        assert_eq!(
            metrics
                .fitted(upkeep, geometry().measure, 135.0, 35.0, 25.0, 4)
                .expect("a known face"),
            Some((35.0, 2))
        );
        assert!(metrics
            .editorial_opener(&["Unbreakable"; 12].join(" "))
            .is_err());
    }
}
