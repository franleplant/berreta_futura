use crate::caller::{self, Caller, ModelSpec};
use anyhow::{anyhow, bail, Context, Result};
use regex::Regex;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const RAW_DIR: &str = ".magazine/capture";
const USER_AGENT: &str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36";

const SHINGLE_WORDS: usize = 12;
const MISS_RATE_LIMIT: f64 = 0.02;

pub fn source_id(title: &str, url: &str) -> String {
    let mut slug = String::new();
    let mut prev_dash = true;
    for c in title.to_lowercase().chars() {
        if c.is_ascii_alphanumeric() {
            slug.push(c);
            prev_dash = false;
        } else if !prev_dash {
            slug.push('-');
            prev_dash = true;
        }
    }
    let slug: String = slug.trim_matches('-').chars().take(48).collect();
    let slug = slug.trim_end_matches('-');
    let hash = hex::encode(Sha256::digest(url.as_bytes()));
    format!("{slug}-{}", &hash[..8])
}

pub(crate) fn curl_text(url: &str) -> Result<String> {
    let out = Command::new("curl")
        .args(["-sL", "--max-time", "90", "-A", USER_AGENT, "--fail", url])
        .output()
        .context("spawning curl")?;
    if !out.status.success() {
        bail!(
            "fetching {url} failed (curl exit {})",
            out.status.code().unwrap_or(-1)
        );
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

pub(crate) fn curl_image(url: &str, dest_stem: &Path) -> Result<PathBuf> {
    let tmp = dest_stem.with_extension("tmp");
    let out = Command::new("curl")
        .args(["-sL", "--max-time", "120", "-A", USER_AGENT, "--fail", "-o"])
        .arg(&tmp)
        .args(["-w", "%{content_type}", url])
        .output()
        .context("spawning curl")?;
    if !out.status.success() {
        let _ = fs::remove_file(&tmp);
        bail!(
            "downloading image {url} failed (curl exit {})",
            out.status.code().unwrap_or(-1)
        );
    }
    let ctype = String::from_utf8_lossy(&out.stdout).to_lowercase();
    let ext = match ctype.split(';').next().unwrap_or("").trim() {
        "image/png" => "png",
        "image/jpeg" | "image/jpg" => "jpg",
        "image/gif" => "gif",
        "image/webp" => "webp",
        "image/svg+xml" => "svg",
        "image/avif" => "avif",
        other => {
            let _ = fs::remove_file(&tmp);
            bail!("image {url} came back as '{other}', not an image");
        }
    };
    let dest = dest_stem.with_extension(ext);
    fs::rename(&tmp, &dest).with_context(|| format!("writing {}", dest.display()))?;
    Ok(dest)
}

fn decode_entities(s: &str) -> String {
    let named = [
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", "\""),
        ("&#39;", "'"),
        ("&apos;", "'"),
        ("&nbsp;", " "),
        ("&rsquo;", "\u{2019}"),
        ("&lsquo;", "\u{2018}"),
        ("&rdquo;", "\u{201d}"),
        ("&ldquo;", "\u{201c}"),
        ("&hellip;", "\u{2026}"),
        ("&mdash;", "\u{2014}"),
        ("&ndash;", "\u{2013}"),
    ];
    let mut out = s.to_string();
    for (from, to) in named {
        out = out.replace(from, to);
    }
    let numeric = Regex::new(r"&#(x?)([0-9a-fA-F]+);").unwrap();
    numeric
        .replace_all(&out, |c: &regex::Captures| {
            let radix = if c[1].is_empty() { 10 } else { 16 };
            u32::from_str_radix(&c[2], radix)
                .ok()
                .and_then(char::from_u32)
                .map(String::from)
                .unwrap_or_default()
        })
        .into_owned()
}

fn strip_block(html: &str, tag: &str) -> String {
    Regex::new(&format!(r"(?is)<{tag}\b.*?</{tag}>"))
        .unwrap()
        .replace_all(html, " ")
        .into_owned()
}

fn strip_sr_only(html: &str) -> String {
    Regex::new(r#"(?is)<span\b[^>]*class="[^"]*\bsr-only\b[^"]*"[^>]*>.*?</span>"#)
        .unwrap()
        .replace_all(html, " ")
        .into_owned()
}

fn page_text(html: &str) -> String {
    let mut s = strip_sr_only(html);
    for tag in ["script", "style", "svg", "noscript"] {
        s = strip_block(&s, tag);
    }
    s = Regex::new(r"(?s)<!--.*?-->")
        .unwrap()
        .replace_all(&s, " ")
        .into_owned();
    s = Regex::new(r"(?s)<[^>]*>")
        .unwrap()
        .replace_all(&s, " ")
        .into_owned();
    normalize_ws(&decode_entities(&s))
}

fn page_for_model(html: &str) -> String {
    let mut s = strip_sr_only(html);
    for tag in ["script", "style", "svg", "noscript", "head"] {
        s = strip_block(&s, tag);
    }
    s = Regex::new(r"(?s)<!--.*?-->")
        .unwrap()
        .replace_all(&s, " ")
        .into_owned();
    s = Regex::new(r#"(?s)\bsrc="data:[^"]*""#)
        .unwrap()
        .replace_all(&s, "")
        .into_owned();
    Regex::new(r"\n{3,}")
        .unwrap()
        .replace_all(&s, "\n\n")
        .into_owned()
}

fn normalize_ws(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn comparison_form(s: &str) -> String {
    s.chars()
        .filter(|c| {
            !c.is_whitespace() && !matches!(c, '\u{2060}' | '\u{200b}' | '\u{feff}' | '\u{ad}')
        })
        .map(|c| match c {
            '\u{2018}' | '\u{2019}' => '\'',
            '\u{201c}' | '\u{201d}' => '"',
            c => c,
        })
        .collect()
}

fn pre_runs(html: &str) -> Vec<String> {
    Regex::new(r"(?is)<pre\b[^>]*>(.*?)</pre>")
        .unwrap()
        .captures_iter(html)
        .map(|c| {
            let inner = Regex::new(r"(?s)<[^>]*>").unwrap().replace_all(&c[1], "");
            normalize_code(&decode_entities(&inner))
        })
        .collect()
}

fn normalize_code(s: &str) -> String {
    s.lines()
        .map(str::trim_end)
        .collect::<Vec<_>>()
        .join("\n")
        .trim()
        .to_string()
}

fn meta_content(html: &str, keys: &[&str]) -> Option<String> {
    for key in keys {
        for pat in [
            format!(r#"(?i)<meta[^>]+(?:property|name)=["']{key}["'][^>]+content=["']([^"']+)"#),
            format!(
                r#"(?i)<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']{key}["']"#
            ),
            format!(r#""{key}"\s*:\s*"([^"]+)""#),
        ] {
            if let Some(c) = Regex::new(&pat).unwrap().captures(html) {
                return Some(decode_entities(c[1].trim()));
            }
        }
    }
    None
}

pub(crate) fn page_title(html: &str) -> Option<String> {
    let raw = meta_content(html, &["og:title"]).or_else(|| {
        Regex::new(r"(?is)<title[^>]*>(.*?)</title>")
            .unwrap()
            .captures(html)
            .map(|c| decode_entities(c[1].trim()))
    })?;

    let head = Regex::new(r"\s+[|\u{2022}\u{00b7}]\s+")
        .unwrap()
        .split(&raw)
        .next()
        .unwrap_or(&raw)
        .trim()
        .to_string();
    let clean = normalize_ws(&head);
    (!clean.is_empty()).then_some(clean)
}

fn page_published(html: &str) -> Option<String> {
    meta_content(html, &["article:published_time", "datePublished"])
        .map(|s| s.chars().take(10).collect())
        .or_else(|| {
            Regex::new(r#"datetime=["'](\d{4}-\d{2}-\d{2})"#)
                .unwrap()
                .captures(html)
                .map(|c| c[1].to_string())
        })
}

struct Extraction {
    article: String,
    synopsis: String,
    author: String,
    published: String,
}

fn parse_reply(reply: &str, haystack: &str, pres: &[String]) -> Result<Extraction> {
    let (article, meta) = reply
        .rsplit_once("===META===")
        .ok_or_else(|| anyhow!("reply has no ===META=== separator"))?;

    let field = |k: &str| {
        meta.lines()
            .find_map(|l| l.trim().strip_prefix(&format!("{k}:")))
            .map(|v| v.trim().trim_matches(['"', '\'']).to_string())
            .unwrap_or_default()
    };
    let synopsis = field("synopsis");
    if synopsis.is_empty() {
        bail!("META block has no synopsis");
    }
    let article = article.trim().to_string();
    fidelity_gate(&article, haystack, pres)?;
    Ok(Extraction {
        article,
        synopsis,
        author: field("author"),
        published: field("published"),
    })
}

fn fidelity_gate(article: &str, haystack: &str, pres: &[String]) -> Result<()> {
    let fence = Regex::new(r"(?s)```[^\n]*\n(.*?)```").unwrap();
    for block in fence.captures_iter(article) {
        let code = normalize_code(&block[1]);
        if code.is_empty() {
            continue;
        }
        let ok = |c: &str| {
            pres.iter().any(|p| p.contains(c))
                || comparison_form(haystack).contains(&comparison_form(c))
        };

        let dequoted = block[1]
            .lines()
            .filter(|l| !l.trim().is_empty())
            .all(|l| l.starts_with('>'))
            .then(|| {
                normalize_code(
                    &block[1]
                        .lines()
                        .map(|l| {
                            l.strip_prefix('>')
                                .map_or(l, |r| r.strip_prefix(' ').unwrap_or(r))
                        })
                        .collect::<Vec<_>>()
                        .join("\n"),
                )
            });
        if !ok(&code) && !dequoted.as_deref().is_some_and(ok) {
            let first = code.lines().next().unwrap_or("");
            bail!("code block starting '{first}' is not an exact contiguous run from the page");
        }
    }

    let link = Regex::new(r"\[([^\]]*)\]\([^)]*\)").unwrap();
    let image = Regex::new(r"!\[[^\]]*\]\([^)]*\)").unwrap();
    let body = fence.replace_all(article, " ");
    let body = image.replace_all(&body, " ");
    let body = link.replace_all(&body, "$1");

    const PROSE_FOLD: [char; 5] = ['*', '`', '[', ']', '\u{2197}'];
    let folded_haystack = comparison_form(haystack).replace(PROSE_FOLD, "");
    let mut misses = Vec::new();
    let mut total = 0usize;
    let ordinal = Regex::new(r"^\d+\.\s").unwrap();
    for (i, line) in body.lines().enumerate() {
        let t = line.trim();

        if i < 3 || t.starts_with('#') || t.starts_with('|') || t.starts_with("![") {
            continue;
        }
        let t = t.trim_start_matches(['-', '*', '>']).trim_start();
        let t = ordinal.replace(t, "");
        let t = t.replace(PROSE_FOLD, "");
        let words: Vec<&str> = t.split_whitespace().collect();
        if words.len() < 5 {
            continue;
        }
        let mut windows: Vec<String> = Vec::new();
        if words.len() <= SHINGLE_WORDS {
            windows.push(words.join(" "));
        } else {
            let mut i = 0;
            while i + SHINGLE_WORDS <= words.len() {
                windows.push(words[i..i + SHINGLE_WORDS].join(" "));
                i += SHINGLE_WORDS;
            }
            if !words.len().is_multiple_of(SHINGLE_WORDS) {
                windows.push(words[words.len() - SHINGLE_WORDS..].join(" "));
            }
        }
        for w in windows {
            total += 1;
            if !folded_haystack.contains(&comparison_form(&w)) {
                misses.push(w);
            }
        }
    }
    let limit = ((total as f64) * MISS_RATE_LIMIT).max(1.0) as usize;
    if misses.len() > limit {
        let examples: Vec<String> = misses
            .iter()
            .take(5)
            .map(|m| format!("  ...{m}..."))
            .collect();
        bail!(
            "{} of {} prose passages are not verbatim from the page; transcribe the page's \
             own wording exactly. Examples:\n{}",
            misses.len(),
            total,
            examples.join("\n")
        );
    }
    Ok(())
}

fn yaml_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "''"))
}

struct SourceMeta<'a> {
    sid: &'a str,
    title: &'a str,
    author: &'a str,
    url: &'a str,
    captured_at: &'a str,
    published: &'a str,
    tags: &'a [String],
    synopsis: &'a str,
}

fn record_yaml(m: &SourceMeta) -> String {
    let mut out = format!(
        "id: {}\ntitle: {}\nauthor: {}\nurl: {}\ncaptured_at: {}\n",
        m.sid,
        yaml_quote(m.title),
        if m.author.is_empty() {
            "''".to_string()
        } else {
            yaml_quote(m.author)
        },
        m.url,
        yaml_quote(m.captured_at),
    );
    if !m.published.is_empty() {
        out += &format!("published_at: {}\n", yaml_quote(m.published));
    }
    if m.tags.is_empty() {
        out += "tags: []\n";
    } else {
        out += "tags:\n";
        for t in m.tags {
            out += &format!("- {t}\n");
        }
    }
    out += &format!("synopsis: {}\n", yaml_quote(m.synopsis));
    out
}

pub fn queue_in_release_state(text: &str, edition: &str, sid: &str) -> Result<(String, usize)> {
    let mut lines: Vec<String> = text.lines().map(str::to_string).collect();
    let section = lines
        .iter()
        .position(|l| l == "collecting_editions:")
        .ok_or_else(|| anyhow!("release-state.yaml has no collecting_editions list"))?;
    let section_end = lines
        .iter()
        .enumerate()
        .skip(section + 1)
        .find(|(_, l)| !l.is_empty() && !l.starts_with(' ') && !l.starts_with('-'))
        .map(|(i, _)| i)
        .unwrap_or(lines.len());

    let id_line_of = |l: &str| -> Option<String> {
        l.strip_prefix("- id: ")
            .map(|v| v.trim().trim_matches('\'').trim_matches('"').to_string())
    };
    let entry_start = lines[section + 1..section_end]
        .iter()
        .position(|l| id_line_of(l).as_deref() == Some(edition))
        .map(|i| i + section + 1);

    match entry_start {
        Some(start) => {
            let entry_end = lines[start + 1..section_end]
                .iter()
                .position(|l| l.starts_with("- "))
                .map(|i| i + start + 1)
                .unwrap_or(section_end);
            let ids: Vec<usize> = (start + 1..entry_end)
                .filter(|&i| lines[i].starts_with("  - "))
                .collect();
            if ids.iter().any(|&i| lines[i].trim() == format!("- {sid}")) {
                bail!("source {sid} is already queued for edition {edition}");
            }
            let insert_at = ids
                .last()
                .map(|&i| i + 1)
                .ok_or_else(|| anyhow!("collecting edition '{edition}' has no source_ids list"))?;
            lines.insert(insert_at, format!("  - {sid}"));
            let count = ids.len() + 1;
            Ok((lines.join("\n") + "\n", count))
        }
        None => {
            let block = vec![
                format!("- id: '{edition}'"),
                format!("  issue_number: {}", edition.trim_start_matches('0')),
                "  status: collecting".to_string(),
                "  source_ids:".to_string(),
                format!("  - {sid}"),
            ];
            lines.splice(section_end..section_end, block);
            if let Some(i) = lines
                .iter()
                .position(|l| l.starts_with("intake_edition_id:"))
            {
                lines[i] = format!("intake_edition_id: '{edition}'");
            }
            Ok((lines.join("\n") + "\n", 1))
        }
    }
}

pub fn prepend_sources_md(text: &str, entry: &[String], edition: &str, queued: usize) -> String {
    let mut lines: Vec<String> = text.lines().map(str::to_string).collect();
    let collecting_line = format!("_Collecting: `{edition}` ({queued} queued)._");
    let marker = format!("_Collecting: `{edition}` (");
    if let Some(i) = lines.iter().position(|l| l.starts_with(&marker)) {
        lines[i] = collecting_line;
    } else {
        let last_meta = lines
            .iter()
            .take(20)
            .enumerate()
            .filter(|(_, l)| l.starts_with('_'))
            .map(|(i, _)| i)
            .next_back()
            .unwrap_or(2);
        lines.splice(
            last_meta + 1..last_meta + 1,
            ["".to_string(), collecting_line],
        );
    }
    let first_entry = lines
        .iter()
        .position(|l| l.starts_with("## "))
        .unwrap_or(lines.len());
    let mut block: Vec<String> = entry.to_vec();
    block.push(String::new());
    lines.splice(first_entry..first_entry, block);
    lines.join("\n").trim_end().to_string() + "\n"
}

fn sources_md_entry(m: &SourceMeta, edition: &str) -> Vec<String> {
    let dash = '\u{2014}';
    let mut lines = vec![
        if m.author.is_empty() {
            format!("## {}", m.title)
        } else {
            format!("## {} {dash} {}", m.title, m.author)
        },
        String::new(),
        format!("- ID: `{}`", m.sid),
        format!("- Source: {}", m.url),
    ];
    if !m.published.is_empty() {
        lines.push(format!("- Published: {}", m.published));
    }
    lines.push(format!("- Captured: {}", m.captured_at));
    if !m.tags.is_empty() {
        lines.push(format!("- Tags: {}", m.tags.join(", ")));
    }
    lines.push(format!("- Release: queued for `{edition}`"));
    lines.push(String::new());
    lines.push(m.synopsis.to_string());
    lines
}

fn capture_prompt(html: &str, url: &str) -> Result<String> {
    Ok(format!(
        "<page>\n{}\n</page>\n\n{}\n",
        page_for_model(html),
        fs::read_to_string(crate::produce::prompts_path("capture.md"))
            .context("reading prompts/capture.md")?
            .replace("{url}", url)
            .trim()
    ))
}

struct StateLock(PathBuf);

impl StateLock {
    fn acquire() -> Result<Self> {
        let path = PathBuf::from(".magazine/capture.lock");
        fs::create_dir_all(".magazine")?;
        for _ in 0..1200 {
            match fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&path)
            {
                Ok(_) => return Ok(Self(path)),
                Err(_) => std::thread::sleep(std::time::Duration::from_millis(500)),
            }
        }
        bail!(
            "timed out waiting for {} (stale lock from a crashed capture? delete it)",
            path.display()
        );
    }
}

impl Drop for StateLock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

fn publish_source(m: &SourceMeta, src_dir: &Path, edition: &str, release_text: &str) -> Result<()> {
    fs::write(src_dir.join("record.yaml"), record_yaml(m))?;
    let (new_release, queued) = queue_in_release_state(release_text, edition, m.sid)?;
    fs::write("library/release-state.yaml", new_release)?;
    let sources_path = PathBuf::from("sources.md");
    let entry = sources_md_entry(m, edition);
    let sources_text = fs::read_to_string(&sources_path).context("reading sources.md")?;
    fs::write(
        &sources_path,
        prepend_sources_md(&sources_text, &entry, edition, queued),
    )?;
    Ok(())
}

fn iso_now() -> String {
    let s = caller::now_stamp();
    let (date, time) = s.split_at(11);
    format!("{date}{}Z", time.replace('-', ":"))
}

fn intake_edition(release_state: &str) -> Option<String> {
    release_state.lines().find_map(|l| {
        l.strip_prefix("intake_edition_id:")
            .map(|v| v.trim().trim_matches('\'').trim_matches('"').to_string())
    })
}

fn localize_images(article: &str, media_dir: &Path) -> Result<(String, usize)> {
    let re = Regex::new(r"!\[[^\]]*\]\((https?://[^)\s]+)\)").unwrap();
    let mut mapping: Vec<(String, String)> = Vec::new();
    for c in re.captures_iter(article) {
        let url = c[1].to_string();
        if mapping.iter().any(|(u, _)| *u == url) {
            continue;
        }
        let stem = media_dir.join(format!("{:03}", mapping.len() + 1));
        let dest = curl_image(&url, &stem)?;
        let name = dest.file_name().unwrap().to_string_lossy().into_owned();
        mapping.push((url, format!("media/{name}")));
    }
    let mut out = article.to_string();
    for (url, local) in &mapping {
        out = out.replace(&format!("({url})"), &format!("({local})"));
    }
    let any_image = Regex::new(r"!\[[^\]]*\]\(([^)]+)\)").unwrap();
    for c in any_image.captures_iter(&out) {
        if !c[1].starts_with("media/") {
            bail!("article still references a non-local image: {}", &c[1]);
        }
    }
    Ok((out, mapping.len()))
}

pub struct CaptureArgs {
    pub url: String,
    pub edition: Option<String>,
    pub tags: Option<String>,
    pub title: Option<String>,
    pub author: Option<String>,
    pub published: Option<String>,
    pub html: Option<PathBuf>,
    pub article: Option<String>,
    pub mode: Option<String>,
}

pub fn run(args: &CaptureArgs, spec: &ModelSpec) -> Result<i32> {
    let (url, edition, tags, mode) = (
        args.url.as_str(),
        args.edition.as_deref(),
        args.tags.as_deref(),
        args.mode.as_deref(),
    );
    let (title_override, author_override, published_override) = (
        args.title.as_deref(),
        args.author.as_deref(),
        args.published.as_deref(),
    );
    let (html_file, join_article) = (args.html.as_deref(), args.article.as_deref());
    if let Some(mode) = mode {
        if !crate::plan_cmd::CONTENT_MODES.contains(&mode) {
            bail!(
                "unknown --mode '{mode}'; one of: {}",
                crate::plan_cmd::CONTENT_MODES.join(", ")
            );
        }
    }
    let html = match html_file {
        Some(p) => fs::read_to_string(p).with_context(|| format!("reading {}", p.display()))?,
        None => curl_text(url)?,
    };
    let title = title_override
        .map(str::to_string)
        .or_else(|| page_title(&html))
        .ok_or_else(|| anyhow!("could not extract a title from {url}; pass --title"))?;
    let sid = source_id(&title, url);
    let src_dir = PathBuf::from("library/sources").join(&sid);
    if src_dir.exists() {
        bail!("{} already exists", src_dir.display());
    }

    let release_path = PathBuf::from("library/release-state.yaml");
    let release_text = fs::read_to_string(&release_path).context("reading release-state.yaml")?;
    let edition = edition
        .map(str::to_string)
        .or_else(|| intake_edition(&release_text))
        .ok_or_else(|| anyhow!("no --edition and no intake_edition_id in release-state.yaml"))?;

    fs::create_dir_all(RAW_DIR)?;
    let raw_path = PathBuf::from(RAW_DIR).join(format!("{sid}.html"));
    fs::write(&raw_path, &html).with_context(|| format!("writing {}", raw_path.display()))?;
    println!("  {sid}");
    println!("  raw html: {}", raw_path.display());

    let haystack = page_text(&html);
    let pres = pre_runs(&html);
    let prompt = capture_prompt(&html, url)?;

    let caller = Caller::new(Path::new(RAW_DIR));
    let extraction = caller.call_with_parse(&format!("capture {sid}"), spec, &prompt, |reply| {
        parse_reply(reply, &haystack, &pres)
    })?;

    let media_dir = src_dir.join("media");
    fs::create_dir_all(&media_dir)?;
    let (article, image_count) = match localize_images(&extraction.article, &media_dir) {
        Ok(v) => v,
        Err(e) => {
            let _ = fs::remove_dir_all(&src_dir);
            return Err(e);
        }
    };
    fs::write(
        src_dir.join("article.md"),
        article.trim_end().to_string() + "\n",
    )?;

    let captured_at = iso_now();
    let author = author_override
        .map(str::to_string)
        .unwrap_or_else(|| extraction.author.clone());
    let published = published_override
        .map(str::to_string)
        .or_else(|| (!extraction.published.is_empty()).then(|| extraction.published.clone()))
        .or_else(|| page_published(&html))
        .unwrap_or_default();
    let tags: Vec<String> = tags
        .unwrap_or("")
        .split(',')
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
        .collect();
    let meta = SourceMeta {
        sid: &sid,
        title: &title,
        author: &author,
        url,
        captured_at: &captured_at,
        published: &published,
        tags: &tags,
        synopsis: &extraction.synopsis,
    };
    let lock = StateLock::acquire()?;
    let release_text = fs::read_to_string(&release_path).context("reading release-state.yaml")?;
    publish_source(&meta, &src_dir, &edition, &release_text)?;
    crate::plan_cmd::add_source(&edition, &sid, join_article, mode)?;
    drop(lock);

    let words = article.split_whitespace().count();
    println!(
        "  captured: {words} words, {image_count} images, queued for {edition} (${:.2})",
        caller.total_cost()
    );
    Ok(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn source_id_matches_existing_scheme() {
        assert_eq!(
            source_id(
                "Your agent needs a computer, not a container \u{2014} introducing @cloudflare/computer",
                "https://blog.cloudflare.com/cloudflare-computer"
            ),
            "your-agent-needs-a-computer-not-a-container-intr-4851b3c5"
        );
        assert_eq!(
            source_id(
                "The actor model in 10 minutes",
                "https://www.brianstorti.com/the-actor-model/"
            ),
            "the-actor-model-in-10-minutes-47394faa"
        );
    }

    #[test]
    fn gate_accepts_verbatim_and_rejects_paraphrase() {
        let html = "<html><body><p>The actor model is a conceptual model to deal with \
                    concurrent computation and it defines some general rules for how the \
                    system components should behave and interact with each other.</p></body></html>";
        let haystack = page_text(html);
        let verbatim = "# T\nByline\n\nThe actor model is a conceptual model to deal with \
                        concurrent computation and it defines some general rules for how the \
                        system components should behave and interact with each other.";
        assert!(fidelity_gate(verbatim, &haystack, &[]).is_ok());
        let paraphrase = "# T\nByline\n\nThe actor model is a framework for concurrency that \
                          lays out rules describing the ways components of a system interact \
                          and communicate with one another over time.";
        assert!(fidelity_gate(paraphrase, &haystack, &[]).is_err());
    }

    #[test]
    fn meta_field_tolerates_colons_in_values() {
        let html = "<html><body><p>It covers dynamic Worker loading, node: imports, \
                    compatibility flags, and Wrangler configuration in celld.</p></body></html>";
        let reply = "# T\nByline\n\nIt covers dynamic Worker loading, node: imports, \
                     compatibility flags, and Wrangler configuration in celld.\n\n===META===\n\
                     synopsis: Covers dynamic Worker loading, node: imports, and flags.\n\
                     author:\npublished: 2026-08-01\n";
        let e = parse_reply(reply, &page_text(html), &[]).unwrap();
        assert_eq!(
            e.synopsis,
            "Covers dynamic Worker loading, node: imports, and flags."
        );
        assert_eq!(e.author, "");
        assert_eq!(e.published, "2026-08-01");
    }

    #[test]
    fn gate_accepts_literal_asterisks_in_page_prose() {
        let html = "<html><body><p>The bucket credentials come from the <code>AWS_*</code> \
                    environment or from explicit managed credentials, which includes instance \
                    metadata and web identity tokens.</p></body></html>";
        let reply = "# T\nByline\n\nThe bucket credentials come from the `AWS_*` environment \
                     or from explicit managed credentials, which includes instance metadata \
                     and web identity tokens.";
        assert!(fidelity_gate(reply, &page_text(html), &[]).is_ok());
    }

    #[test]
    fn gate_accepts_blockquoted_code_from_callouts() {
        let html = "<html><body><p>A note about timeouts follows here below:</p>\
                    <pre>try {\n\tconst event = await step.waitForEvent();\n} catch (e) {\n\tconsole.log(\"none\");\n}</pre></body></html>";
        let pres = pre_runs(html);
        let reply = "# T\nByline\n\n> A note about timeouts follows here below:\n>\n> ```js\n\
                     > try {\n> \tconst event = await step.waitForEvent();\n> } catch (e) {\n\
                     > \tconsole.log(\"none\");\n> }\n> ```";
        assert!(fidelity_gate(reply, &page_text(html), &pres).is_ok());
        let edited = reply.replace("console.log(\"none\")", "console.log(\"changed\")");
        assert!(fidelity_gate(&edited, &page_text(html), &pres).is_err());
    }

    #[test]
    fn gate_folds_footnote_brackets_and_link_arrows() {
        let html = "<html><body><p>Uses a TypeScript <a>type parameter \u{2197}</a> to type \
                    the return value, which must be set (up to 100 characters <sup>1</sup>) \
                    on the corresponding instance.</p></body></html>";
        let reply = "# T\nByline\n\nUses a TypeScript [type parameter](https://example.com) \
                     to type the return value, which must be set (up to 100 characters [1]) \
                     on the corresponding instance.";
        assert!(fidelity_gate(reply, &page_text(html), &[]).is_ok());
    }

    #[test]
    fn gate_accepts_links_wrapped_across_lines() {
        let html = "<html><body><p>celld implements the Workers JS RPC system: named \
                    entrypoints on service bindings, and method calls on Durable Object \
                    stubs.</p></body></html>";
        let reply = "# T\nByline\n\ncelld implements the Workers [JS RPC\nsystem](https://example.com/rpc): named entrypoints on service bindings,\nand method calls on Durable Object stubs.";
        assert!(fidelity_gate(reply, &page_text(html), &[]).is_ok());
    }

    #[test]
    fn gate_requires_exact_code_blocks() {
        let html = "<html><pre><span>let</span> x = 1;\nlet y = 2;</pre></html>";
        let pres = pre_runs(html);
        let exact = "# T\nB\n\n```js\nlet x = 1;\nlet y = 2;\n```";
        assert!(fidelity_gate(exact, &page_text(html), &pres).is_ok());
        let edited = "# T\nB\n\n```js\nlet x = 1;\nlet y = 3;\n```";
        assert!(fidelity_gate(edited, &page_text(html), &pres).is_err());
    }

    #[test]
    fn queue_appends_and_creates_editions() {
        let state = "schema_version: 2\nintake_edition_id: '006'\ncollecting_editions:\n\
                     - id: '006'\n  issue_number: 6\n  status: collecting\n  source_ids:\n  \
                     - a\n  - b\nreleased_editions:\n- id: old\n  source_ids:\n  - z\n";
        let (out, n) = queue_in_release_state(state, "006", "c").unwrap();
        assert_eq!(n, 3);
        assert!(out.contains("  - b\n  - c\nreleased_editions:"));
        assert!(queue_in_release_state(&out, "006", "c").is_err());

        let (out2, n2) = queue_in_release_state(&out, "007", "d").unwrap();
        assert_eq!(n2, 1);
        assert!(out2.contains("intake_edition_id: '007'"));
        assert!(out2.contains("- id: '007'\n  issue_number: 7\n  status: collecting\n  source_ids:\n  - d\nreleased_editions:"));
    }

    #[test]
    fn sources_md_gets_entry_and_count() {
        let md = "# Sources\n\n_Generated from source records. Do not edit by hand._\n\n\
                  _Collecting: `006` (2 queued)._\n\n## Old entry\n\n- ID: `x`\n";
        let entry = vec!["## New".to_string(), String::new(), "- ID: `y`".to_string()];
        let out = prepend_sources_md(md, &entry, "006", 3);
        assert!(out.contains("_Collecting: `006` (3 queued)._"));
        let new_pos = out.find("## New").unwrap();
        let old_pos = out.find("## Old entry").unwrap();
        assert!(new_pos < old_pos);
    }
}
