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

fn article_row(source_id: &str, title: &str, author: &str) -> serde_yaml::Value {
    let mut row = serde_yaml::Mapping::new();
    let mut set = |k: &str, v: serde_yaml::Value| {
        row.insert(serde_yaml::Value::String(k.to_string()), v);
    };
    set("id", serde_yaml::Value::String(article_slug(source_id)));
    set("title", serde_yaml::Value::String(title.to_string()));
    set("author", serde_yaml::Value::String(author.to_string()));
    set("content_mode", serde_yaml::Value::String("article".to_string()));
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
fn row_from_record(sid: &str) -> Result<serde_yaml::Value> {
    let record_path = PathBuf::from("library/sources").join(sid).join("record.yaml");
    let record: serde_yaml::Value = serde_yaml::from_str(&read(&record_path)?)
        .with_context(|| format!("parsing {}", record_path.display()))?;
    let title = record
        .get("title")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("source '{sid}' record.yaml has no title"))?;
    let author = record.get("author").and_then(|v| v.as_str()).unwrap_or("");
    Ok(article_row(sid, title, author))
}

pub fn propose_plan(edition: &str) -> Result<i32> {
    let dirs = matching_edition_dirs(edition)?;
    let out_dir =
        dirs.into_iter().next().unwrap_or_else(|| PathBuf::from("editions").join(edition));
    let out_path = out_dir.join("plan.yaml");

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
            rows.push(row_from_record(sid)?);
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
        articles.push(row_from_record(sid)?);
        println!("  queued: {sid}");
    }

    let mut edition_map = serde_yaml::Mapping::new();
    edition_map.insert(
        serde_yaml::Value::String("id".to_string()),
        serde_yaml::Value::String(edition_id.clone()),
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

    fs::create_dir_all(&out_dir)?;
    fs::write(&out_path, serde_yaml::to_string(&serde_yaml::Value::Mapping(plan))?)?;
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
        let row = article_row("d-77778888", "New Piece", "Someone");
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
        let row = article_row("d-77778888", "New Piece", "Someone");
        let err = append_rows(plan, &[row]).unwrap_err().to_string();
        assert!(err.contains("add these rows by hand"), "{err}");
    }

    #[test]
    fn article_row_defaults_to_the_article_writer() {
        let row = article_row("prime-agent-2c19ce14", "Prime Agent", "Prime Intellect Team");
        assert_eq!(row.get("content_mode").unwrap().as_str(), Some("article"));
        assert_eq!(row.get("id").unwrap().as_str(), Some("prime-agent"));
        assert_eq!(
            row.get("source_ids").unwrap().as_sequence().unwrap()[0].as_str(),
            Some("prime-agent-2c19ce14")
        );
    }
}
