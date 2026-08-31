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
.kg-audio-card, .kg-file-card, .kg-signup-card, .kg-cta-card";
const CHROME: &str = "header, nav, footer, aside";
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
const PRINT_CSS: &str = "<style>\n@page { size: A4; margin: 18mm 15mm; }\nimg { max-width: 100% \
!important; height: auto !important; }\npre { white-space: pre-wrap !important; word-break: \
break-word; }\n@media print {\n  html, body { background: #fff !important; }\n  img, figure, \
blockquote, pre { break-inside: avoid; }\n  h1, h2, h3, h4 { break-after: avoid; }\n}\n</style>";

pub struct PrintArgs {
    pub url: String,
    pub html: Option<PathBuf>,
    pub out: Option<PathBuf>,
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
    strip_empty(&mut doc);
    let page = doc.root_element().html();
    let (page, images) = localize_images(&page, &base, &out_dir)?;
    let (page, sheets) = inline_styles(&page, &base);
    let index = out_dir.join("index.html");
    fs::write(&index, finish(&page, &base))?;
    println!(
        "printable: {} ({images} images localized, {sheets} stylesheets inlined)",
        index.display()
    );
    println!("next: open {} and print from the browser", index.display());
    Ok(0)
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
        && !e
            .descendants()
            .filter_map(scraper::ElementRef::wrap)
            .any(|d| CONTENT_TAGS.contains(&d.value().name()))
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
    for k in ["alt", "title", "class", "width", "height"] {
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

fn inline_styles(html: &str, base: &Url) -> (String, usize) {
    let re = Regex::new(r"(?is)<link\b[^>]*>").unwrap();
    let mut count = 0usize;
    let out = re.replace_all(html, |c: &regex::Captures| {
        let tag = c.get(0).unwrap().as_str();
        let is_sheet = attr(tag, "rel").is_some_and(|r| r.eq_ignore_ascii_case("stylesheet"));
        let href = attr(tag, "href").and_then(|h| base.join(&h).ok());
        let (Some(u), true) = (href, is_sheet) else {
            return tag.to_string();
        };
        match capture::curl_text(u.as_str()) {
            Ok(css) => {
                count += 1;
                format!("<style>\n{}\n</style>", absolutize_css(&css, &u))
            }
            Err(e) => {
                eprintln!("warning: keeping remote stylesheet {u}: {e:#}");
                format!("<link rel=\"stylesheet\" href=\"{u}\">")
            }
        }
    });
    (out.into_owned(), count)
}

fn absolutize_css(css: &str, css_url: &Url) -> String {
    Regex::new(r#"url\(\s*(['"]?)([^'")]+)['"]?\s*\)"#)
        .unwrap()
        .replace_all(css, |c: &regex::Captures| {
            let target = &c[2];
            if target.starts_with("data:") || target.starts_with("http") {
                c[0].to_string()
            } else {
                css_url
                    .join(target)
                    .map_or_else(|_| c[0].to_string(), |u| format!("url(\"{u}\")"))
            }
        })
        .into_owned()
}

fn absolutize_inline_styles(html: &str, base: &Url) -> String {
    Regex::new(r"(?is)(<style\b[^>]*>)(.*?)(</style>)")
        .unwrap()
        .replace_all(html, |c: &regex::Captures| {
            format!("{}{}{}", &c[1], absolutize_css(&c[2], base), &c[3])
        })
        .into_owned()
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

fn finish(html: &str, base: &Url) -> String {
    let s = Regex::new(r"(?s)<!--.*?-->")
        .unwrap()
        .replace_all(html, " ")
        .into_owned();
    let s = absolutize_inline_styles(&s, base);
    let s = absolutize_hrefs(&s, base);
    let head = Regex::new(r"(?i)</head>").unwrap();
    let s = if head.is_match(&s) {
        head.replace(&s, format!("{PRINT_CSS}\n</head>").as_str())
            .into_owned()
    } else {
        format!("{PRINT_CSS}\n{s}")
    };
    format!("<!DOCTYPE html>\n{s}")
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
        assert_eq!(
            out,
            "<img src=\"assets/001.png\" alt=\"a\" class=\"kg-image\">"
        );
    }

    #[test]
    fn css_urls_become_absolute() {
        let base = Url::parse("https://x.com/assets/built/screen.css").unwrap();
        let css =
            "a{background:url(../fonts/f.woff2)}b{mask:url('/m.svg')}c{cursor:url(\"data:x\")}";
        let out = absolutize_css(css, &base);
        assert!(out.contains("url(\"https://x.com/assets/fonts/f.woff2\")"));
        assert!(out.contains("url(\"https://x.com/m.svg\")"));
        assert!(out.contains("url(\"data:x\")"));
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
