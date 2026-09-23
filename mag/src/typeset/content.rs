use crate::model::doc::{
    educate_reader_quotes, fold_reader_characters, parse_publication_document, settable_codepoints,
    Block, Document, Inline,
};
use crate::model::manifest::{
    load_edition, Article, Edition, Editorial, LoadOptions, Records, Section,
};
use crate::model::records::{load_records, Extract, Figure};
use crate::model::shared::{
    clamp_roster, content_label, is_name_roster, py_casefold, py_repr, py_str, ui, Result,
    ValidationError,
};
use crate::typeset::estimate::{Metrics, Opener};
use crate::typeset::media::pixels;
use std::collections::BTreeSet;
use std::path::Path;
use typst_syntax::{SyntaxKind, SyntaxNode};
use unicode_normalization::UnicodeNormalization;

pub const CONTENTS_TITLE_LIMIT: usize = 62;
pub const CONTENTS_TIGHT_ABOVE: usize = 8;
const ILLUSTRATED: &str = "illustrated_paper_spots_v1";
const OPENER_ANCHOR: &str = "__opener__";
const REFERENCE_HEADINGS: [&str; 2] = ["references", "referencias"];
const MAIN: &str = "main.typ";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct File {
    pub path: String,
    pub source: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Tree {
    pub files: Vec<File>,
}

impl Tree {
    pub fn get(&self, path: &str) -> Option<&File> {
        self.files.iter().find(|file| file.path == path)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Projection {
    pub text: String,
    pub verbatim: Vec<String>,
}

pub struct Inputs<'a> {
    pub root: &'a Path,
    pub edition_id: &'a str,
    pub publication_name: &'a str,
    pub fonts: &'a Path,
    pub allow_missing_art: bool,
    pub allow_unanchored_figures: bool,
}

pub fn pipeline(inputs: &Inputs) -> Result<Tree> {
    let records: Records = load_records(&inputs.root.join("library").join("sources"))?
        .into_iter()
        .map(|record| (record.id.clone(), record))
        .collect();
    let known: BTreeSet<String> = records.keys().cloned().collect();
    let edition = load_edition(
        inputs.root,
        inputs.edition_id,
        &known,
        &LoadOptions {
            publication_name: inputs.publication_name,
            source_records: Some(&records),
            allow_missing_art: inputs.allow_missing_art,
            allow_unanchored_figures: inputs.allow_unanchored_figures,
        },
    )?;
    let settable = settable_codepoints(inputs.fonts).map_err(refusal)?;
    build(&edition, &settable, &Metrics::load(inputs.fonts)?)
}

pub fn build(edition: &Edition, settable: &BTreeSet<u32>, metrics: &Metrics) -> Result<Tree> {
    Writer {
        edition,
        settable,
        metrics,
        illustrated: article_opener_format(edition) == ILLUSTRATED,
    }
    .tree()
}

fn refusal(error: anyhow::Error) -> ValidationError {
    ValidationError::one(format!("{error:#}"))
}

fn article_opener_format(edition: &Edition) -> String {
    edition
        .raw
        .get("format")
        .and_then(|value| value.get("article_opener"))
        .map(py_str)
        .map(|value| value.trim().to_string())
        .unwrap_or_default()
}

fn anchor_key(value: &str) -> String {
    py_casefold(value.trim())
}

fn is_reference_heading(text: &str) -> bool {
    REFERENCE_HEADINGS.contains(&anchor_key(text).as_str())
}

struct Writer<'a> {
    edition: &'a Edition,
    settable: &'a BTreeSet<u32>,
    metrics: &'a Metrics,
    illustrated: bool,
}

struct ContentsEntry {
    destination: String,
    label: String,
    title: String,
    author: String,
}

impl Writer<'_> {
    fn ui(&self, key: &str) -> String {
        ui(&self.edition.language, key)
    }

    fn prose(&self, value: &str) -> String {
        escape_markup(&fold_reader_characters(
            &educate_reader_quotes(value),
            self.settable,
        ))
    }

    fn literal(&self, value: &str) -> String {
        escape_markup(&fold_reader_characters(value, self.settable))
    }

    fn said(&self, value: &str) -> String {
        format!("[{}]", self.prose(value))
    }

    fn verbatim(&self, value: &str) -> String {
        format!("[{}]", self.literal(value))
    }

    fn tree(&self) -> Result<Tree> {
        let mut files = Vec::new();
        let mut main = String::from("#import \"/template.typ\": *\n\n");
        main.push_str(&self.header());
        main.push_str(&self.contents()?);
        if let Some(editorial) = &self.edition.editorial {
            let document = read_manuscript(&editorial.path)?;
            main.push_str(&include_piece(
                &mut files,
                "pieces/editorial.typ".to_string(),
                self.editorial(editorial, &document),
            ));
        }
        for (index, article) in self.edition.articles.iter().enumerate() {
            let document = read_manuscript(&article.manuscript)?;
            main.push_str(&include_piece(
                &mut files,
                format!("pieces/article-{:02}-{}.typ", index + 1, article.id),
                self.article(article, &document, index + 1)?,
            ));
        }
        for (index, section) in self.edition.sections.iter().enumerate() {
            let document = read_manuscript(&section.path)?;
            main.push_str(&include_piece(
                &mut files,
                format!("pieces/section-{index}.typ"),
                self.section(index, section, &document),
            ));
        }
        main.push_str(&self.closing_plates());
        files.insert(
            0,
            File {
                path: MAIN.to_string(),
                source: main,
            },
        );
        Ok(Tree { files })
    }

    fn header(&self) -> String {
        let edition = self.edition;
        let subtitle = edition
            .raw
            .get("subtitle")
            .map(py_str)
            .map(|value| value.trim().to_string())
            .unwrap_or_default();
        format!(
            "#edition-header[\n  #publication-name{}\n  #issue-line{}\n  #edition-title{}\n{}  \
             #edition-date{}\n]\n\n",
            self.said(&edition.publication_name),
            self.said(&format!("{} {}", self.ui("issue"), edition.issue_number)),
            self.said(&edition.title),
            if subtitle.is_empty() {
                String::new()
            } else {
                format!("  #edition-subtitle{}\n", self.said(&subtitle))
            },
            self.said(&edition.publication_date),
        )
    }

    fn contents(&self) -> Result<String> {
        let entries = self.contents_entries();
        let refusals: Vec<String> = entries
            .iter()
            .filter(|entry| entry.title.chars().count() > CONTENTS_TITLE_LIMIT)
            .map(|entry| {
                format!(
                    "Contents title {} ({} characters) would wrap onto the entry's author \
                     line; shorten the article title to {CONTENTS_TITLE_LIMIT} characters \
                     or fewer.",
                    py_repr(&entry.title),
                    entry.title.chars().count()
                )
            })
            .collect();
        if !refusals.is_empty() {
            return Err(ValidationError(refusals));
        }
        let rows: String = entries
            .iter()
            .map(|entry| {
                format!(
                    "  #contents-entry(destination: {})[#entry-label{}#entry-title{}{}]\n",
                    string_literal(&entry.destination),
                    self.said(&entry.label),
                    self.said(&entry.title),
                    if entry.author.is_empty() {
                        String::new()
                    } else {
                        format!("#entry-author{}", self.said(&clamp_roster(&entry.author)))
                    },
                )
            })
            .collect();
        Ok(format!(
            "#contents(tight: {})[\n  #contents-kicker{}\n  #contents-label{}\n{rows}]\n\n",
            entries.len() > CONTENTS_TIGHT_ABOVE,
            self.said(&format!(
                "{} {} / {}",
                self.ui("issue"),
                self.edition.issue_number,
                self.ui("contents")
            )),
            self.said(&self.ui("contents")),
        ))
    }

    fn contents_entries(&self) -> Vec<ContentsEntry> {
        let mut entries = Vec::new();
        if let Some(editorial) = &self.edition.editorial {
            entries.push(ContentsEntry {
                destination: "editorial".to_string(),
                label: self.ui("editorial"),
                title: editorial.title.clone(),
                author: editorial.byline.clone(),
            });
        }
        for (index, article) in self.edition.articles.iter().enumerate() {
            entries.push(ContentsEntry {
                destination: format!("article-{}", article.id),
                label: format!("{} {:02}", self.ui("feature"), index + 1),
                title: article.title.clone(),
                author: article.author.clone(),
            });
        }
        for (index, section) in self.edition.sections.iter().enumerate() {
            entries.push(ContentsEntry {
                destination: format!("section-{index}"),
                label: self.ui(&section.kind),
                title: section.title.clone(),
                author: String::new(),
            });
        }
        entries
    }

    fn editorial(&self, editorial: &Editorial, document: &Document) -> String {
        format!(
            "#piece(\n  id: {},\n  kind: {},\n  short-title: {},\n)[\n  \
             #content-label[#label-primary{}]\n  #piece-title{}\n  {}\n{}]\n",
            string_literal("editorial"),
            string_literal("original_editorial"),
            string_literal(&self.ui("editorial")),
            self.said(&editorial.label),
            self.said(&editorial.title),
            self.byline(&editorial.byline),
            self.blocks(&document.blocks, true),
        )
    }

    fn section(&self, index: usize, section: &Section, document: &Document) -> String {
        format!(
            "#piece(\n  id: {},\n  kind: {},\n  short-title: {},\n)[\n  \
             #content-label[#label-primary{}]\n  #piece-title{}\n{}]\n",
            string_literal(&format!("section-{index}")),
            string_literal(&section.kind),
            string_literal(&section.title),
            self.said(&self.ui(&section.kind)),
            self.said(&section.title),
            self.blocks(&document.blocks, true),
        )
    }

    fn byline(&self, name: &str) -> String {
        format!(
            "#byline[#byline-prefix{}#byline-name{}]",
            self.said(&self.ui("by")),
            self.said(&format!(" {name}"))
        )
    }

    fn article(&self, article: &Article, document: &Document, index: usize) -> Result<String> {
        let illustrated = self.illustrated && article.opener_art.is_some();
        if illustrated && !matches!(document.blocks.first(), Some(Block::Paragraph(_))) {
            return Err(ValidationError::one(format!(
                "{ILLUSTRATED} requires a paragraph as the first manuscript block"
            )));
        }
        let mut out = self.article_head(article, document, index, illustrated);
        if !illustrated {
            out.push_str("  #opener-end()\n");
        }
        if let (true, Some(block)) = (illustrated, document.blocks.first()) {
            out.push_str(&self.standfirst(article, block));
        }
        out.push_str(&self.article_body(article, document, usize::from(illustrated))?);
        out.push_str(&self.key_ideas(article));
        out.push_str(&format!(
            "#end-mark{}\n\n",
            self.said(&format!("{} / {index:02}", self.ui("end")))
        ));
        if article.tail_art.is_some() {
            out.push_str("#tail-art()\n\n");
        }
        if !illustrated {
            out.push_str(&self.source_link(article));
        }
        out.push_str("]\n");
        Ok(out)
    }

    fn standfirst(&self, article: &Article, block: &Block) -> String {
        let Block::Paragraph(children) = block else {
            return self.block(block, true, false);
        };
        let plain = |value: &str| fold_reader_characters(value, self.settable);
        let keep = self.metrics.standfirst_keep_words(&Opener {
            title: &plain(&article.title),
            byline: &plain(&article.author),
            note: &plain(&article.author_note),
            intro: &self.plain_text(children),
        });
        let Some((kept, moved)) = split_words(children, keep) else {
            return self.block(block, true, false);
        };
        format!(
            "#doc-paragraph(standfirst: true, roster: {}, split: true)[{}]\n\n\
             #doc-paragraph(standfirst: false, roster: false)[{}]\n\n",
            is_name_roster(&inline_text(children)),
            self.inlines(&kept),
            self.inlines(&moved),
        )
    }

    fn plain_text(&self, inlines: &[Inline]) -> String {
        inlines
            .iter()
            .map(|inline| match inline {
                Inline::Text(value) => {
                    fold_reader_characters(&educate_reader_quotes(value), self.settable)
                }
                Inline::Code(value) => fold_reader_characters(value, self.settable),
                Inline::Emphasis(children) | Inline::Strong(children) => self.plain_text(children),
                Inline::Link { children, .. } => self.plain_text(children),
                Inline::LineBreak { .. } => "\n".to_string(),
            })
            .collect()
    }

    fn article_head(
        &self,
        article: &Article,
        document: &Document,
        index: usize,
        illustrated: bool,
    ) -> String {
        let mut label = format!(
            "  #content-label[#label-primary{}",
            self.said(&format!("{} {index:02}", self.ui("feature")))
        );
        if illustrated {
            label.push_str(&format!("#label-separator{}", self.said(" / ")));
        }
        label.push_str(&format!(
            "#label-secondary{}",
            self.said(&content_label(
                &self.edition.language,
                &document.metadata,
                &article.content_mode
            ))
        ));
        if let Some(dateline) = article.dateline.as_deref().filter(|d| !d.is_empty()) {
            label.push_str(&format!(
                "#label-separator{}#label-date{}",
                self.said(" / "),
                self.said(dateline)
            ));
        }
        label.push_str("]\n");
        let note = match article.author_note.is_empty() {
            true => String::new(),
            false => format!("  #author-note{}\n", self.said(&article.author_note)),
        };
        let provenance = if illustrated {
            match &article.source_url {
                Some(url) => format!("  #{}\n", self.source_link_call(article, url)),
                None => String::new(),
            }
        } else {
            format!(
                "  #provenance{}\n",
                self.said(&format!(
                    "{}: {}",
                    self.ui("sources"),
                    article.source_ids.join(", ")
                ))
            )
        };
        format!(
            "#piece(\n  id: {},\n  kind: {},\n  short-title: {},\n  source-ids: {},\n  \
             figure-layouts: {},\n  opener: {},\n)[\n{label}  #piece-title{}\n  {}\n{note}\
             {provenance}",
            string_literal(&format!("article-{}", article.id)),
            string_literal(&article.content_mode),
            string_literal(&article.short_title),
            string_array(&article.source_ids),
            string_array(&figure_layouts(article)),
            string_literal(if illustrated { ILLUSTRATED } else { "plain" }),
            self.said(&article.title),
            self.byline(&article.author),
        )
    }

    fn article_body(&self, article: &Article, document: &Document, skip: usize) -> Result<String> {
        let (opener_figures, anchored_figures) = split_figures(&article.figures);
        let (opener_extracts, anchored_extracts) = split_extracts(&article.extracts);
        let mut out = String::new();
        for figure in &opener_figures {
            out.push_str(&self.figure(figure)?);
        }
        for extract in &opener_extracts {
            out.push_str(&self.extract(extract));
        }
        let mut references = false;
        for (position, block) in document.blocks.iter().enumerate().skip(skip) {
            if let Block::Heading { children, .. } = block {
                references = is_reference_heading(&inline_text(children));
            }
            out.push_str(&self.block(block, skip == 0 && position == 0, references));
            let Block::Heading { children, .. } = block else {
                continue;
            };
            let key = anchor_key(&inline_text(children));
            for figure in anchored_figures
                .iter()
                .filter(|figure| anchor_key(&figure.anchor) == key)
            {
                out.push_str(&self.figure(figure)?);
            }
            for extract in anchored_extracts
                .iter()
                .filter(|extract| anchor_key(&extract.anchor) == key)
            {
                out.push_str(&self.extract(extract));
            }
        }
        Ok(out)
    }

    fn key_ideas(&self, article: &Article) -> String {
        if article.key_ideas.is_empty() {
            return String::new();
        }
        let items: String = article
            .key_ideas
            .iter()
            .map(|idea| format!("  #key-idea{}\n", self.said(idea)))
            .collect();
        format!(
            "#key-ideas[\n  #key-ideas-label{}\n{items}]\n\n",
            self.said(&self.ui("key_ideas"))
        )
    }

    fn source_link(&self, article: &Article) -> String {
        match &article.source_url {
            None => String::new(),
            Some(url) => format!("#{}\n\n", self.source_link_call(article, url)),
        }
    }

    fn source_link_call(&self, article: &Article, url: &str) -> String {
        format!(
            "source-link(destination: {}, source-id: {}){}",
            string_literal(url),
            string_literal(article.source_ids.first().map(String::as_str).unwrap_or("")),
            self.verbatim(url),
        )
    }

    fn figure(&self, figure: &Figure) -> Result<String> {
        let (width, height) = pixels(&figure.path)?;
        Ok(format!(
            "#figure-block(\n  id: {},\n  source-id: {},\n  anchor: {},\n  layout: {},\n  \
             word: {},\n  alt: {},\n  pixels: ({width}, {height}),\n\
             )[#figure-caption{}#figure-credit{}]\n\n",
            string_literal(&figure.id),
            string_literal(&figure.source_id),
            string_literal(&figure.anchor),
            string_literal(&figure.layout),
            string_literal(&self.ui("figure")),
            string_literal(&figure.alt_text),
            self.said(&figure.caption),
            self.said(&figure.credit),
        ))
    }

    fn extract(&self, extract: &Extract) -> String {
        let body = if extract.style == "code" {
            raw_block(&fold_reader_characters(&extract.text, self.settable))
        } else {
            extract
                .text
                .split("\n\n")
                .map(str::trim)
                .filter(|paragraph| !paragraph.is_empty())
                .map(|paragraph| format!("  #quote-line{}\n", self.verbatim(paragraph)))
                .collect()
        };
        format!(
            "#extract(\n  id: {},\n  source-id: {},\n  anchor: {},\n  style: {},\n  word: {},\n)\
             [\n{body}  #extract-caption{}\n]\n\n",
            string_literal(&extract.id),
            string_literal(&extract.source_id),
            string_literal(&extract.anchor),
            string_literal(&extract.style),
            string_literal(&self.ui("verbatim")),
            self.said(&extract.caption),
        )
    }

    fn blocks(&self, blocks: &[Block], standfirst: bool) -> String {
        blocks
            .iter()
            .enumerate()
            .map(|(index, block)| self.block(block, standfirst && index == 0, false))
            .collect()
    }

    fn block(&self, block: &Block, standfirst: bool, references: bool) -> String {
        match block {
            Block::Heading { level, children } => format!(
                "#doc-heading(level: {level})[{}]\n\n",
                self.inlines(children)
            ),
            Block::Paragraph(children) => format!(
                "#doc-paragraph(standfirst: {standfirst}, roster: {})[{}]\n\n",
                is_name_roster(&inline_text(children)),
                self.inlines(children)
            ),
            Block::FencedCode { code, info } => format!(
                "#doc-code(lang: {})[\n{}]\n\n",
                string_literal(info.split_whitespace().next().unwrap_or("")),
                raw_block(&fold_reader_characters(code, self.settable)),
            ),
            Block::Quote(children) => {
                format!("#doc-quote[\n{}]\n\n", self.blocks(children, false))
            }
            Block::List {
                ordered,
                start,
                items,
            } => format!(
                "#doc-list(ordered: {ordered}, start: {start}, references: {references})[\n{}]\n\n",
                items
                    .iter()
                    .map(|item| format!("  #doc-item[\n{}]\n", self.blocks(item, false)))
                    .collect::<String>()
            ),
            Block::HorizontalRule => "#doc-rule()\n\n".to_string(),
        }
    }

    fn inlines(&self, inlines: &[Inline]) -> String {
        inlines.iter().map(|inline| self.inline(inline)).collect()
    }

    fn inline(&self, inline: &Inline) -> String {
        match inline {
            Inline::Text(value) => self.prose(value),
            Inline::Emphasis(children) => format!("#emph[{}]", self.inlines(children)),
            Inline::Strong(children) => format!("#strong[{}]", self.inlines(children)),
            Inline::Code(value) => format!("#inline-code{}", self.verbatim(value)),
            Inline::Link {
                destination,
                title,
                children,
            } => format!(
                "#doc-link(destination: {}, title: {})[{}]",
                string_literal(destination),
                title
                    .as_deref()
                    .map(string_literal)
                    .unwrap_or_else(|| "none".to_string()),
                self.inlines(children)
            ),
            Inline::LineBreak { hard } => {
                if *hard {
                    "\\\n".to_string()
                } else {
                    "\n".to_string()
                }
            }
        }
    }

    fn closing_plates(&self) -> String {
        self.edition
            .closing_plates
            .iter()
            .enumerate()
            .map(|(index, plate)| {
                format!(
                    "#closing-plate(index: {}, alt: {})\n",
                    index + 1,
                    string_literal(&plate.title)
                )
            })
            .collect()
    }
}

fn include_piece(files: &mut Vec<File>, path: String, source: String) -> String {
    let line = format!("#include \"/{path}\"\n");
    files.push(File { path, source });
    line
}

fn figure_layouts(article: &Article) -> Vec<String> {
    let mut layouts: Vec<String> = Vec::new();
    for figure in &article.figures {
        let layout = figure.layout.trim().to_string();
        if !layout.is_empty() && !layouts.contains(&layout) {
            layouts.push(layout);
        }
    }
    layouts
}

fn split_figures(figures: &[Figure]) -> (Vec<&Figure>, Vec<&Figure>) {
    figures.iter().partition(|f| f.anchor == OPENER_ANCHOR)
}

fn split_extracts(extracts: &[Extract]) -> (Vec<&Extract>, Vec<&Extract>) {
    extracts.iter().partition(|e| e.anchor == OPENER_ANCHOR)
}

fn inline_text(inlines: &[Inline]) -> String {
    inlines
        .iter()
        .map(|inline| match inline {
            Inline::Text(value) | Inline::Code(value) => value.clone(),
            Inline::Emphasis(children) | Inline::Strong(children) => inline_text(children),
            Inline::Link { children, .. } => inline_text(children),
            Inline::LineBreak { .. } => "\n".to_string(),
        })
        .collect()
}

fn split_words(inlines: &[Inline], mut remaining: usize) -> Option<(Vec<Inline>, Vec<Inline>)> {
    if remaining == 0 {
        return None;
    }
    for (index, inline) in inlines.iter().enumerate() {
        let Inline::Text(value) = inline else {
            let words = inline_text(std::slice::from_ref(inline))
                .split_whitespace()
                .count();
            if remaining == 0 || words > remaining {
                return Some((inlines[..index].to_vec(), inlines[index..].to_vec()));
            }
            remaining -= words;
            continue;
        };
        let starts = value.char_indices().filter(|(at, c)| {
            !c.is_whitespace()
                && value[..*at]
                    .chars()
                    .next_back()
                    .is_none_or(char::is_whitespace)
        });
        for (at, _) in starts {
            if remaining == 0 {
                let mut kept = inlines[..index].to_vec();
                kept.push(Inline::Text(value[..at].trim_end().to_string()));
                let mut moved = vec![Inline::Text(value[at..].to_string())];
                moved.extend_from_slice(&inlines[index + 1..]);
                return Some((kept, moved));
            }
            remaining -= 1;
        }
    }
    None
}

fn read_manuscript(path: &Path) -> Result<Document> {
    let text = std::fs::read_to_string(path).map_err(|error| {
        ValidationError::one(format!("Cannot read {}: {error}", path.display()))
    })?;
    parse_publication_document(&text).map_err(refusal)
}

pub fn escape_markup(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for character in text.chars() {
        if character.is_ascii_punctuation() {
            out.push('\\');
        }
        out.push(character);
    }
    out
}

pub fn string_literal(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for character in value.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            other => out.push(other),
        }
    }
    out.push('"');
    out
}

fn string_array(values: &[String]) -> String {
    if values.is_empty() {
        return "()".to_string();
    }
    format!(
        "({},)",
        values
            .iter()
            .map(|value| string_literal(value))
            .collect::<Vec<String>>()
            .join(", ")
    )
}

pub fn raw_block(code: &str) -> String {
    let mut fence = "`".repeat(3);
    while code.contains(&fence) {
        fence.push('`');
    }
    format!("{fence}\n{code}\n{fence}\n")
}

pub fn project(tree: &Tree) -> Result<Projection> {
    let main = tree
        .get(MAIN)
        .ok_or_else(|| ValidationError::one(format!("the source tree has no {MAIN}")))?;
    let mut walker = Walker {
        tree,
        raw: String::new(),
        verbatim: Vec::new(),
        depth: 0,
    };
    walker.file(main)?;
    Ok(Projection {
        text: normalize_reader_text(&walker.raw),
        verbatim: walker.verbatim,
    })
}

struct Walker<'a> {
    tree: &'a Tree,
    raw: String,
    verbatim: Vec<String>,
    depth: usize,
}

impl Walker<'_> {
    fn file(&mut self, file: &File) -> Result<()> {
        self.depth += 1;
        if self.depth > 8 {
            return Err(ValidationError::one(format!(
                "include depth exceeded at {}",
                file.path
            )));
        }
        let root = typst_syntax::parse(&file.source);
        let (errors, _) = root.errors_and_warnings();
        if let Some(first) = errors.first() {
            return Err(ValidationError::one(format!(
                "{} is not valid Typst: {}",
                file.path, first.message
            )));
        }
        self.node(&root, true, &file.path)?;
        self.depth -= 1;
        Ok(())
    }

    fn node(&mut self, node: &SyntaxNode, markup: bool, origin: &str) -> Result<()> {
        let kind = node.kind();
        if kind == SyntaxKind::ModuleInclude {
            return self.include(node, origin);
        }
        if kind == SyntaxKind::Raw {
            let text = raw_text(node);
            self.raw.push('\n');
            self.raw.push_str(&text);
            self.raw.push('\n');
            self.verbatim.push(text);
            return Ok(());
        }
        if node.children().len() == 0 {
            return self.leaf(kind, node.leaf_text(), markup, origin);
        }
        let inner = match kind {
            SyntaxKind::Markup => true,
            SyntaxKind::Code
            | SyntaxKind::CodeBlock
            | SyntaxKind::Args
            | SyntaxKind::Array
            | SyntaxKind::Dict
            | SyntaxKind::Named
            | SyntaxKind::FuncCall
            | SyntaxKind::ModuleImport
            | SyntaxKind::ImportItems
            | SyntaxKind::Parenthesized => false,
            _ => markup,
        };
        for child in node.children() {
            self.node(child, inner, origin)?;
        }
        Ok(())
    }

    fn include(&mut self, node: &SyntaxNode, origin: &str) -> Result<()> {
        let target = node
            .children()
            .find(|child| child.kind() == SyntaxKind::Str)
            .map(|child| {
                child
                    .leaf_text()
                    .trim_matches('"')
                    .trim_start_matches('/')
                    .to_string()
            })
            .ok_or_else(|| {
                ValidationError::one(format!("{origin} has an include with no path string"))
            })?;
        let file = self.tree.get(&target).ok_or_else(|| {
            ValidationError::one(format!("{origin} includes {target}, which the tree lacks"))
        })?;
        self.file(file)
    }

    fn leaf(&mut self, kind: SyntaxKind, text: &str, markup: bool, origin: &str) -> Result<()> {
        if !markup {
            return Ok(());
        }
        match kind {
            SyntaxKind::Text | SyntaxKind::Space | SyntaxKind::Parbreak => self.raw.push_str(text),
            SyntaxKind::Linebreak => self.raw.push('\n'),
            SyntaxKind::Escape => self.raw.push(decode_escape(text)?),
            SyntaxKind::Hash | SyntaxKind::End => {}
            other => {
                return Err(ValidationError::one(format!(
                    "{origin} carries unprojectable markup {other:?} ({text:?}); the emitter \
                     must produce escaped text, raw blocks and function calls only"
                )))
            }
        }
        Ok(())
    }
}

fn raw_text(node: &SyntaxNode) -> String {
    node.children()
        .filter(|child| child.kind() == SyntaxKind::Text)
        .map(|child| child.leaf_text().to_string())
        .collect::<Vec<String>>()
        .join("\n")
}

fn decode_escape(text: &str) -> Result<char> {
    let body = text.strip_prefix('\\').ok_or_else(|| {
        ValidationError::one(format!("escape {text:?} does not start with a backslash"))
    })?;
    if let Some(hex) = body
        .strip_prefix("u{")
        .and_then(|rest| rest.strip_suffix('}'))
    {
        return u32::from_str_radix(hex, 16)
            .ok()
            .and_then(char::from_u32)
            .ok_or_else(|| ValidationError::one(format!("escape {text:?} is not a codepoint")));
    }
    body.chars()
        .next()
        .ok_or_else(|| ValidationError::one(format!("escape {text:?} carries no character")))
}

pub fn normalize_reader_text(raw: &str) -> String {
    let composed: String = raw.nfc().collect();
    let rejoined = rejoin_hyphenated_words(&composed);
    let stripped: String = rejoined.chars().filter(|c| *c != '\u{ad}').collect();
    stripped.split_whitespace().collect::<Vec<&str>>().join(" ")
}

fn rejoin_hyphenated_words(text: &str) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len());
    let mut index = 0;
    while index < chars.len() {
        let hyphenated = matches!(chars[index], '-' | '\u{ad}' | '\u{2010}')
            && index > 0
            && chars[index - 1].is_alphabetic()
            && chars.get(index + 1) == Some(&'\n')
            && chars.get(index + 2).is_some_and(|c| c.is_alphabetic());
        if hyphenated {
            index += 2;
            continue;
        }
        out.push(chars[index]);
        index += 1;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::shared::ROSTER_CLAMP_LIMIT;
    use std::path::PathBuf;

    const PUBLICATION: &str = "Fixture Press";

    fn repository() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("the crate sits inside the repository")
            .to_path_buf()
    }

    fn fonts() -> PathBuf {
        repository().join("src/magazine/assets/fonts")
    }

    fn fixtures() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/typeset_fixtures")
    }

    fn corpus() -> PathBuf {
        fixtures().join("corpus")
    }

    fn settable() -> BTreeSet<u32> {
        settable_codepoints(&fonts()).expect("the reader faces are readable")
    }

    fn inputs(root: &Path, edition_id: &str) -> Inputs<'static> {
        let root: &'static Path = Box::leak(root.to_path_buf().into_boxed_path());
        Inputs {
            root,
            edition_id: Box::leak(edition_id.to_string().into_boxed_str()),
            publication_name: PUBLICATION,
            fonts: Box::leak(fonts().into_boxed_path()),
            allow_missing_art: false,
            allow_unanchored_figures: false,
        }
    }

    fn oracle(edition_id: &str) -> serde_json::Value {
        let path = fixtures().join(format!("expected-{edition_id}.json"));
        serde_json::from_str(&std::fs::read_to_string(&path).expect("the oracle dump is readable"))
            .expect("the oracle dump is JSON")
    }

    fn copy_tree(from: &Path, to: &Path) {
        std::fs::create_dir_all(to).expect("the destination is creatable");
        for entry in std::fs::read_dir(from).expect("the fixture is readable") {
            let entry = entry.expect("the entry is readable");
            let target = to.join(entry.file_name());
            if entry.file_type().expect("the kind is readable").is_dir() {
                copy_tree(&entry.path(), &target);
            } else {
                std::fs::copy(entry.path(), &target).expect("the file is copyable");
            }
        }
    }

    fn mutated(case: &str, edition_id: &str, edits: &[(&str, &str)]) -> PathBuf {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("the clock is after the epoch")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("mag-typeset-{case}-{stamp}"));
        copy_tree(&corpus(), &root);
        let manifest = root.join("editions").join(edition_id).join("edition.yaml");
        let mut text = std::fs::read_to_string(&manifest).expect("the manifest is readable");
        for (from, to) in edits {
            assert!(
                text.contains(from),
                "the fixture no longer carries {from:?}, so case {case} would not bite"
            );
            text = text.replace(from, to);
        }
        std::fs::write(&manifest, text).expect("the manifest is writable");
        root
    }

    fn refusal_of(root: &Path, edition_id: &str) -> String {
        match pipeline(&inputs(root, edition_id)) {
            Ok(_) => panic!("the pipeline accepted inputs the oracle refuses"),
            Err(error) => error.to_string(),
        }
    }

    fn projection_of(root: &Path, edition_id: &str) -> Projection {
        let tree = pipeline(&inputs(root, edition_id)).expect("the fixture edition loads");
        project(&tree).expect("the emitted tree projects")
    }

    fn compare(edition_id: &str, projection: &Projection) {
        let expected = oracle(edition_id);
        assert_eq!(
            projection.text,
            expected["text"].as_str().expect("the oracle carries text"),
            "edition {edition_id} projection differs from the Python oracle"
        );
        let want: Vec<String> = expected["verbatim"]
            .as_array()
            .expect("the oracle carries verbatim runs")
            .iter()
            .map(|run| run.as_str().expect("a run is a string").to_string())
            .collect();
        let got: Vec<String> = projection
            .verbatim
            .iter()
            .map(|run| run.trim_end_matches('\n').to_string())
            .collect();
        let want: Vec<String> = want
            .iter()
            .map(|run| run.trim_end_matches('\n').to_string())
            .collect();
        assert_eq!(got, want, "edition {edition_id} verbatim runs differ");
    }

    #[test]
    fn the_plain_opener_fixture_projects_to_the_python_text() {
        let root = corpus();
        compare("900", &projection_of(&root, "900"));
    }

    #[test]
    fn the_illustrated_opener_fixture_projects_to_the_python_text() {
        let root = corpus();
        compare("901", &projection_of(&root, "901"));
    }

    #[test]
    fn every_extract_run_is_byte_exact_against_the_captured_source() {
        let root = corpus();
        let tree = pipeline(&inputs(&root, "900")).expect("the fixture edition loads");
        let projection = project(&tree).expect("the emitted tree projects");
        let captured =
            std::fs::read_to_string(root.join("library/sources/fixture-source-a/article.md"))
                .expect("the captured source is readable");
        let code_run = projection
            .verbatim
            .iter()
            .find(|run| run.contains("BEGIN-CODE"))
            .expect("the code extract reached the projection");
        let code_run = code_run.trim_end_matches('\n');
        assert!(
            captured.contains(code_run),
            "the extract run is not a contiguous run of the captured source"
        );
        assert!(
            projection
                .text
                .contains("And it ends on this line, verbatim."),
            "the quote extract reached the reader text"
        );
    }

    #[test]
    fn the_live_edition_projection_matches_the_oracle() {
        let root = std::env::var("MAG_TYPESET_ROOT").ok();
        let dump = std::env::var("MAG_TYPESET_ORACLE").ok();
        let publication = std::env::var("MAG_TYPESET_PUBLICATION").ok();
        let (root, dump, publication) = match (root, dump, publication) {
            (None, None, None) => {
                println!(
                    "skipped, env not set: MAG_TYPESET_ROOT, MAG_TYPESET_ORACLE and \
                     MAG_TYPESET_PUBLICATION select the staged live edition"
                );
                return;
            }
            (Some(root), Some(dump), Some(publication)) => (root, dump, publication),
            _ => panic!(
                "MAG_TYPESET_ROOT, MAG_TYPESET_ORACLE and MAG_TYPESET_PUBLICATION must be \
                 set together"
            ),
        };
        let edition_id = std::env::var("MAG_TYPESET_EDITION").unwrap_or_else(|_| "010".to_string());
        let root = PathBuf::from(root);
        let leaked: &'static Path = Box::leak(root.clone().into_boxed_path());
        let tree = pipeline(&Inputs {
            root: leaked,
            edition_id: Box::leak(edition_id.clone().into_boxed_str()),
            publication_name: Box::leak(publication.into_boxed_str()),
            fonts: Box::leak(fonts().into_boxed_path()),
            allow_missing_art: false,
            allow_unanchored_figures: false,
        })
        .expect("the staged live edition loads");
        let projection = project(&tree).expect("the emitted tree projects");
        let expected: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&dump).expect("the oracle is readable"))
                .expect("the oracle is JSON");
        let want = expected["text"].as_str().expect("the oracle carries text");
        assert!(
            want.len() > 10_000,
            "the live oracle carries {} characters, too few to be edition {edition_id}",
            want.chars().count()
        );
        assert_eq!(
            projection.text, want,
            "compared the live edition: projection differs from the Python oracle"
        );
        println!(
            "compared the live edition: {} characters of reader text, {} verbatim runs",
            projection.text.chars().count(),
            projection.verbatim.len()
        );
    }

    #[test]
    fn an_ambiguous_begin_marker_is_refused() {
        let root = mutated(
            "ambiguous-begin",
            "900",
            &[("begin: BEGIN-CODE", "begin: AMBIGUOUS")],
        );
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("begin marker must occur exactly once in the source (found 2)"),
            "{message}"
        );
    }

    #[test]
    fn a_begin_marker_that_is_absent_is_refused() {
        let root = mutated(
            "missing-begin",
            "900",
            &[("begin: BEGIN-CODE", "begin: NO-SUCH-MARKER")],
        );
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("begin marker must occur exactly once in the source (found 0)"),
            "{message}"
        );
    }

    #[test]
    fn an_ambiguous_end_marker_is_refused() {
        let root = mutated(
            "ambiguous-end",
            "900",
            &[("end: END-CODE", "end: AMBIGUOUS")],
        );
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("end marker must occur exactly once at or after begin (found 2)"),
            "{message}"
        );
    }

    #[test]
    fn a_run_already_in_the_manuscript_is_refused() {
        let root = mutated("verbatim-run", "900", &[]);
        let manuscript = root.join("editions/900/articles/plain-opener-article.md");
        let mut text = std::fs::read_to_string(&manuscript).expect("the manuscript is readable");
        text.push_str(
            "\nBEGIN-CODE\nbudget = lambda tokens: tokens // 4\nceiling = budget(4096)\nEND-CODE\n",
        );
        std::fs::write(&manuscript, text).expect("the manuscript is writable");
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("run already appears verbatim in the manuscript"),
            "{message}"
        );
    }

    #[test]
    fn an_extract_naming_a_source_the_article_does_not_carry_is_refused() {
        let root = mutated(
            "unknown-source",
            "900",
            &[(
                "    source_id: fixture-source-a\n    begin: BEGIN-CODE",
                "    source_id: fixture-source-b\n    begin: BEGIN-CODE",
            )],
        );
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("source_id must be one of the article source_ids"),
            "{message}"
        );
    }

    #[test]
    fn a_figure_path_escaping_the_source_directory_is_refused() {
        let root = mutated(
            "escaping-figure",
            "900",
            &[("path: media/diagram.png", "path: ../../../etc/passwd")],
        );
        let message = refusal_of(&root, "900");
        assert!(message.contains("has unsafe path:"), "{message}");
    }

    #[test]
    fn the_extract_maximum_straddles_two_and_three() {
        let fits = corpus();
        let tree = pipeline(&inputs(&fits, "900"));
        assert!(tree.is_ok(), "two extracts must be accepted");
        let root = mutated(
            "three-extracts",
            "900",
            &[("  - id: budget-code\n", "  - id: budget-third\n    source_id: fixture-source-a\n    begin: BEGIN-CODE\n    end: END-CODE\n    style: code\n    caption: A third extract.\n    anchor: Budgets\n  - id: budget-code\n")],
        );
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("selects 3 extracts; maximum is 2"),
            "{message}"
        );
    }

    #[test]
    fn the_contents_title_limit_straddles_sixty_two_and_sixty_three() {
        let stem = "Plain Opener";
        let at_limit = format!(
            "{stem}{}",
            " A".repeat((CONTENTS_TITLE_LIMIT - stem.len()) / 2)
        );
        let over = format!("{at_limit} A");
        assert_eq!(at_limit.chars().count(), CONTENTS_TITLE_LIMIT);
        assert_eq!(over.chars().count(), CONTENTS_TITLE_LIMIT + 2);
        let fitting = mutated(
            "title-62",
            "900",
            &[(
                "  title: A Plain Opener Article",
                &format!("  title: {at_limit}"),
            )],
        );
        if let Err(error) = pipeline(&inputs(&fitting, "900")) {
            panic!("a {CONTENTS_TITLE_LIMIT}-character title must be accepted: {error}");
        }
        let refusing = mutated(
            "title-63",
            "900",
            &[(
                "  title: A Plain Opener Article",
                &format!("  title: {over}"),
            )],
        );
        let message = refusal_of(&refusing, "900");
        assert!(
            message.contains("would wrap onto the entry's author line"),
            "{message}"
        );
        assert!(
            message.contains(&format!("({} characters)", CONTENTS_TITLE_LIMIT + 2)),
            "{message}"
        );
    }

    #[test]
    fn the_roster_clamp_straddles_fifty_four_and_fifty_five() {
        let at_limit: String = std::iter::repeat_n('a', ROSTER_CLAMP_LIMIT).collect();
        assert_eq!(clamp_roster(&at_limit), at_limit);
        let over = format!("{at_limit}a");
        assert_ne!(clamp_roster(&over), over);
        assert!(clamp_roster(&over).ends_with(" et al."));
        let names = "Ada Fixture, Bo Fixture, Cy Fixture, Di Fixture, Eve Fixture, Fay";
        assert!(names.chars().count() > ROSTER_CLAMP_LIMIT);
        assert_eq!(
            clamp_roster(names),
            "Ada Fixture, Bo Fixture, Cy Fixture et al."
        );
    }

    #[test]
    fn the_roster_test_straddles_its_name_and_word_counts() {
        assert!(!is_name_roster("Ada Fixture \u{2022} Bo Fixture"));
        assert!(is_name_roster(
            "Ada Fixture \u{2022} Bo Fixture \u{2022} Cy Fixture"
        ));
        let six = "a b c d e f";
        let seven = "a b c d e f g";
        assert!(is_name_roster(&format!(
            "{six} \u{2022} {six} \u{2022} {six}"
        )));
        assert!(!is_name_roster(&format!(
            "{six} \u{2022} {seven} \u{2022} {six}"
        )));
    }

    #[test]
    fn escaping_round_trips_every_text_atom_the_fixtures_carry() {
        let settable = settable();
        let mut atoms: Vec<String> = vec![
            "plain words".to_string(),
            "#hash $dollar *star _under `tick [bracket] <angle> @at =eq ~tilde +plus -dash /slash"
                .to_string(),
            "-- en dash shorthand and ... an ellipsis".to_string(),
            "1. not a list item".to_string(),
            "a\\backslash and \"quotes\" and 'apostrophes'".to_string(),
            "https://example.invalid/path?a=b&c=d".to_string(),
        ];
        for edition in ["900", "901"] {
            let tree = pipeline(&inputs(&corpus(), edition)).expect("the fixture loads");
            for file in &tree.files {
                atoms.push(file.source.clone());
            }
        }
        for atom in &atoms[..6] {
            let source = format!("{}\n", escape_markup(atom));
            let tree = Tree {
                files: vec![File {
                    path: MAIN.to_string(),
                    source,
                }],
            };
            let projected = project(&tree).expect("the escaped atom projects");
            assert_eq!(
                projected.text,
                normalize_reader_text(atom),
                "escaping did not round trip {atom:?}"
            );
        }
        let _ = settable;
    }

    #[test]
    fn the_projection_refuses_markup_it_cannot_account_for() {
        let tree = Tree {
            files: vec![File {
                path: MAIN.to_string(),
                source: "= A Typst heading the emitter never writes\n".to_string(),
            }],
        };
        let Err(error) = project(&tree) else {
            panic!("unescaped markup must refuse rather than project silently");
        };
        assert!(
            error.to_string().contains("unprojectable markup"),
            "{error}"
        );
    }

    #[test]
    fn a_standfirst_splits_at_its_word_budget_and_moves_an_unfitting_inline_whole() {
        let text = |v: &str| Inline::Text(v.to_string());
        let run = [
            text("one two "),
            Inline::Code("three four".into()),
            text(" five six"),
        ];
        let (kept, moved) = split_words(&run, 1).expect("one word splits");
        assert_eq!(
            (kept, moved),
            (
                vec![text("one")],
                vec![text("two "), run[1].clone(), run[2].clone()]
            )
        );
        let (kept, moved) = split_words(&run, 3).expect("the code does not fit");
        assert_eq!((kept, moved), (run[..1].to_vec(), run[1..].to_vec()));
        let (kept, moved) = split_words(&run, 5).expect("five of six words");
        assert_eq!(kept, vec![text("one two "), run[1].clone(), text(" five")]);
        assert_eq!(moved, vec![text("six")]);
        assert_eq!(split_words(&run, 6), None);
        assert_eq!(split_words(&run, 0), None);
    }

    #[test]
    fn the_emitted_tree_is_deterministic_and_includes_every_piece() {
        let root = corpus();
        let first = pipeline(&inputs(&root, "900")).expect("the fixture loads");
        let second = pipeline(&inputs(&root, "900")).expect("the fixture loads");
        assert_eq!(first, second, "two builds of one edition differ");
        let main = first.get(MAIN).expect("the tree carries main.typ");
        for file in &first.files {
            if file.path == MAIN {
                continue;
            }
            assert!(
                main.source.contains(&format!("\"/{}\"", file.path)),
                "main.typ does not include {}",
                file.path
            );
        }
        assert_eq!(
            first.files.len(),
            5,
            "editorial, two articles and a section"
        );
    }
}
