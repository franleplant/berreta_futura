use mag::model::doc;
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("mag sits inside the repository")
        .to_path_buf()
}

fn settable() -> BTreeSet<u32> {
    doc::settable_codepoints(&repository().join("mag/assets/fonts"))
        .expect("the vendored faces are readable")
}

#[test]
fn settable_codepoints_cover_text_but_not_unbundled_scripts() {
    let settable = settable();
    for character in ['A', 'z', '\u{e9}', '\u{2014}'] {
        assert!(settable.contains(&(character as u32)), "{character:?}");
    }
    assert!(!settable.contains(&0x5915));
}

#[test]
fn fenced_code_survives_parsing_byte_for_byte() {
    let code = "  indented\n\ttabbed  \n\n---\n# not a heading\n| a | b |\n\nlast";
    let markdown = format!("Before.\n\n```rust\n{code}\n```\n\nAfter.\n");
    let document = doc::parse_publication_document(&markdown).expect("the manuscript parses");
    let fenced: Vec<&doc::Block> = document
        .blocks
        .iter()
        .filter(|block| matches!(block, doc::Block::FencedCode { .. }))
        .collect();
    assert_eq!(fenced.len(), 1);
    let doc::Block::FencedCode { code: kept, info } = fenced[0] else {
        unreachable!()
    };
    assert_eq!(info, "rust");
    assert_eq!(kept.trim_end_matches('\n'), code);
}

#[test]
fn a_pipe_table_parses_into_rows_of_inline_cells() {
    let markdown = "Before.\n\n| Name | `code` |\n| --- | :-: |\n| **A** | 1 \\| 2 |\n| B |\n";
    let document = doc::parse_publication_document(markdown).expect("the table parses");
    assert_eq!(
        doc::block_signature(&document.blocks),
        ["body", "table[2,2,2]"]
    );
    let doc::Block::Table(rows) = &document.blocks[1] else {
        panic!("the second block is a table")
    };
    let cells: Vec<String> = rows
        .iter()
        .flatten()
        .map(|cell| doc::inline_text(cell))
        .collect();
    assert_eq!(cells, ["Name", "code", "A", "1 | 2", "B", ""]);
}
