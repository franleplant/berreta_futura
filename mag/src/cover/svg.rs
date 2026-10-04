use std::path::Path;

use anyhow::{bail, Context, Result};
use base64::Engine as _;

use super::art::{art_zones, extreme_pixels, graded_art, luminance, Zone};
use super::outline::Outliner;

pub const PAGE_WIDTH: f64 = 419.527559;
pub const PAGE_HEIGHT: f64 = 595.275591;
pub const WORDMARK_SVG: &str = include_str!("../../assets/brand/wordmark.svg");
pub const MARK_SVG: &str = include_str!("../../assets/brand/mark.svg");
pub const MARK_SQUARE_SVG: &str = include_str!("../../assets/brand/mark-square.svg");
const WORDMARK_INSET: (f64, f64) = (2.85, -28.91);
const WORDMARK_HEIGHT: f64 = 75.13;

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

pub fn brand_view(svg: &str) -> [f64; 4] {
    let view = svg
        .split_once("viewBox=\"")
        .and_then(|(_, rest)| rest.split_once('"'))
        .map_or("", |(view, _)| view);
    let mut numbers = view.split(' ').map(|v| v.parse().unwrap_or(0.0));
    [0; 4].map(|_| numbers.next().unwrap_or(0.0))
}

pub fn brand_body(svg: &str) -> &str {
    let start = svg.find("</title>").map_or(0, |at| at + "</title>".len());
    &svg[start..svg.rfind("</svg>").unwrap_or(svg.len())]
}

pub fn paint<'a>(markup: &str, colour: impl Fn(&str) -> Option<&'a str>) -> String {
    let mut out = String::new();
    let mut rest = markup;
    while let Some(at) = rest.find("var(--") {
        out.push_str(&rest[..at]);
        let tail = &rest[at + "var(--".len()..];
        let end = tail.find(')').unwrap_or(tail.len());
        let (name, fallback) = tail[..end].split_once(", ").unwrap_or((&tail[..end], ""));
        out.push_str(colour(name).unwrap_or(fallback));
        rest = tail.get(end + 1..).unwrap_or("");
    }
    out + rest
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

fn hex(colour: &str) -> Result<[f64; 3]> {
    let channel = |at: usize| {
        u8::from_str_radix(colour.get(at..at + 2).unwrap_or(""), 16)
            .map(|value| f64::from(value) / 255.0)
            .with_context(|| format!("cover colour {colour} is not #rrggbb"))
    };
    Ok([channel(1)?, channel(3)?, channel(5)?])
}

fn scrim_alpha(text: [f64; 3], scrim: [f64; 3], pixel: [f64; 3]) -> f64 {
    let ink = luminance(text);
    (0..=50)
        .map(|step| f64::from(step) / 50.0)
        .find(|alpha| {
            let ground = luminance([0, 1, 2].map(|c| alpha * scrim[c] + (1.0 - alpha) * pixel[c]));
            (ink.max(ground) + 0.05) / (ink.min(ground) + 0.05) >= 7.0
        })
        .unwrap_or(1.0)
}

fn scrim_band(colour: &str, alpha: f64, top: f64, band: f64) -> String {
    let height = PAGE_HEIGHT - top;
    format!(
        "<defs><linearGradient id=\"cap-b\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">\
<stop offset=\"0\" stop-color=\"{colour}\" stop-opacity=\"0\"/>\
<stop offset=\"{}\" stop-color=\"{colour}\" stop-opacity=\"{}\"/>\
<stop offset=\"1\" stop-color=\"{colour}\" stop-opacity=\"{}\"/>\
</linearGradient></defs>\
<rect x=\"0\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"url(#cap-b)\"/>",
        pyf(60.0 / height),
        pyf(alpha),
        pyf(alpha),
        pyf(top),
        pyf(band),
        pyf(height)
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

    fn wordmark(&self, on_dark: bool) -> String {
        let (colors, spot) = (&self.design.colors, &self.design.wordmark);
        let [vx, vy, vw, vh] = brand_view(WORDMARK_SVG);
        let (x, y) = (spot.x + WORDMARK_INSET.0, spot.top + WORDMARK_INSET.1);
        let max_width = PAGE_WIDTH - self.design.tab.width - spot.right_reserve - WORDMARK_INSET.0;
        let scale = (WORDMARK_HEIGHT / vh).min(max_width / vw);
        let body = brand_body(WORDMARK_SVG).to_string();
        let head = if on_dark { &colors.paper } else { &colors.ink };
        let body = paint(&body, |name| match name {
            "ink" => Some(head.as_str()),
            "paper" => Some(colors.paper.as_str()),
            "red" => Some(colors.orange.as_str()),
            "box" => Some(colors.ink.as_str()),
            _ => None,
        });
        format!(
            "<g data-slot=\"wordmark\" transform=\"translate({x:.4} {y:.4}) scale({scale:.6}) translate({} {})\">{body}</g>",
            pyf(-vx),
            pyf(-vy)
        )
    }

    fn scaled_wordmark(&self, on_dark: bool, scale: f64, dx: f64, dy: f64) -> String {
        format!(
            "<g transform=\"translate({dx:.4} {dy:.4}) scale({})\">{}</g>",
            pyf(scale),
            self.wordmark(on_dark)
        )
    }

    fn margin_locked_wordmark(&self, on_dark: bool, scale: f64, margin: f64, dy: f64) -> String {
        let dx = margin - (self.design.wordmark.x + 0.36) * scale;
        self.scaled_wordmark(on_dark, scale, dx, dy)
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

    fn fitted_roster(&mut self, roster: &str, size: f64, width: f64) -> Result<String> {
        let names: Vec<&str> = roster.split(" / ").collect();
        for keep in (1..=names.len()).rev() {
            let line = match keep == names.len() {
                true => roster.to_string(),
                false => format!("{} / \u{2026}", names[..keep].join(" / ")),
            };
            if self.fonts.regular.measure(&line, size, 0.0, 100.0)? <= width {
                return Ok(line);
            }
        }
        Ok("\u{2026}".to_string())
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
        let (ax, ay) = (self.design.art.x, self.design.art.top);
        let (aw, ah) = (self.design.art.width, self.design.art.height);
        let art = self.full_art(cover_art, ax, ay, aw, ah)?;
        self.framed_with(text, art)
    }

    pub fn framed_with(&mut self, text: &CoverText, art: String) -> Result<String> {
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
        parts.push(self.wordmark(false));
        parts.push(self.headline(&text.headline)?);
        let (ax, ay) = (self.design.art.x, self.design.art.top);
        let (aw, ah) = (self.design.art.width, self.design.art.height);
        parts.push(art);
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
                false,
                self.design.honored_plate.wordmark_scale,
                6.0,
                PAGE_HEIGHT - footer - 22.0 - 14.0,
            ),
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
        let (top, _) = art_zones(cover_art, band, PAGE_HEIGHT)?;
        let title_top = PAGE_HEIGHT - 46.0 - self.design.footer_caption.title_size;
        let area = [spec_margin, title_top, right_edge, PAGE_HEIGHT - 18.0];
        let (darkest, brightest) = extreme_pixels(cover_art, band, PAGE_HEIGHT, area)?;
        let (paper, ink) = (&self.design.colors.paper, &self.design.colors.ink);
        let on_paper = scrim_alpha(hex(ink)?, hex(paper)?, darkest);
        let on_ink = scrim_alpha(hex(paper)?, hex(ink)?, brightest);
        let (fill, scrim, alpha) = match on_ink < on_paper {
            true => (paper.clone(), ink.clone(), on_ink),
            false => (ink.clone(), paper.clone(), on_paper),
        };

        let art_data = base64::engine::general_purpose::STANDARD.encode(graded_art(cover_art)?);
        let mut parts = vec![format!(
            "<image data-slot=\"art\" x=\"0\" y=\"0\" width=\"{}\" height=\"{}\" preserveAspectRatio=\"xMidYMid slice\" href=\"data:image/png;base64,{art_data}\"/>",
            pyf(band),
            pyf(PAGE_HEIGHT)
        )];

        parts.push(scrim_band(&scrim, alpha, title_top - 60.0, band));
        parts.extend(self.caption_gradients(&top, band));
        let dy = self.design.footer_caption.wordmark_dy;
        parts.push(self.margin_locked_wordmark(top.mean < 118.0, scale, spec_margin, dy));
        self.caption_body(&mut parts, text, spec_margin, right_edge, &fill, band)?;
        Ok(self.shell(&parts.join("\n    ")))
    }

    fn caption_gradients(&self, top: &Zone, band: f64) -> Vec<String> {
        let mut parts = Vec::new();
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
            let roster = self.fitted_roster(&text.contributors, 4.6, right_edge - spec_margin)?;
            let deck = self.justified_line(
                &roster,
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
