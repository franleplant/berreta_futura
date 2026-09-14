use anyhow::{bail, Result};

pub(crate) fn render_edition() -> Result<i32> {
    bail!(
        "--engine typst is not implemented: the Typst reader template lands in WP-2.2a \
         (meta/plans/typst-parity-and-rust-migration.md). Use --engine weasyprint."
    )
}
