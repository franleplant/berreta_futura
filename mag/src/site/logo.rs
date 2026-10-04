use anyhow::{anyhow, Result};

const WORDMARK_SVG: &str = include_str!("../../assets/brand/wordmark.svg");
const MARK_SVG: &str = include_str!("../../assets/brand/mark.svg");
const MARK_SQUARE_SVG: &str = include_str!("../../assets/brand/mark-square.svg");

fn pyf(value: f64) -> String {
    if value == value.trunc() && value.abs() < 1e16 {
        format!("{value:.1}")
    } else {
        format!("{value}")
    }
}

fn brand_view(svg: &str) -> [f64; 4] {
    let view = svg
        .split_once("viewBox=\"")
        .and_then(|(_, rest)| rest.split_once('"'))
        .map_or("", |(view, _)| view);
    let mut numbers = view.split(' ').map(|v| v.parse().unwrap_or(0.0));
    [0; 4].map(|_| numbers.next().unwrap_or(0.0))
}

fn brand_body(svg: &str) -> &str {
    let start = svg.find("</title>").map_or(0, |at| at + "</title>".len());
    &svg[start..svg.rfind("</svg>").unwrap_or(svg.len())]
}

fn paint(markup: &str) -> String {
    let mut out = String::new();
    let mut rest = markup;
    while let Some(at) = rest.find("var(--") {
        out.push_str(&rest[..at]);
        let tail = &rest[at + "var(--".len()..];
        let end = tail.find(')').unwrap_or(tail.len());
        let fallback = tail[..end]
            .split_once(", ")
            .map_or("", |(_, fallback)| fallback);
        out.push_str(fallback);
        rest = tail.get(end + 1..).unwrap_or("");
    }
    out + rest
}

fn escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn render(svg: &str) -> Result<tiny_skia::Pixmap> {
    let tree = usvg::Tree::from_str(svg, &usvg::Options::default())
        .map_err(|error| anyhow!("Could not parse the logo SVG: {error}"))?;
    let size = tree.size().to_int_size();
    let mut pixmap = tiny_skia::Pixmap::new(size.width(), size.height())
        .ok_or_else(|| anyhow!("The logo raster size is invalid"))?;
    resvg::render(
        &tree,
        tiny_skia::Transform::identity(),
        &mut pixmap.as_mut(),
    );
    Ok(pixmap)
}

pub struct Logo {
    pub inline: String,
    pub favicon: String,
    pub touch: Vec<u8>,
    pub card: Vec<u8>,
}

pub fn build(name: &str) -> Result<Logo> {
    let label = escape(name).replace('"', "&quot;");
    let view = brand_view(WORDMARK_SVG).map(pyf).join(" ");
    Ok(Logo {
        inline: format!(
            "<svg class=\"logo\" viewBox=\"{view}\" role=\"img\" aria-label=\"{label}\">{}</svg>",
            brand_body(WORDMARK_SVG)
        ),
        favicon: MARK_SVG.to_string(),
        touch: png(MARK_SQUARE_SVG, (180.0, 180.0), 1.0)?,
        card: png(WORDMARK_SVG, (1200.0, 630.0), 0.6)?,
    })
}

fn png(svg: &str, (width, height): (f64, f64), share: f64) -> Result<Vec<u8>> {
    let [x, y, w, h] = brand_view(svg);
    let scale = (width * share / w).min(height * share / h);
    let dx = (width - w * scale) / 2.0 - x * scale;
    let dy = (height - h * scale) / 2.0 - y * scale;
    let body = paint(brand_body(svg));
    let page = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">\
<rect width=\"{width}\" height=\"{height}\" fill=\"#ffffff\"/>\
<g transform=\"translate({dx:.4} {dy:.4}) scale({scale:.6})\">{body}</g></svg>"
    );
    render(&page)?
        .encode_png()
        .map_err(|error| anyhow!("Could not encode the logo PNG: {error}"))
}
