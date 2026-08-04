// Port of tools/produce.py's `plan` subcommand: one model call proposes
// plan.yaml for an edition; a human edits it before `mag produce` runs it.

use crate::caller::{Caller, ModelSpec};
use crate::produce::INLINE_PREAMBLE;
use anyhow::{anyhow, bail, Context, Result};
use regex::Regex;
use std::fs;
use std::path::PathBuf;

fn section(title: &str, body: &str) -> String {
    format!("\n\n========== {title} ==========\n\n{}\n", body.trim())
}

fn read(path: &std::path::Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

/// Directories under editions/ whose name starts with `edition` — mirrors
/// `sorted(ROOT.glob(f"editions/{edition}*"))`.
fn matching_edition_dirs(edition: &str) -> Result<Vec<PathBuf>> {
    let root = PathBuf::from("editions");
    let mut out = Vec::new();
    if root.is_dir() {
        for entry in fs::read_dir(&root).with_context(|| format!("reading {}", root.display()))? {
            let path = entry?.path();
            if path.is_dir() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if name.starts_with(edition) {
                        out.push(path);
                    }
                }
            }
        }
    }
    out.sort();
    Ok(out)
}

/// `editions/00*/edition.yaml`, sorted — past edition specs, for used sources
/// and tone.
fn past_edition_specs() -> Result<Vec<PathBuf>> {
    let root = PathBuf::from("editions");
    let mut out = Vec::new();
    if root.is_dir() {
        for entry in fs::read_dir(&root).with_context(|| format!("reading {}", root.display()))? {
            let path = entry?.path();
            if path.is_dir() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if name.starts_with("00") {
                        let spec = path.join("edition.yaml");
                        if spec.exists() {
                            out.push(spec);
                        }
                    }
                }
            }
        }
    }
    out.sort();
    Ok(out)
}

pub fn propose_plan(edition: &str, model: &ModelSpec) -> Result<i32> {
    let dirs = matching_edition_dirs(edition)?;
    let out_dir = dirs.into_iter().next().unwrap_or_else(|| PathBuf::from("editions").join(edition));
    let out_path = out_dir.join("plan.yaml");
    if out_path.exists() {
        bail!("{} already exists; edit it or delete it first", out_path.display());
    }

    let lib_root = PathBuf::from("library/sources");
    let mut src_dirs: Vec<PathBuf> = fs::read_dir(&lib_root)
        .with_context(|| format!("reading {}", lib_root.display()))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_dir())
        .collect();
    src_dirs.sort();

    let mut excerpts = String::new();
    for src_dir in &src_dirs {
        let extract = src_dir.join("extracted.md");
        if extract.exists() {
            let body = read(&extract)?;
            let words: Vec<&str> = body.split_whitespace().take(600).collect();
            let name = src_dir.file_name().unwrap().to_string_lossy();
            excerpts += &section(&format!("source: {name}"), &words.join(" "));
        }
    }

    let past_specs = past_edition_specs()?;
    let past: Vec<String> = past_specs.iter().map(|p| read(p)).collect::<Result<_>>()?;

    let task = format!(
        "Propose the plan for edition {edition} of this magazine. Pick the 7 \
strongest, most complementary unpublished sources below (skip any already \
used by a past edition), pair related sources where it makes one better \
article, and assign each article a content_mode: faithful_synthesis (retell \
at ~1/3 length), faithful_edit (light edit at source length), or \
in_a_nutshell (explainer). Derive authors from the sources. Return exactly \
one yaml document between <plan> and </plan> tags with this shape:\n\n\
edition:\n  id: <id>\n  title: ...\n  subtitle: ...\n\
articles:\n- id: <slug>\n  title: ...\n  short_title: ...\n\
  author: ...\n  author_note: ...\n  content_mode: ...\n\
  source_ids: [ ... ]\n  rationale: <one line>"
    );

    let mut prompt = String::new();
    prompt += INLINE_PREAMBLE;
    prompt += &section("task", &task);
    prompt += &section("past edition specs (for used sources and tone)", &past.join("\n---\n"));
    prompt += &excerpts;

    // The plan call logs into the edition dir itself.
    fs::create_dir_all(&out_dir)?;
    let caller = Caller::new(&out_dir);
    let reply = caller.llm(&format!("plan {edition}"), model, &prompt)?;

    let re = Regex::new(r"(?s)<plan>(.*?)</plan>").unwrap();
    let plan_text = re
        .captures_iter(&reply)
        .last()
        .map(|c| c[1].to_string())
        .ok_or_else(|| anyhow!("plan reply contained no <plan> block"))?;
    let plan_value: serde_yaml::Value = serde_yaml::from_str(&plan_text).context("parsing <plan> block as yaml")?;

    fs::create_dir_all(&out_dir)?;
    fs::write(&out_path, serde_yaml::to_string(&plan_value)?)?;
    println!("\nwrote {} — edit it, then: mag produce {}", out_path.display(), out_path.display());
    Ok(0)
}
