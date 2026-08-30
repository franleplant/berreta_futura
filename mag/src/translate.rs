use crate::caller::{Caller, ModelSpec};
use crate::produce::{section, INLINE_PREAMBLE};
use anyhow::{anyhow, bail, Context, Result};
use regex::Regex;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::thread;

fn read(path: &Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

#[derive(Clone)]
struct PieceJob {
    id: String,
    source_path: PathBuf,
    output_path: PathBuf,
}

#[derive(Serialize, Debug, Clone)]
struct PieceTranslation {
    piece: String,
    state: String,
    words: usize,
}

fn discover_jobs(run_dir: &Path) -> Result<Vec<PieceJob>> {
    let mut jobs = Vec::new();
    let translations_root = run_dir.join("translations").join("es");

    let articles_dir = run_dir.join("articles");
    if articles_dir.is_dir() {
        let mut ids: Vec<String> = fs::read_dir(&articles_dir)
            .with_context(|| format!("reading {}", articles_dir.display()))?
            .filter_map(|e| e.ok())
            .filter(|e| e.path().is_dir())
            .filter_map(|e| e.file_name().into_string().ok())
            .collect();
        ids.sort();
        for id in ids {
            let source_path = articles_dir.join(&id).join("final.md");
            if source_path.is_file() {
                let output_path = translations_root.join("articles").join(format!("{id}.md"));
                jobs.push(PieceJob {
                    id,
                    source_path,
                    output_path,
                });
            }
        }
    }

    let editorial_final = run_dir.join("editorial").join("final.md");
    if editorial_final.is_file() {
        jobs.push(PieceJob {
            id: "editorial".to_string(),
            source_path: editorial_final,
            output_path: translations_root.join("editorial.md"),
        });
    }

    Ok(jobs)
}

fn build_prompt(piece_id: &str, manuscript: &str, hash_hex: &str) -> Result<String> {
    let lens_path = PathBuf::from("prompts").join("translation-es.md");
    let mut out = String::new();
    out += INLINE_PREAMBLE;
    out += &section("prompts/translation-es.md", &read(&lens_path)?);
    out += &section(&format!("english manuscript: {piece_id}"), manuscript);
    out += &format!("\nenglish_sha256: {hash_hex}\n");
    out += "\nCompute nothing yourself — use the english_sha256 value given above exactly \
            as provided, unchanged. Reply with exactly one fenced ```json code block \
            containing a JSON object with exactly two keys: \"english_sha256\" (the value \
            above, unchanged) and \"markdown\" (a JSON string holding the full Spanish \
            translation). Do not include any other fenced ```json block in your reply.";
    Ok(out)
}

fn parse_translation(
    reply: &str,
    expected_hash: &str,
    english_fence_count: usize,
    label: &str,
) -> Result<String> {
    let re = Regex::new(r"(?s)```json\s*\n(.*)```").unwrap();
    let fence = re
        .captures_iter(reply)
        .last()
        .map(|c| c[1].trim().to_string())
        .ok_or_else(|| anyhow!("{label}: reply contained no ```json fenced block"))?;

    let value: serde_json::Value = serde_json::from_str(&fence)
        .with_context(|| format!("{label}: invalid json in fenced block"))?;
    let obj = value
        .as_object()
        .ok_or_else(|| anyhow!("{label}: json block is not an object"))?;

    let got_hash = obj
        .get("english_sha256")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("{label}: json missing string field 'english_sha256'"))?;
    if got_hash != expected_hash {
        bail!(
            "{label}: english_sha256 mismatch — model must echo the provided hash \
             unchanged (expected {expected_hash}, got {got_hash})"
        );
    }

    let markdown = obj
        .get("markdown")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("{label}: json missing string field 'markdown'"))?;
    if markdown.trim().is_empty() {
        bail!("{label}: markdown field is empty");
    }

    let got_fence_count = markdown.matches("```").count();
    if got_fence_count != english_fence_count {
        bail!(
            "{label}: fenced code block count mismatch — english input has \
             {english_fence_count}, translation has {got_fence_count}"
        );
    }

    Ok(markdown.to_string())
}

fn translate_piece(caller: &Caller, model: &ModelSpec, job: &PieceJob) -> Result<PieceTranslation> {
    if job.output_path.exists() {
        println!("  {}: translation exists, skipping (resume)", job.id);
        let existing = read(&job.output_path)?;
        return Ok(PieceTranslation {
            piece: job.id.clone(),
            state: "skipped".to_string(),
            words: existing.split_whitespace().count(),
        });
    }

    let manuscript = read(&job.source_path)?;
    let hash_hex = hex::encode(Sha256::digest(manuscript.as_bytes()));
    let english_fence_count = manuscript.matches("```").count();
    let prompt = build_prompt(&job.id, &manuscript, &hash_hex)?;

    let label = format!("translate:{}", job.id);
    let parse_label = job.id.clone();
    let markdown = caller.call_with_parse(&label, model, &prompt, |reply| {
        parse_translation(reply, &hash_hex, english_fence_count, &parse_label)
    })?;

    if let Some(parent) = job.output_path.parent() {
        fs::create_dir_all(parent).with_context(|| format!("creating {}", parent.display()))?;
    }
    fs::write(&job.output_path, &markdown)
        .with_context(|| format!("writing {}", job.output_path.display()))?;

    Ok(PieceTranslation {
        piece: job.id.clone(),
        state: "done".to_string(),
        words: markdown.split_whitespace().count(),
    })
}

pub fn run(run_dir: &Path, model: &ModelSpec) -> Result<i32> {
    let jobs = discover_jobs(run_dir)?;
    let translations_root = run_dir.join("translations").join("es");
    fs::create_dir_all(translations_root.join("articles"))
        .with_context(|| format!("creating {}", translations_root.display()))?;

    let caller = Arc::new(Caller::new(run_dir));

    let mut handles = Vec::new();
    for job in &jobs {
        let caller = Arc::clone(&caller);
        let model = model.clone();
        let job = job.clone();
        handles.push(thread::spawn(move || -> Result<PieceTranslation> {
            translate_piece(&caller, &model, &job)
        }));
    }

    let mut results = Vec::with_capacity(jobs.len());
    let mut failures: Vec<(String, String)> = Vec::new();
    for (job, handle) in jobs.iter().zip(handles) {
        match handle.join() {
            Ok(Ok(status)) => results.push(status),
            Ok(Err(e)) => {
                eprintln!("  FAILED {}: {e}", job.id);
                failures.push((job.id.clone(), e.to_string()));
                results.push(PieceTranslation {
                    piece: job.id.clone(),
                    state: "failed".to_string(),
                    words: 0,
                });
            }
            Err(_) => {
                eprintln!("  FAILED {}: worker thread panicked", job.id);
                failures.push((job.id.clone(), "worker thread panicked".to_string()));
                results.push(PieceTranslation {
                    piece: job.id.clone(),
                    state: "failed".to_string(),
                    words: 0,
                });
            }
        }
    }

    fs::write(
        translations_root.join("status.yaml"),
        serde_yaml::to_string(&results)?,
    )
    .with_context(|| {
        format!(
            "writing {}",
            translations_root.join("status.yaml").display()
        )
    })?;

    println!(
        "{} pieces, {} calls, ${:.2}",
        jobs.len(),
        caller.calls(),
        caller.total_cost()
    );

    if !failures.is_empty() {
        eprintln!("\n{} piece(s) failed to translate:", failures.len());
        for (id, e) in &failures {
            eprintln!("  {id}: {e}");
        }
    }

    Ok(if failures.is_empty() { 0 } else { 1 })
}
