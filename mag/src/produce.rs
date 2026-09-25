use crate::caller::{Caller, ModelSpec};
use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::thread;
use std::time::Instant;

pub const INLINE_PREAMBLE: &str = "You are running non-interactively with NO file access and NO tools. Every\ndocument you need is inlined below. If an included instruction tells you to\nread a file or path, the content of that file is already included here —\nnever claim to have read anything that is not inlined.";

pub(crate) fn section(title: &str, body: &str) -> String {
    format!("\n\n========== {title} ==========\n\n{}\n", body.trim())
}

fn writer_prompt_file(mode: &str) -> Result<&'static str> {
    match mode {
        "article" => Ok("article.md"),
        "in_a_nutshell" => Ok("in-a-nutshell.md"),
        other => bail!("unknown content_mode '{other}'"),
    }
}

fn read(path: &Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

pub(crate) fn prompts_path(file: &str) -> PathBuf {
    let local = PathBuf::from("prompts").join(file);
    if local.exists() {
        return local;
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../prompts")
        .join(file)
}

fn source_text(source_id: &str) -> Result<String> {
    let path = PathBuf::from("library/sources")
        .join(source_id)
        .join("article.md");
    if !path.exists() {
        bail!(
            "no captured article for source '{source_id}' at {}",
            path.display()
        );
    }
    read(&path)
}

fn value_to_string(v: &serde_yaml::Value) -> Option<String> {
    match v {
        serde_yaml::Value::String(s) => Some(s.clone()),
        serde_yaml::Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

fn sources_block(sources: &[(String, String)]) -> String {
    let mut out = String::from("<sources>\n");
    for (_sid, text) in sources {
        out += "\n";
        out += text.trim();
        out += "\n";
    }
    out += "\n</sources>\n\n";
    out
}

fn writer_prompt(article: &serde_yaml::Value, sources: &[(String, String)]) -> Result<String> {
    let mode = article
        .get("content_mode")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("article missing content_mode"))?;
    let file = writer_prompt_file(mode)?;
    let mut prompt = read(&prompts_path(file))?.trim().to_string();
    if let Some(title) = article.get("title").and_then(|v| v.as_str()) {
        prompt = prompt.replace("{topic}", title);
    }
    if prompt.contains("{topic}") {
        bail!("prompts/{file} needs a topic but the article row has no title");
    }
    Ok(sources_block(sources) + &prompt + "\n")
}

fn strip_frontmatter(text: &str) -> &str {
    let Some(rest) = text.strip_prefix("---\n") else {
        return text;
    };
    match rest.split_once("\n---\n") {
        Some((_, body)) => body,
        None => text,
    }
}

const ARTICLE_MAX_WORDS: usize = 1450;

fn is_bold_label(line: &str) -> bool {
    let t = line.trim();
    let Some(inner) = t.strip_prefix("**").and_then(|s| s.strip_suffix("**")) else {
        return false;
    };
    !inner.is_empty()
        && !inner.contains('*')
        && inner.split_whitespace().count() <= 8
        && !inner.ends_with(['.', ':', '!', '?', ','])
}

fn normalize_bold_labels(body: &str) -> String {
    let lines: Vec<&str> = body.lines().collect();
    let mut out: Vec<String> = Vec::with_capacity(lines.len());
    for (i, line) in lines.iter().enumerate() {
        let alone = (i == 0 || lines[i - 1].trim().is_empty())
            && (i + 1 == lines.len() || lines[i + 1].trim().is_empty());
        if alone && is_bold_label(line) {
            let inner = line
                .trim()
                .trim_start_matches("**")
                .trim_end_matches("**")
                .trim();
            out.push(format!("## {inner}"));
        } else {
            out.push(line.to_string());
        }
    }
    out.join("\n")
}

fn extract_body(reply: &str, label: &str) -> Result<String> {
    let normalized = normalize_bold_labels(reply.trim());
    let mut body = normalized.as_str();
    while body.starts_with('#') {
        body = body
            .split_once('\n')
            .map(|(_, rest)| rest)
            .unwrap_or("")
            .trim_start();
    }
    if body.is_empty() {
        bail!("{label}: reply was empty");
    }
    Ok(format!("{}\n", body.trim_end()))
}

const TRIM_PASSES: usize = 3;

fn weighted_words(body: &str, heading_cost: usize) -> usize {
    let headings = body.lines().filter(|l| l.starts_with("## ")).count();
    body.split_whitespace().count() + headings * heading_cost
}

fn fit_to_budget(
    caller: &Caller,
    writer_model: &ModelSpec,
    piece_id: &str,
    prompt: &str,
    mut body: String,
    max: usize,
    heading_cost: usize,
) -> Result<String> {
    for pass in 1..=TRIM_PASSES {
        let weighted = weighted_words(&body, heading_cost);
        if weighted <= max {
            return Ok(body);
        }
        let words = body.split_whitespace().count();
        let label = format!("{piece_id} trim{pass}");

        let ask = max - max / 8;
        let heading_note = if heading_cost > 0 {
            format!(" Every `##` heading line costs {heading_cost} words of the budget.")
        } else {
            String::new()
        };
        let trim_prompt = format!(
            "{prompt}\n\n========== your draft ({words} words) ==========\n\n{body}\n\
             \nThe print budget is {ask} words.{heading_note} Write the piece again \
             within the budget: cut whole paragraphs or sections rather than \
             compressing every sentence. Reply with the piece only, no notes about \
             what you cut."
        );
        let parse_label = label.clone();
        body = caller.call_with_parse(&label, writer_model, &trim_prompt, |r| {
            extract_body(r, &parse_label)
        })?;
    }
    let weighted = weighted_words(&body, heading_cost);
    if weighted > max {
        bail!("{piece_id}: still {weighted} weighted words after {TRIM_PASSES} trim passes (budget {max})");
    }
    Ok(body)
}

fn em_dash_violations(body: &str, sources: &[(String, String)]) -> Vec<String> {
    let mut violations = Vec::new();
    let mut in_fence = false;
    for line in body.lines() {
        if line.starts_with("```") {
            in_fence = !in_fence;
            continue;
        }
        if in_fence || !line.contains('\u{2014}') {
            continue;
        }
        let chars: Vec<char> = line.chars().collect();
        let verbatim = chars
            .iter()
            .enumerate()
            .filter(|(_, c)| **c == '\u{2014}')
            .all(|(i, _)| em_dash_verbatim(&chars, i, sources));
        if !verbatim {
            violations.push(line.trim().to_string());
        }
    }
    violations
}

fn em_dash_verbatim(chars: &[char], i: usize, sources: &[(String, String)]) -> bool {
    const W: usize = 25;
    let len = chars.len();
    if len <= W {
        let whole: String = chars.iter().collect();
        return sources.iter().any(|(_, t)| t.contains(whole.trim()));
    }
    let lo = i.saturating_sub(W - 1);
    let hi = i.min(len - W);
    (lo..=hi).any(|start| {
        let w: String = chars[start..start + W].iter().collect();
        sources.iter().any(|(_, t)| t.contains(w.as_str()))
    })
}

const EM_DASH_PASSES: usize = 2;

fn fix_em_dashes(
    caller: &Caller,
    writer_model: &ModelSpec,
    piece_id: &str,
    prompt: &str,
    mut body: String,
    sources: &[(String, String)],
) -> Result<String> {
    for pass in 1..=EM_DASH_PASSES {
        let violations = em_dash_violations(&body, sources);
        if violations.is_empty() {
            return Ok(body);
        }
        let listed = violations
            .iter()
            .map(|l| format!("  {l}"))
            .collect::<Vec<_>>()
            .join("\n");
        let label = format!("{piece_id} emdash{pass}");
        let fix_prompt = format!(
            "{prompt}\n\n========== your draft ==========\n\n{body}\n\
             \nThe draft prints the em dash character (U+2014) in sentences of your own. \
             This magazine never prints an em dash outside a verbatim quotation from the \
             source. Rewrite the piece with those sentences repunctuated using a comma, \
             colon, semicolon, or period, changing nothing else. The offending lines:\n\
             {listed}\nReply with the piece only."
        );
        let parse_label = label.clone();
        body = caller.call_with_parse(&label, writer_model, &fix_prompt, |r| {
            extract_body(r, &parse_label)
        })?;
    }
    let violations = em_dash_violations(&body, sources);
    if !violations.is_empty() {
        bail!(
            "{piece_id}: em dash outside verbatim source text after {EM_DASH_PASSES} fix passes:\n{}",
            violations.join("\n")
        );
    }
    Ok(body)
}

fn verbatim_body(sources: &[(String, String)]) -> Result<String> {
    let [(_, text)] = sources else {
        bail!(
            "verbatim mode requires exactly one source, got {}",
            sources.len()
        );
    };
    let image = regex::Regex::new(r"^!\[[^\]]*\]\([^)]*\)\s*$").unwrap();
    let mut lines = text.lines().skip_while(|l| l.trim().is_empty()).peekable();
    if lines.peek().is_some_and(|l| l.starts_with("# ")) {
        lines.next();
        while lines.peek().is_some_and(|l| l.trim().is_empty()) {
            lines.next();
        }
        if lines
            .peek()
            .is_some_and(|l| (l.starts_with("By:") || l.starts_with("By ")) && l.len() < 240)
        {
            lines.next();
        }
    }
    let body: Vec<&str> = lines.filter(|l| !image.is_match(l)).collect();
    Ok(body.join("\n").trim().to_string() + "\n")
}

fn article_frontmatter(article: &serde_yaml::Value) -> Result<String> {
    let mode = article
        .get("content_mode")
        .and_then(|v| v.as_str())
        .ok_or_else(|| anyhow!("article missing content_mode"))?;
    let source_ids = article
        .get("source_ids")
        .and_then(|v| v.as_sequence())
        .ok_or_else(|| anyhow!("article missing source_ids"))?;
    let mut out = String::from("---\nsource_ids:\n");
    for sid in source_ids {
        let sid = sid
            .as_str()
            .ok_or_else(|| anyhow!("non-string source id"))?;
        out += &format!("- {sid}\n");
    }
    out += &format!(
        "content_mode: {mode}\nlabel: {}\n---\n\n",
        mode.to_uppercase().replace('_', " ")
    );
    Ok(out)
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct PieceStatus {
    piece: String,
    #[serde(default)]
    words: usize,
    state: String,
}

fn produce_piece(
    caller: &Arc<Caller>,
    run_dir: &Path,
    piece_id: &str,
    article: &serde_yaml::Value,
    sources: &[(String, String)],
    writer_model: &ModelSpec,
) -> Result<PieceStatus> {
    let out = run_dir.join("articles").join(piece_id);
    fs::create_dir_all(&out)?;
    let final_path = out.join("final.md");
    if final_path.exists() {
        println!("  {piece_id}: final.md exists, skipping (resume)");
        return Ok(
            match read(&out.join("status.yaml"))
                .ok()
                .and_then(|t| serde_yaml::from_str(&t).ok())
            {
                Some(status) => status,
                None => PieceStatus {
                    piece: piece_id.to_string(),
                    words: strip_frontmatter(&read(&final_path)?)
                        .split_whitespace()
                        .count(),
                    state: "written".to_string(),
                },
            },
        );
    }

    {
        let mode = article.get("content_mode").and_then(|v| v.as_str());
        if mode == Some("verbatim") {
            let body = verbatim_body(sources)?;
            fs::write(&final_path, article_frontmatter(article)? + &body)?;
            let status = PieceStatus {
                piece: piece_id.to_string(),
                words: body.split_whitespace().count(),
                state: "written".to_string(),
            };
            fs::write(out.join("status.yaml"), serde_yaml::to_string(&status)?)?;
            println!(
                "  {piece_id}: verbatim from source ({} words)",
                status.words
            );
            return Ok(status);
        }
    }

    let label = format!("{piece_id} write");
    let prompt = writer_prompt(article, sources)?;
    let frontmatter = article_frontmatter(article)?;
    let (max_words, heading_cost) = (ARTICLE_MAX_WORDS, 0);
    let parse_label = label.clone();
    let body = caller.call_with_parse(&label, writer_model, &prompt, |r| {
        extract_body(r, &parse_label)
    })?;
    let body = fit_to_budget(
        caller,
        writer_model,
        piece_id,
        &prompt,
        body,
        max_words,
        heading_cost,
    )?;
    let body = fix_em_dashes(caller, writer_model, piece_id, &prompt, body, sources)?;
    fs::write(&final_path, frontmatter + &body)?;

    let status = PieceStatus {
        piece: piece_id.to_string(),
        words: body.split_whitespace().count(),
        state: "written".to_string(),
    };
    fs::write(out.join("status.yaml"), serde_yaml::to_string(&status)?)?;
    println!("  {piece_id}: written ({} words)", status.words);
    Ok(status)
}

#[derive(Serialize, Deserialize, Debug)]
struct Plan {
    edition: serde_yaml::Value,
    articles: Vec<serde_yaml::Value>,
}

fn yq(s: &str) -> String {
    if s.is_empty()
        || s.contains(':')
        || s.contains('#')
        || s.contains('\'')
        || s.starts_with(['[', '{', '&', '*', '!', '|', '>', '%', '@', '`', '"'])
    {
        format!("'{}'", s.replace('\'', "''"))
    } else {
        s.to_string()
    }
}

fn source_figure_candidates(sid: &str) -> Vec<(String, String)> {
    let path = PathBuf::from("library/sources")
        .join(sid)
        .join("article.md");
    let Ok(text) = fs::read_to_string(&path) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for line in text.lines() {
        let Some(rest) = line.trim_start().strip_prefix("![") else {
            continue;
        };
        let Some((alt, tail)) = rest.split_once("](") else {
            continue;
        };
        let Some((media, _)) = tail.split_once(')') else {
            continue;
        };
        if media.starts_with("media/") {
            out.push((media.to_string(), alt.chars().take(110).collect()));
        }
    }
    out
}

fn scaffold_edition_yaml(
    edition_dir: &Path,
    edition_id: &str,
    plan: &Plan,
) -> Result<Option<PathBuf>> {
    let path = edition_dir.join("edition.yaml");
    if path.exists() {
        return Ok(None);
    }
    let issue_number: u32 = edition_id.trim_start_matches('0').parse().unwrap_or(0);
    let today = crate::caller::now_stamp()
        .chars()
        .take(10)
        .collect::<String>();
    let mut y = String::new();
    y += &format!(
        "# Edition {issue_number} spec, scaffolded by `mag produce` from plan.yaml.\n\
         # Title and cover copy are drafted by produce for the editor to revise; TODO marks figure and art picks.\n\
         # Art paths are filled by picking in art/showcase.html after `mag art {edition_id}`.\n\
         # Article order here is the reading order; reorder freely.\n"
    );
    y += &format!("id: '{edition_id}'\nissue_number: {issue_number}\n");
    y += "title: TODO\nsubtitle: TODO\n";
    y += &format!("publication_date: '{today}'\nstatus: draft\n");
    y += "format:\n  article_opener: illustrated_paper_spots_v1\n";
    y += "art_direction_path: art-directions/story-led-boy-and-robot.yaml\n";
    y += "cover:\n  layout: footer_caption\n  headline: TODO\n  deck: TODO\n  back_text: TODO\n  art_path: TODO\n";
    y += "articles:\n";
    for a in &plan.articles {
        let get = |k: &str| a.get(k).and_then(value_to_string).unwrap_or_default();
        let id = get("id");
        let title = get("title");
        y += &format!(
            "- id: {}\n  title: {}\n  short_title: {}\n",
            yq(&id),
            yq(&title),
            yq(&title)
        );
        y += "  display_emphasis: TODO\n  opener_variant: stepped_title\n";
        y += &format!(
            "  author: {}\n  author_note: TODO\n  content_mode: {}\n",
            yq(&get("author")),
            yq(&get("content_mode"))
        );
        y += "  source_ids:\n";
        let sids: Vec<String> = a
            .get("source_ids")
            .and_then(|v| v.as_sequence())
            .map(|s| s.iter().filter_map(value_to_string).collect())
            .unwrap_or_default();
        for sid in &sids {
            y += &format!("  - {sid}\n");
        }
        y += &format!("  manuscript: editions/{edition_id}/articles/{id}.md\n");
        if let Some(ex) = a.get("extracts") {
            let mut m = serde_yaml::Mapping::new();
            m.insert(serde_yaml::Value::String("extracts".into()), ex.clone());
            for line in serde_yaml::to_string(&serde_yaml::Value::Mapping(m))?.lines() {
                y += &format!("  {line}\n");
            }
        }
        let mut any = false;
        for sid in &sids {
            for (media, alt) in source_figure_candidates(sid) {
                if !any {
                    y += "  # figure candidates (uncomment into a `figures:` list; each row needs id, source_id, path, caption, alt_text, credit,\n  # anchor = a ## or ### heading in the manuscript, and layout = one of evidence_band, evidence_band_prose, adaptive_band,\n  # compact_band, column_plate, landscape_plate). short_title and display_emphasis must occur inside title.\n";
                    any = true;
                }
                y += &format!("  #   {sid} {media}: {alt}\n");
            }
        }
        y += "  opener_art:\n    path: TODO\n    alt_text: TODO\n    credit: Illustration generated for this edition.\n";
        y += "  tail_art_path: TODO\n";
    }
    y += "tail_art_fit: contain\nclosing_plates: []\n";
    fs::write(&path, y)?;
    Ok(Some(path))
}

pub fn run_edition(
    plan_path: &Path,
    resume: Option<PathBuf>,
    only: Option<HashSet<String>>,
    writer_model: &ModelSpec,
) -> Result<i32> {
    let plan_text = read(plan_path)?;
    let plan: Plan = serde_yaml::from_str(&plan_text).context("parsing plan.yaml")?;
    let edition_id = plan
        .edition
        .get("id")
        .and_then(value_to_string)
        .ok_or_else(|| anyhow!("plan.edition.id missing or not a string/number"))?;

    let edition_dir = plan_path.parent().map(PathBuf::from).unwrap_or_default();
    let run_dir =
        resume.unwrap_or_else(|| edition_dir.join(format!("run-{}", crate::caller::now_stamp())));
    fs::create_dir_all(&run_dir)?;
    fs::write(run_dir.join("plan.yaml"), serde_yaml::to_string(&plan)?)?;
    let caller = Arc::new(Caller::new(&run_dir));
    let started = Instant::now();
    println!("run dir: {}", run_dir.display());

    let scaffold_plan = Plan {
        edition: plan.edition.clone(),
        articles: plan.articles.clone(),
    };
    let articles: Vec<serde_yaml::Value> = plan
        .articles
        .into_iter()
        .filter(|a| match &only {
            None => true,
            Some(ids) => a
                .get("id")
                .and_then(|v| v.as_str())
                .map(|s| ids.contains(s))
                .unwrap_or(false),
        })
        .collect();

    let (statuses, failures) = write_articles(&caller, &run_dir, &articles, writer_model);

    let minutes = started.elapsed().as_secs_f64() / 60.0;
    let lines = summary_lines(
        &edition_id,
        &caller,
        minutes,
        writer_model,
        &statuses,
        &failures,
    );
    fs::write(run_dir.join("summary.md"), lines.join("\n") + "\n")?;
    println!("\n{}", run_dir.join("summary.md").display());
    println!("{}", lines.join("\n"));

    if failures.is_empty() {
        print_next_steps(
            &caller,
            writer_model,
            &edition_dir,
            &edition_id,
            &scaffold_plan,
            &run_dir,
        )?;
    } else {
        println!(
            "\nnext: fix the failures above, then: mag produce {} --resume {}",
            plan_path.display(),
            run_dir.display()
        );
    }

    Ok(if failures.is_empty() { 0 } else { 1 })
}

type Failures = Vec<(String, String)>;

fn write_articles(
    caller: &Arc<Caller>,
    run_dir: &Path,
    articles: &[serde_yaml::Value],
    writer_model: &ModelSpec,
) -> (Vec<PieceStatus>, Failures) {
    let mut handles = Vec::new();
    for article in articles {
        let article_owned = article.clone();
        let caller = Arc::clone(caller);
        let run_dir = run_dir.to_path_buf();
        let writer_model = writer_model.clone();
        handles.push(thread::spawn(move || -> Result<PieceStatus> {
            let id = article_owned
                .get("id")
                .and_then(|v| v.as_str())
                .ok_or_else(|| anyhow!("article missing id"))?
                .to_string();
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
            produce_piece(
                &caller,
                &run_dir,
                &id,
                &article_owned,
                &sources,
                &writer_model,
            )
        }));
    }

    let mut statuses = Vec::new();
    let mut failures = Vec::new();
    for (article, handle) in articles.iter().zip(handles) {
        let id = article
            .get("id")
            .and_then(|v| v.as_str())
            .unwrap_or("?")
            .to_string();
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
    (statuses, failures)
}

fn summary_lines(
    edition_id: &str,
    caller: &Caller,
    minutes: f64,
    writer_model: &ModelSpec,
    statuses: &[PieceStatus],
    failures: &Failures,
) -> Vec<String> {
    let mut lines = vec![
        format!("# Run summary — edition {edition_id}"),
        String::new(),
        format!(
            "- {} model calls, ${:.2}, {:.1} minutes",
            caller.calls(),
            caller.total_cost(),
            minutes
        ),
        format!("- writer `{}`", writer_model.full),
        String::new(),
        "| piece | words |".to_string(),
        "|---|---|".to_string(),
    ];
    for st in statuses {
        lines.push(format!("| {} | {} |", st.piece, st.words));
    }
    for (pid, err) in failures {
        let short: String = err.chars().take(80).collect();
        lines.push(format!("| {pid} | **FAILED** — {short} |"));
    }
    lines
}

const FRONT_TODOS: [(&str, &str); 5] = [
    ("title: TODO", "title"),
    ("subtitle: TODO", "subtitle"),
    ("  headline: TODO", "title"),
    ("  deck: TODO", "subtitle"),
    ("  back_text: TODO", "back_text"),
];

fn parse_front_matter(reply: &str) -> Result<HashMap<String, String>> {
    let yaml = reply.trim().trim_start_matches("```yaml").trim_matches('`');
    let drafted: HashMap<String, String> =
        serde_yaml::from_str(yaml).context("the front matter reply is not a YAML mapping")?;
    for key in ["title", "subtitle", "back_text"] {
        let value = drafted.get(key).map(|v| v.trim()).unwrap_or("");
        if value.is_empty() || value.contains('\u{2014}') {
            bail!("front matter {key} is missing, empty, or carries an em dash");
        }
    }
    let words = drafted["back_text"].split_whitespace().count();
    if words > 60 {
        bail!("front matter back_text runs {words} words; the budget is 60");
    }
    Ok(drafted)
}

fn front_matter(
    caller: &Caller,
    model: &ModelSpec,
    edition_yaml: &Path,
    run_dir: &Path,
) -> Result<bool> {
    let text = read(edition_yaml)?;
    let todo = |line: &str| FRONT_TODOS.iter().find(|(todo, _)| line == *todo);
    if !text.lines().any(|line| todo(line).is_some()) {
        return Ok(false);
    }
    let edition: serde_yaml::Value = serde_yaml::from_str(&text)?;
    let finals = edition["articles"]
        .as_sequence()
        .into_iter()
        .flatten()
        .filter_map(|a| Some((a["id"].as_str()?, a["title"].as_str()?)))
        .map(|(id, title)| {
            let body = read(&run_dir.join("articles").join(id).join("final.md"))?;
            Ok(section(title, strip_frontmatter(&body)))
        })
        .collect::<Result<Vec<_>>>()?
        .join("\n");
    let prompt = format!(
        "{INLINE_PREAMBLE}\n\n{}\n\n{finals}",
        read(&prompts_path("edition-front-matter.md"))?
    );
    let drafted = caller.call_with_parse("front-matter", model, &prompt, parse_front_matter)?;
    let filled: Vec<String> = text
        .lines()
        .map(|line| match todo(line) {
            Some((todo, key)) => format!("{}{}", &todo[..todo.len() - 4], yq(&drafted[*key])),
            None => line.to_string(),
        })
        .collect();
    fs::write(edition_yaml, filled.join("\n") + "\n")?;
    Ok(true)
}

fn print_next_steps(
    caller: &Caller,
    model: &ModelSpec,
    edition_dir: &Path,
    edition_id: &str,
    plan: &Plan,
    run_dir: &Path,
) -> Result<()> {
    let edition_yaml = edition_dir.join("edition.yaml");
    match scaffold_edition_yaml(edition_dir, edition_id, plan)? {
        Some(p) => println!("\nscaffolded {}", p.display()),
        None => println!("\n{} already exists; left as is", edition_yaml.display()),
    }
    if front_matter(caller, model, &edition_yaml, run_dir)? {
        println!(
            "drafted title, deck, and back cover into {} (review them)",
            edition_yaml.display()
        );
    }
    println!(
        "\nnext:\n  1. read the finals under {}/articles/*/final.md\n  \
         2. edit {}: review the drafted title and cover copy; article order, figures\n  \
         3. mag art {edition_id}            (image candidates; pick in art/showcase.html)\n  \
         4. mag source-codes {edition_id}   (after picking opener art)\n  \
         5. mag render {edition_id}",
        run_dir.display(),
        edition_yaml.display()
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn em_dash_composed_prose_is_a_violation() {
        let sources = vec![("s".to_string(), "plain source text".to_string())];
        let body = "A claim \u{2014} and its clincher.";
        assert_eq!(em_dash_violations(body, &sources).len(), 1);
    }

    #[test]
    fn em_dash_inside_verbatim_source_run_passes() {
        let quoted = "the walls \u{2014} not the mind \u{2014} were the problem";
        let sources = vec![("s".to_string(), format!("He wrote that {quoted}, twice."))];
        let body = format!("As the author put it, \"{quoted}\".");

        assert!(em_dash_violations(&body, &sources).is_empty());
    }

    #[test]
    fn em_dash_inside_code_fence_is_ignored() {
        let sources = vec![("s".to_string(), String::new())];
        let body = "```\nlet x = \"\u{2014}\";\n```\nProse without dashes.";
        assert!(em_dash_violations(body, &sources).is_empty());
    }

    #[test]
    fn em_dash_violation_reports_the_line() {
        let sources: Vec<(String, String)> = vec![];
        let body = "Fine line.\nBad \u{2014} line.\nFine again.";
        let v = em_dash_violations(body, &sources);
        assert_eq!(v, vec!["Bad \u{2014} line.".to_string()]);
    }

    fn article_row() -> serde_yaml::Value {
        serde_yaml::from_str(
            "id: mcp\ntitle: MCP in a Nutshell\ncontent_mode: in_a_nutshell\nsource_ids: [a-1, b-2]\n",
        )
        .unwrap()
    }

    #[test]
    fn writer_prompt_opens_with_sources_block() {
        let sources = vec![("a-1".to_string(), "SOURCE TEXT".to_string())];
        let row: serde_yaml::Value =
            serde_yaml::from_str("content_mode: article\ntitle: T\n").unwrap();
        let p = writer_prompt(&row, &sources).unwrap();
        assert!(p.starts_with("<sources>\n\nSOURCE TEXT\n\n</sources>\n\n"));
        assert!(p.contains("90% orwell"));
    }

    #[test]
    fn nutshell_prompt_substitutes_topic() {
        let sources = vec![("a-1".to_string(), "S".to_string())];
        let p = writer_prompt(&article_row(), &sources).unwrap();
        assert!(p.contains("MCP in a Nutshell, covered in <sources>."));
        assert!(!p.contains("{topic}"));
    }

    #[test]
    fn article_frontmatter_is_deterministic() {
        let fm = article_frontmatter(&article_row()).unwrap();
        assert_eq!(
            fm,
            "---\nsource_ids:\n- a-1\n- b-2\ncontent_mode: in_a_nutshell\nlabel: IN A NUTSHELL\n---\n\n"
        );
    }

    #[test]
    fn verbatim_body_strips_capture_chrome_only() {
        let src = "# Title\n\nBy: A. Author - 2026\n\nFirst para.\n\n![fig](media/001.png)\n\n## Head\n\nSecond - para.\n";
        let body = verbatim_body(&[("s-1".to_string(), src.to_string())]).unwrap();
        assert_eq!(body, "First para.\n\n\n## Head\n\nSecond - para.\n");
        assert!(verbatim_body(&[]).is_err());
        let dotted = "# Title\n\nBy Ann Lee & Bo Chen \u{b7} Sep 23, 2026\n\nBy design, first.\n";
        let body = verbatim_body(&[("s-1".to_string(), dotted.to_string())]).unwrap();
        assert_eq!(body, "By design, first.\n");
    }

    #[test]
    fn extract_body_drops_leading_headings_only() {
        let reply = "# MCP in a Nutshell\n\n## The 30-Second Version\n\nAn AI application needs things.\n\n## Later\n\nMore.";
        assert_eq!(
            extract_body(reply, "t").unwrap(),
            "An AI application needs things.\n\n## Later\n\nMore.\n"
        );
        assert_eq!(
            extract_body("Plain paragraph first.", "t").unwrap(),
            "Plain paragraph first.\n"
        );
        assert!(extract_body("# Only a title", "t").is_err());
        assert!(extract_body("   ", "t").is_err());
    }

    #[test]
    fn extract_body_promotes_bold_labels_to_headings() {
        let reply = "**Thirty seconds**\n\nIntro paragraph.\n\n**The curve**\n\nMore prose with **inline bold** kept.\n\n**A full sentence ends with a period.**\n\nTail.";
        assert_eq!(
            extract_body(reply, "t").unwrap(),
            "Intro paragraph.\n\n## The curve\n\nMore prose with **inline bold** kept.\n\n**A full sentence ends with a period.**\n\nTail.\n"
        );
    }

    #[test]
    fn strip_frontmatter_leaves_plain_text_alone() {
        assert_eq!(strip_frontmatter("no fm here"), "no fm here");
        assert_eq!(strip_frontmatter("---\na: b\n---\nbody"), "body");
    }
}
