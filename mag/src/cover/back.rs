use std::path::Path;

use anyhow::{bail, Context, Result};

use super::outline::Outliner;
use super::svg::{escape, pyf, Design, Fonts, PAGE_HEIGHT, PAGE_WIDTH};

pub struct Back {
    pub overdraw: f64,
    pub rail_width: f64,
    pub rail_top: f64,
    pub rail_size: f64,
    pub rail_tracking: f64,
    pub mass_x: f64,
    pub mass_top: f64,
    pub mass_size: f64,
    pub mass_leading: f64,
    pub mass_tracking: f64,
    pub panel_x: f64,
    pub panel_top: f64,
    pub panel_right: f64,
    pub panel_bottom: f64,
    pub panel_padding: f64,
    pub statement_max_size: f64,
    pub statement_min_size: f64,
    pub statement_leading_ratio: f64,
    pub slug_x: f64,
    pub slug_bottom: f64,
    pub slug_size: f64,
    pub slug_tracking: f64,
}

pub struct BackText {
    pub mass: [String; 2],
    pub statement: String,
    pub slug: String,
    pub identity: String,
}

pub struct Serif {
    font: Outliner,
    data: Vec<u8>,
}

impl Serif {
    pub fn open(assets: &Path) -> Result<Self> {
        let path = assets.join("fonts/source-serif-4/SourceSerif4SmText-Regular.ttf");
        let data = std::fs::read(&path)
            .with_context(|| format!("Bundled cover font is missing: {}", path.display()))?;
        Ok(Self {
            font: Outliner::load(&path)?,
            data,
        })
    }

    fn ink_extent(&self, text: &str, size: f64) -> Result<(f64, f64)> {
        let face = ttf_parser::Face::parse(&self.data, 0).context("the serif face parses")?;
        let (mut rise, mut drop) = (0.0_f64, 0.0_f64);
        for character in text.chars() {
            let id = face
                .glyph_index(character)
                .with_context(|| format!("Bundled cover font has no glyph for {character:?}"))?;
            if let Some(bounds) = face.glyph_bounding_box(id) {
                rise = rise.max(f64::from(bounds.y_max));
                drop = drop.max(-f64::from(bounds.y_min));
            }
        }
        let scale = size / f64::from(face.units_per_em());
        Ok((rise * scale, drop * scale))
    }
}

struct Statement {
    markup: String,
    block: f64,
}

fn statement(
    back: &Back,
    serif: &mut Serif,
    ink: &str,
    text: &str,
    width: f64,
    height: f64,
) -> Result<Statement> {
    let mut size = back.statement_max_size;
    while size >= back.statement_min_size {
        let lines = serif.font.wrap(text, size, width)?;
        if let (Some(first), Some(last)) = (lines.first(), lines.last()) {
            let (rise, _) = serif.ink_extent(first, size)?;
            let (_, drop) = serif.ink_extent(last, size)?;
            let leading = size * back.statement_leading_ratio;
            let block =
                rise + (lines.len() - 1) as f64 * size * back.statement_leading_ratio + drop;
            if block <= height {
                let x = back.panel_x + back.panel_padding;
                let mut markup = String::new();
                for (index, line) in lines.iter().enumerate() {
                    let baseline =
                        back.panel_top + back.panel_padding + rise + index as f64 * leading;
                    markup += &serif
                        .font
                        .outline(line, x, baseline, size, ink, -0.12, 100.0, None, "")?
                        .markup;
                }
                return Ok(Statement { markup, block });
            }
        }
        size -= 0.5;
    }
    bail!("Back-cover issue statement cannot fit: {text}")
}

fn mass(back: &Back, fonts: &mut Fonts, design: &Design, words: &[String]) -> Result<String> {
    let max_width = PAGE_WIDTH - back.rail_width - back.mass_x + 4.0;
    let mut size = back.mass_size;
    while size >= 72.0 {
        let mut fits = true;
        for word in words {
            fits &= fonts.bold.measure(word, size, back.mass_tracking, 100.0)? <= max_width;
        }
        if fits {
            let leading = back.mass_leading * size / back.mass_size;
            let mut markup = String::new();
            for (index, word) in words.iter().enumerate() {
                let fill = if index == 0 {
                    &design.colors.violet
                } else {
                    &design.colors.ink
                };
                let baseline = back.mass_top + size + index as f64 * leading;
                markup += &fonts
                    .bold
                    .outline(
                        word,
                        back.mass_x,
                        baseline,
                        size,
                        fill,
                        back.mass_tracking,
                        100.0,
                        None,
                        "",
                    )?
                    .markup;
            }
            return Ok(markup);
        }
        size -= 0.5;
    }
    bail!("Back-cover display words cannot fit: {}", words.join(" / "))
}

fn rail(back: &Back, fonts: &mut Fonts, ink: &str, identity: &str) -> Result<String> {
    let max_length = PAGE_HEIGHT - back.rail_top - 28.0;
    let mut scale = 100.0;
    while scale >= 70.0 {
        if fonts
            .bold
            .measure(identity, back.rail_size, back.rail_tracking, scale)?
            <= max_length
        {
            let rail = fonts.bold.outline(
                identity,
                0.0,
                0.0,
                back.rail_size,
                ink,
                back.rail_tracking,
                scale,
                None,
                "",
            )?;
            let x = PAGE_WIDTH - back.rail_width / 2.0 - (rail.ascent - rail.descent) / 2.0;
            return Ok(format!(
                "<g transform=\"translate({x:.5} {:.5}) rotate(90)\">{}</g>",
                back.rail_top, rail.markup
            ));
        }
        scale -= 1.0;
    }
    bail!("Back-cover identity rail cannot fit: {identity}")
}

pub fn back_svg(
    design: &Design,
    back: &Back,
    fonts: &mut Fonts,
    serif: &mut Serif,
    text: &BackText,
) -> Result<String> {
    let colors = &design.colors;
    let mass = mass(back, fonts, design, &text.mass)?;
    let panel_width = PAGE_WIDTH - back.panel_x - back.panel_right;
    let padding = back.panel_padding;
    let height = PAGE_HEIGHT - back.panel_top - back.panel_bottom - padding * 2.0;
    let statement = statement(
        back,
        serif,
        &colors.ink,
        &text.statement,
        panel_width - padding * 2.0,
        height,
    )?;
    let slug = fonts.bold.outline(
        &text.slug,
        back.slug_x,
        PAGE_HEIGHT - back.slug_bottom,
        back.slug_size,
        &colors.paper,
        back.slug_tracking,
        100.0,
        None,
        "",
    )?;
    let rail = rail(back, fonts, &colors.ink, &text.identity)?;
    let overdraw = back.overdraw;
    let parts = [
        format!(
            "<rect data-slot=\"field\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"{}\"/>",
            pyf(-overdraw),
            pyf(-overdraw),
            pyf(PAGE_WIDTH + overdraw * 2.0),
            pyf(PAGE_HEIGHT + overdraw * 2.0),
            colors.orange
        ),
        format!(
            "<defs><clipPath id=\"mass-safe\" clipPathUnits=\"userSpaceOnUse\"><rect x=\"0\" y=\"0\" width=\"{}\" height=\"{PAGE_HEIGHT}\"/></clipPath></defs>",
            pyf(PAGE_WIDTH - back.rail_width)
        ),
        format!("<g data-slot=\"mass\" clip-path=\"url(#mass-safe)\">{mass}</g>"),
        format!(
            "<rect data-slot=\"statement-panel\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"{}\"/>",
            pyf(back.panel_x),
            pyf(back.panel_top),
            pyf(panel_width),
            pyf(statement.block + padding * 2.0),
            colors.paper
        ),
        format!("<g data-slot=\"statement\">{}</g>", statement.markup),
        format!("<g data-slot=\"slug\">{}</g>", slug.markup),
        format!("<g data-slot=\"identity-label\">{rail}</g>"),
    ];
    Ok(format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n\
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{PAGE_WIDTH}pt\" height=\"{PAGE_HEIGHT}pt\" viewBox=\"0 0 {PAGE_WIDTH} {PAGE_HEIGHT}\" overflow=\"hidden\">\n  \
<title>Berreta Futura back cover</title>\n  \
<g id=\"back-cover\" data-design=\"{}\">\n    {}\n  </g>\n</svg>\n",
        escape(&design.id),
        parts.join("\n    ")
    ))
}
