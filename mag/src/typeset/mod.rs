pub(crate) mod content;
pub(crate) mod estimate;
pub(crate) mod layout;
pub(crate) mod media;
pub(crate) mod template;
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
) -> Result<Value> {
    let request: Value =
        serde_json::from_str(request_json).context("parsing the render request as JSON")?;
    let language = field(&request, "primaryLanguage")?.to_string();
    let out_dir = render_dir.join(&language);
    fs::create_dir_all(&out_dir).with_context(|| format!("creating {}", out_dir.display()))?;
    let request_path = render_dir.join("request.json");
    fs::write(
        &request_path,
        serde_json::to_string_pretty(&request)? + "\n",
    )
    .with_context(|| format!("writing {}", request_path.display()))?;
    println!("request: {}", request_path.display());
    println!("out dir: {}", out_dir.display());

    let staged = render_dir.join("staged");
    let rows = stage(&request, &staged)?;
    println!("staged {rows} inputs into {}", staged.display());

    let fonts = repo_root.join(template::FONT_DIR);
    let tree = content::pipeline(&content::Inputs {
        root: &staged,
        edition_id: field(&request, "editionId")?,
        publication_name: field(&request, "publicationName")?,
        fonts: &fonts,
        allow_missing_art: false,
        allow_unanchored_figures: false,
    })?;
    let typ_dir = render_dir.join("typst");
    for file in &tree.files {
        let path = typ_dir.join(&file.path);
        let parent = path.parent().context("a tree file has no parent")?;
        fs::create_dir_all(parent).with_context(|| format!("creating {}", parent.display()))?;
        fs::write(&path, &file.source).with_context(|| format!("writing {}", path.display()))?;
    }
    fs::write(typ_dir.join("template.typ"), template::TEMPLATE_TYP)?;
    fs::write(typ_dir.join("root.typ"), template::ROOT_TYP)?;
    let projection = content::project(&tree)?;
    println!(
        "typst source tree: {} files, {} characters of reader text",
        tree.files.len(),
        projection.text.chars().count()
    );
    let document = template::document(&template::world(&tree, &fonts)?)?;
    layout::report(
        &layout::Request {
            operation: field(&request, "operation")?,
            article: request.get("articleId").and_then(Value::as_str),
            edition_id: field(&request, "editionId")?,
            publication_name: field(&request, "publicationName")?,
            language: &language,
            staged: &staged,
            out_dir: &out_dir,
        },
        &document,
        &tree,
    )
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
