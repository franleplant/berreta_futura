use crate::cover::raster::render;
use crate::cover::svg::{
    brand_body, brand_view, escape, paint, pyf, MARK_SQUARE_SVG, MARK_SVG, WORDMARK_SVG,
};
use anyhow::{anyhow, Result};

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
    let body = paint(brand_body(svg), |_| None);
    let page = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">\
<rect width=\"{width}\" height=\"{height}\" fill=\"#ffffff\"/>\
<g transform=\"translate({dx:.4} {dy:.4}) scale({scale:.6})\">{body}</g></svg>"
    );
    render(&page)?
        .encode_png()
        .map_err(|error| anyhow!("Could not encode the logo PNG: {error}"))
}
