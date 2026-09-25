use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::critic::inspect::{PageInspection, RASTER_DPI};
use crate::critic::rules::{self, Critique, Inputs, Issue, PageAnnotation, Spread};
use crate::impose::{
    cover_wrap_plan, impose_a5_on_a4, imposed_reader_page_plan, A4_LANDSCAPE_POINTS,
};
use crate::package::contact::write_contact_sheets;
use crate::package::preflight::{inspect_package, FigurePlacement, Pdf};
use crate::trace::TextFace;

const RENDERED_TAIL_ARTS_KEY: &str = "_rendered_tail_arts";
const REVIEW_INSTRUCTIONS: &str = "Inspect every page on the contact sheets, then reopen every crop from its exact file path at original resolution. Do not approve from a resized preview. Automated checks do not judge typographic rhythm, visual hierarchy, or aesthetic quality. For an illustrated opener, verify the orange rectangle begins down and right: white remains outside the black frame at the top-right before the shadow begins and at the bottom-left before it begins. The crops/ set enlarges every opener block, placed figure, printed tail band, and flagged region at 300 ppi so type quality and locked geometry are judged from source pixels rather than thumbnails.";
const INTERIOR_RATIONALE: &str = "Interior sides re-impose reader pages that the reader pass already rasterizes and judges; imposition order is proven by exact left/right text pairing, so per-side rasters would only add build time.";

pub struct Release<'a> {
    pub reader_pdf: &'a Path,
    pub destination: &'a Path,
    pub manifest: Value,
    pub cover_art: Option<&'a Path>,
    pub cover_art_size_points: Option<(f64, f64)>,
    pub figure_placements: &'a [FigurePlacement],
    pub language: &'a str,
    pub toc: &'a BTreeMap<String, usize>,
    pub article_pages: &'a BTreeMap<String, usize>,
    pub editorial_pages: Option<i64>,
    pub edition_id: &'a str,
    pub recorded_review: Option<&'a Value>,
    pub fonts: &'a BTreeMap<String, TextFace>,
}

pub fn adopt_rendered_layout(manifest: &mut Value) -> Result<()> {
    let ledger = manifest
        .get_mut("edition")
        .and_then(Value::as_object_mut)
        .and_then(|edition| edition.remove(RENDERED_TAIL_ARTS_KEY));
    let (Some(ledger), Some(root)) = (
        ledger.filter(|value| !value.is_null()),
        manifest.as_object_mut(),
    ) else {
        return Ok(());
    };
    match root
        .entry("layout")
        .or_insert_with(|| json!({}))
        .as_object_mut()
    {
        Some(layout) => layout.insert("tail_arts".into(), ledger),
        None => bail!("manifest layout must be a mapping to adopt the rendered tail arts"),
    };
    Ok(())
}

pub fn sha256(path: &Path) -> Result<String> {
    let bytes = std::fs::read(path).with_context(|| format!("cannot read {}", path.display()))?;
    Ok(hex::encode(Sha256::digest(bytes)))
}

fn py_float(value: f64) -> String {
    if !value.is_finite() {
        return if value.is_nan() {
            "NaN"
        } else if value > 0.0 {
            "Infinity"
        } else {
            "-Infinity"
        }
        .into();
    }
    let scientific = format!("{value:e}");
    let (mantissa, exponent) = scientific.split_once('e').unwrap_or((&scientific, "0"));
    let exponent: i32 = exponent.parse().unwrap_or(0);
    if (-4..16).contains(&exponent) {
        let plain = format!("{value}");
        return if plain.contains('.') {
            plain
        } else {
            format!("{plain}.0")
        };
    }
    let sign = if exponent < 0 { '-' } else { '+' };
    format!("{mantissa}e{sign}{:02}", exponent.abs())
}

fn write_json(value: &Value, depth: usize, out: &mut String) {
    let pad = |level: usize| format!("\n{}", "  ".repeat(level));
    match value {
        Value::Number(number) => match number.as_f64().filter(|_| number.is_f64()) {
            Some(float) => out.push_str(&py_float(float)),
            None => out.push_str(&number.to_string()),
        },
        Value::Array(items) if !items.is_empty() => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                out.push_str(if index == 0 { "" } else { "," });
                out.push_str(&pad(depth + 1));
                write_json(item, depth + 1, out);
            }
            out.push_str(&pad(depth));
            out.push(']');
        }
        Value::Object(map) if !map.is_empty() => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            out.push('{');
            for (index, key) in keys.into_iter().enumerate() {
                out.push_str(if index == 0 { "" } else { "," });
                out.push_str(&pad(depth + 1));
                out.push_str(&Value::String(key.clone()).to_string());
                out.push_str(": ");
                write_json(&map[key], depth + 1, out);
            }
            out.push_str(&pad(depth));
            out.push('}');
        }
        other => out.push_str(&other.to_string()),
    }
}

pub fn py_json(value: &Value) -> String {
    let mut out = String::new();
    write_json(value, 0, &mut out);
    out.push('\n');
    out
}

fn write(path: &Path, text: &str) -> Result<()> {
    std::fs::write(path, text).with_context(|| format!("cannot write {}", path.display()))
}

fn relative(path: &Path, root: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .into_owned()
}

pub fn visual_review_status(
    review: Option<&Value>,
    edition_id: &str,
    language: &str,
    reader_pdf: &Path,
    booklet_pdf: &Path,
) -> Result<Value> {
    let reader_sha = sha256(reader_pdf)?;
    let booklet_sha = sha256(booklet_pdf)?;
    let mut status = json!({
        "status": "required_before_release",
        "reviewer": null,
        "reviewed_at": null,
        "result": null,
        "findings": [],
        "reader_sha256": reader_sha,
        "booklet_sha256": booklet_sha,
    });
    let Some(review) = review else {
        return Ok(status);
    };
    let Some(fields) = review.as_object() else {
        bail!("a recorded visual review must be a mapping");
    };
    let row = match fields.get("languages") {
        None => &Value::Null,
        Some(Value::Object(languages)) => languages.get(language).unwrap_or(&Value::Null),
        Some(_) => bail!("a recorded visual review's languages must be a mapping"),
    };
    let field = |key: &str| fields.get(key).cloned().unwrap_or(Value::Null);
    status["findings"] = match fields.get("findings") {
        None => json!([]),
        Some(Value::Array(items)) => json!(items),
        Some(Value::String(text)) => json!(text.chars().map(String::from).collect::<Vec<_>>()),
        Some(Value::Object(map)) => json!(map.keys().collect::<Vec<_>>()),
        Some(_) => bail!("a recorded visual review's findings must be iterable"),
    };
    let unchanged = row.get("reader_sha256") == Some(&json!(reader_sha))
        && row.get("booklet_sha256") == Some(&json!(booklet_sha));
    status["status"] = json!(if field("edition_id") != json!(edition_id)
        || !row.is_object()
        || !unchanged
    {
        "stale"
    } else if field("result") == json!("approved") {
        "approved"
    } else {
        "changes_required"
    });
    for key in ["reviewer", "reviewed_at", "result"] {
        status[key] = field(key);
    }
    Ok(status)
}

fn a4_landscape(pdf: &Pdf) -> bool {
    pdf.page_count() > 0 && pdf.all_near(A4_LANDSCAPE_POINTS)
}

struct Legs<'a> {
    booklet: &'a Path,
    interior: &'a Path,
    cover: &'a Path,
}

fn paths(items: &[PathBuf], root: &Path) -> Vec<String> {
    items.iter().map(|path| relative(path, root)).collect()
}

fn booklet_sections(
    critique: &Critique,
    legs: &Legs,
    root: &Path,
    page_count: usize,
) -> Result<serde_json::Map<String, Value>> {
    let (booklet, interior, cover) = (
        Pdf::read(legs.booklet)?,
        Pdf::read(legs.interior)?,
        Pdf::read(legs.cover)?,
    );
    let cover_plan = if page_count >= 4 {
        cover_wrap_plan(page_count)?.len()
    } else {
        0
    };
    let spreads = |rows: &[Spread]| rows.iter().map(Spread::as_row).collect::<Vec<Value>>();
    let inspected =
        |rows: &[PageInspection]| rows.iter().map(PageInspection::row).collect::<Vec<Value>>();
    let sections = json!({
        "home_booklet": {
            "path": relative(legs.booklet, root),
            "sheet_sides": booklet.page_count(),
            "raster_page_count_matches": critique.rasters.booklet.len() == booklet.page_count(),
            "binding": "saddle_stitch",
            "duplex_flip": "short_edge",
            "orientation": "upright",
            "spreads": spreads(&critique.spreads),
            "pages": inspected(&critique.booklet_pages),
        },
        "home_booklet_interior": {
            "path": relative(legs.interior, root),
            "reader_pages": critique.interior_reader_pages,
            "sheet_sides": interior.page_count(),
            "sheets": interior.page_count() / 2,
            "expected_sheet_sides": imposed_reader_page_plan(&critique.interior_reader_pages).len(),
            "all_sides_a4_landscape": a4_landscape(&interior),
            "binding": "saddle_stitch",
            "duplex_flip": "short_edge",
            "rasterized": false,
            "rasterization_rationale": INTERIOR_RATIONALE,
            "spreads": spreads(&critique.interior_spreads),
        },
        "home_booklet_cover": {
            "path": relative(legs.cover, root),
            "reader_pages": critique.cover_reader_pages,
            "sheet_sides": cover.page_count(),
            "sheets": cover.page_count(),
            "expected_sheet_sides": cover_plan,
            "all_sides_a4_landscape": a4_landscape(&cover),
            "binding": "saddle_stitch_wrap",
            "duplex_flip": "none (single-sided)",
            "rasterized": true,
            "raster_page_count_matches": critique.rasters.cover_booklet.len() == cover.page_count(),
            "inside_cover_sides": critique.cover_booklet_inside_sides,
            "spreads": spreads(&critique.cover_spreads),
            "pages": inspected(&critique.cover_booklet_pages),
        },
    });
    Ok(sections.as_object().cloned().unwrap_or_default())
}

fn render_report(
    release: &Release,
    critique: &Critique,
    legs: &Legs,
    sheets: (&[PathBuf], &[PathBuf]),
) -> Result<Value> {
    let root = release.destination;
    let page_count = Pdf::read(release.reader_pdf)?.page_count();
    let shape = rules::geometry(page_count, release.toc);
    let illustrated = rules::manifest_opener_article_ids(root);
    let errors = critique
        .issues
        .iter()
        .filter(|row| row.severity == "error")
        .count();
    let reviews = critique
        .issues
        .iter()
        .filter(|row| row.severity == "review")
        .count();
    let mut review = visual_review_status(
        release.recorded_review,
        release.edition_id,
        release.language,
        release.reader_pdf,
        legs.booklet,
    )?;
    let extra = json!({
        "reader_contact_sheets": paths(sheets.0, root),
        "booklet_contact_sheets": paths(sheets.1, root),
        "reader_pages": paths(&critique.rasters.reader, root),
        "booklet_sides": paths(&critique.rasters.booklet, root),
        "cover_booklet_sides": paths(&critique.rasters.cover_booklet, root),
        "crops": critique.crops,
        "instructions": REVIEW_INSTRUCTIONS,
    });
    for (key, value) in extra.as_object().into_iter().flatten() {
        review[key] = value.clone();
    }
    let mut report = json!({
        "schema_version": 1,
        "result": critique.result,
        "language": release.language,
        "reader": "reader.pdf",
        "page_count": page_count,
        "raster_dpi": RASTER_DPI,
        "checks": {
            "raster_page_count_matches": critique.rasters.reader.len() == page_count,
            "page_count_multiple_of_four": page_count % 4 == 0,
            "contents_pages": critique.contents_pages,
            "maximum_contents_pages": critique.maximum_contents_pages,
            "inside_cover_pages": shape.inside_cover_pages,
            "article_page_cap": 7,
            "editorial_page_cap": critique.editorial_page_cap,
            "live_area_points": critique.live_area_points,
            "void_min_height_points": rules::VOID_MIN_HEIGHT_POINTS,
            "void_min_width_fraction": rules::VOID_MIN_WIDTH_FRACTION,
            "void_report_limit": rules::VOID_REPORT_LIMIT,
            "tail_band_symmetry_tolerance_points": rules::TAIL_BAND_SYMMETRY_TOLERANCE_POINTS,
            "stub_body_line_minimum": rules::STUB_BODY_LINE_MINIMUM,
            "article_opener_offsets": critique.opener_offsets,
            "article_opener_offset_count_matches": critique.opener_offsets.len() == illustrated.len(),
            "article_opener_crop_fidelity": critique.opener_crop_fidelity,
        },
        "issues": critique.issues.iter().map(Issue::as_row).collect::<Vec<Value>>(),
        "summary": {"errors": errors, "review_items": reviews},
        "pages": critique.pages.iter().map(PageAnnotation::as_row).collect::<Vec<Value>>(),
        "visual_review": review,
    });
    for (key, value) in booklet_sections(critique, legs, root, page_count)? {
        report[key.as_str()] = value;
    }
    Ok(report)
}

fn inspect(release: &Release, legs: &Legs) -> Result<(PathBuf, Vec<PathBuf>)> {
    let root = release.destination;
    let reader = root.join("reader.pdf");
    let critique = rules::inspect_render(&Inputs {
        reader_pdf: &reader,
        booklet_pdf: legs.booklet,
        interior_booklet_pdf: legs.interior,
        cover_booklet_pdf: legs.cover,
        destination: root,
        toc: release.toc,
        article_pages: release.article_pages,
        editorial_pages: release.editorial_pages,
        fonts: release.fonts,
    })?;
    let review_dir = root.join("render-review");
    let reader_sheets = write_contact_sheets(
        &critique.rasters.reader,
        &review_dir,
        "reader-contact-sheet",
    )?;
    let booklet_sheets = write_contact_sheets(
        &critique.rasters.booklet,
        &review_dir,
        "booklet-contact-sheet",
    )?;
    let report = render_report(release, &critique, legs, (&reader_sheets, &booklet_sheets))?;
    let path = root.join("render-critic.json");
    write(&path, &py_json(&report))?;
    if critique.result == "fail" {
        let codes: Vec<&str> = critique
            .issues
            .iter()
            .filter(|row| row.severity == "error")
            .map(|row| row.code.as_str())
            .collect();
        bail!(
            "Render critic rejected {} reader: {}",
            release.language,
            codes.join(", ")
        );
    }
    let rasters = &critique.rasters;
    let artifacts = [
        &rasters.reader,
        &rasters.booklet,
        &rasters.cover_booklet,
        &reader_sheets,
        &booklet_sheets,
        &critique.crop_paths,
    ]
    .into_iter()
    .flatten()
    .cloned()
    .collect();
    Ok((path, artifacts))
}

pub fn package_release(mut release: Release) -> Result<Vec<PathBuf>> {
    adopt_rendered_layout(&mut release.manifest)?;
    let root = release.destination;
    std::fs::create_dir_all(root).with_context(|| format!("cannot create {}", root.display()))?;
    let reader = root.join("reader.pdf");
    std::fs::copy(release.reader_pdf, &reader)
        .with_context(|| format!("cannot copy {}", release.reader_pdf.display()))?;
    let booklet = impose_a5_on_a4(&reader, &root.join("booklet-a4.pdf"), "all")?;
    let interior = impose_a5_on_a4(&reader, &root.join("booklet-a4-interior.pdf"), "interior")?;
    let cover = impose_a5_on_a4(&reader, &root.join("booklet-a4-cover.pdf"), "cover")?;
    let manifest = root.join("edition-manifest.json");
    write(&manifest, &py_json(&release.manifest))?;
    let legs = Legs {
        booklet: &booklet,
        interior: &interior,
        cover: &cover,
    };
    let (report, artifacts) = inspect(
        &Release {
            reader_pdf: &reader,
            ..release
        },
        &legs,
    )?;
    let instructions = root.join("booklet-a4-printing-instructions.md");
    write(
        &instructions,
        &printing_instructions(
            release.language,
            Pdf::read(&reader)?.page_count(),
            Pdf::read(&booklet)?.page_count() / 2,
            Pdf::read(&interior)?.page_count() / 2,
            Pdf::read(&cover)?.page_count(),
        ),
    )?;
    let studio = root.join("studio").join("README.md");
    std::fs::create_dir_all(root.join("studio"))?;
    write(&studio, studio_note(release.language))?;
    let preflight = root.join("preflight.json");
    let facts = inspect_package(
        &reader,
        &booklet,
        &interior,
        &cover,
        release.cover_art,
        release.cover_art_size_points,
        release.figure_placements,
        release.language,
    )?;
    write(&preflight, &py_json(&facts))?;
    let mut files: Vec<PathBuf> = [
        reader,
        booklet,
        interior,
        cover,
        instructions,
        studio,
        preflight,
        manifest,
        report,
    ]
    .into_iter()
    .chain(artifacts)
    .collect();
    files.sort_by_key(|path| relative(path, root));
    let mut sums = String::new();
    for path in &files {
        sums.push_str(&format!("{}  {}\n", sha256(path)?, relative(path, root)));
    }
    let checksums = root.join("SHA256SUMS");
    write(&checksums, &sums)?;
    files.push(checksums);
    Ok(files)
}

fn is_spanish(language: &str) -> bool {
    language.split('-').next() == Some("es")
}

pub fn printing_instructions(
    language: &str,
    reader_page_count: usize,
    all_in_one_sheets: usize,
    interior_sheets: usize,
    cover_sheets: usize,
) -> String {
    let first_interior = 3;
    let last_interior = reader_page_count as i64 - 2;
    if is_spanish(language) {
        return format!(
            "# Impresión doméstica\n\nImprimir al 100 % en A4 horizontal, a doble cara y volteando por el borde corto. En una impresora de una sola cara, imprimir primero las páginas impares del PDF y después las pares en orden inverso. Doblar el bloque por la mitad y graparlo a caballete. Hacer primero una prueba para confirmar la orientación de alimentación de la impresora.\n\n\
Hay tres imposiciones de la misma revista. Imprimir el cuadernillo completo o bien la pareja de interior y cubierta, no ambas cosas.\n\n\
## booklet-a4.pdf \u{2014} todo en uno\n\n\
La revista entera, cubierta incluida: {all_in_one_sheets} hojas A4 en un solo papel. Es la opción para imprimir con un único gramaje y sin nada que intercalar.\n\n\
## booklet-a4-interior.pdf \u{2014} interior en papel de texto\n\n\
Las páginas {first_interior} a {last_interior} del PDF de lectura: la revista sin la cubierta y sin las páginas en blanco de su cara interior. Son {interior_sheets} hojas A4 en papel corriente de 80 a 100 g/m².\n\n\
## booklet-a4-cover.pdf \u{2014} cubierta en papel más grueso\n\n\
{cover_sheets} hoja A4, a una sola cara: la contracubierta junto a la cubierta. El PDF es esa única página \u{2014} no hay cara interior que imprimir. Usar papel más grueso \u{2014}de 160 a 250 g/m², que dobla bien\u{2014} y dejar secar la tinta antes de doblar.\n\n\
## Montaje de la impresión en dos papeles\n\n\
Doblar por separado el bloque interior y la hoja de cubierta, encajar el interior dentro de la cubierta doblada y grapar a caballete atravesando ambos por el lomo.\n"
        );
    }
    format!(
        "# Home printing\n\nPrint at 100% on A4 landscape, duplex, flipping on the short edge. On a simplex printer, print odd PDF pages first, then even PDF pages in reverse order. Fold the stack in half and saddle-staple. First run a test to confirm your printer's feed direction.\n\n\
Three impositions of the same magazine are included. Print either the all-in-one booklet or the interior-and-cover pair, not both.\n\n\
## booklet-a4.pdf \u{2014} all in one\n\n\
The whole magazine, cover included: {all_in_one_sheets} A4 sheets on one stock. This is the single-stock print, with nothing to collate.\n\n\
## booklet-a4-interior.pdf \u{2014} interior on text stock\n\n\
Reader pages {first_interior} to {last_interior}: the magazine without the cover and without the blank inside covers. {interior_sheets} A4 sheets on ordinary 80-100 gsm text stock.\n\n\
## booklet-a4-cover.pdf \u{2014} cover wrap on heavier stock\n\n\
{cover_sheets} A4 sheet, printed single-sided: the back cover beside the front cover. The PDF is that one page \u{2014} there is no inside face to print. Use heavier stock \u{2014} 160-250 gsm folds well \u{2014} and let the ink dry before folding.\n\n\
## Assembling the two-stock print\n\n\
Fold the interior stack and the cover sheet separately, nest the interior inside the folded cover, then saddle-staple through the spine of both.\n"
    )
}

pub fn studio_note(language: &str) -> &'static str {
    if is_spanish(language) {
        return "# Entrega a imprenta pendiente\n\nEl PDF de lectura tiene formato A5, pero no es PDF/X. Antes de imprimir hay que seleccionar el perfil ICC de la imprenta, añadir el sangrado requerido, convertir a PDF/X-4 y superar la verificación de preimpresión.\n";
    }
    "# Studio handoff pending\n\nThe reader PDF is A5, but it is not PDF/X. Select a printer ICC profile, add bleed where artwork requires it, convert to PDF/X-4, and pass the printer's preflight before release.\n"
}
