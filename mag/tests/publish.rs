use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn scratch() -> PathBuf {
    let root = std::env::temp_dir().join(format!("mag-publish-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(root.join("prompts")).unwrap();
    std::fs::create_dir_all(root.join("editions/011")).unwrap();
    std::fs::write(
        root.join("magazine.toml"),
        "[publication]\nname = \"Berreta Futura\"\n\n[site]\nbase_url = \"https://b.example\"\neditions = [\"011\"]\npdf_bucket = \"pdfs\"\npdf_base_url = \"https://files.example/\"\n",
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
fn publish_names_the_object_by_content_merges_languages_and_refuses_a_non_pdf() {
    let root = scratch();
    std::fs::write(root.join("a.pdf"), "%PDF-1.7 english").unwrap();
    std::fs::write(root.join("b.pdf"), "%PDF-1.7 spanish").unwrap();
    std::fs::write(root.join("fake.pdf"), "<html>").unwrap();
    let english = publish(&root, "a.pdf", "en");
    assert!(english.status.success(), "{english:?}");
    let stdout = String::from_utf8(english.stdout).unwrap();
    let sha = "a85679e8";
    let key = format!("011/en/berreta-futura-011-en-{sha}.pdf");
    assert!(stdout.contains(&format!(
        "npx wrangler r2 object put pdfs/{key} --file a.pdf --remote --content-type application/pdf"
    )));
    assert!(stdout.contains("git add editions/011/publish.yaml"));
    assert!(publish(&root, "b.pdf", "es").status.success());
    let refused = publish(&root, "fake.pdf", "en");
    assert!(!refused.status.success());
    assert!(String::from_utf8_lossy(&refused.stderr).contains("is not a PDF"));
    let record: serde_yaml::Value = serde_yaml::from_str(
        &std::fs::read_to_string(root.join("editions/011/publish.yaml")).unwrap(),
    )
    .unwrap();
    let en = &record["pdfs"]["en"];
    assert_eq!(
        en["url"].as_str(),
        Some(format!("https://files.example/{key}").as_str())
    );
    assert_eq!(en["bytes"].as_u64(), Some(16));
    assert!(en["sha256"].as_str().unwrap().starts_with(sha));
    assert!(record["pdfs"]["es"]["url"]
        .as_str()
        .unwrap()
        .contains("/011/es/berreta-futura-011-es-"));
    std::fs::remove_dir_all(&root).unwrap();
}
