use super::layout::{FileRow, Layout};
use crate::critic::text::Run;
use crate::model::manifest::Edition;
use crate::package::archive::archive_tree;
use crate::package::preflight::FigurePlacement;
use crate::package::release::{package_release, Release};
use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

const CONTRACT_VERSION: &str = "magazine-renderer/1";
const STUDIO_BLOCKER: &str = "A named printer profile and preflight are required.";

pub struct Publish<'a> {
    pub request: &'a crate::render::Request,
    pub edition: &'a Edition,
    pub layout: Layout,
    pub interior: Vec<u8>,
    pub runs: Vec<Vec<Run>>,
    pub staged: &'a Path,
    pub assets: &'a Path,
    pub render_dir: &'a Path,
    pub work: &'a Path,
    pub out_dir: &'a Path,
}

fn placements(layout: &Layout, staged: &Path) -> Vec<FigurePlacement> {
    layout
        .figures
        .iter()
        .map(|figure| FigurePlacement {
            figure_id: figure.id.clone(),
            article_id: figure.article_id.clone(),
            page: figure.page as i64,
            path: staged.join(&figure.path),
            pixel_dimensions: Some(figure.pixel_dimensions),
            box_points: figure.box_points.to_vec(),
            effective_ppi: Some(figure.effective_ppi),
            caption: figure.caption.clone(),
            credit: figure.credit.clone(),
        })
        .collect()
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
        _ => ("render_file", "text/plain"),
    }
}

fn file_row(path: &Path, root: &Path) -> FileRow {
    let (kind, media_type) = kind(path);
    let relative = path
        .strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/");
    FileRow {
        kind: kind.to_string(),
        media_type: Some(media_type.to_string()),
        path: relative,
    }
}

fn edition_summary(edition: &Edition) -> Result<Value> {
    let articles: Vec<Value> = edition
        .articles
        .iter()
        .map(|article| {
            json!({
                "id": article.id,
                "title": article.title,
                "short_title": article.short_title,
                "author": article.author,
                "content_mode": article.content_mode,
                "source_ids": article.source_ids,
            })
        })
        .collect();
    Ok(json!({
        "id": edition.id,
        "issue_number": edition.issue_number,
        "title": edition.title,
        "subtitle": edition.subtitle,
        "publication_date": edition.publication_date,
        "cover": serde_json::to_value(&edition.cover)?,
        "format": serde_json::to_value(&edition.format)?,
        "tail_art_fit": edition.tail_art_fit,
        "articles": articles,
    }))
}

fn manifest(p: &Publish) -> Result<Value> {
    let ids: Vec<&str> = p
        .request
        .inputs
        .iter()
        .map(|row| row.artifact_id.as_str())
        .collect();
    Ok(json!({
        "schema_version": 1,
        "renderer_contract_version": CONTRACT_VERSION,
        "publication": {
            "name": p.request.publication_name,
            "language": p.edition.language,
            "locale": p.edition.locale,
            "available_languages": p.request.languages,
        },
        "edition": edition_summary(p.edition)?,
        "inputs": {"artifact_ids": ids},
        "layout": p.layout,
        "studio_release_ready": false,
        "studio_blocker": STUDIO_BLOCKER,
    }))
}

pub fn publish(p: &Publish) -> Result<(Vec<FileRow>, String)> {
    let work = p.work;
    let faces = super::cover::faces(p.staged, p.assets, p.edition, work)?;
    std::fs::create_dir_all(p.out_dir)?;
    let cover = p.out_dir.join("cover.png");
    std::fs::write(&cover, &faces.picture)?;
    let reader = work.join("reader.pdf");
    std::fs::write(work.join("interior.pdf"), &p.interior)?;
    std::fs::write(
        &reader,
        super::cover::replace_outer_pages(&p.interior, &faces.front, &faces.back)?,
    )?;
    let figures = placements(&p.layout, &p.staged.canonicalize()?);
    let cover_art = p
        .edition
        .cover_art
        .as_deref()
        .map(Path::canonicalize)
        .transpose()?;
    let mut runs = p.runs.clone();
    let last = runs.len() - 1;
    runs[0] = faces.front_runs;
    runs[last] = faces.back_runs;
    let written = package_release(Release {
        reader_pdf: &reader,
        destination: p.out_dir,
        manifest: manifest(p)?,
        cover_art: cover_art.as_deref(),
        cover_art_size_points: None,
        figure_placements: &figures,
        language: &p.edition.language,
        toc: &p.layout.toc,
        article_pages: &p.layout.article_pages,
        editorial_pages: p.layout.editorial_pages.map(|n| n as i64),
        edition_id: &p.edition.id,
        recorded_review: None,
        runs: &runs,
    })?;
    let package = archive_tree(p.out_dir, &p.out_dir.join("package.zip"))?;
    let report: Value = serde_json::from_str(&std::fs::read_to_string(
        p.out_dir.join("render-critic.json"),
    )?)?;
    let critic = report["result"]
        .as_str()
        .context("render-critic.json has no result")?
        .to_string();
    let files: Vec<PathBuf> = written.into_iter().chain([package, cover]).collect();
    Ok((
        files
            .iter()
            .map(|path| file_row(path, p.render_dir))
            .collect(),
        critic,
    ))
}
