use anyhow::{anyhow, Result};
use regex::Regex;

use super::svg::{PAGE_HEIGHT, PAGE_WIDTH};

fn blank_slot(svg: &str, slot: &str) -> String {
    let pattern = Regex::new(&format!(
        "(<rect data-slot=\"{slot}\"[^>]*?) fill=\"[^\"]+\""
    ))
    .expect("static pattern");
    pattern.replace(svg, "$1 fill=\"none\"").into_owned()
}

pub fn raster_svg(svg: &str, dpi: u32) -> String {
    let pixel_width = (PAGE_WIDTH / 72.0 * f64::from(dpi)).round() as u32;
    let pixel_height = (PAGE_HEIGHT / 72.0 * f64::from(dpi)).round() as u32;
    let size = Regex::new("width=\"[^\"]+\" height=\"[^\"]+\"").expect("static pattern");
    let sized = size
        .replace(
            svg,
            format!("width=\"{pixel_width}\" height=\"{pixel_height}\"").as_str(),
        )
        .into_owned();
    let mut out = sized;
    for slot in ["paper", "edge-tab", "field"] {
        out = blank_slot(&out, slot);
    }
    out
}

pub fn render(svg: &str) -> Result<tiny_skia::Pixmap> {
    let tree = usvg::Tree::from_str(svg, &usvg::Options::default())
        .map_err(|error| anyhow!("Could not parse cover SVG: {error}"))?;
    let size = tree.size().to_int_size();
    let mut pixmap = tiny_skia::Pixmap::new(size.width(), size.height())
        .ok_or_else(|| anyhow!("Cover raster size is invalid"))?;
    resvg::render(
        &tree,
        tiny_skia::Transform::identity(),
        &mut pixmap.as_mut(),
    );
    Ok(pixmap)
}
