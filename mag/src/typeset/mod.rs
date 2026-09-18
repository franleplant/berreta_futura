#[allow(dead_code)]
pub(crate) mod content;

use anyhow::{bail, Result};

pub(crate) fn render_edition() -> Result<i32> {
    bail!(
        "--engine typst is not implemented: the Typst reader template lands in WP-2.2a \
         (meta/plans/typst-parity-and-rust-migration.md). Use --engine weasyprint."
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
