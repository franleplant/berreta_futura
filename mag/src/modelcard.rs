use crate::caller::{Caller, ModelSpec};
use crate::produce::{section, INLINE_PREAMBLE};
use crate::util::{prompts_path, read};
use anyhow::{bail, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::LazyLock;

pub const ART_STYLE: &str = "Collectible-card creature art in the style of a 1970s science-fiction paperback cover: smooth airbrushed gradients, crisp highlights, a little film grain. Subject: ";
pub const ART_FRAME: &str = " Full-bleed, no border, no frame, no text, no letters, no numbers, no logos anywhere in the image. Landscape card art window composition.";
const ADVICE_KEYS: [&str; 3] = ["Use it for", "Start with", "Tip"];
const PRICE_LABELS: [&str; 3] = ["in", "cached", "out"];

static LAUNCH_HINTS: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"(?i)benchmark|SWE-bench|Terminal-Bench|Humanity.s Last Exam|GPQA|OSWorld|ARC-AGI|MMLU",
    )
    .unwrap()
});
static TOKEN_PRICE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\$\d[\d.,]*[^.\n]{0,60}(?:per|/)\s*(?:1\s?M|million)\b[^.\n]{0,20}tokens|per million (?:input |output )?tokens").unwrap()
});
static FACT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\$[\d.,]+|[\d.,]*\d%|\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s?[x×]|\d+(?:\.\d+)? points|\b\d+\.\d+\b").unwrap()
});
static VERSION: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[A-Z][\w-]*[\s\u{2011}-]+v?\d+(?:\.\d+)*").unwrap());
static NAMED: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b(?:GPT|Claude|Opus|Sonnet|Haiku|Fable|Mythos|Gemini|Sol|Astra|Llama|Grok|Muse)[\s\u{2011}-]+\d[\w.]*")
        .unwrap()
});

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Card {
    pub name: String,
    pub model_id: Option<String>,
    pub lab: String,
    pub cost: Vec<Pair<String>>,
    pub type_line: TypeLine,
    pub traits: Vec<String>,
    pub effort: Option<Vec<String>>,
    pub advice: Vec<Row>,
    pub strength: Option<String>,
    pub weakness: Option<String>,
    pub resistance: Option<String>,
    pub benchmark: Option<Benchmark>,
    pub flavor: Option<Flavor>,
    pub released: Option<String>,
    pub art_briefs: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Pair<T> {
    pub label: T,
    pub value: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct TypeLine {
    pub kind: String,
    pub roles: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Row {
    pub key: String,
    pub value: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Benchmark {
    pub name: String,
    pub score: Option<String>,
    pub unit: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Flavor {
    pub quote: String,
    pub who: String,
}

pub(crate) fn squash(text: &str) -> String {
    let text = text
        .replace(['\u{2019}', '\u{2018}'], "'")
        .replace(['\u{201c}', '\u{201d}'], "\"")
        .replace('\u{2011}', "-")
        .replace(['\u{202f}', '\u{a0}'], " ");
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn json_reply<T: for<'de> Deserialize<'de>>(reply: &str) -> Result<T> {
    let body = reply
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();
    Ok(serde_json::from_str(body)?)
}

pub fn looks_like_launch(article: &str) -> bool {
    LAUNCH_HINTS.find_iter(article).count() >= 3 || TOKEN_PRICE.is_match(article)
}

#[derive(Deserialize)]
struct Launch {
    launch: bool,
    model: Option<String>,
    evidence: Option<String>,
}

pub fn parse_launch(reply: &str, article: &str) -> Result<Option<String>> {
    let verdict: Launch = json_reply(reply)?;
    if !verdict.launch {
        return Ok(None);
    }
    let (Some(model), Some(evidence)) = (verdict.model, verdict.evidence) else {
        bail!("a launch needs both model and evidence");
    };
    let page = squash(article);
    for (what, text) in [("model", &model), ("evidence", &evidence)] {
        if !page.contains(&squash(text)) {
            bail!("the {what} {text:?} is not on the page; copy it character for character");
        }
    }
    Ok(Some(model))
}

pub fn detect_launch(caller: &Caller, label: &str, article: &str) -> Result<Option<String>> {
    if !looks_like_launch(article) {
        return Ok(None);
    }
    let prompt = format!(
        "{}\n{article}",
        read(&prompts_path("model-card-detect.md"))?
    );
    caller.call_with_parse(label, &ModelSpec::parse("sonnet")?, &prompt, |reply| {
        parse_launch(reply, article)
    })
}

fn strip_versions(text: &str) -> String {
    let mut out = String::new();
    let mut last = 0;
    for m in VERSION.find_iter(text) {
        let rest = &text[m.end()..];
        if rest.starts_with(['%', ',', 'x', '\u{d7}'])
            || rest.starts_with(" points")
            || rest.starts_with(" times")
        {
            continue;
        }
        out.push_str(&text[last..m.start()]);
        last = m.end();
    }
    out + &text[last..]
}

fn facts(text: &str) -> Vec<String> {
    let stripped = strip_versions(text);
    FACT.find_iter(&stripped)
        .filter(|m| {
            !stripped[m.end()..]
                .starts_with(|c: char| c.is_alphanumeric() || c == '.' || c == '-' || c == '_')
        })
        .map(|m| m.as_str().trim().to_string())
        .collect()
}

fn slots(card: &Card) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = [
        ("strength", &card.strength),
        ("weakness", &card.weakness),
        ("resistance", &card.resistance),
    ]
    .into_iter()
    .filter_map(|(k, v)| v.as_ref().map(|v| (k.to_string(), v.clone())))
    .collect();
    out.extend(
        card.traits
            .iter()
            .enumerate()
            .map(|(i, t)| (format!("trait {}", i + 1), t.clone())),
    );
    out.extend(
        card.advice
            .iter()
            .map(|r| (format!("advice {}", r.key), r.value.clone())),
    );
    if let Some(b) = &card.benchmark {
        let unit = if b.unit == "%" { "%" } else { "" };
        out.push((
            "benchmark".into(),
            format!("{} {}{unit}", b.name, b.score.clone().unwrap_or_default()),
        ));
    }
    out.push((
        "cost".into(),
        card.cost
            .iter()
            .map(|p| p.value.as_str())
            .collect::<Vec<_>>()
            .join(" "),
    ));
    out
}

fn over(errs: &mut Vec<String>, what: &str, text: &str, limit: usize) {
    if text.chars().count() > limit {
        errs.push(format!(
            "{what} is {} characters, over {limit}",
            text.chars().count()
        ));
    }
}

pub fn shape_errors(card: &Card) -> Vec<String> {
    let mut errs = Vec::new();
    let labels: Vec<&str> = card.cost.iter().map(|p| p.label.as_str()).collect();
    if labels.iter().any(|l| !PRICE_LABELS.contains(l))
        || !labels.windows(2).all(|w| {
            PRICE_LABELS.iter().position(|l| *l == w[0])
                < PRICE_LABELS.iter().position(|l| *l == w[1])
        })
    {
        errs.push("cost labels must be in, cached, out, in that order".into());
    }
    if !(2..=3).contains(&card.traits.len()) {
        errs.push("traits must be two or three".into());
    }
    for (i, t) in card.traits.iter().enumerate() {
        over(&mut errs, &format!("trait {}", i + 1), t, 90);
        if t.contains('$') {
            errs.push(format!("trait {} names a price", i + 1));
        }
    }
    if card
        .effort
        .as_ref()
        .is_some_and(|e| e.iter().any(|l| l.chars().count() > 12 || l.contains('(')))
    {
        errs.push("effort is a plain list of level names, no caveats".into());
    }
    if !(1..=2).contains(&card.advice.len())
        || card
            .advice
            .iter()
            .any(|r| !ADVICE_KEYS.contains(&r.key.as_str()))
    {
        errs.push(format!(
            "advice must be one or two rows keyed from {ADVICE_KEYS:?}"
        ));
    }
    for r in &card.advice {
        over(&mut errs, &format!("advice {}", r.key), &r.value, 80);
    }
    for (k, v) in [
        ("strength", &card.strength),
        ("weakness", &card.weakness),
        ("resistance", &card.resistance),
    ] {
        if let Some(v) = v {
            over(&mut errs, k, v, 55);
        }
    }
    if card
        .strength
        .as_ref()
        .is_some_and(|s| s.chars().any(|c| c.is_ascii_digit()))
    {
        errs.push("strength is an area of work, no numbers".into());
    }
    if let Some(b) = &card.benchmark {
        over(&mut errs, "benchmark name", &b.name, 22);
        if !["%", "Elo", ""].contains(&b.unit.as_str()) {
            errs.push("benchmark unit must be %, Elo, or empty".into());
        }
        if b.score.is_none() {
            errs.push("a benchmark with no score must be null".into());
        }
    }
    if card.art_briefs.len() != 2 {
        errs.push("art_briefs must be two".into());
    }
    let first_name = card
        .name
        .split_whitespace()
        .next()
        .unwrap_or_default()
        .to_lowercase();
    for (i, brief) in card.art_briefs.iter().enumerate() {
        if brief.split_whitespace().count() > 90 {
            errs.push(format!("art brief {} over 90 words", i + 1));
        }
        let lower = brief.to_lowercase();
        if [card.lab.to_lowercase(), first_name.clone()]
            .iter()
            .any(|w| !w.is_empty() && lower.contains(w.as_str()))
        {
            errs.push(format!("art brief {} names the lab or the model", i + 1));
        }
    }
    let mut unquoted = card.clone();
    unquoted.flavor = None;
    if serde_json::to_string(&unquoted)
        .unwrap_or_default()
        .contains('\u{2014}')
    {
        errs.push("em dash outside the flavor quote".into());
    }
    errs
}

pub fn card_errors(card: &Card, source: &str) -> Vec<String> {
    let mut errs = shape_errors(card);
    let page = squash(source);
    let present = |f: &str| {
        page.replace('×', "x").contains(&f.replace('×', "x"))
            || page.contains(f.trim_end_matches(['x', '×', ' ']))
    };
    let mut seen: HashMap<String, String> = HashMap::new();
    let mut names: HashMap<String, String> = HashMap::new();
    for (slot, text) in slots(card) {
        for fact in facts(&text) {
            if !present(&fact) {
                errs.push(format!("{slot}: '{fact}' does not appear in the sources"));
            }
            match seen.get(&fact) {
                Some(first) if *first != slot => errs.push(format!(
                    "'{fact}' appears in both {first} and {slot}; each fact once"
                )),
                _ => {
                    seen.insert(fact, slot.clone());
                }
            }
        }
        for name in NAMED.find_iter(&text).map(|m| m.as_str().to_string()) {
            match names.get(&name) {
                Some(first) if *first != slot => errs.push(format!(
                    "'{name}' appears in both {first} and {slot}; each fact once"
                )),
                _ => {
                    names.insert(name, slot.clone());
                }
            }
        }
    }
    if let Some(score) = card.benchmark.as_ref().and_then(|b| b.score.as_ref()) {
        if !page.contains(score.as_str()) {
            errs.push(format!(
                "benchmark score '{score}' does not appear in the sources"
            ));
        }
    }
    if let Some(id) = &card.model_id {
        if !page.contains(&squash(id)) {
            errs.push(format!("model_id '{id}' does not appear in the sources"));
        }
    }
    errs.extend(art_errors(card));
    if let Some(date) = card.released.as_deref().filter(|d| !date_on_page(d, &page)) {
        errs.push(format!("released '{date}' is not a date the sources print"));
    }
    if let Some(f) = &card.flavor {
        if !page.contains(squash(&f.quote).trim_end_matches('.')) {
            errs.push("flavor quote is not a verbatim run of the sources".into());
        }
        over(&mut errs, "flavor quote", &f.quote, 120);
    }
    errs
}

const MONTHS: [&str; 12] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

fn date_on_page(date: &str, page: &str) -> bool {
    let parts: Vec<usize> = date.split('-').filter_map(|p| p.parse().ok()).collect();
    let [year, month, day] = parts[..] else {
        return false;
    };
    let Some(name) = MONTHS.get(month.wrapping_sub(1)) else {
        return false;
    };
    [
        date.to_string(),
        format!("{name} {day}, {year}"),
        format!("{} {day}, {year}", &name[..3]),
        format!("{}. {day}, {year}", &name[..3]),
        format!("{day} {name} {year}"),
    ]
    .iter()
    .any(|form| page.contains(form.as_str()))
}

static NOT_A_CHARACTER: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\b(?:tower|building|house|castle|city|ship|boat|vehicle|car|tree|garden|lantern|lamp|machine|engine|factory)s?\b").unwrap()
});
static MANY_ARMED: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)\b(?:many|multi|four|six|eight)[- ]armed\b").unwrap());

fn art_errors(card: &Card) -> Vec<String> {
    let mut errs = Vec::new();
    for (i, brief) in card.art_briefs.iter().enumerate() {
        let subject = brief.split([',', ':', ';']).next().unwrap_or_default();
        if let Some(word) = NOT_A_CHARACTER.find(subject) {
            errs.push(format!("art brief {}: the subject is a {}, not a character; make it a dragon, robot, knight, beast, golem, spirit, or another being with a face", i + 1, word.as_str()));
        }
        if MANY_ARMED.is_match(brief) {
            errs.push(format!("art brief {}: no many-armed figures", i + 1));
        }
    }
    errs
}

pub fn parse_card(reply: &str, source: &str) -> Result<Card> {
    let card: Card = json_reply(reply)?;
    let errs = card_errors(&card, source);
    if !errs.is_empty() {
        bail!("fix every problem:\n- {}", errs.join("\n- "));
    }
    Ok(card)
}

pub fn missing(card: &Card) -> Vec<&'static str> {
    [
        (card.cost.is_empty(), "price"),
        (card.model_id.is_none(), "model id"),
        (card.released.is_none(), "release date"),
        (card.benchmark.is_none(), "benchmark score"),
    ]
    .into_iter()
    .filter_map(|(gap, what)| gap.then_some(what))
    .collect()
}

const LAB_SITES: [(&str, &[&str]); 4] = [
    ("anthropic", &["anthropic.com", "claude.com"]),
    ("openai", &["openai.com"]),
    (
        "google",
        &[
            "google.dev",
            "blog.google",
            "deepmind.google",
            "google.com",
            "googleblog.com",
        ],
    ),
    ("meta", &["meta.com", "llama.com", "facebook.com"]),
];

fn host(url: &str) -> Option<&str> {
    let rest = url.strip_prefix("https://")?;
    let host = rest.split(['/', '?', '#']).next()?;
    Some(host.strip_prefix("www.").unwrap_or(host))
}

pub fn lab_domains(lab: &str, source_url: &str) -> Vec<String> {
    let squashed = lab.to_lowercase().replace(' ', "");
    let mut domains: Vec<String> = LAB_SITES
        .iter()
        .filter(|(key, _)| squashed.contains(key))
        .flat_map(|(_, sites)| sites.iter().map(|s| (*s).to_string()))
        .collect();
    if let Some(h) = host(source_url) {
        let labels: Vec<&str> = h.split('.').collect();
        domains.push(labels[labels.len().saturating_sub(2)..].join("."));
    }
    domains.sort();
    domains.dedup();
    domains
}

#[derive(Deserialize)]
struct Pages {
    urls: Vec<String>,
}

pub fn parse_pages(reply: &str, domains: &[String]) -> Result<Vec<String>> {
    let pages: Pages = json_reply(reply)?;
    if pages.urls.len() > 3 {
        bail!("list at most three pages");
    }
    for url in &pages.urls {
        let Some(h) = host(url) else {
            bail!("{url} is not an https URL");
        };
        if !domains
            .iter()
            .any(|d| h == d || h.ends_with(&format!(".{d}")))
        {
            bail!(
                "{url} is not on the lab's own sites ({}); list only the lab's own pages",
                domains.join(", ")
            );
        }
    }
    Ok(pages.urls)
}

pub fn find_pages(
    caller: &Caller,
    label: &str,
    card: &Card,
    source_url: &str,
) -> Result<Vec<String>> {
    let domains = lab_domains(&card.lab, source_url);
    let prompt = read(&prompts_path("model-card-sources.md"))?
        .replace("{model}", &card.name)
        .replace("{lab}", &card.lab)
        .replace("{missing}", &missing(card).join(", "))
        .replace("{domains}", &domains.join(", "));
    let mut spec = ModelSpec::parse("sonnet")?;
    spec.web = true;
    caller.call_with_parse(label, &spec, &prompt, |reply| parse_pages(reply, &domains))
}

pub fn write_card(caller: &Caller, label: &str, model: &ModelSpec, sources: &str) -> Result<Card> {
    let prompt = format!(
        "{INLINE_PREAMBLE}\n\n{}\n\n{}",
        read(&prompts_path("model-card.md"))?,
        section("sources", sources)
    );
    caller.call_with_parse(label, model, &prompt, |reply| parse_card(reply, sources))
}

#[cfg(test)]
mod tests {
    use super::*;

    const SOURCE: &str = "Introducing Example 2. Today we release Example 2. It costs $8 per million input tokens and $40 per million output tokens. On FrontierCode it scores 49.1%. It answers 30% faster than Example 1. Call it with `example-2`. \u{201c}It found the bug in a day,\u{201d} said Ana, Acme.";

    fn card() -> Card {
        Card {
            name: "Example 2".into(),
            model_id: Some("example-2".into()),
            lab: "Lab".into(),
            cost: vec![
                Pair {
                    label: "in".into(),
                    value: "$8".into(),
                },
                Pair {
                    label: "out".into(),
                    value: "$40".into(),
                },
            ],
            type_line: TypeLine {
                kind: "Frontier Model".into(),
                roles: vec!["Coder".into()],
            },
            traits: vec![
                "Answers 30% faster than Example 1.".into(),
                "Writes code.".into(),
            ],
            effort: None,
            advice: vec![Row {
                key: "Use it for".into(),
                value: "hard bugs".into(),
            }],
            strength: Some("Debugging".into()),
            weakness: None,
            resistance: Some("Blocks misuse".into()),
            benchmark: Some(Benchmark {
                name: "FrontierCode".into(),
                score: Some("49.1".into()),
                unit: "%".into(),
            }),
            flavor: Some(Flavor {
                quote: "It found the bug in a day,".into(),
                who: "Ana, Acme".into(),
            }),
            released: None,
            art_briefs: vec![
                "a calm heron. Background: a sun. Red palette.".into(),
                "a tall figure. Background: sea. Blue palette.".into(),
            ],
        }
    }

    #[test]
    fn a_grounded_card_passes() {
        assert_eq!(card_errors(&card(), SOURCE), Vec::<String>::new());
    }

    #[test]
    fn a_number_missing_from_the_sources_is_refused() {
        let mut c = card();
        c.traits[1] = "Uses 40% fewer tokens.".into();
        assert!(card_errors(&c, SOURCE)
            .iter()
            .any(|e| e.contains("'40%' does not appear")));
    }

    #[test]
    fn a_repeated_fact_is_refused() {
        let mut c = card();
        c.strength = Some("Debugging".into());
        c.advice[0].value = "work that needs $40 answers".into();
        assert!(card_errors(&c, SOURCE)
            .iter()
            .any(|e| e.contains("each fact once")));
    }

    #[test]
    fn a_reworded_quote_is_refused() {
        let mut c = card();
        c.flavor = Some(Flavor {
            quote: "It fixed the bug in a day".into(),
            who: "Ana, Acme".into(),
        });
        assert!(card_errors(&c, SOURCE)
            .iter()
            .any(|e| e.contains("flavor quote")));
    }

    #[test]
    fn found_pages_must_be_on_the_labs_own_sites() {
        let domains = lab_domains("OpenAI", "https://openai.com/index/introducing-gpt-6-2/");
        assert_eq!(domains, vec!["openai.com".to_string()]);
        let ok = r#"{"urls": ["https://platform.openai.com/docs/pricing", "https://www.openai.com/api/pricing/"]}"#;
        assert_eq!(parse_pages(ok, &domains).unwrap().len(), 2);
        assert!(parse_pages(
            r#"{"urls": ["https://techcrunch.com/openai-pricing"]}"#,
            &domains
        )
        .is_err());
        assert!(parse_pages(r#"{"urls": ["http://openai.com/pricing"]}"#, &domains).is_err());
        assert!(
            lab_domains("Google", "https://blog.google/technology/gemini-4/")
                .contains(&"google.dev".to_string())
        );
    }

    #[test]
    fn the_art_is_always_a_character() {
        let mut c = card();
        c.art_briefs[0] = "a walking marble lantern tower full of drawers, in a desert. Background: moons. Red palette.".into();
        assert!(card_errors(&c, SOURCE)
            .iter()
            .any(|e| e.contains("not a character")));
        c.art_briefs[0] = "a brass robot with a kind face, carrying a lamp and a tiny city. Background: sea. Red palette.".into();
        assert!(card_errors(&c, SOURCE).is_empty());
        c.art_briefs[1] = "a four-armed giant made of glass. Background: sea. Blue palette.".into();
        assert!(card_errors(&c, SOURCE)
            .iter()
            .any(|e| e.contains("many-armed")));
    }

    #[test]
    fn a_release_date_must_be_printed_in_the_sources() {
        assert!(date_on_page("2026-11-17", "Published November 17, 2026 by"));
        assert!(date_on_page("2026-11-09", "Nov 9, 2026"));
        assert!(!date_on_page("2026-11-18", "Published November 17, 2026"));
    }

    #[test]
    fn missing_slots_are_named() {
        assert_eq!(missing(&card()), vec!["release date"]);
    }

    #[test]
    fn a_launch_needs_its_evidence_on_the_page() {
        let yes =
            r#"{"launch": true, "model": "Example 2", "evidence": "Today we release Example 2."}"#;
        assert_eq!(parse_launch(yes, SOURCE).unwrap(), Some("Example 2".into()));
        let made_up = r#"{"launch": true, "model": "Example 2", "evidence": "We are thrilled to launch Example 2."}"#;
        assert!(parse_launch(made_up, SOURCE).is_err());
        assert_eq!(
            parse_launch(
                r#"{"launch": false, "model": null, "evidence": null}"#,
                SOURCE
            )
            .unwrap(),
            None
        );
    }

    #[test]
    fn the_prefilter_needs_benchmarks_or_a_token_price() {
        assert!(looks_like_launch(SOURCE));
        assert!(!looks_like_launch("A story about gardening."));
    }

    #[test]
    fn the_card_prompt_has_no_em_dash() {
        let prompt = std::fs::read_to_string(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../prompts/model-card.md"
        ))
        .unwrap();
        assert!(!prompt.contains('\u{2014}'));
    }
}
