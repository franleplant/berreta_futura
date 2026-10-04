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
    let yaml: serde_yaml::Value = serde_yaml::from_str(&edition).unwrap();
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
