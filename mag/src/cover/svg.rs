use std::path::Path;

use anyhow::{bail, Result};
use base64::Engine as _;

use super::art::{art_zones, graded_art, Zone};
use super::outline::Outliner;

pub const PAGE_WIDTH: f64 = 419.527559;
pub const PAGE_HEIGHT: f64 = 595.275591;
const WORDMARK_TRACKING: f64 = -3.6;
const WORDMARK_HEAD_SCALE: f64 = 89.9;

pub struct Palette {
    pub paper: String,
    pub ink: String,
    pub orange: String,
    pub violet: String,
}

pub struct Tab {
    pub width: f64,
    pub edge_reveal: f64,
    pub issue_top: f64,
    pub identity_top: f64,
    pub overdraw: f64,
}

pub struct Headline {
    pub x: f64,
    pub top: f64,
    pub width: f64,
}

pub struct Art {
    pub x: f64,
    pub top: f64,
    pub width: f64,
    pub height: f64,
}

pub struct Deck {
    pub top: f64,
    pub size: f64,
    pub wrap_size: f64,
    pub leading: f64,
    pub horizontal_scale: f64,
    pub tracking: f64,
}

pub struct Footer {
    pub x: f64,
    pub bottom: f64,
    pub size: f64,
    pub tracking: f64,
}

pub struct HonoredPlate {
    pub margin: f64,
    pub footer: f64,
    pub wordmark_scale: f64,
    pub title_size: f64,
}

pub struct Wordmark {
    pub x: f64,
    pub top: f64,
    pub right_reserve: f64,
}

pub struct FooterCaption {
    pub margin: f64,
    pub wordmark_scale: f64,
    pub wordmark_dy: f64,
    pub title_size: f64,
}

pub struct Design {
    pub id: String,
    pub colors: Palette,
    pub tab: Tab,
    pub wordmark: Wordmark,
    pub footer_caption: FooterCaption,
    pub headline: Headline,
    pub art: Art,
    pub deck: Deck,
    pub footer: Footer,
    pub honored_plate: HonoredPlate,
}

pub struct CoverText {
    pub publication_name: String,
    pub headline: String,
    pub date_line: String,
    pub contributors: String,
    pub tab_issue: String,
    pub tab_identity: String,
}

pub struct Fonts {
    pub regular: Outliner,
    pub bold: Outliner,
    pub display: Outliner,
}

impl Fonts {
    pub fn load(assets: &Path) -> Result<Self> {
        let inter = assets.join("fonts").join("inter");
        Ok(Self {
            regular: Outliner::load(&inter.join("Inter-Regular.ttf"))?,
            bold: Outliner::load(&inter.join("Inter-Bold.ttf"))?,
            display: Outliner::load(
                &assets
                    .join("fonts")
                    .join("archivo")
                    .join("ArchivoCondensed-Bold.ttf"),
            )?,
        })
    }
}

pub(crate) fn pyf(value: f64) -> String {
    if value == value.trunc() && value.abs() < 1e16 {
        format!("{value:.1}")
    } else {
        format!("{value}")
    }
}

pub(crate) fn escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

struct Gradient<'a> {
    id: &'a str,
    x: &'a str,
    y: f64,
    w: f64,
    h: &'a str,
    color: &'a str,
    top: f64,
    bottom: f64,
}

fn gradient(spec: Gradient<'_>) -> String {
    let Gradient {
        id,
        x,
        y,
        w,
        h,
        color,
        top,
        bottom,
    } = spec;
    format!(
        "<defs><linearGradient id=\"{id}\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">\
<stop offset=\"0\" stop-color=\"{color}\" stop-opacity=\"{}\"/>\
<stop offset=\"1\" stop-color=\"{color}\" stop-opacity=\"{}\"/>\
</linearGradient></defs>\
<rect x=\"{x}\" y=\"{}\" width=\"{}\" height=\"{h}\" fill=\"url(#{id})\"/>",
        pyf(top),
        pyf(bottom),
        pyf(y),
        pyf(w)
    )
}

pub struct Builder<'a> {
    pub design: &'a Design,
    pub fonts: &'a mut Fonts,
}

impl Builder<'_> {
    fn band_x(&self) -> f64 {
        PAGE_WIDTH - self.design.tab.width
    }

    fn tab_band(&self) -> (f64, f64) {
        let width = self.design.tab.width;
        (PAGE_WIDTH - width, width - self.design.tab.edge_reveal)
    }

    fn wordmark_size(&mut self, head: &str, tail: &str, publication_name: &str) -> Result<f64> {
        let tracking = WORDMARK_TRACKING;
        let max_width = PAGE_WIDTH - self.design.tab.width - self.design.wordmark.right_reserve;
        let mut size = 42.0;
        loop {
            if size < 25.0 {
                bail!("Publication wordmark cannot fit: {publication_name}");
            }
            let head_width = self
                .fonts
                .bold
                .measure(head, size, tracking, WORDMARK_HEAD_SCALE)?;
            let tail_width = if tail.is_empty() {
                0.0
            } else {
                self.fonts.bold.measure(tail, size, tracking, 105.1)?
            };
            let tail_offset = size * (97.0 / 42.0);
            let box_width = tail_width + if tail.is_empty() { 0.0 } else { 13.0 };
            if head_width.max(tail_offset + box_width) <= max_width {
                return Ok(size);
            }
            size -= 0.5;
        }
    }

    fn wordmark(&mut self, publication_name: &str) -> Result<String> {
        let value = publication_name.to_uppercase();
        let value = value.trim();
        let (head, tail) = match value.rsplit_once(' ') {
            Some((head, tail)) => (head.to_string(), tail.to_string()),
            None => (value.to_string(), String::new()),
        };
        let x = self.design.wordmark.x;
        let top = self.design.wordmark.top;
        let pdf_baseline = PAGE_HEIGHT - top;
        let baseline = PAGE_HEIGHT - (pdf_baseline - 1.65);
        let tracking = WORDMARK_TRACKING;
        let head_scale = WORDMARK_HEAD_SCALE;
        let size = self.wordmark_size(&head, &tail, publication_name)?;
        let ink = self.design.colors.ink.clone();
        let head_path = self
            .fonts
            .bold
            .outline(
                &head,
                x + 0.36,
                baseline,
                size,
                &ink,
                tracking,
                head_scale,
                Some((&ink, 0.30)),
                "",
            )?
            .markup;
        if tail.is_empty() {
            return Ok(format!("<g data-slot=\"wordmark\">{head_path}</g>"));
        }
        let tail_offset = size * (97.0 / 42.0);
        let tail_x = x + tail_offset;
        let tail_origin_y = PAGE_HEIGHT - (pdf_baseline - size * 0.91);
        let tail_width = self.fonts.bold.measure(&tail, size, tracking, 105.1)?;
        let (box_x, box_y) = (-7.0_f64, -7.0_f64);
        let box_height = size * 1.04 - 1.0;
        let box_width = tail_width + 13.0;
        let slug_y = box_y - 1.0;
        let center_x = box_x + box_width / 2.0;
        let center_y = box_y + box_height / 2.0;
        let skew = (-10.0_f64).to_radians().tan();
        let group = format!(
            "translate({tail_x:.5} {tail_origin_y:.5}) translate({center_x:.5} {:.5}) matrix(1 0 {skew:.8} 1 0 0) translate({:.5} {center_y:.5})",
            -center_y,
            -center_x
        );
        let slug = format!(
            "<path d=\"M {} {} H {} V {} H {} Z\" fill=\"{}\"/>",
            pyf(box_x),
            pyf(-slug_y),
            pyf(box_x + box_width),
            pyf(-slug_y - (box_height + 0.65)),
            pyf(box_x),
            self.design.colors.ink
        );
        let orange_colour = self.design.colors.orange.clone();
        let orange = self
            .fonts
            .bold
            .outline(
                &tail,
                -13.0,
                -1.65,
                size,
                &orange_colour,
                tracking,
                106.6,
                Some((&orange_colour, 0.15)),
                "",
            )?
            .markup;
        let paper = self.design.colors.paper.clone();
        let white = self
            .fonts
            .bold
            .outline(
                &tail,
                0.0,
                -1.65,
                size,
                &paper,
                tracking,
                105.1,
                Some((&paper, 0.30)),
                "",
            )?
            .markup;
        Ok(format!(
            "<g data-slot=\"wordmark\">{head_path}<g transform=\"{group}\">{slug}{orange}{white}</g></g>"
        ))
    }

    fn scaled_wordmark(
        &mut self,
        publication_name: &str,
        mode: &str,
        scale: f64,
        dx: f64,
        dy: f64,
    ) -> Result<String> {
        let mut part = self.wordmark(publication_name)?;
        if mode == "light" {
            if let Some(i) = part.find("matrix(") {
                if let Some(j) = part[..i].rfind("<g transform=") {
                    let head =
                        part[..j].replace(&self.design.colors.ink, &self.design.colors.paper);
                    part = format!("{head}{}", &part[j..]);
                }
            } else {
                part = part.replace(&self.design.colors.ink, &self.design.colors.paper);
            }
        }
        Ok(format!(
            "<g transform=\"translate({dx:.4} {dy:.4}) scale({})\">{part}</g>",
            pyf(scale)
        ))
    }

    fn margin_locked_wordmark(
        &mut self,
        publication_name: &str,
        mode: &str,
        scale: f64,
        margin: f64,
        dy: f64,
    ) -> Result<String> {
        let dx = margin - (self.design.wordmark.x + 0.36) * scale;
        self.scaled_wordmark(publication_name, mode, scale, dx, dy)
    }

    fn fit_display_line(&mut self, text: &str, max_size: f64, width: f64) -> Result<f64> {
        let mut size = max_size;
        while size >= 12.0 && self.fonts.display.measure(text, size, 0.2, 100.0)? > width {
            size -= 0.5;
        }
        if size < 12.0 {
            bail!("Cover title cannot fit on one line: {text}");
        }
        Ok(size)
    }

    fn justified_line(
        &mut self,
        text: &str,
        x: f64,
        baseline: f64,
        size: f64,
        fill: &str,
        width: f64,
    ) -> Result<String> {
        let base = self.fonts.regular.measure(text, size, 0.0, 100.0)?;
        let count = text.chars().count();
        let divisor = if count > 1 { (count - 1) as f64 } else { 1.0 };
        let tracking = ((width - base) / divisor).max(0.0);
        Ok(self
            .fonts
            .regular
            .outline(text, x, baseline, size, fill, tracking, 100.0, None, "")?
            .markup)
    }

    fn right_line(
        &mut self,
        text: &str,
        right_edge: f64,
        baseline: f64,
        size: f64,
        fill: &str,
    ) -> Result<String> {
        let tracking = 1.4;
        let width = self.fonts.bold.measure(text, size, tracking, 100.0)?;
        Ok(self
            .fonts
            .bold
            .outline(
                text,
                right_edge - width,
                baseline,
                size,
                fill,
                tracking,
                100.0,
                None,
                "",
            )?
            .markup)
    }

    fn tab_labels(&mut self, text: &CoverText) -> Result<Vec<String>> {
        let (band_x, band_width) = self.tab_band();
        let ink = self.design.colors.ink.clone();
        let mut out = Vec::new();
        for (slot, value, top, size, tracking, scale) in [
            (
                "issue-label",
                &text.tab_issue,
                self.design.tab.issue_top,
                7.4,
                1.6,
                100.0,
            ),
            (
                "identity-label",
                &text.tab_identity,
                self.design.tab.identity_top,
                4.8,
                1.6,
                103.0,
            ),
        ] {
            let outlined = self
                .fonts
                .bold
                .outline(value, 0.0, 0.0, size, &ink, tracking, scale, None, "")?;
            let cross = band_x + band_width / 2.0 - (outlined.ascent - outlined.descent) / 2.0;
            out.push(format!(
                "<g data-slot=\"{slot}\"><g transform=\"translate({cross:.5} {top:.5}) rotate(90)\">{}</g></g>",
                outlined.markup
            ));
        }
        Ok(out)
    }

    fn wrap(&mut self, text: &str, bold: bool, size: f64, width: f64) -> Result<Vec<String>> {
        let font = if bold {
            &mut self.fonts.bold
        } else {
            &mut self.fonts.regular
        };
        font.wrap(text, size, width)
    }

    fn display_wrap(&mut self, text: &str, size: f64, width: f64) -> Result<Vec<String>> {
        self.fonts.display.wrap(text, size, width)
    }

    fn headline_layout(&mut self, value: &str, described_as: &str) -> Result<(Vec<String>, f64)> {
        let width = self.design.headline.width;
        let words: Vec<&str> = value.split_whitespace().collect();
        let mut size = 29.0;
        let mut lines;
        loop {
            let mut best: Option<(f64, Vec<String>)> = None;
            if words.len() >= 2 {
                for split in 1..words.len() {
                    let pair = [words[..split].join(" "), words[split..].join(" ")];
                    let a = self.fonts.display.measure(&pair[0], size, 0.0, 100.0)?;
                    let b = self.fonts.display.measure(&pair[1], size, 0.0, 100.0)?;
                    if a.max(b) <= width {
                        let delta = (a - b).abs();
                        if best.as_ref().is_none_or(|(d, _)| delta < *d) {
                            best = Some((delta, pair.to_vec()));
                        }
                    }
                }
            }
            lines = match best {
                Some((_, pair)) => pair,
                None => self.display_wrap(value, size, width)?,
            };
            if lines.len() <= 3 || size < 20.0 {
                break;
            }
            size -= 0.5;
        }
        if size < 20.0 {
            bail!("Cover headline cannot fit: {described_as}");
        }
        Ok((lines, size))
    }

    fn headline(&mut self, text: &str) -> Result<String> {
        let value = text.to_uppercase();
        let value = value.trim();
        let (lines, size) = self.headline_layout(value, text)?;
        let mut baseline = self.design.headline.top + size;
        let leading = size * 0.78;
        let ink = self.design.colors.ink.clone();
        let violet = self.design.colors.violet.clone();
        let colors = [ink.clone(), violet, ink];
        let mut paths = String::new();
        for (index, line) in lines.iter().enumerate() {
            let odd = index % 2 == 1;
            let fill = colors[index].clone();
            let stroke = if odd {
                None
            } else {
                Some((fill.as_str(), 0.09))
            };
            let outlined = self.fonts.display.outline(
                line,
                self.design.headline.x + if odd { 23.0 } else { -0.65 },
                baseline + if odd { 1.0 } else { 0.0 },
                if odd { 28.0 } else { size },
                &fill,
                -1.35,
                100.0,
                stroke,
                "",
            )?;
            paths.push_str(&outlined.markup);
            baseline += leading;
        }
        Ok(format!("<g data-slot=\"headline\">{paths}</g>"))
    }

    fn deck(&mut self, text: &str, x: f64, width: f64) -> Result<String> {
        if text.is_empty() {
            return Ok("<g data-slot=\"deck\"/>".to_string());
        }
        let lines = self.wrap(text, false, self.design.deck.wrap_size, width)?;
        if lines.len() > 5 {
            bail!("Cover deck cannot fit: {text}");
        }
        let baseline = self.design.deck.top + self.design.deck.size;
        let ink = self.design.colors.ink.clone();
        let mut paths = String::new();
        for (index, line) in lines.iter().enumerate() {
            let outlined = self.fonts.regular.outline(
                line,
                x - if index == 0 { 0.65 } else { 0.0 },
                baseline + index as f64 * self.design.deck.leading,
                self.design.deck.size,
                &ink,
                self.design.deck.tracking,
                self.design.deck.horizontal_scale,
                None,
                "",
            )?;
            paths.push_str(&outlined.markup);
        }
        Ok(format!("<g data-slot=\"deck\">{paths}</g>"))
    }

    fn full_art(&self, cover_art: &Path, x: f64, y: f64, w: f64, h: f64) -> Result<String> {
        if !cover_art.is_file() {
            bail!("Cover art is missing: {}", cover_art.display());
        }
        let data = base64::engine::general_purpose::STANDARD.encode(graded_art(cover_art)?);
        Ok(format!(
            "<image data-slot=\"art\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" preserveAspectRatio=\"xMidYMid slice\" href=\"data:image/png;base64,{data}\"/>",
            pyf(x),
            pyf(y),
            pyf(w),
            pyf(h)
        ))
    }

    pub fn framed(&mut self, text: &CoverText, cover_art: &Path) -> Result<String> {
        let (band_x, band_width) = self.tab_band();
        let overdraw = self.design.tab.overdraw;
        let paper = self.design.colors.paper.clone();
        let orange = self.design.colors.orange.clone();
        let ink = self.design.colors.ink.clone();
        let mut parts = vec![
            format!(
                "<rect data-slot=\"paper\" x=\"0\" y=\"0\" width=\"{PAGE_WIDTH}\" height=\"{PAGE_HEIGHT}\" fill=\"{paper}\"/>"
            ),
            format!(
                "<rect data-slot=\"edge-tab\" x=\"{band_x:.5}\" y=\"{:.5}\" width=\"{band_width:.5}\" height=\"{:.5}\" fill=\"{orange}\"/>",
                -overdraw,
                PAGE_HEIGHT + overdraw * 2.0
            ),
        ];
        parts.push(self.wordmark(&text.publication_name)?);
        parts.push(self.headline(&text.headline)?);
        let (ax, ay) = (self.design.art.x, self.design.art.top);
        let (aw, ah) = (self.design.art.width, self.design.art.height);
        parts.push(self.full_art(cover_art, ax, ay, aw, ah)?);
        parts.push(format!(
            "<rect data-slot=\"art-border\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"none\" stroke=\"{ink}\" stroke-width=\".7\"/>",
            pyf(ax),
            pyf(ay),
            pyf(aw),
            pyf(ah)
        ));
        parts.push(self.deck(&text.contributors, ax, aw)?);
        let outlined = self.fonts.bold.outline(
            &text.date_line,
            self.design.footer.x,
            PAGE_HEIGHT - self.design.footer.bottom,
            self.design.footer.size,
            &ink,
            self.design.footer.tracking,
            100.0,
            None,
            "",
        )?;
        parts.push(format!("<g data-slot=\"footer\">{}</g>", outlined.markup));
        parts.extend(self.tab_labels(text)?);
        Ok(self.shell(&parts.join("\n    ")))
    }

    pub fn honored_plate(&mut self, text: &CoverText, cover_art: &Path) -> Result<String> {
        let margin = self.design.honored_plate.margin;
        let footer = self.design.honored_plate.footer;
        let band = self.band_x();
        let right_edge = band - margin - 8.0;
        let ink = self.design.colors.ink.clone();
        let paper = self.design.colors.paper.clone();
        let orange = self.design.colors.orange.clone();
        let mut parts = vec![
            format!(
                "<rect data-slot=\"paper\" x=\"0\" y=\"0\" width=\"{PAGE_WIDTH}\" height=\"{PAGE_HEIGHT}\" fill=\"{paper}\"/>"
            ),
            self.full_art(
                cover_art,
                margin,
                margin,
                band - 2.0 * margin,
                PAGE_HEIGHT - 2.0 * margin - footer,
            )?,
            format!(
                "<rect data-slot=\"art-border\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"none\" stroke=\"{ink}\" stroke-width=\".7\"/>",
                pyf(margin),
                pyf(margin),
                pyf(band - 2.0 * margin),
                pyf(PAGE_HEIGHT - 2.0 * margin - footer)
            ),
            self.scaled_wordmark(
                &text.publication_name,
                "dark",
                self.design.honored_plate.wordmark_scale,
                6.0,
                PAGE_HEIGHT - footer - 22.0 - 14.0,
            )?,
        ];
        let title = text.headline.to_uppercase();
        let title = title.trim().to_string();
        let size = self.fit_display_line(&title, self.design.honored_plate.title_size, 190.0)?;
        let width = self.fonts.display.measure(&title, size, 0.2, 100.0)?;
        let outlined = self.fonts.display.outline(
            &title,
            right_edge - width,
            PAGE_HEIGHT - footer + 22.0,
            size,
            &ink,
            0.2,
            100.0,
            None,
            "",
        )?;
        parts.push(format!("<g data-slot=\"headline\">{}</g>", outlined.markup));
        if !text.contributors.is_empty() {
            let line = self.justified_line(
                &text.contributors,
                margin + 8.0,
                PAGE_HEIGHT - 24.0,
                4.4,
                &ink,
                right_edge - margin - 68.0,
            )?;
            parts.push(format!("<g data-slot=\"deck\">{line}</g>"));
        }
        parts.push(self.right_line(&text.date_line, right_edge, PAGE_HEIGHT - 13.0, 4.4, &ink)?);
        parts.push(format!(
            "<rect data-slot=\"edge-tab\" x=\"{band:.5}\" y=\"-1.5\" width=\"{:.5}\" height=\"{}\" fill=\"{orange}\"/>",
            PAGE_WIDTH - band - self.design.tab.edge_reveal,
            pyf(PAGE_HEIGHT + 3.0)
        ));
        parts.extend(self.tab_labels(text)?);
        Ok(self.shell(&parts.join("\n    ")))
    }

    pub fn materialize(&mut self, layout: &str, text: &CoverText, art: &Path) -> Result<String> {
        match layout {
            "footer_caption" => self.footer_caption(text, art),
            "honored_plate" => self.honored_plate(text, art),
            "framed" => self.framed(text, art),
            other => bail!(
                "Unknown cover layout '{other}': expected framed, footer_caption, or honored_plate"
            ),
        }
    }

    fn shell(&self, body: &str) -> String {
        format!(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n\
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{PAGE_WIDTH}pt\" height=\"{PAGE_HEIGHT}pt\" viewBox=\"0 0 {PAGE_WIDTH} {PAGE_HEIGHT}\" overflow=\"hidden\">\n  \
<title>Berreta Futura cover</title>\n  \
<g id=\"cover\" data-design=\"{}\">\n    {body}\n  </g>\n</svg>\n",
            escape(&self.design.id)
        )
    }

    pub fn footer_caption(&mut self, text: &CoverText, cover_art: &Path) -> Result<String> {
        let spec_margin = self.design.footer_caption.margin;
        let scale = self.design.footer_caption.wordmark_scale;
        let band = self.band_x();
        let right_edge = band - spec_margin;
        let (top, bottom) = art_zones(cover_art, band, PAGE_HEIGHT)?;
        let dark_bottom = bottom.mean < 105.0;
        let fill = if dark_bottom {
            self.design.colors.paper.clone()
        } else {
            self.design.colors.ink.clone()
        };

        let art_data = base64::engine::general_purpose::STANDARD.encode(graded_art(cover_art)?);
        let mut parts = vec![format!(
            "<image data-slot=\"art\" x=\"0\" y=\"0\" width=\"{}\" height=\"{}\" preserveAspectRatio=\"xMidYMid slice\" href=\"data:image/png;base64,{art_data}\"/>",
            pyf(band),
            pyf(PAGE_HEIGHT)
        )];

        parts.extend(self.caption_gradients(dark_bottom, &top, &bottom, band));
        let mode = if top.mean < 118.0 { "light" } else { "dark" };
        let dy = self.design.footer_caption.wordmark_dy;
        parts.push(self.margin_locked_wordmark(
            &text.publication_name,
            mode,
            scale,
            spec_margin,
            dy,
        )?);
        self.caption_body(&mut parts, text, spec_margin, right_edge, &fill, band)?;
        Ok(self.shell(&parts.join("\n    ")))
    }

    fn caption_gradients(
        &self,
        dark_bottom: bool,
        top: &Zone,
        bottom: &Zone,
        band: f64,
    ) -> Vec<String> {
        let mut parts = Vec::new();
        if dark_bottom && bottom.stddev > 46.0 {
            parts.push(gradient(Gradient {
                id: "cap-b",
                x: "0",
                y: PAGE_HEIGHT - 170.0,
                w: band,
                h: "170",
                color: &self.design.colors.ink,
                top: 0.0,
                bottom: 0.72,
            }));
        }
        if !dark_bottom {
            parts.push(gradient(Gradient {
                id: "cap-b",
                x: "0",
                y: PAGE_HEIGHT - 170.0,
                w: band,
                h: "170",
                color: &self.design.colors.paper,
                top: 0.0,
                bottom: 0.7,
            }));
        }
        if top.stddev > 52.0 && top.mean < 150.0 {
            parts.push(gradient(Gradient {
                id: "cap-t",
                x: "0",
                y: 0.0,
                w: band,
                h: "120",
                color: &self.design.colors.ink,
                top: 0.42,
                bottom: 0.0,
            }));
        }
        parts
    }

    fn caption_body(
        &mut self,
        parts: &mut Vec<String>,
        text: &CoverText,
        spec_margin: f64,
        right_edge: f64,
        fill: &str,
        band: f64,
    ) -> Result<()> {
        let title = text.headline.to_uppercase().trim().to_string();
        let size = self.fit_display_line(
            &title,
            self.design.footer_caption.title_size,
            right_edge - spec_margin - 62.0,
        )?;
        let headline = self
            .fonts
            .display
            .outline(
                &title,
                spec_margin,
                PAGE_HEIGHT - 46.0,
                size,
                fill,
                0.2,
                100.0,
                None,
                "",
            )?
            .markup;
        parts.push(format!("<g data-slot=\"headline\">{headline}</g>"));

        parts.push(self.right_line(&text.date_line, right_edge, PAGE_HEIGHT - 46.0, 7.0, fill)?);

        if !text.contributors.is_empty() {
            let deck = self.justified_line(
                &text.contributors,
                spec_margin,
                PAGE_HEIGHT - 24.0,
                4.6,
                fill,
                right_edge - spec_margin,
            )?;
            parts.push(format!("<g data-slot=\"deck\">{deck}</g>"));
        }

        parts.push(format!(
            "<rect data-slot=\"edge-tab\" x=\"{band:.5}\" y=\"-1.5\" width=\"{:.5}\" height=\"{}\" fill=\"{}\"/>",
            PAGE_WIDTH - band - self.design.tab.edge_reveal,
            pyf(PAGE_HEIGHT + 3.0),
            self.design.colors.orange
        ));
        parts.extend(self.tab_labels(text)?);
        Ok(())
    }
}
