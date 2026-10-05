use super::images::Image;
use super::{Issue, SiteConfig};
use crate::model::doc::{
    educate_reader_quotes, inline_text, parse_publication_document, Block, Document, Inline,
};
use crate::model::kinds::ExtractStyle;
use crate::model::manifest::{Article, Edition};
use crate::model::records::{Extract, Figure};
use crate::model::shared::{anchor_key, content_label, ui};
use crate::util::escape_html;
use anyhow::{Context, Result};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

static HTML_TAG: LazyLock<regex::Regex> = LazyLock::new(|| regex::Regex::new("<[^>]*>").unwrap());

const OPENER: &str = "__opener__";
const BODY_SIZES: &str = "(min-width: 44rem) 40rem, calc(100vw - 2.5rem)";
const WIDE_SIZES: &str = "(min-width: 44rem) 40rem, 100vw";
const COVER_SIZES: &str = "(min-width: 52rem) 24rem, 80vw";

type Images = BTreeMap<PathBuf, Image>;

fn prose(value: &str) -> String {
    escape_html(&educate_reader_quotes(value))
}

fn say(language: &str, key: &str) -> &'static str {
    let spanish = language == "es";
    match key {
        "read" if spanish => "Leer el número",
        "read" => "Read the issue",
        "issues" if spanish => "Números",
        "issues" => "Issues",
        "get" if spanish => "Obtener el número",
        "get" => "Get the issue",
        "back" if spanish => "Volver al",
        "back" => "Back to",
        "pdf" if spanish => "diseño A5 para imprimir",
        "pdf" => "A5 print layout",
        "epub" if spanish => "para lectores electrónicos",
        "epub" => "for e-readers",
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
        "tagline" if spanish => "Impresa en una notebook, para leer en cualquier parte.",
        "tagline" => "Printed on a laptop, read anywhere.",
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
    let megabytes = bytes as f64 / 1_000_000.0;
    match megabytes < 10.0 {
        true => format!("{megabytes:.1} MB"),
        false => format!("{megabytes:.0} MB"),
    }
}

const SPRITE: &str = "<svg width=\"0\" height=\"0\" style=\"position:absolute\" aria-hidden=\"true\"><defs>\
<symbol id=\"g-pdf\" viewBox=\"0 0 24 24\"><path d=\"M6 2.75h8.5L19.25 7.5V21.25H6z M14.25 2.75V7.75h5M12.5 11v6m-3-3 3 3 3-3\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.6\" stroke-linejoin=\"round\" stroke-linecap=\"round\"/></symbol>\
<symbol id=\"g-epub\" viewBox=\"0 0 24 24\"><path d=\"M2.75 5.5C6 4.5 9.5 4.5 12 6.5c2.5-2 6-2 9.25-1v13c-3.25-1-6.75-1-9.25 1-2.5-2-6-2-9.25-1zM12 6.5v13\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.6\" stroke-linejoin=\"round\" stroke-linecap=\"round\"/></symbol>\
<symbol id=\"g-down\" viewBox=\"0 0 24 24\"><path d=\"M12 4v13m-5-5 5 5 5-5M5 20.25h14\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/></symbol>\
</defs></svg>\n";

pub struct Piece<'a> {
    pub slug: String,
    pub kicker: String,
    pub title: String,
    pub author: String,
    pub label: String,
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
            label: String::new(),
            article: None,
            document: read(&editorial.path)?,
        });
    }
    for (index, article) in edition.articles.iter().enumerate() {
        let document = read(&article.manuscript)?;
        let label = content_label(language, &document.metadata, article.content_mode.as_str());
        out.push(Piece {
            slug: article.id.clone(),
            kicker: format!("{} {:02} · {label}", ui(language, "feature"), index + 1),
            title: article.title.clone(),
            author: article.author.clone(),
            label: label.clone(),
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
            label: String::new(),
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
                escape_html(alt)
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
            escape_html(alt)
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

    fn figure(&self, language: &str, figure: &Figure) -> String {
        let label = match self.epub {
            true => String::new(),
            false => format!(
                "<span class=\"fig-label\">{}</span>",
                escape_html(&ui(language, "figure"))
            ),
        };
        let credit = match figure.credit.trim() {
            "" => String::new(),
            credit => format!(" <span class=\"credit\">{}</span>", prose(credit)),
        };
        format!(
            "<figure class=\"figure\" id=\"figure-{}\">{}<figcaption>{label}{}{credit}</figcaption></figure>",
            escape_html(&figure.id),
            self.zoomable(&figure.path, &figure.alt_text, BODY_SIZES),
            prose(&figure.caption)
        )
    }

    fn extract(&self, language: &str, extract: &Extract) -> String {
        let body = match extract.style {
            ExtractStyle::Code => format!("<pre><code>{}</code></pre>", escape_html(&extract.text)),
            ExtractStyle::Quote => format!(
                "<blockquote>{}</blockquote>",
                extract
                    .text
                    .split("\n\n")
                    .map(str::trim)
                    .filter(|p| !p.is_empty())
                    .map(|p| format!("<p>{}</p>", escape_html(p)))
                    .collect::<String>()
            ),
        };
        format!(
            "<figure class=\"extract\" id=\"extract-{}\"><p class=\"extract-label\">{}</p>{body}<figcaption>{}</figcaption></figure>",
            escape_html(&extract.id),
            escape_html(&ui(language, "verbatim")),
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
            Inline::Code(value) => format!("<code>{}</code>", escape_html(value)),
            Inline::Link {
                destination,
                title,
                children,
            } => format!(
                "<a href=\"{}\"{}>{}</a>",
                escape_html(destination),
                title
                    .as_deref()
                    .map(|t| format!(" title=\"{}\"", escape_html(t)))
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
        language => format!(" class=\"language-{}\"", escape_html(language)),
    };
    let tail = &code[code.trim_end_matches('\n').len()..];
    Ok(format!(
        "<pre><code{class}>{}{tail}</code></pre>",
        crate::highlight::html(code, crate::highlight::language(code, language))?
    ))
}

fn block(item: &Block, class: &str) -> Result<String> {
    Ok(match item {
        Block::Heading { level, children } => {
            let level = (*level).clamp(2, 6);
            format!("<h{level}>{}</h{level}>", inline(children))
        }
        Block::Paragraph(children) if !class.is_empty() => {
            format!("<p class=\"{class}\">{}</p>", inline(children))
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
    items.iter().map(|item| block(item, "")).collect()
}

fn anchored(ctx: &Ctx, language: &str, article: Option<&Article>, key: &str) -> String {
    let Some(article) = article else {
        return String::new();
    };
    let figures = article
        .figures
        .iter()
        .filter(|f| anchor_key(&f.anchor) == key)
        .map(|f| ctx.figure(language, f));
    let extracts = article
        .extracts
        .iter()
        .filter(|e| anchor_key(&e.anchor) == key)
        .map(|e| ctx.extract(language, e));
    figures.chain(extracts).collect::<Vec<_>>().join("\n")
}

fn opener(ctx: &Ctx, piece: &Piece) -> String {
    piece
        .article
        .and_then(|a| a.opener_art.as_ref())
        .map(|o| {
            format!(
                "<figure class=\"opener\">{}</figure>",
                ctx.picture(&o.path, &o.alt_text, WIDE_SIZES, true)
            )
        })
        .unwrap_or_default()
}

fn body(ctx: &Ctx, language: &str, piece: &Piece) -> Result<String> {
    let mut out = Vec::new();
    let lead = matches!(piece.document.blocks.first(), Some(Block::Paragraph(_)));
    if !lead {
        out.push(opener(ctx, piece));
        out.push(anchored(ctx, language, piece.article, &anchor_key(OPENER)));
    }
    let mut capped = false;
    for (index, item) in piece.document.blocks.iter().enumerate() {
        let is_paragraph = matches!(item, Block::Paragraph(_));
        let class = match (index, is_paragraph && !capped) {
            (0, _) => "standfirst",
            (_, true) => "first",
            _ => "",
        };
        capped |= is_paragraph && index > 0;
        out.push(block(item, class)?);
        if index == 0 && lead {
            out.push(opener(ctx, piece));
            out.push(anchored(ctx, language, piece.article, &anchor_key(OPENER)));
        }
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
    HTML_TAG
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
        if !html.contains(&format!("id=\"figure-{}\"", escape_html(&figure.id)))
            || !html.contains(&format!("alt=\"{}\"", escape_html(&figure.alt_text)))
        {
            want.push((format!("figure {}", figure.id), true));
        }
    }
    for extract in piece.article.iter().flat_map(|a| &a.extracts) {
        let verbatim = extract.style == ExtractStyle::Code;
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
        format!("<title>{}</title>", escape_html(&page.title)),
        format!(
            "<meta name=\"description\" content=\"{}\">",
            escape_html(&page.description)
        ),
        format!("<link rel=\"canonical\" href=\"{url}\">"),
        format!(
            "<meta property=\"og:site_name\" content=\"{}\">",
            escape_html(name)
        ),
        format!(
            "<meta property=\"og:title\" content=\"{}\">",
            escape_html(&page.title)
        ),
        format!(
            "<meta property=\"og:description\" content=\"{}\">",
            escape_html(&page.description)
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
<link rel=\"stylesheet\" href=\"{root}site.css\">\n</head>\n<body>\n{SPRITE}\
<header class=\"masthead\"><a class=\"brand\" href=\"{home}\">{logo}</a>{crumb}<nav class=\"topnav\"><a href=\"{home}\">{issues}</a></nav>{switch}</header>\n\
<main>\n{body}\n</main>\n\
<footer class=\"colophon\"><a href=\"{home}\">{name}</a><span>{tagline}</span></footer>\n</body>\n</html>\n",
        lang = escape_html(&page.language),
        head = head.join("\n"),
        name = escape_html(name),
        issues = say(&page.language, "issues"),
        tagline = say(&page.language, "tagline"),
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
    assets: Option<&'a super::Assets>,
    others: Vec<&'a str>,
}

impl Issued<'_> {
    fn dir(&self) -> String {
        issue_dir(self.edition)
    }

    fn issue_label(&self) -> String {
        format!(
            "{} {}",
            ui(&self.edition.language, "issue"),
            self.edition.issue_number
        )
    }

    fn subtitle(&self) -> String {
        self.edition.subtitle.clone()
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

pub fn issue_dir(edition: &Edition) -> String {
    format!("{}{}/", prefix(&edition.language), edition.id)
}

fn mime(kind: &str) -> &'static str {
    match kind {
        "pdf" => "application/pdf",
        _ => "application/epub+zip",
    }
}

fn download(language: &str, kind: &str, asset: &super::Asset) -> String {
    format!(
        "<a class=\"btn\" href=\"{}?v={}\" type=\"{}\" download><svg class=\"glyph\" aria-hidden=\"true\"><use href=\"#g-{kind}\"/></svg><span class=\"btn-text\"><span class=\"btn-label\">{}</span><span class=\"btn-meta\">{}, {}</span></span><svg class=\"btn-arrow\" aria-hidden=\"true\"><use href=\"#g-down\"/></svg></a>",
        escape_html(&asset.url),
        &asset.sha256[..8],
        mime(kind),
        kind.to_uppercase(),
        megabytes(asset.bytes),
        say(language, kind)
    )
}

fn formats(assets: Option<&super::Assets>) -> Vec<(&'static str, &super::Asset)> {
    let Some(assets) = assets else {
        return Vec::new();
    };
    [("pdf", &assets.pdf), ("epub", &assets.epub)]
        .into_iter()
        .filter_map(|(kind, asset)| Some((kind, asset.as_ref()?)))
        .collect()
}

fn get_issue(language: &str, assets: Option<&super::Assets>) -> String {
    let found = formats(assets);
    let solo = if found.len() == 1 { " solo" } else { "" };
    let buttons: String = found
        .into_iter()
        .map(|(kind, asset)| download(language, kind, asset))
        .collect();
    match buttons.is_empty() {
        true => String::new(),
        false => format!(
            "<div class=\"getissue\" id=\"get\"><h2 class=\"getissue-title\">{}</h2><div class=\"btns{solo}\">{buttons}</div></div>\n",
            say(language, "get")
        ),
    }
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
        .enumerate()
        .map(|(index, piece)| {
            let author = match piece.author.as_str() {
                "" => String::new(),
                author => format!("<span class=\"entry-author\">{}</span>", prose(author)),
            };
            format!(
                "<li><a href=\"{}/\"><span class=\"num\">{:02}</span><span class=\"entry-main\"><span class=\"entry-title\">{}</span>{author}</span><span class=\"mode\">{}</span></a></li>",
                escape_html(&piece.slug),
                index + 1,
                prose(&piece.title),
                prose(&piece.label)
            )
        })
        .collect();
    let pdf = get_issue(language, issued.assets);
    let body = format!(
        "<section class=\"issue\">\n{}\n<div class=\"issue-head\"><p class=\"kicker\">{} · <time datetime=\"{}\">{}</time></p>\n<h1>{}</h1>\n<p class=\"subtitle\">{}</p>\n{pdf}</div>\n</section>\n<nav class=\"contents\" aria-label=\"{}\"><h2>{}</h2><ol>{entries}</ol></nav>",
        issued.cover(&ctx, true),
        escape_html(&issued.issue_label()),
        escape_html(&issued.edition.publication_date),
        date(language, &issued.edition.publication_date),
        prose(&issued.edition.title),
        prose(&issued.subtitle()),
        escape_html(&ui(language, "contents")),
        escape_html(&ui(language, "contents")),
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

fn article_head(language: &str, piece: &Piece) -> String {
    let mut out = Vec::new();
    let dateline = piece
        .article
        .and_then(|a| a.dateline.as_deref())
        .filter(|d| !d.is_empty())
        .map(|d| format!(" · {}", escape_html(d)))
        .unwrap_or_default();
    out.push(format!(
        "<p class=\"kicker\">{}{dateline}</p>",
        prose(&piece.kicker)
    ));
    out.push(format!("<h1>{}</h1>", prose(&piece.title)));
    if !piece.author.is_empty() {
        out.push(format!(
            "<p class=\"byline\">{} {}</p>",
            escape_html(&ui(language, "by")),
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
            escape_html(url),
            say(language, "original"),
            escape_html(&host)
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
            escape_html(&ui(language, "key_ideas")),
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
            escape_html(&piece.slug),
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

fn piece_end(issued: &Issued) -> String {
    let language = &issued.edition.language;
    let names: Vec<String> = formats(issued.assets)
        .iter()
        .map(|(kind, _)| kind.to_uppercase())
        .collect();
    let get = match names.is_empty() {
        true => String::new(),
        false => format!(
            "<a class=\"dl\" href=\"../#get\"><svg class=\"glyph\" aria-hidden=\"true\"><use href=\"#g-down\"/></svg>{}: {}</a>",
            say(language, "get"),
            names.join(", ")
        ),
    };
    format!(
        "<div class=\"piece-end\"><a class=\"back\" href=\"../\">{} {}, {}</a>{get}</div>\n",
        say(language, "back"),
        escape_html(&issued.issue_label()),
        prose(&issued.edition.title)
    )
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
        "<article class=\"piece\">\n<header class=\"piece-head\">\n{}\n</header>\n{}\n{}\n</article>\n{}{}",
        article_head(language, piece),
        body(&ctx, language, piece)?,
        article_tail(&ctx, language, piece.article),
        piece_end(issued),
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
            escape_html(&issued.issue_label())
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
        article_head(language, piece),
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
        escape_html(&format!("{} {}", ui(language, "issue"), edition.issue_number)),
        date(language, &edition.publication_date),
        prose(&edition.title),
        prose(&edition.subtitle),
        escape_html(&edition.publication_name)
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
                "<li><a href=\"{}/\"><span class=\"num\">{}</span><span class=\"entry-main\"><span class=\"entry-title\">{}</span><span class=\"entry-author\">{}</span></span></a></li>",
                escape_html(&i.edition.id),
                escape_html(&i.edition.issue_number),
                prose(&i.edition.title),
                date(language, &i.edition.publication_date)
            )
        })
        .collect();
    let body = format!(
        "<section class=\"issue front\">\n<a class=\"cover-link\" href=\"{id}/\">{cover}</a>\n<div class=\"issue-head\"><p class=\"kicker\">{label} · <time datetime=\"{iso}\">{when}</time></p>\n<h1><a href=\"{id}/\">{title}</a></h1>\n<p class=\"subtitle\">{subtitle}</p>\n<p class=\"read\"><a href=\"{id}/\">{read}</a></p></div>\n</section>\n<nav class=\"contents\" aria-label=\"{issues}\"><h2>{issues}</h2><ol>{rows}</ol></nav>",
        id = escape_html(&latest.edition.id),
        cover = latest.cover(&ctx, true),
        label = escape_html(&latest.issue_label()),
        iso = escape_html(&latest.edition.publication_date),
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
                assets: issue.assets.get(&edition.language),
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
    use super::{block, body, download, dropped, get_issue, Ctx, Image, Piece};
    use crate::model::doc::{Block, Document, Inline};
    use crate::model::kinds::{ContentMode, FigureFit, FigureLayout, FigureTone};
    use crate::model::manifest::{Article, ArticleOpenerArt};
    use crate::model::records::Figure;
    use crate::site::publish_record;
    use std::collections::BTreeMap;
    use std::path::PathBuf;

    #[test]
    fn a_publish_record_links_each_language_file_with_its_hash_and_no_record_links_none() {
        let dir = std::env::temp_dir().join(format!("mag-site-pdf-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("publish.yaml");
        std::fs::write(
            &path,
            "es:\n  pdf:\n    url: https://files.example/011/es/x.pdf\n    bytes: 127300000\n    sha256: abcdef0100000000000000000000000000000000000000000000000000000000\n  epub:\n    url: https://files.example/011/es/x.epub\n    bytes: 5000000\n    sha256: 0123456700000000000000000000000000000000000000000000000000000000\n",
        )
        .unwrap();
        let record = publish_record(&path).unwrap();
        let es = record.get("es").unwrap();
        let pdf = download("es", "pdf", es.pdf.as_ref().unwrap());
        assert!(pdf.contains("href=\"https://files.example/011/es/x.pdf?v=abcdef01\" type=\"application/pdf\" download>"));
        assert!(pdf.contains("<span class=\"btn-label\">PDF</span><span class=\"btn-meta\">127 MB, diseño A5 para imprimir</span>"));
        assert!(download("es", "epub", es.epub.as_ref().unwrap())
            .contains("x.epub?v=01234567\" type=\"application/epub+zip\" download>"));
        assert!(get_issue("en", record.get("none")).is_empty());
        assert!(get_issue("es", Some(es)).contains("5.0 MB, para lectores electrónicos"));
        assert!(publish_record(&dir.join("absent.yaml")).unwrap().is_empty());
        std::fs::write(
            &path,
            "pdfs:\n  en:\n    url: u\n    bytes: 1\n    sha256: ab\n",
        )
        .unwrap();
        let err = format!("{:#}", publish_record(&path).unwrap_err());
        assert!(
            err.contains("publish.yaml") && err.contains("old Drive format"),
            "{err}"
        );
        std::fs::write(
            &path,
            "en:\n  pdf:\n    url: u\n    bytes: 1\n    sha256: ab\n",
        )
        .unwrap();
        let err = format!("{:#}", publish_record(&path).unwrap_err());
        assert!(
            err.contains("64 lowercase hex") && err.contains("publish.yaml"),
            "{err}"
        );
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
        let html: String = blocks.iter().map(|b| block(b, "").unwrap()).collect();
        let piece = Piece {
            slug: "x".into(),
            kicker: String::new(),
            title: String::new(),
            author: String::new(),
            label: String::new(),
            article: None,
            document: Document {
                metadata: serde_norway::Mapping::default(),
                blocks,
            },
        };
        assert!(dropped(&piece, &html).is_empty());
        let cut = html.replace("println", "print");
        assert_eq!(dropped(&piece, &cut), vec![code]);
    }

    #[test]
    fn opener_art_follows_the_standfirst_and_opener_figures_follow_the_art() {
        let image = || Image {
            variants: vec![("a.jpg".into(), 100)],
            width: 100,
            height: 50,
        };
        let images = BTreeMap::from([
            (PathBuf::from("art.png"), image()),
            (PathBuf::from("fig.png"), image()),
        ]);
        let ctx = Ctx {
            root: String::new(),
            images: &images,
            epub: false,
        };
        let article = Article {
            id: "a".into(),
            title: String::new(),
            short_title: String::new(),
            display_emphasis: String::new(),
            opener_variant: String::new(),
            author: String::new(),
            author_note: String::new(),
            source_ids: Vec::new(),
            manuscript: PathBuf::new(),
            content_mode: ContentMode::Article,
            figures: vec![Figure {
                id: "f1".into(),
                source_id: "s".into(),
                path: "fig.png".into(),
                caption: "cap".into(),
                credit: String::new(),
                alt_text: String::new(),
                anchor: "__opener__".into(),
                layout: FigureLayout::ColumnPlate,
                tone: FigureTone::Auto,
                fit: FigureFit::Auto,
            }],
            minimum_reader_pages: 0,
            tail_art: None,
            source_url: None,
            opener_art: Some(ArticleOpenerArt {
                path: "art.png".into(),
                alt_text: String::new(),
                credit: String::new(),
            }),
            key_ideas: Vec::new(),
            dateline: None,
            extracts: Vec::new(),
        };
        let piece = Piece {
            slug: "x".into(),
            kicker: String::new(),
            title: String::new(),
            author: String::new(),
            label: String::new(),
            article: Some(&article),
            document: Document {
                metadata: serde_norway::Mapping::default(),
                blocks: vec![
                    Block::Paragraph(vec![Inline::Text("Stand".into())]),
                    Block::Paragraph(vec![Inline::Text("Later".into())]),
                ],
            },
        };
        let html = body(&ctx, "en", &piece).unwrap();
        let at = |needle: &str| html.find(needle).unwrap();
        assert!(at("Stand") < at("class=\"opener\""));
        assert!(at("class=\"opener\"") < at("id=\"figure-f1\""));
        assert!(at("id=\"figure-f1\"") < at("Later"));
        assert!(dropped(&piece, &html).is_empty());
    }
}
