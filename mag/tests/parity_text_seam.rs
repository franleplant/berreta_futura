#[path = "../src/parity/display.rs"]
#[allow(dead_code)]
mod display;
#[path = "../src/parity/exact.rs"]
#[allow(dead_code)]
mod exact;
#[path = "../src/parity/streams.rs"]
#[allow(dead_code)]
mod streams;

use lopdf::{dictionary, Document, Object, Stream};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const A5: [f64; 2] = [419.528, 595.276];

fn widths() -> Vec<Object> {
    (32..=126).map(|_| Object::Real(500.0)).collect()
}

fn build(dir: &Path, name: &str, text: &str, mode: i64, named_dest: bool) -> PathBuf {
    let mut doc = Document::with_version("1.7");
    let pages_id = doc.new_object_id();
    let font = doc.add_object(dictionary! {
        "Type" => "Font",
        "Subtype" => "Type1",
        "BaseFont" => "Helvetica",
        "Encoding" => "WinAnsiEncoding",
        "FirstChar" => 32,
        "Widths" => Object::Array(widths()),
    });
    let body = format!("BT /F1 12 Tf {mode} Tr 50 700 Td ({text}) Tj ET\n");
    let content = doc.add_object(Stream::new(dictionary! {}, body.into_bytes()));
    let mut page = dictionary! {
        "Type" => "Page",
        "Parent" => pages_id,
        "Contents" => content,
        "MediaBox" => vec![0.into(), 0.into(), A5[0].into(), A5[1].into()],
        "Resources" => dictionary! { "Font" => dictionary! { "F1" => font } },
    };
    if named_dest {
        let annot = doc.add_object(dictionary! {
            "Type" => "Annot",
            "Subtype" => "Link",
            "Rect" => vec![0.into(), 0.into(), 10.into(), 10.into()],
            "A" => dictionary! { "S" => "GoTo", "D" => Object::string_literal("nowhere") },
        });
        page.set("Annots", vec![annot.into()]);
    }
    let page_id = doc.add_object(page);
    doc.objects.insert(
        pages_id,
        Object::Dictionary(dictionary! {
            "Type" => "Pages",
            "Kids" => vec![page_id.into()],
            "Count" => 1,
        }),
    );
    let catalog = doc.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
    doc.trailer.set("Root", catalog);
    let path = dir.join(name);
    doc.save(&path).unwrap();
    path
}

fn elements(pdf: &Path) -> Vec<streams::Element> {
    display::trace_elements(pdf, 1, 1, &BTreeMap::new())
        .unwrap()
        .remove(0)
}

fn shown(pdf: &Path) -> Vec<(String, i64)> {
    elements(pdf)
        .iter()
        .filter_map(|e| match e {
            streams::Element::Text { s, tr, .. } => Some((s.clone(), *tr)),
            _ => None,
        })
        .collect()
}

fn tmp(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("wp02h-{name}"));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

#[test]
fn render_mode_is_recorded_and_distinguishes_invisible_text() {
    let dir = tmp("mode");
    let visible = build(&dir, "visible.pdf", "Hello", 0, false);
    let invisible = build(&dir, "invisible.pdf", "Hello", 3, false);
    assert_eq!(shown(&visible), vec![("Hello".to_string(), 0)]);
    assert_eq!(shown(&invisible), vec![("Hello".to_string(), 3)]);
    assert_ne!(
        shown(&visible),
        shown(&invisible),
        "same string at the same place must differ when one is invisible"
    );
}

#[test]
fn differing_invisible_text_differs() {
    let dir = tmp("content");
    let a = build(&dir, "a.pdf", "Hello", 3, false);
    let b = build(&dir, "b.pdf", "World", 3, false);
    assert_ne!(shown(&a), shown(&b));
}

#[test]
fn standard_14_decodes_without_tounicode() {
    let dir = tmp("std14");
    let pdf = build(&dir, "std14.pdf", "AZaz09", 0, false);
    assert_eq!(shown(&pdf), vec![("AZaz09".to_string(), 0)]);
}

#[test]
fn text_seam_reads_a_document_whose_navigation_is_broken() {
    let dir = tmp("seam");
    let pdf = build(&dir, "broken.pdf", "Hello", 0, true);
    let err = match display::extract(&pdf, 1, 1, &BTreeMap::new()) {
        Err(e) => format!("{e:#}"),
        Ok(_) => panic!("named destination without a Names tree must fail"),
    };
    assert!(err.contains("Names"), "got {err}");
    assert_eq!(shown(&pdf), vec![("Hello".to_string(), 0)]);
}
