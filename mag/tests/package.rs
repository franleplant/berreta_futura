use mag::package::archive;
use mag::package::contact;
use mag::package::release;
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

fn scratch(tag: &str) -> PathBuf {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("a clock after 1970")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("wp55c-{tag}-{stamp}"));
    std::fs::create_dir_all(&path).expect("the scratch directory is writable");
    path
}

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/package_fixtures")
}

#[test]
fn contact_sheets_cover_every_page_and_an_empty_list_writes_none() {
    let pages: Vec<PathBuf> = (0..17)
        .map(|index| fixtures().join(format!("pages/page-{:03}.png", index % 4 + 1)))
        .collect();
    let out = scratch("fixture-sheets");
    let sheets = contact::write_contact_sheets(&pages, &out, "fixture-sheet").unwrap();
    assert!(!sheets.is_empty());
    assert!(sheets.iter().all(|sheet| sheet.is_file()));
    assert!(contact::write_contact_sheets(&[], &out, "none")
        .unwrap()
        .is_empty());
}

#[test]
fn adopting_the_rendered_layout_moves_only_a_present_non_null_ledger() {
    let adopt =
        |mut manifest: Value| release::adopt_rendered_layout(&mut manifest).map(|()| manifest);
    let ledger = json!([{"article": "a", "art": "t1"}]);
    assert_eq!(
        adopt(json!({"edition": {"id": "010", "_rendered_tail_arts": ledger}})).unwrap(),
        json!({"edition": {"id": "010"}, "layout": {"tail_arts": ledger}})
    );
    assert_eq!(
        adopt(json!({"edition": {"_rendered_tail_arts": ledger}, "layout": {"toc": {}}})).unwrap(),
        json!({"edition": {}, "layout": {"toc": {}, "tail_arts": ledger}})
    );
    assert_eq!(
        adopt(json!({"edition": {"_rendered_tail_arts": null}})).unwrap(),
        json!({"edition": {}})
    );
    for untouched in [
        json!({"edition": "010"}),
        json!({"edition": {"id": 1}}),
        json!({"layout": 1}),
    ] {
        assert_eq!(adopt(untouched.clone()).unwrap(), untouched);
    }
    let error =
        adopt(json!({"edition": {"_rendered_tail_arts": ledger}, "layout": []})).unwrap_err();
    assert_eq!(
        error.to_string(),
        "manifest layout must be a mapping to adopt the rendered tail arts"
    );
}

#[test]
fn visual_review_status_covers_every_recorded_review_branch() {
    let dir = scratch("review");
    let (reader, booklet) = (dir.join("reader.pdf"), dir.join("booklet.pdf"));
    std::fs::write(&reader, b"reader").unwrap();
    std::fs::write(&booklet, b"booklet").unwrap();
    let (r, b) = (
        release::sha256(&reader).unwrap(),
        release::sha256(&booklet).unwrap(),
    );
    let status = |review: Option<Value>| {
        release::visual_review_status(review.as_ref(), "010", "en", &reader, &booklet)
    };
    let fresh = json!({"en": {"reader_sha256": r, "booklet_sha256": b}});
    let unrecorded = status(None).unwrap();
    assert_eq!(unrecorded["status"], "required_before_release");
    assert_eq!(unrecorded["findings"], json!([]));
    assert_eq!(unrecorded["reader_sha256"], json!(r));
    let approved = json!({"edition_id": "010", "languages": fresh, "result": "approved", "reviewer": "fran", "findings": ["ok"]});
    let row = status(Some(approved.clone())).unwrap();
    assert_eq!(
        (
            row["status"].clone(),
            row["reviewer"].clone(),
            row["findings"].clone()
        ),
        (json!("approved"), json!("fran"), json!(["ok"]))
    );
    let mut changes = approved.clone();
    changes["result"] = json!("changes_required_by_editor");
    assert_eq!(status(Some(changes)).unwrap()["status"], "changes_required");
    let mut other_edition = approved.clone();
    other_edition["edition_id"] = json!("009");
    let mut no_row = approved.clone();
    no_row["languages"] = json!({"es": fresh["en"]});
    let mut moved = approved.clone();
    moved["languages"]["en"]["booklet_sha256"] = json!("0");
    for stale in [other_edition, no_row, moved, json!({"edition_id": "010"})] {
        assert_eq!(status(Some(stale)).unwrap()["status"], "stale");
    }
    let mut spelled = approved.clone();
    spelled["findings"] = json!("ab");
    assert_eq!(
        status(Some(spelled)).unwrap()["findings"],
        json!(["a", "b"])
    );
    for (broken, message) in [
        (json!([1]), "a recorded visual review must be a mapping"),
        (
            json!({"languages": []}),
            "a recorded visual review's languages must be a mapping",
        ),
        (
            json!({"findings": null}),
            "a recorded visual review's findings must be iterable",
        ),
    ] {
        assert_eq!(status(Some(broken)).unwrap_err().to_string(), message);
    }
}

fn zip_entries(path: &Path) -> Vec<(Value, Vec<u8>)> {
    use std::io::Read;
    let bytes = std::fs::read(path).unwrap();
    let word = |at: usize| u32::from_le_bytes(bytes[at..at + 4].try_into().unwrap());
    let half = |at: usize| u16::from_le_bytes(bytes[at..at + 2].try_into().unwrap()) as usize;
    let end = bytes.len() - 22;
    assert_eq!(word(end), 0x0605_4b50);
    let mut at = word(end + 16) as usize;
    let mut entries = vec![];
    for _ in 0..half(end + 10) {
        assert_eq!(word(at), 0x0201_4b50);
        let (name_len, extra_len, comment_len) = (half(at + 28), half(at + 30), half(at + 32));
        let name = String::from_utf8(bytes[at + 46..at + 46 + name_len].to_vec()).unwrap();
        let (time, date) = (half(at + 12), half(at + 14));
        let date_time = json!([
            1980 + (date >> 9),
            (date >> 5) & 15,
            date & 31,
            time >> 11,
            (time >> 5) & 63,
            (time & 31) * 2
        ]);
        let local = word(at + 42) as usize;
        let start = local + 30 + half(local + 26) + half(local + 28);
        let packed = &bytes[start..start + word(at + 20) as usize];
        let mut data = vec![];
        flate2::read::DeflateDecoder::new(packed)
            .read_to_end(&mut data)
            .unwrap();
        entries.push((
            json!([
                name,
                date_time,
                word(at + 38),
                half(at + 10),
                word(at + 16),
                word(at + 24)
            ]),
            data,
        ));
        at += 46 + name_len + extra_len + comment_len;
    }
    entries
}

#[test]
fn archive_entries_hold_the_tree_files_byte_for_byte() {
    let tree = fixtures().join("tree");
    let out = scratch("archive").join("tree.zip");
    archive::archive_tree(&tree, &out).unwrap();
    let entries = zip_entries(&out);
    assert!(!entries.is_empty());
    for (row, data) in entries {
        assert_eq!(
            data,
            std::fs::read(tree.join(row[0].as_str().unwrap())).unwrap()
        );
    }
}
