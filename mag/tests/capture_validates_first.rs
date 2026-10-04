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
    let release = "intake_edition_id: '099'\ncollecting_editions:\n- id: '099'\n  issue_number: 99\n  status: collecting\n  source_ids:\n  - first-aaaaaaaa\n";
    write(&root.join("library/release-state.yaml"), release);
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
        fs::read_to_string(root.join("library/release-state.yaml")).unwrap(),
        release
    );
    assert!(!root.join("library/sources").exists());
    fs::remove_dir_all(&root).unwrap();
}
