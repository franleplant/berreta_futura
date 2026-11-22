use crate::caller::{now_stamp, write_atomic, Caller, ModelSpec};
use crate::typeset::content::{escape_markup, raw_block, string_literal, File, Tree};
use crate::typeset::template;
use crate::typeset::world::Sources;
use crate::util::{parallel, read};
use anyhow::{bail, ensure, Context, Result};
use pulldown_cmark::{Event, Parser, Tag, TagEnd};
use regex::Regex;
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::collections::{BTreeMap, HashMap};
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

const BOOKS_DIR: &str = "books";
const DIGEST_TYP: &str = include_str!("../assets/typeset/book-digest.typ");
const PASSAGE_MIN: usize = 8_000;
const PASSAGE_MAX: usize = 16_000;
const OVERLAP_WORDS: usize = 1_500;
const WORDS_PER_PAGE: usize = 430;
const MAX_PAGES: usize = 20;
const POINTS_PER_PAGE: usize = 7;
const MERGE_GAP: u32 = 2;
const QUOTE_MATCH: f64 = 0.7;
const CHECKED_QUOTE_WORDS: usize = 8;

static GUTENBERG: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?s)\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG[^*]*\*\*\*(.*?)\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG").unwrap()
});
static BROKEN: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(\p{Ll})[-\x{ac}]\n[ \t]*(\p{Ll})").unwrap());
static FOLIO: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^[ \t]*\d{1,4}[ \t]*\n").unwrap());
static CHAPTER: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^\s*(?:#{1,3} |(?:CHAPTER|Chapter|PART|Part|BOOK|Book|LECTURE|Lecture)\b)")
        .unwrap()
});
static BLANKS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\n[ \t]*(?:\n[ \t]*)+").unwrap());
static MARKER: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^[ \t]*<!--([^>]*)-->[ \t]*\n?").unwrap());
static QUOTED: LazyLock<Regex> =
    LazyLock::new(|| Regex::new("\u{201c}([^\u{201d}]+)\u{201d}|\"([^\"\n]+)\"").unwrap());

#[derive(clap::Args)]
pub struct BookArgs {
    #[command(subcommand)]
    cmd: BookCmd,
}

#[derive(clap::Subcommand)]
enum BookCmd {
    #[command(
        about = "Turn one book (PDF, TXT, Markdown, or HTML files, in reading order) into books/<slug>/text.md and record.yaml (no model call)"
    )]
    Ingest {
        #[arg(required = true)]
        files: Vec<PathBuf>,
        #[arg(long)]
        title: String,
        #[arg(long)]
        author: String,
        #[arg(long, help = "Directory name under books/ (default: from the title)")]
        slug: Option<String>,
    },
    #[command(
        about = "Write books/<slug>/digest.md and digest.pdf: every idea of every passage (quote-gated), an outline that accounts for each idea, and the piece that covers every point of it"
    )]
    Distill {
        slug: String,
        #[arg(
            long,
            help = "Target A5 pages (default: one per 7,000 book words, 10 to 20)"
        )]
        pages: Option<usize>,
        #[arg(
            long,
            default_value = "opus",
            help = "Model for the outline and the piece"
        )]
        model: String,
        #[arg(
            long = "read-model",
            default_value = "opus",
            help = "Model that lists each passage's ideas"
        )]
        read_model: String,
        #[arg(
            long,
            help = "Reuse a run directory: stages whose JSON is already there are not called again"
        )]
        resume: Option<PathBuf>,
    },
    #[command(about = "Typeset books/<slug>/digest.md as an A5 PDF again (no model call)")]
    Render { slug: String },
}

#[derive(Serialize, Deserialize)]
struct Record {
    title: String,
    author: String,
    files: Vec<String>,
    words: usize,
    ingested_at: String,
}

#[derive(Serialize, Deserialize, Clone)]
struct Idea {
    #[serde(default)]
    id: String,
    claim: String,
    explanation: String,
    #[serde(default)]
    example: String,
    quote: String,
    weight: String,
}

#[derive(Serialize, Deserialize)]
struct Ideas {
    ideas: Vec<Idea>,
}

#[derive(Serialize, Deserialize)]
struct Outline {
    thesis: String,
    sections: Vec<Section>,
    #[serde(default)]
    dropped: Vec<Dropped>,
}

#[derive(Serialize, Deserialize)]
struct Section {
    heading: String,
    points: Vec<Point>,
}

#[derive(Serialize, Deserialize)]
struct Point {
    ids: Vec<String>,
    gist: String,
}

#[derive(Serialize, Deserialize)]
struct Dropped {
    id: String,
    reason: String,
}

pub fn run(args: &BookArgs) -> Result<i32> {
    match &args.cmd {
        BookCmd::Ingest {
            files,
            title,
            author,
            slug,
        } => ingest(files, title, author, slug.as_deref()),
        BookCmd::Distill {
            slug,
            pages,
            model,
            read_model,
            resume,
        } => distill(
            slug,
            *pages,
            &ModelSpec::parse(model)?,
            &ModelSpec::parse(read_model)?,
            resume.as_deref(),
        ),
        BookCmd::Render { slug } => {
            let dir = book_dir(slug);
            let pages = render(&dir, &load_record(&dir)?)?;
            println!(
                "digest: {} ({pages} pages)",
                dir.join("digest.pdf").display()
            );
            Ok(0)
        }
    }
}

fn book_dir(slug: &str) -> PathBuf {
    Path::new(BOOKS_DIR).join(slug)
}

fn load_record(dir: &Path) -> Result<Record> {
    let path = dir.join("record.yaml");
    serde_norway::from_str(&read(&path)?).with_context(|| format!("parsing {}", path.display()))
}

fn ingest(files: &[PathBuf], title: &str, author: &str, slug: Option<&str>) -> Result<i32> {
    let raw = files
        .iter()
        .map(|f| extract(f))
        .collect::<Result<Vec<_>>>()?
        .join("\n\n");
    let text = normalize(&raw);
    let words = text.split_whitespace().count();
    ensure!(
        words > 2000,
        "the files yield only {words} words; a scanned PDF needs OCR first"
    );
    let slug = slug.map_or_else(|| slugify(title), str::to_string);
    let dir = book_dir(&slug);
    std::fs::create_dir_all(&dir)?;
    write_atomic(dir.join("text.md"), &text)?;
    let record = Record {
        title: title.to_string(),
        author: author.to_string(),
        files: files
            .iter()
            .filter_map(|f| f.file_name())
            .map(|n| n.to_string_lossy().into_owned())
            .collect(),
        words,
        ingested_at: now_stamp(),
    };
    write_atomic(dir.join("record.yaml"), serde_norway::to_string(&record)?)?;
    println!(
        "book: {} ({words} words, {} passages)",
        dir.display(),
        passages(&text).len()
    );
    println!("next: mag book distill {slug}");
    Ok(0)
}

fn extract(file: &Path) -> Result<String> {
    let ext = file
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    match ext.as_str() {
        "pdf" => pdftotext(file),
        "html" | "htm" | "xhtml" => Ok(html_text(&read(file)?)),
        "txt" | "md" => read(file),
        other => bail!(
            "cannot ingest .{other} ({}): give .pdf, .txt, .md, or .html files",
            file.display()
        ),
    }
}

fn pdftotext(file: &Path) -> Result<String> {
    let out = std::process::Command::new("pdftotext")
        .args(["-enc", "UTF-8"])
        .arg(file)
        .arg("-")
        .output()
        .context("running pdftotext (brew install poppler)")?;
    ensure!(
        out.status.success(),
        "pdftotext failed on {}: {}",
        file.display(),
        String::from_utf8_lossy(&out.stderr)
    );
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn html_text(html: &str) -> String {
    let doc = scraper::Html::parse_document(html);
    let blocks = scraper::Selector::parse("h1, h2, h3, h4, p, pre").expect("static selector");
    doc.select(&blocks)
        .filter_map(|e| {
            let mark = match e.value().name() {
                "h1" | "h2" => "# ",
                "h3" | "h4" => "## ",
                _ => "",
            };
            let text = match mark {
                "" => e.text().collect::<String>().trim().to_string(),
                _ => e
                    .text()
                    .flat_map(str::split_whitespace)
                    .collect::<Vec<_>>()
                    .join(" "),
            };
            (!text.is_empty()).then(|| format!("{mark}{text}"))
        })
        .collect::<Vec<_>>()
        .join("\n\n")
}

fn normalize(raw: &str) -> String {
    let body = GUTENBERG
        .captures(raw)
        .and_then(|c| c.get(1))
        .map_or(raw, |m| m.as_str());
    let text = body
        .replace('\r', "")
        .replace('\u{c}', "\n")
        .replace('\u{fb00}', "ff")
        .replace('\u{fb01}', "fi")
        .replace('\u{fb02}', "fl")
        .replace('\u{fb03}', "ffi")
        .replace('\u{fb04}', "ffl");
    let text = BROKEN.replace_all(&text, "$1$2");
    let text = FOLIO.replace_all(&text, "");
    BLANKS.replace_all(&text, "\n\n").trim().to_string() + "\n"
}

fn slugify(title: &str) -> String {
    title
        .to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .collect::<Vec<_>>()
        .join("-")
}

fn size(text: &str) -> usize {
    text.split_whitespace().count()
}

fn passages(text: &str) -> Vec<String> {
    let mut out: Vec<Vec<&str>> = Vec::new();
    let mut current: Vec<&str> = Vec::new();
    let mut carried = 0;
    let mut words = 0;
    let mut last_chapter = None;
    for para in text.split("\n\n").filter(|p| !p.trim().is_empty()) {
        let chapter = opens_chapter(para);
        if words >= PASSAGE_MIN && (chapter || words + size(para) > PASSAGE_MAX) {
            let at = if chapter { None } else { last_chapter };
            let rest = current.split_off(at.unwrap_or(current.len()));
            let full = std::mem::take(&mut current);
            current = if chapter || at.is_some() {
                rest
            } else {
                overlap(&full)
            };
            carried = if at.is_none() && !chapter {
                current.len()
            } else {
                0
            };
            words = current.iter().map(|p| size(p)).sum();
            last_chapter = None;
            out.push(full);
        }
        if chapter && words >= PASSAGE_MIN / 2 {
            last_chapter = Some(current.len());
        }
        current.push(para);
        words += size(para);
    }
    match out.last_mut() {
        Some(last) if words < PASSAGE_MIN / 2 => last.extend(&current[carried..]),
        _ if words > 0 => out.push(current),
        _ => {}
    }
    out.into_iter().map(|p| p.join("\n\n") + "\n").collect()
}

fn opens_chapter(para: &str) -> bool {
    let head = para.trim_start().lines().next().unwrap_or_default();
    head.len() < 100
        && CHAPTER.is_match(head)
        && !matches!(head.trim_start_matches('#').trim(), "Footnotes" | "Notes")
}

fn overlap<'a>(paras: &[&'a str]) -> Vec<&'a str> {
    let mut words = 0;
    let start = paras
        .iter()
        .rposition(|p| {
            words += size(p);
            words >= OVERLAP_WORDS
        })
        .unwrap_or(0);
    paras[start..].to_vec()
}

struct Index(HashMap<u64, Vec<usize>>);

fn words_of(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(str::to_lowercase)
        .collect()
}

fn pair_key(a: &str, b: &str) -> u64 {
    let mut h = DefaultHasher::new();
    (a, b).hash(&mut h);
    h.finish()
}

impl Index {
    fn new(text: &str) -> Self {
        let mut at: HashMap<u64, Vec<usize>> = HashMap::new();
        for (i, p) in words_of(text).windows(2).enumerate() {
            at.entry(pair_key(&p[0], &p[1])).or_default().push(i);
        }
        Self(at)
    }

    fn quotes(&self, quote: &str) -> bool {
        quote
            .split(['\u{2026}', '['])
            .flat_map(|part| part.split("..."))
            .filter(|part| words_of(part).len() >= 5)
            .all(|part| self.score(part) >= QUOTE_MATCH)
    }

    fn score(&self, quote: &str) -> f64 {
        let words = words_of(quote);
        if words.len() < 5 {
            return 0.0;
        }
        let mut votes: HashMap<i64, usize> = HashMap::new();
        for (j, p) in words.windows(2).enumerate() {
            for &i in self.0.get(&pair_key(&p[0], &p[1])).into_iter().flatten() {
                *votes.entry(i as i64 - j as i64).or_default() += 1;
            }
        }
        let best = votes
            .keys()
            .map(|k| (-2..=2).filter_map(|d| votes.get(&(k + d))).sum::<usize>())
            .max()
            .unwrap_or(0);
        (best as f64 / (words.len() - 1) as f64).min(1.0)
    }
}

fn json_reply<T: DeserializeOwned>(reply: &str) -> Result<T> {
    let start = reply.find('{').context("no JSON object in the reply")?;
    let end = reply.rfind('}').context("no JSON object in the reply")?;
    Ok(serde_json::from_str(&reply[start..=end])?)
}

fn cached<T: Serialize + DeserializeOwned>(
    path: &Path,
    make: impl FnOnce() -> Result<T>,
) -> Result<T> {
    if path.exists() {
        return serde_json::from_str(&read(path)?)
            .with_context(|| format!("parsing {}", path.display()));
    }
    let value = make()?;
    write_atomic(path, serde_json::to_string_pretty(&value)? + "\n")?;
    Ok(value)
}

fn prompt(name: &str, vars: &[(&str, String)]) -> Result<String> {
    let mut text = read(&Path::new("prompts").join(name))?;
    for (key, value) in vars {
        text = text.replace(&format!("{{{key}}}"), value);
    }
    Ok(text)
}

fn book_tag(record: &Record) -> String {
    format!("<book>\n{} by {}\n</book>", record.title, record.author)
}

fn distill(
    slug: &str,
    pages: Option<usize>,
    model: &ModelSpec,
    read_model: &ModelSpec,
    resume: Option<&Path>,
) -> Result<i32> {
    let dir = book_dir(slug);
    let record = load_record(&dir)?;
    let text = read(&dir.join("text.md"))?;
    let most = pages.map_or(MAX_PAGES, |p| (p * 13 / 10).min(MAX_PAGES));
    let pages = pages.unwrap_or_else(|| (record.words / 7000).clamp(10, MAX_PAGES));
    let run = resume.map_or_else(|| dir.join("runs").join(now_stamp()), Path::to_path_buf);
    std::fs::create_dir_all(&run)?;
    let caller = Caller::new(&run);
    let ideas = read_book(&caller, read_model, &record, &text, &run)?;
    let outline = cached(&run.join("outline.json"), || {
        collate(&caller, model, &record, &ideas, pages)
    })?;
    let brief = brief(&ideas, &outline);
    write_atomic(run.join("outline.md"), &brief.0)?;
    let digest = write_digest(
        &caller,
        model,
        &record,
        &brief,
        (pages, most),
        &Index::new(&text),
    )?;
    write_atomic(run.join("digest.md"), &digest)?;
    write_atomic(dir.join("digest.md"), &digest)?;
    let printed = render(&dir, &record)?;
    println!(
        "digest: {} ({printed} pages for a {pages}-page target, {} words, {} ideas, {} dropped, {})",
        dir.join("digest.pdf").display(),
        digest.split_whitespace().count(),
        ideas.len(),
        outline.dropped.len(),
        caller.cost_label()
    );
    println!(
        "next: read {} and edit it, then mag book render {slug}",
        dir.join("digest.md").display()
    );
    Ok(0)
}

fn read_book(
    caller: &Caller,
    spec: &ModelSpec,
    record: &Record,
    text: &str,
    run: &Path,
) -> Result<Vec<Idea>> {
    let parts = passages(text);
    let total = parts.len();
    let ask = prompt("book-read.md", &[])?;
    let numbered: Vec<(usize, &String)> =
        parts.iter().enumerate().map(|(i, s)| (i + 1, s)).collect();
    let results = parallel(&numbered, |(n, passage)| {
        cached(&run.join(format!("ideas-{n:02}.json")), || {
            read_passage(caller, spec, record, (*n, total), passage, &ask)
        })
    });
    let mut ideas = Vec::new();
    let mut failed = Vec::new();
    for ((n, _), result) in numbered.iter().zip(results) {
        match result {
            Ok(found) => ideas.extend(found.ideas.into_iter().enumerate().map(|(k, mut idea)| {
                idea.id = format!("{n}.{}", k + 1);
                idea
            })),
            Err(e) => failed.push(format!("passage {n}: {e:#}")),
        }
    }
    ensure!(
        failed.is_empty(),
        "{}\nrerun with --resume {}",
        failed.join("\n"),
        run.display()
    );
    let core = ideas.iter().filter(|i| i.weight == "core").count();
    println!(
        "  {} ideas from {total} passages ({core} core)",
        ideas.len()
    );
    Ok(ideas)
}

fn read_passage(
    caller: &Caller,
    spec: &ModelSpec,
    record: &Record,
    (n, total): (usize, usize),
    passage: &str,
    ask: &str,
) -> Result<Ideas> {
    let index = Index::new(passage);
    let sent = format!(
        "{}\n\n<passage {n} of {total}>\n\n{passage}\n</passage>\n\n{ask}",
        book_tag(record)
    );
    caller.call_with_parse(&format!("read {n}/{total}"), spec, &sent, |reply| {
        let found: Ideas = json_reply(reply)?;
        check_ideas(&found.ideas, &index)?;
        Ok(found)
    })
}

fn check_ideas(ideas: &[Idea], index: &Index) -> Result<()> {
    ensure!(
        ideas
            .iter()
            .all(|i| matches!(i.weight.as_str(), "core" | "supporting")),
        "every weight must be \"core\" or \"supporting\""
    );
    ensure!(
        ideas.iter().all(|i| !i.claim.trim().is_empty()),
        "every idea needs a claim"
    );
    let missing: Vec<String> = ideas
        .iter()
        .filter(|i| index.score(&i.quote) < QUOTE_MATCH)
        .map(|i| format!("{:?}", i.quote))
        .collect();
    ensure!(
        missing.is_empty(),
        "these quotes are not in the passage word for word; copy each one exactly from the text: {}",
        missing.join("; ")
    );
    Ok(())
}

fn collate(
    caller: &Caller,
    spec: &ModelSpec,
    record: &Record,
    ideas: &[Idea],
    pages: usize,
) -> Result<Outline> {
    let lines: Vec<String> = ideas
        .iter()
        .map(|i| format!("[{}] ({}) {}", i.id, i.weight, i.claim))
        .collect();
    let sent = format!(
        "{}\n\n<ideas>\n{}\n</ideas>\n\n{}",
        book_tag(record),
        lines.join("\n"),
        prompt(
            "book-collate.md",
            &[
                ("pages", pages.to_string()),
                ("points", (pages * POINTS_PER_PAGE).to_string()),
            ]
        )?
    );
    caller.call_with_parse("collate", spec, &sent, |reply| {
        let mut plan: Outline = json_reply(reply)?;
        check_outline(&plan, ideas, pages * POINTS_PER_PAGE)?;
        split_apart(&mut plan, ideas);
        Ok(plan)
    })
}

fn check_outline(plan: &Outline, ideas: &[Idea], most: usize) -> Result<()> {
    let weight: HashMap<&str, &str> = ideas
        .iter()
        .map(|i| (i.id.as_str(), i.weight.as_str()))
        .collect();
    let mut seen: BTreeMap<&str, usize> = BTreeMap::new();
    let placed = plan
        .sections
        .iter()
        .flat_map(|s| &s.points)
        .flat_map(|p| &p.ids);
    for id in placed.chain(plan.dropped.iter().map(|d| &d.id)) {
        *seen.entry(id.as_str()).or_default() += 1;
    }
    let list = |ids: Vec<&str>| ids.join(", ");
    let missing: Vec<&str> = ideas
        .iter()
        .map(|i| i.id.as_str())
        .filter(|id| !seen.contains_key(id))
        .collect();
    let unknown: Vec<&str> = seen
        .keys()
        .copied()
        .filter(|id| !weight.contains_key(id))
        .collect();
    let twice: Vec<&str> = seen
        .iter()
        .filter(|(_, n)| **n > 1)
        .map(|(id, _)| *id)
        .collect();
    let core: Vec<&str> = plan
        .dropped
        .iter()
        .map(|d| d.id.as_str())
        .filter(|id| weight.get(id) == Some(&"core"))
        .collect();
    ensure!(
        missing.is_empty(),
        "these ids are in no point and not dropped: {}",
        list(missing)
    );
    let points = plan.sections.iter().map(|s| s.points.len()).sum::<usize>();
    ensure!(
        points <= most,
        "{points} points will not fit the pages; gather related ideas, across chapters too, into at most {most} points"
    );
    ensure!(
        unknown.is_empty(),
        "these ids are not in <ideas>: {}",
        list(unknown)
    );
    ensure!(
        twice.is_empty(),
        "these ids appear more than once: {}",
        list(twice)
    );
    ensure!(
        core.is_empty(),
        "these core ideas were dropped; place them in a point: {}",
        list(core)
    );
    ensure!(
        (3..=12).contains(&plan.sections.len()),
        "give 4 to 10 sections, not {}",
        plan.sections.len()
    );
    Ok(())
}

fn split_apart(plan: &mut Outline, ideas: &[Idea]) {
    let by_id: HashMap<&str, &Idea> = ideas.iter().map(|i| (i.id.as_str(), i)).collect();
    for section in &mut plan.sections {
        section.points = std::mem::take(&mut section.points)
            .into_iter()
            .flat_map(|point| split_point(point, &by_id))
            .collect();
    }
}

fn position(id: &str) -> Option<(u32, u32)> {
    let (s, k) = id.split_once('.')?;
    Some((s.parse().ok()?, k.parse().ok()?))
}

fn split_point(point: Point, by_id: &HashMap<&str, &Idea>) -> Vec<Point> {
    let core = |id: &String| by_id.get(id.as_str()).is_some_and(|i| i.weight == "core");
    let (mut cores, rest): (Vec<String>, Vec<String>) = point.ids.into_iter().partition(core);
    cores.sort_by_key(|id| position(id));
    let mut groups: Vec<Vec<String>> = vec![rest];
    for id in cores {
        let at = position(&id);
        let fits = |group: &Vec<String>| {
            group
                .iter()
                .filter(|m| core(m))
                .all(|m| match (position(m), at) {
                    (Some((s, k)), Some((t, j))) => s != t || j.abs_diff(k) <= MERGE_GAP,
                    _ => true,
                })
        };
        match groups.iter_mut().find(|g| fits(g)) {
            Some(group) => group.push(id),
            None => groups.push(vec![id]),
        }
    }
    groups
        .into_iter()
        .enumerate()
        .map(|(n, ids)| Point {
            gist: match n {
                0 => point.gist.clone(),
                _ => by_id
                    .get(ids[0].as_str())
                    .map_or_else(String::new, |i| i.claim.clone()),
            },
            ids,
        })
        .collect()
}

fn brief(ideas: &[Idea], plan: &Outline) -> (String, usize) {
    let by_id: HashMap<&str, &Idea> = ideas.iter().map(|i| (i.id.as_str(), i)).collect();
    let mut out = format!("Thesis: {}\n", plan.thesis);
    let mut n = 0;
    for section in &plan.sections {
        out.push_str(&format!("\n## {}\n", section.heading));
        for point in &section.points {
            n += 1;
            out.push_str(&format!("\nP{n}. {}\n", point.gist));
            for idea in point.ids.iter().filter_map(|id| by_id.get(id.as_str())) {
                out.push_str(&idea_lines(idea));
            }
        }
    }
    (out, n)
}

fn idea_lines(idea: &Idea) -> String {
    let mut out = format!(
        "  - ({}) {}\n    why: {}\n",
        idea.weight, idea.claim, idea.explanation
    );
    if !idea.example.trim().is_empty() {
        out.push_str(&format!("    example: {}\n", idea.example));
    }
    out.push_str(&format!(
        "    quote: \u{201c}{}\u{201d}\n",
        idea.quote.trim()
    ));
    out
}

fn write_digest(
    caller: &Caller,
    spec: &ModelSpec,
    record: &Record,
    (brief, points): &(String, usize),
    (pages, most): (usize, usize),
    book: &Index,
) -> Result<String> {
    let words = pages * WORDS_PER_PAGE;
    let sent = format!(
        "{}\n\n<outline>\n{brief}\n</outline>\n\n{}",
        book_tag(record),
        prompt("book-write.md", &[("words", words.to_string())])?
    );
    caller.call_with_parse("write", spec, &sent, |reply| {
        let body = check_digest(reply, *points, words, book)?;
        let printed = typeset(&body, record)?.pages().len() - 1;
        ensure!(
            printed <= most,
            "the piece typesets to {printed} pages; it must fit in {most}, so cut detail, not points"
        );
        Ok(body)
    })
}

fn check_digest(reply: &str, points: usize, words: usize, book: &Index) -> Result<String> {
    let covered: Vec<usize> = MARKER
        .captures_iter(reply)
        .flat_map(|c| words_of(&c[1]))
        .filter_map(|w| w.strip_prefix('p').and_then(|n| n.parse().ok()))
        .collect();
    let missing: Vec<String> = (1..=points)
        .filter(|p| !covered.contains(p))
        .map(|p| format!("P{p}"))
        .collect();
    ensure!(
        missing.is_empty(),
        "these points are not covered (or their marker lines are missing): {}",
        missing.join(" ")
    );
    let body = MARKER.replace_all(reply, "").trim().to_string() + "\n";
    let count = body.split_whitespace().count();
    ensure!(
        count * 4 >= words * 3,
        "the piece is {count} words; write at least {}",
        words * 3 / 4
    );
    ensure!(!body.contains("[^"), "do not use footnotes");
    ensure!(
        !QUOTED.replace_all(&body, "").contains('\u{2014}'),
        "do not use em dashes in your own sentences"
    );
    let invented: Vec<String> = QUOTED
        .captures_iter(&body)
        .filter_map(|c| {
            c.get(1)
                .or_else(|| c.get(2))
                .map(|m| m.as_str().to_string())
        })
        .filter(|q| words_of(q).len() >= CHECKED_QUOTE_WORDS && !book.quotes(q))
        .collect();
    ensure!(
        invented.is_empty(),
        "these quotations are not in the book; quote only the outline's quotes, word for word, or drop the quotation marks and say it in your own words: {}",
        invented.join(" | ")
    );
    Ok(body)
}

fn render(dir: &Path, record: &Record) -> Result<usize> {
    let document = typeset(&read(&dir.join("digest.md"))?, record)?;
    std::fs::write(dir.join("digest.pdf"), template::pdf(&document)?)?;
    Ok(document.pages().len())
}

fn typeset(markdown: &str, record: &Record) -> Result<typst_layout::PagedDocument> {
    let body = typst_markup(markdown);
    let source = format!(
        "#show: digest.with(title: {}, author: {})\n\n{body}",
        string_literal(&record.title),
        string_literal(&record.author)
    );
    let tree = Tree {
        files: vec![File {
            path: "main.typ".to_string(),
            source,
        }],
        ..Tree::default()
    };
    template::document(&Sources::new(
        &tree,
        DIGEST_TYP,
        "#include \"/main.typ\"\n",
    )?)
}

fn typst_markup(md: &str) -> String {
    let mut out = String::new();
    let mut code: Option<String> = None;
    for event in Parser::new(md) {
        match (&mut code, event) {
            (Some(buf), Event::Text(t)) => buf.push_str(&t),
            (Some(buf), Event::End(TagEnd::CodeBlock)) => {
                out.push_str(&raw_block(buf.trim_end()));
                code = None;
            }
            (Some(_), _) => {}
            (None, Event::Start(Tag::CodeBlock(_))) => code = Some(String::new()),
            (None, event) => out.push_str(&markup(event)),
        }
    }
    out
}

fn markup(event: Event) -> String {
    match event {
        Event::Start(Tag::Heading { level, .. }) => format!("\n{} ", "=".repeat(level as usize)),
        Event::End(TagEnd::Heading(_) | TagEnd::Paragraph) => "\n\n".into(),
        Event::Start(Tag::Emphasis) => "#emph[".into(),
        Event::Start(Tag::Strong) => "#strong[".into(),
        Event::Start(Tag::BlockQuote(_)) => "#quote(block: true)[".into(),
        Event::End(TagEnd::Emphasis | TagEnd::Strong | TagEnd::BlockQuote(_)) => "]".into(),
        Event::Start(Tag::List(Some(_))) => "#enum(".into(),
        Event::Start(Tag::List(None)) => "#list(".into(),
        Event::End(TagEnd::List(_)) => ")\n\n".into(),
        Event::Start(Tag::Item) => "[".into(),
        Event::End(TagEnd::Item) => "],".into(),
        Event::Text(t) => escape_markup(&t).replace("\\\"", "\"").replace("\\'", "'"),
        Event::Code(t) => format!("#raw({})", string_literal(&t)),
        Event::SoftBreak => " ".into(),
        Event::HardBreak => "#linebreak()".into(),
        Event::Rule => "\n#line(length: 100%)\n".into(),
        _ => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quotes_match_through_scanning_noise_and_paraphrase_does_not() {
        let book = Index::new("Naturally, I didn't want to pay the increase, but what was the use of talking to the hotel about what I wanted? They were interested only in what they wanted.");
        assert!(book.score("what was the use of talking to the hotel about what I wanted? Th^ were interested only in what they wanted") >= QUOTE_MATCH);
        assert!(
            book.score(
                "the hotel only cared about its own wants, so talking about mine was useless"
            ) < QUOTE_MATCH
        );
    }

    #[test]
    fn an_elided_quote_passes_when_each_fragment_is_in_the_book() {
        let book = Index::new("Pairs provide a primitive glue that we can use to construct compound data objects, and in fact the single compound-data primitive pair is the only glue we need.");
        assert!(book.quotes("Pairs provide a primitive glue that we can use \u{2026} the single compound-data primitive pair is the only glue we need"));
        assert!(!book.quotes("the single compound-data primitive pair, implemented as a list, is all the structure a program will ever need"));
    }

    #[test]
    fn outline_must_place_every_idea_and_never_drop_a_core_one() {
        let idea = |id: &str, weight: &str| Idea {
            id: id.into(),
            claim: "c".into(),
            explanation: "e".into(),
            example: String::new(),
            quote: "q".into(),
            weight: weight.into(),
        };
        let ideas = [
            idea("1.1", "core"),
            idea("1.2", "supporting"),
            idea("2.1", "core"),
        ];
        let plan = |dropped: &str| Outline {
            thesis: "t".into(),
            sections: ["a", "b", "c"]
                .iter()
                .map(|h| Section {
                    heading: (*h).into(),
                    points: vec![Point {
                        ids: ["1.1", "1.2", "2.1"]
                            .iter()
                            .filter(|id| **id != dropped && h == &"a")
                            .map(|s| (*s).into())
                            .collect(),
                        gist: "g".into(),
                    }],
                })
                .collect(),
            dropped: vec![Dropped {
                id: dropped.into(),
                reason: "r".into(),
            }],
        };
        assert!(check_outline(&plan("1.2"), &ideas, 99).is_ok());
        let err = check_outline(&plan("2.1"), &ideas, 99)
            .unwrap_err()
            .to_string();
        assert!(err.contains("core ideas were dropped"), "{err}");
    }

    #[test]
    fn core_ideas_apart_in_one_passage_are_split_into_their_own_points() {
        let idea = |id: &str, weight: &str| Idea {
            id: id.into(),
            claim: format!("claim {id}"),
            explanation: String::new(),
            example: String::new(),
            quote: String::new(),
            weight: weight.into(),
        };
        let ideas = [
            idea("1.1", "core"),
            idea("1.2", "core"),
            idea("1.3", "supporting"),
            idea("1.9", "core"),
            idea("2.1", "core"),
        ];
        let by_id: HashMap<&str, &Idea> = ideas.iter().map(|i| (i.id.as_str(), i)).collect();
        let point = |ids: &[&str]| Point {
            ids: ids.iter().map(|s| (*s).into()).collect(),
            gist: "g".into(),
        };
        assert_eq!(
            split_point(point(&["1.1", "1.2", "2.1", "1.3"]), &by_id).len(),
            1
        );
        let parts = split_point(point(&["1.9", "1.1", "1.3"]), &by_id);
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[0].ids, vec!["1.3", "1.1"]);
        assert_eq!(
            (parts[1].ids.clone(), parts[1].gist.as_str()),
            (vec!["1.9".to_string()], "claim 1.9")
        );
    }

    #[test]
    fn passages_cut_at_chapters_and_overlap_only_mid_chapter_cuts() {
        let para = format!("{}\n\n", "word ".repeat(1000));
        let chapter = |n: usize, paras: usize| format!("CHAPTER {n}\n\n{}", para.repeat(paras));
        let parts = passages(&format!(
            "{}{}{}",
            chapter(1, 9),
            chapter(2, 9),
            chapter(3, 2)
        ));
        assert_eq!(parts.len(), 2);
        assert!(parts[1].starts_with("CHAPTER 2"));
        assert!(parts[1].contains("CHAPTER 3"));
        let late = passages(&format!("{}{}", chapter(1, 7), chapter(2, 12)));
        assert_eq!(late.len(), 2);
        assert!(late[1].starts_with("CHAPTER 2"));
        let long = passages(&chapter(1, 30));
        assert_eq!(long.len(), 2);
        let size = |p: &String| p.split_whitespace().count();
        assert_eq!(size(&long[0]) + size(&long[1]), 30_002 + 2 * 1000);
    }

    #[test]
    fn markdown_becomes_escaped_typst() {
        let out = typst_markup("## Heading\n\nA *b* [#x].\n\n```\n(define x 1)\n```\n");
        assert!(out.contains("== Heading"), "{out}");
        assert!(
            out.contains("#emph[b]") && out.contains("\\[\\#x\\]"),
            "{out}"
        );
        assert!(out.contains("```\n(define x 1)\n```"), "{out}");
        let quoted = typst_markup("He said \"go\" and it's done.");
        assert!(quoted.contains("\"go\" and it's"), "{quoted}");
    }
}
