use crate::caller::{Caller, ModelSpec};
use crate::produce::{self, INLINE_PREAMBLE};
use anyhow::{anyhow, bail, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::thread;

const GEN_CONCURRENCY: usize = 8;

fn read(path: &Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

fn prompts_path(file: &str) -> PathBuf {
    PathBuf::from("prompts").join(file)
}

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
        0 => bail!("no edition directory matching 'editions/{edition}' or 'editions/{edition}*'"),
        1 => Ok(matches.remove(0)),
        _ => {
            let names: Vec<String> = matches.iter().map(|p| p.display().to_string()).collect();
            bail!(
                "edition '{edition}' matches multiple directories: {}",
                names.join(", ")
            )
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Brief {
    id: String,
    #[serde(alias = "slot")]
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

    #[serde(default, skip_serializing_if = "Option::is_none")]
    cast_references: Option<Vec<String>>,
}

#[derive(Debug, Deserialize, Serialize)]
struct BriefsDoc {
    briefs: Vec<Brief>,
}

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

#[derive(Debug, Clone, Deserialize)]
struct CastMember {
    name: String,
    prompt: String,

    #[serde(default)]
    reference: Option<String>,
}

fn cast_members(art_direction_text: &str) -> Result<Vec<CastMember>> {
    let doc: serde_yaml::Value = serde_yaml::from_str(art_direction_text)
        .context("parsing art direction file for direction.cast")?;
    match doc.get("direction").and_then(|d| d.get("cast")) {
        Some(v) => serde_yaml::from_value(v.clone())
            .context("direction.cast entries need `name` and `prompt`"),
        None => Ok(Vec::new()),
    }
}

fn cast_license(art_direction_text: &str) -> Result<HashMap<String, String>> {
    let doc: serde_yaml::Value = serde_yaml::from_str(art_direction_text)
        .context("parsing art direction file for direction.cast_license")?;
    let map: HashMap<String, String> =
        match doc.get("direction").and_then(|d| d.get("cast_license")) {
            Some(v) => serde_yaml::from_value(v.clone())
                .context("direction.cast_license must map purposes to license text")?,
            None => HashMap::new(),
        };
    for k in map.keys() {
        if !matches!(k.as_str(), "cover" | "opener" | "tail" | "closing") {
            bail!("direction.cast_license has unknown purpose '{k}'");
        }
    }
    Ok(map)
}

fn inject_cast(briefs: &mut [Brief], cast: &[CastMember], license: &HashMap<String, String>) {
    for brief in briefs.iter_mut() {
        let named: Vec<&CastMember> = cast
            .iter()
            .filter(|m| brief.prompt.to_lowercase().contains(&m.name.to_lowercase()))
            .collect();
        if named.is_empty() {
            continue;
        }
        let preamble = match license.get(&brief.purpose) {
            Some(_) => "Recurring cast — identities below are canon:",
            None => "Recurring cast — draw exactly as specified, never redesign:",
        };
        let mut block: String = std::iter::once(preamble.to_string())
            .chain(named.iter().map(|m| m.prompt.trim().to_string()))
            .collect::<Vec<_>>()
            .join(" ");
        if let Some(l) = license.get(&brief.purpose) {
            block += &format!(
                "\n\nThis slot is licensed to vary presentation, overriding the \
                 fixed outfits above where they conflict: {}",
                l.trim()
            );
        }
        brief.prompt = format!("{}\n\n{block}", brief.prompt.trim_end());
        let mut refs: Vec<String> = named.iter().filter_map(|m| m.reference.clone()).collect();
        refs.dedup();
        if !refs.is_empty() {
            brief.cast_references = Some(refs);
        }
    }
}

fn validate_cast_named(briefs: &[Brief], cast: &[CastMember], label: &str) -> Result<()> {
    if cast.is_empty() {
        return Ok(());
    }
    for b in briefs {
        if b.purpose == "cover" {
            continue;
        }
        let names_one = cast
            .iter()
            .any(|m| b.prompt.to_lowercase().contains(&m.name.to_lowercase()));
        if !names_one {
            let names: Vec<&str> = cast.iter().map(|m| m.name.as_str()).collect();
            bail!(
                "{label}: interior brief '{}' names no cast member ({}) — every \
                 interior prompt must name each cast member who appears, by name",
                b.id,
                names.join(", ")
            );
        }
    }
    Ok(())
}

fn ensure_ref_placeholder(gen_cmd: &str, briefs: &[Brief]) -> Result<()> {
    let needs = briefs
        .iter()
        .any(|b| b.cast_references.as_ref().is_some_and(|r| !r.is_empty()));
    if needs && !gen_cmd.contains("{ref}") {
        bail!(
            "the cast defines reference images but --gen-cmd has no {{ref}} \
             placeholder; add one (e.g. --ref '{{ref}}') or remove the \
             `reference` keys from the art direction's cast"
        );
    }
    Ok(())
}

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
        out.extend(
            doc.briefs
                .into_iter()
                .filter(|b| purposes.contains(&b.purpose)),
        );
    }
    Ok(out)
}

fn build_brief_prompt(
    edition_yaml_text: &str,
    candidates: u32,
    only: Option<&[String]>,
    articles: Option<&[String]>,
    rejected: &[Brief],
    note: Option<&str>,
) -> Result<String> {
    let process_doc = read(&prompts_path("illustrations.md"))?;
    let brief_doc = read(&prompts_path("cover-art-candidates.md"))?;
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &produce::section("prompts/illustrations.md", &process_doc);
    out += &produce::section("prompts/cover-art-candidates.md", &brief_doc);
    let mut cast = Vec::new();
    if let Some((path, text)) = art_direction_section(edition_yaml_text)? {
        cast = cast_members(&text)?;
        out += &produce::section(&path, &text);
    }
    out += &produce::section("edition.yaml", edition_yaml_text);
    if !cast.is_empty() {
        let names: Vec<&str> = cast.iter().map(|m| m.name.as_str()).collect();
        out += &format!(
            "\nThe art direction defines a canonical recurring cast: {}. Never \
             describe their appearance in a prompt — the pipeline appends each \
             member's canonical description verbatim to every prompt that \
             names the member. Name each cast member who appears in a scene \
             (the direction's constraints say who must appear), and give only \
             pose, action, expression, props, and setting; an interior brief \
             naming no cast member is rejected. Prompts still restate the \
             direction's style, palette, constraints, and avoid-list.\n",
            names.join(", ")
        );
    }
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
    if let Some(ids) = articles {
        out += &format!(
            "\nPropose ONLY the opener and tail briefs (one of each) for these \
             articles, which were added to the edition after its art slate was \
             made: {}. Every other article, the cover, and the closing plates \
             already have art; do not propose anything for them. Keep the \
             edition's established art direction and shared constraints.\n\n\
             You are not generating images yourself — a later pipeline step \
             will run each brief through an image generator {candidates} \
             time(s) to produce that many variants.\n\n",
            ids.join(", ")
        );
    } else {
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
    }
    out += "Return exactly one fenced yaml code block (```yaml ... ```) and nothing \
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

#[derive(Debug, Clone, Serialize)]
struct GeneratedItem {
    brief: String,
    variant: u32,
    file: String,
    ok: bool,
}

fn shell_single_quote_escape(s: &str) -> String {
    s.replace('\'', "'\\''")
}

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
    let refs = brief
        .cast_references
        .as_deref()
        .unwrap_or_default()
        .join(" ");
    let cmd_str = gen_cmd
        .replace("{prompt}", &escaped_prompt)
        .replace("{out}", &out_path.to_string_lossy())
        .replace("{ref}", &shell_single_quote_escape(&refs));
    (filename, cmd_str)
}

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

fn run_gen_command(cmd_str: &str, out_path: &Path) -> Result<(), String> {
    let output = Command::new("sh")
        .arg("-c")
        .arg(cmd_str)
        .output()
        .map_err(|e| format!("failed to spawn gen-cmd: {e}"))?;
    if !output.status.success() {
        let err_text = String::from_utf8_lossy(&output.stderr);
        let truncated: String = err_text.trim().chars().take(200).collect();
        return Err(format!(
            "gen-cmd exited with {}: {truncated}",
            output.status
        ));
    }
    match fs::metadata(out_path) {
        Ok(m) if m.len() > 0 => Ok(()),
        Ok(_) => Err("output file is empty".to_string()),
        Err(_) => Err("output file was not created".to_string()),
    }
}

fn generate_all(
    briefs: &[Brief],
    candidates: u32,
    gen_cmd: &str,
    round_dir: &Path,
) -> Vec<GeneratedItem> {
    let jobs: Vec<(String, u32, String, String)> = briefs
        .iter()
        .flat_map(|b| {
            (1..=candidates).map(move |v| {
                let (file, cmd) = candidate_command(gen_cmd, b, v, round_dir);
                (b.id.clone(), v, file, cmd)
            })
        })
        .collect();
    let next = AtomicUsize::new(0);
    let results = Mutex::new(Vec::with_capacity(jobs.len()));
    thread::scope(|s| {
        for _ in 0..GEN_CONCURRENCY.min(jobs.len()) {
            s.spawn(|| loop {
                let i = next.fetch_add(1, Ordering::Relaxed);
                let Some((brief, variant, file, cmd)) = jobs.get(i) else {
                    break;
                };
                let out_path = round_dir.join(file);
                let ok = if fs::metadata(&out_path)
                    .map(|m| m.len() > 0)
                    .unwrap_or(false)
                {
                    println!("    {brief} v{variant}: kept (already on disk)");
                    true
                } else {
                    match run_gen_command(cmd, &out_path) {
                        Ok(()) => {
                            println!("    {brief} v{variant}: ok");
                            true
                        }
                        Err(e) => {
                            eprintln!("    {brief} v{variant}: FAILED — {e}");
                            false
                        }
                    }
                };
                let item = GeneratedItem {
                    brief: brief.clone(),
                    variant: *variant,
                    file: file.clone(),
                    ok,
                };
                results.lock().unwrap().push((i, item));
            });
        }
    });
    let mut results = results.into_inner().unwrap();
    results.sort_by_key(|(i, _)| *i);
    results.into_iter().map(|(_, item)| item).collect()
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
    let prompts_by_id: HashMap<&str, &str> = briefs
        .iter()
        .map(|b| (b.id.as_str(), b.prompt.as_str()))
        .collect();

    let mut html = String::new();
    html += "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n";
    html += &format!(
        "<title>Art proof sheet — {}</title>\n",
        html_escape(edition_label)
    );
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
    html += &format!(
        "<h1>Art proof sheet — {}</h1>\n",
        html_escape(edition_label)
    );
    html += "<div class=\"grid\">\n";
    for item in generated {
        let prompt = prompts_by_id
            .get(item.brief.as_str())
            .copied()
            .unwrap_or("");
        html += "<figure>\n";
        if item.ok {
            html += &format!(
                "<img src=\"{}\" loading=\"lazy\">\n",
                html_escape(&item.file)
            );
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

struct ShowcaseItem {
    round: String,
    file: String,
    brief_id: String,
    purpose: String,
    article_id: Option<String>,
    prompt: String,
    variant: u32,
    selected: bool,

    verdicts: Vec<MemberVerdict>,
}

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
    if let Some(plates) = edition_yaml
        .get("closing_plates")
        .and_then(|v| v.as_sequence())
    {
        for plate in plates {
            push(plate.get("art_path"));
        }
    }
    out
}

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
        let briefs: BriefsDoc = serde_yaml::from_str(&read(&briefs_path)?)
            .with_context(|| format!("parsing {}", briefs_path.display()))?;
        let by_id: HashMap<&str, &Brief> =
            briefs.briefs.iter().map(|b| (b.id.as_str(), b)).collect();
        let round: serde_yaml::Value = serde_yaml::from_str(&read(&round_path)?)
            .with_context(|| format!("parsing {}", round_path.display()))?;
        let check_path = round_dir.join("cast-check.yaml");
        let checks: HashMap<String, Vec<MemberVerdict>> = if check_path.exists() {
            let doc: CastCheckDoc = serde_yaml::from_str(&read(&check_path)?)
                .with_context(|| format!("parsing {}", check_path.display()))?;
            doc.results
                .into_iter()
                .map(|r| (r.file, r.verdicts))
                .collect()
        } else {
            HashMap::new()
        };
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
                verdicts: checks.get(file).cloned().unwrap_or_default(),
            });
        }
    }
    Ok(items)
}

fn write_showcase(edition_dir: &Path, edition_label: &str) -> Result<PathBuf> {
    let edition_yaml_path = edition_dir.join("edition.yaml");
    let mut cover_frame = CoverFrame {
        publication: crate::render::publication_name(Path::new(".")),
        headline: edition_label.to_string(),
        issue: edition_label.to_string(),
        date: String::new(),
    };
    let selected = if edition_yaml_path.exists() {
        let doc: serde_yaml::Value = serde_yaml::from_str(&read(&edition_yaml_path)?)
            .with_context(|| format!("parsing {}", edition_yaml_path.display()))?;
        if let Some(h) = doc
            .get("cover")
            .and_then(|c| c.get("headline"))
            .and_then(|v| v.as_str())
        {
            cover_frame.headline = h.to_string();
        }
        if let Some(n) = doc.get("issue_number").and_then(|v| v.as_u64()) {
            cover_frame.issue = format!("{n:03}");
        }
        if let Some(d) = doc.get("publication_date").and_then(|v| v.as_str()) {
            cover_frame.date = d.replace('-', " ");
        }
        selected_art_paths(&doc)
    } else {
        Vec::new()
    };
    let items = collect_showcase_items(edition_dir, &selected)?;

    let mut html = String::new();
    html += "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n";
    html += &format!(
        "<title>Art showcase — {}</title>\n",
        html_escape(edition_label)
    );
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
        .offbadge { position: absolute; top: 1rem; left: 1rem; background: #c73; color: #310; font-weight: bold;\n\
            font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 999px; }\n\
        figure.offmodel { border-color: #c73; }\n\
        .verdicts { margin-top: 0.4rem; font-size: 0.8rem; color: #c95; }\n\
        figcaption { margin-top: 0.5rem; font-size: 0.85rem; color: #aaa; }\n\
        details { margin-top: 0.4rem; }\n\
        details pre { white-space: pre-wrap; font-size: 0.8rem; color: #ccc; }\n\
        .empty { color: #777; font-style: italic; }\n\
        .rounds { font-size: 0.85rem; color: #9ab; }\n\
        figure.picked { border-color: #4ad; box-shadow: 0 0 0 2px #4ad; }\n\
        figure img { cursor: pointer; }\n\
        .btnrow { margin-top: 0.5rem; display: flex; gap: 0.4rem; flex-wrap: wrap; }\n\
        .btnrow a, .btnrow button, #basket button {\n\
            background: #2a2a2a; color: #ddd; border: 1px solid #444; border-radius: 4px;\n\
            font-size: 0.72rem; padding: 0.2rem 0.55rem; cursor: pointer; text-decoration: none; }\n\
        .btnrow a:hover, .btnrow button:hover, #basket button:hover { border-color: #4ad; color: #fff; }\n\
        #basket { position: fixed; left: 0; right: 0; bottom: 0; background: #181d20ee;\n\
            border-top: 1px solid #345; padding: 0.6rem 2rem; display: flex; gap: 0.5rem;\n\
            align-items: center; flex-wrap: wrap; backdrop-filter: blur(4px); }\n\
        #basket .count { font-size: 0.85rem; color: #9cd; margin-right: 0.5rem; }\n\
        #flash { font-size: 0.8rem; color: #4a4; margin-left: 0.5rem; }\n\
        body { padding-bottom: 4.5rem; }\n\
        .coverframe { aspect-ratio: 1 / 1.414; background: #f7f2e9; color: #14120f;\n\
            position: relative; padding: 6% 16% 5% 8%; box-sizing: border-box; overflow: hidden;\n\
            font-family: 'Archivo Black', 'Arial Black', -apple-system, sans-serif; cursor: pointer; }\n\
        .cf-spine { position: absolute; top: 0; right: 0; bottom: 0; width: 9%; background: #f05737;\n\
            display: flex; flex-direction: column; justify-content: space-between; align-items: center;\n\
            padding: 6% 0; box-sizing: border-box; }\n\
        .cf-issue, .cf-imprint { writing-mode: vertical-rl; font-size: 0.5rem; letter-spacing: 0.25em;\n\
            font-weight: 700; }\n\
        .cf-issue { color: #14120f; }\n\
        .cf-imprint { color: #f7f2e9; }\n\
        .cf-masthead { line-height: 0.95; margin-bottom: 7%; }\n\
        .cf-m1 { display: block; font-size: 1.5rem; letter-spacing: 0.01em; }\n\
        .cf-m2 { display: inline-block; font-size: 1.5rem; background: #14120f; color: #f7f2e9;\n\
            padding: 0 0.25rem; transform: skewX(-8deg); box-shadow: 0.22rem 0.22rem 0 #f05737;\n\
            margin-left: 12%; }\n\
        .cf-headline { line-height: 1.0; margin-bottom: 6%; }\n\
        .cf-headline span, .cf-headline em { display: block; font-style: normal;\n\
            font-size: 1.05rem; text-transform: uppercase; letter-spacing: 0.01em; }\n\
        .cf-headline em { color: #5b2fd8; margin-left: 9%; }\n\
        .cf-plate { width: 78%; margin: 0 auto; }\n\
        .coverframe img { width: 100%; height: auto; display: block; border-radius: 0; }\n\
        .cf-credits { font-size: 0.42rem; letter-spacing: 0.14em; color: #3a362f; margin-top: 5%;\n\
            font-family: -apple-system, sans-serif; font-weight: 600; }\n\
        .cf-date { position: absolute; bottom: 4%; left: 8%; font-size: 0.5rem;\n\
            letter-spacing: 0.2em; font-weight: 700; }\n\
        </style>\n</head>\n<body>\n";
    let mut rounds: Vec<&str> = items.iter().map(|i| i.round.as_str()).collect();
    rounds.sort();
    rounds.dedup();
    let rounds_line = rounds
        .iter()
        .map(|r| {
            let n = items.iter().filter(|i| i.round == *r).count();
            format!("{} ({n})", html_escape(r))
        })
        .collect::<Vec<_>>()
        .join(" · ");
    html += &format!(
        "<h1>Art showcase — {} ({} image(s))</h1>\n\
         <p class=\"rounds\">Rounds: {rounds_line}</p>\n\
         <p>Every generated candidate across every round. A green badge marks \
         what edition.yaml currently selects. Click an image to pick it for its \
         slot (cover, per-article opener/tail: one pick; closing plates: toggle). \
         The bar below copies commands to run from the repo root, and \
         edition.yaml lines for the picks. Give feedback per image as \
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
            let off: Vec<&MemberVerdict> = item
                .verdicts
                .iter()
                .filter(|v| v.verdict == "off_model")
                .collect();
            let mut classes = Vec::new();
            if item.selected {
                classes.push("selected");
            }
            if !off.is_empty() {
                classes.push("offmodel");
            }
            let repo_path = format!(
                "{}/art/rounds/{}/{}",
                edition_dir.display(),
                item.round,
                item.file
            );
            let slot = match item.purpose.as_str() {
                "cover" => "cover".to_string(),
                "closing" => format!("closing:{}", item.brief_id),
                p => format!(
                    "{p}:{}",
                    item.article_id.as_deref().unwrap_or(&item.brief_id)
                ),
            };
            html += &format!(
                "<figure class=\"{}\" data-path=\"{}\" data-slot=\"{}\">\n",
                classes.join(" "),
                html_escape(&repo_path),
                html_escape(&slot)
            );
            if item.selected {
                html += "<span class=\"badge\">SELECTED</span>\n";
            }
            if !off.is_empty() {
                let names: Vec<&str> = off.iter().map(|v| v.name.as_str()).collect();
                html += &format!(
                    "<span class=\"offbadge\">OFF-MODEL: {}</span>\n",
                    html_escape(&names.join(", "))
                );
            }
            let img_tag = format!(
                "<img src=\"rounds/{}/{}\" loading=\"lazy\">",
                html_escape(&item.round),
                html_escape(&item.file)
            );
            if item.purpose == "cover" {
                let mut words = cover_frame.headline.split_whitespace();
                let first = words.next().unwrap_or("");
                let rest = words.collect::<Vec<_>>().join(" ");
                html += &format!(
                    "<div class=\"coverframe\">\
                     <span class=\"cf-spine\"><span class=\"cf-issue\">ISSUE {issue}</span>\
                     <span class=\"cf-imprint\">{publication}</span></span>\
                     <div class=\"cf-masthead\">{masthead}</div>\
                     <div class=\"cf-headline\"><span>{first}</span><em>{rest}</em></div>\
                     <div class=\"cf-plate\">{img_tag}</div>\
                     <div class=\"cf-credits\">COVER CANDIDATE / {brief} v{variant}</div>\
                     <div class=\"cf-date\">{date}</div>\
                     </div>\n",
                    issue = html_escape(&cover_frame.issue),
                    publication = html_escape(&cover_frame.publication.to_uppercase()),
                    masthead = cover_frame
                        .publication
                        .split_whitespace()
                        .enumerate()
                        .map(|(i, w)| if i == 0 {
                            format!("<span class=\"cf-m1\">{}</span>", html_escape(w))
                        } else {
                            format!("<span class=\"cf-m2\">{}</span>", html_escape(w))
                        })
                        .collect::<String>(),
                    first = html_escape(first),
                    rest = html_escape(&rest),
                    brief = html_escape(&item.brief_id),
                    variant = item.variant,
                    date = html_escape(&cover_frame.date),
                );
            } else {
                html += &img_tag;
                html += "\n";
            }
            html += &format!(
                "<figcaption>{} v{} ({})</figcaption>\n",
                html_escape(&item.brief_id),
                item.variant,
                html_escape(&item.round)
            );
            html += &format!(
                "<div class=\"btnrow\"><a href=\"rounds/{}/{}\" target=\"_blank\">view</a>\
                 <button data-copy=\"path\">copy path</button>\
                 <button data-copy=\"preview\">preview cmd</button>\
                 <button data-copy=\"finder\">finder cmd</button></div>\n",
                html_escape(&item.round),
                html_escape(&item.file)
            );
            if !item.verdicts.is_empty() {
                let lines: Vec<String> = item
                    .verdicts
                    .iter()
                    .map(|v| format!("{}: {} — {}", v.name, v.verdict, v.reason))
                    .collect();
                html += &format!(
                    "<div class=\"verdicts\">{}</div>\n",
                    html_escape(&lines.join(" · "))
                );
            }
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
    html += SHOWCASE_BASKET;
    html += "</body>\n</html>\n";

    let path = edition_dir.join("art").join("showcase.html");
    fs::create_dir_all(path.parent().unwrap())?;
    fs::write(&path, html)?;
    Ok(path)
}

struct CoverFrame {
    publication: String,
    headline: String,
    issue: String,
    date: String,
}

const SHOWCASE_BASKET: &str = r#"<div id="basket">
<span class="count">0 picked</span>
<button data-bar="preview">open picked in Preview</button>
<button data-bar="finder">reveal picked in Finder</button>
<button data-bar="paths">copy picked paths</button>
<button data-bar="yaml">copy edition.yaml lines</button>
<button data-bar="clear">clear picks</button>
<span id="flash"></span>
</div>
<script>
(function () {
  var picks = {}; // slot -> array of paths (closing slots toggle, others hold one)
  var q = function (s) { return "'" + s.replace(/'/g, "'\\''") + "'"; };

  function figs() { return Array.prototype.slice.call(document.querySelectorAll('figure[data-path]')); }
  function repaint() {
    var chosen = {};
    Object.keys(picks).forEach(function (slot) {
      picks[slot].forEach(function (p) { chosen[p] = true; });
    });
    figs().forEach(function (f) {
      f.classList.toggle('picked', !!chosen[f.dataset.path]);
    });
    var n = Object.keys(chosen).length;
    document.querySelector('#basket .count').textContent = n + ' picked';
  }
  function pickedPaths() {
    var out = [];
    Object.keys(picks).sort().forEach(function (slot) {
      picks[slot].forEach(function (p) { out.push({ slot: slot, path: p }); });
    });
    return out;
  }
  function copy(text, label) {
    var done = function () {
      var flash = document.getElementById('flash');
      flash.textContent = 'copied ' + label;
      setTimeout(function () { flash.textContent = ''; }, 2500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); });
    } else { fallback(text); done(); }
  }
  function fallback(text) {
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  }
  function yamlLines() {
    return pickedPaths().map(function (e) {
      var s = e.slot, p = e.path;
      if (s === 'cover') return 'cover:\n  art_path: ' + p;
      if (s.indexOf('closing:') === 0) return '# ' + s.slice(8) + '\n- art_path: ' + p;
      var kind = s.split(':')[0], article = s.split(':').slice(1).join(':');
      if (kind === 'tail') return '# article ' + article + '\n  tail_art_path: ' + p;
      return '# article ' + article + '\n  opener_art:\n    path: ' + p;
    }).join('\n');
  }

  figs().forEach(function (f) {
    if (f.classList.contains('selected')) {
      var slot = f.dataset.slot;
      picks[slot] = (picks[slot] || []).concat([f.dataset.path]);
    }
    (f.querySelector('.coverframe') || f.querySelector('img')).addEventListener('click', function () {
      var slot = f.dataset.slot, p = f.dataset.path;
      var cur = picks[slot] || [];
      if (slot.indexOf('closing:') === 0) {
        picks[slot] = cur.indexOf(p) >= 0 ? cur.filter(function (x) { return x !== p; }) : cur.concat([p]);
      } else {
        picks[slot] = cur.length === 1 && cur[0] === p ? [] : [p];
      }
      repaint();
    });
    f.querySelectorAll('button[data-copy]').forEach(function (b) {
      b.addEventListener('click', function () {
        var p = f.dataset.path;
        if (b.dataset.copy === 'path') copy(p, 'path');
        if (b.dataset.copy === 'preview') copy('open -a Preview ' + q(p), 'Preview command');
        if (b.dataset.copy === 'finder') copy('open -R ' + q(p), 'Finder command');
      });
    });
  });
  document.querySelectorAll('#basket button[data-bar]').forEach(function (b) {
    b.addEventListener('click', function () {
      var entries = pickedPaths();
      if (b.dataset.bar === 'clear') { picks = {}; repaint(); return; }
      if (!entries.length) { copy('', 'nothing (no picks)'); return; }
      var paths = entries.map(function (e) { return e.path; });
      if (b.dataset.bar === 'paths') copy(paths.join('\n'), 'paths');
      if (b.dataset.bar === 'preview') copy('open -a Preview ' + paths.map(q).join(' '), 'Preview command');
      if (b.dataset.bar === 'finder') copy(paths.map(function (p) { return 'open -R ' + q(p); }).join('\n'), 'Finder commands');
      if (b.dataset.bar === 'yaml') copy(yamlLines(), 'edition.yaml lines');
    });
  });
  repaint();
})();
</script>
"#;

fn cast_sheet_prompt(
    direction: &serde_yaml::Value,
    cast: &[CastMember],
    note: Option<&str>,
) -> String {
    let field = |k: &str| {
        direction
            .get(k)
            .and_then(|v| v.as_str())
            .map(|s| s.trim().to_string())
            .unwrap_or_default()
    };
    let avoid: Vec<String> = direction
        .get("avoid")
        .and_then(|v| v.as_sequence())
        .map(|s| {
            s.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    let mut p = String::from(
        "An original character model sheet for a print magazine's recurring \
         illustrated cast, entirely wordless: no letters, numerals, labels, \
         captions, arrows, or watermarks anywhere. ",
    );
    let visual_language = field("visual_language");
    if !visual_language.is_empty() {
        p += &format!("Visual language: {visual_language} ");
    }
    let palette = field("palette");
    if !palette.is_empty() {
        p += &format!("Palette: {palette} ");
    }
    p += "Show every cast member together on one plain warm off-white sheet \
          at their true relative sizes: for each member a front view, a side \
          view, and a back view in a neutral standing pose, plus a small row \
          of three expressions, arranged in clean rows with generous spacing. \
          No scene, no background objects, no panel borders. ";
    p += "Cast:";
    for m in cast {
        p += &format!(" {}", m.prompt.trim());
    }
    if !avoid.is_empty() {
        p += &format!(" Avoid: {}.", avoid.join("; "));
    }
    if let Some(note) = note {
        p += &format!(" Editor's note: {}", note.trim());
    }
    p
}

fn cast_ref_href(repo_relative: &str) -> String {
    match repo_relative.strip_prefix("art-directions/") {
        Some(rest) => format!("../../{rest}"),
        None => format!("../../../{repo_relative}"),
    }
}

pub fn write_cast_showcase(direction_path: &Path) -> Result<PathBuf> {
    let text = read(direction_path)?;
    let cast = cast_members(&text)?;
    let stem = direction_path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .ok_or_else(|| anyhow!("no file stem in {}", direction_path.display()))?;
    let root = direction_path.parent().unwrap_or(Path::new("."));
    let rounds_root = root.join("rounds").join(&stem);

    let mut refs: Vec<String> = cast.iter().filter_map(|m| m.reference.clone()).collect();
    refs.dedup();
    let canon: Vec<(String, Vec<u8>)> = refs
        .iter()
        .filter_map(|r| fs::read(r).ok().map(|b| (r.clone(), b)))
        .collect();

    let mut round_dirs: Vec<PathBuf> = match fs::read_dir(&rounds_root) {
        Ok(entries) => entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.is_dir())
            .collect(),
        Err(_) => Vec::new(),
    };
    round_dirs.sort();
    round_dirs.reverse();

    let mut html = String::new();
    html += "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n";
    html += &format!("<title>Cast — {}</title>\n", html_escape(&stem));
    html += "<style>\n\
        body { font-family: -apple-system, sans-serif; margin: 2rem; background: #f6f2ea; color: #222; }\n\
        h1 { font-size: 1.3rem; }\n\
        h2 { font-size: 1.05rem; margin-top: 2.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }\n\
        p.hint { color: #666; max-width: 60rem; }\n\
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 1.25rem; }\n\
        figure { margin: 0; background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 0.75rem; position: relative;\n\
            box-shadow: 0 1px 4px rgba(0,0,0,.06); }\n\
        figure.canon { border-color: #1a6e62; box-shadow: 0 0 0 2px #1a6e62; }\n\
        figure img { width: 100%; height: auto; display: block; border-radius: 6px; cursor: zoom-in; }\n\
        .badge { position: absolute; top: 1.1rem; right: 1.1rem; background: #1a6e62; color: #eaf6f3; font-weight: bold;\n\
            font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 999px; }\n\
        figcaption { margin-top: 0.5rem; font-size: 0.85rem; color: #666; }\n\
        .empty { color: #888; font-style: italic; }\n\
        code { background: #eee; padding: 0.05rem 0.3rem; border-radius: 4px; }\n\
        </style>\n</head>\n<body>\n";
    html += &format!("<h1>Cast — {}</h1>\n", html_escape(&stem));
    html += &format!(
        "<p class=\"hint\">Judge the designs, not the poses. Approve a new sheet by \
         copying it over the <code>reference:</code> path in {} (the CANON badge \
         marks the variant whose bytes match the installed reference).</p>\n",
        html_escape(&direction_path.display().to_string())
    );

    html += "<h2>Current canon</h2>\n";
    if refs.is_empty() {
        html += "<p class=\"empty\">the cast defines no reference images yet</p>\n";
    } else {
        html += "<div class=\"grid\">\n";
        for r in &refs {
            html += "<figure class=\"canon\">\n<span class=\"badge\">CANON</span>\n";
            let href = cast_ref_href(r);
            html += &format!(
                "<a href=\"{0}\" target=\"_blank\"><img src=\"{0}\" loading=\"lazy\"></a>\n",
                html_escape(&href)
            );
            html += &format!("<figcaption>{}</figcaption>\n</figure>\n", html_escape(r));
        }
        html += "</div>\n";
    }

    let mut any_round = false;
    for round_dir in &round_dirs {
        let round_name = round_dir.file_name().unwrap().to_string_lossy().to_string();
        let round_path = round_dir.join("round.yaml");
        if !round_path.exists() {
            continue;
        }
        let round: serde_yaml::Value = serde_yaml::from_str(&read(&round_path)?)
            .with_context(|| format!("parsing {}", round_path.display()))?;
        let mut cells = String::new();
        for item in round
            .get("generated")
            .and_then(|v| v.as_sequence())
            .into_iter()
            .flatten()
        {
            let ok = item.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
            let file = item.get("file").and_then(|v| v.as_str()).unwrap_or("");
            let variant = item.get("variant").and_then(|v| v.as_u64()).unwrap_or(0);
            let path = round_dir.join(file);
            if !ok || file.is_empty() || !path.exists() {
                continue;
            }
            let is_canon = !canon.is_empty()
                && fs::read(&path)
                    .map(|b| canon.iter().any(|(_, c)| c == &b))
                    .unwrap_or(false);
            cells += &format!(
                "<figure class=\"{}\">\n",
                if is_canon { "canon" } else { "" }
            );
            if is_canon {
                cells += "<span class=\"badge\">CANON</span>\n";
            }
            cells += &format!(
                "<a href=\"{0}/{1}\" target=\"_blank\"><img src=\"{0}/{1}\" loading=\"lazy\"></a>\n",
                html_escape(&round_name),
                html_escape(file)
            );
            cells += &format!(
                "<figcaption>v{variant} ({})</figcaption>\n</figure>\n",
                html_escape(&round_name)
            );
        }
        if !cells.is_empty() {
            any_round = true;
            html += &format!(
                "<h2>Round {}</h2>\n<div class=\"grid\">\n{cells}</div>\n",
                html_escape(&round_name)
            );
        }
    }
    if !any_round {
        html += "<h2>Rounds</h2>\n<p class=\"empty\">no sheet candidates generated yet</p>\n";
    }
    html += "</body>\n</html>\n";

    fs::create_dir_all(&rounds_root)?;
    let path = rounds_root.join("showcase.html");
    fs::write(&path, html)?;
    Ok(path)
}

pub fn cast_sheet_run(
    direction_path: &Path,
    gen_cmd: Option<&str>,
    candidates: u32,
    dry_run: bool,
    showcase_only: bool,
    note: Option<&str>,
) -> Result<i32> {
    if showcase_only {
        let path = write_cast_showcase(direction_path)?;
        println!("cast showcase rebuilt: {}", path.display());
        return Ok(0);
    }
    let text = read(direction_path)?;
    let cast = cast_members(&text)?;
    if cast.is_empty() {
        bail!(
            "{} defines no direction.cast — nothing to sheet",
            direction_path.display()
        );
    }
    let doc: serde_yaml::Value = serde_yaml::from_str(&text)
        .with_context(|| format!("parsing {}", direction_path.display()))?;
    let direction = doc
        .get("direction")
        .ok_or_else(|| anyhow!("{} has no direction block", direction_path.display()))?;

    let stem = direction_path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .ok_or_else(|| anyhow!("no file stem in {}", direction_path.display()))?;
    let mut refs: Vec<String> = cast.iter().filter_map(|m| m.reference.clone()).collect();
    refs.dedup();
    let brief = Brief {
        id: format!("{stem}-cast-sheet"),
        purpose: "cast-sheet".to_string(),
        article_id: None,
        prompt: cast_sheet_prompt(direction, &cast, note),
        subject: None,
        composition: None,
        alt_text: None,
        credit: None,
        cast_references: if refs.is_empty() { None } else { Some(refs) },
    };
    let briefs = vec![brief];
    if let Some(cmd) = gen_cmd {
        ensure_ref_placeholder(cmd, &briefs)?;
    }

    let round_dir = PathBuf::from("art-directions")
        .join("rounds")
        .join(&stem)
        .join(crate::caller::now_stamp());
    if round_dir.exists() {
        bail!(
            "round directory already exists, refusing to touch it: {}",
            round_dir.display()
        );
    }
    fs::create_dir_all(&round_dir)
        .with_context(|| format!("creating round directory {}", round_dir.display()))?;
    println!("round dir: {}", round_dir.display());
    fs::write(
        round_dir.join("briefs.yaml"),
        serde_yaml::to_string(&BriefsDoc {
            briefs: briefs.clone(),
        })?,
    )?;

    let approval_note = format!(
        "approve by pointing every cast member's `reference:` in {} at the \
         chosen variant (conventionally copied to \
         art-directions/references/{stem}-cast.png).",
        direction_path.display()
    );

    if dry_run {
        write_round_yaml(&round_dir, &stem, true, &[])?;
        write_cast_showcase(direction_path)?;
        println!();
        println!("dry run: no image credits spent.");
        match gen_cmd {
            Some(cmd) => {
                let script = write_generate_script(&round_dir, &stem, &briefs, candidates, cmd)?;
                println!(
                    "run {} from the repo root when credits are available; {approval_note}",
                    script.display()
                );
            }
            None => println!(
                "no --gen-cmd recorded; the prompt is in {}/briefs.yaml — {approval_note}",
                round_dir.display()
            ),
        }
        return Ok(0);
    }
    let gen_cmd = gen_cmd.expect("clap requires --gen-cmd when not a dry run");
    let generated = generate_all(&briefs, candidates, gen_cmd, &round_dir);
    write_proof_sheet(&round_dir, &stem, &briefs, &generated)?;
    let failures = write_round_yaml(&round_dir, &stem, false, &generated)?;
    let showcase = write_cast_showcase(direction_path)?;
    println!();
    println!("open {}; {approval_note}", showcase.display());
    let all_failed = !generated.is_empty() && failures == generated.len();
    Ok(if all_failed { 1 } else { 0 })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct MemberVerdict {
    name: String,
    verdict: String,
    reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CastCheckResult {
    file: String,
    verdicts: Vec<MemberVerdict>,
}

#[derive(Serialize, Deserialize)]
struct CastCheckDoc {
    model: String,
    checked: String,
    results: Vec<CastCheckResult>,
}

fn cast_check_prompt(cast: &[CastMember], image_abs: &Path, license: Option<&str>) -> String {
    let mut p = String::from(
        "You are the on-model continuity check for a print magazine's \
         recurring illustrated cast. The canonical cast definitions:\n\n",
    );
    for m in cast {
        p += &format!("- {}\n", m.prompt.trim());
    }
    if let Some(l) = license {
        p += &format!(
            "\nThis image comes from a licensed slot. License: {} \
             Judge identity anchors only — wardrobe, apparent age, rendering \
             style, and mood are licensed and never count as deviations.\n",
            l.trim()
        );
    }
    p += &format!(
        "\nExamine the illustration image; if it is not already attached to \
         this conversation, view it with the Read tool at: {}\n\n\
         Judge each cast member's DESIGN strictly against its definition — \
         pose, action, expression, props, and setting are free and never \
         count against a character:\n\
         - on_model: a character of this kind appears and matches every \
           specified design attribute\n\
         - off_model: a character of this kind appears but deviates from the \
           definition (name the deviation)\n\
         - absent: no character of this kind appears in the image\n\n\
         Return exactly one fenced yaml code block and nothing else of \
         consequence:\n\
         ```yaml\n\
         verdicts:\n\
         - name: <cast member name>\n\
         \x20 verdict: on_model | off_model | absent\n\
         \x20 reason: one short factual sentence\n\
         ```\n\
         with exactly one entry per cast member listed above.",
        image_abs.display()
    );
    p
}

fn extract_verdicts(reply: &str, label: &str, cast: &[CastMember]) -> Result<Vec<MemberVerdict>> {
    let re = Regex::new(r"(?s)```ya?ml\s*\n(.*?)```").unwrap();
    let fence = re
        .captures_iter(reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no fenced yaml block"))?;
    #[derive(Deserialize)]
    struct Doc {
        verdicts: Vec<MemberVerdict>,
    }
    let doc: Doc = serde_yaml::from_str(&fence)
        .with_context(|| format!("{label}: invalid yaml, or no 'verdicts' list"))?;
    for m in cast {
        let n = doc.verdicts.iter().filter(|v| v.name == m.name).count();
        if n != 1 {
            bail!(
                "{label}: expected exactly one verdict for {}, got {n}",
                m.name
            );
        }
    }
    for v in &doc.verdicts {
        if !matches!(v.verdict.as_str(), "on_model" | "off_model" | "absent") {
            bail!(
                "{label}: verdict '{}' for {} is not on_model, off_model, or absent",
                v.verdict,
                v.name
            );
        }
    }
    Ok(doc.verdicts)
}

struct CheckTarget {
    round_dir: PathBuf,
    file: String,
    purpose: String,
}

fn check_targets(round_dir: &Path, cast: &[CastMember]) -> Result<Vec<CheckTarget>> {
    let briefs_path = round_dir.join("briefs.yaml");
    let round_path = round_dir.join("round.yaml");
    if !briefs_path.exists() || !round_path.exists() {
        return Ok(Vec::new());
    }
    let briefs: BriefsDoc = serde_yaml::from_str(&read(&briefs_path)?)
        .with_context(|| format!("parsing {}", briefs_path.display()))?;
    let applies: HashMap<&str, (bool, &str)> = briefs
        .briefs
        .iter()
        .map(|b| {
            let a = b.purpose != "cover"
                || cast
                    .iter()
                    .any(|m| b.prompt.to_lowercase().contains(&m.name.to_lowercase()));
            (b.id.as_str(), (a, b.purpose.as_str()))
        })
        .collect();
    let round: serde_yaml::Value = serde_yaml::from_str(&read(&round_path)?)
        .with_context(|| format!("parsing {}", round_path.display()))?;
    let mut out = Vec::new();
    for item in round
        .get("generated")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten()
    {
        let ok = item.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);
        let file = item.get("file").and_then(|v| v.as_str()).unwrap_or("");
        let brief = item.get("brief").and_then(|v| v.as_str()).unwrap_or("");
        let (applicable, purpose) = applies.get(brief).copied().unwrap_or((false, ""));
        if ok && !file.is_empty() && round_dir.join(file).exists() && applicable {
            out.push(CheckTarget {
                round_dir: round_dir.to_path_buf(),
                file: file.to_string(),
                purpose: purpose.to_string(),
            });
        }
    }
    Ok(out)
}

pub fn cast_check_run(
    edition: &str,
    round_filter: Option<&str>,
    direction_override: Option<&Path>,
    model: &ModelSpec,
) -> Result<i32> {
    let edition_dir = resolve_edition_dir(edition)?;
    let edition_label = edition_dir
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| edition.to_string());
    let direction_text = match direction_override {
        Some(p) => read(p)?,
        None => {
            let edition_yaml_text = read(&edition_dir.join("edition.yaml"))?;
            match art_direction_section(&edition_yaml_text)? {
                Some((_, text)) => text,
                None => bail!("edition.yaml has no art_direction_path; pass --direction"),
            }
        }
    };
    let cast = cast_members(&direction_text)?;
    if cast.is_empty() {
        bail!("the art direction defines no cast to check against; pass --direction at a file that does");
    }
    let license = cast_license(&direction_text)?;

    let rounds_root = edition_dir.join("art").join("rounds");
    let mut round_dirs: Vec<PathBuf> = fs::read_dir(&rounds_root)
        .with_context(|| format!("reading {}", rounds_root.display()))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_dir())
        .collect();
    round_dirs.sort();
    let round_dirs: Vec<PathBuf> = match round_filter {
        Some("all") => round_dirs,
        Some(stamp) => {
            let wanted = rounds_root.join(stamp);
            if !wanted.is_dir() {
                bail!("no round {} under {}", stamp, rounds_root.display());
            }
            vec![wanted]
        }
        None => round_dirs.into_iter().last().into_iter().collect(),
    };

    let mut exit = 0;
    for round_dir in &round_dirs {
        let targets = check_targets(round_dir, &cast)?;
        let round_name = round_dir.file_name().unwrap().to_string_lossy().to_string();
        if targets.is_empty() {
            println!("{round_name}: no applicable candidates");
            continue;
        }
        println!("{round_name}: checking {} image(s)", targets.len());
        let caller = Caller::new(round_dir);
        let results = Mutex::new(Vec::new());
        let errors = Mutex::new(Vec::new());
        thread::scope(|s| {
            for t in &targets {
                let caller = &caller;
                let cast = &cast;
                let license = &license;
                let results = &results;
                let errors = &errors;
                s.spawn(move || {
                    let abs = match t.round_dir.join(&t.file).canonicalize() {
                        Ok(p) => p,
                        Err(e) => {
                            errors.lock().unwrap().push(format!("{}: {e}", t.file));
                            return;
                        }
                    };
                    let label = format!("cast-check {}", t.file);
                    let prompt =
                        cast_check_prompt(cast, &abs, license.get(&t.purpose).map(String::as_str));
                    match caller.call_with_parse_images(&label, model, &prompt, &[abs], |r| {
                        extract_verdicts(r, &label, cast)
                    }) {
                        Ok(verdicts) => results.lock().unwrap().push(CastCheckResult {
                            file: t.file.clone(),
                            verdicts,
                        }),
                        Err(e) => errors.lock().unwrap().push(format!("{}: {e:#}", t.file)),
                    }
                });
            }
        });
        let fresh = results.into_inner().unwrap();
        let errors = errors.into_inner().unwrap();

        let check_path = round_dir.join("cast-check.yaml");
        let mut by_file: HashMap<String, CastCheckResult> = if check_path.exists() {
            let old: CastCheckDoc = serde_yaml::from_str(&read(&check_path)?)
                .with_context(|| format!("parsing {}", check_path.display()))?;
            old.results
                .into_iter()
                .map(|r| (r.file.clone(), r))
                .collect()
        } else {
            HashMap::new()
        };
        for r in fresh {
            by_file.insert(r.file.clone(), r);
        }
        let mut merged: Vec<CastCheckResult> = by_file.into_values().collect();
        merged.sort_by(|a, b| a.file.cmp(&b.file));
        let off_model: Vec<String> = merged
            .iter()
            .flat_map(|r| {
                r.verdicts
                    .iter()
                    .filter(|v| v.verdict == "off_model")
                    .map(|v| format!("  {} — {}: {}", r.file, v.name, v.reason))
            })
            .collect();
        fs::write(
            &check_path,
            serde_yaml::to_string(&CastCheckDoc {
                model: model.full.clone(),
                checked: crate::caller::now_stamp(),
                results: merged,
            })?,
        )?;
        println!("  wrote {}", check_path.display());
        if off_model.is_empty() {
            println!("  everything on model");
        } else {
            println!("  off-model ({}):", off_model.len());
            for line in &off_model {
                println!("{line}");
            }
        }
        if !errors.is_empty() {
            exit = 1;
            eprintln!("  {} check call(s) FAILED:", errors.len());
            for e in &errors {
                eprintln!("    {e}");
            }
        }
    }
    let showcase = write_showcase(&edition_dir, &edition_label)?;
    println!("showcase: {}", showcase.display());
    Ok(exit)
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
    let doc = RoundYaml {
        edition: edition_label,
        dry_run,
        generated,
        failures,
    };
    fs::write(round_dir.join("round.yaml"), serde_yaml::to_string(&doc)?)?;
    Ok(failures)
}

pub const DEFAULT_GEN_CMD: &str = "tools/imagegen '{prompt}' --out {out} --ref '{ref}'";

pub fn run(
    edition: &str,
    gen_cmd: Option<&str>,
    candidates: u32,
    model: &ModelSpec,
    dry_run: bool,
    showcase_only: bool,
    only: Option<&str>,
    note: Option<&str>,
    articles: Option<&str>,
    resume_round: Option<&str>,
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

    if let Some(resume) = resume_round {
        if dry_run || only.is_some() || note.is_some() || articles.is_some() {
            bail!("--resume-round completes an existing round; drop --dry-run/--only/--note/--articles");
        }
        let gen_cmd = gen_cmd.ok_or_else(|| anyhow!("--resume-round requires --gen-cmd"))?;
        let round_dir = PathBuf::from(resume);
        let briefs_path = round_dir.join("briefs.yaml");
        let doc: BriefsDoc = serde_yaml::from_str(&read(&briefs_path)?)
            .with_context(|| format!("parsing {}", briefs_path.display()))?;
        if doc.briefs.is_empty() {
            bail!("{} has no briefs to resume", briefs_path.display());
        }
        ensure_ref_placeholder(gen_cmd, &doc.briefs)?;
        println!("resuming round: {}", round_dir.display());
        return generate_and_finish(
            &doc.briefs,
            candidates,
            gen_cmd,
            &round_dir,
            &edition_dir,
            &edition_label,
        );
    }

    let edition_yaml_text = read(&edition_dir.join("edition.yaml"))?;

    let round_dir = edition_dir
        .join("art")
        .join("rounds")
        .join(crate::caller::now_stamp());
    if round_dir.exists() {
        bail!(
            "round directory already exists, refusing to touch it: {}",
            round_dir.display()
        );
    }
    fs::create_dir_all(&round_dir)
        .with_context(|| format!("creating round directory {}", round_dir.display()))?;

    println!("round dir: {}", round_dir.display());

    let only_purposes: Option<Vec<String>> = match only {
        Some(raw) => {
            let purposes: Vec<String> = raw
                .split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
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
    let only_articles: Option<Vec<String>> = match articles {
        Some(raw) => {
            if only_purposes.is_some() {
                bail!("--articles and --only are separate scopes; pass one");
            }
            let ids: Vec<String> = raw
                .split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
            if ids.is_empty() {
                bail!("--articles was given but named no article ids");
            }
            let doc: serde_yaml::Value = serde_yaml::from_str(&edition_yaml_text)
                .context("parsing edition.yaml for article ids")?;
            let known: Vec<String> = doc
                .get("articles")
                .and_then(|v| v.as_sequence())
                .map(|s| {
                    s.iter()
                        .filter_map(|a| a.get("id").and_then(|v| v.as_str()).map(str::to_string))
                        .collect()
                })
                .unwrap_or_default();
            for id in &ids {
                if !known.contains(id) {
                    bail!(
                        "--articles: '{id}' is not an article in edition.yaml; known: {}",
                        known.join(", ")
                    );
                }
            }
            Some(ids)
        }
        None => None,
    };

    let caller = Caller::new(&round_dir);
    let prompt = build_brief_prompt(
        &edition_yaml_text,
        candidates,
        only_purposes.as_deref(),
        only_articles.as_deref(),
        &rejected,
        note,
    )?;
    let (cast, license) = match art_direction_section(&edition_yaml_text)? {
        Some((_, text)) => (cast_members(&text)?, cast_license(&text)?),
        None => (Vec::new(), HashMap::new()),
    };
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
        if let Some(ids) = &only_articles {
            for b in &briefs {
                let aid = b.article_id.as_deref().unwrap_or("");
                if !matches!(b.purpose.as_str(), "opener" | "tail") || !ids.iter().any(|i| i == aid) {
                    bail!(
                        "{label}: this round is scoped to opener/tail briefs for {}; brief '{}' is a {} for '{aid}'",
                        ids.join(", "),
                        b.id,
                        b.purpose
                    );
                }
            }
        }
        validate_cast_named(&briefs, &cast, label)?;
        Ok(briefs)
    })?;

    let mut briefs = briefs;
    inject_cast(&mut briefs, &cast, &license);
    if let Some(cmd) = gen_cmd {
        ensure_ref_placeholder(cmd, &briefs)?;
    }

    let briefs_doc = BriefsDoc {
        briefs: briefs.clone(),
    };
    fs::write(
        round_dir.join("briefs.yaml"),
        serde_yaml::to_string(&briefs_doc)?,
    )?;
    println!("  {} brief(s) proposed", briefs.len());

    if dry_run {
        write_round_yaml(&round_dir, &edition_label, true, &[])?;
        write_showcase(&edition_dir, &edition_label)?;
        println!();
        println!("dry run: no image credits spent.");
        match gen_cmd {
            Some(cmd) => {
                let script =
                    write_generate_script(&round_dir, &edition_label, &briefs, candidates, cmd)?;
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

    generate_and_finish(
        &briefs,
        candidates,
        gen_cmd,
        &round_dir,
        &edition_dir,
        &edition_label,
    )
}

fn generate_and_finish(
    briefs: &[Brief],
    candidates: u32,
    gen_cmd: &str,
    round_dir: &Path,
    edition_dir: &Path,
    edition_label: &str,
) -> Result<i32> {
    let generated = generate_all(briefs, candidates, gen_cmd, round_dir);

    write_proof_sheet(round_dir, edition_label, briefs, &generated)?;
    let failures = write_round_yaml(round_dir, edition_label, false, &generated)?;
    let showcase = write_showcase(edition_dir, edition_label)?;
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
    for brief in briefs {
        let (ok, fail) = per_brief.get(brief.id.as_str()).copied().unwrap_or((0, 0));
        println!("  {} [{}]: {ok} ok, {fail} failed", brief.id, brief.purpose);
    }
    println!(
        "\nnext:\n  1. mag cast-check {edition_label}        (optional: badge off-model candidates in the showcase)\n  \
         2. open editions/{edition_label}/art/showcase.html and pick; clicking writes the paths to copy into edition.yaml \
         (cover.art_path / opener_art.path / tail_art_path / closing_plates); historic images are never deleted\n  \
         3. mag render {edition_label}"
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
        let reply = yaml_reply("briefs:\n- id: x\n  purpose: opener\n  prompt: p\n  alt_text: a\n");
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
            cast_references: None,
        };
        let (filename, cmd) =
            candidate_command("gen '{prompt}' -o {out}", &brief, 2, Path::new("rounds/r1"));
        assert_eq!(filename, "tail-a-v2.png");
        assert_eq!(
            cmd,
            "gen 'a robot'\\''s day — variation 2' -o rounds/r1/tail-a-v2.png"
        );
    }

    fn brief(id: &str, purpose: &str, prompt: &str) -> Brief {
        Brief {
            id: id.into(),
            purpose: purpose.into(),
            article_id: None,
            prompt: prompt.into(),
            subject: None,
            composition: None,
            alt_text: None,
            credit: None,
            cast_references: None,
        }
    }

    #[test]
    fn cast_members_parses_direction_cast() {
        let text = "direction:\n  cast:\n  - name: Pedro\n    prompt: a boy\n\
                    \x20 - name: Maro\n    prompt: a robot\n";
        let cast = cast_members(text).unwrap();
        assert_eq!(cast.len(), 2);
        assert_eq!(cast[0].name, "Pedro");
        assert_eq!(cast[1].prompt, "a robot");
        assert!(cast_members("direction:\n  name: x\n").unwrap().is_empty());
    }

    #[test]
    fn cast_members_rejects_malformed_cast() {
        let err = cast_members("direction:\n  cast:\n  - name: Pedro\n").unwrap_err();
        assert!(err.to_string().contains("direction.cast"), "{err}");
    }

    #[test]
    fn inject_cast_appends_only_the_named_members() {
        let cast = vec![
            CastMember {
                name: "Pedro".into(),
                prompt: "Pedro: a boy.".into(),
                reference: Some("refs/cast.png".into()),
            },
            CastMember {
                name: "Maro".into(),
                prompt: "Maro: a robot.".into(),
                reference: Some("refs/cast.png".into()),
            },
            CastMember {
                name: "Flopaz".into(),
                prompt: "Flopaz: a girl.".into(),
                reference: None,
            },
        ];
        let mut briefs = vec![
            brief("opener-a", "opener", "maro waves while Pedro reads"),
            brief("cover-synthetic", "cover", "an abstract door"),
            brief("tail-b", "tail", "Flopaz ties a knot"),
        ];
        inject_cast(&mut briefs, &cast, &HashMap::new());
        let pair = "Recurring cast — draw exactly as specified, never \
                    redesign: Pedro: a boy. Maro: a robot.";
        let solo = "Recurring cast — draw exactly as specified, never \
                    redesign: Flopaz: a girl.";
        assert_eq!(
            briefs[0].prompt,
            format!("maro waves while Pedro reads\n\n{pair}")
        );
        assert_eq!(briefs[1].prompt, "an abstract door");
        assert_eq!(briefs[2].prompt, format!("Flopaz ties a knot\n\n{solo}"));

        assert_eq!(
            briefs[0].cast_references.as_deref(),
            Some(&["refs/cast.png".to_string()][..])
        );
        assert!(briefs[1].cast_references.is_none());
        assert!(briefs[2].cast_references.is_none());
    }

    #[test]
    fn inject_cast_swaps_preamble_and_appends_license_on_licensed_slots() {
        let cast = vec![CastMember {
            name: "Pedro".into(),
            prompt: "Pedro: a boy.".into(),
            reference: None,
        }];
        let license: HashMap<String, String> =
            [("tail".to_string(), "may age up".to_string())].into();
        let mut briefs = vec![
            brief("opener-a", "opener", "Pedro reads"),
            brief("tail-a", "tail", "Pedro sleeps"),
        ];
        inject_cast(&mut briefs, &cast, &license);
        assert!(
            briefs[0].prompt.contains("never redesign"),
            "{}",
            briefs[0].prompt
        );
        assert!(
            !briefs[0].prompt.contains("licensed"),
            "{}",
            briefs[0].prompt
        );
        assert!(
            briefs[1].prompt.contains("identities below are canon"),
            "{}",
            briefs[1].prompt
        );
        assert!(
            briefs[1]
                .prompt
                .ends_with("overriding the fixed outfits above where they conflict: may age up"),
            "{}",
            briefs[1].prompt
        );
    }

    #[test]
    fn cast_license_parses_and_rejects_unknown_purposes() {
        let ok = cast_license("direction:\n  cast_license:\n    tail: quiet\n").unwrap();
        assert_eq!(ok.get("tail").map(String::as_str), Some("quiet"));
        assert!(cast_license("direction:\n  name: x\n").unwrap().is_empty());
        let err = cast_license("direction:\n  cast_license:\n    poster: p\n").unwrap_err();
        assert!(err.to_string().contains("poster"), "{err}");
    }

    #[test]
    fn cast_check_prompt_carries_the_license() {
        let cast = vec![CastMember {
            name: "Pedro".into(),
            prompt: "Pedro: a boy.".into(),
            reference: None,
        }];
        let strict = cast_check_prompt(&cast, Path::new("/img.png"), None);
        assert!(!strict.contains("licensed slot"), "{strict}");
        let licensed = cast_check_prompt(&cast, Path::new("/img.png"), Some("may age up"));
        assert!(
            licensed.contains("licensed slot. License: may age up"),
            "{licensed}"
        );
        assert!(licensed.contains("identity anchors only"), "{licensed}");
    }

    #[test]
    fn validate_cast_named_rejects_anonymous_interior_briefs() {
        let cast = vec![CastMember {
            name: "Pedro".into(),
            prompt: "p".into(),
            reference: None,
        }];
        let ok = vec![
            brief("opener-a", "opener", "pedro reads"),
            brief("cover-x", "cover", "an abstract door"),
        ];
        assert!(validate_cast_named(&ok, &cast, "t").is_ok());
        let bad = vec![brief("tail-b", "tail", "the boy reads")];
        let err = validate_cast_named(&bad, &cast, "t")
            .unwrap_err()
            .to_string();
        assert!(err.contains("tail-b") && err.contains("Pedro"), "{err}");
        assert!(validate_cast_named(&bad, &[], "t").is_ok());
    }

    #[test]
    fn candidate_command_substitutes_refs_or_empties_the_placeholder() {
        let mut b = brief("opener-a", "opener", "maro waves");
        let template = "imagegen '{prompt}' --out {out} --ref '{ref}'";
        let (_, cmd) = candidate_command(template, &b, 1, Path::new("r"));
        assert!(cmd.ends_with("--ref ''"), "{cmd}");
        b.cast_references = Some(vec!["a.png".into(), "b.png".into()]);
        let (_, cmd) = candidate_command(template, &b, 1, Path::new("r"));
        assert!(cmd.ends_with("--ref 'a.png b.png'"), "{cmd}");
    }

    #[test]
    fn ensure_ref_placeholder_fails_loud_when_refs_would_drop() {
        let mut b = brief("opener-a", "opener", "p");
        assert!(ensure_ref_placeholder("gen '{prompt}' -o {out}", &[b.clone()]).is_ok());
        b.cast_references = Some(vec!["a.png".into()]);
        let err = ensure_ref_placeholder("gen '{prompt}' -o {out}", &[b.clone()])
            .unwrap_err()
            .to_string();
        assert!(err.contains("{ref}"), "{err}");
        assert!(ensure_ref_placeholder("gen --ref '{ref}'", &[b]).is_ok());
    }

    #[test]
    fn cast_ref_href_walks_up_from_the_rounds_dir() {
        assert_eq!(
            cast_ref_href("art-directions/references/cast.png"),
            "../../references/cast.png"
        );
        assert_eq!(
            cast_ref_href("editions/004/x.png"),
            "../../../editions/004/x.png"
        );
    }

    #[test]
    fn cast_sheet_prompt_is_wordless_verbatim_composition() {
        let direction: serde_yaml::Value = serde_yaml::from_str(
            "visual_language: manga.\npalette: soft print.\navoid:\n- photorealism\n- neon\n",
        )
        .unwrap();
        let cast = vec![
            CastMember {
                name: "Pedro".into(),
                prompt: "Pedro: a boy.".into(),
                reference: None,
            },
            CastMember {
                name: "Maro".into(),
                prompt: "Maro: a robot.".into(),
                reference: None,
            },
        ];
        let p = cast_sheet_prompt(&direction, &cast, Some("rounder robot"));
        assert!(p.contains("model sheet"), "{p}");
        assert!(p.contains("Visual language: manga."), "{p}");
        assert!(p.contains("Palette: soft print."), "{p}");
        assert!(p.contains("Cast: Pedro: a boy. Maro: a robot."), "{p}");
        assert!(p.contains("Avoid: photorealism; neon."), "{p}");
        assert!(p.ends_with("Editor's note: rounder robot"), "{p}");
    }

    #[test]
    fn extract_verdicts_validates_names_and_values() {
        let cast = vec![
            CastMember {
                name: "Pedro".into(),
                prompt: "p".into(),
                reference: None,
            },
            CastMember {
                name: "Maro".into(),
                prompt: "m".into(),
                reference: None,
            },
        ];
        let good = yaml_reply(
            "verdicts:\n\
             - {name: Pedro, verdict: on_model, reason: matches}\n\
             - {name: Maro, verdict: off_model, reason: single eye}\n",
        );
        let v = extract_verdicts(&good, "t", &cast).unwrap();
        assert_eq!(v[1].verdict, "off_model");

        let missing = yaml_reply("verdicts:\n- {name: Pedro, verdict: on_model, reason: r}\n");
        let err = extract_verdicts(&missing, "t", &cast)
            .unwrap_err()
            .to_string();
        assert!(err.contains("Maro"), "{err}");

        let bad = yaml_reply(
            "verdicts:\n\
             - {name: Pedro, verdict: great, reason: r}\n\
             - {name: Maro, verdict: on_model, reason: r}\n",
        );
        let err = extract_verdicts(&bad, "t", &cast).unwrap_err().to_string();
        assert!(err.contains("'great'"), "{err}");
    }

    #[test]
    fn check_targets_skips_covers_that_do_not_name_the_cast() {
        let dir = std::env::temp_dir().join("mag-art-test-check-targets");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("briefs.yaml"),
            "briefs:\n\
             - id: opener-a\n  purpose: opener\n  article_id: a\n  prompt: p\n  alt_text: alt\n\
             - id: cover-synthetic\n  purpose: cover\n  prompt: abstract\n\
             - id: cover-directed\n  purpose: cover\n  prompt: maro at a door\n",
        )
        .unwrap();
        fs::write(
            dir.join("round.yaml"),
            "edition: '005'\ndry_run: false\nfailures: 0\ngenerated:\n\
             - {brief: opener-a, variant: 1, file: opener-a-v1.png, ok: true}\n\
             - {brief: opener-a, variant: 2, file: opener-a-v2.png, ok: false}\n\
             - {brief: cover-synthetic, variant: 1, file: cover-synthetic-v1.png, ok: true}\n\
             - {brief: cover-directed, variant: 1, file: cover-directed-v1.png, ok: true}\n",
        )
        .unwrap();
        for f in [
            "opener-a-v1.png",
            "cover-synthetic-v1.png",
            "cover-directed-v1.png",
        ] {
            fs::write(dir.join(f), b"png").unwrap();
        }
        let cast = vec![CastMember {
            name: "Maro".into(),
            prompt: "m".into(),
            reference: None,
        }];
        let targets = check_targets(&dir, &cast).unwrap();
        let files: Vec<&str> = targets.iter().map(|t| t.file.as_str()).collect();
        assert_eq!(files, ["opener-a-v1.png", "cover-directed-v1.png"]);
    }

    #[test]
    fn art_direction_section_is_none_without_the_field() {
        assert!(art_direction_section("id: e\n").unwrap().is_none());
        assert!(art_direction_section("art_direction_path: ''\n")
            .unwrap()
            .is_none());
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
        let ed = std::env::temp_dir()
            .join("mag-art-test-showcase")
            .join("editions")
            .join("009");
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
        assert!(
            html.contains("opener-a</h3>") || html.contains("opener-a — a</h3>"),
            "{html}"
        );

        assert!(!html.contains("opener-a-v2.png"), "{html}");
        assert_eq!(html.matches("SELECTED").count(), 1, "{html}");
        assert!(
            html.contains("rounds/2026-01-01T00-00-00/cover-wildcard-v1.png"),
            "{html}"
        );

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
            cast_references: None,
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
