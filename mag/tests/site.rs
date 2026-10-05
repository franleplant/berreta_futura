use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

fn repository() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}

fn build(out: &Path) -> String {
    let output = Command::new(env!("CARGO_BIN_EXE_mag"))
        .args(["site", "--out"])
        .arg(out)
        .current_dir(repository())
        .output()
        .unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(
        output.status.success(),
        "{stdout}{}",
        String::from_utf8_lossy(&output.stderr)
    );
    stdout
}

fn files(dir: &Path, root: &Path, out: &mut BTreeMap<String, Vec<u8>>) {
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        match path.is_dir() {
            true => files(&path, root, out),
            false => {
                let key = path.strip_prefix(root).unwrap().display().to_string();
                out.insert(key, std::fs::read(&path).unwrap());
            }
        }
    }
}

#[test]
fn the_site_is_built_from_the_newest_tracked_run_with_every_page_and_the_same_bytes_twice() {
    let base = std::env::temp_dir().join(format!("mag-site-{}", std::process::id()));
    let (first, second) = (base.join("a"), base.join("b"));
    let live = repository().join(".magazine/site");
    let existed = live.exists();
    let log = build(&first);
    assert!(
        existed || !live.exists(),
        "the site build wrote into the live .magazine/site"
    );
    build(&second);
    let run = log
        .lines()
        .find_map(|line| line.strip_prefix("content: "))
        .expect("the site names the run it read");
    let tracked = Command::new("git")
        .args(["ls-files", "--", run])
        .current_dir(repository())
        .output()
        .unwrap()
        .stdout;
    assert!(!tracked.is_empty(), "{run} is not tracked by git");
    let (mut a, mut b) = (BTreeMap::new(), BTreeMap::new());
    files(&first, &first, &mut a);
    files(&second, &second, &mut b);
    assert!(a == b, "two builds from the same inputs differ");
    let edition = std::fs::read_to_string(repository().join("editions/011/edition.yaml")).unwrap();
    let yaml: serde_norway::Value = serde_norway::from_str(&edition).unwrap();
    for article in yaml["articles"].as_sequence().unwrap() {
        let page = format!("011/{}/index.html", article["id"].as_str().unwrap());
        assert!(a.contains_key(&page), "missing {page}");
    }
    for page in [
        "index.html",
        "011/index.html",
        "404.html",
        "site.css",
        "favicon.svg",
        "apple-touch-icon.png",
        "og.png",
    ] {
        assert!(a.contains_key(page), "missing {page}");
    }
    let brand = repository().join("mag/assets/brand");
    assert_eq!(
        a["favicon.svg"],
        std::fs::read(brand.join("mark.svg")).unwrap()
    );
    let wordmark = std::fs::read_to_string(brand.join("wordmark.svg")).unwrap();
    let body = &wordmark[wordmark.find("</title>").unwrap() + 8..wordmark.rfind("</svg>").unwrap()];
    assert!(String::from_utf8_lossy(&a["index.html"]).contains(body));
    std::fs::remove_dir_all(&base).unwrap();
}

#[test]
fn epub_rebuilds_its_own_tracked_file_while_site_refuses_a_modified_epub() {
    let dir = std::env::temp_dir().join(format!("mag-epub-clone-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let origin = repository().display().to_string();
    let target = dir.display().to_string();
    let git = |args: &[&str], cwd: &Path| {
        let status = Command::new("git")
            .args(args)
            .current_dir(cwd)
            .status()
            .unwrap();
        assert!(status.success(), "git {args:?}");
    };
    git(
        &["clone", "-q", "--local", "--no-checkout", &origin, &target],
        &repository(),
    );
    git(
        &[
            "sparse-checkout",
            "set",
            "--cone",
            "editions/012",
            "library",
            "mag/assets",
            "prompts",
        ],
        &dir,
    );
    git(&["checkout", "-q", "HEAD"], &dir);
    let cover = std::fs::read_dir(dir.join("editions/012/art/picks"))
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .find(|path| {
            path.file_name()
                .unwrap()
                .to_string_lossy()
                .starts_with("cover-")
        })
        .unwrap();
    let mag = |args: &[&str]| {
        Command::new(env!("CARGO_BIN_EXE_mag"))
            .args(args)
            .current_dir(&dir)
            .output()
            .unwrap()
    };
    let cover = cover.display().to_string();
    let epub = dir.join("editions/012/epub/berreta-futura-012-en.epub");
    for _ in 0..2 {
        let out = mag(&["epub", "012", "--cover", &cover]);
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        std::fs::write(&epub, b"modified").unwrap();
    }
    let site = mag(&["site", "--out", &dir.join("site").display().to_string()]);
    assert!(!site.status.success());
    let stderr = String::from_utf8_lossy(&site.stderr);
    assert!(stderr.contains("untracked or modified"), "{stderr}");
    std::fs::remove_dir_all(&dir).unwrap();
}
