// Port of tools/produce.py's `run` subcommand — sources in, edition content
// out, no state outside memory, plain output files. If it dies, rerun with
// --resume; pieces whose final.md already exists are skipped.

use crate::caller::{Caller, ModelSpec};
use anyhow::{anyhow, bail, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, OnceLock};
use std::thread;
use std::time::Instant;

const MAX_REWRITE_ROUNDS: u32 = 2;

pub const INLINE_PREAMBLE: &str = "You are running non-interactively with NO file access and NO tools. Every\ndocument you need is inlined below. If an included instruction tells you to\nread a file or path, the content of that file is already included here —\nnever claim to have read anything that is not inlined.";

/// Which lenses run on what, and which may see the source. Source-blindness
/// is enforced by construction: a blind lens's prompt simply never contains
/// the source text.
#[derive(Clone, Copy)]
struct LensSpec {
    file: &'static str,
    sources: bool,
}

fn article_lenses() -> Vec<(String, LensSpec)> {
    vec![
        ("worth".to_string(), LensSpec { file: "worth-review.md", sources: true }),
        ("evidence".to_string(), LensSpec { file: "evidence-review.md", sources: true }),
        ("mechanics".to_string(), LensSpec { file: "mechanics-review.md", sources: false }),
        ("shape".to_string(), LensSpec { file: "shape-review.md", sources: false }),
        ("craft".to_string(), LensSpec { file: "craft-review.md", sources: false }),
    ]
}

fn explainer_lenses() -> Vec<(String, LensSpec)> {
    vec![("teaching".to_string(), LensSpec { file: "teaching-review.md", sources: true })]
}

fn editorial_lenses() -> Vec<(String, LensSpec)> {
    article_lenses()
        .into_iter()
        .filter(|(k, _)| k == "mechanics" || k == "shape" || k == "craft")
        .collect()
}

fn writer_prompt_file(mode: &str) -> Result<&'static str> {
    match mode {
        "faithful_synthesis" => Ok("faithful-synthesis.md"),
        "faithful_edit" => Ok("faithful-edit.md"),
        "in_a_nutshell" => Ok("in-a-nutshell.md"),
        other => bail!("unknown content_mode '{other}'"),
    }
}

pub(crate) fn section(title: &str, body: &str) -> String {
    format!("\n\n========== {title} ==========\n\n{}\n", body.trim())
}

fn read(path: &Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

fn prompts_path(file: &str) -> PathBuf {
    PathBuf::from("prompts").join(file)
}

fn docs_path(file: &str) -> PathBuf {
    PathBuf::from("docs").join(file)
}

fn source_text(source_id: &str) -> Result<String> {
    let path = PathBuf::from("library/sources").join(source_id).join("extracted.md");
    if !path.exists() {
        bail!("no extraction for source '{source_id}' at {}", path.display());
    }
    read(&path)
}

/// An optional style overlay (`--style <path>`) appended to the writing pack,
/// so a run can wear a different voice without editing the house docs.
static STYLE_OVERLAY: OnceLock<Option<PathBuf>> = OnceLock::new();

fn writing_pack() -> Result<String> {
    let mut pack = section("docs/WRITING_STYLE.md", &read(&docs_path("WRITING_STYLE.md"))?)
        + &section("docs/WRITING_RULES.md", &read(&docs_path("WRITING_RULES.md"))?);
    if let Some(Some(path)) = STYLE_OVERLAY.get() {
        pack += &section(&format!("style overlay: {}", path.display()), &read(path)?);
    }
    Ok(pack)
}

fn value_to_string(v: &serde_yaml::Value) -> Option<String> {
    match v {
        serde_yaml::Value::String(s) => Some(s.clone()),
        serde_yaml::Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

fn severity_of(finding: &serde_yaml::Value) -> String {
    match finding.get("severity") {
        Some(serde_yaml::Value::String(s)) => s.to_lowercase(),
        Some(serde_yaml::Value::Number(n)) => n.to_string().to_lowercase(),
        Some(serde_yaml::Value::Bool(b)) => b.to_string().to_lowercase(),
        _ => String::new(),
    }
}

/// The writer prompts end replies with working notes below this marker;
/// everything from it on is scratch and never reaches disk, judges, or print.
const SCRATCH_MARKER: &str = "<!-- SCRATCH: not part of the manuscript -->";

fn extract_manuscript(reply: &str, label: &str) -> Result<String> {
    let re = Regex::new(r"(?s)<manuscript>(.*?)</manuscript>").unwrap();
    let last = re
        .captures_iter(reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no <manuscript> block"))?;
    let body = last.split(SCRATCH_MARKER).next().unwrap_or(&last);
    Ok(format!("{}\n", body.trim()))
}

/// A lens's yaml report — a mapping guaranteed to have a `findings` sequence
/// (never null, per extract_findings normalization below).
fn extract_findings(reply: &str, label: &str) -> Result<serde_yaml::Value> {
    let re = Regex::new(r"(?s)```ya?ml\s*\n(.*?)```").unwrap();
    let fence = re
        .captures_iter(reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no yaml findings block"))?;
    let mut data: serde_yaml::Value =
        serde_yaml::from_str(&fence).with_context(|| format!("{label}: invalid yaml in findings block"))?;
    let map = data
        .as_mapping_mut()
        .ok_or_else(|| anyhow!("{label}: yaml block has no findings key"))?;
    let key = serde_yaml::Value::String("findings".to_string());
    if !map.contains_key(&key) {
        bail!("{label}: yaml block has no findings key");
    }
    let normalized = match map.get(&key) {
        Some(serde_yaml::Value::Null) | None => serde_yaml::Value::Sequence(vec![]),
        Some(other) => other.clone(),
    };
    map.insert(key, normalized);
    Ok(data)
}

const LOOP_SEVERITIES: [&str; 2] = ["blocking", "major"];

/// Findings at blocking/major severity across a set of lens reports, each
/// tagged with the lens that raised it (lens field first, mirroring
/// produce.py's `{"lens": lens, **finding}`).
fn loop_findings(reports: &[(String, serde_yaml::Value)]) -> Vec<serde_yaml::Value> {
    let mut hits = Vec::new();
    for (lens, report) in reports {
        let Some(findings) = report.get("findings").and_then(|v| v.as_sequence()) else {
            continue;
        };
        for finding in findings {
            if LOOP_SEVERITIES.contains(&severity_of(finding).as_str()) {
                let mut new_map = serde_yaml::Mapping::new();
                new_map.insert(serde_yaml::Value::String("lens".to_string()), serde_yaml::Value::String(lens.clone()));
                if let Some(fields) = finding.as_mapping() {
                    for (k, v) in fields {
                        new_map.insert(k.clone(), v.clone());
                    }
                }
                hits.push(serde_yaml::Value::Mapping(new_map));
            }
        }
    }
    hits
}

fn ordered_mapping(pairs: &[(String, serde_yaml::Value)]) -> serde_yaml::Value {
    let mut map = serde_yaml::Mapping::new();
    for (k, v) in pairs {
        map.insert(serde_yaml::Value::String(k.clone()), v.clone());
    }
    serde_yaml::Value::Mapping(map)
}

fn writer_prompt(
    article: &serde_yaml::Value,
    sources: &[(String, String)],
    draft: Option<&str>,
    findings: Option<&[serde_yaml::Value]>,
) -> Result<String> {
    let mode = article
        .get("content_mode")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("article missing content_mode"))?;
    let file = writer_prompt_file(mode)?;
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &section(&format!("prompts/{file}"), &read(&prompts_path(file))?);
    out += &writing_pack()?;
    out += &section("edition.yaml article row", &serde_yaml::to_string(article)?);
    for (sid, text) in sources {
        out += &section(&format!("source extraction: {sid}"), text);
    }
    if let Some(draft) = draft {
        out += &section("current manuscript (to revise)", draft);
        let findings_yaml = serde_yaml::to_string(&findings.unwrap_or(&[]))?;
        out += &section("review findings to address", &findings_yaml);
        out += "\nRevise the manuscript to resolve every finding above without breaking \
                the writing rules. Return the complete revised manuscript between \
                <manuscript> and </manuscript> tags.";
    } else {
        out += "\nFollow the production prompt above (including its pre-draft answers, \
                written before the manuscript). Return the complete manuscript between \
                <manuscript> and </manuscript> tags.";
    }
    Ok(out)
}

fn judge_prompt(
    spec: &LensSpec,
    piece_label: &str,
    manuscript: &str,
    article_yaml: Option<&str>,
    sources: &[(String, String)],
) -> Result<String> {
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &section(&format!("prompts/{}", spec.file), &read(&prompts_path(spec.file))?);
    if let Some(article_yaml) = article_yaml {
        out += &section("edition.yaml article row", article_yaml);
    }
    out += &section(&format!("manuscript: {piece_label}"), manuscript);
    if spec.sources {
        for (sid, text) in sources {
            out += &section(&format!("pinned source extraction: {sid}"), text);
        }
    }
    out += "\nApply your lens exactly as specified. End your reply with the yaml findings \
            block in the format the lens prompt defines (```yaml ... ```), with \
            `findings: []` for a clean pass.";
    Ok(out)
}

fn editorial_prompt(
    draft: Option<&str>,
    findings: Option<&[serde_yaml::Value]>,
    articles_final: &[(String, String)],
) -> Result<String> {
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &section("prompts/opening-editorial.md", &read(&prompts_path("opening-editorial.md"))?);
    out += &writing_pack()?;
    for (aid, text) in articles_final {
        out += &section(&format!("accepted article: {aid}"), text);
    }
    if let Some(draft) = draft {
        out += &section("current editorial (to revise)", draft);
        out += &section("review findings to address", &serde_yaml::to_string(&findings.unwrap_or(&[]))?);
        out += "\nRevise the editorial to resolve every finding. Return it between \
                <manuscript> and </manuscript> tags.";
    } else {
        out += "\nWrite the opening editorial per the prompt above. Return it between \
                <manuscript> and </manuscript> tags.";
    }
    Ok(out)
}

/// Judge every lens in parallel (one OS thread per lens, capped in-flight by
/// the Caller's own semaphore), preserving `lenses`' order in the result.
#[allow(clippy::too_many_arguments)]
fn judge_all(
    caller: &Arc<Caller>,
    judge_model: &ModelSpec,
    piece_label: &str,
    manuscript: &str,
    lenses: &[(String, LensSpec)],
    article_yaml: Option<&str>,
    sources: &[(String, String)],
    round_no: u32,
) -> Result<Vec<(String, serde_yaml::Value)>> {
    let mut handles = Vec::new();
    for (lens, spec) in lenses {
        let prompt = judge_prompt(spec, piece_label, manuscript, article_yaml, sources)?;
        let caller = Arc::clone(caller);
        let judge_model = judge_model.clone();
        let label = format!("{piece_label} r{round_no} judge:{lens}");
        let parse_label = format!("{piece_label}:{lens}");
        let lens_owned = lens.clone();
        handles.push(thread::spawn(move || -> Result<(String, serde_yaml::Value)> {
            let report = caller.call_with_parse(&label, &judge_model, &prompt, |r| extract_findings(r, &parse_label))?;
            Ok((lens_owned, report))
        }));
    }
    let mut results = Vec::with_capacity(handles.len());
    for h in handles {
        results.push(h.join().map_err(|_| anyhow!("judge thread panicked"))??);
    }
    Ok(results)
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct RoundStatus {
    round: u32,
    words: usize,
    loop_findings: usize,
    all_findings: usize,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct PieceStatus {
    piece: String,
    rounds: Vec<RoundStatus>,
    state: String,
    #[serde(default)]
    open_findings: Vec<serde_yaml::Value>,
}

/// Write -> judge -> rewrite loop for one article or the editorial.
#[allow(clippy::too_many_arguments)]
fn produce_piece(
    caller: &Arc<Caller>,
    run_dir: &Path,
    piece_id: &str,
    article: Option<&serde_yaml::Value>,
    lenses: &[(String, LensSpec)],
    sources: &[(String, String)],
    writer_model: &ModelSpec,
    judge_model: &ModelSpec,
) -> Result<PieceStatus> {
    let out = if article.is_none() {
        run_dir.join("editorial")
    } else {
        run_dir.join("articles").join(piece_id)
    };
    fs::create_dir_all(&out)?;
    let final_path = out.join("final.md");
    if final_path.exists() {
        println!("  {piece_id}: final.md exists, skipping (resume)");
        let text = read(&out.join("status.yaml"))?;
        let status: PieceStatus = serde_yaml::from_str(&text)?;
        return Ok(status);
    }

    let article_yaml = match article {
        Some(a) => Some(serde_yaml::to_string(a)?),
        None => None,
    };

    let mut status = PieceStatus {
        piece: piece_id.to_string(),
        rounds: Vec::new(),
        state: "in_progress".to_string(),
        open_findings: Vec::new(),
    };
    let mut draft: Option<String> = None;
    let mut findings: Option<Vec<serde_yaml::Value>> = None;
    let mut round_no: u32 = 1;
    loop {
        let findings_nonempty = findings.as_ref().is_some_and(|f| !f.is_empty());
        if draft.is_none() || findings_nonempty {
            let verb = if draft.is_none() { "write" } else { "rewrite" };
            let label = format!("{piece_id} r{round_no} {verb}");
            let prompt = if let Some(article) = article {
                writer_prompt(article, sources, draft.as_deref(), findings.as_deref())?
            } else {
                editorial_prompt(draft.as_deref(), findings.as_deref(), sources)?
            };
            let parse_label = label.clone();
            let new_draft = caller.call_with_parse(&label, writer_model, &prompt, |r| extract_manuscript(r, &parse_label))?;
            draft = Some(new_draft);
        }
        let draft_text = draft.clone().expect("draft populated above");
        fs::write(out.join(format!("draft-{round_no}.md")), &draft_text)?;

        let reports = judge_all(caller, judge_model, piece_id, &draft_text, lenses, article_yaml.as_deref(), sources, round_no)?;
        fs::write(out.join(format!("findings-{round_no}.yaml")), serde_yaml::to_string(&ordered_mapping(&reports))?)?;

        let hits = loop_findings(&reports);
        let all_findings_count: usize = reports
            .iter()
            .map(|(_, r)| r.get("findings").and_then(|v| v.as_sequence()).map(|s| s.len()).unwrap_or(0))
            .sum();
        status.rounds.push(RoundStatus {
            round: round_no,
            words: draft_text.split_whitespace().count(),
            loop_findings: hits.len(),
            all_findings: all_findings_count,
        });

        if hits.is_empty() {
            status.state = "clean".to_string();
            findings = None;
            break;
        }
        if round_no > MAX_REWRITE_ROUNDS {
            status.state = "rounds_exhausted".to_string();
            findings = Some(hits);
            break;
        }
        findings = Some(hits);
        round_no += 1;
    }
    fs::write(&final_path, draft.as_deref().unwrap_or(""))?;
    status.open_findings = findings.unwrap_or_default();
    fs::write(out.join("status.yaml"), serde_yaml::to_string(&status)?)?;
    println!("  {piece_id}: {} after {} round(s)", status.state, status.rounds.len());
    Ok(status)
}

#[derive(Serialize, Deserialize, Debug)]
struct Plan {
    edition: serde_yaml::Value,
    articles: Vec<serde_yaml::Value>,
}

pub fn run_edition(
    plan_path: &Path,
    resume: Option<PathBuf>,
    only: Option<HashSet<String>>,
    writer_model: &ModelSpec,
    judge_model: &ModelSpec,
    style: Option<PathBuf>,
) -> Result<i32> {
    if let Some(path) = &style {
        if !path.exists() {
            bail!("style overlay not found: {}", path.display());
        }
    }
    let _ = STYLE_OVERLAY.set(style.clone());
    let plan_text = read(plan_path)?;
    let plan: Plan = serde_yaml::from_str(&plan_text).context("parsing plan.yaml")?;
    let edition_id = plan
        .edition
        .get("id")
        .and_then(value_to_string)
        .ok_or_else(|| anyhow!("plan.edition.id missing or not a string/number"))?;

    // Runs live inside the edition dir, name-sortable: editions/<ed>/run-<ts>/
    let edition_dir = plan_path.parent().map(PathBuf::from).unwrap_or_default();
    let run_dir = resume
        .unwrap_or_else(|| edition_dir.join(format!("run-{}", crate::caller::now_stamp())));
    fs::create_dir_all(&run_dir)?;
    fs::write(run_dir.join("plan.yaml"), serde_yaml::to_string(&plan)?)?;
    let caller = Arc::new(Caller::new(&run_dir));
    let started = Instant::now();
    println!("run dir: {}", run_dir.display());

    let articles: Vec<serde_yaml::Value> = plan
        .articles
        .into_iter()
        .filter(|a| match &only {
            None => true,
            Some(ids) => a.get("id").and_then(|v| v.as_str()).map(|s| ids.contains(s)).unwrap_or(false),
        })
        .collect();

    let mut handles = Vec::new();
    for article in &articles {
        let article_owned = article.clone();
        let caller = Arc::clone(&caller);
        let run_dir = run_dir.clone();
        let writer_model = writer_model.clone();
        let judge_model = judge_model.clone();
        handles.push(thread::spawn(move || -> Result<PieceStatus> {
            let id = article_owned
                .get("id")
                .and_then(|v| v.as_str())
                .ok_or_else(|| anyhow!("article missing id"))?
                .to_string();
            let content_mode = article_owned.get("content_mode").and_then(|v| v.as_str()).unwrap_or("");
            let mut lenses = article_lenses();
            if content_mode == "in_a_nutshell" {
                lenses.extend(explainer_lenses());
            }
            let source_ids = article_owned
                .get("source_ids")
                .and_then(|v| v.as_sequence())
                .ok_or_else(|| anyhow!("article '{id}' missing source_ids"))?;
            let mut sources = Vec::new();
            for sid_v in source_ids {
                let sid = sid_v
                    .as_str()
                    .ok_or_else(|| anyhow!("non-string source id in article '{id}'"))?
                    .to_string();
                let text = source_text(&sid)?;
                sources.push((sid, text));
            }
            produce_piece(&caller, &run_dir, &id, Some(&article_owned), &lenses, &sources, &writer_model, &judge_model)
        }));
    }

    let mut statuses = Vec::new();
    let mut failures: Vec<(String, String)> = Vec::new();
    for (article, handle) in articles.iter().zip(handles) {
        let id = article.get("id").and_then(|v| v.as_str()).unwrap_or("?").to_string();
        match handle.join() {
            Ok(Ok(status)) => statuses.push(status),
            Ok(Err(e)) => {
                eprintln!("  FAILED {id}: {e}");
                failures.push((id, e.to_string()));
            }
            Err(_) => {
                eprintln!("  FAILED {id}: worker thread panicked");
                failures.push((id, "worker thread panicked".to_string()));
            }
        }
    }

    let mut finals: Vec<(String, String)> = Vec::new();
    for article in &articles {
        if let Some(id) = article.get("id").and_then(|v| v.as_str()) {
            let fp = run_dir.join("articles").join(id).join("final.md");
            if fp.exists() {
                finals.push((id.to_string(), read(&fp)?));
            }
        }
    }

    let mut editorial_status: Option<PieceStatus> = None;
    if !finals.is_empty() && failures.is_empty() {
        match produce_piece(&caller, &run_dir, "editorial", None, &editorial_lenses(), &finals, writer_model, judge_model) {
            Ok(st) => editorial_status = Some(st),
            Err(e) => {
                eprintln!("  FAILED editorial: {e}");
                failures.push(("editorial".to_string(), e.to_string()));
            }
        }
    }

    let mut edition_report: Option<serde_yaml::Value> = None;
    if !finals.is_empty() {
        let mut pieces = finals.clone();
        let editorial_final = run_dir.join("editorial/final.md");
        if editorial_final.exists() {
            pieces.push(("editorial".to_string(), read(&editorial_final)?));
        }
        let mut prompt = String::new();
        prompt += INLINE_PREAMBLE;
        prompt += &section("prompts/edition-review.md", &read(&prompts_path("edition-review.md"))?);
        prompt += &section("edition plan", &serde_yaml::to_string(&plan.edition)?);
        for (pid, text) in &pieces {
            prompt += &section(&format!("piece: {pid}"), text);
        }
        prompt += "\nReview the edition as specified. End with the yaml findings block (```yaml ... ```).";
        match caller.call_with_parse("edition-review", judge_model, &prompt, |r| extract_findings(r, "edition-review")) {
            Ok(report) => {
                fs::write(run_dir.join("edition-review.yaml"), serde_yaml::to_string(&report)?)?;
                edition_report = Some(report);
            }
            Err(e) => {
                eprintln!("  FAILED edition-review: {e}");
                failures.push(("edition-review".to_string(), e.to_string()));
            }
        }
    }

    let minutes = started.elapsed().as_secs_f64() / 60.0;
    let mut lines = vec![
        format!("# Run summary — edition {edition_id}"),
        String::new(),
        format!("- {} model calls, ${:.2}, {:.1} minutes", caller.calls(), caller.total_cost(), minutes),
        format!("- writer `{}`, judges `{}`{}", writer_model.full, judge_model.full,
            match &style { Some(p) => format!(", style overlay `{}`", p.display()), None => String::new() }),
        String::new(),
        "| piece | state | rounds | words | open findings |".to_string(),
        "|---|---|---|---|---|".to_string(),
    ];
    let mut all_statuses = statuses;
    if let Some(es) = editorial_status {
        all_statuses.push(es);
    }
    for st in &all_statuses {
        let last = st.rounds.last();
        let words = last.map(|r| r.words.to_string()).unwrap_or_else(|| "—".to_string());
        lines.push(format!("| {} | {} | {} | {} | {} |", st.piece, st.state, st.rounds.len(), words, st.open_findings.len()));
    }
    for (pid, err) in &failures {
        let short: String = err.chars().take(80).collect();
        lines.push(format!("| {pid} | **FAILED** | — | — | {short} |"));
    }
    if let Some(report) = &edition_report {
        let n = report.get("findings").and_then(|v| v.as_sequence()).map(|s| s.len()).unwrap_or(0);
        lines.push(String::new());
        lines.push(format!("Edition review: {n} finding(s) — see edition-review.yaml"));
    }
    let summary_text = lines.join("\n") + "\n";
    fs::write(run_dir.join("summary.md"), &summary_text)?;
    println!("\n{}", run_dir.join("summary.md").display());
    println!("{}", lines.join("\n"));

    Ok(if failures.is_empty() { 0 } else { 1 })
}
