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
