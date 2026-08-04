// Art candidate rounds — port of produce.py's image-round shape: one model
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
    prompt: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct BriefsDoc {
    briefs: Vec<Brief>,
}

fn build_brief_prompt(edition_yaml_text: &str, candidates: u32) -> Result<String> {
    let brief_doc = read(&prompts_path("cover-art-candidates.md"))?;
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &produce::section("prompts/cover-art-candidates.md", &brief_doc);
    out += &produce::section("edition.yaml", edition_yaml_text);
    out += &format!(
        "\nPropose the art briefs for this edition now. You are not generating \
         images yourself — a later pipeline step will run each brief through an \
         image generator {candidates} time(s) to produce that many variants. \
         Produce the briefs only once for this edition (typically 3 to 6 briefs \
         total), covering the cover per the brief above plus any article \
         openers, tails, or closing plates the edition's contents call for.\n\n\
         Return exactly one fenced yaml code block (```yaml ... ```) and nothing \
         else of consequence outside it. The block must contain a top-level \
         `briefs:` list, non-empty, where every entry has:\n\
         - `id`: a short, unique kebab-case slug\n\
         - `purpose`: one of `cover`, `opener`, `tail`, `closing`\n\
         - `prompt`: the complete, standalone image-generation prompt text for \
           this brief — it must stand entirely on its own, since the image \
           generator that reads it will see nothing else from this reply, this \
           conversation, or the edition.yaml above.\n"
    );
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
            let gen_cmd = gen_cmd.to_string();
            let round_dir = round_dir.to_path_buf();
            let brief_id = brief.id.clone();
            let variant_prompt = format!("{} — variation {variant}", brief.prompt);
            handles.push(thread::spawn(move || -> GeneratedItem {
                let filename = format!("{brief_id}-v{variant}.png");
                let out_path = round_dir.join(&filename);
                let escaped_prompt = shell_single_quote_escape(&variant_prompt);
                let cmd_str = gen_cmd
                    .replace("{prompt}", &escaped_prompt)
                    .replace("{out}", &out_path.to_string_lossy());

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

#[derive(Serialize)]
struct RoundYaml<'a> {
    edition: &'a str,
    generated: &'a [GeneratedItem],
    failures: usize,
}

fn write_round_yaml(round_dir: &Path, edition_label: &str, generated: &[GeneratedItem]) -> Result<usize> {
    let failures = generated.iter().filter(|g| !g.ok).count();
    let doc = RoundYaml { edition: edition_label, generated, failures };
    fs::write(round_dir.join("round.yaml"), serde_yaml::to_string(&doc)?)?;
    Ok(failures)
}

pub fn run(edition: &str, gen_cmd: &str, candidates: u32, model: &ModelSpec) -> Result<i32> {
    let edition_dir = resolve_edition_dir(edition)?;
    let edition_label = edition_dir
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| edition.to_string());
    let edition_yaml_text = read(&edition_dir.join("edition.yaml"))?;

    let round_dir = edition_dir.join("art").join("rounds").join(crate::caller::now_stamp());
    if round_dir.exists() {
        bail!("round directory already exists, refusing to touch it: {}", round_dir.display());
    }
    fs::create_dir_all(&round_dir)
        .with_context(|| format!("creating round directory {}", round_dir.display()))?;

    println!("round dir: {}", round_dir.display());

    let caller = Caller::new(&round_dir);
    let prompt = build_brief_prompt(&edition_yaml_text, candidates)?;
    let label = "art-briefs";
    let briefs = caller.call_with_parse(label, model, &prompt, |r| extract_briefs(r, label))?;

    let briefs_doc = BriefsDoc { briefs: briefs.clone() };
    fs::write(round_dir.join("briefs.yaml"), serde_yaml::to_string(&briefs_doc)?)?;
    println!("  {} brief(s) proposed", briefs.len());

    let generated = generate_all(&briefs, candidates, gen_cmd, &round_dir);

    write_proof_sheet(&round_dir, &edition_label, &briefs, &generated)?;
    let failures = write_round_yaml(&round_dir, &edition_label, &generated)?;

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
         (cover.art_path / opener_art.path / closing_plates), historic images are \
         never deleted."
    );

    let all_failed = !generated.is_empty() && failures == generated.len();
    Ok(if all_failed { 1 } else { 0 })
}
