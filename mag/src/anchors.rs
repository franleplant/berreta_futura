use crate::caller::{Caller, ModelSpec};
use crate::model::spec::{ArticleRow, EditionFile};
use crate::produce::yq;
use crate::render::{load_edition, manuscript_headings, pick_content_run};
use anyhow::{anyhow, bail, Result};
use std::path::Path;

#[derive(clap::Args)]
pub struct AnchorsArgs {
    pub edition: String,
    #[arg(
        long,
        help = "Run dir whose headings to anchor to (default: newest complete run)"
    )]
    pub run: Option<String>,
    #[arg(
        long,
        default_value = "haiku",
        help = "Cheap model that re-anchors figures to the run's headings"
    )]
    pub model: String,
    #[arg(long, help = "Only list unresolved anchors, no model call, no edits")]
    pub check: bool,
}

struct Pending {
    id: String,
    anchor: String,
    meta: String,
}

fn pending_figures(article: &ArticleRow, headings: &[String]) -> Vec<Pending> {
    let unresolved = |anchor: &str| {
        !(anchor.is_empty() || anchor == "__opener__" || headings.iter().any(|h| h == anchor))
    };
    article
        .figures
        .iter()
        .filter(|figure| unresolved(&figure.anchor))
        .map(|figure| {
            let mut meta = format!("- id: {}\n", figure.id);
            for (label, value) in [
                ("caption", &figure.caption),
                ("alt_text", &figure.alt_text),
                ("previous_section", &figure.anchor),
            ] {
                if !value.is_empty() {
                    meta += &format!("  {label}: {value}\n");
                }
            }
            Pending {
                id: figure.id.clone(),
                anchor: figure.anchor.clone(),
                meta,
            }
        })
        .collect()
}

fn final_md(run: &Path, article_id: &str) -> std::path::PathBuf {
    run.join("articles").join(article_id).join("final.md")
}

pub(crate) fn unresolved(run: &Path, edition: &EditionFile) -> Vec<String> {
    let mut stale = Vec::new();
    for article in edition.articles.iter().filter(|a| !a.id.is_empty()) {
        let headings = manuscript_headings(&final_md(run, &article.id));
        for pending in pending_figures(article, &headings) {
            stale.push(format!(
                "{}:{} (anchor '{}')",
                article.id, pending.id, pending.anchor
            ));
        }
    }
    stale
}

fn parse_anchor_reply(
    reply: &str,
    ids: &[String],
    headings: &[String],
) -> Result<Vec<Option<String>>> {
    let mut out = Vec::with_capacity(ids.len());
    for id in ids {
        let line = reply
            .lines()
            .find(|l| {
                l.split("::")
                    .next()
                    .is_some_and(|s| s.trim().trim_start_matches('-').trim() == id)
            })
            .ok_or_else(|| anyhow!("reply has no `{id} :: <heading>` line"))?;
        let value = line
            .split_once("::")
            .map_or("", |(_, v)| v)
            .trim()
            .trim_start_matches("##")
            .trim();
        if value.eq_ignore_ascii_case("none") {
            out.push(None);
            continue;
        }
        let matched = headings
            .iter()
            .find(|h| h.trim().eq_ignore_ascii_case(value))
            .ok_or_else(|| {
                anyhow!(
                    "'{value}' is not a heading of this manuscript; the headings are: {}",
                    headings.join(" | ")
                )
            })?;
        out.push(Some(matched.clone()));
    }
    Ok(out)
}

fn resolve(
    caller: &Caller,
    model: &ModelSpec,
    article_id: &str,
    manuscript: &Path,
    headings: &[String],
    pending: &[Pending],
) -> Result<Vec<Option<String>>> {
    if headings.is_empty() {
        return Ok(vec![None; pending.len()]);
    }
    let ids: Vec<String> = pending.iter().map(|p| p.id.clone()).collect();
    let meta: String = pending.iter().map(|p| p.meta.as_str()).collect();
    let text = std::fs::read_to_string(manuscript)?;
    let prompt = format!(
        "Below are a magazine article manuscript and the figures that must be placed in \
         it. For each figure, choose the manuscript section heading whose section \
         discusses what the figure shows. Reply with exactly one line per figure, in the \
         order given, formatted `<figure id> :: <heading text exactly as written, \
         without the leading ##>`. Use `<figure id> :: NONE` only if no section fits.\n\n\
         ========== manuscript ==========\n\n{text}\n\n\
         ========== figures ==========\n\n{meta}"
    );
    caller.call_with_parse(
        &format!("{article_id} figure anchors"),
        model,
        &prompt,
        |reply| parse_anchor_reply(reply, &ids, headings),
    )
}

fn patch_anchor_lines(yaml: &str, edits: &[(String, String, String)]) -> Result<String> {
    let id_of = |line: &str, prefix: &str| {
        line.strip_prefix(prefix)
            .map(|id| id.trim().trim_matches(['\'', '"']).to_string())
    };
    let (mut article, mut figure) = (String::new(), String::new());
    let mut applied = 0;
    let mut out: Vec<String> = Vec::new();
    let mut skipping = false;
    for line in yaml.lines() {
        if skipping && line.starts_with("      ") {
            continue;
        }
        skipping = false;
        if let Some(id) = id_of(line, "- id:") {
            article = id;
        } else if let Some(id) = id_of(line, "  - id:") {
            figure = id;
        } else if line.starts_with("    anchor:") {
            if let Some((_, _, heading)) =
                edits.iter().find(|(a, f, _)| *a == article && *f == figure)
            {
                out.push(format!("    anchor: {}", yq(heading)));
                applied += 1;
                skipping = true;
                continue;
            }
        }
        out.push(line.to_string());
    }
    if applied != edits.len() {
        bail!(
            "edition.yaml: patched {applied} of {} anchors; edit the rest by hand",
            edits.len()
        );
    }
    Ok(out.join("\n") + "\n")
}

pub fn run(args: &AnchorsArgs) -> Result<i32> {
    let edition = load_edition(&args.edition)?;
    let Some(run) = pick_content_run(
        args.run.as_deref(),
        &edition.dir,
        &edition.article_ids,
        &edition.yaml,
    )?
    else {
        bail!("{} has no complete run to anchor against", args.edition);
    };
    let stale = unresolved(&run, &edition.yaml);
    for line in &stale {
        println!("  unresolved: {line}");
    }
    if stale.is_empty() {
        println!(
            "all figure anchors resolve\nnext: mag render {}",
            args.edition
        );
        return Ok(0);
    }
    if args.check {
        println!(
            "\nnext: mag anchors {} --run {}",
            args.edition,
            run.display()
        );
        return Ok(1);
    }
    let model = ModelSpec::parse(&args.model)?;
    let caller = Caller::new(&run);
    let (mut edits, mut dropped) = (Vec::new(), Vec::new());
    for article in edition.yaml.articles.iter().filter(|a| !a.id.is_empty()) {
        let manuscript = final_md(&run, &article.id);
        let headings = manuscript_headings(&manuscript);
        let pending = pending_figures(article, &headings);
        if pending.is_empty() {
            continue;
        }
        let answers = resolve(
            &caller,
            &model,
            &article.id,
            &manuscript,
            &headings,
            &pending,
        )?;
        for (figure, answer) in pending.iter().zip(answers) {
            match answer {
                Some(heading) => {
                    println!(
                        "  re-anchored {}:{} '{}' -> '{heading}'",
                        article.id, figure.id, figure.anchor
                    );
                    edits.push((article.id.clone(), figure.id.clone(), heading));
                }
                None => dropped.push(format!(
                    "{}:{} (was '{}')",
                    article.id, figure.id, figure.anchor
                )),
            }
        }
    }
    let path = edition.yaml_path;
    std::fs::write(
        &path,
        patch_anchor_lines(&std::fs::read_to_string(&path)?, &edits)?,
    )?;
    println!("patched {} anchor(s) in {}", edits.len(), path.display());
    if dropped.is_empty() {
        println!("\nnext: mag render {}", args.edition);
        return Ok(0);
    }
    println!("no heading of this run fits these figures; remove them from edition.yaml or set an anchor by hand:");
    for d in &dropped {
        println!("    {d}");
    }
    println!("\nthen: mag anchors {} --check", args.edition);
    Ok(1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn anchor_reply_matches_headings_exactly_and_case_insensitively() {
        let ids = vec!["fig-a".to_string(), "fig-b".to_string()];
        let headings = vec!["The Escalation".to_string(), "How it talked".to_string()];
        let reply = "fig-a :: the escalation\nfig-b :: NONE\n";
        let out = parse_anchor_reply(reply, &ids, &headings).unwrap();
        assert_eq!(out, vec![Some("The Escalation".to_string()), None]);
        assert!(
            parse_anchor_reply("fig-a :: Not A Heading\nfig-b :: NONE", &ids, &headings).is_err()
        );
        assert!(parse_anchor_reply("fig-a :: The Escalation", &ids, &headings).is_err());
    }

    #[test]
    fn only_the_named_figure_anchor_is_rewritten_and_comments_survive() {
        let yaml = "# top\narticles:\n- id: a\n  figures:\n  - id: f1\n    anchor: Old one\n    layout: x\n  - id: f2\n    anchor: Keep\n- id: b\n  figures:\n  - id: f1\n    anchor: Other\n";
        let edits = vec![(
            "b".to_string(),
            "f1".to_string(),
            "New: heading".to_string(),
        )];
        let out = patch_anchor_lines(yaml, &edits).unwrap();
        assert_eq!(out, yaml.replace("anchor: Other", "anchor: 'New: heading'"));
        assert!(patch_anchor_lines(yaml, &[("c".into(), "f".into(), "H".into())]).is_err());
    }
}
