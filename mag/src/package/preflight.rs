use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use lopdf::{Document, Object, ObjectId};
use serde_json::{json, Map, Value};

use crate::critic::metrics::{prepare_print_image, round_places, PreparedPrintImage};
use crate::impose::{section_reader_pages, A4_LANDSCAPE_POINTS};

pub const A5_POINTS: (f64, f64) = (419.5276, 595.2756);

const NEAR_TOLERANCE: f64 = 0.75;
const STUDIO_PPI_TARGET: f64 = 300.0;

#[derive(Debug, Clone)]
pub struct FigurePlacement {
    pub figure_id: String,
    pub article_id: String,
    pub page: i64,
    pub path: PathBuf,
    pub pixel_dimensions: Option<(u32, u32)>,
    pub box_points: Vec<f64>,
    pub effective_ppi: Option<f64>,
    pub caption: String,
    pub credit: String,
}

struct Messages {
    pdfx: &'static str,
    bleed: &'static str,
    cover_resolution: &'static str,
    figure_resolution: &'static str,
    figure_geometry: &'static str,
    figure_contrast: &'static str,
}

const ENGLISH: Messages = Messages {
    pdfx: "PDF/X-4 conversion and printer output intent are not configured.",
    bleed: "Trim bleed is not configured for the selected printer.",
    cover_resolution: "Cover artwork is below the 300 ppi studio target at its rendered placement.",
    figure_resolution: "One or more curated figures are below 300 ppi at their rendered placement.",
    figure_geometry: "One or more curated figure placements are invalid or collide.",
    figure_contrast: "One or more curated figures remain too faint after print-contrast treatment.",
};

const SPANISH: Messages = Messages {
    pdfx: "No están configurados la conversión a PDF/X-4 ni el propósito de salida de la imprenta.",
    bleed: "No está configurado el sangrado de corte para la imprenta seleccionada.",
    cover_resolution:
        "La ilustración de cubierta no alcanza el objetivo de 300 ppp en su tamaño de reproducción.",
    figure_resolution:
        "Una o más figuras seleccionadas no alcanzan 300 ppp en su tamaño de reproducción.",
    figure_geometry:
        "Una o más ubicaciones de figuras seleccionadas son inválidas o se superponen.",
    figure_contrast: "Una o más figuras seleccionadas siguen siendo demasiado tenues después del ajuste de contraste para impresión.",
};

fn messages_for(language: &str) -> &'static Messages {
    match language.split_once('-').map_or(language, |(head, _)| head) {
        "es" => &SPANISH,
        _ => &ENGLISH,
    }
}

fn near(actual: (f64, f64), expected: (f64, f64)) -> bool {
    (actual.0 - expected.0).abs() <= NEAR_TOLERANCE
        && (actual.1 - expected.1).abs() <= NEAR_TOLERANCE
}

fn effective_image_ppi(pixels: (u32, u32), placement: (f64, f64)) -> f64 {
    let horizontal = f64::from(pixels.0) / (placement.0 / 72.0);
    let vertical = f64::from(pixels.1) / (placement.1 / 72.0);
    horizontal.min(vertical)
}

fn png_dimensions(bytes: &[u8]) -> Option<(u32, u32)> {
    let header = bytes.get(..8)?;
    if header != b"\x89PNG\r\n\x1a\n" || bytes.get(12..16)? != b"IHDR" {
        return None;
    }
    let width = u32::from_be_bytes(bytes.get(16..20)?.try_into().ok()?);
    let height = u32::from_be_bytes(bytes.get(20..24)?.try_into().ok()?);
    Some((width, height))
}

fn jpeg_dimensions(bytes: &[u8]) -> Option<(u32, u32)> {
    if bytes.get(..2)? != b"\xff\xd8" {
        return None;
    }
    let mut cursor = 2usize;
    while cursor + 3 < bytes.len() {
        if bytes[cursor] != 0xff {
            cursor += 1;
            continue;
        }
        let marker = bytes[cursor + 1];
        if matches!(marker, 0xd8 | 0xd9 | 0xff) || (0xd0..=0xd7).contains(&marker) {
            cursor += 2;
            continue;
        }
        let length = u16::from_be_bytes(bytes.get(cursor + 2..cursor + 4)?.try_into().ok()?);
        let frame = matches!(marker, 0xc0..=0xc3 | 0xc5..=0xc7 | 0xc9..=0xcb | 0xcd..=0xcf);
        if frame {
            let height = u16::from_be_bytes(bytes.get(cursor + 5..cursor + 7)?.try_into().ok()?);
            let width = u16::from_be_bytes(bytes.get(cursor + 7..cursor + 9)?.try_into().ok()?);
            return Some((u32::from(width), u32::from(height)));
        }
        cursor += 2 + usize::from(length);
    }
    None
}

fn raster_dimensions(path: Option<&Path>) -> Option<(u32, u32)> {
    let path = path?;
    let extension = path.extension()?.to_str()?.to_ascii_lowercase();
    if !matches!(extension.as_str(), "png" | "jpg" | "jpeg") || !path.is_file() {
        return None;
    }
    let bytes = std::fs::read(path).ok()?;
    png_dimensions(&bytes).or_else(|| jpeg_dimensions(&bytes))
}

fn inherited_media_box(document: &Document, page: ObjectId) -> Result<(f64, f64)> {
    let mut current = Some(page);
    while let Some(id) = current {
        let dictionary = document.get_dictionary(id)?;
        if let Ok(entry) = dictionary.get(b"MediaBox") {
            let items = document.dereference(entry)?.1.as_array()?;
            let mut edges = [0.0f64; 4];
            for (slot, item) in edges.iter_mut().zip(items.iter()) {
                *slot = match document.dereference(item)?.1 {
                    Object::Integer(value) => *value as f64,
                    Object::Real(value) => f64::from(*value),
                    other => anyhow::bail!("MediaBox carries a non-numeric entry {other:?}"),
                };
            }
            return Ok(((edges[2] - edges[0]).abs(), (edges[3] - edges[1]).abs()));
        }
        current = dictionary
            .get(b"Parent")
            .ok()
            .and_then(|parent| parent.as_reference().ok());
    }
    anyhow::bail!("page {page:?} has no MediaBox")
}

struct Pdf {
    sizes: Vec<(f64, f64)>,
    encrypted: bool,
}

impl Pdf {
    fn read(path: &Path) -> Result<Self> {
        let document =
            Document::load(path).with_context(|| format!("cannot read pdf {}", path.display()))?;
        let pages: BTreeMap<u32, ObjectId> = document.get_pages();
        let mut sizes = Vec::with_capacity(pages.len());
        for id in pages.into_values() {
            sizes.push(inherited_media_box(&document, id)?);
        }
        Ok(Self {
            sizes,
            encrypted: document.is_encrypted(),
        })
    }

    fn page_count(&self) -> usize {
        self.sizes.len()
    }

    fn all_near(&self, expected: (f64, f64)) -> bool {
        self.sizes.iter().all(|size| near(*size, expected))
    }
}

fn booklet_section_facts(
    document: &Pdf,
    reader_page_count: usize,
    section: &str,
    stock: &str,
) -> Result<Value> {
    let expected = if reader_page_count >= 4 {
        section_reader_pages(reader_page_count, section)?
    } else {
        Vec::new()
    };
    let single_sided = section == "cover";
    let sides = document.page_count();
    let expected_sheets = if single_sided {
        1
    } else {
        expected.len().div_ceil(4)
    };
    Ok(json!({
        "reader_pages": expected,
        "sheet_sides": sides,
        "sheets": if single_sided { sides } else { sides / 2 },
        "expected_sheets": expected_sheets,
        "all_pages_a4_landscape": document.all_near(A4_LANDSCAPE_POINTS),
        "encrypted": document.encrypted,
        "print_scale": "100%",
        "duplex_flip": if single_sided { "none (single-sided)" } else { "short edge" },
        "stock": stock,
    }))
}

fn cover_facts(cover_art: Option<&Path>, placement_points: Option<(f64, f64)>) -> Value {
    let dimensions = raster_dimensions(cover_art);
    let mut info = Map::new();
    info.insert(
        "path".into(),
        cover_art.map_or(Value::Null, |path| json!(path.display().to_string())),
    );
    info.insert(
        "pixel_dimensions".into(),
        dimensions.map_or(Value::Null, |(width, height)| json!([width, height])),
    );
    if let Some(pixels) = dimensions {
        let placement = placement_points.unwrap_or(A5_POINTS);
        let at_placement = effective_image_ppi(pixels, placement);
        info.insert(
            "effective_ppi_at_a5".into(),
            json!(round_places(effective_image_ppi(pixels, A5_POINTS), 1)),
        );
        info.insert(
            "placement_points".into(),
            json!([round_places(placement.0, 3), round_places(placement.1, 3)]),
        );
        info.insert(
            "effective_ppi_at_placement".into(),
            json!(round_places(at_placement, 1)),
        );
        info.insert(
            "studio_300ppi_target_met".into(),
            json!(at_placement >= STUDIO_PPI_TARGET),
        );
    }
    Value::Object(info)
}

struct FigureRow {
    row: Value,
    prepared: Option<PreparedPrintImage>,
    figure_id: String,
    page: i64,
    box_points: Vec<f64>,
    effective_ppi: Option<f64>,
}

fn figure_row(placement: &FigurePlacement) -> Result<FigureRow> {
    let dimensions = placement
        .pixel_dimensions
        .or_else(|| raster_dimensions(Some(&placement.path)));
    let box_points: Vec<f64> = placement
        .box_points
        .iter()
        .map(|value| round_places(*value, 3))
        .collect();
    let placement_size: Vec<f64> = if placement.box_points.len() == 4 {
        placement.box_points[2..].to_vec()
    } else {
        placement.box_points.clone()
    };
    let mut ppi = placement.effective_ppi;
    if ppi.is_none() {
        if let (Some(pixels), 2) = (dimensions, placement_size.len()) {
            ppi = Some(effective_image_ppi(
                pixels,
                (placement_size[0], placement_size[1]),
            ));
        }
    }
    let mut contrast = Value::Null;
    let mut prepared = None;
    if dimensions.is_some() {
        let outcome = prepare_print_image(&placement.path)?;
        contrast = json!({
            "paper_pixel_ratio": outcome.before.paper_pixel_ratio,
            "mark_pixel_ratio": outcome.before.mark_pixel_ratio,
            "minimum_mark_contrast_ratio": outcome.before.minimum_mark_contrast_ratio,
            "needs_treatment": outcome.before.needs_treatment,
            "treatment": if outcome.adjusted { "contrast_strengthened" } else { "none" },
            "post_treatment_minimum_mark_contrast_ratio": outcome.after.minimum_mark_contrast_ratio,
        });
        prepared = Some(outcome);
    }
    let rounded_ppi = ppi.map(|value| round_places(value, 1));
    let row = json!({
        "figure_id": placement.figure_id,
        "article_id": placement.article_id,
        "page": placement.page,
        "path": placement.path.display().to_string(),
        "pixel_dimensions": dimensions.map_or(Value::Null, |(width, height)| json!([width, height])),
        "box_points": box_points,
        "effective_ppi": rounded_ppi.map_or(Value::Null, |value| json!(value)),
        "caption": placement.caption,
        "credit": placement.credit,
        "print_contrast": contrast,
    });
    Ok(FigureRow {
        row,
        prepared,
        figure_id: placement.figure_id.clone(),
        page: placement.page,
        box_points,
        effective_ppi: rounded_ppi,
    })
}

fn box_invalid(row: &FigureRow, page_count: usize) -> bool {
    let (x, y, width, height) = (
        row.box_points[0],
        row.box_points[1],
        row.box_points[2],
        row.box_points[3],
    );
    row.page < 1
        || row.page > page_count as i64
        || width <= 0.0
        || height <= 0.0
        || x < 0.0
        || y < 0.0
        || x + width > A5_POINTS.0 + NEAR_TOLERANCE
        || y + height > A5_POINTS.1 + NEAR_TOLERANCE
}

fn figure_geometry(rows: &[FigureRow], page_count: usize) -> (Vec<Value>, Vec<Value>) {
    let mut invalid = Vec::new();
    let mut collisions = Vec::new();
    let mut by_page: BTreeMap<i64, Vec<&FigureRow>> = BTreeMap::new();
    for row in rows {
        if row.box_points.len() != 4 || box_invalid(row, page_count) {
            invalid.push(json!({
                "figure_id": row.figure_id,
                "box_points": row.box_points,
            }));
            continue;
        }
        let (x, y, width, height) = (
            row.box_points[0],
            row.box_points[1],
            row.box_points[2],
            row.box_points[3],
        );
        let placed = by_page.entry(row.page).or_default();
        for previous in placed.iter() {
            let left = x.max(previous.box_points[0]);
            let bottom = y.max(previous.box_points[1]);
            let right = (x + width).min(previous.box_points[0] + previous.box_points[2]);
            let top = (y + height).min(previous.box_points[1] + previous.box_points[3]);
            if right > left && top > bottom {
                collisions.push(json!({
                    "figure_ids": [previous.figure_id, row.figure_id],
                    "page": row.page,
                }));
            }
        }
        placed.push(row);
    }
    (invalid, collisions)
}

#[allow(clippy::too_many_arguments)]
pub fn inspect_package(
    reader_pdf: &Path,
    booklet_pdf: &Path,
    interior_booklet_pdf: &Path,
    cover_booklet_pdf: &Path,
    cover_art: Option<&Path>,
    cover_art_size_points: Option<(f64, f64)>,
    figure_placements: &[FigurePlacement],
    language: &str,
) -> Result<Value> {
    let reader = Pdf::read(reader_pdf)?;
    let booklet = Pdf::read(booklet_pdf)?;
    let interior = Pdf::read(interior_booklet_pdf)?;
    let cover = Pdf::read(cover_booklet_pdf)?;
    let cover_info = cover_facts(cover_art, cover_art_size_points);

    let mut rows = Vec::with_capacity(figure_placements.len());
    for placement in figure_placements {
        rows.push(figure_row(placement)?);
    }
    let mut low_resolution = Vec::new();
    let mut contrast_adjusted = Vec::new();
    let mut unresolved = Vec::new();
    for row in &rows {
        if row
            .effective_ppi
            .is_none_or(|value| value < STUDIO_PPI_TARGET)
        {
            low_resolution.push(json!({
                "figure_id": row.figure_id,
                "effective_ppi": row.effective_ppi,
            }));
        }
        let Some(prepared) = &row.prepared else {
            continue;
        };
        if prepared.adjusted {
            contrast_adjusted.push(json!({
                "figure_id": row.figure_id,
                "minimum_mark_contrast_ratio": prepared.before.minimum_mark_contrast_ratio,
                "post_treatment_minimum_mark_contrast_ratio": prepared.after.minimum_mark_contrast_ratio,
            }));
        }
        if prepared.after.needs_treatment {
            unresolved.push(json!({
                "figure_id": row.figure_id,
                "post_treatment_minimum_mark_contrast_ratio": prepared.after.minimum_mark_contrast_ratio,
            }));
        }
    }
    let (invalid_boxes, collisions) = figure_geometry(&rows, reader.page_count());

    let messages = messages_for(language);
    let mut blockers = vec![json!(messages.pdfx), json!(messages.bleed)];
    if cover_info.get("studio_300ppi_target_met") == Some(&Value::Bool(false)) {
        blockers.push(json!(messages.cover_resolution));
    }
    if !low_resolution.is_empty() {
        blockers.push(json!(messages.figure_resolution));
    }
    if !invalid_boxes.is_empty() || !collisions.is_empty() {
        blockers.push(json!(messages.figure_geometry));
    }
    if !unresolved.is_empty() {
        blockers.push(json!(messages.figure_contrast));
    }

    let reader_pages = reader.page_count();
    Ok(json!({
        "schema_version": 1,
        "result": if blockers.is_empty() { "ready" } else { "home_ready_studio_blocked" },
        "reader": {
            "page_count": reader_pages,
            "page_count_multiple_of_four": reader_pages % 4 == 0,
            "all_pages_a5": reader.all_near(A5_POINTS),
            "encrypted": reader.encrypted,
        },
        "home_booklet": {
            "sheet_sides": booklet.page_count(),
            "sheets": booklet.page_count() / 2,
            "all_pages_a4_landscape": booklet.all_near(A4_LANDSCAPE_POINTS),
            "encrypted": booklet.encrypted,
            "print_scale": "100%",
            "duplex_flip": "short edge",
        },
        "home_booklet_interior": booklet_section_facts(&interior, reader_pages, "interior", "text")?,
        "home_booklet_cover": booklet_section_facts(&cover, reader_pages, "cover", "cover")?,
        "cover_art": cover_info,
        "figures": rows.iter().map(|row| row.row.clone()).collect::<Vec<_>>(),
        "low_resolution_figures": low_resolution,
        "contrast_adjusted_figures": contrast_adjusted,
        "unresolved_low_contrast_figures": unresolved,
        "invalid_figure_boxes": invalid_boxes,
        "figure_collisions": collisions,
        "studio": {"ready": blockers.is_empty(), "blockers": blockers},
    }))
}
