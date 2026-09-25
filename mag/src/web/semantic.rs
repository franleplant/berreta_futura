use super::text::Escaper;
use crate::model::doc::{
    fold_reader_characters, inline_text, parse_publication_document, Block, Document, Inline,
};
use crate::model::manifest::{Article, Edition, Editorial, Section};
use crate::model::records::{Extract, Figure};
use crate::model::shared::{
    anchor_key, article_opener_format, clamp_roster, content_label, is_name_roster,
    is_reference_heading, py_repr, py_strip, raw_or, scalar_label, ui,
};
use anyhow::{bail, Context, Result};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

pub const ILLUSTRATED: &str = "illustrated_paper_spots_v1";
const OPENER_ANCHOR: &str = "__opener__";
const PLATE_WINDOW_ASPECT: f64 = 333.0079 / 390.2756;
const CONTENTS_TITLE_LIMIT: usize = 62;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct HtmlAsset {
    pub id: String,
    pub role: String,
    pub path: PathBuf,
    pub src: String,
    pub alt_text: String,
    pub article_id: Option<String>,
    pub figure_id: Option<String>,
    pub source_id: Option<String>,
    pub caption: Option<String>,
    pub credit: Option<String>,
    pub anchor: Option<String>,
    pub layout: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HtmlEdition {
    pub html: String,
    pub assets: Vec<HtmlAsset>,
}

pub fn render_html_edition(edition: &Edition, settable: &BTreeSet<u32>) -> Result<HtmlEdition> {
    Renderer {
        edition,
        settable,
        escape: Escaper(settable),
    }
    .render()
}

pub fn file_uri(path: &Path) -> String {
    let mut uri = String::from("file://");
    for byte in path.to_string_lossy().bytes() {
        if byte.is_ascii_alphanumeric() || b"/_.-~".contains(&byte) {
            uri.push(char::from(byte));
        } else {
            uri.push_str(&format!("%{byte:02X}"));
        }
    }
    uri
}

fn indent(lines: &[String], spaces: usize) -> Vec<String> {
    let prefix = " ".repeat(spaces);
    lines.iter().map(|line| format!("{prefix}{line}")).collect()
}

fn read_document(path: &Path) -> Result<Document> {
    let markdown = std::fs::read_to_string(path)
        .with_context(|| format!("Cannot read manuscript {}", path.display()))?;
    let document = parse_publication_document(&markdown)?;
    scalar_label(&document.metadata)?;
    Ok(document)
}

fn asset(id: String, role: &str, path: &Path, alt_text: &str) -> HtmlAsset {
    HtmlAsset {
        id,
        role: role.to_string(),
        path: path.to_path_buf(),
        src: file_uri(path),
        alt_text: alt_text.to_string(),
        ..HtmlAsset::default()
    }
}

fn figure_layouts(article: &Article) -> String {
    let mut layouts: Vec<&str> = Vec::new();
    for figure in &article.figures {
        let layout = py_strip(&figure.layout);
        if !layout.is_empty() && !layouts.contains(&layout) {
            layouts.push(layout);
        }
    }
    layouts.join(" ")
}

fn by_anchor<T>(rows: &[T], anchor: impl Fn(&T) -> &str) -> (Vec<&T>, BTreeMap<String, Vec<&T>>) {
    let mut opener = Vec::new();
    let mut anchored: BTreeMap<String, Vec<&T>> = BTreeMap::new();
    for row in rows {
        if anchor(row) == OPENER_ANCHOR {
            opener.push(row);
        } else {
            anchored
                .entry(anchor_key(anchor(row)))
                .or_default()
                .push(row);
        }
    }
    (opener, anchored)
}

struct Anchored<'a> {
    opener_figures: Vec<&'a Figure>,
    figures: BTreeMap<String, Vec<&'a Figure>>,
    opener_extracts: Vec<&'a Extract>,
    extracts: BTreeMap<String, Vec<&'a Extract>>,
}

impl<'a> Anchored<'a> {
    fn of(article: &'a Article) -> Self {
        let (opener_figures, figures) = by_anchor(&article.figures, |figure| &figure.anchor);
        let (opener_extracts, extracts) = by_anchor(&article.extracts, |extract| &extract.anchor);
        Self {
            opener_figures,
            figures,
            opener_extracts,
            extracts,
        }
    }
}

struct Renderer<'a> {
    edition: &'a Edition,
    settable: &'a BTreeSet<u32>,
    escape: Escaper<'a>,
}

impl Renderer<'_> {
    fn render(&self) -> Result<HtmlEdition> {
        let edition = self.edition;
        let mut assets = Vec::new();
        let mut body = vec![self.edition_header(), self.contents_nav()?];
        if let Some(editorial) = &edition.editorial {
            body.push(self.editorial(&read_document(&editorial.path)?, editorial)?);
        }
        for (index, article) in edition.articles.iter().enumerate() {
            let document = read_document(&article.manuscript)?;
            body.push(self.article(article, &document, index + 1, &mut assets)?);
        }
        for (index, section) in edition.sections.iter().enumerate() {
            body.push(self.section(index, section, &read_document(&section.path)?)?);
        }
        body.extend(self.closing_plates(&mut assets)?);
        if let Some(cover_art) = &edition.cover_art {
            let alt = raw_or(edition.cover.get("headline"), &edition.title);
            assets.push(asset("cover-art".to_string(), "cover_art", cover_art, &alt));
        }
        let title = format!("{}: {}", edition.publication_name, edition.title);
        let format_attribute = if article_opener_format(&edition.raw) == ILLUSTRATED {
            format!(" data-article-opener-format=\"{ILLUSTRATED}\"")
        } else {
            String::new()
        };
        let id = self.escape.attr(&edition.id);
        let mut lines = vec![
            "<!doctype html>".to_string(),
            format!(
                "<html lang=\"{}\" data-edition-id=\"{id}\"{format_attribute}>",
                self.escape.attr(&edition.locale)
            ),
            "<head>".to_string(),
            "  <meta charset=\"utf-8\">".to_string(),
            format!("  <title>{}</title>", self.escape.text(&title)),
            "</head>".to_string(),
            "<body>".to_string(),
            format!("  <main data-edition-id=\"{id}\">"),
        ];
        lines.extend(indent(&body, 4));
        lines.extend(["  </main>", "</body>", "</html>", ""].map(String::from));
        Ok(HtmlEdition {
            html: lines.join("\n"),
            assets,
        })
    }

    fn edition_header(&self) -> String {
        let edition = self.edition;
        let subtitle = py_strip(&raw_or(edition.raw.get("subtitle"), "")).to_string();
        let mut lines = vec![
            "<header class=\"edition-header\" data-edition-header=\"true\">".to_string(),
            format!(
                "  <p class=\"publication-name\">{}</p>",
                self.escape.text(&edition.publication_name)
            ),
            format!(
                "  <p class=\"issue-number\" data-issue-number=\"{}\">{} {}</p>",
                self.escape.attr(&edition.issue_number),
                self.escape.text(&ui(&self.edition.language, "issue")),
                self.escape.text(&edition.issue_number)
            ),
            format!("  <h1>{}</h1>", self.escape.text(&edition.title)),
        ];
        if !subtitle.is_empty() {
            lines.push(format!(
                "  <p class=\"subtitle\">{}</p>",
                self.escape.text(&subtitle)
            ));
        }
        lines.push(format!(
            "  <time datetime=\"{}\">{}</time>",
            self.escape.attr(&edition.publication_date),
            self.escape.text(&edition.publication_date)
        ));
        lines.push("</header>".to_string());
        lines.join("\n")
    }

    fn contents_entries(&self) -> Vec<[String; 4]> {
        let edition = self.edition;
        let mut entries: Vec<[String; 4]> = Vec::new();
        if let Some(editorial) = &edition.editorial {
            entries.push([
                "editorial".to_string(),
                ui(&self.edition.language, "editorial"),
                editorial.title.clone(),
                editorial.byline.clone(),
            ]);
        }
        for (index, article) in edition.articles.iter().enumerate() {
            entries.push([
                format!("article-{}", article.id),
                format!("{} {:02}", ui(&self.edition.language, "feature"), index + 1),
                article.title.clone(),
                article.author.clone(),
            ]);
        }
        for (index, section) in edition.sections.iter().enumerate() {
            entries.push([
                format!("section-{index}"),
                ui(&self.edition.language, &section.kind),
                section.title.clone(),
                String::new(),
            ]);
        }
        for entry in &mut entries {
            entry[3] = clamp_roster(&entry[3]);
        }
        entries
    }

    fn contents_nav(&self) -> Result<String> {
        let label = ui(&self.edition.language, "contents");
        let kicker = format!(
            "{} {} / {label}",
            ui(&self.edition.language, "issue"),
            self.edition.issue_number
        );
        let entries = self.contents_entries();
        for [_, _, title, _] in &entries {
            let length = title.chars().count();
            if length > CONTENTS_TITLE_LIMIT {
                bail!(
                    "Contents title {} ({length} characters) would wrap onto the entry's author \
                     line; shorten the article title to 62 characters or fewer.",
                    py_repr(title)
                );
            }
        }
        let density = if entries.len() > 8 {
            " data-contents-density=\"tight\""
        } else {
            ""
        };
        let mut lines = vec![
            format!(
                "<nav aria-label=\"{}\" data-edition-navigation=\"contents\"{density}>",
                self.escape.attr(&label)
            ),
            format!(
                "  <p class=\"contents-kicker\">{}</p>",
                self.escape.text(&kicker)
            ),
            format!("  <h2>{}</h2>", self.escape.text(&label)),
            "  <ol>".to_string(),
        ];
        for [destination, entry_label, title, author] in &entries {
            let author = if author.is_empty() {
                String::new()
            } else {
                format!(
                    "<span class=\"entry-author\">{}</span>",
                    self.escape.text(author)
                )
            };
            let href = self.escape.attr(destination);
            lines.push(format!(
                "    <li><span class=\"entry-label\">{}</span><a class=\"entry-folio\" \
                 href=\"#{href}\" aria-hidden=\"true\"></a><a class=\"entry-title\" \
                 href=\"#{href}\">{}</a>{author}</li>",
                self.escape.text(entry_label),
                self.escape.text(title)
            ));
        }
        lines.extend(["  </ol>", "</nav>"].map(String::from));
        Ok(lines.join("\n"))
    }

    fn byline(&self, author: &str) -> String {
        format!(
            "<p class=\"byline\" data-byline=\"true\"><span class=\"byline-prefix\">{}</span> {}</p>",
            self.escape.text(&ui(&self.edition.language, "by")),
            self.escape.text(author)
        )
    }

    fn editorial(&self, document: &Document, editorial: &Editorial) -> Result<String> {
        let mut lines = vec![
            format!(
                "<section id=\"editorial\" class=\"editorial\" data-section-kind=\"original_editorial\" \
                 data-short-title=\"{}\">",
                self.escape.attr(&ui(&self.edition.language, "editorial"))
            ),
            "  <header>".to_string(),
            format!(
                "    <p class=\"content-label\" data-content-mode=\"original_editorial\">\
                 <span class=\"label-primary\">{}</span></p>",
                self.escape.text(&editorial.label)
            ),
            format!("    <h1>{}</h1>", self.escape.text(&editorial.title)),
            format!("    {}", self.byline(&editorial.byline)),
            "  </header>".to_string(),
        ];
        lines.extend(indent(&self.standfirst_blocks(&document.blocks)?, 2));
        lines.push("</section>".to_string());
        Ok(lines.join("\n"))
    }

    fn section(&self, index: usize, section: &Section, document: &Document) -> Result<String> {
        let kind = self.escape.attr(&section.kind);
        let mut lines = vec![
            format!(
                "<section id=\"section-{index}\" data-section-kind=\"{kind}\" data-short-title=\"{}\">",
                self.escape.attr(&section.title)
            ),
            "  <header>".to_string(),
            format!(
                "    <p class=\"content-label\" data-content-mode=\"{kind}\">\
                 <span class=\"label-primary\">{}</span></p>",
                self.escape.text(&ui(&self.edition.language, &section.kind))
            ),
            format!("    <h1>{}</h1>", self.escape.text(&section.title)),
            "  </header>".to_string(),
        ];
        lines.extend(indent(&self.standfirst_blocks(&document.blocks)?, 2));
        lines.push("</section>".to_string());
        Ok(lines.join("\n"))
    }

    fn standfirst_blocks(&self, blocks: &[Block]) -> Result<Vec<String>> {
        blocks
            .iter()
            .enumerate()
            .map(|(index, block)| self.block(block, index == 0, false))
            .collect()
    }

    fn article_opening(&self, article: &Article, illustrated: bool) -> String {
        format!(
            "<article id=\"{}\" data-article-id=\"{}\" data-content-mode=\"{}\" \
             data-source-ids=\"{}\" data-figure-layouts=\"{}\" data-short-title=\"{}\"{}>",
            self.escape.attr(&format!("article-{}", article.id)),
            self.escape.attr(&article.id),
            self.escape.attr(&article.content_mode),
            self.escape.attr(&article.source_ids.join(" ")),
            self.escape.attr(&figure_layouts(article)),
            self.escape.attr(&article.short_title),
            if illustrated {
                format!(" data-article-opener=\"{ILLUSTRATED}\"")
            } else {
                String::new()
            }
        )
    }

    fn content_label_line(
        &self,
        article: &Article,
        document: &Document,
        index: usize,
        separated: bool,
    ) -> String {
        let separator = "<span class=\"label-separator\" aria-hidden=\"true\"> / </span>";
        let date = article
            .dateline
            .as_deref()
            .filter(|dateline| !dateline.is_empty())
            .map(|dateline| {
                format!(
                    "{separator}<span class=\"label-date\">{}</span>",
                    self.escape.text(dateline)
                )
            })
            .unwrap_or_default();
        format!(
            "<p class=\"content-label\" data-content-mode=\"{}\"><span class=\"label-primary\">{} {index:02}</span>{}\
             <span class=\"label-secondary\">{}</span>{date}</p>",
            self.escape.attr(&article.content_mode),
            self.escape.text(&ui(&self.edition.language, "feature")),
            if separated { separator } else { "" },
            self.escape.text(&content_label(
                &self.edition.language,
                &document.metadata,
                &article.content_mode
            ))
        )
    }

    fn article_header_lines(
        &self,
        article: &Article,
        document: &Document,
        index: usize,
    ) -> Vec<String> {
        let mut lines = vec![
            self.article_opening(article, false),
            "  <header>".to_string(),
            format!(
                "    {}",
                self.content_label_line(article, document, index, false)
            ),
            format!("    <h1>{}</h1>", self.escape.text(&article.title)),
            format!("    {}", self.byline(&article.author)),
        ];
        if !article.author_note.is_empty() {
            lines.push(format!(
                "    <p class=\"author-note\">{}</p>",
                self.escape.text(&article.author_note)
            ));
        }
        let sources: Vec<String> = article
            .source_ids
            .iter()
            .map(|id| {
                format!(
                    "<span data-source-id=\"{}\">{}</span>",
                    self.escape.attr(id),
                    self.escape.text(id)
                )
            })
            .collect();
        lines.push(format!(
            "    <p class=\"provenance\" data-provenance=\"source-ids\">{}: {}</p>",
            self.escape.text(&ui(&self.edition.language, "sources")),
            sources.join(", ")
        ));
        lines.push("  </header>".to_string());
        lines
    }

    fn article(
        &self,
        article: &Article,
        document: &Document,
        index: usize,
        assets: &mut Vec<HtmlAsset>,
    ) -> Result<String> {
        let anchored = Anchored::of(article);
        let illustrated = article_opener_format(&self.edition.raw) == ILLUSTRATED;
        let (mut lines, rest) = match (&article.opener_art, illustrated) {
            (Some(_), true) => (
                self.illustrated_header(article, document, index, assets)?,
                document.blocks.get(1..).unwrap_or_default(),
            ),
            _ => (
                self.article_header_lines(article, document, index),
                &document.blocks[..],
            ),
        };
        let standfirst_first = !(article.opener_art.is_some() && illustrated);
        self.opener_rows(article, &anchored, &mut lines, assets);
        let mut references = false;
        for (position, block) in rest.iter().enumerate() {
            let heading = match block {
                Block::Heading { children, .. } => Some(inline_text(children)),
                _ => None,
            };
            if let Some(heading) = &heading {
                references = is_reference_heading(heading);
            }
            let standfirst = standfirst_first && position == 0;
            lines.push(format!("  {}", self.block(block, standfirst, references)?));
            if let Some(heading) = heading {
                self.anchored_rows(
                    article,
                    &anchored,
                    &anchor_key(&heading),
                    &mut lines,
                    assets,
                );
            }
        }
        self.article_tail(article, index, &mut lines, assets);
        if standfirst_first {
            lines.extend(indent(&self.source_link(article), 2));
        }
        lines.push("</article>".to_string());
        Ok(lines.join("\n"))
    }

    fn opener_rows(
        &self,
        article: &Article,
        anchored: &Anchored,
        lines: &mut Vec<String>,
        assets: &mut Vec<HtmlAsset>,
    ) {
        for figure in &anchored.opener_figures {
            lines.push(format!("  {}", self.figure(article, figure, assets)));
        }
        for extract in &anchored.opener_extracts {
            lines.push(format!("  {}", self.extract(article, extract)));
        }
    }

    fn anchored_rows(
        &self,
        article: &Article,
        anchored: &Anchored,
        key: &str,
        lines: &mut Vec<String>,
        assets: &mut Vec<HtmlAsset>,
    ) {
        for figure in anchored.figures.get(key).into_iter().flatten() {
            lines.push(format!("  {}", self.figure(article, figure, assets)));
        }
        for extract in anchored.extracts.get(key).into_iter().flatten() {
            lines.push(format!("  {}", self.extract(article, extract)));
        }
    }

    fn article_tail(
        &self,
        article: &Article,
        index: usize,
        lines: &mut Vec<String>,
        assets: &mut Vec<HtmlAsset>,
    ) {
        lines.extend(indent(&self.key_ideas(article), 2));
        lines.push(format!(
            "  <p class=\"end-mark\" data-end-mark=\"true\">{} / {index:02}</p>",
            self.escape.text(&ui(&self.edition.language, "end"))
        ));
        let Some(tail) = &article.tail_art else {
            return;
        };
        let fit = raw_or(self.edition.raw.get("tail_art_fit"), "cover");
        let mut tail_asset = asset(
            format!("article-tail-{}", article.id),
            "article_tail",
            tail,
            &format!("Tail art for {}", article.title),
        );
        tail_asset.article_id = Some(article.id.clone());
        lines.push(format!(
            "  <figure class=\"article-tail\" data-asset-role=\"article_tail\" data-fit=\"{}\">\
             <img src=\"{}\" alt=\"{}\"></figure>",
            self.escape.attr(&fit),
            self.escape.attr(&tail_asset.src),
            self.escape.attr(&tail_asset.alt_text)
        ));
        assets.push(tail_asset);
    }

    fn illustrated_header(
        &self,
        article: &Article,
        document: &Document,
        index: usize,
        assets: &mut Vec<HtmlAsset>,
    ) -> Result<Vec<String>> {
        let Some(first @ Block::Paragraph(_)) = document.blocks.first() else {
            bail!("{ILLUSTRATED} requires a paragraph as the first manuscript block");
        };
        let Some(opener) = &article.opener_art else {
            bail!("{ILLUSTRATED} requires article opener art");
        };
        let mut art = asset(
            format!("article-opener-{}", article.id),
            "article_opener",
            &opener.path,
            &opener.alt_text,
        );
        art.article_id = Some(article.id.clone());
        art.credit = Some(opener.credit.clone());
        let mut lines = vec![
            self.article_opening(article, true),
            format!(
                "  <header class=\"article-opener\" data-article-id=\"{}\">",
                self.escape.attr(&article.id)
            ),
            "    <figure class=\"article-opener-art\" data-asset-role=\"article_opener\">"
                .to_string(),
            "      <span class=\"article-opener-art-offset\" aria-hidden=\"true\"></span>"
                .to_string(),
            format!(
                "      <img src=\"{}\" alt=\"{}\">",
                self.escape.attr(&art.src),
                self.escape.attr(&art.alt_text)
            ),
            "    </figure>".to_string(),
            format!(
                "    {}",
                self.content_label_line(article, document, index, true)
            ),
            format!("    <h1>{}</h1>", self.escape.text(&article.title)),
            "    <span class=\"opener-tick\" aria-hidden=\"true\"></span>".to_string(),
            "    <div class=\"opener-meta\">".to_string(),
            "      <div class=\"opener-credit\">".to_string(),
            format!("        {}", self.byline(&article.author)),
        ];
        assets.push(art);
        if !article.author_note.is_empty() {
            lines.push(format!(
                "        <p class=\"author-note\">{}</p>",
                self.escape.text(&article.author_note)
            ));
        }
        lines.push("      </div>".to_string());
        lines.extend(indent(&self.source_link(article), 6));
        lines.push("    </div>".to_string());
        lines.push(format!("    {}", self.block(first, true, false)?));
        lines.push("  </header>".to_string());
        Ok(lines)
    }

    fn key_ideas(&self, article: &Article) -> Vec<String> {
        if article.key_ideas.is_empty() {
            return Vec::new();
        }
        let items: String = article
            .key_ideas
            .iter()
            .map(|idea| format!("<li>{}</li>", self.escape.text(idea)))
            .collect();
        vec![format!(
            "<aside class=\"key-ideas\" data-key-ideas=\"{}\" data-article-id=\"{}\">\
             <p class=\"key-ideas-label\">{}</p><ul>{items}</ul></aside>",
            article.key_ideas.len(),
            self.escape.attr(&article.id),
            self.escape.text(&ui(&self.edition.language, "key_ideas"))
        )]
    }

    fn source_link(&self, article: &Article) -> Vec<String> {
        let Some(url) = article.source_url.as_deref().filter(|url| !url.is_empty()) else {
            return Vec::new();
        };
        vec![format!(
            "<a class=\"source-link\" data-source-link=\"primary\" data-source-id=\"{}\" href=\"{}\">{}</a>",
            self.escape.attr(article.source_ids.first().map_or("", String::as_str)),
            self.escape.attr(url),
            self.escape.verbatim(url)
        )]
    }

    fn closing_plates(&self, assets: &mut Vec<HtmlAsset>) -> Result<Vec<String>> {
        let mut plates = Vec::new();
        for (position, plate) in self.edition.closing_plates.iter().enumerate() {
            let index = position + 1;
            let path = &plate.art_path;
            let aspect = match crate::typeset::media::pixels(path) {
                Ok((width, height)) => f64::from(width) / f64::from(height),
                Err(_) => bail!(
                    "Closing plate {index} needs a readable raster source: {}",
                    path.display()
                ),
            };
            if !(PLATE_WINDOW_ASPECT / 2.0..=PLATE_WINDOW_ASPECT * 2.0).contains(&aspect) {
                bail!(
                    "Closing plate {index} art {} has aspect {aspect:.2}; contained in the \
                     {PLATE_WINDOW_ASPECT:.2} plate window it would print as a sliver. Use art \
                     nearer the window's shape.",
                    path.display()
                );
            }
            let plate_asset = asset(
                format!("closing-plate-{index}"),
                "closing_plate",
                path,
                &plate.title,
            );
            plates.push(format!(
                "<figure class=\"closing-plate\" data-asset-role=\"closing_plate\" \
                 data-closing-plate=\"{index}\"><img src=\"{}\" alt=\"{}\"></figure>",
                self.escape.attr(&plate_asset.src),
                self.escape.attr(&plate.title)
            ));
            assets.push(plate_asset);
        }
        Ok(plates)
    }

    fn figure(&self, article: &Article, figure: &Figure, assets: &mut Vec<HtmlAsset>) -> String {
        let mut figure_asset = asset(
            format!("figure-{}-{}", article.id, figure.id),
            "figure",
            &figure.path,
            &figure.alt_text,
        );
        figure_asset.article_id = Some(article.id.clone());
        figure_asset.figure_id = Some(figure.id.clone());
        figure_asset.source_id = Some(figure.source_id.clone());
        figure_asset.caption = Some(figure.caption.clone());
        figure_asset.credit = Some(figure.credit.clone());
        figure_asset.anchor = Some(figure.anchor.clone());
        figure_asset.layout = Some(figure.layout.clone());
        let html = format!(
            "<figure data-figure-id=\"{}\" data-article-id=\"{}\" data-source-id=\"{}\" \
             data-anchor=\"{}\" data-layout=\"{}\" data-figure-label=\"{}\"><img src=\"{}\" \
             alt=\"{}\"><figcaption><span class=\"caption\">{}</span></figcaption></figure>",
            self.escape.attr(&figure.id),
            self.escape.attr(&article.id),
            self.escape.attr(&figure.source_id),
            self.escape.attr(&figure.anchor),
            self.escape.attr(&figure.layout),
            self.escape.attr(&ui(&self.edition.language, "figure")),
            self.escape.attr(&figure_asset.src),
            self.escape.attr(&figure.alt_text),
            self.escape.text(&figure.caption)
        );
        assets.push(figure_asset);
        html
    }

    fn extract(&self, article: &Article, extract: &Extract) -> String {
        let body = if extract.style == "code" {
            let lines: Vec<String> = extract
                .text
                .split('\n')
                .map(|line| self.escape.verbatim(line))
                .collect();
            format!("<pre><code>{}</code></pre>", lines.join("<br>"))
        } else {
            let paragraphs: String = extract
                .text
                .split("\n\n")
                .map(py_strip)
                .filter(|paragraph| !paragraph.is_empty())
                .map(|paragraph| format!("<p>{}</p>", self.escape.verbatim(paragraph)))
                .collect();
            format!("<blockquote>{paragraphs}</blockquote>")
        };
        format!(
            "<aside class=\"extract\" data-extract-id=\"{}\" data-article-id=\"{}\" \
             data-source-id=\"{}\" data-anchor=\"{}\" data-style=\"{}\" data-extract-label=\"{}\">\
             {body}<p class=\"extract-caption\">{}</p></aside>",
            self.escape.attr(&extract.id),
            self.escape.attr(&article.id),
            self.escape.attr(&extract.source_id),
            self.escape.attr(&extract.anchor),
            self.escape.attr(&extract.style),
            self.escape.attr(&ui(&self.edition.language, "verbatim")),
            self.escape.text(&extract.caption)
        )
    }

    fn block(&self, block: &Block, standfirst: bool, references: bool) -> Result<String> {
        Ok(match block {
            Block::Heading { level, children } => {
                format!("<h{level}>{}</h{level}>", self.inline_html(children))
            }
            Block::Paragraph(children) => {
                let class = if standfirst {
                    " class=\"standfirst\""
                } else {
                    ""
                };
                let roster = if is_name_roster(&inline_text(children)) {
                    " data-name-roster=\"true\""
                } else {
                    ""
                };
                format!("<p{class}{roster}>{}</p>", self.inline_html(children))
            }
            Block::FencedCode { code, info } => self.fenced_code(code, info)?,
            Block::Quote(children) => {
                let inner = self.children(children)?;
                format!("<blockquote>{inner}</blockquote>")
            }
            Block::List {
                ordered,
                start,
                items,
            } => {
                let tag = if *ordered { "ol" } else { "ul" };
                let start = if *ordered && *start != 1 {
                    format!(" start=\"{start}\"")
                } else {
                    String::new()
                };
                let role = if references {
                    " data-reference-list=\"true\""
                } else {
                    ""
                };
                let items = items
                    .iter()
                    .map(|item| Ok(format!("<li>{}</li>", self.children(item)?)))
                    .collect::<Result<String>>()?;
                format!("<{tag}{start}{role}>{items}</{tag}>")
            }
            Block::HorizontalRule => "<hr>".to_string(),
        })
    }

    fn children(&self, blocks: &[Block]) -> Result<String> {
        blocks
            .iter()
            .map(|child| self.block(child, false, false))
            .collect()
    }

    fn fenced_code(&self, code: &str, info: &str) -> Result<String> {
        let language = info
            .split(char::is_whitespace)
            .find(|word| !word.is_empty())
            .unwrap_or("");
        let class = if language.is_empty() {
            String::new()
        } else {
            format!(" class=\"language-{}\"", self.escape.attr(language))
        };
        let folded = fold_reader_characters(code, self.settable);
        let body = crate::highlight::html(&folded, language)?;
        Ok(format!("<pre><code{class}>{body}</code></pre>"))
    }

    fn inline_html(&self, inlines: &[Inline]) -> String {
        inlines
            .iter()
            .map(|inline| match inline {
                Inline::Text(value) => self.escape.text(value),
                Inline::Emphasis(children) => format!("<em>{}</em>", self.inline_html(children)),
                Inline::Strong(children) => {
                    format!("<strong>{}</strong>", self.inline_html(children))
                }
                Inline::Code(value) => format!("<code>{}</code>", self.escape.verbatim(value)),
                Inline::Link {
                    destination,
                    title,
                    children,
                } => {
                    let title = title
                        .as_deref()
                        .map(|title| format!(" title=\"{}\"", self.escape.attr(title)))
                        .unwrap_or_default();
                    format!(
                        "<a href=\"{}\"{title}>{}</a>",
                        self.escape.attr(destination),
                        self.inline_html(children)
                    )
                }
                Inline::LineBreak { hard: true } => "<br>".to_string(),
                Inline::LineBreak { hard: false } => "\n".to_string(),
            })
            .collect()
    }
}
