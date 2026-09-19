mod parity_fixture;

use parity_fixture::{leg, root};
use std::path::Path;
use std::process::Command;

const LADDER: [&str; 6] = ["none", "G1", "G2", "V1", "V2", "E"];

fn committed() -> serde_json::Value {
    let out = Command::new("git")
        .current_dir(root())
        .args(["show", "HEAD:meta/verification/baseline.json"])
        .output()
        .expect("git show");
    assert!(out.status.success(), "git show HEAD:baseline.json failed");
    serde_json::from_slice(&out.stdout).expect("committed baseline json")
}

fn first_page(doc: &serde_json::Value) -> Option<String> {
    doc["pages"].as_object()?.keys().next().cloned()
}

fn shifted(doc: &serde_json::Value, page: &str, by: i64) -> serde_json::Value {
    let mut doc = doc.clone();
    let tier = doc["pages"][page]["tier"]
        .as_str()
        .expect("tier")
        .to_string();
    let rank = LADDER.iter().position(|t| *t == tier).expect("known tier");
    let moved = rank
        .saturating_add_signed(by as isize)
        .min(LADDER.len() - 1);
    doc["pages"][page]["tier"] = serde_json::Value::String(LADDER[moved].into());
    doc
}

fn run(label: &str, dir: &Path, baseline: &Path, a: &Path) -> (bool, String) {
    let out = Command::new(env!("CARGO_BIN_EXE_mag"))
        .current_dir(root())
        .env("MAG_PARITY_OUT_DIR", dir.join("out"))
        .env("MAG_PARITY_BASELINE", baseline)
        .args(["parity", label, "--pre-rendered"])
        .args([a, a])
        .output()
        .expect("mag parity");
    (
        out.status.success(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
    )
}

#[test]
fn a_lowered_working_tree_baseline_is_refused_and_a_raised_one_is_accepted() {
    let doc = committed();
    let Some(page) = first_page(&doc) else {
        println!("MODE: skipped, HEAD:baseline.json carries no page entries");
        return;
    };
    let entries = doc["pages"].as_object().expect("pages").len();
    let tier = doc["pages"][&page]["tier"].as_str().expect("tier");
    println!("MODE: full, {entries} committed page entries, exercising page {page} at tier {tier}");

    let dir = root().join("output/parity-ratchet");
    let a = leg(&dir, "equal", 0.0);
    std::fs::create_dir_all(&dir).expect("mkdir");
    let write = |name: &str, value: &serde_json::Value| {
        let path = dir.join(name);
        std::fs::write(&path, serde_json::to_string_pretty(value).expect("json")).expect("write");
        path
    };

    let mut dropped = doc.clone();
    dropped["pages"]
        .as_object_mut()
        .expect("pages")
        .remove(&page);
    let removed = write("removed.json", &dropped);
    let (ok, err) = run("ratchet", &dir, &removed, &a);
    assert!(!ok, "a removed baseline entry must refuse the run");
    assert!(
        err.contains("lowers 1 committed baseline entries")
            && err.contains(&format!("page {page}: entry removed")),
        "the refusal must name the removed page: {err}"
    );

    if LADDER.iter().position(|t| *t == tier).expect("known tier") > 0 {
        let lowered = write("lowered.json", &shifted(&doc, &page, -1));
        let (ok, err) = run("ratchet", &dir, &lowered, &a);
        assert!(!ok, "a lowered baseline entry must refuse the run");
        assert!(
            err.contains(&format!("page {page}: tier lowered")),
            "the refusal must name the lowered page: {err}"
        );
    } else {
        println!("MODE: tier-lowering not exercised, page {page} is at the bottom rung");
    }

    let unchanged = write("unchanged.json", &doc);
    let (ok, err) = run("ratchet", &dir, &unchanged, &a);
    assert!(ok, "an unchanged baseline must be accepted: {err}");

    let raised = write("raised.json", &shifted(&doc, &page, 1));
    let (ok, err) = run("ratchet", &dir, &raised, &a);
    assert!(ok, "a raised baseline entry must be accepted: {err}");
}
