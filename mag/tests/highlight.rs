use mag::highlight;
use std::collections::BTreeSet;
use std::path::PathBuf;

fn repo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn colour_rules() -> Vec<(BTreeSet<String>, String)> {
    let css = std::fs::read_to_string(repo().join("mag/tests/code-inks.css")).unwrap();
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
    assert!(highlight::spans("x := 1", "go").is_err());
    let html_body = "GET / HTTP/1.1\nContent-Type: text/html\n\n<p>";
    assert!(highlight::spans(html_body, "http").is_err());
}

#[test]
fn python_fstring_and_keywords() {
    expect(
        "def f(x):\n    return f\"{x}\"\n",
        "python",
        &[
            ("def", "k"),
            (" ", "w"),
            ("f", "nf"),
            ("(", "p"),
            ("x", "n"),
            ("):", "p"),
            ("\n", "w"),
            ("    ", ""),
            ("return", "k"),
            (" ", ""),
            ("f", "sa"),
            ("\"", "s2"),
            ("{", "si"),
            ("x", "n"),
            ("}", "si"),
            ("\"", "s2"),
            ("\n", "w"),
        ],
    );
}

#[test]
fn c_standard_types_become_keyword_types() {
    expect(
        "size_t n = 0;",
        "c",
        &[
            ("size_t", "kt"),
            (" ", "w"),
            ("n", "n"),
            (" ", "w"),
            ("=", "o"),
            (" ", "w"),
            ("0", "mi"),
            (";", "p"),
        ],
    );
}

#[test]
fn http_body_is_lexed_by_its_content_type() {
    expect(
        "GET / HTTP/1.1\nContent-Type: application/json\n\n[1]",
        "http",
        &[
            ("GET", "nf"),
            (" ", ""),
            ("/", "nn"),
            (" ", ""),
            ("HTTP", "kr"),
            ("/", "o"),
            ("1.1", "m"),
            ("\n", ""),
            ("Content-Type", "na"),
            (":", "o"),
            (" ", ""),
            ("application/json", "l"),
            ("\n\n", ""),
            ("[", "p"),
            ("1", "mi"),
            ("]", "p"),
        ],
    );
}

#[test]
fn a_jsonc_fence_is_coloured_by_the_json_lexer() {
    let code = "{\n  // comment\n  \"a\": 1\n}\n";
    assert_eq!(highlight::language(code, "jsonc"), "json");
    assert!(highlight::spans(code, highlight::language(code, "JSONC"))
        .unwrap()
        .is_some());
}
