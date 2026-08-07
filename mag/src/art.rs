// Art candidate rounds: one model
// call proposes a slate of art briefs for the edition, then a user-supplied
// shell command renders `candidates` variants of each brief. Purely
// additive: every round lives in its own timestamped directory under
// `editions/<ed>/art/rounds/`, nothing is ever overwritten or deleted, and a
// human makes the final selection by hand-editing edition.yaml.

use crate::caller::{Caller, ModelSpec};
use crate::produce::{self, INLINE_PREAMBLE};
use anyhow::{anyhow, bail, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::{Arc, Condvar, Mutex};
use std::thread;

/// Cap on concurrent `gen_cmd` subprocesses in flight at once.
const GEN_CONCURRENCY: usize = 4;

fn read(path: &Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

fn prompts_path(file: &str) -> PathBuf {
    PathBuf::from("prompts").join(file)
}

/// Resolve `editions/<edition>` directly, or else the unique directory
/// matching `editions/<edition>*`.
fn resolve_edition_dir(edition: &str) -> Result<PathBuf> {
    let direct = PathBuf::from("editions").join(edition);
    if direct.is_dir() {
        return Ok(direct);
    }
    let editions_root = Path::new("editions");
    let mut matches = Vec::new();
    for entry in fs::read_dir(editions_root)
        .with_context(|| format!("reading {}", editions_root.display()))?
    {
        let entry = entry?;
        if !entry.file_type()?.is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if name.starts_with(edition) {
            matches.push(entry.path());
        }
    }
    match matches.len() {
        0 => bail!(
            "no edition directory matching 'editions/{edition}' or 'editions/{edition}*'"
        ),
        1 => Ok(matches.remove(0)),
        _ => {
            let names: Vec<String> = matches.iter().map(|p| p.display().to_string()).collect();
            bail!("edition '{edition}' matches multiple directories: {}", names.join(", "))
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Brief {
    id: String,
    purpose: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    article_id: Option<String>,
    prompt: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    subject: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    composition: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    alt_text: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    credit: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
struct BriefsDoc {
    briefs: Vec<Brief>,
}

/// The edition's declared art direction: `art_direction_path` from
/// edition.yaml, read so the brief writer restates the visual language
/// inside every standalone prompt.
fn art_direction_section(edition_yaml_text: &str) -> Result<Option<(String, String)>> {
    let doc: serde_yaml::Value = serde_yaml::from_str(edition_yaml_text)
        .context("parsing edition.yaml for art_direction_path")?;
    let Some(path) = doc.get("art_direction_path").and_then(|v| v.as_str()) else {
        return Ok(None);
    };
    let path = path.trim();
    if path.is_empty() {
        return Ok(None);
    }
    let text = read(Path::new(path))?;
    Ok(Some((path.to_string(), text)))
}

/// Briefs from every earlier round whose purpose is in `purposes` — the
/// rejected material a scoped re-round must not repeat.
fn previous_briefs(edition_dir: &Path, purposes: &[String]) -> Result<Vec<Brief>> {
    let rounds_root = edition_dir.join("art").join("rounds");
    let mut round_dirs: Vec<PathBuf> = match fs::read_dir(&rounds_root) {
        Ok(entries) => entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.is_dir())
            .collect(),
        Err(_) => Vec::new(),
    };
    round_dirs.sort();
    let mut out = Vec::new();
    for round_dir in &round_dirs {
        let briefs_path = round_dir.join("briefs.yaml");
        if !briefs_path.exists() {
            continue;
        }
        let doc: BriefsDoc = serde_yaml::from_str(&read(&briefs_path)?)
            .with_context(|| format!("parsing {}", briefs_path.display()))?;
        out.extend(doc.briefs.into_iter().filter(|b| purposes.contains(&b.purpose)));
    }
    Ok(out)
}

fn build_brief_prompt(
    edition_yaml_text: &str,
    candidates: u32,
    only: Option<&[String]>,
    rejected: &[Brief],
    note: Option<&str>,
) -> Result<String> {
    let process_doc = read(&prompts_path("illustrations.md"))?;
    let brief_doc = read(&prompts_path("cover-art-candidates.md"))?;
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &produce::section("prompts/illustrations.md", &process_doc);
    out += &produce::section("prompts/cover-art-candidates.md", &brief_doc);
    if let Some((path, text)) = art_direction_section(edition_yaml_text)? {
        out += &produce::section(&path, &text);
    }
    out += &produce::section("edition.yaml", edition_yaml_text);
    if !rejected.is_empty() {
        let mut body = String::new();
        for b in rejected {
            body += &format!("--- {} [{}]\n{}\n\n", b.id, b.purpose, b.prompt);
        }
        out += &produce::section("rejected earlier briefs (do not repeat)", &body);
    }
    if let Some(note) = note {
        out += &produce::section("editor's note for this round", note);
    }
    match only {
        Some(purposes) => {
            out += &format!(
                "\nPropose a fresh round of art briefs covering ONLY these \
                 purposes: {}. Every earlier candidate for them was rejected; \
                 their briefs are above. Keep each branch's established art \
                 direction and the shared constraints, but change the \
                 editorial proposition, subject, metaphor, and composition \
                 completely — reuse nothing conceptual from the rejected \
                 briefs.\n\n\
                 You are not generating images yourself — a later pipeline \
                 step will run each brief through an image generator \
                 {candidates} time(s) to produce that many variants.\n\n",
                purposes.join(", ")
            );
        }
        None => {
            out += &format!(
                "\nPropose the complete art-brief slate for this edition now. You are \
         not generating images yourself — a later pipeline step will run each \
         brief through an image generator {candidates} time(s) to produce that \
         many variants. Per prompts/illustrations.md the slate covers the \
         cover (one brief per cover branch), one opener brief and one tail \
         brief per article, and closing-plate briefs keeping the approved pool \
         at three or more.\n\n"
            );
        }
    }
    out +=
        "Return exactly one fenced yaml code block (```yaml ... ```) and nothing \
         else of consequence outside it. The block must contain a top-level \
         `briefs:` list, non-empty, where every entry has:\n\
         - `id`: a short, unique kebab-case slug\n\
         - `purpose`: one of `cover`, `opener`, `tail`, `closing`\n\
         - `article_id`: for `opener` and `tail` briefs, the edition.yaml id \
           of the article the brief illustrates; omit it otherwise\n\
         - `prompt`: the complete, standalone image-generation prompt text for \
           this brief — it must stand entirely on its own, restating the art \
           direction's visual language, palette, constraints, and avoid-list, \
           since the image generator that reads it will see nothing else from \
           this reply, this conversation, or the documents above\n\
         - `subject` and `composition`: for interior briefs, the one-sentence \
           records prompts/illustrations.md asks for\n\
         - `alt_text`: for `opener`, `tail`, and `closing` briefs, the alt \
           text approval will copy into edition.yaml\n\
         - `credit`: for interior briefs, the credit line approval will copy \
           into edition.yaml\n";
    Ok(out)
}

fn extract_briefs(reply: &str, label: &str) -> Result<Vec<Brief>> {
    let re = Regex::new(r"(?s)```ya?ml\s*\n(.*?)```").unwrap();
    let fence = re
        .captures_iter(reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no fenced yaml block"))?;
    let doc: BriefsDoc = serde_yaml::from_str(&fence)
        .with_context(|| format!("{label}: invalid yaml, or no non-empty 'briefs' list"))?;
    if doc.briefs.is_empty() {
        bail!("{label}: 'briefs' list is empty");
    }
    for b in &doc.briefs {
        if b.id.trim().is_empty() || b.prompt.trim().is_empty() {
            bail!("{label}: every brief needs a non-empty id and prompt");
        }
        let purpose = b.purpose.as_str();
        if !matches!(purpose, "cover" | "opener" | "tail" | "closing") {
            bail!(
                "{label}: brief '{}' has purpose '{purpose}', expected \
                 cover, opener, tail, or closing",
                b.id
            );
        }
        let article_id = b.article_id.as_deref().unwrap_or("").trim();
        if matches!(purpose, "opener" | "tail") && article_id.is_empty() {
            bail!("{label}: {purpose} brief '{}' needs an article_id", b.id);
        }
        let alt = b.alt_text.as_deref().unwrap_or("").trim();
        if matches!(purpose, "opener" | "tail" | "closing") && alt.is_empty() {
            bail!("{label}: {purpose} brief '{}' needs alt_text", b.id);
        }
    }
    Ok(doc.briefs)
}

/// A simple counting semaphore capping in-flight `gen_cmd` subprocesses,
/// same pattern as caller.rs's Semaphore (acquired only around the
/// subprocess run, never around the whole per-candidate task).
struct Semaphore {
    count: Mutex<usize>,
    cond: Condvar,
    max: usize,
}

impl Semaphore {
    fn new(max: usize) -> Self {
        Self { count: Mutex::new(0), cond: Condvar::new(), max }
    }

    fn acquire(&self) {
        let mut count = self.count.lock().unwrap();
        while *count >= self.max {
            count = self.cond.wait(count).unwrap();
        }
        *count += 1;
    }

    fn release(&self) {
        let mut count = self.count.lock().unwrap();
        *count -= 1;
        self.cond.notify_one();
    }
}

struct SemaphoreGuard<'a>(&'a Semaphore);

impl<'a> SemaphoreGuard<'a> {
    fn acquire(sem: &'a Semaphore) -> Self {
        sem.acquire();
        Self(sem)
    }
}

impl Drop for SemaphoreGuard<'_> {
    fn drop(&mut self) {
        self.0.release();
    }
}

#[derive(Debug, Clone, Serialize)]
struct GeneratedItem {
    brief: String,
    variant: u32,
    file: String,
    ok: bool,
}

/// Escape a string for safe embedding inside a single-quoted shell argument:
/// close the quote, emit an escaped literal quote, reopen the quote.
fn shell_single_quote_escape(s: &str) -> String {
    s.replace('\'', "'\\''")
}

/// The one place a candidate's output filename and shell command are built,
/// so the live run and the dry-run script can never drift apart.
fn candidate_command(
    gen_cmd: &str,
    brief: &Brief,
    variant: u32,
    round_dir: &Path,
) -> (String, String) {
    let filename = format!("{}-v{variant}.png", brief.id);
    let out_path = round_dir.join(&filename);
    let variant_prompt = format!("{} — variation {variant}", brief.prompt);
    let escaped_prompt = shell_single_quote_escape(&variant_prompt);
    let cmd_str = gen_cmd
        .replace("{prompt}", &escaped_prompt)
        .replace("{out}", &out_path.to_string_lossy());
    (filename, cmd_str)
}

/// Dry run: write the exact per-candidate commands as an executable script
/// beside the briefs, to be run from the repo root once image credits exist.
fn write_generate_script(
    round_dir: &Path,
    edition_label: &str,
    briefs: &[Brief],
    candidates: u32,
    gen_cmd: &str,
) -> Result<PathBuf> {
    let mut script = String::new();
    script += "#!/bin/sh\n";
    script += &format!(
        "# mag art dry run for {edition_label}: {} brief(s) x {candidates} \
         variant(s).\n",
        briefs.len()
    );
    script += "# Run from the repo root. Every command renders one candidate \
               into this\n# round directory; rerunning a line overwrites only \
               its own file.\n";
    script += "set -eu\n";
    for brief in briefs {
        script += &format!("\n# {} [{}]\n", brief.id, brief.purpose);
        for variant in 1..=candidates {
            let (_, cmd_str) = candidate_command(gen_cmd, brief, variant, round_dir);
            script += &cmd_str;
            script += "\n";
        }
    }
    let path = round_dir.join("generate.sh");
    fs::write(&path, script)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&path, fs::Permissions::from_mode(0o755))?;
    }
    Ok(path)
}

/// Run one `gen_cmd` subprocess for a candidate. Returns Ok on a zero exit
/// with a non-empty output file, otherwise a description of the failure.
fn run_gen_command(cmd_str: &str, out_path: &Path) -> Result<(), String> {
    let output = Command::new("sh")
        .arg("-c")
        .arg(cmd_str)
        .output()
        .map_err(|e| format!("failed to spawn gen-cmd: {e}"))?;
    if !output.status.success() {
        let err_text = String::from_utf8_lossy(&output.stderr);
        let truncated: String = err_text.trim().chars().take(200).collect();
        return Err(format!("gen-cmd exited with {}: {truncated}", output.status));
    }
    match fs::metadata(out_path) {
        Ok(m) if m.len() > 0 => Ok(()),
        Ok(_) => Err("output file is empty".to_string()),
        Err(_) => Err("output file was not created".to_string()),
    }
}

/// Run every brief x variant candidate, capped at GEN_CONCURRENCY in flight.
fn generate_all(
    briefs: &[Brief],
    candidates: u32,
    gen_cmd: &str,
    round_dir: &Path,
) -> Vec<GeneratedItem> {
    let sem = Arc::new(Semaphore::new(GEN_CONCURRENCY));
    let mut handles = Vec::new();
    for brief in briefs {
        for variant in 1..=candidates {
            let sem = Arc::clone(&sem);
            let round_dir = round_dir.to_path_buf();
            let brief_id = brief.id.clone();
            let (filename, cmd_str) = candidate_command(gen_cmd, brief, variant, round_dir.as_path());
            handles.push(thread::spawn(move || -> GeneratedItem {
                let out_path = round_dir.join(&filename);
                let result = {
                    let _permit = SemaphoreGuard::acquire(&sem);
                    run_gen_command(&cmd_str, &out_path)
                };
                match result {
                    Ok(()) => {
                        println!("    {brief_id} v{variant}: ok");
                        GeneratedItem { brief: brief_id, variant, file: filename, ok: true }
                    }
                    Err(e) => {
                        eprintln!("    {brief_id} v{variant}: FAILED — {e}");
                        GeneratedItem { brief: brief_id, variant, file: filename, ok: false }
                    }
                }
            }));
        }
    }
    let mut results = Vec::with_capacity(handles.len());
    for h in handles {
        match h.join() {
            Ok(item) => results.push(item),
            Err(_) => eprintln!("    a gen-cmd worker thread panicked"),
        }
    }
    results
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn write_proof_sheet(
    round_dir: &Path,
    edition_label: &str,
    briefs: &[Brief],
    generated: &[GeneratedItem],
) -> Result<()> {
    let prompts_by_id: HashMap<&str, &str> =
        briefs.iter().map(|b| (b.id.as_str(), b.prompt.as_str())).collect();

    let mut html = String::new();
    html += "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n";
    html += &format!("<title>Art proof sheet — {}</title>\n", html_escape(edition_label));
    html += "<style>\n\
        body { font-family: -apple-system, sans-serif; margin: 2rem; background: #111; color: #eee; }\n\
        h1 { font-size: 1.2rem; }\n\
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.5rem; }\n\
        figure { margin: 0; background: #1b1b1b; border: 1px solid #333; border-radius: 6px; padding: 0.75rem; }\n\
        figure img { width: 100%; height: auto; display: block; border-radius: 4px; background: #000; }\n\
        .failed { width: 100%; height: 200px; display: flex; align-items: center; justify-content: center;\n\
            background: #300; color: #f88; border-radius: 4px; font-weight: bold; }\n\
        figcaption { margin-top: 0.5rem; font-size: 0.85rem; color: #aaa; }\n\
        details { margin-top: 0.4rem; }\n\
        details pre { white-space: pre-wrap; font-size: 0.8rem; color: #ccc; }\n\
        </style>\n</head>\n<body>\n";
    html += &format!("<h1>Art proof sheet — {}</h1>\n", html_escape(edition_label));
    html += "<div class=\"grid\">\n";
    for item in generated {
        let prompt = prompts_by_id.get(item.brief.as_str()).copied().unwrap_or("");
        html += "<figure>\n";
        if item.ok {
            html += &format!("<img src=\"{}\" loading=\"lazy\">\n", html_escape(&item.file));
        } else {
            html += "<div class=\"failed\">FAILED</div>\n";
        }
        html += &format!(
            "<figcaption>{} — variant {}</figcaption>\n",
            html_escape(&item.brief),
            item.variant
        );
        html += &format!(
            "<details><summary>prompt</summary><pre>{}</pre></details>\n",
            html_escape(prompt)
        );
        html += "</figure>\n";
    }
    html += "</div>\n</body>\n</html>\n";
    fs::write(round_dir.join("proof-sheet.html"), html)?;
    Ok(())
}

/// One generated image on the edition's showcase page: where it lives,
/// which brief produced it, and whether edition.yaml currently selects it.
struct ShowcaseItem {
    round: String,
    file: String,
    brief_id: String,
    purpose: String,
    article_id: Option<String>,
    prompt: String,
    variant: u32,
    selected: bool,
}

/// Every art path edition.yaml currently selects, repo-relative as written:
/// the cover, each article's opener and tail, and the closing plates.
fn selected_art_paths(edition_yaml: &serde_yaml::Value) -> Vec<String> {
    let mut out = Vec::new();
    let mut push = |v: Option<&serde_yaml::Value>| {
        if let Some(s) = v.and_then(|v| v.as_str()) {
            if !s.trim().is_empty() {
                out.push(s.to_string());
            }
        }
    };
    push(edition_yaml.get("cover").and_then(|c| c.get("art_path")));
    if let Some(articles) = edition_yaml.get("articles").and_then(|v| v.as_sequence()) {
        for article in articles {
            push(article.get("opener_art").and_then(|o| o.get("path")));
            push(article.get("tail_art_path"));
        }
    }
    if let Some(plates) = edition_yaml.get("closing_plates").and_then(|v| v.as_sequence()) {
        for plate in plates {
            push(plate.get("art_path"));
        }
    }
    out
}

/// Walk every round under `editions/<ed>/art/rounds/`, pairing round.yaml's
/// generated items with briefs.yaml's purposes and prompts.
fn collect_showcase_items(edition_dir: &Path, selected: &[String]) -> Result<Vec<ShowcaseItem>> {
    let rounds_root = edition_dir.join("art").join("rounds");
    let mut round_dirs: Vec<PathBuf> = match fs::read_dir(&rounds_root) {
        Ok(entries) => entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.is_dir())
            .collect(),
        Err(_) => Vec::new(),
    };
    round_dirs.sort();

    let mut items = Vec::new();
    for round_dir in &round_dirs {
        let round_name = round_dir.file_name().unwrap().to_string_lossy().to_string();
        let briefs_path = round_dir.join("briefs.yaml");
        let round_path = round_dir.join("round.yaml");
        if !briefs_path.exists() || !round_path.exists() {
            continue;
        }
        let briefs: BriefsDoc =
            serde_yaml::from_str(&read(&briefs_path)?).with_context(|| format!("parsing {}", briefs_path.display()))?;
        let by_id: HashMap<&str, &Brief> =
            briefs.briefs.iter().map(|b| (b.id.as_str(), b)).collect();
        let round: serde_yaml::Value =
            serde_yaml::from_str(&read(&round_path)?).with_context(|| format!("parsing {}", round_path.display()))?;
        let generated = round.get("generated").and_then(|v| v.as_sequence());
        for item in generated.into_iter().flatten() {
            let ok = item.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
            let file = item.get("file").and_then(|v| v.as_str()).unwrap_or("");
            if !ok || file.is_empty() || !round_dir.join(file).exists() {
                continue;
            }
            let brief_id = item.get("brief").and_then(|v| v.as_str()).unwrap_or("");
            let variant = item.get("variant").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
            let (purpose, article_id, prompt) = match by_id.get(brief_id) {
                Some(b) => (b.purpose.clone(), b.article_id.clone(), b.prompt.clone()),
                None => ("unknown".to_string(), None, String::new()),
            };
            let repo_path = format!(
                "{}/art/rounds/{round_name}/{file}",
                edition_dir.to_string_lossy()
            );
            items.push(ShowcaseItem {
                round: round_name.clone(),
                file: file.to_string(),
                brief_id: brief_id.to_string(),
                purpose,
                article_id,
                prompt,
                variant,
                selected: selected.iter().any(|s| s == &repo_path),
            });
        }
    }
    Ok(items)
}

/// The edition's one-stop review page: every generated image across every
/// round, grouped cover → openers → tails → closing plates, selected assets
/// badged. Rewritten from disk on every `mag art` invocation.
fn write_showcase(edition_dir: &Path, edition_label: &str) -> Result<PathBuf> {
    let edition_yaml_path = edition_dir.join("edition.yaml");
    let selected = if edition_yaml_path.exists() {
        let doc: serde_yaml::Value = serde_yaml::from_str(&read(&edition_yaml_path)?)
            .with_context(|| format!("parsing {}", edition_yaml_path.display()))?;
        selected_art_paths(&doc)
    } else {
        Vec::new()
    };
    let items = collect_showcase_items(edition_dir, &selected)?;

    let mut html = String::new();
    html += "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n";
    html += &format!("<title>Art showcase — {}</title>\n", html_escape(edition_label));
    html += "<style>\n\
        body { font-family: -apple-system, sans-serif; margin: 2rem; background: #111; color: #eee; }\n\
        h1 { font-size: 1.3rem; }\n\
        h2 { font-size: 1.1rem; margin-top: 2.5rem; border-bottom: 1px solid #333; padding-bottom: 0.3rem; }\n\
        h3 { font-size: 0.95rem; color: #bbb; margin: 1.5rem 0 0.5rem; }\n\
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.25rem; }\n\
        figure { margin: 0; background: #1b1b1b; border: 1px solid #333; border-radius: 6px; padding: 0.75rem; position: relative; }\n\
        figure.selected { border-color: #4a4; box-shadow: 0 0 0 2px #4a4; }\n\
        figure img { width: 100%; height: auto; display: block; border-radius: 4px; background: #000; }\n\
        .badge { position: absolute; top: 1rem; right: 1rem; background: #4a4; color: #041; font-weight: bold;\n\
            font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 999px; }\n\
        figcaption { margin-top: 0.5rem; font-size: 0.85rem; color: #aaa; }\n\
        details { margin-top: 0.4rem; }\n\
        details pre { white-space: pre-wrap; font-size: 0.8rem; color: #ccc; }\n\
        .empty { color: #777; font-style: italic; }\n\
        </style>\n</head>\n<body>\n";
    html += &format!(
        "<h1>Art showcase — {} ({} image(s))</h1>\n\
         <p>Every generated candidate across every round. A green badge marks \
         what edition.yaml currently selects. Give feedback per image as \
         <code>brief-id vN (round)</code>.</p>\n",
        html_escape(edition_label),
        items.len()
    );

    for (purpose, heading) in [
        ("cover", "Cover"),
        ("opener", "Article openers"),
        ("tail", "Article tails"),
        ("closing", "Closing plates"),
        ("unknown", "Unmatched"),
    ] {
        let mut section: Vec<&ShowcaseItem> =
            items.iter().filter(|i| i.purpose == purpose).collect();
        if section.is_empty() {
            if purpose != "unknown" {
                html += &format!("<h2>{heading}</h2>\n<p class=\"empty\">none generated yet</p>\n");
            }
            continue;
        }
        section.sort_by(|a, b| {
            (&a.brief_id, &a.round, a.variant).cmp(&(&b.brief_id, &b.round, b.variant))
        });
        html += &format!("<h2>{heading}</h2>\n");
        let mut current_brief = "";
        let mut open = false;
        for item in section {
            if item.brief_id != current_brief {
                if open {
                    html += "</div>\n";
                }
                current_brief = &item.brief_id;
                let article_note = item
                    .article_id
                    .as_deref()
                    .map(|a| format!(" — {}", html_escape(a)))
                    .unwrap_or_default();
                html += &format!(
                    "<h3>{}{article_note}</h3>\n<div class=\"grid\">\n",
                    html_escape(&item.brief_id)
                );
                open = true;
            }
            let classes = if item.selected { "selected" } else { "" };
            html += &format!("<figure class=\"{classes}\">\n");
            if item.selected {
                html += "<span class=\"badge\">SELECTED</span>\n";
            }
            html += &format!(
                "<img src=\"rounds/{}/{}\" loading=\"lazy\">\n",
                html_escape(&item.round),
                html_escape(&item.file)
            );
            html += &format!(
                "<figcaption>{} v{} ({})</figcaption>\n",
                html_escape(&item.brief_id),
                item.variant,
                html_escape(&item.round)
            );
            if !item.prompt.is_empty() {
                html += &format!(
                    "<details><summary>prompt</summary><pre>{}</pre></details>\n",
                    html_escape(&item.prompt)
                );
            }
            html += "</figure>\n";
        }
        if open {
            html += "</div>\n";
        }
    }
    html += "</body>\n</html>\n";

    let path = edition_dir.join("art").join("showcase.html");
    fs::create_dir_all(path.parent().unwrap())?;
    fs::write(&path, html)?;
    Ok(path)
}

#[derive(Serialize)]
struct RoundYaml<'a> {
    edition: &'a str,
    dry_run: bool,
    generated: &'a [GeneratedItem],
    failures: usize,
}

fn write_round_yaml(
    round_dir: &Path,
    edition_label: &str,
    dry_run: bool,
    generated: &[GeneratedItem],
) -> Result<usize> {
    let failures = generated.iter().filter(|g| !g.ok).count();
    let doc = RoundYaml { edition: edition_label, dry_run, generated, failures };
    fs::write(round_dir.join("round.yaml"), serde_yaml::to_string(&doc)?)?;
    Ok(failures)
}

pub fn run(
    edition: &str,
    gen_cmd: Option<&str>,
    candidates: u32,
    model: &ModelSpec,
    dry_run: bool,
    showcase_only: bool,
    only: Option<&str>,
    note: Option<&str>,
) -> Result<i32> {
    let edition_dir = resolve_edition_dir(edition)?;
    let edition_label = edition_dir
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| edition.to_string());

    if showcase_only {
        let path = write_showcase(&edition_dir, &edition_label)?;
        println!("showcase rebuilt: {}", path.display());
        return Ok(0);
    }

    let edition_yaml_text = read(&edition_dir.join("edition.yaml"))?;

    let round_dir = edition_dir.join("art").join("rounds").join(crate::caller::now_stamp());
    if round_dir.exists() {
        bail!("round directory already exists, refusing to touch it: {}", round_dir.display());
    }
    fs::create_dir_all(&round_dir)
        .with_context(|| format!("creating round directory {}", round_dir.display()))?;

    println!("round dir: {}", round_dir.display());

    let only_purposes: Option<Vec<String>> = match only {
        Some(raw) => {
            let purposes: Vec<String> =
                raw.split(',').map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect();
            for p in &purposes {
                if !matches!(p.as_str(), "cover" | "opener" | "tail" | "closing") {
                    bail!("--only accepts cover, opener, tail, closing; got '{p}'");
                }
            }
            if purposes.is_empty() {
                bail!("--only was given but named no purposes");
            }
            Some(purposes)
        }
        None => None,
    };
    let rejected = match &only_purposes {
        Some(purposes) => previous_briefs(&edition_dir, purposes)?,
        None => Vec::new(),
    };

    let caller = Caller::new(&round_dir);
    let prompt = build_brief_prompt(
        &edition_yaml_text,
        candidates,
        only_purposes.as_deref(),
        &rejected,
        note,
    )?;
    let label = "art-briefs";
    let briefs = caller.call_with_parse(label, model, &prompt, |r| {
        let briefs = extract_briefs(r, label)?;
        if let Some(purposes) = &only_purposes {
            for b in &briefs {
                if !purposes.contains(&b.purpose) {
                    bail!(
                        "{label}: this round is scoped to {}; brief '{}' has purpose '{}'",
                        purposes.join(", "),
                        b.id,
                        b.purpose
                    );
                }
            }
        }
        Ok(briefs)
    })?;

    let briefs_doc = BriefsDoc { briefs: briefs.clone() };
    fs::write(round_dir.join("briefs.yaml"), serde_yaml::to_string(&briefs_doc)?)?;
    println!("  {} brief(s) proposed", briefs.len());

    if dry_run {
        write_round_yaml(&round_dir, &edition_label, true, &[])?;
        write_showcase(&edition_dir, &edition_label)?;
        println!();
        println!("dry run: no image credits spent.");
        match gen_cmd {
            Some(cmd) => {
                let script = write_generate_script(
                    &round_dir, &edition_label, &briefs, candidates, cmd,
                )?;
                println!(
                    "run {} from the repo root when credits are available, \
                     then review the images in {} and select by hand-editing \
                     edition.yaml.",
                    script.display(),
                    round_dir.display()
                );
            }
            None => println!(
                "no --gen-cmd recorded; the prompts are in {}/briefs.yaml — \
                 generate them by hand, or rerun with --dry-run --gen-cmd to \
                 get an executable generate.sh.",
                round_dir.display()
            ),
        }
        return Ok(0);
    }
    let gen_cmd = gen_cmd.expect("clap requires --gen-cmd when not a dry run");

    let generated = generate_all(&briefs, candidates, gen_cmd, &round_dir);

    write_proof_sheet(&round_dir, &edition_label, &briefs, &generated)?;
    let failures = write_round_yaml(&round_dir, &edition_label, false, &generated)?;
    let showcase = write_showcase(&edition_dir, &edition_label)?;
    println!("showcase: {}", showcase.display());

    let mut per_brief: HashMap<&str, (usize, usize)> = HashMap::new();
    for item in &generated {
        let entry = per_brief.entry(item.brief.as_str()).or_insert((0, 0));
        if item.ok {
            entry.0 += 1;
        } else {
            entry.1 += 1;
        }
    }
    println!();
    println!("round dir: {}", round_dir.display());
    for brief in &briefs {
        let (ok, fail) = per_brief.get(brief.id.as_str()).copied().unwrap_or((0, 0));
        println!("  {} [{}]: {ok} ok, {fail} failed", brief.id, brief.purpose);
    }
    println!(
        "\nopen proof-sheet.html, record your selection in edition.yaml \
         (cover.art_path / opener_art.path / tail_art_path / closing_plates), \
         historic images are never deleted."
    );

    let all_failed = !generated.is_empty() && failures == generated.len();
    Ok(if all_failed { 1 } else { 0 })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn yaml_reply(body: &str) -> String {
        format!("```yaml\n{body}\n```")
    }

    #[test]
    fn extract_briefs_accepts_a_complete_slate() {
        let reply = yaml_reply(
            "briefs:\n\
             - id: cover-synthetic\n  purpose: cover\n  prompt: a cover\n\
             - id: opener-a\n  purpose: opener\n  article_id: a\n  prompt: p\n\
             \x20 alt_text: a boy\n  credit: the editors\n\
             - id: tail-a\n  purpose: tail\n  article_id: a\n  prompt: p\n\
             \x20 alt_text: a robot\n\
             - id: plate-one\n  purpose: closing\n  prompt: p\n  alt_text: a plate\n",
        );
        let briefs = extract_briefs(&reply, "t").unwrap();
        assert_eq!(briefs.len(), 4);
        assert_eq!(briefs[1].article_id.as_deref(), Some("a"));
    }

    #[test]
    fn extract_briefs_rejects_unknown_purpose() {
        let reply = yaml_reply("briefs:\n- id: x\n  purpose: poster\n  prompt: p\n");
        let err = extract_briefs(&reply, "t").unwrap_err().to_string();
        assert!(err.contains("purpose 'poster'"), "{err}");
    }

    #[test]
    fn extract_briefs_rejects_opener_without_article_id() {
        let reply =
            yaml_reply("briefs:\n- id: x\n  purpose: opener\n  prompt: p\n  alt_text: a\n");
        let err = extract_briefs(&reply, "t").unwrap_err().to_string();
        assert!(err.contains("needs an article_id"), "{err}");
    }

    #[test]
    fn extract_briefs_rejects_interior_brief_without_alt_text() {
        let reply = yaml_reply("briefs:\n- id: x\n  purpose: closing\n  prompt: p\n");
        let err = extract_briefs(&reply, "t").unwrap_err().to_string();
        assert!(err.contains("needs alt_text"), "{err}");
    }

    #[test]
    fn candidate_command_substitutes_prompt_and_out() {
        let brief = Brief {
            id: "tail-a".into(),
            purpose: "tail".into(),
            article_id: Some("a".into()),
            prompt: "a robot's day".into(),
            subject: None,
            composition: None,
            alt_text: Some("alt".into()),
            credit: None,
        };
        let (filename, cmd) =
            candidate_command("gen '{prompt}' -o {out}", &brief, 2, Path::new("rounds/r1"));
        assert_eq!(filename, "tail-a-v2.png");
        assert_eq!(cmd, "gen 'a robot'\\''s day — variation 2' -o rounds/r1/tail-a-v2.png");
    }

    #[test]
    fn art_direction_section_is_none_without_the_field() {
        assert!(art_direction_section("id: e\n").unwrap().is_none());
        assert!(art_direction_section("art_direction_path: ''\n").unwrap().is_none());
    }

    #[test]
    fn art_direction_section_reads_the_declared_file() {
        let dir = std::env::temp_dir().join("mag-art-test");
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("direction.yaml");
        fs::write(&path, "direction: manga\n").unwrap();
        let yaml = format!("art_direction_path: {}\n", path.display());
        let (label, text) = art_direction_section(&yaml).unwrap().unwrap();
        assert_eq!(label, path.display().to_string());
        assert_eq!(text, "direction: manga\n");
    }

    #[test]
    fn showcase_groups_by_purpose_and_badges_selection() {
        let ed = std::env::temp_dir().join("mag-art-test-showcase").join("editions").join("009");
        let round = ed.join("art").join("rounds").join("2026-01-01T00-00-00");
        fs::create_dir_all(&round).unwrap();
        fs::write(
            round.join("briefs.yaml"),
            "briefs:\n\
             - id: cover-wildcard\n  purpose: cover\n  prompt: p-cover\n\
             - id: opener-a\n  purpose: opener\n  article_id: a\n  prompt: p-a\n\
             \x20 alt_text: alt\n",
        )
        .unwrap();
        fs::write(
            round.join("round.yaml"),
            "edition: '009'\ndry_run: false\nfailures: 1\ngenerated:\n\
             - {brief: cover-wildcard, variant: 1, file: cover-wildcard-v1.png, ok: true}\n\
             - {brief: opener-a, variant: 1, file: opener-a-v1.png, ok: true}\n\
             - {brief: opener-a, variant: 2, file: opener-a-v2.png, ok: false}\n",
        )
        .unwrap();
        fs::write(round.join("cover-wildcard-v1.png"), b"png").unwrap();
        fs::write(round.join("opener-a-v1.png"), b"png").unwrap();
        let selected_path = format!(
            "{}/art/rounds/2026-01-01T00-00-00/opener-a-v1.png",
            ed.to_string_lossy()
        );
        fs::write(
            ed.join("edition.yaml"),
            format!(
                "id: '009'\ncover:\n  headline: h\narticles:\n- id: a\n  opener_art:\n    path: {selected_path}\n"
            ),
        )
        .unwrap();

        let path = write_showcase(&ed, "009").unwrap();
        let html = fs::read_to_string(&path).unwrap();
        assert!(html.contains("<h2>Cover</h2>"), "{html}");
        assert!(html.contains("<h2>Article openers</h2>"), "{html}");
        assert!(html.contains("opener-a</h3>") || html.contains("opener-a — a</h3>"), "{html}");
        // The failed v2 never renders; the selected v1 carries the badge.
        assert!(!html.contains("opener-a-v2.png"), "{html}");
        assert_eq!(html.matches("SELECTED").count(), 1, "{html}");
        assert!(html.contains("rounds/2026-01-01T00-00-00/cover-wildcard-v1.png"), "{html}");
        // Tails were never generated: the section says so rather than vanishing.
        assert!(html.contains("none generated yet"), "{html}");
    }

    #[test]
    fn generate_script_lists_every_candidate() {
        let dir = std::env::temp_dir().join("mag-art-test-script");
        fs::create_dir_all(&dir).unwrap();
        let briefs = vec![Brief {
            id: "cover-wildcard".into(),
            purpose: "cover".into(),
            article_id: None,
            prompt: "one improbable idea".into(),
            subject: None,
            composition: None,
            alt_text: None,
            credit: None,
        }];
        let path =
            write_generate_script(&dir, "005", &briefs, 2, "gen '{prompt}' -o {out}").unwrap();
        let script = fs::read_to_string(&path).unwrap();
        assert!(script.starts_with("#!/bin/sh\n"), "{script}");
        assert!(script.contains("# cover-wildcard [cover]"), "{script}");
        assert!(script.contains("variation 1"), "{script}");
        assert!(script.contains("variation 2"), "{script}");
        assert!(script.contains("cover-wildcard-v2.png"), "{script}");
    }
}
