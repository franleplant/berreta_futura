use crate::model::doc::settable_codepoints;
use crate::model::manifest::Edition;
use crate::model::records::load_records;
use crate::package::archive::archive_tree;
use crate::package::preflight::FigurePlacement;
use crate::package::release::{package_release, Release};
use crate::web::edition::{write_web_edition, WebOptions};
use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const CONTRACT_VERSION: &str = "magazine-renderer/1";
const STUDIO_BLOCKER: &str = "A named printer profile and preflight are required.";

pub struct Publish<'a> {
    pub request: &'a Value,
    pub edition: &'a Edition,
    pub layout: Value,
    pub interior: Vec<u8>,
    pub staged: &'a Path,
    pub assets: &'a Path,
    pub render_dir: &'a Path,
    pub out_dir: &'a Path,
}

fn placements(layout: &Value, staged: &Path) -> Result<Vec<FigurePlacement>> {
    let rows = layout["figures"].as_array().map_or(&[][..], Vec::as_slice);
    rows.iter()
        .map(|row| {
            let text = |key: &str| {
                row[key]
                    .as_str()
                    .map(str::to_string)
                    .with_context(|| format!("layout figure {key}"))
            };
            let pixels = row["pixel_dimensions"].as_array();
            Ok(FigurePlacement {
                figure_id: text("id")?,
                article_id: text("article_id")?,
                page: row["page"].as_i64().context("layout figure page")?,
                path: staged.join(text("path")?),
                pixel_dimensions: pixels
                    .and_then(|p| Some((p.first()?.as_u64()? as u32, p.get(1)?.as_u64()? as u32))),
                box_points: row["box_points"]
                    .as_array()
                    .into_iter()
                    .flatten()
                    .filter_map(Value::as_f64)
                    .collect(),
                effective_ppi: row["effective_ppi"].as_f64(),
                caption: text("caption")?,
                credit: text("credit")?,
            })
        })
        .collect()
}

fn pages(layout: &Value, key: &str) -> Result<BTreeMap<String, usize>> {
    serde_json::from_value(layout[key].clone())
        .with_context(|| format!("layout {key} is not a page map"))
}

fn kind(path: &Path) -> (&'static str, &'static str) {
    let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
    match path.extension().and_then(|e| e.to_str()).unwrap_or("") {
        "pdf" if name == "reader.pdf" => ("reader_pdf", "application/pdf"),
        "pdf" if name == "booklet.pdf" || name == "booklet-a4.pdf" => {
            ("booklet_pdf", "application/pdf")
        }
        "pdf" => ("render_pdf", "application/pdf"),
        "png" => ("render_review_image", "image/png"),
        "json" if name == "preflight.json" => ("printer_preflight", "application/json"),
        "json" if name == "render-critic.json" => ("render_critic_report", "application/json"),
        "json" => ("render_report", "application/json"),
        "md" => ("render_instructions", "text/markdown"),
        "zip" if name == "package.zip" => ("package_artifact", "application/zip"),
        "zip" => ("web_output", "application/zip"),
        _ => ("render_file", "text/plain"),
    }
}

fn file_row(path: &Path, root: &Path) -> Value {
    let (kind, media_type) = kind(path);
    let relative = path
        .strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/");
    json!({"path": relative, "mediaType": media_type, "kind": kind})
}

fn manifest(p: &Publish) -> Result<Value> {
    let ids: Vec<&str> = p.request["inputs"]
        .as_array()
        .context("the render request has no inputs array")?
        .iter()
        .filter_map(|row| row["artifactId"].as_str())
        .collect();
    Ok(json!({
        "schema_version": 1,
        "renderer_contract_version": CONTRACT_VERSION,
        "publication": {
            "name": p.request["publicationName"],
            "language": p.edition.language,
            "locale": p.edition.locale,
            "available_languages": p.request["languages"],
        },
        "edition": serde_json::to_value(&p.edition.raw)?,
        "inputs": {"artifact_ids": ids},
        "layout": p.layout,
        "studio_release_ready": false,
        "studio_blocker": STUDIO_BLOCKER,
    }))
}

pub fn publish(p: Publish) -> Result<(Vec<Value>, String)> {
    let work = p.render_dir.join("typst");
    let (front, back) = super::cover::faces(p.staged, p.assets, p.edition, &work)?;
    let reader = work.join("reader.pdf");
    std::fs::write(work.join("interior.pdf"), &p.interior)?;
    std::fs::write(
        &reader,
        super::cover::replace_outer_pages(&p.interior, &front, &back)?,
    )?;
    let figures = placements(&p.layout, &p.staged.canonicalize()?)?;
    let cover_art = p
        .edition
        .cover_art
        .as_deref()
        .map(Path::canonicalize)
        .transpose()?;
    let (toc, article_pages) = (pages(&p.layout, "toc")?, pages(&p.layout, "article_pages")?);
    let fonts = crate::parity::text_font_map()?;
    let written = package_release(Release {
        reader_pdf: &reader,
        destination: p.out_dir,
        manifest: manifest(&p)?,
        cover_art: cover_art.as_deref(),
        cover_art_size_points: None,
        figure_placements: &figures,
        language: &p.edition.language,
        toc: &toc,
        article_pages: &article_pages,
        editorial_pages: p.layout["editorial_pages"].as_i64(),
        edition_id: &p.edition.id,
        recorded_review: None,
        fonts: &fonts,
    })?;
    let urls = load_records(&p.staged.join("library").join("sources"))?
        .into_iter()
        .filter(|record| !record.url.is_empty())
        .map(|record| (record.id, record.url))
        .collect();
    let settable = settable_codepoints(&p.assets.join("fonts"))?;
    let options = WebOptions {
        source_urls: urls,
        ..WebOptions::default()
    };
    write_web_edition(
        p.edition,
        &settable,
        p.assets,
        &p.out_dir.join("web"),
        &options,
    )?;
    let web = archive_tree(&p.out_dir.join("web"), &p.out_dir.join("web-output.zip"))?;
    let package = archive_tree(p.out_dir, &p.out_dir.join("package.zip"))?;
    let report: Value = serde_json::from_str(&std::fs::read_to_string(
        p.out_dir.join("render-critic.json"),
    )?)?;
    let critic = report["result"]
        .as_str()
        .context("render-critic.json has no result")?
        .to_string();
    let files: Vec<PathBuf> = written.into_iter().chain([web, package]).collect();
    Ok((
        files
            .iter()
            .map(|path| file_row(path, p.render_dir))
            .collect(),
        critic,
    ))
}
