use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::Command;

fn write(path: &Path, text: &str) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, text).unwrap();
}

#[test]
fn a_bad_article_fails_before_any_model_call_or_write() {
    let root = std::env::temp_dir().join(format!("mag-capture-first-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("prompts")).unwrap();
    let bin = root.join("bin");
    let marker = root.join("model-was-called");
    write(
        &bin.join("claude"),
        &format!("#!/bin/sh\ntouch {}\nexit 1\n", marker.display()),
    );
    fs::set_permissions(bin.join("claude"), fs::Permissions::from_mode(0o755)).unwrap();
    let toml = "[intake]\nedition = \"099\"\n";
    write(&root.join("magazine.toml"), toml);
    fs::create_dir_all(root.join("editions/099")).unwrap();
    write(&root.join("sources.md"), "# Sources\n");
    write(
        &root.join("page.html"),
        "<html><head><title>A Page About Things</title></head><body><p>Hello</p></body></html>",
    );
    let path = format!(
        "{}:{}",
        bin.display(),
        std::env::var("PATH").unwrap_or_default()
    );
    let out = Command::new(env!("CARGO_BIN_EXE_mag"))
        .current_dir(&root)
        .env("PATH", path)
        .args([
            "capture",
            "https://example.com/post",
            "--html",
            "page.html",
            "--edition",
            "099",
            "--article",
            "no-such-article",
        ])
        .output()
        .unwrap();
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(!out.status.success(), "{stderr}");
    assert!(stderr.contains("no-such-article"), "{stderr}");
    assert!(!marker.exists(), "the model was invoked");
    assert_eq!(
        fs::read_to_string(root.join("magazine.toml")).unwrap(),
        toml
    );
    assert!(!root.join("library/sources").exists());
    fs::remove_dir_all(&root).unwrap();
}

const PAGE_WORDS: &str = "Refreshing a source means transcribing the page again through the same fidelity gate that captured it the first time around, and nothing else in the repository may change when that happens.";

#[test]
fn refresh_replaces_one_source_and_touches_no_plan() {
    let root = std::env::temp_dir().join(format!("mag-capture-refresh-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    write(&root.join("prompts/capture.md"), "Transcribe {url}.\n");
    let bin = root.join("bin");
    let reply = format!(
        "# A Page About Things\nBy Someone\n\n{PAGE_WORDS}\n===META===\nsynopsis: A fresh synopsis.\n"
    );
    let envelope = serde_json::json!({"subtype": "success", "result": reply});
    write(&root.join("reply.json"), &envelope.to_string());
    write(
        &bin.join("claude"),
        &format!("#!/bin/sh\ncat {}\n", root.join("reply.json").display()),
    );
    fs::set_permissions(bin.join("claude"), fs::Permissions::from_mode(0o755)).unwrap();
    let sid = "a-page-about-things-aaaaaaaa";
    let record = format!(
        "id: {sid}\ntitle: 'A Page About Things'\nauthor: 'Someone'\nurl: https://example.com/post\ncaptured_at: '2026-01-01T00:00:00Z'\ntags: []\nsynopsis: 'Old synopsis.'\n"
    );
    write(
        &root.join(format!("library/sources/{sid}/record.yaml")),
        &record,
    );
    write(
        &root.join(format!("library/sources/{sid}/article.md")),
        "old text\n",
    );
    let plan = "edition:\n  id: '099'\narticles: []\n";
    write(&root.join("editions/099/plan.yaml"), plan);
    let dash = '\u{2014}';
    let md = format!(
        "# Sources\n\n## A Page About Things {dash} Someone\n\n- ID: `{sid}`\n- Source: https://example.com/post\n- Captured: 2026-01-01T00:00:00Z\n- Release: queued for `099`\n\nOld synopsis.\n"
    );
    write(&root.join("sources.md"), &md);
    write(
        &root.join("page.html"),
        &format!("<html><head><title>A Page About Things</title></head><body><p>{PAGE_WORDS}</p></body></html>"),
    );
    let path = format!(
        "{}:{}",
        bin.display(),
        std::env::var("PATH").unwrap_or_default()
    );
    let out = Command::new(env!("CARGO_BIN_EXE_mag"))
        .current_dir(&root)
        .env("PATH", path)
        .args(["capture", "--refresh", sid, "--html", "page.html"])
        .output()
        .unwrap();
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(out.status.success(), "{stderr}");
    let article =
        fs::read_to_string(root.join(format!("library/sources/{sid}/article.md"))).unwrap();
    assert!(article.contains(PAGE_WORDS), "{article}");
    let record_after =
        fs::read_to_string(root.join(format!("library/sources/{sid}/record.yaml"))).unwrap();
    assert_eq!(
        record_after,
        record.replace("Old synopsis.", "A fresh synopsis.")
    );
    let md_after = fs::read_to_string(root.join("sources.md")).unwrap();
    assert_eq!(md_after, md.replace("Old synopsis.", "A fresh synopsis."));
    assert_eq!(
        fs::read_to_string(root.join("editions/099/plan.yaml")).unwrap(),
        plan
    );
    assert!(!root.join("library/release-state.yaml").exists());
    fs::remove_dir_all(&root).unwrap();
}
