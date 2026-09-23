use super::markup::{is_illustrated_opener_header, is_print_only, piece_opening, source_link};
use super::semantic::{raw_or, render_html_edition, HtmlAsset};
use super::text::{attr, Escaper};
use crate::cover::text::{cover_contributors, cover_date, cover_tab_identity, cover_tab_issue};
use crate::model::manifest::{source_code_payload, Edition};
use crate::model::shared::{is_python_space, py_casefold, py_repr, py_strip, py_upper};
use anyhow::{bail, Context, Result};
use regex::{Captures, Regex};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

const VIEWPORT: &str = "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">";
const STYLESHEET_LINK: &str = "<link rel=\"stylesheet\" href=\"edition.css\">";
const CHARSET_LINE: &str = "  <meta charset=\"utf-8\">";
const MAIN_OPENING: &str = r"(?m)^  <main [^\n]*>$";
const MAIN_CLOSING: &str = "  </main>";
const RESERVED_NAMES: [&str; 3] = ["index.html", "edition.html", "edition.css"];
const FILLER_ROLES: [&str; 2] = ["article_tail", "closing_plate"];
const PAGE_CLOSE: [&str; 4] = [MAIN_CLOSING, "</body>", "</html>", ""];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WebAsset {
    pub asset: HtmlAsset,
    pub href: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WebEdition {
    pub root: PathBuf,
    pub index: PathBuf,
    pub pages: Vec<PathBuf>,
    pub edition_document: PathBuf,
    pub assets: Vec<WebAsset>,
}

#[derive(Default)]
pub struct WebOptions<'a> {
    pub wordmark: Option<&'a Path>,
    pub favicon: Option<&'a Path>,
    pub source_urls: BTreeMap<String, String>,
    pub headline_lines: Option<Vec<String>>,
    pub alternates: Vec<(String, String)>,
}

struct Piece {
    lines: Vec<String>,
    element_id: String,
    short_title: String,
    heading: String,
    filename: String,
}

struct Document {
    html_open: String,
    main_open: String,
    title: String,
    publication: String,
    issue: String,
    contents_label: String,
    header: Vec<String>,
    contents: Vec<String>,
    pieces: Vec<Piece>,
}

struct Cover {
    index_lines: Vec<String>,
    standalone: Vec<String>,
}

struct Chrome {
    wordmark: Option<String>,
    favicon: Option<String>,
}

struct Web<'a> {
    edition: &'a Edition,
    settable: &'a BTreeSet<u32>,
    escape: Escaper<'a>,
}

pub fn write_web_edition(
    edition: &Edition,
    settable: &BTreeSet<u32>,
    package_assets: &Path,
    destination: &Path,
    options: &WebOptions,
) -> Result<WebEdition> {
    Web {
        edition,
        settable,
        escape: Escaper(settable),
    }
    .write(package_assets, destination, options)
}

pub fn sanitize(value: &str) -> String {
    value
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || matches!(character, '.' | '_' | '-') {
                character
            } else {
                '-'
            }
        })
        .collect()
}

pub fn source_code_directory(anchor: &Path) -> Option<PathBuf> {
    anchor
        .ancestors()
        .find(|parent| parent.join("edition.yaml").is_file())
        .map(|parent| parent.join("source-codes"))
}

pub fn committed_source_svg(anchor: &Path, payload: &str) -> Result<Option<PathBuf>> {
    let Some(directory) = source_code_directory(anchor) else {
        return Ok(None);
    };
    let index = directory.join("codes.json");
    if !index.is_file() {
        return Ok(None);
    }
    let codes: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&index)?)?;
    Ok(codes["codes"]
        .as_array()
        .context("codes.json carries no codes list")?
        .iter()
        .rev()
        .find(|row| row["payload"] == payload)
        .and_then(|row| row["svg"].as_str())
        .map(|svg| directory.join(svg)))
}

fn suffix(path: &Path) -> String {
    path.extension()
        .map(|extension| extension.to_string_lossy())
        .filter(|extension| !extension.is_empty())
        .map(|extension| format!(".{extension}"))
        .unwrap_or_default()
}

fn clip(line: &str) -> String {
    py_repr(&py_strip(line).chars().take(80).collect::<String>())
}

fn split(html: &str) -> Vec<String> {
    html.split('\n').map(String::from).collect()
}

fn regex(pattern: &str) -> Regex {
    Regex::new(pattern).expect("the pattern compiles")
}

fn write_page(path: &Path, html: &str) -> Result<PathBuf> {
    if html.contains("src=\"file:") {
        bail!(
            "web page {} still references a local file: URI after source rewriting; either an \
             asset was rendered that the inventory did not declare, or an authored code span \
             contains a literal src=\"file: -- code keeps its straight quotes, so this guard \
             cannot tell the two apart and refuses both",
            path.file_name().unwrap_or_default().to_string_lossy()
        );
    }
    std::fs::write(path, html)?;
    Ok(path.to_path_buf())
}

fn copy_tree(source: &Path, target: &Path) -> Result<()> {
    std::fs::create_dir_all(target)?;
    let mut entries: Vec<PathBuf> = std::fs::read_dir(source)?
        .map(|entry| entry.map(|entry| entry.path()))
        .collect::<std::io::Result<_>>()?;
    entries.sort_by_key(|entry| entry.file_name().map(std::ffi::OsStr::to_os_string));
    for entry in entries {
        let destination = target.join(entry.file_name().unwrap_or_default());
        if entry.is_dir() {
            copy_tree(&entry, &destination)?;
        } else {
            std::fs::write(destination, std::fs::read(&entry)?)?;
        }
    }
    Ok(())
}

fn closing_line(lines: &[String], start: usize, stop: usize, closing: &str) -> Result<usize> {
    match (start + 1..stop).find(|&position| lines[position] == closing) {
        Some(position) => Ok(position),
        None => bail!(
            "web edition expected a {} line closing the element opened at {}; the semantic body \
             has changed shape",
            py_repr(closing),
            clip(&lines[start])
        ),
    }
}

fn piece(
    lines: Vec<String>,
    element_id: &str,
    claimed: &mut BTreeMap<String, String>,
) -> Result<Piece> {
    let Some(short_title) = regex(r#"data-short-title="([^"]*)""#)
        .captures(&lines[0])
        .map(|found| found[1].to_string())
    else {
        bail!(
            "web edition expected a data-short-title attribute on the piece opened at {}; the \
             page turns have nothing to say without it",
            clip(&lines[0])
        );
    };
    let heading_line = regex(r"^\s*<h1>(.*)</h1>$");
    let Some(heading) = lines.iter().find_map(|line| {
        heading_line
            .captures(line)
            .map(|found| found[1].to_string())
    }) else {
        bail!(
            "web edition expected an <h1> inside the piece opened at {}; a page needs its own title",
            clip(&lines[0])
        );
    };
    let filename = format!("{}.html", sanitize(element_id));
    let folded = py_casefold(&filename);
    if RESERVED_NAMES
        .iter()
        .any(|name| py_casefold(name) == folded)
    {
        bail!(
            "web page filename collision: piece id {} claims {filename}, a name the web \
             directory itself owns",
            py_repr(element_id)
        );
    }
    if let Some(prior) = claimed.get(&folded) {
        bail!(
            "web page filename collision: piece ids {} and {} both claim {filename}, compared \
             case-insensitively because a case-insensitive filesystem would store one file for \
             both",
            py_repr(element_id),
            py_repr(prior)
        );
    }
    claimed.insert(folded, element_id.to_string());
    Ok(Piece {
        lines,
        element_id: element_id.to_string(),
        short_title,
        heading,
        filename,
    })
}

fn header_text(header: &[String], class_name: &str) -> Result<String> {
    let pattern = regex(&format!(r#"^\s*<p class="{class_name}"[^>]*>(.*)</p>$"#));
    match header
        .iter()
        .find_map(|line| pattern.captures(line).map(|found| found[1].to_string()))
    {
        Some(text) => Ok(text),
        None => bail!(
            "web edition expected a '{class_name}' paragraph in the edition header; the masthead \
             has nothing to say without it"
        ),
    }
}

fn main_bounds(lines: &[String]) -> Result<(usize, usize)> {
    let opening = regex(MAIN_OPENING);
    let openings: Vec<usize> = (0..lines.len())
        .filter(|&index| opening.is_match(&lines[index]))
        .collect();
    let [start] = openings[..] else {
        bail!(
            "web edition expected exactly one '<main>' opening; the semantic body has changed shape"
        );
    };
    match (start..lines.len()).find(|&index| lines[index] == MAIN_CLOSING) {
        Some(stop) => Ok((start, stop)),
        None => bail!(
            "web edition expected a '  </main>' closing line; the semantic body has changed shape"
        ),
    }
}

type Parts = (Option<Vec<String>>, Option<Vec<String>>, Vec<Piece>);

fn body_parts(lines: &[String], start: usize, stop: usize) -> Result<Parts> {
    let (mut header, mut contents): (Option<Vec<String>>, Option<Vec<String>>) = (None, None);
    let mut pieces = Vec::new();
    let mut claimed = BTreeMap::new();
    let mut position = start + 1;
    while position < stop {
        let line = &lines[position];
        let closing = if line.starts_with("    <header class=\"edition-header\"") {
            let closing = closing_line(lines, position, stop, "</header>")?;
            header = Some(lines[position..=closing].to_vec());
            closing
        } else if line.starts_with("    <nav ")
            && line.contains("data-edition-navigation=\"contents\"")
        {
            let closing = closing_line(lines, position, stop, "</nav>")?;
            contents
                .get_or_insert_with(Vec::new)
                .extend_from_slice(&lines[position..=closing]);
            closing
        } else if let Some(opened) = piece_opening(line) {
            let closing = closing_line(lines, position, stop, &format!("</{}>", opened.kind))?;
            pieces.push(piece(
                lines[position..=closing].to_vec(),
                opened.id,
                &mut claimed,
            )?);
            closing
        } else {
            bail!(
                "web edition met a top-level line it does not recognize while paging the \
                 document: {}; the semantic body has changed shape",
                clip(line)
            );
        };
        position = closing + 1;
    }
    Ok((header, contents, pieces))
}

fn parse_document(html: &str) -> Result<Document> {
    let lines = split(html);
    if lines.len() < 2 || !lines[1].starts_with("<html ") {
        bail!(
            "web edition expected the semantic document to open '<html ' on its second line; the \
             document has changed shape"
        );
    }
    let title_line = regex(r"^  <title>(.*)</title>$");
    let titles: Vec<String> = lines
        .iter()
        .filter_map(|line| title_line.captures(line).map(|found| found[1].to_string()))
        .collect();
    let [title] = &titles[..] else {
        bail!(
            "web edition expected exactly one '  <title>' line in the semantic head; the document \
             has changed shape"
        );
    };
    let (start, stop) = main_bounds(&lines)?;
    let (Some(header), Some(contents), pieces) = body_parts(&lines, start, stop)? else {
        bail!(
            "web edition expected the edition header and the contents navigation inside <main>; \
             the semantic body has changed shape"
        );
    };
    let heading = regex(r"^\s*<h2>(.*)</h2>$");
    let Some(contents_label) = contents
        .iter()
        .find_map(|line| heading.captures(line).map(|found| found[1].to_string()))
    else {
        bail!(
            "web edition expected an <h2> heading inside the contents navigation; the cover cue \
             and the page turns name it"
        );
    };
    Ok(Document {
        html_open: lines[1].clone(),
        main_open: lines[start].clone(),
        title: title.clone(),
        publication: header_text(&header, "publication-name")?,
        issue: header_text(&header, "issue-number")?,
        contents_label,
        header,
        contents,
        pieces,
    })
}

fn favicon_link(href: &str, settable: &BTreeSet<u32>) -> String {
    format!(
        "<link rel=\"icon\" type=\"image/svg+xml\" href=\"{}\">",
        attr(href, settable)
    )
}

fn inject_head(html: &str, favicon: Option<&str>, settable: &BTreeSet<u32>) -> Result<String> {
    let mut lines = split(html);
    if lines.iter().filter(|line| *line == CHARSET_LINE).count() != 1 {
        bail!(
            "web edition expected exactly one '  <meta charset=\"utf-8\">' line to anchor the \
             viewport and stylesheet injection; the semantic head has changed shape"
        );
    }
    let anchor = lines
        .iter()
        .position(|line| line == CHARSET_LINE)
        .unwrap_or_default();
    let mut injected = vec![format!("  {VIEWPORT}"), format!("  {STYLESHEET_LINK}")];
    injected.extend(favicon.map(|href| format!("  {}", favicon_link(href, settable))));
    lines.splice(anchor + 1..anchor + 1, injected);
    Ok(lines.join("\n"))
}

fn close_with_colophon(html: &str, colophon: &[String]) -> Result<String> {
    let mut lines = split(html);
    if lines.iter().filter(|line| *line == MAIN_CLOSING).count() != 1 {
        bail!(
            "web edition expected exactly one '  </main>' line to anchor the colophon; the \
             semantic body has changed shape"
        );
    }
    let anchor = lines
        .iter()
        .position(|line| line == MAIN_CLOSING)
        .unwrap_or_default();
    lines.splice(anchor..anchor, colophon.iter().cloned());
    Ok(lines.join("\n"))
}

fn insert_cover_block(html: &str, block: &[String]) -> Result<String> {
    if block.is_empty() {
        return Ok(html.to_string());
    }
    let openings: Vec<&str> = regex(MAIN_OPENING)
        .find_iter(html)
        .map(|found| found.as_str())
        .collect();
    let [opening] = openings[..] else {
        bail!(
            "web edition expected exactly one '<main>' opening to anchor the cover block; the \
             semantic body has changed shape"
        );
    };
    Ok(html.replacen(opening, &format!("{opening}\n{}", block.join("\n")), 1))
}

fn drop_print_only_lines(html: &str) -> String {
    html.split('\n')
        .filter(|line| !is_print_only(line))
        .collect::<Vec<&str>>()
        .join("\n")
}

fn link_figures(html: &str) -> String {
    let image = regex(r#"(<img src="([^"]*)"[^>]*>)"#);
    html.split('\n')
        .map(|line| {
            if line
                .trim_start_matches(is_python_space)
                .starts_with("<figure data-figure-id=")
            {
                image
                    .replace_all(line, r#"<a class="figure-link" href="$2">$1</a>"#)
                    .into_owned()
            } else {
                line.to_string()
            }
        })
        .collect::<Vec<String>>()
        .join("\n")
}

fn rewrite_sources(html: &str, web_assets: &[WebAsset], settable: &BTreeSet<u32>) -> String {
    let mut replacements: Vec<(String, String)> = Vec::new();
    for web in web_assets {
        let needle = format!("src=\"{}\"", attr(&web.asset.src, settable));
        if !replacements.iter().any(|(existing, _)| *existing == needle) {
            replacements.push((needle, format!("src=\"{}\"", attr(&web.href, settable))));
        }
    }
    replacements
        .iter()
        .fold(html.to_string(), |html, (needle, replacement)| {
            html.replace(needle, replacement)
        })
}

impl Web<'_> {
    fn write(
        &self,
        package_assets: &Path,
        destination: &Path,
        options: &WebOptions,
    ) -> Result<WebEdition> {
        let semantic = render_html_edition(self.edition, self.settable)?;
        std::fs::create_dir_all(destination)?;
        let (web_assets, chrome) =
            self.materialize_assets(&semantic.assets, destination, options)?;
        let codes = self.materialize_source_codes(destination, &web_assets)?;
        let html = self.install_source_codes(&semantic.html, &codes)?;
        let html = drop_print_only_lines(&html);
        let html = self.number_provenance(&html, &options.source_urls);
        let html = rewrite_sources(&html, &web_assets, self.settable);
        let html = link_figures(&html);
        let document = parse_document(&html)?;
        let cover = self.cover_lines(
            &document,
            &web_assets,
            chrome.wordmark.as_deref(),
            options.headline_lines.as_deref(),
        );
        let masthead = self.masthead_line(&document, chrome.wordmark.as_deref());
        let favicon = chrome.favicon.as_deref();
        let mut pages = Vec::new();
        for (position, current) in document.pieces.iter().enumerate() {
            let previous = position.checked_sub(1).map(|index| &document.pieces[index]);
            let following = document.pieces.get(position + 1);
            let page = self.piece_page(&document, current, previous, following, &masthead, favicon);
            pages.push(write_page(&destination.join(&current.filename), &page)?);
        }
        let colophon_index = self.colophon_lines(&document, &options.alternates, "edition.html");
        let colophon_edition = self.colophon_lines(&document, &options.alternates, "index.html");
        let index = write_page(
            &destination.join("index.html"),
            &self.index_page(&document, &cover, &colophon_index, favicon)?,
        )?;
        let standalone = insert_cover_block(
            &inject_head(&html, favicon, self.settable)?,
            &cover.standalone,
        )?;
        let edition_document = write_page(
            &destination.join("edition.html"),
            &close_with_colophon(&standalone, &colophon_edition)?,
        )?;
        let css = package_assets.join("screen-edition.css");
        let Ok(stylesheet) = std::fs::read(&css) else {
            bail!(
                "the packaged screen stylesheet assets/screen-edition.css is missing; the web \
                 edition ships no page it cannot style"
            );
        };
        std::fs::write(destination.join("edition.css"), stylesheet)?;
        copy_tree(&package_assets.join("fonts"), &destination.join("fonts"))?;
        Ok(WebEdition {
            root: destination.to_path_buf(),
            index,
            pages,
            edition_document,
            assets: web_assets,
        })
    }

    fn materialize_assets(
        &self,
        assets: &[HtmlAsset],
        destination: &Path,
        options: &WebOptions,
    ) -> Result<(Vec<WebAsset>, Chrome)> {
        let directory = destination.join("assets");
        std::fs::create_dir_all(&directory)?;
        let mut claimed: BTreeMap<String, String> = BTreeMap::new();
        let mut chrome = Chrome {
            wordmark: None,
            favicon: None,
        };
        for (source, name, owner, slot) in [
            (
                options.wordmark,
                "wordmark.svg",
                "the publication wordmark",
                &mut chrome.wordmark,
            ),
            (
                options.favicon,
                "favicon.svg",
                "the publication favicon",
                &mut chrome.favicon,
            ),
        ] {
            if let Some(source) = source {
                claimed.insert(name.to_string(), owner.to_string());
                std::fs::copy(source, directory.join(name))?;
                *slot = Some(format!("assets/{name}"));
            }
        }
        let mut materialized = Vec::new();
        for asset in assets
            .iter()
            .filter(|asset| !FILLER_ROLES.contains(&asset.role.as_str()))
        {
            let name = format!("{}{}", sanitize(&asset.id), sanitize(&suffix(&asset.path)));
            let folded = py_casefold(&name);
            if let Some(prior) = claimed.get(&folded) {
                bail!(
                    "web asset filename collision: {} and {} both sanitize to assets/{name}, \
                     compared case-insensitively because a case-insensitive filesystem would \
                     store one file for both",
                    py_repr(&asset.id),
                    py_repr(prior)
                );
            }
            claimed.insert(folded, asset.id.clone());
            std::fs::copy(&asset.path, directory.join(&name))?;
            materialized.push(WebAsset {
                asset: asset.clone(),
                href: format!("assets/{name}"),
            });
        }
        Ok((materialized, chrome))
    }

    fn materialize_source_codes(
        &self,
        destination: &Path,
        web_assets: &[WebAsset],
    ) -> Result<BTreeMap<String, String>> {
        let mut result = BTreeMap::new();
        let mut claimed: BTreeSet<String> = web_assets
            .iter()
            .map(|web| py_casefold(web.href.rsplit('/').next().unwrap_or_default()))
            .collect();
        for article in &self.edition.articles {
            let Some(url) = article.source_url.as_deref().filter(|url| !url.is_empty()) else {
                continue;
            };
            if article.opener_art.is_none() {
                continue;
            }
            let source_id = article.source_ids.first().unwrap_or(&article.id);
            if result.contains_key(source_id) {
                continue;
            }
            let name = format!("source-code-{}.svg", sanitize(source_id));
            if !claimed.insert(py_casefold(&name)) {
                bail!("web source-code filename collision at assets/{name}");
            }
            let Some(svg) = committed_source_svg(&article.manuscript, &source_code_payload(url))?
            else {
                bail!(
                    "No committed source code for article {}; regenerate editions/<id>/source-codes",
                    article.id
                );
            };
            std::fs::write(destination.join("assets").join(&name), std::fs::read(svg)?)?;
            result.insert(source_id.clone(), format!("assets/{name}"));
        }
        Ok(result)
    }

    fn install_source_codes(&self, html: &str, codes: &BTreeMap<String, String>) -> Result<String> {
        let mut lines = Vec::new();
        let mut inside = false;
        for line in html.split('\n') {
            inside = inside || is_illustrated_opener_header(line);
            let installed = match source_link(line).filter(|_| inside) {
                Some(link) => {
                    let Some(code) = codes.get(link.source_id) else {
                        bail!(
                            "Illustrated opener source link {} has no web QR asset",
                            py_repr(link.source_id)
                        );
                    };
                    format!(
                        "{}<a class=\"source-link opener-source-link\" data-source-link=\"primary\" \
                         data-source-id=\"{}\" href=\"{}\" aria-label=\"{}\"><img class=\"source-qr\" \
                         src=\"{}\" alt=\"\"></a>",
                        link.indent,
                        link.source_id,
                        link.href,
                        link.href,
                        self.escape.attr(code)
                    )
                }
                None => line.to_string(),
            };
            inside = inside && py_strip(&installed) != "</header>";
            lines.push(installed);
        }
        Ok(lines.join("\n"))
    }

    fn number_provenance(&self, html: &str, source_urls: &BTreeMap<String, String>) -> String {
        let addresses: BTreeMap<String, String> = source_urls
            .iter()
            .map(|(id, url)| (self.escape.attr(id), self.escape.attr(url)))
            .collect();
        let span = regex(r#"<span data-source-id="([^"]*)">(.*?)</span>"#);
        html.split('\n')
            .map(|line| {
                if !line.contains("<p class=\"provenance\"") {
                    return line.to_string();
                }
                let mut counter = 0;
                span.replace_all(line, |found: &Captures| {
                    counter += 1;
                    let id = &found[1];
                    let identity = format!("data-source-id=\"{id}\" title=\"{id}\" aria-label=\"{id}\"");
                    match addresses.get(id) {
                        None => format!("<span class=\"provenance-source\" {identity}>{counter:02}</span>"),
                        Some(address) => format!(
                            "<a class=\"provenance-source\" {identity} href=\"{address}\">{counter:02}</a>"
                        ),
                    }
                })
                .into_owned()
            })
            .collect::<Vec<String>>()
            .join("\n")
    }

    fn cover_lines(
        &self,
        document: &Document,
        web_assets: &[WebAsset],
        wordmark: Option<&str>,
        headline_lines: Option<&[String]>,
    ) -> Cover {
        let edition = self.edition;
        let art_lines: Vec<String> = web_assets
            .iter()
            .find(|web| web.asset.role == "cover_art")
            .map(|art| {
                format!(
                    "    <figure class=\"cover-art\" data-asset-role=\"cover_art\"><img src=\"{}\" \
                     alt=\"{}\"></figure>",
                    self.escape.attr(&art.href),
                    self.escape.attr(&art.asset.alt_text)
                )
            })
            .into_iter()
            .collect();
        let Some(wordmark) = wordmark else {
            let mut index_lines = art_lines.clone();
            index_lines.extend(document.header.iter().cloned());
            return Cover {
                index_lines,
                standalone: art_lines,
            };
        };
        let headline_text = raw_or(edition.cover.get("headline"), &edition.title);
        let words = |text: &str| -> Vec<String> {
            text.split(is_python_space)
                .filter(|word| !word.is_empty())
                .map(String::from)
                .collect()
        };
        let headline = match headline_lines {
            Some(lines)
                if !lines.is_empty() && words(&lines.join(" ")) == words(&headline_text) =>
            {
                lines
                    .iter()
                    .map(|line| {
                        format!(
                            "<span class=\"cover-headline-line\">{}</span>",
                            self.escape.verbatim(line)
                        )
                    })
                    .collect()
            }
            _ => self.escape.verbatim(&headline_text),
        };
        let roster = self.escape.verbatim(&cover_contributors(edition));
        let date = &edition.publication_date;
        let mut block = vec![
            "    <header class=\"cover\" data-web-chrome=\"cover\">".to_string(),
            format!(
                "      <p class=\"canto\"><span class=\"canto-issue\">{}</span><span \
                 class=\"canto-identity\">{}</span></p>",
                self.escape.verbatim(&cover_tab_issue(edition)),
                self.escape.verbatim(&cover_tab_identity(edition))
            ),
            format!(
                "      <img class=\"cover-wordmark\" src=\"{}\" alt=\"{}\">",
                self.escape.attr(wordmark),
                self.escape.attr(&edition.publication_name)
            ),
            format!("      <h1 class=\"cover-headline\">{headline}</h1>"),
        ];
        block.extend(art_lines.iter().map(|line| format!("  {line}")));
        if !roster.is_empty() {
            block.push(format!("      <p class=\"cover-roster\">{roster}</p>"));
        }
        block.push(format!(
            "      <time class=\"cover-date\" datetime=\"{}\">{}</time>",
            self.escape.attr(date),
            self.escape.verbatim(&cover_date(date))
        ));
        block.push("    </header>".to_string());
        let after_headline = block
            .iter()
            .position(|line| line.contains("class=\"cover-headline\""))
            .map_or(0, |index| index + 1);
        let mut index_lines = block.clone();
        index_lines.insert(
            after_headline,
            format!(
                "      <a class=\"cover-cue\" href=\"#contents\">{}</a>",
                document.contents_label
            ),
        );
        Cover {
            index_lines,
            standalone: block,
        }
    }

    fn masthead_line(&self, document: &Document, wordmark: Option<&str>) -> String {
        let identity = match wordmark {
            None => format!(
                "<span class=\"publication-name\">{}</span>",
                document.publication
            ),
            Some(href) => format!(
                "<img class=\"masthead-wordmark\" src=\"{}\" alt=\"{}\">",
                self.escape.attr(href),
                self.escape.attr(&self.edition.publication_name)
            ),
        };
        format!(
            "    <nav class=\"masthead\" data-web-chrome=\"masthead\"><a href=\"index.html\">\
             {identity}<span class=\"issue-number\">{}</span></a></nav>",
            document.issue
        )
    }

    fn colophon_lines(
        &self,
        document: &Document,
        alternates: &[(String, String)],
        sibling: &str,
    ) -> Vec<String> {
        let edition = self.edition;
        let (sibling_label, here) = if sibling == "edition.html" {
            (
                self.escape.verbatim(&cover_tab_issue(edition)),
                "index.html",
            )
        } else {
            (document.contents_label.clone(), "edition.html")
        };
        let mut links = format!(
            "<a class=\"colophon-sibling\" href=\"{}\">{sibling_label}</a>",
            self.escape.attr(sibling)
        );
        for (code, prefix) in alternates {
            links.push_str(&format!(
                "<a class=\"colophon-language\" href=\"{}\" hreflang=\"{}\" lang=\"{}\">{}</a>",
                self.escape.attr(&format!("{prefix}{here}")),
                self.escape.attr(code),
                self.escape.attr(code),
                self.escape.verbatim(&py_upper(code))
            ));
        }
        let date = &edition.publication_date;
        vec![
            "    <footer class=\"colophon\" data-web-chrome=\"colophon\">".to_string(),
            format!(
                "      <p class=\"colophon-identity\">{}</p>",
                self.escape.verbatim(&cover_tab_identity(edition))
            ),
            format!("      <nav class=\"colophon-links\">{links}</nav>"),
            format!(
                "      <time class=\"colophon-date\" datetime=\"{}\">{}</time>",
                self.escape.attr(date),
                self.escape.verbatim(&cover_date(date))
            ),
            "    </footer>".to_string(),
        ]
    }

    fn shared_head(&self, document: &Document, title: &str, favicon: Option<&str>) -> Vec<String> {
        let mut lines = vec![
            "<!doctype html>".to_string(),
            document.html_open.clone(),
            "<head>".to_string(),
            CHARSET_LINE.to_string(),
            format!("  {VIEWPORT}"),
            format!("  {STYLESHEET_LINK}"),
        ];
        lines.extend(favicon.map(|href| format!("  {}", favicon_link(href, self.settable))));
        lines.extend([
            format!("  <title>{title}</title>"),
            "</head>".to_string(),
            "<body>".to_string(),
            document.main_open.clone(),
        ]);
        lines
    }

    fn index_page(
        &self,
        document: &Document,
        cover: &Cover,
        colophon: &[String],
        favicon: Option<&str>,
    ) -> Result<String> {
        let filenames: BTreeMap<&str, &str> = document
            .pieces
            .iter()
            .map(|piece| (piece.element_id.as_str(), piece.filename.as_str()))
            .collect();
        let href = regex(r##"href="#([^"]*)""##);
        let mut contents = Vec::new();
        for line in &document.contents {
            if let Some(missing) = href
                .captures_iter(line)
                .map(|found| found[1].to_string())
                .find(|target| !filenames.contains_key(target.as_str()))
            {
                bail!(
                    "the contents navigation points at #{missing} but no piece with that id was \
                     paged; the semantic body has changed shape"
                );
            }
            contents.push(
                href.replace_all(line, |found: &Captures| {
                    format!("href=\"{}\"", filenames[&found[1]])
                })
                .into_owned(),
            );
        }
        if !contents[0]
            .trim_start_matches(is_python_space)
            .starts_with("<nav ")
        {
            bail!(
                "web edition expected the contents block to open on its <nav> line; the semantic \
                 body has changed shape"
            );
        }
        contents[0] = contents[0].replacen("<nav ", "<nav id=\"contents\" ", 1);
        let mut lines = self.shared_head(document, &document.title, favicon);
        lines.extend(cover.index_lines.iter().cloned());
        lines.extend(contents);
        lines.extend(colophon.iter().cloned());
        lines.extend(PAGE_CLOSE.map(String::from));
        Ok(lines.join("\n"))
    }

    fn piece_page(
        &self,
        document: &Document,
        piece: &Piece,
        previous: Option<&Piece>,
        following: Option<&Piece>,
        masthead: &str,
        favicon: Option<&str>,
    ) -> String {
        let mut turns = String::new();
        if let Some(previous) = previous {
            turns.push_str(&format!(
                "<a class=\"page-turn-previous\" rel=\"prev\" href=\"{}\">{}</a>",
                self.escape.attr(&previous.filename),
                previous.short_title
            ));
        }
        turns.push_str(&format!(
            "<a class=\"page-turn-contents\" href=\"index.html\">{}</a>",
            document.contents_label
        ));
        if let Some(following) = following {
            turns.push_str(&format!(
                "<a class=\"page-turn-next\" rel=\"next\" href=\"{}\">{}</a>",
                self.escape.attr(&following.filename),
                following.short_title
            ));
        }
        let title = format!("{} \u{2014} {}", document.publication, piece.heading);
        let mut lines = self.shared_head(document, &title, favicon);
        lines.push(masthead.to_string());
        lines.extend(piece.lines.iter().cloned());
        lines.push(format!(
            "    <nav class=\"page-turn\" data-web-chrome=\"page-turn\">{turns}</nav>"
        ));
        lines.extend(PAGE_CLOSE.map(String::from));
        lines.join("\n")
    }
}
