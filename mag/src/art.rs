use crate::caller::{write_atomic, Caller, ModelSpec};
use crate::model::kinds::ArtPurpose;
use crate::produce::{self, INLINE_PREAMBLE};
use crate::util::{escape_html, parallel, prompts_path, read};
use anyhow::{anyhow, bail, ensure, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::LazyLock;
use std::sync::Mutex;
use std::thread;

#[derive(clap::Args)]
pub struct ArtArgs {
    pub edition: String,
    #[arg(long = "gen-cmd", default_value = DEFAULT_GEN_CMD, help = "Shell command for one image; {prompt}, {out}, {ref}, {size} must each be a whole word (bare or quoted) and expand to quoted MAG_* variables")]
    pub gen_cmd: String,
    #[arg(long, default_value_t = 4, help = "How many candidates per art brief")]
    pub candidates: u32,
    #[arg(long, default_value = "opus")]
    pub model: String,
    #[arg(
        long = "dry-run",
        help = "Propose briefs and write generate.sh, but spend no image credits"
    )]
    pub dry_run: bool,
    #[arg(
        long,
        help = "Only rebuild art/showcase.html from the rounds on disk (no model call, no generation)"
    )]
    pub showcase: bool,
    #[arg(
        long,
        help = "Scope this round to some purposes (comma-separated: cover,opener,tail,closing); earlier briefs for them are treated as rejected and fed back as what not to repeat"
    )]
    pub only: Option<String>,
    #[arg(
        long,
        help = "Editor's note appended to the brief prompt (why the last round was rejected, direction for this one)"
    )]
    pub note: Option<String>,
    #[arg(
        long,
        help = "Scope this round to opener and tail briefs for these edition.yaml article ids (comma-separated): for articles added after the slate was generated"
    )]
    pub articles: Option<String>,
    #[arg(
        long = "resume-round",
        help = "Complete an interrupted round dir: reuse its briefs.yaml, keep candidates already on disk, generate only the missing ones, then finish the round"
    )]
    pub resume_round: Option<String>,
    #[arg(
        long,
        help = "Convert the art edition.yaml names under art/rounds/ (which stay out of git) to JPEGs in art/picks/ and point edition.yaml at them; run after picking"
    )]
    pub promote: bool,
}

#[derive(clap::Args)]
pub struct CastSheetArgs {
    #[arg(help = "The art direction file whose direction.cast to sheet")]
    pub direction: PathBuf,
    #[arg(long = "gen-cmd", required_unless_present_any = ["dry_run", "showcase"], help = "Shell command for one image; {prompt}, {out}, {ref}, {size} must each be a whole word (bare or quoted) and expand to quoted MAG_* variables")]
    pub gen_cmd: Option<String>,
    #[arg(
        long,
        default_value_t = 4,
        help = "How many sheet candidates to render"
    )]
    pub candidates: u32,
    #[arg(
        long = "dry-run",
        help = "Write the prompt and generate.sh, but spend no image credits"
    )]
    pub dry_run: bool,
    #[arg(
        long,
        help = "Only rebuild the direction's cast showcase.html from the rounds on disk"
    )]
    pub showcase: bool,
    #[arg(long, help = "Editor's note appended to the sheet prompt")]
    pub note: Option<String>,
}

#[derive(clap::Args)]
pub struct CastCheckArgs {
    pub edition: String,
    #[arg(
        long,
        help = "Round stamp to check, or 'all' (default: the newest round)"
    )]
    pub round: Option<String>,
    #[arg(
        long,
        help = "Art direction file to take the cast from (default: the edition's art_direction_path)"
    )]
    pub direction: Option<PathBuf>,
    #[arg(long, default_value = "sonnet", help = "Vision-capable judge model")]
    pub model: String,
}

static YAML_FENCE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)```ya?ml\s*\n(.*?)```").unwrap());
static KEBAB_ID: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^[a-z0-9]+(-[a-z0-9]+)*$").unwrap());

const GEN_CONCURRENCY: usize = 8;

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
    purpose: ArtPurpose,
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
    let doc: serde_norway::Value = serde_norway::from_str(edition_yaml_text)
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
    let doc: serde_norway::Value = serde_norway::from_str(art_direction_text)
        .context("parsing art direction file for direction.cast")?;
    match doc.get("direction").and_then(|d| d.get("cast")) {
        Some(v) => serde_norway::from_value(v.clone())
            .context("direction.cast entries need `name` and `prompt`"),
        None => Ok(Vec::new()),
    }
}

fn slot_purpose(text: &str) -> Result<ArtPurpose, String> {
    match ArtPurpose::parse(text) {
        Ok(ArtPurpose::CastSheet) | Err(_) => {
            Err(format!("{text:?} is not one of {}", join(SLOT_PURPOSES)))
        }
        Ok(purpose) => Ok(purpose),
    }
}

const SLOT_PURPOSES: &[ArtPurpose] = &[
    ArtPurpose::Cover,
    ArtPurpose::Opener,
    ArtPurpose::Tail,
    ArtPurpose::Closing,
];

fn join(purposes: &[ArtPurpose]) -> String {
    purposes
        .iter()
        .map(ToString::to_string)
        .collect::<Vec<_>>()
        .join(", ")
}

fn cast_license(art_direction_text: &str) -> Result<HashMap<ArtPurpose, String>> {
    let doc: serde_norway::Value = serde_norway::from_str(art_direction_text)
        .context("parsing art direction file for direction.cast_license")?;
    let map: HashMap<String, String> =
        match doc.get("direction").and_then(|d| d.get("cast_license")) {
            Some(v) => serde_norway::from_value(v.clone())
                .context("direction.cast_license must map purposes to license text")?,
            None => HashMap::new(),
        };
    map.into_iter()
        .map(|(k, text)| match slot_purpose(&k) {
            Ok(purpose) => Ok((purpose, text)),
            Err(_) => bail!("direction.cast_license has unknown purpose '{k}'"),
        })
        .collect()
}

fn inject_cast(briefs: &mut [Brief], cast: &[CastMember], license: &HashMap<ArtPurpose, String>) {
    for brief in briefs.iter_mut() {
        let named: Vec<&CastMember> = cast
            .iter()
            .filter(|m| brief.prompt.to_lowercase().contains(&m.name.to_lowercase()))
            .collect();
        if named.is_empty() {
            continue;
        }
        let preamble = match license.get(&brief.purpose) {
            Some(_) => "Recurring cast: identities below are canon:",
            None => "Recurring cast: draw exactly as specified, never redesign:",
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
        if b.purpose == ArtPurpose::Cover {
            continue;
        }
        let names_one = cast
            .iter()
            .any(|m| b.prompt.to_lowercase().contains(&m.name.to_lowercase()));
        if !names_one {
            let names: Vec<&str> = cast.iter().map(|m| m.name.as_str()).collect();
            bail!(
                "{label}: interior brief '{}' names no cast member ({}); every \
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

fn previous_briefs(edition_dir: &Path, purposes: &[ArtPurpose]) -> Result<Vec<Brief>> {
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
        let doc: BriefsDoc = serde_norway::from_str(&read(&briefs_path)?)
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
    only: Option<&[ArtPurpose]>,
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
    out += FRAME_GUIDE;
    if !cast.is_empty() {
        let names: Vec<&str> = cast.iter().map(|m| m.name.as_str()).collect();
        out += &format!(
            "\nThe art direction defines a canonical recurring cast: {}. Never \
             describe their appearance in a prompt; the pipeline appends each \
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
             You are not generating images yourself; a later pipeline step \
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
                 completely: reuse nothing conceptual from the rejected \
                 briefs.\n\n\
                 You are not generating images yourself; a later pipeline \
                 step will run each brief through an image generator \
                 {candidates} time(s) to produce that many variants.\n\n",
                    join(purposes)
                );
            }
            None => {
                out += &format!(
                    "\nPropose the complete art-brief slate for this edition now. You are \
         not generating images yourself; a later pipeline step will run each \
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
           this brief; it must stand entirely on its own, restating the art \
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
    let fence = YAML_FENCE
        .captures_iter(reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no fenced yaml block"))?;
    let invalid = |e: serde_norway::Error| {
        anyhow!("{label}: invalid yaml, or no non-empty 'briefs' list: {e}")
    };
    let raw: serde_norway::Value = serde_norway::from_str(&fence).map_err(invalid)?;
    for text in raw
        .get("briefs")
        .and_then(|b| b.as_sequence())
        .into_iter()
        .flatten()
        .filter_map(|b| b.get("purpose").or_else(|| b.get("slot")))
        .filter_map(|p| p.as_str())
    {
        slot_purpose(text).map_err(|e| anyhow!("{label}: brief purpose {e}"))?;
    }
    let doc: BriefsDoc = serde_norway::from_value(raw).map_err(invalid)?;
    if doc.briefs.is_empty() {
        bail!("{label}: 'briefs' list is empty");
    }
    let mut seen = HashSet::new();
    for b in &doc.briefs {
        if b.prompt.trim().is_empty() {
            bail!("{label}: every brief needs a non-empty prompt");
        }
        if !KEBAB_ID.is_match(&b.id) {
            bail!(
                "{label}: brief id '{}' must be lowercase letters and digits joined by single hyphens",
                b.id
            );
        }
        if !seen.insert(b.id.as_str()) {
            bail!("{label}: brief id '{}' is used more than once", b.id);
        }
        let purpose = b.purpose;
        if !SLOT_PURPOSES.contains(&purpose) {
            bail!(
                "{label}: brief '{}' has purpose '{purpose}', expected \
                 cover, opener, tail, or closing",
                b.id
            );
        }
        let article_id = b.article_id.as_deref().unwrap_or("").trim();
        if matches!(purpose, ArtPurpose::Opener | ArtPurpose::Tail) && article_id.is_empty() {
            bail!("{label}: {purpose} brief '{}' needs an article_id", b.id);
        }
        let alt = b.alt_text.as_deref().unwrap_or("").trim();
        if !matches!(purpose, ArtPurpose::Cover) && alt.is_empty() {
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

fn shell_single_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\\''"))
}

type GenEnv = [(&'static str, String); 4];

const GEN_PLACEHOLDERS: [(&str, &str); 4] = [
    ("{prompt}", "MAG_PROMPT"),
    ("{out}", "MAG_OUT"),
    ("{ref}", "MAG_REF"),
    ("{size}", "MAG_SIZE"),
];

fn expand_placeholders(gen_cmd: &str) -> Result<String> {
    for word in gen_cmd.split_whitespace() {
        for (placeholder, _) in GEN_PLACEHOLDERS {
            let whole = [
                placeholder.to_string(),
                format!("'{placeholder}'"),
                format!("\"{placeholder}\""),
            ];
            ensure!(
                !word.contains(placeholder) || whole.iter().any(|w| w == word),
                "gen-cmd: {placeholder} must be a whole shell word, not part of {word}"
            );
        }
    }
    for (placeholder, _) in GEN_PLACEHOLDERS {
        for (at, _) in gen_cmd.match_indices(placeholder) {
            let before = &gen_cmd[..at];
            let after = &gen_cmd[at + placeholder.len()..];
            let wrapped = ['\'', '"']
                .iter()
                .any(|q| before.ends_with(*q) && after.starts_with(*q));
            let open = if wrapped {
                &before[..before.len() - 1]
            } else {
                before
            };
            ensure!(
                open.matches('\'').count() % 2 == 0 && open.matches('"').count() % 2 == 0,
                "gen-cmd: {placeholder} sits inside a quoted string; give it its own shell word"
            );
        }
    }
    Ok(GEN_PLACEHOLDERS
        .iter()
        .fold(gen_cmd.to_string(), |cmd, (placeholder, var)| {
            let value = format!("\"${var}\"");
            [
                format!("'{placeholder}'"),
                format!("\"{placeholder}\""),
                (*placeholder).to_string(),
            ]
            .iter()
            .fold(cmd, |cmd, form| cmd.replace(form.as_str(), &value))
        }))
}

fn candidate_command(
    gen_cmd: &str,
    brief: &Brief,
    variant: u32,
    round_dir: &Path,
) -> Result<(String, String, GenEnv)> {
    let filename = format!("{}-v{variant}.png", brief.id);
    let refs = brief
        .cast_references
        .as_deref()
        .unwrap_or_default()
        .join(" ");
    let env = [
        (
            "MAG_PROMPT",
            format!("{} (variation {variant})", brief.prompt),
        ),
        (
            "MAG_OUT",
            round_dir.join(&filename).to_string_lossy().into_owned(),
        ),
        ("MAG_REF", refs),
        ("MAG_SIZE", size_for(brief.purpose).to_string()),
    ];
    Ok((filename, expand_placeholders(gen_cmd)?, env))
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
            let (_, cmd_str, env) = candidate_command(gen_cmd, brief, variant, round_dir)?;
            let exports: String = env
                .iter()
                .map(|(k, v)| format!("{k}={} ", shell_single_quote(v)))
                .collect();
            script += &format!("(export {}; {cmd_str})\n", exports.trim_end());
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

fn run_gen_command(cmd_str: &str, env: &GenEnv, out_path: &Path) -> Result<(), String> {
    let output = Command::new("sh")
        .arg("-c")
        .arg(cmd_str)
        .envs(env.iter().map(|(k, v)| (*k, v)))
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
) -> Result<Vec<GeneratedItem>> {
    let jobs: Vec<(String, u32, String, String, GenEnv)> = briefs
        .iter()
        .flat_map(|b| (1..=candidates).map(move |v| (b, v)))
        .map(|(b, v)| {
            let (file, cmd, env) = candidate_command(gen_cmd, b, v, round_dir)?;
            Ok((b.id.clone(), v, file, cmd, env))
        })
        .collect::<Result<_>>()?;
    let next = AtomicUsize::new(0);
    let results = Mutex::new(Vec::with_capacity(jobs.len()));
    thread::scope(|s| {
        for _ in 0..GEN_CONCURRENCY.min(jobs.len()) {
            s.spawn(|| loop {
                let i = next.fetch_add(1, Ordering::Relaxed);
                let Some((brief, variant, file, cmd, env)) = jobs.get(i) else {
                    break;
                };
                let out_path = round_dir.join(file);
                let ok = if fs::metadata(&out_path).is_ok_and(|m| m.len() > 0) {
                    println!("    {brief} v{variant}: kept (already on disk)");
                    true
                } else {
                    match run_gen_command(cmd, env, &out_path) {
                        Ok(()) => {
                            println!("    {brief} v{variant}: ok");
                            true
                        }
                        Err(e) => {
                            eprintln!("    {brief} v{variant}: FAILED: {e}");
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
    Ok(results.into_iter().map(|(_, item)| item).collect())
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
        "<title>Art proof sheet: {}</title>\n",
        escape_html(edition_label)
    );
    html += PROOF_SHEET_CSS;
    html += &format!("<h1>Art proof sheet: {}</h1>\n", escape_html(edition_label));
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
                escape_html(&item.file)
            );
        } else {
            html += "<div class=\"failed\">FAILED</div>\n";
        }
        html += &format!(
            "<figcaption>{}, variant {}</figcaption>\n",
            escape_html(&item.brief),
            item.variant
        );
        html += &format!(
            "<details><summary>prompt</summary><pre>{}</pre></details>\n",
            escape_html(prompt)
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
    purpose: Option<ArtPurpose>,
    article_id: Option<String>,
    prompt: String,
    variant: u32,
    selected: bool,

    verdicts: Vec<MemberVerdict>,
}

pub fn selected_art_paths(edition_yaml: &serde_norway::Value) -> Vec<String> {
    let mut out = Vec::new();
    let mut push = |v: Option<&serde_norway::Value>| {
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
        let briefs: BriefsDoc = serde_norway::from_str(&read(&briefs_path)?)
            .with_context(|| format!("parsing {}", briefs_path.display()))?;
        let by_id: HashMap<&str, &Brief> =
            briefs.briefs.iter().map(|b| (b.id.as_str(), b)).collect();
        let round: serde_norway::Value = serde_norway::from_str(&read(&round_path)?)
            .with_context(|| format!("parsing {}", round_path.display()))?;
        let check_path = round_dir.join("cast-check.yaml");
        let checks: HashMap<String, Vec<MemberVerdict>> = if check_path.exists() {
            let doc: CastCheckDoc = serde_norway::from_str(&read(&check_path)?)
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
            let ok = item
                .get("ok")
                .and_then(serde_norway::Value::as_bool)
                .unwrap_or(false);
            let file = item.get("file").and_then(|v| v.as_str()).unwrap_or("");
            if !ok || file.is_empty() || !round_dir.join(file).exists() {
                continue;
            }
            let brief_id = item.get("brief").and_then(|v| v.as_str()).unwrap_or("");
            let variant = item
                .get("variant")
                .and_then(serde_norway::Value::as_u64)
                .unwrap_or(0) as u32;
            let (purpose, article_id, prompt) = match by_id.get(brief_id) {
                Some(b) => (Some(b.purpose), b.article_id.clone(), b.prompt.clone()),
                None => (None, None, String::new()),
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
                selected: selected.iter().any(|s| {
                    s == &repo_path
                        || (*s == crate::picks::pick_path(&repo_path)
                            && crate::picks::picked_from(s, &round_dir.join(file)))
                }),
                verdicts: checks.get(file).cloned().unwrap_or_default(),
            });
        }
    }
    Ok(items)
}

const PROOF_SHEET_CSS: &str = "<style>\n\
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

fn showcase_frame(edition_dir: &Path, edition_label: &str) -> Result<(CoverFrame, Vec<String>)> {
    let edition_yaml_path = edition_dir.join("edition.yaml");
    let repo_root = edition_dir
        .ancestors()
        .nth(2)
        .context("an edition directory sits under editions/")?;
    let mut cover_frame = CoverFrame {
        publication: crate::render::publication_name(repo_root)?,
        headline: edition_label.to_string(),
        issue: edition_label.to_string(),
        date: String::new(),
    };
    if !edition_yaml_path.exists() {
        return Ok((cover_frame, Vec::new()));
    }
    let doc: serde_norway::Value = serde_norway::from_str(&read(&edition_yaml_path)?)
        .with_context(|| format!("parsing {}", edition_yaml_path.display()))?;
    if let Some(h) = doc
        .get("cover")
        .and_then(|c| c.get("headline"))
        .and_then(|v| v.as_str())
    {
        cover_frame.headline = h.to_string();
    }
    if let Some(n) = doc
        .get("issue_number")
        .and_then(serde_norway::Value::as_u64)
    {
        cover_frame.issue = format!("{n:03}");
    }
    if let Some(d) = doc.get("publication_date").and_then(|v| v.as_str()) {
        cover_frame.date = d.replace('-', " ");
    }
    Ok((cover_frame, selected_art_paths(&doc)))
}

fn cover_frame_html(cover_frame: &CoverFrame, item: &ShowcaseItem, img_tag: &str) -> String {
    let mut words = cover_frame.headline.split_whitespace();
    let first = words.next().unwrap_or("");
    let rest = words.collect::<Vec<_>>().join(" ");
    format!(
        "<div class=\"coverframe\">\
         <span class=\"cf-spine\"><span class=\"cf-issue\">ISSUE {issue}</span>\
         <span class=\"cf-imprint\">{publication}</span></span>\
         <div class=\"cf-masthead\">{masthead}</div>\
         <div class=\"cf-headline\"><span>{first}</span><em>{rest}</em></div>\
         <div class=\"cf-plate\">{img_tag}</div>\
         <div class=\"cf-credits\">COVER CANDIDATE / {brief} v{variant}</div>\
         <div class=\"cf-date\">{date}</div>\
         </div>\n",
        issue = escape_html(&cover_frame.issue),
        publication = escape_html(&cover_frame.publication.to_uppercase()),
        masthead = cover_frame
            .publication
            .split_whitespace()
            .enumerate()
            .map(|(i, w)| if i == 0 {
                format!("<span class=\"cf-m1\">{}</span>", escape_html(w))
            } else {
                format!("<span class=\"cf-m2\">{}</span>", escape_html(w))
            })
            .collect::<String>(),
        first = escape_html(first),
        rest = escape_html(&rest),
        brief = escape_html(&item.brief_id),
        variant = item.variant,
        date = escape_html(&cover_frame.date),
    )
}

fn showcase_figure(item: &ShowcaseItem, edition_dir: &Path, cover_frame: &CoverFrame) -> String {
    let mut html = String::new();
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
    let article_or_brief = item.article_id.as_deref().unwrap_or(&item.brief_id);
    let slot = match item.purpose {
        Some(ArtPurpose::Cover) => "cover".to_string(),
        Some(ArtPurpose::Closing) => format!("closing:{}", item.brief_id),
        Some(p) => format!("{p}:{article_or_brief}"),
        None => format!("unknown:{article_or_brief}"),
    };
    html += &format!(
        "<figure class=\"{}\" data-path=\"{}\" data-slot=\"{}\">\n",
        classes.join(" "),
        escape_html(&repo_path),
        escape_html(&slot)
    );
    if item.selected {
        html += "<span class=\"badge\">SELECTED</span>\n";
    }
    if !off.is_empty() {
        let names: Vec<&str> = off.iter().map(|v| v.name.as_str()).collect();
        html += &format!(
            "<span class=\"offbadge\">OFF-MODEL: {}</span>\n",
            escape_html(&names.join(", "))
        );
    }
    let img_tag = format!(
        "<img src=\"rounds/{}/{}\" loading=\"lazy\">",
        escape_html(&item.round),
        escape_html(&item.file)
    );
    if item.purpose == Some(ArtPurpose::Cover) {
        html += &cover_frame_html(cover_frame, item, &img_tag);
    } else {
        html += &img_tag;
        html += "\n";
    }
    html += &format!(
        "<figcaption>{} v{} ({})</figcaption>\n",
        escape_html(&item.brief_id),
        item.variant,
        escape_html(&item.round)
    );
    html += &format!(
        "<div class=\"btnrow\"><a href=\"rounds/{}/{}\" target=\"_blank\">view</a>\
         <button data-copy=\"path\">copy path</button>\
         <button data-copy=\"preview\">preview cmd</button>\
         <button data-copy=\"finder\">finder cmd</button></div>\n",
        escape_html(&item.round),
        escape_html(&item.file)
    );
    if !item.verdicts.is_empty() {
        let lines: Vec<String> = item
            .verdicts
            .iter()
            .map(|v| format!("{}: {}, {}", v.name, v.verdict, v.reason))
            .collect();
        html += &format!(
            "<div class=\"verdicts\">{}</div>\n",
            escape_html(&lines.join(" · "))
        );
    }
    if !item.prompt.is_empty() {
        html += &format!(
            "<details><summary>prompt</summary><pre>{}</pre></details>\n",
            escape_html(&item.prompt)
        );
    }
    html += "</figure>\n";
    html
}

const SHOWCASE_CSS: &str = "<style>\n\
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

fn showcase_sections(
    items: &[ShowcaseItem],
    edition_dir: &Path,
    cover_frame: &CoverFrame,
) -> String {
    let mut html = String::new();
    for (purpose, heading) in [
        (Some(ArtPurpose::Cover), "Cover"),
        (Some(ArtPurpose::Opener), "Article openers"),
        (Some(ArtPurpose::Tail), "Article tails"),
        (Some(ArtPurpose::Closing), "Closing plates"),
        (None, "Unmatched"),
    ] {
        let mut section: Vec<&ShowcaseItem> =
            items.iter().filter(|i| i.purpose == purpose).collect();
        if section.is_empty() {
            if purpose.is_some() {
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
                    .map(|a| format!(": {}", escape_html(a)))
                    .unwrap_or_default();
                html += &format!(
                    "<h3>{}{article_note}</h3>\n<div class=\"grid\">\n",
                    escape_html(&item.brief_id)
                );
                open = true;
            }
            html += &showcase_figure(item, edition_dir, cover_frame);
        }
        if open {
            html += "</div>\n";
        }
    }
    html
}

fn write_showcase(edition_dir: &Path, edition_label: &str) -> Result<PathBuf> {
    let (cover_frame, selected) = showcase_frame(edition_dir, edition_label)?;
    let items = collect_showcase_items(edition_dir, &selected)?;

    let mut html = String::new();
    html += "<!doctype html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n";
    html += &format!(
        "<title>Art showcase: {}</title>\n",
        escape_html(edition_label)
    );
    html += SHOWCASE_CSS;
    let mut rounds: Vec<&str> = items.iter().map(|i| i.round.as_str()).collect();
    rounds.sort_unstable();
    rounds.dedup();
    let rounds_line = rounds
        .iter()
        .map(|r| {
            let n = items.iter().filter(|i| i.round == *r).count();
            format!("{} ({n})", escape_html(r))
        })
        .collect::<Vec<_>>()
        .join(" · ");
    html += &format!(
        "<h1>Art showcase: {} ({} image(s))</h1>\n\
         <p class=\"rounds\">Rounds: {rounds_line}</p>\n\
         <p>Every generated candidate across every round. A green badge marks \
         what edition.yaml currently selects. Click an image to pick it for its \
         slot (cover, per-article opener/tail: one pick; closing plates: toggle). \
         The bar below copies commands to run from the repo root, and \
         edition.yaml lines for the picks. Give feedback per image as \
         <code>brief-id vN (round)</code>.</p>\n",
        escape_html(edition_label),
        items.len()
    );

    html += &showcase_sections(&items, edition_dir, &cover_frame);
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
    direction: &serde_norway::Value,
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

const CAST_SHOWCASE_CSS: &str = "<style>\n\
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

fn cast_round_cells(round_dir: &Path, canon: &[(String, Vec<u8>)]) -> Result<String> {
    let round_name = round_dir.file_name().unwrap().to_string_lossy().to_string();
    let round_path = round_dir.join("round.yaml");
    if !round_path.exists() {
        return Ok(String::new());
    }
    let round: serde_norway::Value = serde_norway::from_str(&read(&round_path)?)
        .with_context(|| format!("parsing {}", round_path.display()))?;
    let mut cells = String::new();
    for item in round
        .get("generated")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten()
    {
        let ok = item
            .get("ok")
            .and_then(serde_norway::Value::as_bool)
            .unwrap_or(false);
        let file = item.get("file").and_then(|v| v.as_str()).unwrap_or("");
        let variant = item
            .get("variant")
            .and_then(serde_norway::Value::as_u64)
            .unwrap_or(0);
        let path = round_dir.join(file);
        if !ok || file.is_empty() || !path.exists() {
            continue;
        }
        let is_canon =
            !canon.is_empty() && fs::read(&path).is_ok_and(|b| canon.iter().any(|(_, c)| c == &b));
        cells += &format!(
            "<figure class=\"{}\">\n",
            if is_canon { "canon" } else { "" }
        );
        if is_canon {
            cells += "<span class=\"badge\">CANON</span>\n";
        }
        cells += &format!(
            "<a href=\"{0}/{1}\" target=\"_blank\"><img src=\"{0}/{1}\" loading=\"lazy\"></a>\n",
            escape_html(&round_name),
            escape_html(file)
        );
        cells += &format!(
            "<figcaption>v{variant} ({})</figcaption>\n</figure>\n",
            escape_html(&round_name)
        );
    }
    Ok(cells)
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
    html += &format!("<title>Cast: {}</title>\n", escape_html(&stem));
    html += CAST_SHOWCASE_CSS;
    html += &format!("<h1>Cast: {}</h1>\n", escape_html(&stem));
    html += &format!(
        "<p class=\"hint\">Judge the designs, not the poses. Approve a new sheet by \
         copying it over the <code>reference:</code> path in {} (the CANON badge \
         marks the variant whose bytes match the installed reference).</p>\n",
        escape_html(&direction_path.display().to_string())
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
                escape_html(&href)
            );
            html += &format!("<figcaption>{}</figcaption>\n</figure>\n", escape_html(r));
        }
        html += "</div>\n";
    }

    let mut any_round = false;
    for round_dir in &round_dirs {
        let round_name = round_dir.file_name().unwrap().to_string_lossy().to_string();
        let cells = cast_round_cells(round_dir, &canon)?;
        if !cells.is_empty() {
            any_round = true;
            html += &format!(
                "<h2>Round {}</h2>\n<div class=\"grid\">\n{cells}</div>\n",
                escape_html(&round_name)
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

pub fn cast_sheet_run(args: &CastSheetArgs) -> Result<i32> {
    let direction_path = args.direction.as_path();
    let gen_cmd = args.gen_cmd.as_deref();
    let (candidates, dry_run, showcase_only) = (args.candidates, args.dry_run, args.showcase);
    let note = args.note.as_deref();
    if showcase_only {
        let path = write_cast_showcase(direction_path)?;
        println!("cast showcase rebuilt: {}", path.display());
        return Ok(0);
    }
    if let Some(cmd) = gen_cmd {
        expand_placeholders(cmd)?;
    }
    let text = read(direction_path)?;
    let cast = cast_members(&text)?;
    if cast.is_empty() {
        bail!(
            "{} defines no direction.cast; nothing to sheet",
            direction_path.display()
        );
    }
    let doc: serde_norway::Value = serde_norway::from_str(&text)
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
        purpose: ArtPurpose::CastSheet,
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
    crate::caller::create_fresh_dir(&round_dir)?;
    println!("round dir: {}", round_dir.display());
    write_atomic(
        round_dir.join("briefs.yaml"),
        serde_norway::to_string(&BriefsDoc {
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
                "no --gen-cmd recorded; the prompt is in {}/briefs.yaml; {approval_note}",
                round_dir.display()
            ),
        }
        return Ok(0);
    }
    let gen_cmd = gen_cmd.expect("clap requires --gen-cmd when not a dry run");
    let generated = generate_all(&briefs, candidates, gen_cmd, &round_dir)?;
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
    #[serde(default, skip_serializing_if = "Option::is_none")]
    attribute: Option<String>,
}

const LICENSED_ATTRIBUTES: &[&str] = &["hairstyle", "garment_cut", "pose", "style", "other"];

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
             Judge identity anchors only: wardrobe, apparent age, rendering \
             style, and mood are licensed and never count as deviations.\n",
            l.trim()
        );
    }
    p += &format!(
        "\nExamine the illustration image; if it is not already attached to \
         this conversation, view it with the Read tool at: {}\n\n\
         Judge each cast member's IDENTITY against its definition. Identity \
         is what a reader uses to recognise the character across pages: for \
         a human, hair colour, glasses or their absence, and the colour and \
         kind of each garment; for a robot, body shape, body and panel \
         colours, the face screen, the antenna, and the pouch. Everything \
         else is licence and never counts: pose, action, expression, props, \
         setting, hairstyle (ponytail, bob, loose, bangs), lace or sole \
         colours, the cut of a garment, proportions under perspective, \
         rendering style, shading, and small colour shifts from lighting. \
         If a definition describes a hairstyle (ponytail, side, bangs, bob) \
         or a garment's cut or layering (pinafore over a top, sleeve length), \
         that wording is a rendering preference for the generator, not an \
         identity anchor: only the hair colour and the garment colours count. \
         A deviation counts only when it is unmistakable at a glance and \
         would make a reader think this is a different character; when in \
         doubt, the verdict is on_model.\n\
         - on_model: a character of this kind appears and reads as the same \
           character\n\
         - off_model: a character of this kind appears but an identity \
           attribute is unmistakably wrong (name it)\n\
         - absent: no character of this kind appears in the image\n\n\
         Return exactly one fenced yaml code block and nothing else of \
         consequence:\n\
         ```yaml\n\
         verdicts:\n\
         - name: <cast member name>\n\
         \x20 verdict: on_model | off_model | absent\n\
         \x20 attribute: hair_colour | glasses | garment_colour | body_shape | body_colour | face_screen | antenna | pouch | hairstyle | garment_cut | pose | style | other\n\
         \x20 reason: one short factual sentence\n\
         ```\n\
         with exactly one entry per cast member listed above; attribute names \
         what the reason is about (for on_model or absent, use other).",
        image_abs.display()
    );
    p
}

fn extract_verdicts(reply: &str, label: &str, cast: &[CastMember]) -> Result<Vec<MemberVerdict>> {
    #[derive(Deserialize)]
    struct Doc {
        verdicts: Vec<MemberVerdict>,
    }
    let fence = YAML_FENCE
        .captures_iter(reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no fenced yaml block"))?;
    let doc: Doc = serde_norway::from_str(&fence)
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
    Ok(doc.verdicts.into_iter().map(license_verdict).collect())
}

fn license_verdict(mut v: MemberVerdict) -> MemberVerdict {
    let licensed = v
        .attribute
        .as_deref()
        .is_some_and(|a| LICENSED_ATTRIBUTES.contains(&a));
    if v.verdict == "off_model" && licensed {
        v.verdict = "on_model".to_string();
        v.reason = format!(
            "licensed {}: {}",
            v.attribute.as_deref().unwrap_or(""),
            v.reason
        );
    }
    v
}

struct CheckTarget {
    round_dir: PathBuf,
    file: String,
    purpose: ArtPurpose,
}

fn check_targets(round_dir: &Path, cast: &[CastMember]) -> Result<Vec<CheckTarget>> {
    let briefs_path = round_dir.join("briefs.yaml");
    let round_path = round_dir.join("round.yaml");
    if !briefs_path.exists() || !round_path.exists() {
        return Ok(Vec::new());
    }
    let briefs: BriefsDoc = serde_norway::from_str(&read(&briefs_path)?)
        .with_context(|| format!("parsing {}", briefs_path.display()))?;
    let applies: HashMap<&str, (bool, ArtPurpose)> = briefs
        .briefs
        .iter()
        .map(|b| {
            let a = b.purpose != ArtPurpose::Cover
                || cast
                    .iter()
                    .any(|m| b.prompt.to_lowercase().contains(&m.name.to_lowercase()));
            (b.id.as_str(), (a, b.purpose))
        })
        .collect();
    let round: serde_norway::Value = serde_norway::from_str(&read(&round_path)?)
        .with_context(|| format!("parsing {}", round_path.display()))?;
    let mut out = Vec::new();
    for item in round
        .get("generated")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten()
    {
        let ok = item
            .get("ok")
            .and_then(serde_norway::Value::as_bool)
            .unwrap_or(false);
        let file = item.get("file").and_then(|v| v.as_str()).unwrap_or("");
        let brief = item.get("brief").and_then(|v| v.as_str()).unwrap_or("");
        let Some(&(applicable, purpose)) = applies.get(brief) else {
            continue;
        };
        if ok && !file.is_empty() && round_dir.join(file).exists() && applicable {
            out.push(CheckTarget {
                round_dir: round_dir.to_path_buf(),
                file: file.to_string(),
                purpose,
            });
        }
    }
    Ok(out)
}

pub fn cast_check_run(args: &CastCheckArgs) -> Result<i32> {
    let edition = args.edition.as_str();
    let round_filter = args.round.as_deref();
    let direction_override = args.direction.as_deref();
    let model = &ModelSpec::parse(&args.model)?;
    let edition_dir = resolve_edition_dir(edition)?;
    let edition_label = edition_dir
        .file_name()
        .map_or_else(|| edition.to_string(), |n| n.to_string_lossy().to_string());
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
    let mut exit = 0;
    for round_dir in &select_rounds(&rounds_root, round_filter)? {
        if !check_round(round_dir, &cast, &license, model)? {
            exit = 1;
        }
    }
    let showcase = write_showcase(&edition_dir, &edition_label)?;
    println!("showcase: {}", showcase.display());
    Ok(exit)
}

fn select_rounds(rounds_root: &Path, round_filter: Option<&str>) -> Result<Vec<PathBuf>> {
    let mut round_dirs: Vec<PathBuf> = fs::read_dir(rounds_root)
        .with_context(|| format!("reading {}", rounds_root.display()))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_dir())
        .collect();
    round_dirs.sort();
    Ok(match round_filter {
        Some("all") => round_dirs,
        Some(stamp) => {
            let wanted = rounds_root.join(stamp);
            if !wanted.is_dir() {
                bail!("no round {} under {}", stamp, rounds_root.display());
            }
            vec![wanted]
        }
        None => round_dirs.into_iter().last().into_iter().collect(),
    })
}

fn check_round(
    round_dir: &Path,
    cast: &[CastMember],
    license: &HashMap<ArtPurpose, String>,
    model: &ModelSpec,
) -> Result<bool> {
    let targets = check_targets(round_dir, cast)?;
    let round_name = round_dir.file_name().unwrap().to_string_lossy().to_string();
    if targets.is_empty() {
        println!("{round_name}: no applicable candidates");
        return Ok(true);
    }
    println!("{round_name}: checking {} image(s)", targets.len());
    let caller = Caller::new(round_dir);
    let outcomes = parallel(&targets, |t| {
        let abs = t.round_dir.join(&t.file).canonicalize()?;
        let label = format!("cast-check {}", t.file);
        let prompt = cast_check_prompt(cast, &abs, license.get(&t.purpose).map(String::as_str));
        let verdicts = caller.call_with_parse_images(&label, model, &prompt, &[abs], |r| {
            extract_verdicts(r, &label, cast)
        })?;
        Ok(CastCheckResult {
            file: t.file.clone(),
            verdicts,
        })
    });
    let mut fresh = Vec::new();
    let mut errors = Vec::new();
    for (t, outcome) in targets.iter().zip(outcomes) {
        match outcome {
            Ok(r) => fresh.push(r),
            Err(e) => errors.push(format!("{}: {e:#}", t.file)),
        }
    }

    let check_path = round_dir.join("cast-check.yaml");
    let mut by_file: HashMap<String, CastCheckResult> = if check_path.exists() {
        let old: CastCheckDoc = serde_norway::from_str(&read(&check_path)?)
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
                .map(|v| format!("  {}, {}: {}", r.file, v.name, v.reason))
        })
        .collect();
    write_atomic(
        &check_path,
        serde_norway::to_string(&CastCheckDoc {
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
        eprintln!("  {} check call(s) FAILED:", errors.len());
        for e in &errors {
            eprintln!("    {e}");
        }
    }
    Ok(errors.is_empty())
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
    write_atomic(round_dir.join("round.yaml"), serde_norway::to_string(&doc)?)?;
    Ok(failures)
}

pub const DEFAULT_GEN_CMD: &str = "tools/imagegen {prompt} --out {out} --ref {ref} --size {size}";

fn size_for(purpose: ArtPurpose) -> &'static str {
    match purpose {
        ArtPurpose::Cover => "1440x2160",
        ArtPurpose::Opener => "1760x1024",
        ArtPurpose::Tail => "2160x720",
        ArtPurpose::Closing | ArtPurpose::CastSheet => "1536x2160",
    }
}

const FRAME_GUIDE: &str =
    "\nEvery brief is generated at the pixel size its slot prints in, so compose for \
that frame and nothing else. cover: portrait 2:3, 1440x2160, a full A5 page with the top left reserved for a small \\
wordmark and the bottom 90pt tolerant of a caption line. opener: landscape 1.71:1 \
(the frame is 348x203pt, object-fit cover), 1760x1024; keep every head, hand, \
and essential prop well inside the frame with headroom, since nothing outside \
prints. tail: a 3:1 strip, 2160x720. closing: portrait 1:1.41 (an A5 page), \
1536x2160. Never describe a composition as square unless it is the cover.\n";

struct ArtRun<'a> {
    pub edition: &'a str,
    pub gen_cmd: Option<&'a str>,
    pub candidates: u32,
    pub model: &'a ModelSpec,
    pub dry_run: bool,
    pub showcase_only: bool,
    pub only: Option<&'a str>,
    pub note: Option<&'a str>,
    pub articles: Option<&'a str>,
    pub resume_round: Option<&'a str>,
    pub promote: bool,
}

fn parse_only_purposes(only: Option<&str>) -> Result<Option<Vec<ArtPurpose>>> {
    let Some(raw) = only else {
        return Ok(None);
    };
    let purposes = raw
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|p| {
            slot_purpose(p)
                .map_err(|_| anyhow!("--only accepts {}; got '{p}'", join(SLOT_PURPOSES)))
        })
        .collect::<Result<Vec<_>>>()?;
    if purposes.is_empty() {
        bail!("--only was given but named no purposes");
    }
    Ok(Some(purposes))
}

fn parse_only_articles(
    articles: Option<&str>,
    has_only: bool,
    edition_yaml_text: &str,
) -> Result<Option<Vec<String>>> {
    let Some(raw) = articles else {
        return Ok(None);
    };
    if has_only {
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
    let doc: serde_norway::Value = serde_norway::from_str(edition_yaml_text)
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
    Ok(Some(ids))
}

fn check_scope(
    briefs: &[Brief],
    only_purposes: Option<&[ArtPurpose]>,
    only_articles: Option<&[String]>,
    label: &str,
) -> Result<()> {
    if let Some(purposes) = only_purposes {
        for b in briefs {
            if !purposes.contains(&b.purpose) {
                bail!(
                    "{label}: this round is scoped to {}; brief '{}' has purpose '{}'",
                    join(purposes),
                    b.id,
                    b.purpose
                );
            }
        }
    }
    if let Some(ids) = only_articles {
        for b in briefs {
            let aid = b.article_id.as_deref().unwrap_or("");
            if !matches!(b.purpose, ArtPurpose::Opener | ArtPurpose::Tail)
                || !ids.iter().any(|i| i == aid)
            {
                bail!(
                    "{label}: this round is scoped to opener/tail briefs for {}; brief '{}' is a {} for '{aid}'",
                    ids.join(", "),
                    b.id,
                    b.purpose
                );
            }
        }
    }
    Ok(())
}

fn resume_round(
    opts: &ArtRun,
    resume: &str,
    edition_dir: &Path,
    edition_label: &str,
) -> Result<i32> {
    if opts.dry_run || opts.only.is_some() || opts.note.is_some() || opts.articles.is_some() {
        bail!(
            "--resume-round completes an existing round; drop --dry-run/--only/--note/--articles"
        );
    }
    let gen_cmd = opts
        .gen_cmd
        .ok_or_else(|| anyhow!("--resume-round requires --gen-cmd"))?;
    let mut round_dir = PathBuf::from(resume);
    if !round_dir.join("briefs.yaml").exists() {
        round_dir = edition_dir.join("art/rounds").join(resume);
    }
    let briefs_path = round_dir.join("briefs.yaml");
    let doc: BriefsDoc = serde_norway::from_str(&read(&briefs_path)?)
        .with_context(|| format!("parsing {}", briefs_path.display()))?;
    if doc.briefs.is_empty() {
        bail!("{} has no briefs to resume", briefs_path.display());
    }
    expand_placeholders(gen_cmd)?;
    ensure_ref_placeholder(gen_cmd, &doc.briefs)?;
    println!("resuming round: {}", round_dir.display());
    generate_and_finish(
        &doc.briefs,
        opts.candidates,
        gen_cmd,
        &round_dir,
        edition_dir,
        edition_label,
    )
}

fn dry_run_report(
    opts: &ArtRun,
    briefs: &[Brief],
    round_dir: &Path,
    edition_dir: &Path,
    edition_label: &str,
) -> Result<i32> {
    write_round_yaml(round_dir, edition_label, true, &[])?;
    write_showcase(edition_dir, edition_label)?;
    println!();
    println!("dry run: no image credits spent.");
    match opts.gen_cmd {
        Some(cmd) => {
            let script =
                write_generate_script(round_dir, edition_label, briefs, opts.candidates, cmd)?;
            println!(
                "run {} from the repo root when credits are available, \
                 then review the images in {} and select by hand-editing \
                 edition.yaml.",
                script.display(),
                round_dir.display()
            );
        }
        None => println!(
            "no --gen-cmd recorded; the prompts are in {}/briefs.yaml; \
             generate them by hand, or rerun with --dry-run --gen-cmd to \
             get an executable generate.sh.",
            round_dir.display()
        ),
    }
    Ok(0)
}

pub fn run(args: &ArtArgs) -> Result<i32> {
    let model = ModelSpec::parse(&args.model)?;
    run_round(&ArtRun {
        edition: &args.edition,
        gen_cmd: Some(args.gen_cmd.as_str()),
        candidates: args.candidates,
        model: &model,
        dry_run: args.dry_run,
        showcase_only: args.showcase,
        only: args.only.as_deref(),
        note: args.note.as_deref(),
        articles: args.articles.as_deref(),
        resume_round: args.resume_round.as_deref(),
        promote: args.promote,
    })
}

fn run_round(opts: &ArtRun) -> Result<i32> {
    let ArtRun {
        edition,
        gen_cmd,
        candidates,
        model,
        dry_run,
        showcase_only,
        only,
        note,
        articles,
        resume_round: resume,
        promote,
    } = *opts;
    let edition_dir = resolve_edition_dir(edition)?;
    let edition_label = edition_dir
        .file_name()
        .map_or_else(|| edition.to_string(), |n| n.to_string_lossy().to_string());

    if showcase_only {
        let path = write_showcase(&edition_dir, &edition_label)?;
        println!("showcase rebuilt: {}", path.display());
        return Ok(0);
    }
    if promote {
        return promote_picks(&edition_dir, &edition_label);
    }
    if let Some(resume) = resume {
        return resume_round(opts, resume, &edition_dir, &edition_label);
    }

    if let Some(cmd) = gen_cmd {
        expand_placeholders(cmd)?;
    }
    let edition_yaml_text = read(&edition_dir.join("edition.yaml"))?;

    let round_dir = edition_dir
        .join("art")
        .join("rounds")
        .join(crate::caller::now_stamp());
    crate::caller::create_fresh_dir(&round_dir)?;

    println!("round dir: {}", round_dir.display());

    let only_purposes = parse_only_purposes(only)?;
    let rejected = match &only_purposes {
        Some(purposes) => previous_briefs(&edition_dir, purposes)?,
        None => Vec::new(),
    };
    let only_articles = parse_only_articles(articles, only_purposes.is_some(), &edition_yaml_text)?;

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
        check_scope(
            &briefs,
            only_purposes.as_deref(),
            only_articles.as_deref(),
            label,
        )?;
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
    write_atomic(
        round_dir.join("briefs.yaml"),
        serde_norway::to_string(&briefs_doc)?,
    )?;
    println!("  {} brief(s) proposed", briefs.len());

    if dry_run {
        return dry_run_report(opts, &briefs, &round_dir, &edition_dir, &edition_label);
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

fn promote_picks(edition_dir: &Path, edition_label: &str) -> Result<i32> {
    let moves = crate::picks::promote(edition_dir)?;
    for (pick, round) in &moves {
        println!("  {round} -> {pick}");
    }
    println!(
        "promoted {} pick(s) into {}/art/picks\n\nnext:\n  1. mag source-codes {edition_label}   (opener QR codes)\n  2. mag render {edition_label}\n  3. commit {}/art/picks and edition.yaml",
        moves.len(),
        edition_dir.display(),
        edition_dir.display()
    );
    Ok(0)
}

fn generate_and_finish(
    briefs: &[Brief],
    candidates: u32,
    gen_cmd: &str,
    round_dir: &Path,
    edition_dir: &Path,
    edition_label: &str,
) -> Result<i32> {
    let generated = generate_all(briefs, candidates, gen_cmd, round_dir)?;

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
         (cover.art_path / opener_art.path / tail_art_path / closing_plates); rounds stay local, out of git\n  \
         3. mag art {edition_label} --promote   (picks become committed JPEGs in art/picks)\n  \
         4. mag source-codes {edition_label}   (opener QR codes; reads the picked opener art)\n  \
         5. mag render {edition_label}"
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
        assert!(err.contains("poster"), "{err}");
    }

    #[test]
    fn extract_briefs_feedback_lists_only_slot_purposes() {
        let reply = yaml_reply("briefs:\n- id: x\n  purpose: poster\n  prompt: p\n");
        let err = extract_briefs(&reply, "t").unwrap_err().to_string();
        assert!(
            err.contains("closing") && !err.contains("cast-sheet"),
            "{err}"
        );
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
    fn shell_single_quote_survives_apostrophes_and_metacharacters() {
        assert_eq!(shell_single_quote("it's"), "'it'\\''s'");
        assert_eq!(shell_single_quote("$(x); `y` && z"), "'$(x); `y` && z'");
    }

    #[test]
    fn candidate_command_substitutes_prompt_and_out() {
        let brief = Brief {
            id: "tail-a".into(),
            purpose: ArtPurpose::Tail,
            article_id: Some("a".into()),
            prompt: "a robot's day".into(),
            subject: None,
            composition: None,
            alt_text: Some("alt".into()),
            credit: None,
            cast_references: None,
        };
        let (filename, cmd, env) =
            candidate_command("gen '{prompt}' -o {out}", &brief, 2, Path::new("rounds/r1"))
                .unwrap();
        assert_eq!(filename, "tail-a-v2.png");
        assert_eq!(cmd, "gen \"$MAG_PROMPT\" -o \"$MAG_OUT\"");
        assert_eq!(env[0].1, "a robot's day (variation 2)");
        assert_eq!(env[1].1, "rounds/r1/tail-a-v2.png");
    }

    fn brief(id: &str, purpose: &str, prompt: &str) -> Brief {
        Brief {
            id: id.into(),
            purpose: ArtPurpose::parse(purpose).unwrap(),
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
        let pair = "Recurring cast: draw exactly as specified, never \
                    redesign: Pedro: a boy. Maro: a robot.";
        let solo = "Recurring cast: draw exactly as specified, never \
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
        let license: HashMap<ArtPurpose, String> =
            [(ArtPurpose::Tail, "may age up".to_string())].into();
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
        assert_eq!(ok.get(&ArtPurpose::Tail).map(String::as_str), Some("quiet"));
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
    fn candidate_command_refuses_a_placeholder_inside_a_larger_word() {
        let b = brief("p1", "cover", "a prompt");
        for template in [
            "gen --p=\"x {prompt}\"",
            "gen --p='x {prompt}'",
            "gen --p={prompt}",
            "gen 'a {prompt} b'",
            "gen \"a {out} b\"",
        ] {
            assert!(candidate_command(template, &b, 1, Path::new("r")).is_err());
        }
    }

    #[test]
    fn candidate_command_substitutes_refs_or_empties_the_placeholder() {
        let mut b = brief("opener-a", "opener", "maro waves");
        let template = "imagegen '{prompt}' --out {out} --ref '{ref}'";
        let (_, cmd, env) = candidate_command(template, &b, 1, Path::new("r")).unwrap();
        assert!(cmd.ends_with("--ref \"$MAG_REF\""), "{cmd}");
        assert_eq!(env[2].1, "");
        b.cast_references = Some(vec!["a.png".into(), "b.png".into()]);
        let (_, _, env) = candidate_command(template, &b, 1, Path::new("r")).unwrap();
        assert_eq!(env[2].1, "a.png b.png");
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
        let direction: serde_norway::Value = serde_norway::from_str(
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
            ed.join("../../magazine.toml"),
            "[publication]\nname = \"Test\"\n",
        )
        .unwrap();
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
            html.contains("opener-a</h3>") || html.contains("opener-a: a</h3>"),
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
            purpose: ArtPurpose::Cover,
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

    #[test]
    fn hostile_values_reach_the_generator_as_data_only() {
        let dir = std::env::temp_dir().join(format!("mag-gen-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let marker = dir.join("pwned");
        let mut b = brief(
            "cover-a",
            "cover",
            &format!("$(touch {}); `x` it's", marker.display()),
        );
        b.cast_references = Some(vec!["a b.png".into()]);
        let cmd = "printf '%s|%s|%s' {prompt} {ref} {size} > {out}";
        let (file, cmd_str, env) = candidate_command(cmd, &b, 1, &dir).unwrap();
        let out = dir.join(&file);
        run_gen_command(&cmd_str, &env, &out).unwrap();
        let got = fs::read_to_string(&out).unwrap();
        assert!(got.starts_with("$(touch "), "{got}");
        assert!(
            got.contains("it's (variation 1)|a b.png|1440x2160"),
            "{got}"
        );
        assert!(!marker.exists());
        let script = write_generate_script(&dir, "x", &[b], 1, cmd).unwrap();
        let status = Command::new("sh").arg(&script).status().unwrap();
        assert!(status.success());
        assert!(!marker.exists());
        assert!(fs::read_to_string(&out)
            .unwrap()
            .contains("it's (variation 1)"));
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn extract_briefs_rejects_unsafe_and_duplicate_ids() {
        for bad in ["a;b", "a$(x)", "a b", "../x", "A", "a--b", "-a", ""] {
            let reply = yaml_reply(&format!(
                "briefs:\n- id: \"{bad}\"\n  purpose: cover\n  prompt: p\n"
            ));
            let err = extract_briefs(&reply, "t").unwrap_err().to_string();
            assert!(err.contains("brief id"), "{bad}: {err}");
        }
        let reply = yaml_reply(
            "briefs:\n- id: x\n  purpose: cover\n  prompt: p\n- id: x\n  purpose: cover\n  prompt: p\n",
        );
        let err = extract_briefs(&reply, "t").unwrap_err().to_string();
        assert!(err.contains("more than once"), "{err}");
    }
}
