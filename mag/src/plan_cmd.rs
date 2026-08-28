// The `plan` subcommand, deterministic: every source queued for the intake
// edition in library/release-state.yaml becomes one article row in plan.yaml.
// No model call, no selection — the editor curates by editing the file.
// Idempotent: re-running appends a row per queued source the plan does not
// reference yet and never rewrites existing rows, so hand edits (merged
// source_ids, content_mode flips, titles, rationales) survive later captures.

use anyhow::{anyhow, bail, Context, Result};
use std::fs;
use std::path::PathBuf;

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

/// The sources queued for an edition in library/release-state.yaml: the
/// collecting entry whose id starts with the requested edition label.
fn queued_source_ids(release_state: &str, edition: &str) -> Result<(String, Vec<String>)> {
    let doc: serde_yaml::Value =
        serde_yaml::from_str(release_state).context("parsing library/release-state.yaml")?;
    let collecting = doc
        .get("collecting_editions")
        .and_then(|v| v.as_sequence())
        .ok_or_else(|| anyhow!("release-state.yaml has no collecting_editions list"))?;
    for entry in collecting {
        let id = entry.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if !id.starts_with(edition) {
            continue;
        }
        let sources = entry
            .get("source_ids")
            .and_then(|v| v.as_sequence())
            .ok_or_else(|| anyhow!("collecting edition '{id}' has no source_ids"))?
            .iter()
            .map(|v| {
                v.as_str()
                    .map(str::to_string)
                    .ok_or_else(|| anyhow!("non-string source id in '{id}'"))
            })
            .collect::<Result<Vec<String>>>()?;
        if sources.is_empty() {
            bail!("collecting edition '{id}' has no sources queued");
        }
        return Ok((id.to_string(), sources));
    }
    bail!("no collecting edition matching '{edition}' in library/release-state.yaml")
}

/// An article slug from a library source id: the trailing capture-hash
/// segment goes, the truncation artifacts of slug generation stay for the
/// editor to tidy.
fn article_slug(source_id: &str) -> String {
    let trimmed = match source_id.rsplit_once('-') {
        Some((head, tail))
            if tail.len() == 8 && tail.chars().all(|c| c.is_ascii_hexdigit()) =>
        {
            head
        }
        _ => source_id,
    };
    trimmed.trim_end_matches('-').to_string()
}

fn article_row(source_id: &str, title: &str, author: &str, mode: &str) -> serde_yaml::Value {
    let mut row = serde_yaml::Mapping::new();
    let mut set = |k: &str, v: serde_yaml::Value| {
        row.insert(serde_yaml::Value::String(k.to_string()), v);
    };
    set("id", serde_yaml::Value::String(article_slug(source_id)));
    set("title", serde_yaml::Value::String(title.to_string()));
    set("author", serde_yaml::Value::String(author.to_string()));
    set("content_mode", serde_yaml::Value::String(mode.to_string()));
    set(
        "source_ids",
        serde_yaml::Value::Sequence(vec![serde_yaml::Value::String(source_id.to_string())]),
    );
    serde_yaml::Value::Mapping(row)
}

/// The source ids referenced by any article row in an existing plan.
fn referenced_source_ids(plan_text: &str) -> Result<std::collections::HashSet<String>> {
    let doc: serde_yaml::Value =
        serde_yaml::from_str(plan_text).context("parsing existing plan.yaml")?;
    let articles = doc
        .get("articles")
        .and_then(|v| v.as_sequence())
        .ok_or_else(|| anyhow!("existing plan.yaml has no articles list"))?;
    let mut out = std::collections::HashSet::new();
    for article in articles {
        let sids = article
            .get("source_ids")
            .and_then(|v| v.as_sequence())
            .ok_or_else(|| anyhow!("an article row in plan.yaml has no source_ids"))?;
        for sid in sids {
            let sid = sid
                .as_str()
                .ok_or_else(|| anyhow!("non-string source id in plan.yaml"))?;
            out.insert(sid.to_string());
        }
    }
    Ok(out)
}

/// The existing plan text with new article rows appended to its articles
/// list. Text-level append so hand-written comments and formatting survive;
/// the result is re-parsed to prove the rows landed in the list (they only
/// can if `articles:` is the file's last top-level key), and nothing is
/// returned for writing otherwise.
fn append_rows(plan_text: &str, rows: &[serde_yaml::Value]) -> Result<String> {
    let before: serde_yaml::Value =
        serde_yaml::from_str(plan_text).context("parsing existing plan.yaml")?;
    let before_len = before
        .get("articles")
        .and_then(|v| v.as_sequence())
        .map(|s| s.len())
        .ok_or_else(|| anyhow!("existing plan.yaml has no articles list"))?;

    let rows_text = serde_yaml::to_string(&serde_yaml::Value::Sequence(rows.to_vec()))?;
    let mut appended = plan_text.to_string();
    if !appended.ends_with('\n') {
        appended.push('\n');
    }
    appended.push_str(&rows_text);

    let check = |appended: &str| -> Option<usize> {
        serde_yaml::from_str::<serde_yaml::Value>(appended)
            .ok()?
            .get("articles")?
            .as_sequence()
            .map(|s| s.len())
    };
    if check(&appended) != Some(before_len + rows.len()) {
        bail!(
            "could not append to plan.yaml (its articles list is not at the end of the \
             file); add these rows by hand:\n\n{rows_text}"
        );
    }
    Ok(appended)
}

/// An article row for a queued source, title and author read from its
/// record.yaml.
fn row_from_record(sid: &str, mode: &str) -> Result<serde_yaml::Value> {
    let record_path = PathBuf::from("library/sources").join(sid).join("record.yaml");
    let record: serde_yaml::Value = serde_yaml::from_str(&read(&record_path)?)
        .with_context(|| format!("parsing {}", record_path.display()))?;
    let title = record
        .get("title")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("source '{sid}' record.yaml has no title"))?;
    let author = record.get("author").and_then(|v| v.as_str()).unwrap_or("");
    Ok(article_row(sid, title, author, mode))
}

pub const CONTENT_MODES: &[&str] = &["article", "in_a_nutshell"];

/// The existing plan text with `sid` appended to the source_ids of the
/// article row whose id is `article`. Text-level edit so comments and hand
/// formatting survive; the result is re-parsed to prove the id landed in
/// that row's list.
fn join_article(plan_text: &str, article: &str, sid: &str) -> Result<String> {
    let lines: Vec<&str> = plan_text.lines().collect();
    let row_start = lines
        .iter()
        .position(|l| l.trim_end() == format!("- id: {article}") || l.trim_end() == format!("- id: '{article}'"))
        .ok_or_else(|| {
            let ids: Vec<String> = lines
                .iter()
                .filter_map(|l| l.strip_prefix("- id: "))
                .map(|s| s.trim().trim_matches('\'').to_string())
                .collect();
            anyhow!("plan.yaml has no article '{article}'; existing articles: {}", ids.join(", "))
        })?;
    let row_end = lines[row_start + 1..]
        .iter()
        .position(|l| l.starts_with("- ") || (!l.is_empty() && !l.starts_with(' ') && !l.starts_with('#')))
        .map(|i| row_start + 1 + i)
        .unwrap_or(lines.len());
    let sids_line = lines[row_start..row_end]
        .iter()
        .position(|l| l.trim_end() == "  source_ids:")
        .map(|i| row_start + i)
        .ok_or_else(|| anyhow!("article '{article}' in plan.yaml has no block-style source_ids list"))?;
    let mut insert_at = sids_line + 1;
    while insert_at < row_end && lines[insert_at].starts_with("  - ") {
        insert_at += 1;
    }
    let mut out: Vec<String> = lines.iter().map(|l| l.to_string()).collect();
    out.insert(insert_at, format!("  - {sid}"));
    let mut joined = out.join("\n");
    joined.push('\n');

    let doc: serde_yaml::Value =
        serde_yaml::from_str(&joined).context("re-parsing plan.yaml after join")?;
    let landed = doc
        .get("articles")
        .and_then(|v| v.as_sequence())
        .map(|arts| {
            arts.iter().any(|a| {
                a.get("id").and_then(|v| v.as_str()) == Some(article)
                    && a
                        .get("source_ids")
                        .and_then(|v| v.as_sequence())
                        .map(|s| s.iter().any(|x| x.as_str() == Some(sid)))
                        .unwrap_or(false)
            })
        })
        .unwrap_or(false);
    if !landed {
        bail!("could not add {sid} to article '{article}' in plan.yaml; add it by hand");
    }
    Ok(joined)
}

fn plan_path_for(edition: &str) -> Result<PathBuf> {
    let dirs = matching_edition_dirs(edition)?;
    let out_dir =
        dirs.into_iter().next().unwrap_or_else(|| PathBuf::from("editions").join(edition));
    Ok(out_dir.join("plan.yaml"))
}

fn write_new_plan(out_path: &std::path::Path, edition_id: &str, articles: Vec<serde_yaml::Value>) -> Result<()> {
    let mut edition_map = serde_yaml::Mapping::new();
    edition_map.insert(
        serde_yaml::Value::String("id".to_string()),
        serde_yaml::Value::String(edition_id.to_string()),
    );
    let mut plan = serde_yaml::Mapping::new();
    plan.insert(
        serde_yaml::Value::String("edition".to_string()),
        serde_yaml::Value::Mapping(edition_map),
    );
    plan.insert(
        serde_yaml::Value::String("articles".to_string()),
        serde_yaml::Value::Sequence(articles),
    );
    if let Some(dir) = out_path.parent() {
        fs::create_dir_all(dir)?;
    }
    fs::write(out_path, serde_yaml::to_string(&serde_yaml::Value::Mapping(plan))?)?;
    Ok(())
}

/// Record a freshly captured source in the edition's plan.yaml right away, so
/// the source-to-article mapping lives on disk from intake, never only in
/// whoever's head ran the capture. With `article`, the source joins that
/// existing row's source_ids; otherwise it gets its own row in `mode`. A
/// missing plan.yaml is created first from every queued source, so earlier
/// captures are covered too.
pub fn add_source(edition: &str, sid: &str, article: Option<&str>, mode: &str) -> Result<()> {
    if !CONTENT_MODES.contains(&mode) {
        bail!("unknown content mode '{mode}'; one of: {}", CONTENT_MODES.join(", "));
    }
    let out_path = plan_path_for(edition)?;
    let release_state = read(&PathBuf::from("library/release-state.yaml"))?;
    let (edition_id, queued) = queued_source_ids(&release_state, edition)?;

    if !out_path.exists() {
        let mut articles = Vec::new();
        for q in &queued {
            if q == sid {
                if article.is_none() {
                    articles.push(row_from_record(q, mode)?);
                }
            } else {
                articles.push(row_from_record(q, "article")?);
            }
        }
        write_new_plan(&out_path, &edition_id, articles)?;
        println!("  plan: wrote {} ({} row(s))", out_path.display(), queued.len());
        if article.is_none() {
            return Ok(());
        }
    }

    let plan_text = read(&out_path)?;
    if referenced_source_ids(&plan_text)?.contains(sid) {
        println!("  plan: {} already references {sid}", out_path.display());
        return Ok(());
    }
    let new_text = match article {
        Some(a) => {
            let t = join_article(&plan_text, a, sid)?;
            println!("  plan: {sid} joined article '{a}'");
            t
        }
        None => {
            let t = append_rows(&plan_text, &[row_from_record(sid, mode)?])?;
            println!("  plan: {sid} added as its own {mode} row");
            t
        }
    };
    fs::write(&out_path, new_text)?;
    Ok(())
}

pub fn propose_plan(edition: &str) -> Result<i32> {
    let out_path = plan_path_for(edition)?;

    let release_state = read(&PathBuf::from("library/release-state.yaml"))?;
    let (edition_id, source_ids) = queued_source_ids(&release_state, edition)?;

    if out_path.exists() {
        let plan_text = read(&out_path)?;
        let referenced = referenced_source_ids(&plan_text)?;
        let missing: Vec<&String> =
            source_ids.iter().filter(|sid| !referenced.contains(*sid)).collect();
        if missing.is_empty() {
            println!(
                "{} already covers all {} queued source(s); nothing to add",
                out_path.display(),
                source_ids.len()
            );
            return Ok(0);
        }
        let mut rows = Vec::new();
        for sid in &missing {
            rows.push(row_from_record(sid, "article")?);
            println!("  added: {sid}");
        }
        fs::write(&out_path, append_rows(&plan_text, &rows)?)?;
        println!(
            "\nappended {} row(s) to {}; existing rows untouched. Edit the new rows \
             (merge source_ids, flip content_mode, fix titles), then: mag produce {}",
            rows.len(),
            out_path.display(),
            out_path.display()
        );
        return Ok(0);
    }

    let mut articles = Vec::new();
    for sid in &source_ids {
        articles.push(row_from_record(sid, "article")?);
        println!("  queued: {sid}");
    }

    write_new_plan(&out_path, &edition_id, articles)?;
    println!(
        "\nwrote {} — {} article(s) from '{edition_id}'. Edit it (drop rows, flip \
         content_mode to in_a_nutshell, fix titles), then: mag produce {}",
        out_path.display(),
        source_ids.len(),
        out_path.display()
    );
    Ok(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn article_slug_strips_only_a_trailing_capture_hash() {
        assert_eq!(article_slug("prime-agent-a-self-improving-rlm-agent-2c19ce14"), "prime-agent-a-self-improving-rlm-agent");
        assert_eq!(article_slug("how-enabling-two-settings-tripled-our-scores-on--265c6a01"), "how-enabling-two-settings-tripled-our-scores-on");
        assert_eq!(article_slug("no-hash-here"), "no-hash-here");
        // 8 chars but not hex: stays.
        assert_eq!(article_slug("keep-my-suffixes"), "keep-my-suffixes");
    }

    #[test]
    fn queued_source_ids_finds_the_matching_collecting_edition() {
        let yaml = "\
collecting_editions:
- id: '005'
  source_ids: [a-11112222, b-33334444]
released_editions: []
";
        let (id, sources) = queued_source_ids(yaml, "005").unwrap();
        assert_eq!(id, "005");
        assert_eq!(sources, vec!["a-11112222", "b-33334444"]);
    }

    #[test]
    fn queued_source_ids_fails_loud_on_no_match() {
        let yaml = "collecting_editions:\n- id: 006-x\n  source_ids: [a-11112222]\n";
        assert!(queued_source_ids(yaml, "005").is_err());
    }

    const PLAN: &str = "\
# hand-written header comment
edition:
  id: '006'
articles:
- id: merged-nutshell
  title: Merged Nutshell
  content_mode: in_a_nutshell
  source_ids:
  - a-11112222
  - b-33334444
- id: solo-article
  title: Solo
  content_mode: article
  source_ids:
  - c-55556666
";

    #[test]
    fn referenced_source_ids_walks_every_article_row() {
        let ids = referenced_source_ids(PLAN).unwrap();
        assert_eq!(ids.len(), 3);
        assert!(ids.contains("a-11112222"));
        assert!(ids.contains("b-33334444"));
        assert!(ids.contains("c-55556666"));
    }

    #[test]
    fn append_rows_keeps_existing_text_and_adds_rows_at_the_end() {
        let row = article_row("d-77778888", "New Piece", "Someone", "article");
        let out = append_rows(PLAN, &[row]).unwrap();
        assert!(out.starts_with("# hand-written header comment\n"));
        assert!(out.contains("- id: merged-nutshell"));
        let doc: serde_yaml::Value = serde_yaml::from_str(&out).unwrap();
        let articles = doc.get("articles").unwrap().as_sequence().unwrap();
        assert_eq!(articles.len(), 3);
        assert_eq!(articles[2].get("id").unwrap().as_str(), Some("d"));
        assert_eq!(
            articles[2].get("source_ids").unwrap().as_sequence().unwrap()[0].as_str(),
            Some("d-77778888")
        );
    }

    #[test]
    fn append_rows_fails_loud_when_articles_is_not_the_last_key() {
        let plan = "\
articles:
- id: solo-article
  source_ids: [c-55556666]
edition:
  id: '006'
";
        let row = article_row("d-77778888", "New Piece", "Someone", "article");
        let err = append_rows(plan, &[row]).unwrap_err().to_string();
        assert!(err.contains("add these rows by hand"), "{err}");
    }

    #[test]
    fn join_article_appends_to_that_rows_source_ids_only() {
        let out = join_article(PLAN, "merged-nutshell", "d-77778888").unwrap();
        assert!(out.starts_with("# hand-written header comment\n"));
        let doc: serde_yaml::Value = serde_yaml::from_str(&out).unwrap();
        let arts = doc.get("articles").unwrap().as_sequence().unwrap();
        let merged = arts[0].get("source_ids").unwrap().as_sequence().unwrap();
        assert_eq!(merged.len(), 3);
        assert_eq!(merged[2].as_str(), Some("d-77778888"));
        assert_eq!(arts[1].get("source_ids").unwrap().as_sequence().unwrap().len(), 1);
        // Works for the last row too (no following row to bound the block).
        let out = join_article(PLAN, "solo-article", "d-77778888").unwrap();
        let doc: serde_yaml::Value = serde_yaml::from_str(&out).unwrap();
        let solo = doc.get("articles").unwrap().as_sequence().unwrap()[1].get("source_ids").unwrap();
        assert_eq!(solo.as_sequence().unwrap().len(), 2);
    }

    #[test]
    fn join_article_fails_loud_on_unknown_article() {
        let err = join_article(PLAN, "nope", "d-77778888").unwrap_err().to_string();
        assert!(err.contains("merged-nutshell, solo-article"), "{err}");
    }

    #[test]
    fn article_row_defaults_to_the_article_writer() {
        let row = article_row("prime-agent-2c19ce14", "Prime Agent", "Prime Intellect Team", "article");
        assert_eq!(row.get("content_mode").unwrap().as_str(), Some("article"));
        assert_eq!(row.get("id").unwrap().as_str(), Some("prime-agent"));
        assert_eq!(
            row.get("source_ids").unwrap().as_sequence().unwrap()[0].as_str(),
            Some("prime-agent-2c19ce14")
        );
    }
}
