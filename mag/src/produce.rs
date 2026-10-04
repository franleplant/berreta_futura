use crate::caller::{write_atomic, Caller, ModelSpec};
use anyhow::{anyhow, bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::thread;
use std::time::Instant;

pub const INLINE_PREAMBLE: &str = "You are running non-interactively with NO file access and NO tools. Every\ndocument you need is inlined below. If an included instruction tells you to\nread a file or path, the content of that file is already included here;\nnever claim to have read anything that is not inlined.";

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

fn unique_at(text: &str, marker: &str) -> Result<usize> {
    match text
        .match_indices(marker)
        .map(|(i, _)| i)
        .collect::<Vec<_>>()[..]
    {
        [at] => Ok(at),
        ref hits => bail!(
            "source_range marker {marker:?} must occur exactly once, found {}",
            hits.len()
        ),
    }
}

fn ranged(text: String, range: Option<&serde_norway::Value>) -> Result<String> {
    let Some(range) = range else {
        return Ok(text);
    };
    let marker = |k: &str| range.get(k).and_then(|v| v.as_str());
    let begin = marker("begin").ok_or_else(|| anyhow!("source_range needs a begin marker"))?;
    let start = unique_at(&text, begin)?;
    let stop = match marker("end") {
        Some(end) => {
            let stop = unique_at(&text, end)?;
            if stop <= start {
                bail!("source_range end {end:?} comes before begin {begin:?}");
            }
            stop
        }
        None => text.len(),
    };
    Ok(text[start..stop].trim_end().to_string() + "\n")
}

fn ranged_source(source_id: &str, range: Option<&serde_norway::Value>) -> Result<String> {
    ranged(source_text(source_id)?, range)
}

fn value_to_string(v: &serde_norway::Value) -> Option<String> {
    match v {
        serde_norway::Value::String(s) => Some(s.clone()),
        serde_norway::Value::Number(n) => Some(n.to_string()),
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

fn writer_prompt(article: &serde_norway::Value, sources: &[(String, String)]) -> Result<String> {
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
            .map_or("", |(_, rest)| rest)
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

fn article_frontmatter(article: &serde_norway::Value) -> Result<String> {
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
    article: &serde_norway::Value,
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
                .and_then(|t| serde_norway::from_str(&t).ok())
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
            write_atomic(&final_path, article_frontmatter(article)? + &body)?;
            let status = PieceStatus {
                piece: piece_id.to_string(),
                words: body.split_whitespace().count(),
                state: "written".to_string(),
            };
            write_atomic(out.join("status.yaml"), serde_norway::to_string(&status)?)?;
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
    write_atomic(&final_path, frontmatter + &body)?;

    let status = PieceStatus {
        piece: piece_id.to_string(),
        words: body.split_whitespace().count(),
        state: "written".to_string(),
    };
    write_atomic(out.join("status.yaml"), serde_norway::to_string(&status)?)?;
    println!("  {piece_id}: written ({} words)", status.words);
    Ok(status)
}

#[derive(Serialize, Deserialize, Debug)]
struct Plan {
    edition: serde_norway::Value,
    articles: Vec<serde_norway::Value>,
}

fn yq(s: &str) -> String {
    if s.contains(['\n', '\r']) {
        serde_json::to_string(s).expect("a string serializes")
    } else {
        serde_norway::to_string(s)
            .expect("a string serializes")
            .trim_end()
            .to_string()
    }
}

struct SourceImage {
    media: String,
    alt: String,
    anchor: String,
}

fn source_images(sid: &str, range: Option<&serde_norway::Value>) -> Vec<SourceImage> {
    ranged_source(sid, range)
        .map(|text| images_in(&text))
        .unwrap_or_default()
}

fn images_in(text: &str) -> Vec<SourceImage> {
    let mut anchor = "__opener__".to_string();
    let mut out = Vec::new();
    for line in text.lines() {
        if let Some(heading) = line.strip_prefix("## ").or(line.strip_prefix("### ")) {
            anchor = heading.trim().to_string();
        }
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
            out.push(SourceImage {
                media: media.to_string(),
                alt: alt.trim().to_string(),
                anchor: anchor.clone(),
            });
        }
    }
    out
}

fn verbatim_figures(sids: &[String], range: Option<&serde_norway::Value>) -> String {
    let rows: Vec<String> = sids
        .iter()
        .flat_map(|sid| {
            source_images(sid, range)
                .into_iter()
                .map(move |image| (sid, image))
        })
        .enumerate()
        .map(|(index, (sid, image))| {
            let caption = if image.alt.is_empty() {
                "TODO"
            } else {
                &image.alt
            };
            format!(
                "  - id: figure-{}\n    source_id: {sid}\n    path: {}\n    caption: {}\n    \
                 alt_text: {}\n    anchor: {}\n    layout: evidence_band\n",
                index + 1,
                image.media,
                yq(caption),
                yq(caption),
                yq(&image.anchor)
            )
        })
        .collect();
    match rows.is_empty() {
        true => String::new(),
        false => format!("  figures:\n{}", rows.concat()),
    }
}

fn article_scaffold(a: &serde_norway::Value, edition_id: &str) -> Result<String> {
    let get = |k: &str| a.get(k).and_then(value_to_string).unwrap_or_default();
    let mut y = String::new();
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
        let mut m = serde_norway::Mapping::new();
        m.insert(serde_norway::Value::String("extracts".into()), ex.clone());
        for line in serde_norway::to_string(&serde_norway::Value::Mapping(m))?.lines() {
            y += &format!("  {line}\n");
        }
    }
    if get("content_mode") == "verbatim" {
        y += &verbatim_figures(&sids, a.get("source_range"));
    } else {
        let mut any = false;
        for sid in &sids {
            for image in source_images(sid, a.get("source_range")) {
                if !any {
                    y += "  # figure candidates (uncomment into a `figures:` list; each row needs id, source_id, path, caption, alt_text,\n  # anchor = a ## or ### heading in the manuscript, and layout = one of evidence_band, evidence_band_prose, adaptive_band,\n  # compact_band, column_plate, landscape_plate, full_band, rotated_plate; render enlarges small-text figures\n  # itself unless the row sets fit: keep, and tone: auto|keep|invert controls dark-image inversion). short_title and display_emphasis must occur inside title.\n";
                    any = true;
                }
                let alt: String = image.alt.chars().take(110).collect();
                y += &format!("  #   {sid} {}: {alt}\n", image.media);
            }
        }
    }
    y += "  opener_art:\n    path: TODO\n    alt_text: TODO\n    credit: Illustration generated for this edition.\n";
    y += "  tail_art_path: TODO\n";
    Ok(y)
}

fn append_missing_articles(path: &Path, edition_id: &str, plan: &Plan) -> Result<String> {
    let text = read(path)?;
    let spec: serde_norway::Value = serde_norway::from_str(&text)?;
    let have: HashSet<&str> = spec
        .get("articles")
        .and_then(|v| v.as_sequence())
        .map(|s| s.iter().filter_map(|a| a.get("id")?.as_str()).collect())
        .unwrap_or_default();
    let mut rows = String::new();
    let mut added = Vec::new();
    for a in &plan.articles {
        let id = a.get("id").and_then(value_to_string).unwrap_or_default();
        if !have.contains(id.as_str()) {
            rows += &article_scaffold(a, edition_id)?;
            added.push(id);
        }
    }
    if added.is_empty() {
        return Ok(format!(
            "{} already lists every plan article",
            path.display()
        ));
    }
    let lines: Vec<&str> = text.lines().collect();
    let articles_at = lines
        .iter()
        .position(|l| *l == "articles:")
        .ok_or_else(|| anyhow!("{} has no top-level articles: list", path.display()))?;
    let insert_at = lines[articles_at + 1..]
        .iter()
        .position(|l| l.chars().next().is_some_and(|c| c.is_ascii_alphabetic()))
        .map_or(lines.len(), |i| articles_at + 1 + i);
    let out = lines[..insert_at].join("\n") + "\n" + &rows + &lines[insert_at..].join("\n") + "\n";
    write_atomic(path, out)?;
    Ok(format!(
        "added {} to {} (fill their TODOs)",
        added.join(", "),
        path.display()
    ))
}

fn scaffold_edition_yaml(edition_dir: &Path, edition_id: &str, plan: &Plan) -> Result<String> {
    let path = edition_dir.join("edition.yaml");
    if path.exists() {
        return append_missing_articles(&path, edition_id, plan);
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
        y += &article_scaffold(a, edition_id)?;
    }
    y += "tail_art_fit: contain\nclosing_plates: []\n";
    write_atomic(&path, y)?;
    Ok(format!("scaffolded {}", path.display()))
}

pub fn run_edition(
    plan_path: &Path,
    resume: Option<PathBuf>,
    only: Option<&HashSet<String>>,
    writer_model: &ModelSpec,
) -> Result<i32> {
    let plan_text = read(plan_path)?;
    let plan: Plan = serde_norway::from_str(&plan_text).context("parsing plan.yaml")?;
    let edition_id = plan
        .edition
        .get("id")
        .and_then(value_to_string)
        .ok_or_else(|| anyhow!("plan.edition.id missing or not a string/number"))?;

    let edition_dir = plan_path.parent().map(PathBuf::from).unwrap_or_default();
    let run_dir = match resume {
        Some(dir) => {
            fs::create_dir_all(&dir)?;
            dir
        }
        None => {
            let dir = edition_dir.join(format!("run-{}", crate::caller::now_stamp()));
            crate::caller::create_fresh_dir(&dir)?;
            dir
        }
    };
    write_atomic(run_dir.join("plan.yaml"), serde_norway::to_string(&plan)?)?;
    let caller = Arc::new(Caller::new(&run_dir));
    let started = Instant::now();
    println!("run dir: {}", run_dir.display());

    let scaffold_plan = Plan {
        edition: plan.edition.clone(),
        articles: plan.articles.clone(),
    };
    let articles: Vec<serde_norway::Value> = plan
        .articles
        .into_iter()
        .filter(|a| match only {
            None => true,
            Some(ids) => a
                .get("id")
                .and_then(|v| v.as_str())
                .is_some_and(|s| ids.contains(s)),
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
    write_atomic(run_dir.join("summary.md"), lines.join("\n") + "\n")?;
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
    articles: &[serde_norway::Value],
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
                let text = ranged_source(&sid, article_owned.get("source_range"))?;
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
        format!("# Run summary: edition {edition_id}"),
        String::new(),
        format!(
            "- {} model calls, {}, {:.1} minutes",
            caller.calls(),
            caller.cost_label(),
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
        lines.push(format!("| {pid} | **FAILED**: {short} |"));
    }
    lines
}

fn front_todo(line: &str) -> Option<&'static (&'static str, &'static str)> {
    FRONT_TODOS.iter().find(|(todo, _)| line == *todo)
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
        serde_norway::from_str(yaml).context("the front matter reply is not a YAML mapping")?;
    for key in ["title", "subtitle", "back_text"] {
        let value = drafted.get(key).map_or("", |v| v.trim());
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
    if !text.lines().any(|line| front_todo(line).is_some()) {
        return Ok(false);
    }
    let edition: serde_norway::Value = serde_norway::from_str(&text)?;
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
    let filled = fill_todos(&read(edition_yaml)?, &drafted);
    write_atomic(edition_yaml, filled)?;
    Ok(true)
}

fn fill_todos(text: &str, drafted: &HashMap<String, String>) -> String {
    let filled: Vec<String> = text
        .lines()
        .map(|line| match front_todo(line) {
            Some((todo, key)) => format!("{}{}", &todo[..todo.len() - 4], yq(&drafted[*key])),
            None => line.to_string(),
        })
        .collect();
    filled.join("\n") + "\n"
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
    println!(
        "\n{}",
        scaffold_edition_yaml(edition_dir, edition_id, plan)?
    );
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
    fn yq_round_trips_every_awkward_scalar() {
        for raw in [
            "true", "null", "~", "1984", "- x", "? x", "a: b", "it's", "a\nb", "", "# x", "yes",
            "0x1F", "1e3", "@x", "a #b", "x:", "'q'", "\"q\"", "é: ü",
        ] {
            let doc: serde_norway::Value =
                serde_norway::from_str(&format!("k: {}\n", yq(raw))).unwrap();
            assert_eq!(doc["k"].as_str(), Some(raw), "{raw:?} -> {}", yq(raw));
        }
    }

    #[test]
    fn fill_todos_leaves_edited_lines_alone() {
        let drafted = HashMap::from([
            ("title".to_string(), "Drafted".to_string()),
            ("subtitle".to_string(), "Sub".to_string()),
        ]);
        let out = fill_todos("title: Edited by hand\nsubtitle: TODO\n", &drafted);
        assert_eq!(out, "title: Edited by hand\nsubtitle: Sub\n");
    }

    #[test]
    fn a_new_plan_article_is_appended_before_the_trailing_keys() {
        let dir = std::env::temp_dir().join(format!("mag-append-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("edition.yaml");
        fs::write(
            &path,
            "id: '099'\narticles:\n- id: old\n  title: Edited\ntail_art_fit: contain\n",
        )
        .unwrap();
        let plan: Plan = serde_norway::from_str(
            "edition: {id: '099'}\narticles:\n- {id: old, title: Old, source_ids: []}\n- {id: new, title: New, content_mode: verbatim, source_ids: []}\n",
        )
        .unwrap();
        let msg = append_missing_articles(&path, "099", &plan).unwrap();
        let out = read(&path).unwrap();
        assert!(msg.contains("added new"), "{msg}");
        let spec: serde_norway::Value = serde_norway::from_str(&out).unwrap();
        let ids: Vec<&str> = spec["articles"]
            .as_sequence()
            .unwrap()
            .iter()
            .map(|a| a["id"].as_str().unwrap())
            .collect();
        assert_eq!(ids, ["old", "new"]);
        assert_eq!(spec["articles"][0]["title"].as_str(), Some("Edited"));
        assert_eq!(spec["tail_art_fit"].as_str(), Some("contain"));
        assert!(append_missing_articles(&path, "099", &plan)
            .unwrap()
            .contains("already lists"));
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn source_range_slices_between_unique_markers() {
        let text = "# T\n\n## 1. Intro\nA\n\n## 2. Depth\nB\n\n## 3. End\nC\n".to_string();
        let range: serde_norway::Value =
            serde_norway::from_str("{begin: '## 2. Depth', end: '## 3. End'}").unwrap();
        assert_eq!(
            ranged(text.clone(), Some(&range)).unwrap(),
            "## 2. Depth\nB\n"
        );
        let open: serde_norway::Value = serde_norway::from_str("{begin: '## 3. End'}").unwrap();
        assert_eq!(ranged(text.clone(), Some(&open)).unwrap(), "## 3. End\nC\n");
        let ambiguous: serde_norway::Value = serde_norway::from_str("{begin: '## '}").unwrap();
        assert!(ranged(text.clone(), Some(&ambiguous)).is_err());
        let backwards: serde_norway::Value =
            serde_norway::from_str("{begin: '## 3. End', end: '## 1. Intro'}").unwrap();
        assert!(ranged(text, Some(&backwards)).is_err());
    }

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

    fn article_row() -> serde_norway::Value {
        serde_norway::from_str(
            "id: mcp\ntitle: MCP in a Nutshell\ncontent_mode: in_a_nutshell\nsource_ids: [a-1, b-2]\n",
        )
        .unwrap()
    }

    #[test]
    fn writer_prompt_opens_with_sources_block() {
        let sources = vec![("a-1".to_string(), "SOURCE TEXT".to_string())];
        let row: serde_norway::Value =
            serde_norway::from_str("content_mode: article\ntitle: T\n").unwrap();
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
    fn source_images_carry_the_heading_above_them() {
        let text = "# T\n\n![lead](media/000.png)\n\n## One\n\n![a](media/001.png)\n\n### Two\n\n![](media/002.png)\n![web](https://x/y.png)\n";
        let images: Vec<(String, String, String)> = images_in(text)
            .into_iter()
            .map(|i| (i.media, i.alt, i.anchor))
            .collect();
        let row = |m: &str, a: &str, h: &str| (m.to_string(), a.to_string(), h.to_string());
        assert_eq!(
            images,
            vec![
                row("media/000.png", "lead", "__opener__"),
                row("media/001.png", "a", "One"),
                row("media/002.png", "", "Two"),
            ]
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
