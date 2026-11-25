use super::html::{date, depth_root, Page};
use super::images::Image;
use super::Issue;
use crate::model::doc::educate_reader_quotes;
use crate::modelcard::Card;
use crate::typeset::template::{card_back_png, card_png, BOOK_TEMPLATE_TYP};
use crate::util::{escape_html, sha256_hex};
use anyhow::{Context, Result};
use pulldown_cmark::{CodeBlockKind, Event, HeadingLevel, Options, Parser, Tag, TagEnd};
use serde::Deserialize;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

const CARD_BACK_SHEET: &str = include_str!("../../assets/typeset/card-sheet.typ");
const GRID_SIZES: &str = "(min-width: 56rem) 19rem, (min-width: 38rem) 44vw, calc(100vw - 2.5rem)";
const HERO_SIZES: &str = "(min-width: 52rem) 24rem, min(24rem, calc(100vw - 2.5rem))";
const BODY_SIZES: &str = "(min-width: 44rem) 40rem, calc(100vw - 2.5rem)";
const CARD_PPI: f32 = 220.0;

#[derive(Clone)]
pub struct SourceArticle {
    pub id: String,
    pub title: String,
    pub author: String,
    pub site: String,
    pub url: String,
    pub published_at: String,
    pub markdown: String,
    pub dir: PathBuf,
    pub media: Vec<PathBuf>,
}

#[derive(Clone)]
pub struct WebCard {
    pub slug: String,
    pub card: Card,
    pub released: String,
    pub front: PathBuf,
    pub issue: Option<(String, String, String)>,
    pub source: Option<SourceArticle>,
}

pub struct Deck {
    pub cards: Vec<WebCard>,
    pub back: PathBuf,
}

#[derive(Deserialize, Default)]
struct SourceMeta {
    #[serde(default)]
    title: String,
    #[serde(default)]
    author: String,
    #[serde(default)]
    site: String,
    #[serde(default)]
    url: String,
    #[serde(default)]
    published_at: String,
}

pub fn label(language: &str) -> &'static str {
    match language {
        "es" => "Model Cards",
        _ => "Model Cards",
    }
}

pub fn path(language: &str) -> String {
    match language {
        "en" => "cards/".to_string(),
        other => format!("{other}/cards/"),
    }
}

fn say(language: &str, key: &str) -> &'static str {
    let es = language == "es";
    match key {
        "kicker" if es => "Colección",
        "kicker" => "Collection",
        "lede" if es => "Modelos de frontera destilados en cartas coleccionables, cada una junto a su artículo original de lanzamiento.",
        "lede" => "Frontier models distilled into collectible cards, each paired with its original launch announcement.",
        "all" if es => "Todos",
        "all" => "All",
        "hint" if es => "Mové el cursor sobre la carta para inclinarla. Hacé clic para darla vuelta.",
        "hint" => "Move across the card to tilt it. Click to flip.",
        "flip" if es => "Dar vuelta",
        "flip" => "Flip card",
        "front" if es => "Ver frente",
        "front" => "Show front",
        "full" if es => "Imagen completa",
        "full" => "Full image",
        "in_issue" if es => "En el Número",
        "in_issue" => "Featured in Issue",
        "sibling" if es => "También en este lanzamiento",
        "sibling" => "Also in this launch",
        "intro_kicker" if es => "Artículo original de lanzamiento",
        "intro_kicker" => "Original introduction article",
        "original" if es => "Leer el original",
        "original" => "Read the original",
        "previous" if es => "Anterior",
        "previous" => "Previous",
        "next" if es => "Siguiente",
        "next" => "Next",
        "count_one" if es => "1 carta",
        "count_one" => "1 card",
        "count_many" if es => "cartas",
        _ => "cards",
    }
}

fn slugify(name: &str) -> String {
    let mut out = String::new();
    let mut dash = false;
    for ch in name.chars() {
        if ch.is_ascii_alphanumeric() {
            if dash && !out.is_empty() {
                out.push('-');
            }
            out.push(ch.to_ascii_lowercase());
            dash = false;
        } else {
            dash = true;
        }
    }
    out
}

fn key_of(card: &Card) -> String {
    card.model_id
        .as_deref()
        .unwrap_or(&card.name)
        .to_lowercase()
}

fn cached_card_png(cache: &Path, card: &Card, art: &Path, date: Option<&str>) -> Result<PathBuf> {
    let mut material = BOOK_TEMPLATE_TYP.as_bytes().to_vec();
    material.extend_from_slice(&serde_json::to_vec(card)?);
    material
        .extend_from_slice(&fs::read(art).with_context(|| format!("reading {}", art.display()))?);
    material.extend_from_slice(date.unwrap_or_default().as_bytes());
    let path = cache
        .join("cards")
        .join(format!("card-{}.png", &sha256_hex(&material)[..24]));
    if !path.is_file() {
        let dir = art
            .parent()
            .map(Path::to_path_buf)
            .into_iter()
            .collect::<Vec<_>>();
        let png = card_png(card, art, date, &dir, CARD_PPI)?;
        fs::create_dir_all(path.parent().context("card cache has no parent")?)?;
        fs::write(&path, png)?;
    }
    Ok(path)
}

fn cached_back_png(cache: &Path, site_host: &str) -> Result<PathBuf> {
    let key = sha256_hex(format!("{CARD_BACK_SHEET}|{site_host}|card-back-v1"));
    let path = cache.join("cards").join(format!("back-{}.png", &key[..24]));
    if !path.is_file() {
        let png = card_back_png(site_host, CARD_PPI)?;
        fs::create_dir_all(path.parent().context("card cache has no parent")?)?;
        fs::write(&path, png)?;
    }
    Ok(path)
}

fn load_source(head: &Path, id: &str) -> Result<Option<SourceArticle>> {
    let dir = head.join("library/sources").join(id);
    let record_path = dir.join("record.yaml");
    let article_path = dir.join("article.md");
    if !record_path.is_file() || !article_path.is_file() {
        return Ok(None);
    }
    let meta: SourceMeta = serde_norway::from_str(&fs::read_to_string(&record_path)?)
        .with_context(|| format!("parsing {}", record_path.display()))?;
    let markdown = fs::read_to_string(&article_path)?;
    let media = referenced_media(&dir, &markdown);
    Ok(Some(SourceArticle {
        id: id.to_string(),
        title: meta.title,
        author: meta.author,
        site: meta.site,
        url: meta.url,
        published_at: meta.published_at,
        markdown,
        dir,
        media,
    }))
}

fn referenced_media(dir: &Path, markdown: &str) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for event in Parser::new_ext(markdown, Options::ENABLE_TABLES) {
        if let Event::Start(Tag::Image { dest_url, .. }) = event {
            let candidate = dir.join(dest_url.as_ref());
            if candidate.is_file() && !out.contains(&candidate) {
                out.push(candidate);
            }
        }
    }
    out
}

fn edition_cards(head: &Path, cache: &Path, issues: &[Issue]) -> Result<Vec<WebCard>> {
    let mut out = Vec::new();
    for issue in issues {
        let Some(edition) = issue
            .editions
            .iter()
            .find(|e| e.language == "en")
            .or_else(|| issue.editions.first())
        else {
            continue;
        };
        for article in &edition.articles {
            let source = match article.source_ids.first() {
                Some(id) => load_source(head, id)?,
                None => None,
            };
            for spread in &article.cards {
                let front = match (&spread.image, &spread.art) {
                    (Some(img), _) if img.is_file() => img.clone(),
                    (_, Some(art)) if art.is_file() => {
                        cached_card_png(cache, &spread.card, art, article.dateline.as_deref())?
                    }
                    _ => continue,
                };
                let released = spread
                    .card
                    .released
                    .clone()
                    .or_else(|| source.as_ref().map(|s| s.published_at.clone()))
                    .filter(|s| !s.is_empty())
                    .unwrap_or_else(|| edition.publication_date.clone());
                out.push(WebCard {
                    slug: slugify(&spread.card.name),
                    card: spread.card.clone(),
                    released,
                    front,
                    issue: Some((
                        edition.id.clone(),
                        edition.issue_number.clone(),
                        article.id.clone(),
                    )),
                    source: source.clone(),
                });
            }
        }
    }
    Ok(out)
}

fn standalone_cards(head: &Path, cache: &Path) -> Result<Vec<WebCard>> {
    let dir = head.join("cards");
    let Ok(read) = fs::read_dir(&dir) else {
        return Ok(Vec::new());
    };
    let mut dirs: Vec<PathBuf> = read
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_dir())
        .collect();
    dirs.sort();
    let mut out = Vec::new();
    for item in dirs {
        let json = item.join("card.json");
        let art = item.join("art.jpg");
        if !json.is_file() || !art.is_file() {
            continue;
        }
        let card: Card = serde_json::from_str(&fs::read_to_string(&json)?)
            .with_context(|| format!("parsing {}", json.display()))?;
        let source_id = fs::read_to_string(item.join("sources.txt"))
            .ok()
            .and_then(|s| {
                s.lines()
                    .map(str::trim)
                    .find(|l| !l.is_empty())
                    .map(str::to_string)
            });
        let source = match source_id {
            Some(id) => load_source(head, &id)?,
            None => None,
        };
        let released = card
            .released
            .clone()
            .or_else(|| source.as_ref().map(|s| s.published_at.clone()))
            .unwrap_or_default();
        let front = cached_card_png(cache, &card, &art, None)?;
        out.push(WebCard {
            slug: slugify(&card.name),
            card,
            released,
            front,
            issue: None,
            source,
        });
    }
    Ok(out)
}

pub fn load(head: &Path, cache: &Path, site_host: &str, issues: &[Issue]) -> Result<Deck> {
    let mut all = edition_cards(head, cache, issues)?;
    all.extend(standalone_cards(head, cache)?);
    let mut seen = BTreeSet::new();
    let mut cards = Vec::new();
    for item in all {
        if seen.insert(key_of(&item.card)) {
            cards.push(item);
        }
    }
    cards.sort_by(|a, b| {
        b.released
            .cmp(&a.released)
            .then_with(|| a.card.name.cmp(&b.card.name))
    });
    let back = cached_back_png(cache, site_host)?;
    Ok(Deck { cards, back })
}

pub fn image_paths(deck: &Deck) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if !deck.cards.is_empty() {
        paths.push(deck.back.clone());
    }
    for item in &deck.cards {
        paths.push(item.front.clone());
        if let Some(source) = &item.source {
            paths.extend(source.media.iter().cloned());
        }
    }
    paths
}

fn picture(
    images: &BTreeMap<PathBuf, Image>,
    root: &str,
    path: &Path,
    alt: &str,
    sizes: &str,
    eager: bool,
) -> String {
    let image = &images[path];
    let srcset: Vec<String> = image
        .variants
        .iter()
        .map(|(name, width)| format!("{root}{name} {width}w"))
        .collect();
    let loading = match eager {
        true => "fetchpriority=\"high\"",
        false => "loading=\"lazy\"",
    };
    format!(
        "<img src=\"{root}{}\" srcset=\"{}\" sizes=\"{sizes}\" width=\"{}\" height=\"{}\" alt=\"{}\" {loading} decoding=\"async\">",
        image.src(),
        srcset.join(", "),
        image.width,
        image.height,
        escape_html(alt),
    )
}

fn prose(value: &str) -> String {
    let cleaned: String = value
        .chars()
        .filter(|c| *c != '\u{ad}' && *c != '\r')
        .map(|c| match c {
            '\u{2011}' | '\u{2010}' | '\u{2212}' => '-',
            other => other,
        })
        .collect();
    escape_html(&educate_reader_quotes(&cleaned))
}

fn host_of(url: &str) -> String {
    url::Url::parse(url)
        .ok()
        .and_then(|u| {
            u.host_str()
                .map(|h| h.trim_start_matches("www.").to_string())
        })
        .unwrap_or_default()
}

fn role_line(card: &Card) -> String {
    let mut parts = vec![card.type_line.kind.clone()];
    parts.extend(card.type_line.roles.iter().cloned());
    parts.join(" · ")
}

fn index_page(
    language: &str,
    deck: &Deck,
    images: &BTreeMap<PathBuf, Image>,
    name: &str,
    other: Option<&str>,
) -> Page {
    let page_path = path(language);
    let root = depth_root(&page_path);
    let mut labs: Vec<&str> = deck.cards.iter().map(|c| c.card.lab.as_str()).collect();
    labs.sort_unstable();
    labs.dedup();
    let filters: String = std::iter::once(format!(
        "<button type=\"button\" class=\"card-filter\" data-filter=\"all\" aria-pressed=\"true\">{}</button>",
        say(language, "all")
    ))
    .chain(labs.iter().map(|lab| {
        format!(
            "<button type=\"button\" class=\"card-filter\" data-filter=\"{}\" aria-pressed=\"false\">{}</button>",
            escape_html(lab),
            escape_html(lab)
        )
    }))
    .collect();
    let items: String = deck
        .cards
        .iter()
        .enumerate()
        .map(|(idx, item)| {
            let img = picture(
                images,
                &root,
                &item.front,
                &format!("Model card: {}", item.card.name),
                GRID_SIZES,
                idx < 3,
            );
            let when = match item.released.is_empty() {
                true => String::new(),
                false => format!(" · {}", date(language, &item.released)),
            };
            format!(
                "<li data-lab=\"{lab}\"><a class=\"card-tile\" href=\"{slug}/\">\
                 <div class=\"mtg-scene\"><div class=\"mtg-card\" data-tilt>\
                 <div class=\"mtg-face mtg-front\">{img}\
                 <span class=\"mtg-foil\" aria-hidden=\"true\"></span>\
                 <span class=\"mtg-sheen\" aria-hidden=\"true\"></span>\
                 </div></div></div>\
                 <div class=\"card-caption\">\
                 <span class=\"card-lab\">{lab}{when}</span>\
                 <span class=\"card-name\">{title}</span>\
                 <span class=\"card-role\">{roles}</span>\
                 </div></a></li>",
                lab = escape_html(&item.card.lab),
                slug = escape_html(&item.slug),
                title = prose(&item.card.name),
                roles = prose(&role_line(&item.card)),
            )
        })
        .collect();
    let count = match deck.cards.len() {
        1 => say(language, "count_one").to_string(),
        n => format!("{n} {}", say(language, "count_many")),
    };
    let og = deck
        .cards
        .first()
        .map(|c| images[&c.front].large().to_string());
    let body = format!(
        "<section class=\"cards-head\">\
         <p class=\"kicker\">{kicker} · <span class=\"card-tally\">{count}</span></p>\
         <h1>{heading}</h1>\
         <p class=\"subtitle\">{lede}</p>\
         <div class=\"card-filters\" role=\"group\" aria-label=\"{heading}\">{filters}</div>\
         </section>\
         <ol class=\"card-grid\">{items}</ol>\
         <script src=\"{root}cards.js\" defer></script>",
        kicker = say(language, "kicker"),
        heading = label(language),
        lede = say(language, "lede"),
    );
    Page {
        path: page_path,
        language: language.to_string(),
        title: format!("{} · {name}", label(language)),
        description: say(language, "lede").to_string(),
        image: og,
        alternate: other.map(|o| (o.to_string(), path(o))),
        crumb: String::new(),
        body,
    }
}

fn detail_links(language: &str, item: &WebCard, deck: &Deck, root: &str) -> String {
    let mut rows = Vec::new();
    if let Some((edition_id, issue_num, article_slug)) = &item.issue {
        let prefix = match language {
            "en" => String::new(),
            other => format!("{other}/"),
        };
        rows.push(format!(
            "<p class=\"card-link-row\"><a href=\"{root}{prefix}{edition_id}/{article_slug}/\">{in_issue} {issue_num}</a></p>",
            in_issue = say(language, "in_issue"),
            edition_id = escape_html(edition_id),
            article_slug = escape_html(article_slug),
            issue_num = escape_html(issue_num),
        ));
    }
    if let Some(source) = &item.source {
        let siblings: Vec<String> = deck
            .cards
            .iter()
            .filter(|other| {
                other.slug != item.slug && other.source.as_ref().is_some_and(|s| s.id == source.id)
            })
            .map(|other| {
                format!(
                    "<a href=\"../{}/\">{}</a>",
                    escape_html(&other.slug),
                    prose(&other.card.name)
                )
            })
            .collect();
        if !siblings.is_empty() {
            rows.push(format!(
                "<p class=\"card-link-row\"><span>{}:</span> {}</p>",
                say(language, "sibling"),
                siblings.join(", ")
            ));
        }
        if !source.url.is_empty() {
            rows.push(format!(
                "<p class=\"source\"><a href=\"{}\">{} <span>{}</span></a></p>",
                escape_html(&source.url),
                say(language, "original"),
                escape_html(&host_of(&source.url))
            ));
        }
    }
    rows.join("\n")
}

fn card_pager(language: &str, deck: &Deck, index: usize) -> String {
    let link = |offset: isize, rel: &str, key: &str| {
        let other = deck.cards.get(index.checked_add_signed(offset)?)?;
        Some(format!(
            "<a rel=\"{rel}\" href=\"../{}/\"><span class=\"kicker\">{}</span>{}</a>",
            escape_html(&other.slug),
            say(language, key),
            prose(&other.card.name)
        ))
    };
    let links: Vec<String> = [link(-1, "prev", "previous"), link(1, "next", "next")]
        .into_iter()
        .flatten()
        .collect();
    match links.is_empty() {
        true => String::new(),
        false => format!("<nav class=\"pager\">{}</nav>", links.join("")),
    }
}

fn detail_page(
    language: &str,
    deck: &Deck,
    index: usize,
    images: &BTreeMap<PathBuf, Image>,
    name: &str,
    other: Option<&str>,
) -> Result<Page> {
    let item = &deck.cards[index];
    let page_path = format!("{}{}/", path(language), item.slug);
    let root = depth_root(&page_path);
    let front = picture(
        images,
        &root,
        &item.front,
        &format!("Model card: {}", item.card.name),
        HERO_SIZES,
        true,
    );
    let back = picture(
        images,
        &root,
        &deck.back,
        &format!("{name} card back"),
        HERO_SIZES,
        false,
    );
    let full = format!("{root}{}", images[&item.front].full());
    let when = match item.released.is_empty() {
        true => String::new(),
        false => format!(
            " · <time datetime=\"{}\">{}</time>",
            escape_html(&item.released),
            date(language, &item.released)
        ),
    };
    let model_id = item
        .card
        .model_id
        .as_deref()
        .map(|id| format!("<p class=\"card-id\"><code>{}</code></p>", escape_html(id)))
        .unwrap_or_default();
    let article = match &item.source {
        Some(source) => render_source_article(language, source, images, &root)?,
        None => String::new(),
    };
    let links = detail_links(language, item, deck, &root);
    let pager = card_pager(language, deck, index);
    let body = format!(
        "<section class=\"card-stage\">\
         <div class=\"mtg-scene mtg-scene-hero\">\
         <div class=\"mtg-card is-hero\" data-tilt data-flippable role=\"button\" tabindex=\"0\" aria-pressed=\"false\" aria-label=\"{flip}: {title}\">\
         <div class=\"mtg-face mtg-front\">{front}\
         <span class=\"mtg-foil\" aria-hidden=\"true\"></span>\
         <span class=\"mtg-sheen\" aria-hidden=\"true\"></span>\
         </div>\
         <div class=\"mtg-face mtg-back\">{back}\
         <span class=\"mtg-sheen\" aria-hidden=\"true\"></span>\
         </div>\
         </div>\
         </div>\
         <div class=\"card-info\">\
         <p class=\"kicker\">{lab}{when}</p>\
         <h1>{title}</h1>\
         <p class=\"card-type\">{roles}</p>\
         {model_id}\
         <p class=\"card-hint\">{hint}</p>\
         <div class=\"card-actions\">\
         <button type=\"button\" class=\"card-btn\" data-flip data-front=\"{show_front}\" data-back=\"{flip}\">{flip}</button>\
         <a class=\"card-btn card-btn-ghost\" href=\"{full}\">{full_label}</a>\
         </div>\
         <div class=\"card-links\">{links}</div>\
         </div>\
         </section>\n{article}\n{pager}\
         <script src=\"{root}cards.js\" defer></script>",
        flip = say(language, "flip"),
        show_front = say(language, "front"),
        full_label = say(language, "full"),
        hint = say(language, "hint"),
        lab = escape_html(&item.card.lab),
        title = prose(&item.card.name),
        roles = prose(&role_line(&item.card)),
    );
    let desc = item
        .card
        .traits
        .first()
        .map_or_else(|| role_line(&item.card), Clone::clone);
    Ok(Page {
        path: page_path,
        language: language.to_string(),
        title: format!("{} · {} · {name}", item.card.name, label(language)),
        description: educate_reader_quotes(&desc),
        image: Some(images[&item.front].large().to_string()),
        alternate: other.map(|o| (o.to_string(), format!("{}{}/", path(o), item.slug))),
        crumb: format!("<a class=\"crumb\" href=\"../\">{}</a>", label(language)),
        body,
    })
}

fn render_source_article(
    language: &str,
    source: &SourceArticle,
    images: &BTreeMap<PathBuf, Image>,
    root: &str,
) -> Result<String> {
    let mut head = Vec::new();
    let when = match source.published_at.is_empty() {
        true => String::new(),
        false => format!(
            " · <time datetime=\"{}\">{}</time>",
            escape_html(&source.published_at),
            date(language, &source.published_at)
        ),
    };
    head.push(format!(
        "<p class=\"kicker\">{}{when}</p>",
        say(language, "intro_kicker")
    ));
    if !source.title.is_empty() {
        head.push(format!("<h2>{}</h2>", prose(&source.title)));
    }
    let by = match (!source.author.is_empty(), !source.site.is_empty()) {
        (true, _) => source.author.as_str(),
        (false, true) => source.site.as_str(),
        (false, false) => "",
    };
    if !by.is_empty() {
        head.push(format!("<p class=\"byline\">{}</p>", prose(by)));
    }
    if !source.url.is_empty() {
        head.push(format!(
            "<p class=\"source\"><a href=\"{}\">{} <span>{}</span></a></p>",
            escape_html(&source.url),
            say(language, "original"),
            escape_html(&host_of(&source.url))
        ));
    }
    let content = render_markdown(&source.markdown, &source.title, &source.dir, images, root)?;
    Ok(format!(
        "<article class=\"piece card-article\">\
         <header class=\"piece-head card-article-head\">\n{}\n</header>\n{content}\n</article>",
        head.join("\n")
    ))
}

struct MdState<'a> {
    dir: &'a Path,
    images: &'a BTreeMap<PathBuf, Image>,
    root: &'a str,
    title_key: String,
    seen_block: bool,
    skip_h1: bool,
    in_code: Option<(String, String)>,
    in_image: Option<(String, String)>,
    in_table_head: bool,
    out: String,
}

fn squash_key(text: &str) -> String {
    text.chars()
        .filter(char::is_ascii_alphanumeric)
        .map(|c| c.to_ascii_lowercase())
        .collect()
}

fn render_markdown(
    markdown: &str,
    source_title: &str,
    dir: &Path,
    images: &BTreeMap<PathBuf, Image>,
    root: &str,
) -> Result<String> {
    let mut state = MdState {
        dir,
        images,
        root,
        title_key: squash_key(source_title),
        seen_block: false,
        skip_h1: false,
        in_code: None,
        in_image: None,
        in_table_head: false,
        out: String::new(),
    };
    let events: Vec<Event> = Parser::new_ext(markdown, Options::ENABLE_TABLES).collect();
    let mut i = 0;
    while i < events.len() {
        if !state.seen_block
            && matches!(
                events[i],
                Event::Start(Tag::Heading {
                    level: HeadingLevel::H1,
                    ..
                })
            )
        {
            let mut h1 = String::new();
            let mut j = i + 1;
            while j < events.len() && !matches!(events[j], Event::End(TagEnd::Heading(_))) {
                if let Event::Text(t) | Event::Code(t) = &events[j] {
                    h1.push_str(t);
                }
                j += 1;
            }
            if !state.title_key.is_empty() && squash_key(&h1) == state.title_key {
                state.seen_block = true;
                i = j + 1;
                continue;
            }
        }
        state.handle(events[i].clone())?;
        i += 1;
    }
    Ok(state
        .out
        .replace("<p><figure ", "<figure ")
        .replace("</figure></p>", "</figure>"))
}

impl MdState<'_> {
    fn handle(&mut self, event: Event<'_>) -> Result<()> {
        if self.in_code.is_some() {
            return self.handle_code(event);
        }
        if self.in_image.is_some() {
            self.handle_image(event);
            return Ok(());
        }
        match event {
            Event::Start(tag) => self.start_tag(tag),
            Event::End(tag) => self.end_tag(tag),
            Event::Text(text) => {
                if !self.skip_h1 {
                    self.out.push_str(&prose(&text));
                }
            }
            Event::Code(code) => {
                self.out
                    .push_str(&format!("<code>{}</code>", escape_html(&code)));
            }
            Event::SoftBreak => self.out.push('\n'),
            Event::HardBreak => self.out.push_str("<br>\n"),
            Event::Rule => self.out.push_str("<hr>\n"),
            _ => {}
        }
        Ok(())
    }

    fn handle_code(&mut self, event: Event<'_>) -> Result<()> {
        match event {
            Event::Text(t) => {
                if let Some((_, buf)) = &mut self.in_code {
                    buf.push_str(&t);
                }
            }
            Event::End(TagEnd::CodeBlock) => {
                let (info, text) = self.in_code.take().unwrap_or_default();
                let lang = info.split_whitespace().next().unwrap_or("");
                let class = match lang {
                    "" => String::new(),
                    l => format!(" class=\"language-{}\"", escape_html(l)),
                };
                let highlighted =
                    crate::highlight::html(&text, crate::highlight::language(&text, lang))?;
                self.out
                    .push_str(&format!("<pre><code{class}>{highlighted}</code></pre>\n"));
            }
            _ => {}
        }
        Ok(())
    }

    fn handle_image(&mut self, event: Event<'_>) {
        match event {
            Event::Text(t) | Event::Code(t) => {
                if let Some((_, alt)) = &mut self.in_image {
                    alt.push_str(&t);
                }
            }
            Event::End(TagEnd::Image) => {
                let (dest, alt) = self.in_image.take().unwrap_or_default();
                let candidate = self.dir.join(&dest);
                if let Some(image) = self.images.get(&candidate) {
                    let pic = picture(self.images, self.root, &candidate, &alt, BODY_SIZES, false);
                    let cap = match alt.trim() {
                        "" => String::new(),
                        text => format!("<figcaption>{}</figcaption>", prose(text)),
                    };
                    self.out.push_str(&format!(
                        "<figure class=\"figure\"><a class=\"zoom\" href=\"{}{}\">{pic}</a>{cap}</figure>",
                        self.root,
                        image.full()
                    ));
                }
            }
            _ => {}
        }
    }

    fn start_tag(&mut self, tag: Tag<'_>) {
        self.seen_block = true;
        match tag {
            Tag::Heading { level, .. } => {
                let n = (level as u8 + 1).clamp(2, 6);
                self.out.push_str(&format!("<h{n}>"));
            }
            Tag::Paragraph => self.out.push_str("<p>"),
            Tag::BlockQuote(_) => self.out.push_str("<blockquote>\n"),
            Tag::List(None) => self.out.push_str("<ul>\n"),
            Tag::List(Some(1)) => self.out.push_str("<ol>\n"),
            Tag::List(Some(start)) => self.out.push_str(&format!("<ol start=\"{start}\">\n")),
            Tag::Item => self.out.push_str("<li>"),
            Tag::Emphasis => self.out.push_str("<em>"),
            Tag::Strong => self.out.push_str("<strong>"),
            Tag::Link {
                dest_url, title, ..
            } => {
                let title_attr = match title.is_empty() {
                    true => String::new(),
                    false => format!(" title=\"{}\"", escape_html(&title)),
                };
                self.out.push_str(&format!(
                    "<a href=\"{}\"{title_attr}>",
                    escape_html(&dest_url)
                ));
            }
            Tag::CodeBlock(kind) => {
                let info = match kind {
                    CodeBlockKind::Fenced(i) => i.to_string(),
                    CodeBlockKind::Indented => String::new(),
                };
                self.in_code = Some((info, String::new()));
            }
            Tag::Image { dest_url, .. } => {
                self.in_image = Some((dest_url.to_string(), String::new()));
            }
            Tag::Table(_) => self.out.push_str("<table>\n"),
            Tag::TableHead => {
                self.in_table_head = true;
                self.out.push_str("<thead><tr>");
            }
            Tag::TableRow => self.out.push_str("<tr>"),
            Tag::TableCell => self
                .out
                .push_str(if self.in_table_head { "<th>" } else { "<td>" }),
            _ => {}
        }
    }

    fn end_tag(&mut self, tag: TagEnd) {
        match tag {
            TagEnd::Heading(level) => {
                let n = (level as u8 + 1).clamp(2, 6);
                self.out.push_str(&format!("</h{n}>\n"));
            }
            TagEnd::Paragraph => self.out.push_str("</p>\n"),
            TagEnd::BlockQuote(_) => self.out.push_str("</blockquote>\n"),
            TagEnd::List(false) => self.out.push_str("</ul>\n"),
            TagEnd::List(true) => self.out.push_str("</ol>\n"),
            TagEnd::Item => self.out.push_str("</li>\n"),
            TagEnd::Emphasis => self.out.push_str("</em>"),
            TagEnd::Strong => self.out.push_str("</strong>"),
            TagEnd::Link => self.out.push_str("</a>"),
            TagEnd::Table => self.out.push_str("</tbody></table>\n"),
            TagEnd::TableHead => {
                self.in_table_head = false;
                self.out.push_str("</tr></thead>\n<tbody>\n");
            }
            TagEnd::TableRow => self.out.push_str("</tr>\n"),
            TagEnd::TableCell => {
                self.out
                    .push_str(if self.in_table_head { "</th>" } else { "</td>" });
            }
            _ => {}
        }
    }
}

pub fn pages(
    language: &str,
    deck: &Deck,
    images: &BTreeMap<PathBuf, Image>,
    name: &str,
    other: Option<&str>,
) -> Result<Vec<Page>> {
    if deck.cards.is_empty() {
        return Ok(Vec::new());
    }
    let mut out = vec![index_page(language, deck, images, name, other)];
    for index in 0..deck.cards.len() {
        out.push(detail_page(language, deck, index, images, name, other)?);
    }
    Ok(out)
}
