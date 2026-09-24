pub(crate) mod content;
pub(crate) mod cover;
pub(crate) mod estimate;
pub(crate) mod hyphen;
pub(crate) mod layout;
pub(crate) mod media;
pub(crate) mod release;
pub(crate) mod runt;
pub(crate) mod template;
pub(crate) mod text_shim;
pub(crate) mod world;

use anyhow::{Context, Result};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

fn field<'a>(request: &'a Value, key: &str) -> Result<&'a str> {
    request
        .get(key)
        .and_then(Value::as_str)
        .with_context(|| format!("the render request has no string field '{key}'"))
}

fn stage(request: &Value, into: &Path) -> Result<usize> {
    let rows = request
        .get("inputs")
        .and_then(Value::as_array)
        .context("the render request has no inputs array")?;
    for row in rows {
        let source = PathBuf::from(field(row, "sourcePath")?);
        let target = into.join(field(row, "targetPath")?);
        let parent = target.parent().context("a staged target has no parent")?;
        fs::create_dir_all(parent).with_context(|| format!("creating {}", parent.display()))?;
        fs::copy(&source, &target)
            .with_context(|| format!("staging {} into {}", source.display(), target.display()))?;
    }
    Ok(rows.len())
}

pub(crate) fn run_request(
    repo_root: &Path,
    render_dir: &Path,
    request_json: &str,
    parity: bool,
) -> Result<Value> {
    let request: Value =
        serde_json::from_str(request_json).context("parsing the render request as JSON")?;
    let primary = field(&request, "primaryLanguage")?;
    let languages: Vec<&str> = request["languages"]
        .as_array()
        .context("the render request has no languages array")?
        .iter()
        .filter_map(Value::as_str)
        .collect();
    anyhow::ensure!(
        languages.contains(&primary),
        "languages must include primaryLanguage"
    );
    fs::create_dir_all(render_dir).with_context(|| format!("creating {}", render_dir.display()))?;
    let request_path = render_dir.join("request.json");
    fs::write(
        &request_path,
        serde_json::to_string_pretty(&request)? + "\n",
    )
    .with_context(|| format!("writing {}", request_path.display()))?;
    println!("request: {}", request_path.display());
    let staged = render_dir.join("staged");
    let rows = stage(&request, &staged)?;
    println!("staged {rows} inputs into {}", staged.display());
    let base = layout::edition(
        &staged,
        field(&request, "editionId")?,
        field(&request, "publicationName")?,
    )?;
    let hyphenation = match parity {
        true => hyphen::Hyphenation::PARITY,
        false => hyphen::Hyphenation::from_settings(|key| {
            crate::render::toml_value(repo_root, "render", key)
        })
        .map_err(anyhow::Error::msg)?,
    };
    let mut result = serde_json::json!({"layouts": [], "files": [], "warnings": []});
    for language in languages {
        let edition = if language == primary {
            base.clone()
        } else {
            crate::model::manifest::load_translation(&staged, &base, language)?
        };
        let work = match language == primary {
            true => render_dir.join("typst"),
            false => render_dir.join(format!("typst-{language}")),
        };
        let one = render_language(
            (repo_root, render_dir),
            &request,
            &staged,
            &edition,
            &work,
            hyphenation,
        )?;
        for key in ["layouts", "files", "warnings"] {
            let rows = one[key].as_array().cloned().unwrap_or_default();
            result[key].as_array_mut().expect("seeded").extend(rows);
        }
        result["operation"] = one["operation"].clone();
    }
    Ok(result)
}

fn render_language(
    (repo_root, render_dir): (&Path, &Path),
    request: &Value,
    staged: &Path,
    edition: &crate::model::manifest::Edition,
    work: &Path,
    hyphenation: hyphen::Hyphenation,
) -> Result<Value> {
    let out_dir = render_dir.join(&edition.language);
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    println!("out dir: {}", out_dir.display());
    let fonts = repo_root.join(template::FONT_DIR);
    let tree = content::compose(edition, &fonts, hyphenation)?;
    let (tree, document) = template::paginate(tree, &fonts, hyphenation)?;
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
            operation: field(request, "operation")?,
            article: request.get("articleId").and_then(Value::as_str),
            edition,
            staged,
            out_dir: &out_dir,
            render_dir,
            work,
            assets: &repo_root.join("src/magazine/assets"),
            raw: request,
        },
        &document,
        &tree,
    )?;
    let ladders = runt::ladder_warnings(&document, &edition.id);
    if let Some(warnings) = one["warnings"].as_array_mut() {
        warnings.extend(ladders.into_iter().map(Value::from));
    }
    Ok(one)
}

#[cfg(test)]
mod the_content_pipeline_is_reachable_from_outside_its_module {
    use crate::typeset::content::{project, Inputs, Tree};
    use std::path::Path;

    #[test]
    fn a_sibling_module_imports_the_pipeline_the_ordinary_way() {
        let _: fn(&Inputs) -> crate::model::shared::Result<Tree> = content_pipeline();
        let empty = Tree { files: Vec::new() };
        let Err(error) = project(&empty) else {
            panic!("a tree with no main.typ must refuse rather than project");
        };
        assert!(error.to_string().contains("main.typ"));
        assert!(Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").is_dir());
    }

    fn content_pipeline() -> fn(&Inputs) -> crate::model::shared::Result<Tree> {
        crate::typeset::content::pipeline
    }
}
