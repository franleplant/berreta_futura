#[path = "pdf_fixtures/checks.rs"]
#[allow(dead_code)]
mod checks;
#[path = "../src/pdf_text.rs"]
#[allow(dead_code)]
mod pdf_text;

use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/pdf_fixtures")
}

fn fixture_dirs() -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = std::fs::read_dir(root())
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.join("source.pdf").exists())
        .collect();
    dirs.sort();
    dirs
}

#[test]
fn every_fidelity_check_passes_on_every_fixture() {
    let mut failures = Vec::new();
    for dir in fixture_dirs() {
        let f = checks::load(&dir);
        let text = pdf_text::transcribe(&dir.join("source.pdf")).unwrap();
        if let Ok(out) = std::env::var("MAG_PDF_TEXT_OUT") {
            std::fs::write(Path::new(&out).join(format!("{}.txt", f.name)), &text).unwrap();
        }
        let v = checks::verdicts(&f, &text);
        let bad: Vec<&str> = v.iter().filter(|x| !x.1).map(|x| x.0.as_str()).collect();
        println!(
            "{}\t{}/{}\t{}",
            f.name,
            v.len() - bad.len(),
            v.len(),
            bad.join(" ")
        );
        failures.extend(bad.iter().map(|b| format!("{}:{b}", f.name)));
    }
    assert!(failures.is_empty(), "failing checks: {failures:?}");
}

#[test]
fn three_runs_are_byte_identical() {
    for dir in fixture_dirs() {
        let runs: Vec<String> = (0..3)
            .map(|_| pdf_text::transcribe(&dir.join("source.pdf")).unwrap())
            .collect();
        assert!(runs.windows(2).all(|w| w[0] == w[1]), "{}", dir.display());
    }
}

use lopdf::{dictionary, Document, Object, Stream};

fn helvetica() -> lopdf::Dictionary {
    dictionary! {
        "Type" => "Font", "Subtype" => "Type1", "BaseFont" => "Helvetica",
        "Encoding" => "WinAnsiEncoding", "FirstChar" => 32, "LastChar" => 126,
        "Widths" => (32..=126).map(|c| Object::Integer(if c == 32 { 278 } else { 556 })).collect::<Vec<_>>(),
    }
}

fn indirect(doc: &mut Document, dict: &mut lopdf::Dictionary) {
    if let Ok(Object::Stream(s)) = dict.get(b"ToUnicode").cloned() {
        let id = doc.add_object(s);
        dict.set("ToUnicode", id);
    }
}

fn pdf_with(mut font: lopdf::Dictionary, content: &str, page_extra: lopdf::Dictionary) -> Document {
    let mut doc = Document::with_version("1.5");
    indirect(&mut doc, &mut font);
    let pages_id = doc.new_object_id();
    let font_id = doc.add_object(font);
    let image = Stream::new(
        dictionary! {"Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1,
        "ColorSpace" => "DeviceGray", "BitsPerComponent" => 8},
        vec![0],
    );
    let image_id = doc.add_object(image);
    let resources = dictionary! {
        "Font" => dictionary! {"F1" => font_id},
        "XObject" => dictionary! {"Im1" => image_id},
    };
    let content_id = doc.add_object(Stream::new(dictionary! {}, content.as_bytes().to_vec()));
    let mut page = dictionary! {
        "Type" => "Page", "Parent" => pages_id, "Contents" => content_id,
        "Resources" => resources, "MediaBox" => vec![0.into(), 0.into(), 612.into(), 792.into()],
    };
    page.extend(&page_extra);
    let page_id = doc.add_object(page);
    let pages = dictionary! {"Type" => "Pages", "Kids" => vec![page_id.into()], "Count" => 1};
    doc.objects.insert(pages_id, Object::Dictionary(pages));
    let catalog_id = doc.add_object(dictionary! {"Type" => "Catalog", "Pages" => pages_id});
    doc.trailer.set("Root", catalog_id);
    doc
}

fn bytes(mut doc: Document) -> Vec<u8> {
    let mut out = Vec::new();
    doc.save_to(&mut out).unwrap();
    out
}

fn read(font: lopdf::Dictionary, content: &str) -> Result<String, String> {
    let doc = pdf_with(font, content, dictionary! {});
    pdf_text::transcribe_bytes(&bytes(doc)).map_err(|e| format!("{e:#}"))
}

fn fails(font: lopdf::Dictionary, content: &str, needle: &str) {
    match read(font, content) {
        Ok(text) => panic!("expected a loud failure naming {needle:?}, got text {text:?}"),
        Err(e) => assert!(e.contains(needle), "{e}"),
    }
}

fn to_unicode(pairs: &str) -> Stream {
    let cmap = format!(
        "begincmap\n1 begincodespacerange\n<0000><FFFF>\nendcodespacerange\n{pairs}\nendcmap"
    );
    Stream::new(dictionary! {}, cmap.into_bytes())
}

const HELLO: &str = "BT /F1 12 Tf 72 700 Td (Hello world) Tj ET";

#[test]
fn positive_control_reads_a_plain_page() {
    assert_eq!(read(helvetica(), HELLO).unwrap(), "Hello world\n");
    let turned = "BT /F1 12 Tf 0 1 -1 0 300 100 Tm (Turned text) Tj ET";
    assert_eq!(read(helvetica(), turned).unwrap(), "Turned text\n");
    let rotated_page = pdf_with(helvetica(), HELLO, dictionary! {"Rotate" => 90});
    assert_eq!(
        pdf_text::transcribe_bytes(&bytes(rotated_page)).unwrap(),
        "Hello world\n"
    );
}

#[test]
fn encrypted_pdf_fails_loud() {
    use lopdf::encryption::{EncryptionState, EncryptionVersion, Permissions};
    let mut doc = pdf_with(helvetica(), HELLO, dictionary! {});
    doc.trailer
        .set("ID", vec![Object::string_literal("0123456789abcdef"); 2]);
    let state = EncryptionState::try_from(EncryptionVersion::V2 {
        document: &doc,
        owner_password: "owner",
        user_password: "",
        key_length: 128,
        permissions: Permissions::all(),
    })
    .unwrap();
    doc.encrypt(&state).unwrap();
    let e = format!("{:#}", pdf_text::transcribe_bytes(&bytes(doc)).unwrap_err());
    assert!(e.contains("encrypted"), "{e}");
}

#[test]
fn type3_font_fails_loud() {
    let font = dictionary! {
        "Type" => "Font", "Subtype" => "Type3", "FontMatrix" => vec![0.001.into(), 0.into(), 0.into(), 0.001.into(), 0.into(), 0.into()],
        "Encoding" => "WinAnsiEncoding", "FirstChar" => 32, "LastChar" => 126,
        "Widths" => (32..=126).map(|c| Object::Integer(400 + c)).collect::<Vec<_>>(),
    };
    fails(font.clone(), HELLO, "Type3 font");
    let mut mapped = font;
    mapped.set(
        "ToUnicode",
        Object::Stream(to_unicode("1 beginbfchar\n<48> <0048>\nendbfchar")),
    );
    assert_eq!(
        read(mapped.clone(), "BT /F1 12 Tf 72 700 Td (H) Tj ET").unwrap(),
        "H\n"
    );
    fails(mapped, HELLO, "Type3 font");
}

fn cid_font(encoding: &str, tounicode: Option<Stream>) -> lopdf::Dictionary {
    let descendant = dictionary! {
        "Type" => "Font", "Subtype" => "CIDFontType2", "BaseFont" => "Fake",
        "CIDSystemInfo" => dictionary! {"Registry" => Object::string_literal("Adobe"), "Ordering" => Object::string_literal("Identity"), "Supplement" => 0},
        "DW" => 500,
    };
    let mut font = dictionary! {
        "Type" => "Font", "Subtype" => "Type0", "BaseFont" => "Fake", "Encoding" => encoding,
        "DescendantFonts" => vec![Object::Dictionary(descendant)],
    };
    if let Some(s) = tounicode {
        font.set("ToUnicode", Object::Stream(s));
    }
    font
}

const CID_HI: &str = "BT /F1 12 Tf 72 700 Td <00480049> Tj ET";

#[test]
fn cid_font_needs_a_usable_mapping() {
    let map = || to_unicode("2 beginbfchar\n<0048> <0048>\n<0049> <0069>\nendbfchar");
    assert_eq!(
        read(cid_font("Identity-H", Some(map())), CID_HI).unwrap(),
        "Hi\n"
    );
    fails(cid_font("Identity-H", None), CID_HI, "no usable /ToUnicode");
    fails(cid_font("Identity-V", Some(map())), CID_HI, "Identity-V");
    fails(
        cid_font("UniJIS-UCS2-H", Some(map())),
        CID_HI,
        "UniJIS-UCS2-H",
    );
    let partial = to_unicode("1 beginbfchar\n<0048> <0048>\nendbfchar");
    fails(
        cid_font("Identity-H", Some(partial)),
        CID_HI,
        "code 0x49 has no Unicode mapping",
    );
}

#[test]
fn simple_font_code_without_a_meaning_fails_loud() {
    let mut font = helvetica();
    font.set(
        "Encoding",
        dictionary! {"Type" => "Encoding", "Differences" => vec![33.into(), Object::Name(b"g17".to_vec())]},
    );
    fails(
        font.clone(),
        "BT /F1 12 Tf 72 700 Td (A!) Tj ET",
        "code 0x21 has no Unicode mapping",
    );
    font.set(
        "ToUnicode",
        Object::Stream(to_unicode("1 beginbfchar\n<21> <0000>\nendbfchar")),
    );
    fails(
        font.clone(),
        "BT /F1 12 Tf 72 700 Td (A!) Tj ET",
        "sits inside a word",
    );
    let apart = "BT /F1 12 Tf 72 700 Td (A) Tj 200 0 Td (!) Tj ET";
    assert_eq!(read(font.clone(), apart).unwrap(), "A\n");
    font.set(
        "ToUnicode",
        Object::Stream(to_unicode("1 beginbfchar\n<21> <2605>\nendbfchar")),
    );
    assert_eq!(
        read(font, "BT /F1 12 Tf 72 700 Td (A!) Tj ET").unwrap(),
        "A\u{2605}\n"
    );
}

#[test]
fn a_named_glyph_outranks_a_contradicting_tounicode() {
    let mut font = helvetica();
    font.set(
        "Encoding",
        dictionary! {"Type" => "Encoding", "Differences" => vec![33.into(), Object::Name(b"ff".to_vec())]},
    );
    font.set(
        "ToUnicode",
        Object::Stream(to_unicode("1 beginbfchar\n<21> <21B5>\nendbfchar")),
    );
    assert_eq!(
        read(font, "BT /F1 12 Tf 72 700 Td (o!ers) Tj ET").unwrap(),
        "offers\n"
    );
}

#[test]
fn right_to_left_text_fails_loud() {
    let mut font = helvetica();
    font.set(
        "ToUnicode",
        Object::Stream(to_unicode("1 beginbfchar\n<41> <05D0>\nendbfchar")),
    );
    fails(font, "BT /F1 12 Tf 72 700 Td (A) Tj ET", "right-to-left");
}

#[test]
fn skewed_mirrored_and_invisible_text_fail_loud() {
    fails(
        helvetica(),
        "BT /F1 12 Tf 0.866 0.5 -0.5 0.866 72 700 Tm (Tilted) Tj ET",
        "degrees",
    );
    fails(
        helvetica(),
        "BT /F1 12 Tf -1 0 0 1 300 700 Tm (Mirror) Tj ET",
        "mirrored",
    );
    fails(
        helvetica(),
        "BT 3 Tr /F1 12 Tf 72 700 Td (Hidden) Tj ET",
        "0 printed",
    );
    let mixed = "BT /F1 12 Tf 72 700 Td (Shown) Tj 3 Tr 0 -20 Td (Hidden) Tj ET";
    fails(helvetica(), mixed, "6 invisible glyphs, 5 printed");
}

#[test]
fn a_scan_with_a_printed_footer_and_an_ocr_layer_fails_loud() {
    let page = "q 612 0 0 792 0 0 cm /Im1 Do Q \
        BT /F1 8 Tf 72 30 Td (Downloaded from a library) Tj ET \
        BT 3 Tr /F1 12 Tf 72 700 Td (The body of the article) Tj ET";
    fails(helvetica(), page, "1 images");
    let one_hidden = "q 612 0 0 792 0 0 cm /Im1 Do Q \
        BT /F1 8 Tf 72 30 Td (Downloaded from a library) Tj ET \
        BT 3 Tr /F1 12 Tf 72 700 Td (x) Tj ET";
    fails(helvetica(), one_hidden, "1 invisible glyphs");
    let footer_only = "q 612 0 0 792 0 0 cm /Im1 Do Q \
        BT /F1 8 Tf 72 30 Td (Downloaded from a library) Tj ET";
    assert_eq!(
        read(helvetica(), footer_only).unwrap(),
        "Downloaded from a library\n"
    );
}

#[test]
fn a_scan_drawn_as_an_inline_image_fails_loud() {
    let page = "q 612 0 0 792 0 0 cm BI /W 1 /H 1 /CS /G /BPC 8 ID A EI Q \
        BT /F1 8 Tf 72 30 Td (Downloaded from a library) Tj ET \
        BT 3 Tr /F1 12 Tf 72 700 Td (Body) Tj ET";
    fails(
        helvetica(),
        page,
        "4 invisible glyphs, 22 printed, 1 images",
    );
}

#[test]
fn a_missing_xobject_fails_loud() {
    fails(
        helvetica(),
        "/Nope Do",
        "XObject /Nope is invoked but missing",
    );
}

#[test]
fn a_self_invoking_form_fails_loud() {
    let mut doc = pdf_with(helvetica(), "/Fm1 Do", dictionary! {});
    let form_id = doc.new_object_id();
    let form = Stream::new(
        dictionary! {"Type" => "XObject", "Subtype" => "Form",
        "BBox" => vec![0.into(), 0.into(), 612.into(), 792.into()],
        "Resources" => dictionary! {"XObject" => dictionary! {"Fm1" => form_id}}},
        b"/Fm1 Do".to_vec(),
    );
    doc.objects.insert(form_id, Object::Stream(form));
    let page_id = *doc.get_pages().values().next().unwrap();
    let page = doc.get_object_mut(page_id).unwrap().as_dict_mut().unwrap();
    let res = page.get_mut(b"Resources").unwrap().as_dict_mut().unwrap();
    res.set("XObject", dictionary! {"Fm1" => form_id});
    let err = pdf_text::transcribe_bytes(&bytes(doc)).unwrap_err();
    assert!(
        format!("{err:#}").contains("nest deeper than 16 levels"),
        "{err:#}"
    );
}

#[test]
fn an_image_only_page_fails_loud() {
    fails(
        helvetica(),
        "q 612 0 0 792 0 0 cm /Im1 Do Q",
        "no text layer",
    );
}

#[test]
fn a_stray_token_fails_loud_instead_of_truncating_the_page() {
    let lost = "BT /F1 12 Tf 72 600 Td (Lost line) Tj ET";
    assert_eq!(
        read(helvetica(), &format!("{HELLO} {lost}")).unwrap(),
        "Hello world\n\nLost line\n"
    );
    for junk in ["@", "]"] {
        fails(
            helvetica(),
            &format!("{HELLO} {junk} {lost}"),
            "holds a token lopdf cannot parse",
        );
    }
}
