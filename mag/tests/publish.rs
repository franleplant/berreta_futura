use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn scratch(tag: &str) -> PathBuf {
    let root = std::env::temp_dir().join(format!("mag-publish-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(root.join("prompts")).unwrap();
    std::fs::create_dir_all(root.join("editions/011")).unwrap();
    std::fs::write(
        root.join("magazine.toml"),
        "[publication]\nname = \"Berreta Futura\"\n\n[site]\nbase_url = \"https://b.example\"\neditions = [\"011\"]\npdf_remote = \"drive:pdfs/\"\n",
    )
    .unwrap();
    root
}

fn publish(root: &Path, file: &str, lang: &str) -> Output {
    Command::new(env!("CARGO_BIN_EXE_mag"))
        .args(["publish", "011", "--pdf", file, "--lang", lang, "--dry-run"])
        .current_dir(root)
        .output()
        .unwrap()
}

#[test]
fn publish_names_the_object_by_content_writes_nothing_on_a_dry_run_and_refuses_a_non_pdf() {
    let root = scratch("dry");
    std::fs::write(root.join("a.pdf"), "%PDF-1.7 english").unwrap();
    std::fs::write(root.join("b.pdf"), "%PDF-1.7 spanish").unwrap();
    std::fs::write(root.join("fake.pdf"), "<html>").unwrap();
    let english = publish(&root, "a.pdf", "en");
    assert!(english.status.success(), "{english:?}");
    let stdout = String::from_utf8(english.stdout).unwrap();
    let sha = "a85679e8";
    let key = format!("011/en/berreta-futura-011-en-{sha}.pdf");
    assert!(stdout.contains(&format!(
        "rclone copyto a.pdf drive:pdfs/{key} && rclone link drive:pdfs/{key}"
    )));
    assert!(stdout.contains(&format!(
        "would write editions/011/publish.yaml with the en PDF at drive:pdfs/{key}"
    )));
    assert!(publish(&root, "b.pdf", "es").status.success());
    let refused = publish(&root, "fake.pdf", "en");
    assert!(!refused.status.success());
    assert!(String::from_utf8_lossy(&refused.stderr).contains("is not a PDF"));
    assert!(!root.join("editions/011/publish.yaml").exists());
    std::fs::remove_dir_all(&root).unwrap();
}

#[test]
fn publish_uploads_through_rclone_and_merges_each_language_into_publish_yaml() {
    use std::os::unix::fs::PermissionsExt;
    let root = scratch("live");
    let bin = root.join("bin");
    std::fs::create_dir_all(&bin).unwrap();
    let stub = bin.join("rclone");
    std::fs::write(
        &stub,
        "#!/bin/sh\nif [ \"$1\" = link ]; then echo \"https://link.example/$2\"; fi\nexit 0\n",
    )
    .unwrap();
    std::fs::set_permissions(&stub, std::fs::Permissions::from_mode(0o755)).unwrap();
    let path = format!("{}:{}", bin.display(), std::env::var("PATH").unwrap());
    std::fs::write(root.join("a.pdf"), "%PDF-1.7 english").unwrap();
    std::fs::write(root.join("b.pdf"), "%PDF-1.7 spanish").unwrap();
    for (file, lang) in [("a.pdf", "en"), ("b.pdf", "es")] {
        let out = Command::new(env!("CARGO_BIN_EXE_mag"))
            .args(["publish", "011", "--pdf", file, "--lang", lang])
            .env("PATH", &path)
            .current_dir(&root)
            .output()
            .unwrap();
        assert!(out.status.success(), "{out:?}");
    }
    let record = std::fs::read_to_string(root.join("editions/011/publish.yaml")).unwrap();
    assert!(
        record.contains(
            "url: https://link.example/drive:pdfs/011/en/berreta-futura-011-en-a85679e8.pdf"
        ),
        "{record}"
    );
    assert!(record.contains("011/es/berreta-futura-011-es-"), "{record}");
    assert!(record.contains("bytes: 16"), "{record}");
    assert!(record.contains(&"sha256: a85679e8".to_string()), "{record}");
    std::fs::remove_dir_all(&root).unwrap();
}
