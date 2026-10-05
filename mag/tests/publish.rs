use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn scratch(tag: &str) -> PathBuf {
    let root = std::env::temp_dir().join(format!("mag-publish-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(root.join("prompts")).unwrap();
    std::fs::create_dir_all(root.join("tmp")).unwrap();
    std::fs::create_dir_all(root.join("editions/011")).unwrap();
    std::fs::write(root.join("editions/011/edition.yaml"), "title: Trust\n").unwrap();
    std::fs::write(
        root.join("magazine.toml"),
        "[publication]\nname = \"Berreta Futura\"\n\n[site]\nbase_url = \"https://b.example\"\neditions = [\"011\"]\nrepo = \"o/r\"\n",
    )
    .unwrap();
    std::fs::write(root.join("a.pdf"), "%PDF-1.7 english").unwrap();
    std::fs::write(root.join("a.epub"), "PK book").unwrap();
    root
}

fn fake_gh(root: &Path) -> String {
    let bin = root.join("bin");
    std::fs::create_dir_all(&bin).unwrap();
    let stub = bin.join("gh");
    std::fs::write(
        &stub,
        "#!/bin/sh\necho \"$@\" >> gh.log\nif [ \"$1\" = api ]; then cat release.json || exit 1; fi\nif [ \"$1 $2\" = \"release create\" ]; then echo '{\"assets\":[]}' > release.json; fi\n",
    )
    .unwrap();
    std::fs::set_permissions(&stub, std::fs::Permissions::from_mode(0o755)).unwrap();
    format!("{}:{}", bin.display(), std::env::var("PATH").unwrap())
}

fn publish(root: &Path, path: &str, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_mag"))
        .args(["publish", "011", "--pdf", "a.pdf"])
        .args(args)
        .env("PATH", path)
        .env("TMPDIR", root.join("tmp"))
        .current_dir(root)
        .output()
        .unwrap()
}

fn log(root: &Path) -> Vec<String> {
    std::fs::read_to_string(root.join("gh.log"))
        .unwrap_or_default()
        .lines()
        .map(str::to_string)
        .collect()
}

#[test]
fn a_dry_run_calls_no_gh_and_writes_nothing_and_a_wrong_file_is_refused() {
    let root = scratch("dry");
    let path = fake_gh(&root);
    std::fs::write(root.join("fake.pdf"), "<html>").unwrap();
    let out = publish(&root, &path, &["--epub", "a.epub", "--dry-run"]);
    assert!(out.status.success(), "{out:?}");
    let stdout = String::from_utf8(out.stdout).unwrap();
    assert!(
        stdout.contains("as berreta-futura-011-en.pdf to o/r"),
        "{stdout}"
    );
    assert!(
        stdout.contains("as berreta-futura-011-en.epub to o/r"),
        "{stdout}"
    );
    assert!(log(&root).is_empty());
    assert!(!root.join("editions/011/publish.yaml").exists());
    let refused = Command::new(env!("CARGO_BIN_EXE_mag"))
        .args(["publish", "011", "--pdf", "fake.pdf"])
        .env("PATH", &path)
        .current_dir(&root)
        .output()
        .unwrap();
    assert!(String::from_utf8_lossy(&refused.stderr).contains("is not a pdf"));
    assert!(log(&root).is_empty());
    std::fs::remove_dir_all(&root).unwrap();
}

#[test]
fn publish_creates_the_release_once_uploads_with_clobber_and_skips_what_is_unchanged() {
    let root = scratch("live");
    let path = fake_gh(&root);
    let out = publish(&root, &path, &["--epub", "a.epub"]);
    assert!(out.status.success(), "{out:?}");
    let calls = log(&root);
    assert_eq!(calls.len(), 4, "{calls:?}");
    assert_eq!(calls[0], "api repos/o/r/releases/tags/issue-011");
    assert_eq!(
        calls[1],
        "release create issue-011 --repo o/r --title Issue 011: Trust --notes  --latest=false"
    );
    for (call, name) in [(&calls[2], "pdf"), (&calls[3], "epub")] {
        assert!(call.starts_with("release upload issue-011 "), "{call}");
        assert!(call.contains(&format!(
            "berreta-futura-011-en.{name} --clobber --repo o/r"
        )));
    }
    let yaml = root.join("editions/011/publish.yaml");
    let record = std::fs::read_to_string(&yaml).unwrap();
    let base = "https://github.com/o/r/releases/download/issue-011/berreta-futura-011-en";
    assert!(record.contains(&format!("url: {base}.pdf")), "{record}");
    assert!(record.contains(&format!("url: {base}.epub")), "{record}");
    assert!(record.contains("bytes: 16") && record.contains("sha256: a85679e8"));
    let digest = record
        .lines()
        .find_map(|l| l.trim().strip_prefix("sha256: a85679e8"))
        .unwrap();
    let pdf = format!("a85679e8{digest}");
    std::fs::write(
        root.join("release.json"),
        format!("{{\"assets\":[{{\"name\":\"berreta-futura-011-en.pdf\",\"digest\":\"sha256:{pdf}\"}}]}}"),
    )
    .unwrap();
    std::fs::remove_file(root.join("gh.log")).unwrap();
    std::fs::write(root.join("a.epub"), "PK changed").unwrap();
    let out = publish(&root, &path, &["--epub", "a.epub"]);
    assert!(out.status.success(), "{out:?}");
    let calls = log(&root);
    assert_eq!(calls.len(), 2, "{calls:?}");
    assert!(calls[1].contains("berreta-futura-011-en.epub --clobber"));
    let record = std::fs::read_to_string(&yaml).unwrap();
    assert!(record.contains("bytes: 10"), "{record}");
    std::fs::remove_dir_all(&root).unwrap();
}

#[test]
fn a_failed_epub_upload_leaves_publish_yaml_unchanged_and_no_staging_dir() {
    let root = scratch("fail");
    let path = fake_gh(&root);
    let stub = root.join("bin/gh");
    let body = std::fs::read_to_string(&stub).unwrap();
    std::fs::write(
        &stub,
        body.replace(
            "if [ \"$1\" = api ]",
            "case \"$*\" in *.epub*) echo boom >&2; exit 1;; esac\nif [ \"$1\" = api ]",
        ),
    )
    .unwrap();
    let out = publish(&root, &path, &["--epub", "a.epub"]);
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("publish.yaml is unchanged"));
    assert!(!root.join("editions/011/publish.yaml").exists());
    assert_eq!(std::fs::read_dir(root.join("tmp")).unwrap().count(), 0);
    std::fs::remove_dir_all(&root).unwrap();
}
