pub mod art;
pub(crate) mod content;
pub(crate) mod cover;
pub(crate) mod flow;
pub(crate) mod geometry;
pub(crate) mod hyphen;
pub(crate) mod layout;
pub(crate) mod legible;
pub(crate) mod measure;
pub(crate) mod media;
pub(crate) mod release;
pub(crate) mod runs;
pub(crate) mod runt;
pub(crate) mod template;
pub(crate) mod tone;
pub(crate) mod world;

use crate::render::Request;
use anyhow::{Context, Result};
use layout::Outcome;
use std::fs;
use std::path::{Component, Path};

pub(crate) fn contained(path: &Path) -> bool {
    path.components()
        .all(|c| matches!(c, Component::Normal(_) | Component::CurDir))
}

fn stage(request: &Request, into: &Path) -> Result<usize> {
    for row in &request.inputs {
        anyhow::ensure!(
            contained(Path::new(&row.target_path)),
            "staged target {:?} must be relative with no '..' components",
            row.target_path
        );
    }
    for row in &request.inputs {
        let target = into.join(&row.target_path);
        let parent = target.parent().context("a staged target has no parent")?;
        fs::create_dir_all(parent).with_context(|| format!("creating {}", parent.display()))?;
        fs::copy(&row.source_path, &target)
            .with_context(|| format!("staging {} into {}", row.source_path, target.display()))?;
    }
    Ok(request.inputs.len())
}

pub(crate) fn run_request(
    repo_root: &Path,
    render_dir: &Path,
    request: &Request,
    legibility: bool,
) -> Result<Outcome> {
    let primary = request.primary_language.as_str();
    anyhow::ensure!(
        request.languages.iter().any(|l| l == primary),
        "languages must include primaryLanguage"
    );
    fs::create_dir_all(render_dir).with_context(|| format!("creating {}", render_dir.display()))?;
    let request_path = render_dir.join("request.json");
    fs::write(&request_path, serde_json::to_string_pretty(request)? + "\n")
        .with_context(|| format!("writing {}", request_path.display()))?;
    println!("request: {}", request_path.display());
    let staged = render_dir.join("staged");
    let rows = stage(request, &staged)?;
    println!("staged {rows} inputs into {}", staged.display());
    let base = layout::edition(&staged, &request.edition_id, &request.publication_name)?;
    let hyphenation =
        hyphen::Hyphenation::from_settings(crate::render::magazine_toml(repo_root)?.get("render"))
            .map_err(anyhow::Error::msg)?;
    if legibility {
        legible::require_tesseract()?;
    }
    let mut result = Outcome {
        files: vec![],
        layouts: vec![],
        operation: request.operation,
        warnings: vec![],
    };
    for language in &request.languages {
        let language = language.as_str();
        let printed = tone::print_figures(
            match language == primary {
                true => base.clone(),
                false => crate::model::manifest::load_translation(&staged, &base, language)?,
            },
            &staged,
        )?;
        let enlarged = match legibility {
            true => legible::enlarge(printed, repo_root)?,
            false => printed,
        };
        let edition = art::print_art(enlarged, &staged)?;
        let work = match language == primary {
            true => render_dir.join("typst"),
            false => render_dir.join(format!("typst-{language}")),
        };
        let one = render_language(
            (repo_root, render_dir),
            request,
            &staged,
            &edition,
            &work,
            hyphenation,
        )?;
        result.files.extend(one.files);
        result.layouts.extend(one.layouts);
        result.warnings.extend(one.warnings);
    }
    Ok(result)
}

fn render_language(
    (repo_root, render_dir): (&Path, &Path),
    request: &Request,
    staged: &Path,
    edition: &crate::model::manifest::Edition,
    work: &Path,
    hyphenation: hyphen::Hyphenation,
) -> Result<Outcome> {
    let out_dir = render_dir.join(&edition.language);
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    println!("out dir: {}", out_dir.display());
    let tree = template::composed(edition, hyphenation)?;
    let (tree, document) = template::paginate(tree, hyphenation)?;
    for file in &tree.files {
        let path = work.join(&file.path);
        let parent = path.parent().context("a tree file has no parent")?;
        fs::create_dir_all(parent).with_context(|| format!("creating {}", parent.display()))?;
        fs::write(&path, &file.source).with_context(|| format!("writing {}", path.display()))?;
    }
    fs::write(work.join("template.typ"), template::TEMPLATE_TYP)?;
    fs::write(work.join("root.typ"), template::ROOT_TYP)?;
    let projection = content::project(&tree)?;
    println!(
        "typst source tree ({}, hyphenation {hyphenation:?}): {} files, {} characters of reader text",
        edition.language,
        tree.files.len(),
        projection.text.chars().count()
    );
    let mut one = layout::report(
        &layout::Request {
            article: request.article_id.as_deref(),
            edition,
            staged,
            out_dir: &out_dir,
            render_dir,
            work,
            assets: &repo_root.join("mag/assets"),
            raw: request,
        },
        &document,
        &tree,
    )?;
    let ladders = runt::ladder_warnings(&document, &edition.id);
    one.warnings.extend(ladders);
    Ok(one)
}

#[cfg(test)]
mod staging_tests {
    use super::*;
    use crate::render::InputRow;

    fn request(source: &Path, target: &str) -> Request {
        Request {
            inputs: vec![InputRow {
                source_path: source.to_string_lossy().to_string(),
                target_path: target.to_string(),
                ..InputRow::default()
            }],
            ..Request::default()
        }
    }

    #[test]
    fn a_target_that_climbs_out_or_is_absolute_is_refused_before_any_copy() {
        let into = std::env::temp_dir().join(format!("mag-stage-{}", std::process::id()));
        let source = std::env::temp_dir().join(format!("mag-stage-src-{}", std::process::id()));
        std::fs::write(&source, "x").expect("writes the source");
        for bad in ["../escape.txt", "a/../../escape.txt", "/tmp/escape.txt"] {
            let error = stage(&request(&source, bad), &into).expect_err("refused");
            assert!(error.to_string().contains("no '..'"), "{bad}: {error}");
        }
        assert!(!into.exists());
        assert_eq!(
            stage(&request(&source, "a/b.txt"), &into).expect("staged"),
            1
        );
        assert!(into.join("a/b.txt").exists());
        std::fs::remove_dir_all(&into).expect("cleanup");
        std::fs::remove_file(&source).expect("cleanup");
    }
}
