use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

const ALLOWED: [(&str, &str, &str); 22] = [
    (
        "cover/outline.rs",
        "move_to",
        "ttf_parser::OutlineBuilder trait-required name on a distinct type",
    ),
    (
        "parity/streams.rs",
        "move_to",
        "ttf_parser::OutlineBuilder trait-required name on a distinct type",
    ),
    (
        "cover/outline.rs",
        "line_to",
        "ttf_parser::OutlineBuilder trait-required name on a distinct type",
    ),
    (
        "parity/streams.rs",
        "line_to",
        "ttf_parser::OutlineBuilder trait-required name on a distinct type",
    ),
    (
        "cover/outline.rs",
        "close",
        "ttf_parser::OutlineBuilder trait-required name on a distinct type",
    ),
    (
        "parity/streams.rs",
        "close",
        "ttf_parser::OutlineBuilder trait-required name on a distinct type",
    ),
    (
        "cover/outline.rs",
        "new",
        "constructor convention on a distinct type",
    ),
    (
        "parity/streams.rs",
        "new",
        "constructor convention on a distinct type",
    ),
    (
        "parity/display.rs",
        "deref",
        "genuine duplicate of parity/streams.rs resolve, renamed; WP-0.2h owns both",
    ),
    (
        "parity/streams.rs",
        "resolve",
        "genuine duplicate of parity/display.rs deref, renamed; WP-0.2h owns both",
    ),
    (
        "caller.rs",
        "drop",
        "Drop::drop is a trait-required name; the bodies differ",
    ),
    (
        "capture.rs",
        "drop",
        "Drop::drop is a trait-required name; the bodies differ",
    ),
    (
        "art.rs",
        "read",
        "genuine duplicate of a one-line fs helper, owned by no Phase 5 WP",
    ),
    (
        "plan_cmd.rs",
        "read",
        "genuine duplicate of a one-line fs helper, owned by no Phase 5 WP",
    ),
    (
        "produce.rs",
        "read",
        "genuine duplicate of a one-line fs helper, owned by no Phase 5 WP",
    ),
    (
        "translate.rs",
        "read",
        "genuine duplicate of a one-line fs helper, owned by no Phase 5 WP",
    ),
    (
        "art.rs",
        "prompts_path",
        "DRIFTED copy: art.rs lacks produce.rs's installed-prompts fallback",
    ),
    (
        "produce.rs",
        "prompts_path",
        "DRIFTED copy: art.rs lacks produce.rs's installed-prompts fallback",
    ),
    (
        "art.rs",
        "resolve_edition_dir",
        "genuine duplicate of render.rs, differing only in local names",
    ),
    (
        "render.rs",
        "resolve_edition_dir",
        "genuine duplicate of art.rs, differing only in local names",
    ),
    (
        "parity/report.rs",
        "esc",
        "genuine duplicate of print_cmd.rs escape_text, renamed",
    ),
    (
        "print_cmd.rs",
        "escape_text",
        "genuine duplicate of parity/report.rs esc, renamed",
    ),
];

fn source_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("src")
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

fn modules(dir: &Path, prefix: &str, found: &mut Vec<(String, String)>) {
    let mut entries: Vec<PathBuf> = std::fs::read_dir(dir)
        .unwrap_or_else(|error| panic!("{} is readable: {error}", dir.display()))
        .map(|entry| entry.expect("directory entry is readable").path())
        .collect();
    entries.sort();
    for path in entries {
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .expect("entry has a name")
            .to_string();
        if path.is_dir() {
            modules(&path, &format!("{prefix}{name}/"), found);
        } else if name.ends_with(".rs") {
            let source = std::fs::read_to_string(&path)
                .unwrap_or_else(|error| panic!("{} is readable: {error}", path.display()));
            found.push((format!("{prefix}{name}"), source));
        }
    }
}

fn collect() -> Vec<Item> {
    let mut sources = Vec::new();
    modules(&source_dir(), "", &mut sources);
    let mut items = Vec::new();
    for (module, source) in &sources {
        items.extend(functions(module, source));
    }
    items
}

fn exempt(places: &[(&str, &str)]) -> bool {
    places.iter().all(|(module, name)| {
        ALLOWED.iter().any(|(allowed_module, allowed_name, _)| {
            allowed_module == module && allowed_name == name
        })
    })
}

#[test]
fn no_helper_is_defined_in_two_modules() {
    let items = collect();
    assert!(items.len() > 400, "the parser found {} items", items.len());
    let mut by_identity: BTreeMap<(&str, &str), Vec<(&str, &str)>> = BTreeMap::new();
    for item in &items {
        by_identity
            .entry((item.name.as_str(), item.signature.as_str()))
            .or_default()
            .push((item.module.as_str(), item.name.as_str()));
    }
    let clashes: Vec<String> = by_identity
        .iter()
        .filter(|(_, places)| {
            places
                .iter()
                .map(|(module, _)| *module)
                .collect::<BTreeSet<_>>()
                .len()
                > 1
                && !exempt(places)
        })
        .map(|((name, _), places)| format!("{name} in {places:?}"))
        .collect();
    assert!(clashes.is_empty(), "same name and signature: {clashes:?}");
}

#[test]
fn no_body_is_copied_between_modules() {
    let items = collect();
    let mut by_body: BTreeMap<&str, Vec<(&str, &str)>> = BTreeMap::new();
    for item in &items {
        if item.body.is_empty() {
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
            let modules: BTreeSet<&str> = places.iter().map(|(module, _)| *module).collect();
            modules.len() > 1 && !exempt(places)
        })
        .map(|places| format!("{places:?}"))
        .collect();
    assert!(
        copies.is_empty(),
        "identical bodies across modules: {copies:?}"
    );
}
