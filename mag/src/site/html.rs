use super::images::Image;
use super::{Issue, SiteConfig};
use crate::model::doc::{
    educate_reader_quotes, inline_text, parse_publication_document, Block, Document, Inline,
};
use crate::model::manifest::{Article, Edition};
use crate::model::records::{Extract, Figure};
use crate::model::shared::{anchor_key, content_label, ui};
use anyhow::{Context, Result};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const OPENER: &str = "__opener__";
const BODY_SIZES: &str = "(min-width: 44rem) 40rem, calc(100vw - 2.5rem)";
const WIDE_SIZES: &str = "(min-width: 44rem) 40rem, 100vw";
const COVER_SIZES: &str = "(min-width: 52rem) 24rem, 80vw";

type Images = BTreeMap<PathBuf, Image>;

fn esc(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn prose(value: &str) -> String {
    esc(&educate_reader_quotes(value))
}

fn say(language: &str, key: &str) -> &'static str {
    let spanish = language == "es";
    match key {
        "read" if spanish => "Leer el número",
        "read" => "Read the issue",
        "issues" if spanish => "Números",
        "issues" => "Issues",
        "pdf" if spanish => "Descargar el PDF",
        "pdf" => "Download the PDF",
        "original" if spanish => "Leer el original",
        "original" => "Read the original",
        "next" if spanish => "Siguiente",
        "next" => "Next",
        "previous" if spanish => "Anterior",
        "previous" => "Previous",
        "lost" if spanish => "Esta página no existe.",
        "lost" => "This page does not exist.",
        "home" if spanish => "Volver a la portada",
        "home" => "Back to the front page",
        "name" if spanish => "Español",
        _ => "English",
    }
}

fn date(language: &str, iso: &str) -> String {
    const EN: [&str; 12] = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ];
    const ES: [&str; 12] = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ];
    let parts: Vec<usize> = iso.split('-').filter_map(|p| p.parse().ok()).collect();
    let [year, month @ 1..=12, day] = parts[..] else {
        return iso.to_string();
    };
    match language {
        "es" => format!("{day} de {} de {year}", ES[month - 1]),
        _ => format!("{day} {} {year}", EN[month - 1]),
    }
}

fn megabytes(bytes: u64) -> String {
    format!("{:.1} MB", bytes as f64 / 1_000_000.0)
}

pub struct Piece<'a> {
    pub slug: String,
    pub kicker: String,
    pub title: String,
    pub author: String,
    pub article: Option<&'a Article>,
    pub document: Document,
}

fn read(path: &Path) -> Result<Document> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("reading manuscript {}", path.display()))?;
    parse_publication_document(&text)
}

pub fn pieces(edition: &Edition) -> Result<Vec<Piece<'_>>> {
    let language = &edition.language;
    let mut out = Vec::new();
    if let Some(editorial) = &edition.editorial {
        out.push(Piece {
            slug: "editorial".to_string(),
            kicker: editorial.label.clone(),
            title: editorial.title.clone(),
            author: editorial.byline.clone(),
            article: None,
            document: read(&editorial.path)?,
        });
    }
    for (index, article) in edition.articles.iter().enumerate() {
        let document = read(&article.manuscript)?;
        let label = content_label(language, &document.metadata, &article.content_mode);
        out.push(Piece {
            slug: article.id.clone(),
            kicker: format!("{} {:02} · {label}", ui(language, "feature"), index + 1),
            title: article.title.clone(),
            author: article.author.clone(),
            article: Some(article),
            document,
        });
    }
    for (index, section) in edition.sections.iter().enumerate() {
        out.push(Piece {
            slug: format!("section-{}", index + 1),
            kicker: ui(language, &section.kind),
            title: section.title.clone(),
            author: String::new(),
            article: None,
            document: read(&section.path)?,
        });
    }
    Ok(out)
}

pub fn art_paths(edition: &Edition) -> Vec<PathBuf> {
    let art = edition.articles.iter().flat_map(|article| {
        let figures = article.figures.iter().map(|f| f.path.clone());
        let opener = article.opener_art.iter().map(|o| o.path.clone());
        opener.chain(article.tail_art.clone()).chain(figures)
    });
    edition.cover_art.clone().into_iter().chain(art).collect()
}

pub fn image_paths(issues: &[Issue]) -> Vec<PathBuf> {
    let mut paths: Vec<PathBuf> = issues
        .iter()
        .flat_map(|issue| &issue.editions)
        .flat_map(art_paths)
        .collect();
    paths.sort();
    paths.dedup();
    paths
}

struct Ctx<'a> {
    root: String,
    images: &'a Images,
    epub: bool,
}

impl Ctx<'_> {
    fn picture(&self, path: &Path, alt: &str, sizes: &str, eager: bool) -> String {
        let image = &self.images[path];
        if self.epub {
            return format!(
                "<img src=\"{}{}\" width=\"{}\" height=\"{}\" alt=\"{}\"/>",
                self.root,
                image.src(),
                image.width,
                image.height,
                esc(alt)
            );
        }
        let srcset: Vec<String> = image
            .variants
            .iter()
            .map(|(name, width)| format!("{}{name} {width}w", self.root))
            .collect();
        let loading = match eager {
            true => "fetchpriority=\"high\"",
            false => "loading=\"lazy\"",
        };
        format!(
            "<img src=\"{}{}\" srcset=\"{}\" sizes=\"{sizes}\" width=\"{}\" height=\"{}\" alt=\"{}\" {loading} decoding=\"async\">",
            self.root,
            image.src(),
            srcset.join(", "),
            image.width,
            image.height,
            esc(alt)
        )
    }

    fn zoomable(&self, path: &Path, alt: &str, sizes: &str) -> String {
        if self.epub {
            return self.picture(path, alt, sizes, false);
        }
        format!(
            "<a class=\"zoom\" href=\"{}{}\">{}</a>",
            self.root,
            self.images[path].full(),
            self.picture(path, alt, sizes, false)
        )
    }

    fn figure(&self, figure: &Figure) -> String {
        let credit = match figure.credit.trim() {
            "" => String::new(),
            credit => format!(" <span class=\"credit\">{}</span>", prose(credit)),
        };
        format!(
            "<figure class=\"figure\" id=\"figure-{}\">{}<figcaption>{}{credit}</figcaption></figure>",
            esc(&figure.id),
            self.zoomable(&figure.path, &figure.alt_text, BODY_SIZES),
            prose(&figure.caption)
        )
    }

    fn extract(&self, language: &str, extract: &Extract) -> String {
        let body = match extract.style.as_str() {
            "code" => format!("<pre><code>{}</code></pre>", esc(&extract.text)),
            _ => format!(
                "<blockquote>{}</blockquote>",
                extract
                    .text
                    .split("\n\n")
                    .map(str::trim)
                    .filter(|p| !p.is_empty())
                    .map(|p| format!("<p>{}</p>", esc(p)))
                    .collect::<String>()
            ),
        };
        format!(
            "<figure class=\"extract\" id=\"extract-{}\"><p class=\"extract-label\">{}</p>{body}<figcaption>{}</figcaption></figure>",
            esc(&extract.id),
            esc(&ui(language, "verbatim")),
            prose(&extract.caption)
        )
    }
}

fn inline(inlines: &[Inline]) -> String {
    inlines
        .iter()
        .map(|item| match item {
            Inline::Text(value) => prose(value),
            Inline::Emphasis(children) => format!("<em>{}</em>", inline(children)),
            Inline::Strong(children) => format!("<strong>{}</strong>", inline(children)),
            Inline::Code(value) => format!("<code>{}</code>", esc(value)),
            Inline::Link {
                destination,
                title,
                children,
            } => format!(
                "<a href=\"{}\"{}>{}</a>",
                esc(destination),
                title
                    .as_deref()
                    .map(|t| format!(" title=\"{}\"", esc(t)))
                    .unwrap_or_default(),
                inline(children)
            ),
            Inline::LineBreak { hard: true } => "<br>".to_string(),
            Inline::LineBreak { hard: false } => "\n".to_string(),
        })
        .collect()
}

fn code(code: &str, info: &str) -> Result<String> {
    let language = info.split_whitespace().next().unwrap_or("");
    let class = match language {
        "" => String::new(),
        language => format!(" class=\"language-{}\"", esc(language)),
    };
    let tail = &code[code.trim_end_matches('\n').len()..];
    Ok(format!(
        "<pre><code{class}>{}{tail}</code></pre>",
        crate::highlight::html(code, crate::highlight::language(code, language))?
    ))
}

fn block(item: &Block, standfirst: bool) -> Result<String> {
    Ok(match item {
        Block::Heading { level, children } => {
            let level = (*level).clamp(2, 6);
            format!("<h{level}>{}</h{level}>", inline(children))
        }
        Block::Paragraph(children) if standfirst => {
            format!("<p class=\"standfirst\">{}</p>", inline(children))
        }
        Block::Paragraph(children) => format!("<p>{}</p>", inline(children)),
        Block::FencedCode { code: text, info } => code(text, info)?,
        Block::Quote(children) => format!("<blockquote>{}</blockquote>", blocks(children)?),
        Block::List {
            ordered,
            start,
            items,
        } => {
            let (tag, start) = match (*ordered, *start) {
                (false, _) => ("ul", String::new()),
                (true, 1) => ("ol", String::new()),
                (true, n) => ("ol", format!(" start=\"{n}\"")),
            };
            let items = items
                .iter()
                .map(|item| Ok(format!("<li>{}</li>", blocks(item)?)))
                .collect::<Result<String>>()?;
            format!("<{tag}{start}>{items}</{tag}>")
        }
        Block::HorizontalRule => "<hr>".to_string(),
        Block::Table(rows) => table(rows),
    })
}

fn table(rows: &[Vec<Vec<Inline>>]) -> String {
    let row = |cells: &Vec<Vec<Inline>>, tag: &str| {
        let cells: String = cells
            .iter()
            .map(|cell| format!("<{tag}>{}</{tag}>", inline(cell)))
            .collect();
        format!("<tr>{cells}</tr>")
    };
    let (head, body) = rows
        .split_first()
        .map_or((String::new(), &[][..]), |(head, body)| {
            (row(head, "th"), body)
        });
    let body: String = body.iter().map(|cells| row(cells, "td")).collect();
    format!("<table><thead>{head}</thead><tbody>{body}</tbody></table>")
}

fn blocks(items: &[Block]) -> Result<String> {
    items.iter().map(|item| block(item, false)).collect()
}

fn anchored(ctx: &Ctx, language: &str, article: Option<&Article>, key: &str) -> String {
    let Some(article) = article else {
        return String::new();
    };
    let figures = article
        .figures
        .iter()
        .filter(|f| anchor_key(&f.anchor) == key)
        .map(|f| ctx.figure(f));
    let extracts = article
        .extracts
        .iter()
        .filter(|e| anchor_key(&e.anchor) == key)
        .map(|e| ctx.extract(language, e));
    figures.chain(extracts).collect::<Vec<_>>().join("\n")
}

fn body(ctx: &Ctx, language: &str, piece: &Piece) -> Result<String> {
    let mut out = vec![anchored(ctx, language, piece.article, &anchor_key(OPENER))];
    for (index, item) in piece.document.blocks.iter().enumerate() {
        out.push(block(item, index == 0)?);
        if let Block::Heading { children, .. } = item {
            let key = anchor_key(&inline_text(children));
            out.push(anchored(ctx, language, piece.article, &key));
        }
    }
    Ok(out
        .into_iter()
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join("\n"))
}

fn markup_free(html: &str) -> String {
    regex::Regex::new("<[^>]*>")
        .expect("a fixed pattern")
        .replace_all(html, "")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&amp;", "&")
}

fn squash(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn reader_text(inlines: &[Inline]) -> String {
    inlines
        .iter()
        .map(|item| match item {
            Inline::Text(value) => educate_reader_quotes(value),
            Inline::Code(value) => value.clone(),
            Inline::Emphasis(children) | Inline::Strong(children) => reader_text(children),
            Inline::Link { children, .. } => reader_text(children),
            Inline::LineBreak { .. } => " ".to_string(),
        })
        .collect()
}

fn expected(item: &Block, out: &mut Vec<(String, bool)>) {
    match item {
        Block::Heading { children, .. } | Block::Paragraph(children) => {
            out.push((reader_text(children), false));
        }
        Block::FencedCode { code, .. } => out.push((code.clone(), true)),
        Block::Quote(children) => children.iter().for_each(|c| expected(c, out)),
        Block::List { items, .. } => items.iter().flatten().for_each(|c| expected(c, out)),
        Block::HorizontalRule => {}
        Block::Table(rows) => rows
            .iter()
            .flatten()
            .for_each(|cell| out.push((reader_text(cell), false))),
    }
}

pub fn dropped(piece: &Piece, html: &str) -> Vec<String> {
    let text = markup_free(html);
    let flat = squash(&text);
    let mut want = Vec::new();
    piece
        .document
        .blocks
        .iter()
        .for_each(|b| expected(b, &mut want));
    for figure in piece.article.iter().flat_map(|a| &a.figures) {
        want.push((educate_reader_quotes(&figure.caption), false));
        if !html.contains(&format!("id=\"figure-{}\"", esc(&figure.id)))
            || !html.contains(&format!("alt=\"{}\"", esc(&figure.alt_text)))
        {
            want.push((format!("figure {}", figure.id), true));
        }
    }
    for extract in piece.article.iter().flat_map(|a| &a.extracts) {
        let verbatim = extract.style == "code";
        want.push((extract.text.clone(), verbatim));
        want.push((educate_reader_quotes(&extract.caption), false));
    }
    want.into_iter()
        .filter(|(fragment, verbatim)| match verbatim {
            true => !text.contains(fragment.as_str()),
            false => !flat.contains(&squash(fragment)),
        })
        .map(|(fragment, _)| fragment)
        .collect()
}

pub struct Page {
    pub path: String,
    pub language: String,
    pub title: String,
    pub description: String,
    pub image: Option<String>,
    pub alternate: Option<(String, String)>,
    pub crumb: String,
    pub body: String,
}

fn depth_root(path: &str) -> String {
    "../".repeat(path.matches('/').count())
}

fn document(page: &Page, site: &SiteConfig, (name, logo): (&str, &str), root: &str) -> String {
    let base = site.base_url.trim_end_matches('/');
    let url = format!("{base}/{}", page.path);
    let mut head = vec![
        format!("<title>{}</title>", esc(&page.title)),
        format!(
            "<meta name=\"description\" content=\"{}\">",
            esc(&page.description)
        ),
        format!("<link rel=\"canonical\" href=\"{url}\">"),
        format!("<meta property=\"og:site_name\" content=\"{}\">", esc(name)),
        format!(
            "<meta property=\"og:title\" content=\"{}\">",
            esc(&page.title)
        ),
        format!(
            "<meta property=\"og:description\" content=\"{}\">",
            esc(&page.description)
        ),
        format!("<meta property=\"og:url\" content=\"{url}\">"),
        "<meta property=\"og:type\" content=\"article\">".to_string(),
    ];
    let image = page.image.as_deref().unwrap_or("og.png");
    head.push(format!(
        "<meta property=\"og:image\" content=\"{base}/{image}\">"
    ));
    head.push("<meta name=\"twitter:card\" content=\"summary_large_image\">".to_string());
    let mut switch = String::new();
    if let Some((language, path)) = &page.alternate {
        head.push(format!(
            "<link rel=\"alternate\" hreflang=\"{language}\" href=\"{base}/{path}\">"
        ));
        switch = format!(
            "<a class=\"switch\" hreflang=\"{language}\" lang=\"{language}\" href=\"{root}{path}\">{}</a>",
            say(language, "name")
        );
    }
    let home = match format!("{root}{}", prefix(&page.language)) {
        home if home.is_empty() => "./".to_string(),
        home => home,
    };
    format!(
        "<!doctype html>\n<html lang=\"{lang}\">\n<head>\n<meta charset=\"utf-8\">\n\
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\
<meta name=\"color-scheme\" content=\"light dark\">\n{head}\n\
<link rel=\"icon\" href=\"{root}favicon.svg\" type=\"image/svg+xml\">\n\
<link rel=\"apple-touch-icon\" href=\"{root}apple-touch-icon.png\">\n\
<link rel=\"preload\" href=\"{root}fonts/SourceSerif4SmText-Regular.ttf\" as=\"font\" type=\"font/ttf\" crossorigin>\n\
<link rel=\"stylesheet\" href=\"{root}site.css\">\n</head>\n<body>\n\
<header class=\"masthead\"><a class=\"brand\" href=\"{home}\">{logo}</a>{crumb}{switch}</header>\n\
<main>\n{body}\n</main>\n\
<footer class=\"colophon\"><a href=\"{home}\">{name}</a></footer>\n</body>\n</html>\n",
        lang = esc(&page.language),
        head = head.join("\n"),
        name = esc(name),
        crumb = page.crumb,
        body = page.body,
    )
}

fn prefix(language: &str) -> String {
    match language {
        "en" => String::new(),
        other => format!("{other}/"),
    }
}

fn summary(document: &Document, fallback: &str) -> String {
    let text = document
        .blocks
        .iter()
        .find_map(|b| match b {
            Block::Paragraph(children) => Some(inline_text(children)),
            _ => None,
        })
        .unwrap_or_else(|| fallback.to_string());
    let text = educate_reader_quotes(text.trim());
    if text.chars().count() <= 200 {
        return text;
    }
    let cut: String = text.chars().take(200).collect();
    format!(
        "{}…",
        cut.rsplit_once(' ').map_or(cut.as_str(), |(head, _)| head)
    )
}

struct Issued<'a> {
    edition: &'a Edition,
    pieces: Vec<Piece<'a>>,
    pdf: Option<&'a super::Pdf>,
    others: Vec<&'a str>,
}

impl Issued<'_> {
    fn dir(&self) -> String {
        format!("{}{}/", prefix(&self.edition.language), self.edition.id)
    }

    fn issue_label(&self) -> String {
        format!(
            "{} {}",
            ui(&self.edition.language, "issue"),
            self.edition.issue_number
        )
    }

    fn subtitle(&self) -> String {
        self.edition.raw["subtitle"]
            .as_str()
            .unwrap_or_default()
            .trim()
            .to_string()
    }

    fn cover(&self, ctx: &Ctx, eager: bool) -> String {
        let alt = format!("{} {}", self.issue_label(), self.edition.title);
        self.edition
            .cover_art
            .as_deref()
            .map_or(String::new(), |art| {
                format!(
                    "<figure class=\"cover\">{}</figure>",
                    ctx.picture(art, &alt, COVER_SIZES, eager)
                )
            })
    }

    fn cover_image(&self, images: &Images) -> Option<String> {
        let art = self.edition.cover_art.as_deref()?;
        Some(images[art].large().to_string())
    }

    fn alternate(&self, path: &str) -> Option<(String, String)> {
        let other = self.others.first()?;
        let own = prefix(&self.edition.language);
        Some((
            other.to_string(),
            format!(
                "{}{}",
                prefix(other),
                path.strip_prefix(&own).unwrap_or(path)
            ),
        ))
    }
}

fn download(language: &str, pdf: Option<&super::Pdf>) -> String {
    pdf.map_or(String::new(), |pdf| {
        format!(
            "<p class=\"download\"><a href=\"{}\" download>{} <span>(PDF, {})</span></a></p>",
            esc(&pdf.url),
            say(language, "pdf"),
            megabytes(pdf.bytes)
        )
    })
}

fn issue_page(issued: &Issued, images: &Images) -> Page {
    let path = issued.dir();
    let ctx = Ctx {
        root: depth_root(&path),
        images,
        epub: false,
    };
    let language = &issued.edition.language;
    let entries: String = issued
        .pieces
        .iter()
        .map(|piece| {
            let author = match piece.author.as_str() {
                "" => String::new(),
                author => format!("<span class=\"entry-author\">{}</span>", prose(author)),
            };
            format!(
                "<li><a href=\"{}/\"><span class=\"kicker\">{}</span><span class=\"entry-title\">{}</span>{author}</a></li>",
                esc(&piece.slug),
                prose(&piece.kicker),
                prose(&piece.title)
            )
        })
        .collect();
    let pdf = download(language, issued.pdf);
    let body = format!(
        "<section class=\"issue\">\n{}\n<div class=\"issue-head\"><p class=\"kicker\">{} · <time datetime=\"{}\">{}</time></p>\n<h1>{}</h1>\n<p class=\"subtitle\">{}</p>\n{pdf}</div>\n</section>\n<nav class=\"contents\" aria-label=\"{}\"><h2>{}</h2><ol>{entries}</ol></nav>",
        issued.cover(&ctx, true),
        esc(&issued.issue_label()),
        esc(&issued.edition.publication_date),
        date(language, &issued.edition.publication_date),
        prose(&issued.edition.title),
        prose(&issued.subtitle()),
        esc(&ui(language, "contents")),
        esc(&ui(language, "contents")),
    );
    Page {
        alternate: issued.alternate(&path),
        title: format!(
            "{}: {}",
            issued.issue_label(),
            educate_reader_quotes(&issued.edition.title)
        ),
        description: issued.subtitle(),
        image: issued.cover_image(images),
        crumb: String::new(),
        language: language.clone(),
        path,
        body,
    }
}

fn article_head(ctx: &Ctx, language: &str, piece: &Piece) -> String {
    let mut out = Vec::new();
    if let Some(opener) = piece.article.and_then(|a| a.opener_art.as_ref()) {
        out.push(format!(
            "<figure class=\"opener\">{}</figure>",
            ctx.picture(&opener.path, &opener.alt_text, WIDE_SIZES, true)
        ));
    }
    let dateline = piece
        .article
        .and_then(|a| a.dateline.as_deref())
        .filter(|d| !d.is_empty())
        .map(|d| format!(" · {}", esc(d)))
        .unwrap_or_default();
    out.push(format!(
        "<p class=\"kicker\">{}{dateline}</p>",
        prose(&piece.kicker)
    ));
    out.push(format!("<h1>{}</h1>", prose(&piece.title)));
    if !piece.author.is_empty() {
        out.push(format!(
            "<p class=\"byline\">{} {}</p>",
            esc(&ui(language, "by")),
            prose(&piece.author)
        ));
    }
    let Some(article) = piece.article else {
        return out.join("\n");
    };
    if !article.author_note.is_empty() {
        out.push(format!(
            "<p class=\"author-note\">{}</p>",
            prose(&article.author_note)
        ));
    }
    if let Some(url) = article.source_url.as_deref().filter(|u| !u.is_empty()) {
        let host = url::Url::parse(url)
            .ok()
            .and_then(|u| {
                u.host_str()
                    .map(|h| h.trim_start_matches("www.").to_string())
            })
            .unwrap_or_default();
        out.push(format!(
            "<p class=\"source\"><a href=\"{}\">{} <span>{}</span></a></p>",
            esc(url),
            say(language, "original"),
            esc(&host)
        ));
    }
    out.join("\n")
}

fn article_tail(ctx: &Ctx, language: &str, article: Option<&Article>) -> String {
    let Some(article) = article else {
        return String::new();
    };
    let ideas = match article.key_ideas.is_empty() {
        true => String::new(),
        false => format!(
            "<aside class=\"key-ideas\"><h2>{}</h2><ul>{}</ul></aside>\n",
            esc(&ui(language, "key_ideas")),
            article
                .key_ideas
                .iter()
                .map(|idea| format!("<li>{}</li>", prose(idea)))
                .collect::<String>()
        ),
    };
    let tail = article.tail_art.as_deref().map_or(String::new(), |art| {
        format!(
            "<figure class=\"tail\" aria-hidden=\"true\">{}</figure>",
            ctx.picture(art, "", "(min-width: 30rem) 14rem, 50vw", false)
        )
    });
    format!("{ideas}{tail}")
}

fn pager(issued: &Issued, index: usize) -> String {
    let language = &issued.edition.language;
    let link = |offset: isize, rel: &str, key: &str| {
        let piece = issued.pieces.get(index.checked_add_signed(offset)?)?;
        Some(format!(
            "<a rel=\"{rel}\" href=\"../{}/\"><span class=\"kicker\">{}</span>{}</a>",
            esc(&piece.slug),
            say(language, key),
            prose(&piece.title)
        ))
    };
    let links: Vec<String> = [link(-1, "prev", "previous"), link(1, "next", "next")]
        .into_iter()
        .flatten()
        .collect();
    format!("<nav class=\"pager\">{}</nav>", links.join(""))
}

fn piece_page(issued: &Issued, index: usize, images: &Images) -> Result<Page> {
    let piece = &issued.pieces[index];
    let path = format!("{}{}/", issued.dir(), piece.slug);
    let ctx = Ctx {
        root: depth_root(&path),
        images,
        epub: false,
    };
    let language = &issued.edition.language;
    let image = piece
        .article
        .and_then(|a| a.opener_art.as_ref())
        .map(|o| images[&o.path].large().to_string())
        .or_else(|| issued.cover_image(images));
    let body = format!(
        "<article class=\"piece\">\n<header class=\"piece-head\">\n{}\n</header>\n{}\n{}\n</article>\n{}",
        article_head(&ctx, language, piece),
        body(&ctx, language, piece)?,
        article_tail(&ctx, language, piece.article),
        pager(issued, index)
    );
    let missing = dropped(piece, &body);
    anyhow::ensure!(
        missing.is_empty(),
        "the web page for {} drops {} block(s) of its manuscript:\n  {}",
        piece.slug,
        missing.len(),
        missing.join("\n  ")
    );
    Ok(Page {
        alternate: issued.alternate(&path),
        title: format!(
            "{} · {}",
            educate_reader_quotes(&piece.title),
            issued.edition.publication_name
        ),
        description: summary(&piece.document, &piece.title),
        image,
        crumb: format!(
            "<a class=\"crumb\" href=\"../\">{}</a>",
            esc(&issued.issue_label())
        ),
        language: language.clone(),
        path,
        body,
    })
}

pub fn chapter(edition: &Edition, piece: &Piece, images: &Images) -> Result<String> {
    let ctx = Ctx {
        root: String::new(),
        images,
        epub: true,
    };
    let language = &edition.language;
    let body = format!(
        "<article class=\"piece\">\n<header class=\"piece-head\">\n{}\n</header>\n{}\n{}\n</article>",
        article_head(&ctx, language, piece),
        body(&ctx, language, piece)?,
        article_tail(&ctx, language, piece.article),
    );
    let missing = dropped(piece, &body);
    anyhow::ensure!(
        missing.is_empty(),
        "the EPUB chapter for {} drops {} block(s) of its manuscript:\n  {}",
        piece.slug,
        missing.len(),
        missing.join("\n  ")
    );
    Ok(body.replace("<br>", "<br/>").replace("<hr>", "<hr/>"))
}

pub fn title_page(edition: &Edition) -> String {
    let language = &edition.language;
    format!(
        "<section class=\"title-page\"><p class=\"kicker\">{} · {}</p>\n<h1>{}</h1>\n<p class=\"subtitle\">{}</p>\n<p class=\"masthead-name\">{}</p></section>",
        esc(&format!("{} {}", ui(language, "issue"), edition.issue_number)),
        date(language, &edition.publication_date),
        prose(&edition.title),
        prose(edition.raw["subtitle"].as_str().unwrap_or_default().trim()),
        esc(&edition.publication_name)
    )
}

fn index_page(language: &str, issued: &[&Issued], images: &Images, other: Option<&str>) -> Page {
    let path = prefix(language);
    let ctx = Ctx {
        root: depth_root(&path),
        images,
        epub: false,
    };
    let latest = issued[0];
    let rows: String = issued
        .iter()
        .map(|i| {
            format!(
                "<li><a href=\"{}/\"><span class=\"kicker\">{}</span><span class=\"entry-title\">{}</span><span class=\"entry-author\">{}</span></a></li>",
                esc(&i.edition.id),
                esc(&i.issue_label()),
                prose(&i.edition.title),
                date(language, &i.edition.publication_date)
            )
        })
        .collect();
    let body = format!(
        "<section class=\"issue front\">\n<a class=\"cover-link\" href=\"{id}/\">{cover}</a>\n<div class=\"issue-head\"><p class=\"kicker\">{label} · <time datetime=\"{iso}\">{when}</time></p>\n<h1><a href=\"{id}/\">{title}</a></h1>\n<p class=\"subtitle\">{subtitle}</p>\n<p class=\"read\"><a href=\"{id}/\">{read}</a></p></div>\n</section>\n<nav class=\"contents\" aria-label=\"{issues}\"><h2>{issues}</h2><ol>{rows}</ol></nav>",
        id = esc(&latest.edition.id),
        cover = latest.cover(&ctx, true),
        label = esc(&latest.issue_label()),
        iso = esc(&latest.edition.publication_date),
        when = date(language, &latest.edition.publication_date),
        title = prose(&latest.edition.title),
        subtitle = prose(&latest.subtitle()),
        read = say(language, "read"),
        issues = say(language, "issues"),
    );
    Page {
        alternate: other.map(|o| (o.to_string(), prefix(o))),
        title: latest.edition.publication_name.clone(),
        description: format!(
            "{}: {}",
            latest.issue_label(),
            educate_reader_quotes(&latest.edition.title)
        ),
        image: latest.cover_image(images),
        crumb: String::new(),
        language: language.to_string(),
        path,
        body,
    }
}

fn lost_page(name: &str) -> Page {
    Page {
        path: "404.html".to_string(),
        language: "en".to_string(),
        title: name.to_string(),
        description: say("en", "lost").to_string(),
        image: None,
        alternate: None,
        crumb: String::new(),
        body: format!(
            "<section class=\"lost\"><h1>404</h1><p>{}</p><p><a href=\"/\">{}</a></p></section>",
            say("en", "lost"),
            say("en", "home")
        ),
    }
}

pub fn pages(
    issues: &[Issue],
    images: &Images,
    site: &SiteConfig,
    name: &str,
    logo: &str,
) -> Result<Vec<(String, String)>> {
    let mut issued = Vec::new();
    for issue in issues {
        let languages: Vec<&str> = issue.editions.iter().map(|e| e.language.as_str()).collect();
        for edition in &issue.editions {
            issued.push(Issued {
                edition,
                pieces: pieces(edition)?,
                pdf: issue.pdfs.get(&edition.language),
                others: languages
                    .iter()
                    .copied()
                    .filter(|l| *l != edition.language)
                    .collect(),
            });
        }
    }
    let mut languages: Vec<&str> = issued.iter().map(|i| i.edition.language.as_str()).collect();
    languages.sort_by_key(|l| (*l != "en", *l));
    languages.dedup();
    let mut out = Vec::new();
    for language in &languages {
        let own: Vec<&Issued> = issued
            .iter()
            .filter(|i| i.edition.language == *language)
            .collect();
        let other = languages.iter().copied().find(|l| l != language);
        out.push(index_page(language, &own, images, other));
        for one in own {
            out.push(issue_page(one, images));
            for index in 0..one.pieces.len() {
                out.push(piece_page(one, index, images)?);
            }
        }
    }
    let mut files: Vec<(String, String)> = out
        .iter()
        .map(|page| {
            let root = depth_root(&page.path);
            (
                format!("{}index.html", page.path),
                document(page, site, (name, logo), &root),
            )
        })
        .collect();
    files.push((
        "404.html".to_string(),
        document(&lost_page(name), site, (name, logo), "/"),
    ));
    Ok(files)
}

#[cfg(test)]
mod tests {
    use super::{block, download, dropped, Piece};
    use crate::model::doc::{Block, Document, Inline};
    use crate::site::publish_record;

    #[test]
    fn a_publish_record_puts_its_language_pdf_link_on_the_issue_page_and_no_record_puts_none() {
        let dir = std::env::temp_dir().join(format!("mag-site-pdf-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("publish.yaml");
        std::fs::write(
            &path,
            "pdfs:\n  es:\n    url: https://files.example/011/es/x.pdf\n    bytes: 127300000\n    sha256: ab\n",
        )
        .unwrap();
        let pdfs = publish_record(&path).unwrap().pdfs;
        assert_eq!(
            download("es", pdfs.get("es")),
            "<p class=\"download\"><a href=\"https://files.example/011/es/x.pdf\" download>Descargar el PDF <span>(PDF, 127.3 MB)</span></a></p>"
        );
        assert_eq!(download("en", pdfs.get("en")), "");
        assert!(publish_record(&dir.join("absent.yaml"))
            .unwrap()
            .pdfs
            .is_empty());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_page_missing_any_manuscript_block_is_reported_and_a_whole_page_is_not() {
        let code = "fn main() {\n    println!(\"<\\\"hi\\\">\");\n}\n".to_string();
        let blocks = vec![
            Block::Paragraph(vec![
                Inline::Text("Say \"hi\" to ".into()),
                Inline::Code("\"raw\"".into()),
            ]),
            Block::FencedCode {
                code: code.clone(),
                info: "rust".into(),
            },
        ];
        let html: String = blocks.iter().map(|b| block(b, false).unwrap()).collect();
        let piece = Piece {
            slug: "x".into(),
            kicker: String::new(),
            title: String::new(),
            author: String::new(),
            article: None,
            document: Document {
                metadata: Default::default(),
                blocks,
            },
        };
        assert!(dropped(&piece, &html).is_empty());
        let cut = html.replace("println", "print");
        assert_eq!(dropped(&piece, &cut), vec![code]);
    }
}
