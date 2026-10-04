use std::fs;
use std::path::Path;

const DETECTION: [&str; 4] = [
    "src/capture.rs",
    "src/produce.rs",
    "src/pdf_text.rs",
    "src/model/doc.rs",
];

fn offenders(root: &Path, dir: &Path, found: &mut Vec<String>) {
    for entry in fs::read_dir(dir).unwrap().flatten() {
        let path = entry.path();
        if path.is_dir() {
            offenders(root, &path, found);
        } else if path.extension().is_some_and(|e| e == "rs") {
            let text = fs::read_to_string(&path).unwrap();
            let relative = path.strip_prefix(root).unwrap().to_str().unwrap();
            for (n, line) in text.lines().enumerate() {
                let escaped = line.contains("\\u{2014}") && !DETECTION.contains(&relative);
                if line.contains('\u{2014}') || escaped {
                    found.push(format!("{}:{}", path.display(), n + 1));
                }
            }
        }
    }
}

#[test]
fn no_em_dash_in_rust_sources() {
    let mut found = Vec::new();
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    offenders(root, &root.join("src"), &mut found);
    assert!(found.is_empty(), "U+2014 in: {}", found.join(", "));
}
