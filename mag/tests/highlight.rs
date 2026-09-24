#[path = "../src/highlight/mod.rs"]
#[allow(dead_code)]
mod highlight;

use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;
use std::process::Command;

fn repo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn uv(script: &str) -> String {
    let out = Command::new("uv")
        .args(["run", "--quiet", "python", script, "."])
        .current_dir(repo())
        .output()
        .expect("uv runs");
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8(out.stdout).unwrap()
}

fn colour_rules() -> Vec<(BTreeSet<String>, String)> {
    let css =
        std::fs::read_to_string(repo().join("src/magazine/assets/weasyprint-a5.css")).unwrap();
    let rule = regex::Regex::new(r"(?m)^(pre code \.[^{]+)\{\s*color:\s*([^;]+);").unwrap();
    rule.captures_iter(&css)
        .map(|c| {
            let classes = c[1]
                .split(',')
                .map(|s| s.trim().trim_start_matches("pre code .").to_owned());
            (classes.collect(), c[2].trim().to_owned())
        })
        .collect()
}

fn colour(rules: &[(BTreeSet<String>, String)], class: &str) -> String {
    let classes: BTreeSet<&str> = class.split_whitespace().collect();
    let hit = rules
        .iter()
        .rev()
        .find(|(set, _)| set.iter().any(|c| classes.contains(c.as_str())));
    hit.map_or("inherit".into(), |(_, colour)| colour.clone())
}

fn colours(
    rules: &[(BTreeSet<String>, String)],
    spans: &[(String, String)],
) -> Vec<(char, String)> {
    let per_char = spans
        .iter()
        .flat_map(|(text, class)| text.chars().map(move |c| (c, class)));
    per_char
        .filter(|(c, _)| *c != '\n')
        .map(|(c, class)| (c, colour(rules, class)))
        .collect()
}

fn pairs(value: &Value) -> Vec<(String, String)> {
    let rows = value.as_array().unwrap().iter();
    rows.map(|p| {
        (
            p[0].as_str().unwrap().to_owned(),
            p[1].as_str().unwrap().to_owned(),
        )
    })
    .collect()
}

#[test]
fn tables_are_generated_from_the_locked_pygments() {
    let fresh = uv("mag/tests/highlight_tables.py");
    let committed = std::fs::read_to_string(repo().join("mag/src/highlight/tables.json")).unwrap();
    assert!(
        fresh == committed,
        "regenerate mag/src/highlight/tables.json"
    );
}

#[test]
fn print_colours_group_the_token_classes_into_seven_inks() {
    let rules = colour_rules();
    let inks: BTreeSet<&str> = rules.iter().map(|(_, c)| c.as_str()).collect();
    assert_eq!(rules.iter().map(|(s, _)| s.len()).sum::<usize>(), 41);
    assert_eq!(inks.len(), 7);
    assert_eq!(colour(&rules, "nb"), colour(&rules, "nf"));
    assert_eq!(colour(&rules, "p p-Indicator"), "inherit");
    assert_eq!(colour(&rules, "sc"), "inherit");
    assert_eq!(colour(&rules, "kt"), "rgb(25% 10% 43%)");
}

#[test]
fn every_corpus_block_matches_pygments() {
    let rules = colour_rules();
    let corpus: Vec<Value> = serde_json::from_str(&uv("mag/tests/highlight_corpus.py")).unwrap();
    let mut stats: BTreeMap<String, (usize, usize)> = BTreeMap::new();
    let (mut spans_total, mut classes, mut refused) = (0, BTreeSet::new(), Vec::new());
    for block in &corpus {
        let (code, language) = (
            block["code"].as_str().unwrap(),
            block["language"].as_str().unwrap(),
        );
        let files = &block["files"];
        let entry = stats.entry(language.to_owned()).or_default();
        entry.0 += 1;
        let spans = match highlight::spans(code, language) {
            Err(e) => {
                assert!(
                    block["scratch"].as_bool().unwrap(),
                    "{language} refused in {files}: {e}"
                );
                assert!(
                    !block["tokens"].is_null(),
                    "refused a language pygments lacks"
                );
                refused.push(language.to_owned());
                continue;
            }
            Ok(spans) => spans,
        };
        assert_eq!(
            spans.is_none(),
            block["tokens"].is_null(),
            "fallback for {language:?}"
        );
        let html = highlight::html(code, language).unwrap();
        assert_eq!(
            html,
            block["html"].as_str().unwrap(),
            "{language} html in {files}"
        );
        let Some(spans) = spans else { continue };
        let oracle = pairs(&block["tokens"]);
        assert_eq!(
            colours(&rules, &spans),
            colours(&rules, &oracle),
            "{language} colours in {files}"
        );
        entry.1 += html.matches("<span class=").count();
        spans_total += html.matches("<span class=").count();
        classes.extend(
            spans
                .iter()
                .map(|(_, c)| c.clone())
                .filter(|c| !c.is_empty()),
        );
    }
    eprintln!(
        "blocks {} spans {spans_total} classes {}",
        corpus.len(),
        classes.len()
    );
    eprintln!("per language (blocks, spans) {stats:?}");
    eprintln!("refused (scratch only) {refused:?}");
    eprintln!("classes {classes:?}");
}

fn classes(code: &str, language: &str) -> Vec<(String, String)> {
    highlight::spans(code, language).unwrap().unwrap()
}

fn expect(code: &str, language: &str, want: &[(&str, &str)]) {
    let want: Vec<(String, String)> = want
        .iter()
        .map(|(t, c)| (t.to_string(), c.to_string()))
        .collect();
    assert_eq!(classes(code, language), want, "{language}: {code:?}");
}

#[test]
fn typescript_declarations() {
    expect(
        "const n: number = 0x1F; // done\n",
        "ts",
        &[
            ("const", "kd"),
            (" ", "w"),
            ("n", "nx"),
            (":", "o"),
            (" ", "w"),
            ("number", "kt"),
            (" ", "w"),
            ("=", "o"),
            (" ", "w"),
            ("0x1F", "mh"),
            (";", "p"),
            (" ", "w"),
            ("// done", "c1"),
            ("\n", "w"),
        ],
    );
}

#[test]
fn javascript_template_string() {
    expect(
        "f(`a${b}`)",
        "js",
        &[
            ("f", "nx"),
            ("(", "p"),
            ("`a", "sb"),
            ("${", "si"),
            ("b", "nx"),
            ("}", "si"),
            ("`", "sb"),
            (")", "p"),
        ],
    );
}

#[test]
fn bash_command_line() {
    expect(
        "echo \"$HOME\" | wc -l\n",
        "sh",
        &[
            ("echo", "nb"),
            (" ", "w"),
            ("\"", "s2"),
            ("$HOME", "nv"),
            ("\"", "s2"),
            (" ", "w"),
            ("|", "p"),
            (" ", "w"),
            ("wc", ""),
            (" ", "w"),
            ("-l", ""),
            ("\n", "w"),
        ],
    );
}

#[test]
fn toml_table_and_key() {
    expect(
        "[a]\nb = \"c\"\n",
        "toml",
        &[
            ("[a]", "k"),
            ("\n", "w"),
            ("b", "n"),
            (" ", "w"),
            ("=", "o"),
            (" ", "w"),
            ("\"c\"", "s2"),
            ("\n", "w"),
        ],
    );
}

#[test]
fn rust_function() {
    expect(
        "fn main() { 1u8 }",
        "rust",
        &[
            ("fn", "k"),
            (" ", "w"),
            ("main", "nf"),
            ("()", "p"),
            (" ", "w"),
            ("{", "p"),
            (" ", "w"),
            ("1", "mi"),
            ("u8", "k"),
            (" ", "w"),
            ("}", "p"),
        ],
    );
}

#[test]
fn sql_is_case_insensitive() {
    expect(
        "select 1 FROM t;",
        "sql",
        &[
            ("select", "k"),
            (" ", "w"),
            ("1", "mi"),
            (" ", "w"),
            ("FROM", "k"),
            (" ", "w"),
            ("t", "n"),
            (";", "p"),
        ],
    );
}

#[test]
fn json_keys_become_tags() {
    expect(
        "{\"a\": [1.5, true], \"b\" x}",
        "json",
        &[
            ("{", "p"),
            ("\"a\"", "nt"),
            (":", "p"),
            (" ", "w"),
            ("[", "p"),
            ("1.5", "mf"),
            (",", "p"),
            (" ", "w"),
            ("true", "kc"),
            ("],", "p"),
            (" ", "w"),
            ("\"b\"", "s2"),
            (" ", "w"),
            ("x", "err"),
            ("}", "p"),
        ],
    );
}

#[test]
fn yaml_mapping() {
    expect(
        "a:\n  - b # c\n",
        "yaml",
        &[
            ("a", "nt"),
            (":", "p"),
            ("\n  ", "w"),
            ("-", "p p-Indicator"),
            (" ", "w"),
            ("b", "l l-Scalar l-Scalar-Plain"),
            (" ", "w"),
            ("# c", "c1"),
            ("\n", "w"),
        ],
    );
}

#[test]
fn unknown_languages_fall_back_and_unimplemented_ones_refuse() {
    assert_eq!(highlight::spans("x", "jsonc").unwrap(), None);
    assert_eq!(highlight::spans("x", "").unwrap(), None);
    assert_eq!(highlight::html("a < b\n", "txt").unwrap(), "a &lt; b\n");
    assert_eq!(highlight::html("a < b\n", "TEXT").unwrap(), "a &lt; b");
    assert!(highlight::spans("x = 1", "python").is_err());
}
