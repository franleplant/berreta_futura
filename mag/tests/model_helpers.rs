use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const MODULES: [&str; 4] = ["doc.rs", "manifest.rs", "records.rs", "shared.rs"];

fn model_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("src/model")
}

struct Item {
    module: String,
    name: String,
    signature: String,
    body: String,
}

fn squeeze(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn functions(module: &str, source: &str) -> Vec<Item> {
    let lines: Vec<&str> = source.lines().collect();
    let mut items = Vec::new();
    let mut index = 0;
    while index < lines.len() {
        let line = lines[index];
        let stripped = line.trim_start();
        let indent = line.len() - stripped.len();
        let after_visibility = stripped
            .strip_prefix("pub(crate) ")
            .or_else(|| stripped.strip_prefix("pub(super) "))
            .or_else(|| stripped.strip_prefix("pub "))
            .unwrap_or(stripped);
        if !after_visibility.starts_with("fn ") {
            index += 1;
            continue;
        }
        let mut header = String::from(after_visibility);
        let mut cursor = index;
        while !lines[cursor].trim_end().ends_with('{') && cursor + 1 < lines.len() {
            cursor += 1;
            header.push(' ');
            header.push_str(lines[cursor].trim());
        }
        let closing = format!("{}}}", " ".repeat(indent));
        let mut body = String::new();
        let mut scan = cursor + 1;
        while scan < lines.len() && lines[scan] != closing {
            body.push_str(lines[scan]);
            body.push('\n');
            scan += 1;
        }
        let name = after_visibility
            .trim_start_matches("fn ")
            .split(['(', '<'])
            .next()
            .unwrap_or_default()
            .to_string();
        items.push(Item {
            module: module.to_string(),
            name,
            signature: squeeze(header.trim_end_matches('{')),
            body: squeeze(&body),
        });
        index = scan + 1;
    }
    items
}

fn collect() -> Vec<Item> {
    let dir = model_dir();
    let mut items = Vec::new();
    for module in MODULES {
        let source = std::fs::read_to_string(dir.join(module))
            .unwrap_or_else(|error| panic!("{module} is readable: {error}"));
        items.extend(functions(module, &source));
    }
    items
}

#[test]
fn no_helper_is_defined_in_two_model_modules() {
    let items = collect();
    assert!(items.len() > 100, "the parser found {} items", items.len());
    let mut by_identity: BTreeMap<(&str, &str), Vec<&str>> = BTreeMap::new();
    for item in &items {
        by_identity
            .entry((item.name.as_str(), item.signature.as_str()))
            .or_default()
            .push(item.module.as_str());
    }
    let clashes: Vec<String> = by_identity
        .iter()
        .filter(|(_, modules)| modules.len() > 1)
        .map(|((name, _), modules)| format!("{name} in {modules:?}"))
        .collect();
    assert!(clashes.is_empty(), "same name and signature: {clashes:?}");
}

#[test]
fn no_body_is_copied_between_model_modules() {
    let items = collect();
    let mut by_body: BTreeMap<&str, Vec<(&str, &str)>> = BTreeMap::new();
    for item in &items {
        if item.body.len() < 40 {
            continue;
        }
        by_body
            .entry(item.body.as_str())
            .or_default()
            .push((item.module.as_str(), item.name.as_str()));
    }
    let copies: Vec<String> = by_body
        .values()
        .filter(|places| {
            places
                .iter()
                .map(|(module, _)| *module)
                .collect::<std::collections::BTreeSet<_>>()
                .len()
                > 1
        })
        .map(|places| format!("{places:?}"))
        .collect();
    assert!(
        copies.is_empty(),
        "identical bodies across modules: {copies:?}"
    );
}
