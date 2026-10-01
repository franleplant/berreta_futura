use crate::cover::raster::render;
use crate::cover::svg::{escape, pyf, Builder, Fonts};
use anyhow::{anyhow, Result};
use std::path::Path;

const DARK: &str = "@media (prefers-color-scheme: dark){.wm-ink{fill:#e7e5e0;stroke:#e7e5e0}.wm-box{stroke:#e7e5e0;stroke-opacity:.35}}";

pub struct Logo {
    pub inline: String,
    pub favicon: String,
    pub touch: Vec<u8>,
    pub card: Vec<u8>,
}

pub fn build(root: &Path, name: &str) -> Result<Logo> {
    let (design, _) = crate::typeset::cover::design(root)?;
    let mut fonts = Fonts::load(&root.join("mag/assets"))?;
    let (mark, bounds) = Builder {
        design: &design,
        fonts: &mut fonts,
    }
    .logo(name)?;
    let (ink, paper) = (&design.colors.ink, &design.colors.paper);
    let themed = mark
        .replace(&format!("fill=\"{ink}\""), "class=\"wm-ink\"")
        .replace(&format!("fill=\"{paper}\""), "class=\"wm-paper\"")
        .replacen("class=\"wm-ink\"/>", "class=\"wm-box\"/>", 1);
    let [x, y, w, h] = bounds;
    let side = w.max(h);
    let square = [x - (side - w) / 2.0, y - (side - h) / 2.0, side, side];
    let label = escape(name).replace('"', "&quot;");
    let style = format!(
        "<style>.wm-ink{{fill:{ink};stroke:{ink}}}.wm-box{{fill:{ink}}}.wm-paper{{fill:{paper};stroke:{paper}}}{DARK}</style>"
    );
    Ok(Logo {
        inline: format!(
            "<svg class=\"logo\" viewBox=\"{}\" role=\"img\" aria-label=\"{label}\">{themed}</svg>",
            view(bounds)
        ),
        favicon: format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"{}\">{style}{themed}</svg>\n",
            view(square)
        ),
        touch: png(&mark, bounds, paper, (180.0, 180.0), 0.82)?,
        card: png(&mark, bounds, paper, (1200.0, 630.0), 0.6)?,
    })
}

fn view(bounds: [f64; 4]) -> String {
    bounds.map(pyf).join(" ")
}

fn png(mark: &str, bounds: [f64; 4], paper: &str, size: (f64, f64), share: f64) -> Result<Vec<u8>> {
    let ([x, y, w, h], (width, height)) = (bounds, size);
    let scale = (width * share / w).min(height * share / h);
    let dx = (width - w * scale) / 2.0 - x * scale;
    let dy = (height - h * scale) / 2.0 - y * scale;
    let svg = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">\
<rect width=\"{width}\" height=\"{height}\" fill=\"{paper}\"/>\
<g transform=\"translate({dx:.4} {dy:.4}) scale({scale:.6})\">{mark}</g></svg>"
    );
    render(&svg)?
        .encode_png()
        .map_err(|error| anyhow!("Could not encode the logo PNG: {error}"))
}
