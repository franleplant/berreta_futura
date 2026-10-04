use crate::caller::write_atomic;
use crate::model::kinds::ContentMode;
use crate::model::shared::read_spec;
use crate::model::spec::SourceRecord;
use crate::util::{read, EditionId};
use anyhow::{anyhow, bail, ensure, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(clap::Args)]
pub struct PlanArgs {
    pub edition: String,
}

pub fn queued_source_ids(release_state: &str, edition: &str) -> Result<(String, Vec<String>)> {
    let doc: serde_norway::Value =
        serde_norway::from_str(release_state).context("parsing library/release-state.yaml")?;
    let collecting = doc
        .get("collecting_editions")
        .and_then(|v| v.as_sequence())
        .ok_or_else(|| anyhow!("release-state.yaml has no collecting_editions list"))?;
    for entry in collecting {
        let id = entry.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if id != edition {
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
    bail!("no collecting edition '{edition}' in library/release-state.yaml")
}

fn article_slug(source_id: &str) -> String {
    let trimmed = match source_id.rsplit_once('-') {
        Some((head, tail)) if tail.len() == 8 && tail.chars().all(|c| c.is_ascii_hexdigit()) => {
            head
        }
        _ => source_id,
    };
    trimmed.trim_end_matches('-').to_string()
}

fn article_row(
    source_id: &str,
    title: &str,
    author: &str,
    mode: ContentMode,
) -> serde_norway::Value {
    let mut row = serde_norway::Mapping::new();
    let mut set = |k: &str, v: serde_norway::Value| {
        row.insert(serde_norway::Value::String(k.to_string()), v);
    };
    set("id", serde_norway::Value::String(article_slug(source_id)));
    set("title", serde_norway::Value::String(title.to_string()));
    set("author", serde_norway::Value::String(author.to_string()));
    set(
        "content_mode",
        serde_norway::Value::String(mode.as_str().to_string()),
    );
    set(
        "source_ids",
        serde_norway::Value::Sequence(vec![serde_norway::Value::String(source_id.to_string())]),
    );
    serde_norway::Value::Mapping(row)
}

fn referenced_source_ids(plan_text: &str) -> Result<std::collections::HashSet<String>> {
    let doc: serde_norway::Value =
        serde_norway::from_str(plan_text).context("parsing existing plan.yaml")?;
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

fn append_rows(plan_text: &str, rows: &[serde_norway::Value]) -> Result<String> {
    let before: serde_norway::Value =
        serde_norway::from_str(plan_text).context("parsing existing plan.yaml")?;
    let before_len = before
        .get("articles")
        .and_then(|v| v.as_sequence())
        .map(std::vec::Vec::len)
        .ok_or_else(|| anyhow!("existing plan.yaml has no articles list"))?;

    let rows_text = serde_norway::to_string(&serde_norway::Value::Sequence(rows.to_vec()))?;
    let mut appended = plan_text.to_string();
    if !appended.ends_with('\n') {
        appended.push('\n');
    }
    appended.push_str(&rows_text);

    let check = |appended: &str| -> Option<usize> {
        serde_norway::from_str::<serde_norway::Value>(appended)
            .ok()?
            .get("articles")?
            .as_sequence()
            .map(std::vec::Vec::len)
    };
    if check(&appended) != Some(before_len + rows.len()) {
        bail!(
            "could not append to plan.yaml (its articles list is not at the end of the \
             file); add these rows by hand:\n\n{rows_text}"
        );
    }
    Ok(appended)
}

const VERBATIM_AUTO_WORD_LIMIT: usize = 1750;
const IMAGE_WORD_COST: usize = 210;

fn mode_for_source_text(text: &str) -> ContentMode {
    let cost = text.split_whitespace().count() + text.matches("![").count() * IMAGE_WORD_COST;
    if cost <= VERBATIM_AUTO_WORD_LIMIT {
        ContentMode::Verbatim
    } else {
        ContentMode::Article
    }
}

fn default_mode(sid: &str) -> Result<ContentMode> {
    let path = PathBuf::from("library/sources")
        .join(sid)
        .join("article.md");
    Ok(mode_for_source_text(&read(&path)?))
}

fn row_from_record(
    sid: &str,
    mode: Option<ContentMode>,
) -> Result<(serde_norway::Value, ContentMode)> {
    let mode = match mode {
        Some(m) => m,
        None => default_mode(sid)?,
    };
    let record_path = PathBuf::from("library/sources")
        .join(sid)
        .join("record.yaml");
    let record: SourceRecord = read_spec(&record_path)?;
    ensure!(
        !record.title.is_empty(),
        "source '{sid}' record.yaml has no title"
    );
    let author = record.author.unwrap_or_default();
    Ok((article_row(sid, &record.title, &author, mode), mode))
}

fn join_article(plan_text: &str, article: &str, sid: &str) -> Result<String> {
    let lines: Vec<&str> = plan_text.lines().collect();
    let row_start = lines
        .iter()
        .position(|l| {
            l.trim_end() == format!("- id: {article}")
                || l.trim_end() == format!("- id: '{article}'")
        })
        .ok_or_else(|| {
            let ids: Vec<String> = lines
                .iter()
                .filter_map(|l| l.strip_prefix("- id: "))
                .map(|s| s.trim().trim_matches('\'').to_string())
                .collect();
            anyhow!(
                "plan.yaml has no article '{article}'; existing articles: {}",
                ids.join(", ")
            )
        })?;
    let row_end = lines[row_start + 1..]
        .iter()
        .position(|l| {
            l.starts_with("- ") || (!l.is_empty() && !l.starts_with(' ') && !l.starts_with('#'))
        })
        .map_or(lines.len(), |i| row_start + 1 + i);
    let sids_line = lines[row_start..row_end]
        .iter()
        .position(|l| l.trim_end() == "  source_ids:")
        .map(|i| row_start + i)
        .ok_or_else(|| {
            anyhow!("article '{article}' in plan.yaml has no block-style source_ids list")
        })?;
    let mut insert_at = sids_line + 1;
    while insert_at < row_end && lines[insert_at].starts_with("  - ") {
        insert_at += 1;
    }
    let mut out: Vec<String> = lines.iter().map(std::string::ToString::to_string).collect();
    out.insert(insert_at, format!("  - {sid}"));
    let mut joined = out.join("\n");
    joined.push('\n');

    let doc: serde_norway::Value =
        serde_norway::from_str(&joined).context("re-parsing plan.yaml after join")?;
    let landed = doc
        .get("articles")
        .and_then(|v| v.as_sequence())
        .is_some_and(|arts| {
            arts.iter().any(|a| {
                a.get("id").and_then(|v| v.as_str()) == Some(article)
                    && a.get("source_ids")
                        .and_then(|v| v.as_sequence())
                        .is_some_and(|s| s.iter().any(|x| x.as_str() == Some(sid)))
            })
        });
    if !landed {
        bail!("could not add {sid} to article '{article}' in plan.yaml; add it by hand");
    }
    Ok(joined)
}

fn plan_path_for(edition: &str) -> PathBuf {
    PathBuf::from("editions").join(edition).join("plan.yaml")
}

fn known_editions(root: &Path, release_state: &str) -> Result<Vec<String>> {
    let doc: serde_norway::Value =
        serde_norway::from_str(release_state).context("parsing library/release-state.yaml")?;
    let mut names: Vec<String> = doc
        .get("collecting_editions")
        .and_then(|v| v.as_sequence())
        .into_iter()
        .flatten()
        .filter_map(|e| e.get("id").and_then(|v| v.as_str()).map(str::to_string))
        .collect();
    if let Ok(dirs) = fs::read_dir(root.join("editions")) {
        names.extend(
            dirs.flatten()
                .filter(|e| e.path().is_dir())
                .map(|e| e.file_name().to_string_lossy().to_string()),
        );
    }
    names.sort();
    names.dedup();
    Ok(names)
}

fn resolve_planned(root: &Path, release_state: &str, given: &str) -> Result<EditionId> {
    EditionId::pick(given, known_editions(root, release_state)?)
}

pub fn intake_edition_for(root: &Path, release_state: &str, given: &str) -> Result<String> {
    let names = known_editions(root, release_state)?;
    let hits: Vec<&str> = names
        .iter()
        .filter(|n| n.starts_with(given))
        .map(String::as_str)
        .collect();
    ensure!(
        hits.is_empty() || names.iter().any(|n| n == given),
        "edition '{given}' is not an existing id but a prefix of {}; pass the full id",
        hits.join(", ")
    );
    Ok(given.to_string())
}

fn write_new_plan(
    out_path: &std::path::Path,
    edition_id: &str,
    articles: Vec<serde_norway::Value>,
) -> Result<()> {
    let mut edition_map = serde_norway::Mapping::new();
    edition_map.insert(
        serde_norway::Value::String("id".to_string()),
        serde_norway::Value::String(edition_id.to_string()),
    );
    let mut plan = serde_norway::Mapping::new();
    plan.insert(
        serde_norway::Value::String("edition".to_string()),
        serde_norway::Value::Mapping(edition_map),
    );
    plan.insert(
        serde_norway::Value::String("articles".to_string()),
        serde_norway::Value::Sequence(articles),
    );
    if let Some(dir) = out_path.parent() {
        fs::create_dir_all(dir)?;
    }
    write_atomic(
        out_path,
        serde_norway::to_string(&serde_norway::Value::Mapping(plan))?,
    )?;
    Ok(())
}

pub fn check_join(edition: &str, article: &str) -> Result<()> {
    let plan = plan_path_for(edition);
    if plan.exists() {
        return join_article(&read(&plan)?, article, "preflight").map(drop);
    }
    let release_state = read(&PathBuf::from("library/release-state.yaml"))?;
    let queued = queued_source_ids(&release_state, edition)?.1;
    ensure!(
        queued.iter().any(|q| article_slug(q) == article),
        "no plan.yaml for edition {edition} and no queued source forms article '{article}'"
    );
    Ok(())
}

pub fn add_source(
    edition: &str,
    sid: &str,
    article: Option<&str>,
    mode: Option<ContentMode>,
) -> Result<()> {
    let out_path = plan_path_for(edition);
    let release_state = read(&PathBuf::from("library/release-state.yaml"))?;
    let (edition_id, queued) = queued_source_ids(&release_state, edition)?;

    if !out_path.exists() {
        let mut articles = Vec::new();
        for q in &queued {
            if q == sid {
                if article.is_none() {
                    articles.push(row_from_record(q, mode)?.0);
                }
            } else {
                articles.push(row_from_record(q, None)?.0);
            }
        }
        write_new_plan(&out_path, &edition_id, articles)?;
        println!(
            "  plan: wrote {} ({} row(s))",
            out_path.display(),
            queued.len()
        );
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
            let (row, mode) = row_from_record(sid, mode)?;
            let t = append_rows(&plan_text, &[row])?;
            println!("  plan: {sid} added as its own {mode} row");
            t
        }
    };
    write_atomic(&out_path, new_text)?;
    Ok(())
}

pub fn run(args: &PlanArgs) -> Result<i32> {
    let release_state = read(&PathBuf::from("library/release-state.yaml"))?;
    let resolved = resolve_planned(Path::new("."), &release_state, &args.edition)?;
    let edition = resolved.as_str();
    let out_path = plan_path_for(edition);
    let (edition_id, source_ids) = queued_source_ids(&release_state, edition)?;

    if out_path.exists() {
        let plan_text = read(&out_path)?;
        let referenced = referenced_source_ids(&plan_text)?;
        let missing: Vec<&String> = source_ids
            .iter()
            .filter(|sid| !referenced.contains(*sid))
            .collect();
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
            let (row, mode) = row_from_record(sid, None)?;
            rows.push(row);
            println!("  added: {sid} ({mode})");
        }
        write_atomic(&out_path, append_rows(&plan_text, &rows)?)?;
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
        let (row, mode) = row_from_record(sid, None)?;
        articles.push(row);
        println!("  queued: {sid} ({mode})");
    }

    write_new_plan(&out_path, &edition_id, articles)?;
    println!(
        "\nwrote {}: {} article(s) from '{edition_id}'. Edit it (drop rows, flip \
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
        assert_eq!(
            article_slug("prime-agent-a-self-improving-rlm-agent-2c19ce14"),
            "prime-agent-a-self-improving-rlm-agent"
        );
        assert_eq!(
            article_slug("how-enabling-two-settings-tripled-our-scores-on--265c6a01"),
            "how-enabling-two-settings-tripled-our-scores-on"
        );
        assert_eq!(article_slug("no-hash-here"), "no-hash-here");

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
    fn planned_edition_prefix_must_be_unambiguous() {
        let yaml = "collecting_editions:\n- id: '990'\n  source_ids: [a]\n- id: '991'\n  source_ids: [b]\n";
        let root = Path::new("/nonexistent");
        assert!(resolve_planned(root, yaml, "99").is_err());
        assert_eq!(resolve_planned(root, yaml, "991").unwrap().as_str(), "991");
    }

    #[test]
    fn intake_refuses_a_prefix_of_existing_editions() {
        let yaml = "collecting_editions:\n- id: '010'\n  source_ids: [a]\n- id: '011'\n  source_ids: [b]\n";
        let root = Path::new("/nonexistent");
        let err = intake_edition_for(root, yaml, "01")
            .unwrap_err()
            .to_string();
        assert!(err.contains("010, 011"));
        assert_eq!(intake_edition_for(root, yaml, "010").unwrap(), "010");
        assert_eq!(intake_edition_for(root, yaml, "099").unwrap(), "099");
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
        let row = article_row("d-77778888", "New Piece", "Someone", ContentMode::Article);
        let out = append_rows(PLAN, &[row]).unwrap();
        assert!(out.starts_with("# hand-written header comment\n"));
        assert!(out.contains("- id: merged-nutshell"));
        let doc: serde_norway::Value = serde_norway::from_str(&out).unwrap();
        let articles = doc.get("articles").unwrap().as_sequence().unwrap();
        assert_eq!(articles.len(), 3);
        assert_eq!(articles[2].get("id").unwrap().as_str(), Some("d"));
        assert_eq!(
            articles[2]
                .get("source_ids")
                .unwrap()
                .as_sequence()
                .unwrap()[0]
                .as_str(),
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
        let row = article_row("d-77778888", "New Piece", "Someone", ContentMode::Article);
        let err = append_rows(plan, &[row]).unwrap_err().to_string();
        assert!(err.contains("add these rows by hand"), "{err}");
    }

    #[test]
    fn join_article_appends_to_that_rows_source_ids_only() {
        let out = join_article(PLAN, "merged-nutshell", "d-77778888").unwrap();
        assert!(out.starts_with("# hand-written header comment\n"));
        let doc: serde_norway::Value = serde_norway::from_str(&out).unwrap();
        let arts = doc.get("articles").unwrap().as_sequence().unwrap();
        let merged = arts[0].get("source_ids").unwrap().as_sequence().unwrap();
        assert_eq!(merged.len(), 3);
        assert_eq!(merged[2].as_str(), Some("d-77778888"));
        assert_eq!(
            arts[1]
                .get("source_ids")
                .unwrap()
                .as_sequence()
                .unwrap()
                .len(),
            1
        );

        let out = join_article(PLAN, "solo-article", "d-77778888").unwrap();
        let doc: serde_norway::Value = serde_norway::from_str(&out).unwrap();
        let solo = doc.get("articles").unwrap().as_sequence().unwrap()[1]
            .get("source_ids")
            .unwrap();
        assert_eq!(solo.as_sequence().unwrap().len(), 2);
    }

    #[test]
    fn join_article_fails_loud_on_unknown_article() {
        let err = join_article(PLAN, "nope", "d-77778888")
            .unwrap_err()
            .to_string();
        assert!(err.contains("merged-nutshell, solo-article"), "{err}");
    }

    #[test]
    fn mode_for_source_text_promotes_when_it_fits_seven_pages() {
        let short = ["word"; 1700].join(" ");
        assert_eq!(mode_for_source_text(&short), ContentMode::Verbatim);
        let long = ["word"; 1800].join(" ");
        assert_eq!(mode_for_source_text(&long), ContentMode::Article);
        let with_images = format!("{} ![a](m/1.png) ![b](m/2.png)", ["word"; 1400].join(" "));
        assert_eq!(mode_for_source_text(&with_images), ContentMode::Article);
    }

    #[test]
    fn article_row_defaults_to_the_article_writer() {
        let row = article_row(
            "prime-agent-2c19ce14",
            "Prime Agent",
            "Prime Intellect Team",
            ContentMode::Article,
        );
        assert_eq!(row.get("content_mode").unwrap().as_str(), Some("article"));
        assert_eq!(row.get("id").unwrap().as_str(), Some("prime-agent"));
        assert_eq!(
            row.get("source_ids").unwrap().as_sequence().unwrap()[0].as_str(),
            Some("prime-agent-2c19ce14")
        );
    }
}
