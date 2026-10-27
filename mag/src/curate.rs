use crate::caller::{Caller, ModelSpec};
use anyhow::{bail, Context, Result};
use regex::Regex;
use serde::Deserialize;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

static MEDIA_LINE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?m)^[ \t]*!\[[^\]]*\]\(media/([^)\s]+)\)[ \t]*\n?").unwrap());
static YAML_FENCE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?s)```ya?ml\s*\n(.*?)```").unwrap());
const CONTEXT_CHARS: usize = 500;
const BATCH: usize = 12;

#[derive(Deserialize)]
struct Verdict {
    file: String,
    verdict: String,
    reason: String,
}

#[derive(Deserialize)]
struct Reply {
    images: Vec<Verdict>,
}

fn context_of(article: &str, start: usize, end: usize) -> String {
    let before: String = article[..start]
        .chars()
        .rev()
        .take(CONTEXT_CHARS)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect();
    let after: String = article[end..].chars().take(CONTEXT_CHARS).collect();
    format!("{}\n[IMAGE HERE]\n{}", before.trim(), after.trim())
}

fn parse(reply: &str, files: &[String]) -> Result<Vec<Verdict>> {
    let body = YAML_FENCE
        .captures_iter(reply)
        .last()
        .map_or(reply, |c| c.get(1).map_or(reply, |m| m.as_str()));
    let doc: Reply =
        serde_norway::from_str(body).context("figure curation reply is not the yaml asked for")?;
    let named: Vec<&str> = doc.images.iter().map(|v| v.file.as_str()).collect();
    if named != files.iter().map(String::as_str).collect::<Vec<_>>() {
        bail!("figure curation named {named:?}; expected exactly {files:?} in order");
    }
    if let Some(v) = doc
        .images
        .iter()
        .find(|v| !matches!(v.verdict.as_str(), "keep" | "drop"))
    {
        bail!(
            "figure curation verdict {:?} for {} is not keep or drop",
            v.verdict,
            v.file
        );
    }
    Ok(doc.images)
}

pub fn curate(article: &str, title: &str, media_dir: &Path, spec: &ModelSpec) -> Result<String> {
    let found: Vec<(String, String)> = MEDIA_LINE
        .captures_iter(article)
        .map(|c| {
            let whole = c.get(0).expect("match");
            (
                c[1].to_string(),
                context_of(article, whole.start(), whole.end()),
            )
        })
        .collect();
    if found.is_empty() {
        return Ok(article.to_string());
    }
    let doc = fs::read_to_string(crate::util::prompts_path("figure-curation.md"))?;
    let caller = Caller::new(Path::new(".magazine/capture"));
    let mut dropped = Vec::new();
    for chunk in found.chunks(BATCH) {
        let files: Vec<String> = chunk.iter().map(|(f, _)| f.clone()).collect();
        let images: Vec<PathBuf> = files
            .iter()
            .map(|f| media_dir.join(f).canonicalize())
            .collect::<std::io::Result<_>>()?;
        let mut prompt = format!("{doc}\n\nArticle: {title}\n");
        for ((file, context), path) in chunk.iter().zip(&images) {
            let _ = write!(
                prompt,
                "\n--- {file} (attached; also at {})\n{context}\n",
                path.display()
            );
        }
        let verdicts =
            caller.call_with_parse_images("curate figures", spec, &prompt, &images, |r| {
                parse(r, &files)
            })?;
        dropped.extend(verdicts.into_iter().filter(|v| v.verdict == "drop"));
    }
    let mut out = article.to_string();
    for v in &dropped {
        println!("  dropped figure media/{}: {}", v.file, v.reason);
        out = MEDIA_LINE
            .replace_all(&out, |c: &regex::Captures| {
                if c[1] == v.file {
                    String::new()
                } else {
                    c[0].to_string()
                }
            })
            .into_owned();
        fs::remove_file(media_dir.join(&v.file))?;
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_reply_must_judge_every_image_in_order_as_keep_or_drop() {
        let files = vec!["001.png".to_string(), "002.jpg".to_string()];
        let ok = "```yaml\nimages:\n- file: 001.png\n  verdict: keep\n  reason: a chart\n- file: 002.jpg\n  verdict: drop\n  reason: a banner\n```";
        assert_eq!(parse(ok, &files).unwrap().len(), 2);
        let missing = "```yaml\nimages:\n- file: 001.png\n  verdict: keep\n  reason: r\n```";
        assert!(parse(missing, &files).is_err());
        let odd = ok.replace("drop", "maybe");
        assert!(parse(&odd, &files).is_err());
    }

    #[test]
    fn media_lines_carry_their_context() {
        let article = "Before text.\n\n![chart](media/001.png)\n\nAfter text.\n";
        let c = MEDIA_LINE.captures(article).unwrap();
        let whole = c.get(0).unwrap();
        assert_eq!(&c[1], "001.png");
        let context = context_of(article, whole.start(), whole.end());
        assert!(context.starts_with("Before text.") && context.ends_with("After text."));
    }
}
