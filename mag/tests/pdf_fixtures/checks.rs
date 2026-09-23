use regex::Regex;
use serde::Deserialize;
use std::path::Path;
use std::sync::LazyLock;

#[derive(Deserialize)]
pub struct Review {
    pub at: String,
    pub pypdf: String,
    pub poppler: String,
    pub truth: String,
}

#[derive(Deserialize)]
pub struct Spec {
    pub source: String,
    pub retrieved: String,
    pub sha256: String,
    pub producer: String,
    pub shape: String,
    #[serde(default)]
    pub line_end_hyphens: Vec<String>,
    #[serde(default)]
    pub real_hyphens: Vec<String>,
    #[serde(default)]
    pub absent: Vec<String>,
    pub order: Vec<Vec<String>>,
    pub review: Vec<Review>,
}

pub struct Fixture {
    pub name: String,
    pub spec: Spec,
    pub truth: String,
    pub passages: Vec<String>,
    pub code: Vec<Vec<String>>,
}

pub type Verdicts = Vec<(String, bool)>;

static HYPHEN_BREAK: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(\w)([-\x{2013}\x{2014}]) ").unwrap());

pub fn load(dir: &Path) -> Fixture {
    let truth = std::fs::read_to_string(dir.join("truth.md")).expect("truth.md is readable");
    let spec = std::fs::read_to_string(dir.join("spec.yaml")).expect("spec.yaml is readable");
    let (passages, code) = blocks(&truth);
    Fixture {
        name: dir.file_name().unwrap().to_string_lossy().into_owned(),
        spec: serde_yaml::from_str(&spec).expect("spec.yaml parses"),
        truth,
        passages,
        code,
    }
}

fn blocks(truth: &str) -> (Vec<String>, Vec<Vec<String>>) {
    let (mut passages, mut code, mut para) = (Vec::new(), Vec::new(), Vec::<&str>::new());
    let mut fence: Option<Vec<String>> = None;
    for line in truth.lines() {
        match (&mut fence, line.starts_with("```")) {
            (Some(_), true) => code.push(fence.take().unwrap()),
            (Some(block), false) => block.push(line.to_string()),
            (None, true) => fence = Some(Vec::new()),
            (None, false) if line.trim().is_empty() => flush(&mut para, &mut passages),
            (None, false) => para.push(line),
        }
    }
    flush(&mut para, &mut passages);
    (passages, code)
}

fn flush(para: &mut Vec<&str>, passages: &mut Vec<String>) {
    if !para.is_empty() {
        passages.push(norm(&para.join(" ")));
        para.clear();
    }
}

pub fn norm(text: &str) -> String {
    let spaced = text.split_whitespace().collect::<Vec<_>>().join(" ");
    HYPHEN_BREAK.replace_all(&spaced, "$1$2").into_owned()
}

pub fn verdicts(fixture: &Fixture, output: &str) -> Verdicts {
    let flat = norm(output);
    let mut out = Verdicts::new();
    for (i, p) in fixture.passages.iter().enumerate() {
        out.push((
            format!("passage:{i}"),
            flat.matches(p.as_str()).count() == 1,
        ));
    }
    for (g, anchors) in fixture.spec.order.iter().enumerate() {
        for (i, pair) in anchors.windows(2).enumerate() {
            let (a, b) = (flat.find(&norm(&pair[0])), flat.find(&norm(&pair[1])));
            out.push((
                format!("order:{g}.{i}"),
                matches!((a, b), (Some(a), Some(b)) if a < b),
            ));
        }
    }
    let lines: Vec<&str> = output.split(['\n', '\x0c']).map(str::trim_end).collect();
    for (i, block) in fixture.code.iter().enumerate() {
        out.push((format!("code:{i}"), code_text(block, &lines)));
        out.push((format!("code-exact:{i}"), code_exact(block, &lines)));
    }
    for (i, h) in fixture.spec.line_end_hyphens.iter().enumerate() {
        out.push((
            format!("hyphen:{i}"),
            flat.contains(&norm(&h.replace('|', ""))),
        ));
    }
    for (i, h) in fixture.spec.real_hyphens.iter().enumerate() {
        out.push((
            format!("real-hyphen:{i}"),
            flat.contains(&norm(&h.replace('|', ""))),
        ));
    }
    for (i, a) in fixture.spec.absent.iter().enumerate() {
        out.push((format!("absent:{i}"), !output.contains(a.as_str())));
    }
    out.extend(chars(output));
    out
}

fn code_text(block: &[String], lines: &[&str]) -> bool {
    let want: Vec<&str> = block
        .iter()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect();
    let have: Vec<&str> = lines
        .iter()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect();
    have.windows(want.len()).any(|w| w == want.as_slice())
}

fn code_exact(block: &[String], lines: &[&str]) -> bool {
    lines.windows(block.len()).any(|w| dedent(w) == block)
}

fn dedent(window: &[&str]) -> Vec<String> {
    let indent = |l: &&str| l.len() - l.trim_start_matches(' ').len();
    let cut = window
        .iter()
        .filter(|l| !l.is_empty())
        .map(indent)
        .min()
        .unwrap_or(0);
    window
        .iter()
        .map(|l| l.get(cut..).unwrap_or("").to_string())
        .collect()
}

fn chars(output: &str) -> Verdicts {
    let none = |bad: fn(char) -> bool| !output.chars().any(bad);
    vec![
        (
            "chars:control".into(),
            none(|c| c.is_control() && !matches!(c, '\n' | '\t' | '\r' | '\x0c')),
        ),
        (
            "chars:ligature".into(),
            none(|c| ('\u{FB00}'..='\u{FB06}').contains(&c)),
        ),
        ("chars:replacement".into(), none(|c| c == '\u{FFFD}')),
        ("chars:soft-hyphen".into(), none(|c| c == '\u{AD}')),
    ]
}
