use crate::typeset::template::TEMPLATE_TYP;
use std::sync::LazyLock;

const MM_PT: f64 = 72.0 / 25.4;

pub struct Geometry {
    pub page_height: f64,
    pub live: f64,
    pub measure: f64,
    pub rail: f64,
    pub opener_rail: f64,
    pub datum: f64,
    pub margin_top: f64,
    pub margin_bottom: f64,
    pub epsilon: f64,
    pub paragraph_after: f64,
    pub body_leading: f64,
    pub figure_cap: f64,
    pub compact_figure_cap: f64,
    pub full_figure_cap: f64,
    pub plate_length: f64,
    pub plate_depth: f64,
    pub compact_inset: f64,
    pub article_cap: usize,
    pub verbatim_cap: usize,
}

fn declared(name: &str) -> f64 {
    let prefix = format!("#let {name} = ");
    TEMPLATE_TYP
        .lines()
        .find_map(|line| {
            let value = line.strip_prefix(&prefix)?;
            match value.strip_suffix("mm") {
                Some(mm) => Some(mm.parse::<f64>().ok()? * MM_PT),
                None => value.strip_suffix("pt").unwrap_or(value).parse().ok(),
            }
        })
        .unwrap_or_else(|| panic!("the template declares no numeric {name}"))
}

static GEOMETRY: LazyLock<Geometry> = LazyLock::new(|| {
    let (page_width, margin_inner, margin_outer) = (
        declared("PAGE-WIDTH"),
        declared("MARGIN-INNER"),
        declared("MARGIN-OUTER"),
    );
    let (live, measure) = (
        page_width - margin_inner - margin_outer,
        declared("MEASURE"),
    );
    Geometry {
        page_height: declared("PAGE-HEIGHT"),
        live,
        measure,
        rail: (live - measure) / 2.0,
        opener_rail: declared("OPENER-RAIL"),
        datum: declared("DATUM"),
        margin_top: declared("MARGIN-TOP"),
        margin_bottom: declared("MARGIN-BOTTOM"),
        epsilon: declared("PAGE-TOP-EPSILON"),
        paragraph_after: declared("PARAGRAPH-AFTER"),
        body_leading: declared("BODY-LEADING"),
        figure_cap: declared("FIGURE-MAX-HEIGHT"),
        compact_figure_cap: declared("COMPACT-FIGURE-MAX-HEIGHT"),
        full_figure_cap: declared("FULL-FIGURE-MAX-HEIGHT"),
        plate_length: declared("ROTATED-PLATE-LENGTH"),
        plate_depth: declared("ROTATED-PLATE-DEPTH"),
        compact_inset: declared("COMPACT-BAND-INSET"),
        article_cap: declared("ARTICLE-PAGE-CAP") as usize,
        verbatim_cap: declared("VERBATIM-PAGE-CAP") as usize,
    }
});

pub fn geometry() -> &'static Geometry {
    &GEOMETRY
}
