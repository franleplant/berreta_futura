use lopdf::{Document, Object};
use mag::impose;
use std::path::PathBuf;

fn colliding_reader(junk: &str, tag: &str) -> PathBuf {
    use lopdf::{dictionary, Stream};
    let mut doc = Document::with_version("1.7");
    let pages_id = doc.new_object_id();
    let kids: Vec<Object> = (1..=4)
        .map(|page| {
            let font = doc.add_object(dictionary! {
                "Type" => "Font", "Subtype" => "Type1", "BaseFont" => format!("Face{page}"),
            });
            let content = format!(
                "BT /F1 12 Tf 72 500 Td (page {page}) Tj ET {junk} 0 0 0 rg 10 10 50 50 re f"
            );
            let content = doc.add_object(Stream::new(dictionary! {}, content.into_bytes()));
            let media: Vec<Object> = vec![0.into(), 0.into(), 420.into(), 595.into()];
            doc.add_object(dictionary! {
                "Type" => "Page", "Parent" => pages_id, "Contents" => content, "MediaBox" => media,
                "Resources" => dictionary! {"Font" => dictionary! {"F1" => font}},
            })
            .into()
        })
        .collect();
    doc.objects.insert(
        pages_id,
        Object::Dictionary(dictionary! {"Type" => "Pages", "Kids" => kids, "Count" => 4}),
    );
    let catalog = doc.add_object(dictionary! {"Type" => "Catalog", "Pages" => pages_id});
    doc.trailer.set("Root", catalog);
    let path = std::env::temp_dir().join(format!("wp51h-{tag}-{}.pdf", std::process::id()));
    doc.save(&path).expect("the reader saves");
    path
}

#[test]
fn a_stray_token_in_a_renamed_page_fails_loud_instead_of_truncating() {
    let clean = colliding_reader("", "clean");
    let produced = clean.with_extension("imposed.pdf");
    impose::impose_a5_on_a4(&clean, &produced, "all").expect("the clean reader imposes");
    let imposed = Document::load(&produced).expect("the sheet loads");
    let sheet = *imposed.get_pages().values().next().expect("one sheet");
    let content = String::from_utf8_lossy(&imposed.get_page_content(sheet)).into_owned();
    assert!(
        content.contains("/F1-0"),
        "the second page was renamed: {content}"
    );
    assert_eq!(content.matches(" re").count(), 4, "{content}");
    for junk in ["@", "]"] {
        let dirty = colliding_reader(junk, "dirty");
        let error = impose::impose_a5_on_a4(&dirty, &produced, "all")
            .expect_err("a stray token must not truncate a page");
        assert!(
            format!("{error:#}").contains("holds a token lopdf cannot parse"),
            "{error:#}"
        );
    }
}

fn object_stream_reader(media: &str) -> Vec<u8> {
    let objects = [
        "<</Type/Catalog/Pages 2 0 R>>".to_string(),
        "<</Type/Pages/Kids[3 0 R]/Count 1>>".to_string(),
        format!("<</Type/Page/Parent 2 0 R/MediaBox [{media}]/Contents 4 0 R/Resources<<>>>>"),
    ];
    let (mut head, mut body) = (String::new(), String::new());
    for (i, o) in objects.iter().enumerate() {
        head.push_str(&format!("{} {} ", i + 1, body.len()));
        body.push_str(&format!("{o}\n"));
    }
    let data = format!("{head}\n{body}");
    let mut out = b"%PDF-1.7\n".to_vec();
    let content = out.len();
    out.extend(b"4 0 obj\n<</Length 19>>\nstream\n0 0 0 rg 0 0 9 9 re f\nendstream\nendobj\n");
    let container = out.len();
    out.extend(
        format!(
            "5 0 obj\n<</Type/ObjStm/N 3/First {}/Length {}>>\nstream\n{data}\nendstream\nendobj\n",
            head.len() + 1,
            data.len()
        )
        .bytes(),
    );
    let xref = out.len();
    let mut rows = vec![[0u8, 0, 0, 0, 0, 255, 255]];
    rows.extend((0..3u8).map(|i| [2, 0, 0, 0, 5, 0, i]));
    for at in [content, container, xref] {
        let b = u32::try_from(at).expect("small").to_be_bytes();
        rows.push([1, b[0], b[1], b[2], b[3], 0, 0]);
    }
    let rows = rows.concat();
    out.extend(
        format!(
            "6 0 obj\n<</Type/XRef/Size 7/W[1 4 2]/Root 1 0 R/Length {}>>\nstream\n",
            rows.len()
        )
        .bytes(),
    );
    out.extend(rows);
    out.extend(format!("\nendstream\nendobj\nstartxref\n{xref}\n%%EOF\n").bytes());
    out
}

#[test]
fn a_reader_whose_pages_live_in_an_object_stream_imposes() {
    let reader = std::env::temp_dir().join(format!("wp02w-objstm-{}.pdf", std::process::id()));
    std::fs::write(&reader, object_stream_reader("0 0 419.527559 595.275591")).expect("written");
    assert!(Document::load(&reader)
        .expect("the reader loads")
        .reference_table
        .get(3)
        .is_some_and(|e| matches!(e, lopdf::xref::XrefEntry::Compressed { container: 5, .. })));
    let produced = reader.with_extension("imposed.pdf");
    impose::impose_a5_on_a4(&reader, &produced, "all").expect("an object-stream reader imposes");
    let imposed = Document::load(&produced).expect("the sheet loads");
    let first = *imposed.get_pages().values().next().expect("a sheet");
    let content = String::from_utf8_lossy(&imposed.get_page_content(first)).into_owned();
    assert!(
        content.contains("q\n1 0 0 1 422.36224 0 cm"),
        "the media box reads at its shortest f32 form, 595.2756: {content}"
    );
}

#[test]
fn a_booklet_of_eight_pages_pairs_outside_with_inside_sheets() {
    assert_eq!(
        impose::booklet_spreads(8),
        vec![(8, 1), (2, 7), (6, 3), (4, 5)]
    );
}
