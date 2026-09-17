use std::collections::HashMap;
use std::fmt::Write as _;
use std::path::Path;

use anyhow::{anyhow, Context, Result};

pub struct Outlined {
    pub markup: String,
    #[allow(dead_code)]
    pub width: f64,
    pub ascent: f64,
    pub descent: f64,
}

pub struct Outliner {
    data: Vec<u8>,
    units: f64,
    ascent_units: f64,
    descent_units: f64,
    advances: HashMap<char, f64>,
    paths: HashMap<char, String>,
}

struct Builder {
    segments: Vec<String>,
    start: (f32, f32),
    cursor: (f32, f32),
    last_line_to_start: bool,
}

impl Builder {
    fn new() -> Self {
        Self {
            segments: Vec::new(),
            start: (0.0, 0.0),
            cursor: (0.0, 0.0),
            last_line_to_start: false,
        }
    }

    fn finish(self) -> String {
        self.segments.concat()
    }
}

fn num(v: f32) -> String {
    let r = (v as f64 * 100.0).round() / 100.0;
    if (r - r.trunc()).abs() < f64::EPSILON {
        format!("{}", r.trunc() as i64)
    } else {
        let s = format!("{r}");
        s
    }
}

impl ttf_parser::OutlineBuilder for Builder {
    fn move_to(&mut self, x: f32, y: f32) {
        self.segments.push(format!("M{} {}", num(x), num(y)));
        self.start = (x, y);
        self.cursor = (x, y);
        self.last_line_to_start = false;
    }

    fn line_to(&mut self, x: f32, y: f32) {
        self.segments.push(format!("L{} {}", num(x), num(y)));
        self.cursor = (x, y);
        self.last_line_to_start = (x, y) == self.start;
    }

    fn quad_to(&mut self, ax: f32, ay: f32, x: f32, y: f32) {
        self.segments
            .push(format!("Q{} {} {} {}", num(ax), num(ay), num(x), num(y)));
        self.cursor = (x, y);
        self.last_line_to_start = false;
    }

    fn curve_to(&mut self, ax: f32, ay: f32, bx: f32, by: f32, x: f32, y: f32) {
        self.segments.push(format!(
            "C{} {} {} {} {} {}",
            num(ax),
            num(ay),
            num(bx),
            num(by),
            num(x),
            num(y)
        ));
        self.cursor = (x, y);
        self.last_line_to_start = false;
    }

    fn close(&mut self) {
        if self.last_line_to_start {
            self.segments.pop();
        }
        self.segments.push("Z".into());
        self.cursor = self.start;
        self.last_line_to_start = false;
    }
}

impl Outliner {
    pub fn load(path: &Path) -> Result<Self> {
        let data = std::fs::read(path)
            .with_context(|| format!("Bundled cover font is missing: {}", path.display()))?;
        let (units, ascent_units, descent_units) = {
            let face = ttf_parser::Face::parse(&data, 0)
                .with_context(|| format!("Bundled cover font is unreadable: {}", path.display()))?;
            (
                f64::from(face.units_per_em()),
                f64::from(face.ascender()),
                f64::from(face.descender()).abs(),
            )
        };
        Ok(Self {
            data,
            units,
            ascent_units,
            descent_units,
            advances: HashMap::new(),
            paths: HashMap::new(),
        })
    }

    fn face(&self) -> ttf_parser::Face<'_> {
        ttf_parser::Face::parse(&self.data, 0).expect("font parsed at load")
    }

    fn glyph(&mut self, character: char) -> Result<(f64, String)> {
        if let (Some(advance), Some(path)) =
            (self.advances.get(&character), self.paths.get(&character))
        {
            return Ok((*advance, path.clone()));
        }
        let face = self.face();
        let id = face.glyph_index(character).ok_or_else(|| {
            anyhow!(
                "Bundled cover font has no glyph for U+{:04X} {:?}",
                character as u32,
                character
            )
        })?;
        let advance = f64::from(
            face.glyph_hor_advance(id)
                .ok_or_else(|| anyhow!("Bundled cover font has no advance for {character:?}"))?,
        );
        let mut builder = Builder::new();
        face.outline_glyph(id, &mut builder);
        let path = builder.finish();
        self.advances.insert(character, advance);
        self.paths.insert(character, path.clone());
        Ok((advance, path))
    }

    pub fn measure(
        &mut self,
        text: &str,
        size: f64,
        tracking: f64,
        horizontal_scale: f64,
    ) -> Result<f64> {
        let scale = size / self.units * horizontal_scale / 100.0;
        let count = text.chars().count();
        let mut width = 0.0;
        for (index, character) in text.chars().enumerate() {
            let (advance, _) = self.glyph(character)?;
            width += advance * scale;
            if index + 1 < count {
                width += tracking * horizontal_scale / 100.0;
            }
        }
        Ok(width)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn outline(
        &mut self,
        text: &str,
        x: f64,
        baseline: f64,
        size: f64,
        fill: &str,
        tracking: f64,
        horizontal_scale: f64,
        stroke: Option<(&str, f64)>,
        extra_transform: &str,
    ) -> Result<Outlined> {
        let scale = size / self.units;
        let scale_x = scale * horizontal_scale / 100.0;
        let count = text.chars().count();
        let mut cursor = 0.0;
        let mut paths = String::new();
        for (index, character) in text.chars().enumerate() {
            let (advance_units, commands) = self.glyph(character)?;
            let advance = advance_units * scale_x;
            if character != ' ' && !commands.is_empty() {
                let mut paint = format!("fill=\"{fill}\"");
                if let Some((colour, width)) = stroke {
                    if width != 0.0 {
                        let _ = write!(
                            paint,
                            " stroke=\"{colour}\" stroke-width=\"{:.4}\" paint-order=\"stroke fill\"",
                            width / scale
                        );
                    }
                }
                let _ = write!(
                    paths,
                    "<path d=\"{commands}\" {paint} transform=\"translate({:.5} 0)\"/>",
                    cursor / scale_x
                );
            }
            cursor += advance;
            if index + 1 < count {
                cursor += tracking * horizontal_scale / 100.0;
            }
        }
        let transform = format!(
            "translate({x:.5} {baseline:.5}) {extra_transform} scale({scale_x:.8} {:.8})",
            -scale
        );
        let transform = transform.trim().to_string();
        Ok(Outlined {
            markup: format!("<g transform=\"{transform}\">{paths}</g>"),
            width: cursor,
            ascent: self.ascent_units * scale,
            descent: self.descent_units * scale,
        })
    }
}
