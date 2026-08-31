use crate::capture;
use anyhow::{Context, Result};
use ego_tree::NodeId;
use regex::Regex;
use scraper::{Html, Selector};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use url::Url;

const JUNK: &str = "script, noscript, iframe, video, audio, embed, object, form, button, input, \
select, textarea, canvas, dialog, template, .related-posts, .related-wrapper, .related, \
.navigation, .post-nav, .pagination, .comments, #comments, .comment-section, .share, .social, \
[class*=\"subscribe\"], [class*=\"newsletter\"], [id*=\"newsletter\"], a[href*=\"#/portal\"], .modal, .popup, .pswp, .post-footer, .sidebar, .search, .cookie-banner, \
.skip-link, .read-next, .site-header, .site-footer, .kg-video-card, .kg-embed-card, \
.kg-audio-card, .kg-file-card, .kg-signup-card, .kg-cta-card, [class*=\"bookmark\"]";
const CHROME: &str = "header, nav, footer, aside";
const CAPS_MM: [u32; 3] = [130, 110, 90];
const CHROME_APPS: [&str; 4] = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
];
const KEEP_EMPTY: [&str; 12] = [
    "br", "wbr", "hr", "img", "svg", "picture", "table", "pre", "td", "th", "col", "colgroup",
];
const CONTENT_TAGS: [&str; 6] = ["img", "svg", "picture", "table", "pre", "hr"];
const ROOTS: [&str; 6] = [
    "main",
    "article",
    "[role=\"main\"]",
    "#content",
    ".post",
    ".entry-content",
];
const READER_CSS: &str = r#"<style>
@page { size: A4; margin: 18mm; }
html { font-size: 11pt; }
body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.5; color: #111;
  background: #fff; max-width: 150mm; margin: 0 auto; }
h1 { font-size: 1.9rem; line-height: 1.25; margin: 0 0 0.4em; }
h2 { font-size: 1.4rem; margin: 1.2em 0 0.4em; }
h3 { font-size: 1.2rem; margin: 1.1em 0 0.3em; }
h4, h5, h6 { font-size: 1.05rem; margin: 1em 0 0.3em; }
p, ul, ol, table { margin: 0.55em 0; }
li { margin: 0.2em 0; }
a { color: inherit; }
img { display: block; max-width: 100%; max-height: {cap}mm; width: auto; height: auto;
  margin: 0.9em auto; }
figure { margin: 0.9em auto; }
figcaption { font-size: 0.85rem; color: #555; text-align: center; margin-top: 0.35em; }
pre { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.8rem;
  line-height: 1.4; background: #f5f5f5; border: 0.3mm solid #ddd; padding: 0.6em 0.8em;
  white-space: pre-wrap; word-break: break-word; margin: 0.8em 0; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85em; }
blockquote { margin: 0.8em 0; padding-left: 1em; border-left: 0.8mm solid #bbb; color: #333; }
table { border-collapse: collapse; font-size: 0.85rem; }
td, th { border: 0.2mm solid #ccc; padding: 0.3em 0.5em; text-align: left; }
hr { border: 0; border-top: 0.3mm solid #ccc; margin: 1.2em 0; }
@media print {
  body { orphans: 3; widows: 3; }
  img, figure, table { break-inside: avoid; }
  h1, h2, h3, h4 { break-after: avoid; }
}
</style>"#;

pub struct PrintArgs {
    pub url: String,
    pub html: Option<PathBuf>,
    pub out: Option<PathBuf>,
    pub chrome: Option<PathBuf>,
    pub image_cap: Option<u32>,
}

pub fn run(args: &PrintArgs) -> Result<i32> {
    let base = Url::parse(&args.url).context("parsing url")?;
    let raw = match &args.html {
        Some(p) => fs::read_to_string(p).with_context(|| format!("reading {}", p.display()))?,
        None => capture::curl_text(&args.url)?,
    };
    let title = capture::page_title(&raw).unwrap_or_else(|| "untitled".to_string());
    let out_dir = args
        .out
        .clone()
        .unwrap_or_else(|| Path::new("output/print").join(capture::source_id(&title, &args.url)));
    fs::create_dir_all(&out_dir)?;
    let mut doc = Html::parse_document(&raw);
    clean(&mut doc);
    strip_link_litter(&mut doc);
    strip_empty(&mut doc);
    strip_dangling_tails(&mut doc);
    strip_empty(&mut doc);
    let page = reader_content(&doc);
    let (page, images) = localize_images(&page, &base, &out_dir)?;
    let index = out_dir.join("index.html");
    let pdf = out_dir.join("print.pdf");
    let chrome = chrome_binary(args.chrome.as_deref())?;
    let caps = args.image_cap.map_or_else(|| CAPS_MM.to_vec(), |c| vec![c]);
    let mut best: Option<(u32, usize)> = None;
    for cap in caps {
        fs::write(&index, finish(&page, &base, &title, cap))?;
        print_pdf(&chrome, &index, &pdf)?;
        let pages = pdf_pages(&pdf)?;
        if best.is_none_or(|(_, p)| pages < p) {
            best = Some((cap, pages));
        }
    }
    let (cap, pages) = best.unwrap();
    fs::write(&index, finish(&page, &base, &title, cap))?;
    print_pdf(&chrome, &index, &pdf)?;
    println!(
        "printable: {} ({pages} pages, images fit to {cap}mm, {images} images localized)",
        pdf.display()
    );
    println!("next: open {} and print it", pdf.display());
    Ok(0)
}

fn pdf_pages(pdf: &Path) -> Result<usize> {
    max_count(&fs::read(pdf)?)
        .ok_or_else(|| anyhow::anyhow!("no page count found in {}", pdf.display()))
}

fn max_count(bytes: &[u8]) -> Option<usize> {
    regex::bytes::Regex::new(r"/Count (\d+)")
        .unwrap()
        .captures_iter(bytes)
        .filter_map(|c| std::str::from_utf8(&c[1]).ok().and_then(|n| n.parse().ok()))
        .max()
}

fn chrome_binary(flag: Option<&Path>) -> Result<PathBuf> {
    if let Some(p) = flag {
        anyhow::ensure!(p.exists(), "--chrome {} does not exist", p.display());
        return Ok(p.to_path_buf());
    }
    if let Some(p) = CHROME_APPS.iter().map(Path::new).find(|p| p.exists()) {
        return Ok(p.to_path_buf());
    }
    for name in ["google-chrome", "chromium", "chromium-browser"] {
        let out = std::process::Command::new("which").arg(name).output();
        if let Ok(o) = out {
            if o.status.success() {
                return Ok(PathBuf::from(
                    String::from_utf8_lossy(&o.stdout).trim().to_string(),
                ));
            }
        }
    }
    anyhow::bail!("no Chrome or Chromium found for PDF output; pass --chrome <browser binary>")
}

fn print_pdf(chrome: &Path, index: &Path, pdf: &Path) -> Result<()> {
    let abs = index.canonicalize()?;
    let out = std::process::Command::new(chrome)
        .args(["--headless=new", "--disable-gpu", "--no-pdf-header-footer"])
        .arg(format!("--print-to-pdf={}", pdf.display()))
        .arg(format!("file://{}", abs.display()))
        .output()
        .context("spawning chrome for pdf print")?;
    if !out.status.success() || !pdf.exists() {
        let err = String::from_utf8_lossy(&out.stderr);
        anyhow::bail!(
            "chrome pdf print failed: {}",
            err.lines().last().unwrap_or("")
        );
    }
    Ok(())
}

fn strip_link_litter(doc: &mut Html) {
    let ids: Vec<NodeId> = doc
        .select(&sel("p, li"))
        .filter(is_link_litter)
        .map(|e| e.id())
        .collect();
    for id in ids {
        if let Some(mut n) = doc.tree.get_mut(id) {
            n.detach();
        }
    }
}

fn is_link_litter(e: &scraper::ElementRef) -> bool {
    let anchors: Vec<String> = e
        .select(&sel("a"))
        .map(|a| a.text().collect::<String>().trim().to_string())
        .collect();
    let url_like = |t: &String| t.starts_with("http") || t.starts_with("www.");
    if anchors.is_empty() || !anchors.iter().all(url_like) {
        return false;
    }
    let total = e.text().flat_map(str::split_whitespace).count();
    let linked: usize = anchors.iter().map(|t| t.split_whitespace().count()).sum();
    total.saturating_sub(linked) <= 2
}

fn sel(s: &str) -> Selector {
    Selector::parse(s).unwrap()
}

fn clean(doc: &mut Html) {
    let mut ids: Vec<NodeId> = doc.select(&sel(JUNK)).map(|e| e.id()).collect();
    let (root, is_body) = content_root(doc);
    ids.extend(
        doc.select(&sel(CHROME))
            .filter(|e| !related(doc, e.id(), root))
            .map(|e| e.id()),
    );
    if is_body {
        let direct = "body > header, body > nav, body > footer, body > aside";
        ids.extend(doc.select(&sel(direct)).map(|e| e.id()));
    }
    for id in ids {
        if let Some(mut n) = doc.tree.get_mut(id) {
            n.detach();
        }
    }
}

fn strip_empty(doc: &mut Html) {
    let ids: Vec<NodeId> = doc
        .select(&sel("body *"))
        .filter(|e| is_empty(e))
        .map(|e| e.id())
        .collect();
    for id in ids {
        if let Some(mut n) = doc.tree.get_mut(id) {
            n.detach();
        }
    }
}

fn is_empty(e: &scraper::ElementRef) -> bool {
    !KEEP_EMPTY.contains(&e.value().name())
        && !e.text().any(|t| !t.trim().is_empty())
        && !has_content(e)
}

fn has_content(e: &scraper::ElementRef) -> bool {
    e.descendants()
        .filter_map(scraper::ElementRef::wrap)
        .any(|d| CONTENT_TAGS.contains(&d.value().name()))
}

fn strip_dangling_tails(doc: &mut Html) {
    loop {
        let ids: Vec<NodeId> = doc
            .select(&sel("p"))
            .filter(is_dangling_tail)
            .map(|e| e.id())
            .collect();
        if ids.is_empty() {
            return;
        }
        for id in ids {
            if let Some(mut n) = doc.tree.get_mut(id) {
                n.detach();
            }
        }
    }
}

fn is_dangling_tail(e: &scraper::ElementRef) -> bool {
    if has_content(e) || e.next_siblings().any(|n| n.value().is_element()) {
        return false;
    }
    let text = e.text().collect::<String>().trim().to_string();
    text.ends_with(':') || text.chars().filter(|c| c.is_alphanumeric()).count() <= 3
}

fn content_root(doc: &Html) -> (NodeId, bool) {
    for s in ROOTS {
        if let Some(e) = doc.select(&sel(s)).next() {
            return (e.id(), false);
        }
    }
    let body = doc
        .select(&sel("body"))
        .next()
        .map_or_else(|| doc.root_element().id(), |e| e.id());
    (body, true)
}

fn related(doc: &Html, a: NodeId, b: NodeId) -> bool {
    let chain = |id: NodeId| {
        doc.tree
            .get(id)
            .into_iter()
            .flat_map(move |n| std::iter::once(id).chain(n.ancestors().map(|x| x.id())))
    };
    chain(a).any(|x| x == b) || chain(b).any(|x| x == a)
}

fn attr(tag: &str, name: &str) -> Option<String> {
    Regex::new(&format!(r#"(?i)\b{name}\s*=\s*["']([^"']*)["']"#))
        .unwrap()
        .captures(tag)
        .map(|c| c[1].to_string())
}

fn img_source(tag: &str, base: &Url) -> Option<String> {
    let raw = attr(tag, "src")
        .filter(|s| !s.is_empty())
        .or_else(|| attr(tag, "data-src"))
        .or_else(|| {
            attr(tag, "srcset")
                .or_else(|| attr(tag, "data-srcset"))
                .and_then(|s| largest_srcset(&s))
        })?;
    base.join(raw.trim()).ok().map(String::from)
}

fn largest_srcset(srcset: &str) -> Option<String> {
    srcset
        .split(',')
        .filter_map(|c| {
            let mut it = c.split_whitespace();
            let u = it.next()?;
            let w = it
                .next()
                .and_then(|d| d.trim_end_matches(['w', 'x']).parse::<f64>().ok())
                .unwrap_or(1.0);
            Some((u.to_string(), w))
        })
        .max_by(|a, b| a.1.total_cmp(&b.1))
        .map(|(u, _)| u)
}

fn rebuild_img(tag: &str, src: &str) -> String {
    let mut out = format!("<img src=\"{src}\"");
    for k in ["alt", "width", "height"] {
        if let Some(v) = attr(tag, k) {
            out += &format!(" {k}=\"{v}\"");
        }
    }
    out + ">"
}

fn localize_images(html: &str, base: &Url, dir: &Path) -> Result<(String, usize)> {
    let tag_re = Regex::new(r"(?is)<img\b[^>]*>").unwrap();
    let mut urls: Vec<String> = Vec::new();
    for m in tag_re.find_iter(html) {
        if attr(m.as_str(), "src").is_some_and(|s| s.starts_with("data:")) {
            continue;
        }
        if let Some(u) = img_source(m.as_str(), base) {
            if u.starts_with("http") && !urls.contains(&u) {
                urls.push(u);
            }
        }
    }
    let assets = dir.join("assets");
    fs::create_dir_all(&assets)?;
    let local = download_all(&urls, &assets);
    let out = tag_re.replace_all(html, |c: &regex::Captures| {
        let tag = c.get(0).unwrap().as_str();
        if attr(tag, "src").is_some_and(|s| s.starts_with("data:")) {
            return tag.to_string();
        }
        match img_source(tag, base).and_then(|u| local.get(&u)) {
            Some(l) => rebuild_img(tag, l),
            None => String::new(),
        }
    });
    Ok((out.into_owned(), local.len()))
}

fn download_all(urls: &[String], assets: &Path) -> HashMap<String, String> {
    let results: Vec<Result<PathBuf>> = std::thread::scope(|s| {
        let handles: Vec<_> = urls
            .iter()
            .enumerate()
            .map(|(i, u)| {
                s.spawn(move || capture::curl_image(u, &assets.join(format!("{:03}", i + 1))))
            })
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    let mut map = HashMap::new();
    for (u, r) in urls.iter().zip(results) {
        match r {
            Ok(p) => {
                let name = p.file_name().unwrap().to_string_lossy().into_owned();
                map.insert(u.clone(), format!("assets/{name}"));
            }
            Err(e) => eprintln!("warning: dropping image {u}: {e:#}"),
        }
    }
    map
}

fn absolutize_hrefs(html: &str, base: &Url) -> String {
    Regex::new(r#"(?is)(<a\b[^>]*\bhref=["'])([^"'#][^"']*)(["'])"#)
        .unwrap()
        .replace_all(html, |c: &regex::Captures| {
            base.join(&c[2])
                .map_or_else(|_| c[0].to_string(), |u| format!("{}{}{}", &c[1], u, &c[3]))
        })
        .into_owned()
}

fn reader_content(doc: &Html) -> String {
    let (root, is_body) = content_root(doc);
    let el = doc
        .tree
        .get(root)
        .and_then(scraper::ElementRef::wrap)
        .unwrap_or_else(|| doc.root_element());
    if is_body {
        el.inner_html()
    } else {
        el.html()
    }
}

fn escape_text(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn strip_attrs(html: &str) -> String {
    let mut svgs: Vec<String> = Vec::new();
    let svg_re = Regex::new(r"(?is)<svg\b.*?</svg>").unwrap();
    let stashed = svg_re.replace_all(html, |c: &regex::Captures| {
        svgs.push(c[0].to_string());
        format!("\u{1}{}\u{1}", svgs.len() - 1)
    });
    let tag = Regex::new(r"<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>").unwrap();
    let mut out = tag
        .replace_all(&stashed, |c: &regex::Captures| {
            let name = c[1].to_lowercase();
            let keep: &[&str] = match name.as_str() {
                "a" => &["href"],
                "img" => &["src", "alt", "width", "height"],
                "td" | "th" => &["colspan", "rowspan"],
                _ => &[],
            };
            let mut t = format!("<{name}");
            for k in keep {
                if let Some(v) = attr(&c[0], k) {
                    t += &format!(" {k}=\"{v}\"");
                }
            }
            t + ">"
        })
        .into_owned();
    for (i, svg) in svgs.iter().enumerate() {
        out = out.replace(&format!("\u{1}{i}\u{1}"), svg);
    }
    out
}

fn ensure_h1(html: &str, title: &str) -> String {
    if Regex::new(r"(?i)<h1[\s>]").unwrap().is_match(html) {
        html.to_string()
    } else {
        format!("<h1>{}</h1>\n{html}", escape_text(title))
    }
}

fn finish(html: &str, base: &Url, title: &str, cap: u32) -> String {
    let s = Regex::new(r"(?s)<!--.*?-->")
        .unwrap()
        .replace_all(html, " ")
        .into_owned();
    let s = Regex::new(r"(?is)<style\b[^>]*>.*?</style>")
        .unwrap()
        .replace_all(&s, " ")
        .into_owned();
    let s = strip_attrs(&s);
    let s = absolutize_hrefs(&s, base);
    let s = ensure_h1(&s, title);
    let css = READER_CSS.replace("{cap}", &cap.to_string());
    format!(
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n<title>{}</title>\n\
{css}\n</head>\n<body>\n{s}\n</body>\n</html>\n",
        escape_text(title)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_strips_chrome_and_keeps_article() {
        let html = "<html><head><title>t</title></head><body><header id=\"site\">chrome</header>\
<nav>menu</nav><article><header><h1>Post</h1></header><p>body</p><script>x()</script>\
<div class=\"related-posts\">more</div></article><footer>foot</footer></body></html>";
        let mut doc = Html::parse_document(html);
        clean(&mut doc);
        let out = doc.root_element().html();
        assert!(out.contains("<h1>Post</h1>"));
        assert!(out.contains("<p>body</p>"));
        for gone in ["chrome", "menu", "more", "foot", "x()"] {
            assert!(!out.contains(gone), "still contains {gone}");
        }
    }

    #[test]
    fn clean_without_content_root_strips_direct_chrome() {
        let html = "<html><body><header>chrome</header><div><h1>Post</h1><p>body</p></div>\
<footer>foot</footer></body></html>";
        let mut doc = Html::parse_document(html);
        clean(&mut doc);
        let out = doc.root_element().html();
        assert!(out.contains("<p>body</p>"));
        assert!(!out.contains("chrome"));
        assert!(!out.contains("foot"));
    }

    #[test]
    fn link_litter_goes_prose_links_stay() {
        let html = "<html><body><article><p>The code is at <a href=\"https://g.com/r\">\
https://g.com/r</a>.</p><p>pinned: <a href=\"https://x.com/a/1\">https://x.com/a/1</a></p>\
<ul><li>X - <a href=\"https://x.com/a\">https://x.com/a</a></li></ul>\
<figure class=\"kg-bookmark-card\"><a href=\"/other\">Other post</a></figure>\
</article></body></html>";
        let mut doc = Html::parse_document(html);
        clean(&mut doc);
        strip_link_litter(&mut doc);
        strip_empty(&mut doc);
        let out = doc.root_element().html();
        assert!(out.contains("The code is at"));
        assert!(!out.contains("pinned:"));
        assert!(!out.contains("<ul>"));
        assert!(!out.contains("Other post"));
    }

    #[test]
    fn page_count_is_the_max_pdf_count() {
        assert_eq!(max_count(b"<</Type/Pages/Count 3>> /Count 16 x"), Some(16));
        assert_eq!(max_count(b"no counts"), None);
    }

    #[test]
    fn finish_builds_a_reader_page() {
        let base = Url::parse("https://x.com/").unwrap();
        let out = finish("<p>x</p>", &base, "T & Co", 110);
        assert!(out.contains("max-height: 110mm"));
        assert!(!out.contains("{cap}"));
        assert!(out.contains("<title>T &amp; Co</title>"));
        assert!(out.contains("<h1>T &amp; Co</h1>"));
        assert!(out.contains("Georgia"));
    }

    #[test]
    fn attrs_are_stripped_to_reader_whitelist() {
        let html = "<div class=\"x\" style=\"c:red\"><a href=\"/a\" target=\"_b\">l</a>\
<img src=\"s\" alt=\"a\" class=\"k\"><svg viewBox=\"0 0 1 1\"><path d=\"M0\"/></svg></div>";
        let out = strip_attrs(html);
        assert!(out.contains("<div><a href=\"/a\">l</a><img src=\"s\" alt=\"a\">"));
        assert!(out.contains("viewBox=\"0 0 1 1\""));
        assert!(out.contains("<path d=\"M0\"/>"));
    }

    #[test]
    fn dangling_tail_labels_are_dropped() {
        let html = "<html><body><article><p>Cya soon.</p><p>ps..</p><p>pps. socials:</p>\
</article></body></html>";
        let mut doc = Html::parse_document(html);
        strip_dangling_tails(&mut doc);
        let out = doc.root_element().html();
        assert!(out.contains("Cya soon."));
        assert!(!out.contains("ps.."));
        assert!(!out.contains("socials"));
    }

    #[test]
    fn strip_empty_drops_spacers_and_keeps_structure() {
        let html = "<html><body><article><p>text<br>more</p>\
<figure class=\"u-placeholder\"><div></div></figure><picture><source srcset=\"x 1w\">\
<img src=\"y\"></picture><table><tr><td></td><td>v</td></tr></table></article></body></html>";
        let mut doc = Html::parse_document(html);
        strip_empty(&mut doc);
        let out = doc.root_element().html();
        assert!(out.contains("text<br>more"));
        assert!(!out.contains("u-placeholder"));
        assert!(!out.contains("<source"));
        assert!(out.contains("<img src=\"y\">"));
        assert!(out.contains("<td></td><td>v</td>"));
    }

    #[test]
    fn largest_srcset_picks_widest() {
        let s = "https://x/a.png 600w, https://x/b.png 1200w, https://x/c.png 900w";
        assert_eq!(largest_srcset(s).unwrap(), "https://x/b.png");
    }

    #[test]
    fn rebuild_img_keeps_content_attrs_only() {
        let tag = "<img src=\"x\" class=\"kg-image\" alt=\"a\" loading=\"lazy\" \
onerror=\"hide()\" srcset=\"y 2x\">";
        let out = rebuild_img(tag, "assets/001.png");
        assert_eq!(out, "<img src=\"assets/001.png\" alt=\"a\">");
    }

    #[test]
    fn hrefs_become_absolute_but_anchors_stay() {
        let base = Url::parse("https://x.com/rad/").unwrap();
        let html = "<a href=\"/other/\">o</a><a href=\"#top\">t</a>";
        let out = absolutize_hrefs(html, &base);
        assert!(out.contains("href=\"https://x.com/other/\""));
        assert!(out.contains("href=\"#top\""));
    }
}
