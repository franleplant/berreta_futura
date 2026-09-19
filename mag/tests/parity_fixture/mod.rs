use lopdf::{dictionary, Document, Object, Stream};
use std::path::{Path, PathBuf};

const PAGES: u32 = 4;
const A5: [f64; 2] = [419.528, 595.276];

pub fn root() -> PathBuf {
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/.."))
}

fn build(path: &Path, shift: f64) {
    let mut doc = Document::with_version("1.7");
    let pages_id = doc.new_object_id();
    let mut kids = Vec::new();
    for page in 1..=PAGES {
        let y = 120.0 + if page == 2 { shift } else { 0.0 };
        let ops = format!("0.2 0.2 0.2 RG 1 w 60 {y} m 300 {y} l S\n");
        let content = doc.add_object(Stream::new(dictionary! {}, ops.into_bytes()));
        let id = doc.add_object(dictionary! {
            "Type" => "Page",
            "Parent" => pages_id,
            "MediaBox" => vec![0.into(), 0.into(), A5[0].into(), A5[1].into()],
            "Contents" => content,
            "Resources" => dictionary! {},
        });
        kids.push(Object::Reference(id));
    }
    doc.objects.insert(
        pages_id,
        Object::Dictionary(dictionary! {
            "Type" => "Pages",
            "Count" => i64::from(PAGES),
            "Kids" => kids,
        }),
    );
    let catalog = doc.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
    doc.trailer.set("Root", catalog);
    std::fs::create_dir_all(path.parent().expect("parent")).expect("mkdir");
    doc.save(path).expect("save");
}

pub fn leg(dir: &Path, name: &str, shift: f64) -> PathBuf {
    build(&dir.join(name).join("en/reader.pdf"), shift);
    dir.join(name)
}
