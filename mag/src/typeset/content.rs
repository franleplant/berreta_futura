use crate::model::doc::{
    educate_reader_quotes, fold_reader_characters, inline_text, is_settable,
    parse_publication_document, settable_codepoints, Block, Document, Inline,
};
use crate::model::manifest::{source_code_payload, Article, Edition, Editorial, Section};
use crate::model::records::{Extract, Figure};
use crate::model::shared::{
    anchor_key, article_opener_format, clamp_roster, content_label, is_name_roster,
    is_reference_heading, quoted, scalar_label, show, text, ui, Result, ValidationError,
};
use crate::sourcecodes::source_code_directory;
use crate::typeset::estimate::Metrics;
use crate::typeset::hyphen::{Hyphenation, Hyphenator};
use crate::typeset::media::pixels;
use std::cell::Cell;
use std::collections::BTreeSet;
use std::path::Path;
use typst_syntax::{SyntaxKind, SyntaxNode};
use unicode_normalization::UnicodeNormalization;

pub const CONTENTS_TITLE_LIMIT: usize = 62;
pub const CONTENTS_TIGHT_ABOVE: usize = 8;
const ILLUSTRATED: &str = "illustrated_paper_spots_v1";
const OPENER_ANCHOR: &str = "__opener__";
const MAIN: &str = "main.typ";
const CODE_INKS: [(&str, &str); 7] = [
    ("k kc kd kn kp kr ow", "rgb(240 87 56)"),
    ("kt", "rgb(25% 10% 43%)"),
    ("s s1 s2 sb sd se si sr ss sa", "rgb(9% 33% 20%)"),
    ("c c1 cm cs cp cpf", "rgb(46% 45% 48%)"),
    ("m mi mf mh mo mb il", "rgb(45% 12% 16%)"),
    ("nf fm nc nn nd", "rgb(11% 22% 55%)"),
    ("nb bp nt", "rgb(11% 22% 55%)"),
];

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

#[cfg(test)]
pub struct Inputs<'a> {
    pub root: &'a Path,
    pub edition_id: &'a str,
    pub publication_name: &'a str,
    pub fonts: &'a Path,
    pub allow_missing_art: bool,
    pub allow_unanchored_figures: bool,
}

#[cfg(test)]
pub fn pipeline(inputs: &Inputs) -> Result<Tree> {
    use crate::model::manifest::{load_edition, LoadOptions, Records};
    let records: Records =
        crate::model::records::load_records(&inputs.root.join("library").join("sources"))?
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
    compose(&edition, inputs.fonts, Hyphenation::PLAIN, &[])
}

pub fn compose(
    edition: &Edition,
    fonts: &Path,
    hyphenation: Hyphenation,
    keeps: &[Option<usize>],
) -> Result<Tree> {
    let settable = settable_codepoints(fonts).map_err(|error| refusal(&error))?;
    let tree = Writer {
        edition,
        metrics: &Metrics::load(fonts)?,
        keeps,
        standfirsts: Cell::new(0),
        illustrated: article_opener_format(&edition.raw) == ILLUSTRATED,
        native: hyphenation.native(&edition.locale),
        hyphenator: Hyphenator::for_locale(&edition.locale)
            .transpose()
            .map_err(ValidationError::one)?,
    }
    .tree()?;
    let misses: Vec<String> = tree
        .files
        .iter()
        .flat_map(|file| unsettable_in(file, &settable))
        .collect();
    if misses.is_empty() {
        Ok(tree)
    } else {
        Err(ValidationError(misses))
    }
}

pub fn unsettable_in(file: &File, settable: &BTreeSet<u32>) -> Vec<String> {
    let piece = file
        .path
        .strip_prefix("pieces/article-")
        .and_then(|rest| rest.get(3..)?.strip_suffix(".typ"))
        .map_or_else(|| file.path.clone(), |id| format!("article {id}"));
    let mut seen = BTreeSet::new();
    file.source
        .char_indices()
        .filter(|&(_, character)| !is_settable(character, settable) && seen.insert(character))
        .map(|(at, character)| {
            let before: Vec<char> = file.source[..at].chars().rev().take(40).collect();
            let near: String = before
                .into_iter()
                .rev()
                .chain(file.source[at..].chars().take(41))
                .collect();
            format!(
                "U+{:04X} {character:?} has no glyph in any bundled font: {piece}, near {:?}",
                character as u32,
                near.replace('\\', "").replace('\n', " "),
            )
        })
        .collect()
}

fn refusal(error: &anyhow::Error) -> ValidationError {
    ValidationError::one(format!("{error:#}"))
}

struct Writer<'a> {
    edition: &'a Edition,
    metrics: &'a Metrics,
    keeps: &'a [Option<usize>],
    standfirsts: Cell<usize>,
    illustrated: bool,
    native: bool,
    hyphenator: Option<Hyphenator>,
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
        escape_markup(&fold_reader_characters(&educate_reader_quotes(value)))
    }

    fn hyphenated(&self, value: &str) -> String {
        self.hyphenable(&fold_reader_characters(&educate_reader_quotes(value)))
    }

    fn hyphenable(&self, folded: &str) -> String {
        match (&self.hyphenator, self.native) {
            (Some(hyphenator), _) => escape_markup(&hyphenator.text(folded)),
            (None, true) => format!("#text(hyphenate: true)[{}]", escape_markup(folded)),
            (None, false) => escape_markup(folded),
        }
    }

    fn body(&self, value: &str) -> String {
        format!("[{}]", self.hyphenated(value))
    }

    fn verbatim_body(&self, value: &str) -> String {
        format!("[{}]", self.hyphenable(&fold_reader_characters(value)))
    }

    fn literal(&self, value: &str) -> String {
        escape_markup(&fold_reader_characters(value))
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
        main.push_str(&self.closing_plates()?);
        main.push_str(&self.contents()?);
        if let Some(editorial) = &self.edition.editorial {
            let document = read_manuscript(&editorial.path)?;
            main.push_str(&include_piece(
                &mut files,
                "pieces/editorial.typ".to_string(),
                self.editorial(editorial, &document)?,
            ));
        }
        for (index, article) in self.edition.articles.iter().enumerate() {
            let document = read_manuscript(&article.manuscript)?;
            main.push_str(&include_piece(
                &mut files,
                format!("pieces/article-{:02}-{}.typ", index + 1, article.id),
                self.article(article, &document, index + 1)?,
            ));
            main.push_str(&format!(
                "#plates-after({}, of: {})\n",
                index + 1,
                self.edition.articles.len()
            ));
        }
        for (index, section) in self.edition.sections.iter().enumerate() {
            let document = read_manuscript(&section.path)?;
            main.push_str(&include_piece(
                &mut files,
                format!("pieces/section-{index}.typ"),
                self.section_piece(index, section, &document)?,
            ));
        }
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
        let subtitle = text(edition.raw.get("subtitle")).trim().to_string();
        format!(
            "#set document(title: {})\n#set text({})\n\n#edition-header[\n  #publication-name{}\n  \
             #issue-line{}\n  #edition-title{}\n{}  #edition-date{}\n]\n\n",
            string_literal(&format!("{}: {}", edition.publication_name, edition.title)),
            text_locale(&edition.locale),
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
                    quoted(&entry.title),
                    entry.title.chars().count()
                )
            })
            .collect();
        if !refusals.is_empty() {
            return Err(ValidationError(refusals));
        }
        let tight = entries.len() > CONTENTS_TIGHT_ABOVE;
        let rows: String = entries
            .iter()
            .map(|entry| {
                format!(
                    "  #contents-entry(destination: {})[{}#entry-title{}{}]\n",
                    string_literal(&entry.destination),
                    match tight {
                        true => String::new(),
                        false => format!("#entry-label{}", self.said(&entry.label)),
                    },
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
            "#contents(tight: {tight})[\n  #contents-kicker{}\n  #contents-label{}\n{rows}]\n\n",
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

    fn editorial(&self, editorial: &Editorial, document: &Document) -> Result<String> {
        let (size, field) = self.metrics.editorial_opener(&editorial.title)?;
        let title = fold_reader_characters(&educate_reader_quotes(&editorial.title));
        Ok(format!(
            "#piece(\n  id: {},\n  kind: {},\n  short-title: {},\n)[\n\
             #plain-opener(size: {size}pt, field: {field}pt, title: {}, wide: true)[\n  \
             #content-label[#label-primary{}]\n  #piece-title{}\n  {}\n]\n{}]\n",
            string_literal("editorial"),
            string_literal("original_editorial"),
            string_literal(&self.ui("editorial")),
            string_literal(&title),
            self.said(&editorial.label),
            self.said(&editorial.title),
            self.byline(&editorial.byline),
            self.blocks(&document.blocks, true, false)?,
        ))
    }

    fn section_piece(
        &self,
        index: usize,
        section: &Section,
        document: &Document,
    ) -> Result<String> {
        Ok(format!(
            "#piece(\n  id: {},\n  kind: {},\n  short-title: {},\n)[\n  \
             #content-label[#label-primary{}]\n  #piece-title{}\n{}]\n",
            string_literal(&format!("section-{index}")),
            string_literal(&section.kind),
            string_literal(&section.title),
            self.said(&self.ui(&section.kind)),
            self.said(&section.title),
            self.blocks(&document.blocks, true, false)?,
        ))
    }

    fn byline(&self, name: &str) -> String {
        self.coded_byline(name, "none")
    }

    fn coded_byline(&self, name: &str, code: &str) -> String {
        format!(
            "#byline(code: {code})[#byline-prefix{}#byline-name{}]",
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
        let (mut out, trim) = self.article_head(article, document, index, illustrated)?;
        if !illustrated {
            out.push_str("  #opener-end()\n");
        }
        if let (true, Some(block)) = (illustrated, document.blocks.first()) {
            out.push_str(&self.standfirst(block)?);
        }
        out.push_str(&self.article_body(article, document, (usize::from(illustrated), trim))?);
        out.push_str(&self.key_ideas(article));
        out.push_str(&format!(
            "#end-mark{}\n\n",
            self.said(&format!("{} / {index:02}", self.ui("end")))
        ));
        if let Some(path) = &article.tail_art {
            out.push_str(&self.tail_art(article, path)?);
        }
        if !illustrated {
            out.push_str(&self.source_link(article));
        }
        out.push_str("]\n");
        Ok(out)
    }

    fn standfirst(&self, block: &Block) -> Result<String> {
        let Block::Paragraph(children) = block else {
            return self.markup_block(block, true, false, false);
        };
        let ordinal = self.standfirsts.replace(self.standfirsts.get() + 1);
        let keep = self.keeps.get(ordinal).copied().flatten().unwrap_or(0);
        let Some((kept, moved)) = split_segments(children, keep) else {
            return self.markup_block(block, true, false, false);
        };
        Ok(format!(
            "#doc-paragraph(standfirst: true, roster: {}, split: true)[{}]\n\n\
             #doc-paragraph(standfirst: false, roster: false)[{}]\n\n",
            is_name_roster(&inline_text(children)),
            self.inlines(&kept),
            self.flowing(&moved, true),
        ))
    }

    fn article_head(
        &self,
        article: &Article,
        document: &Document,
        index: usize,
        illustrated: bool,
    ) -> Result<(String, f64)> {
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
        let rows = match (&article.source_url, illustrated) {
            (Some(url), false) => Some(source_rows(article, url)?),
            _ => None,
        };
        let code = rows.as_deref().map_or("none".to_string(), string_array);
        let figure = !split_figures(&article.figures).0.is_empty();
        let note = match article.author_note.is_empty() || (figure && !illustrated) {
            true => String::new(),
            false => format!(
                "  #author-note(code: {code}){}\n",
                self.said(&article.author_note)
            ),
        };
        let provenance = if illustrated {
            match &article.source_url {
                Some(url) => format!(
                    "  #{}\n",
                    self.source_link_call(article, url, &source_code(article, url)?)
                ),
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
        let art = match (&article.opener_art, illustrated) {
            (Some(art), true) => {
                let (width, height) = pixels(&art.path)?;
                format!(
                    "(path: {}, pixels: ({width}, {height}))",
                    path_literal(&art.path)
                )
            }
            _ => "none".to_string(),
        };
        let titles = match illustrated {
            true => {
                let [(size, lines), (compact, rows)] =
                    self.metrics.illustrated_titles(&article.title)?;
                format!("((size: {size}pt, lines: {lines}), (size: {compact}pt, lines: {rows}))")
            }
            false => "none".to_string(),
        };
        let (head, foot, trim) = match illustrated {
            true => (String::new(), "", 0.0),
            false => self.plain_head(article, rows.as_ref().map(Vec::len), figure)?,
        };
        let head = format!(
            "#piece(\n  id: {},\n  kind: {},\n  short-title: {},\n  source-ids: {},\n  \
             figure-layouts: {},\n  opener: {},\n  art: {art},\n  titles: {titles},\n)[\n{head}{label}  #piece-title{}\n  {}\n\
             {note}{provenance}{foot}",
            string_literal(&format!("article-{}", article.id)),
            string_literal(&article.content_mode),
            string_literal(&article.short_title),
            string_array(&article.source_ids),
            string_array(&figure_layouts(article)),
            string_literal(if illustrated { ILLUSTRATED } else { "plain" }),
            self.said(&article.title),
            self.coded_byline(&article.author, &code),
        );
        Ok((head, trim))
    }

    fn plain_head(
        &self,
        article: &Article,
        rows: Option<usize>,
        figure: bool,
    ) -> Result<(String, &'static str, f64)> {
        let opener = self.metrics.plain_opener(
            &article.title,
            &format!("{} {}", self.ui("by"), article.author),
            &article.author_note,
            rows,
            figure,
        )?;
        let title = fold_reader_characters(&educate_reader_quotes(&article.title));
        Ok((
            format!(
                "#plain-opener(size: {}pt, field: {}pt, tracking: {}pt, title: {})[\n",
                opener.size,
                opener.field,
                opener.tracking,
                string_literal(&title)
            ),
            "]\n",
            opener.trim,
        ))
    }

    fn article_body(
        &self,
        article: &Article,
        document: &Document,
        (skip, trim): (usize, f64),
    ) -> Result<String> {
        let (opener_figures, anchored_figures) = split_figures(&article.figures);
        let (opener_extracts, anchored_extracts) = split_extracts(&article.extracts);
        let mut out = String::new();
        for figure in &opener_figures {
            out.push_str(&self.figure(figure, trim)?);
        }
        for extract in &opener_extracts {
            out.push_str(&self.extract(extract));
        }
        let mut references = false;
        let standfirst = skip == 0 && matches!(document.blocks.first(), Some(Block::Paragraph(_)));
        for (position, block) in document.blocks.iter().enumerate().skip(skip) {
            if let Block::Heading { children, .. } = block {
                references = is_reference_heading(&inline_text(children));
            }
            out.push_str(&match block {
                Block::Heading { level, children } if standfirst && position == 1 => format!(
                    "#doc-heading(level: {level}, standfirst: true)[{}]\n\n",
                    self.inlines(children)
                ),
                _ => self.markup_block(block, skip == 0 && position == 0, references, false)?,
            });
            let Block::Heading { children, .. } = block else {
                continue;
            };
            let key = anchor_key(&inline_text(children));
            for figure in anchored_figures
                .iter()
                .filter(|figure| anchor_key(&figure.anchor) == key)
            {
                out.push_str(&self.figure(figure, 0.0)?);
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
            .map(|idea| format!("  #key-idea{}\n", self.body(idea)))
            .collect();
        format!(
            "#key-ideas[\n  #key-ideas-label{}\n{items}]\n\n",
            self.body(&self.ui("key_ideas"))
        )
    }

    fn source_link(&self, article: &Article) -> String {
        match &article.source_url {
            None => String::new(),
            Some(url) => format!("#{}\n\n", self.source_link_call(article, url, "none")),
        }
    }

    fn source_link_call(&self, article: &Article, url: &str, code: &str) -> String {
        format!(
            "source-link(destination: {}, source-id: {}, code: {code}){}",
            string_literal(url),
            string_literal(article.source_ids.first().map_or("", String::as_str)),
            self.verbatim(url),
        )
    }

    fn figure(&self, figure: &Figure, trim: f64) -> Result<String> {
        let (width, height) = pixels(&figure.path)?;
        let trim = match trim > 0.0 {
            true => format!("  trim: {trim}pt,\n"),
            false => String::new(),
        };
        Ok(format!(
            "#figure-block(\n  id: {},\n  source-id: {},\n  anchor: {},\n  layout: {},\n  \
             word: {},\n  alt: {},\n  path: {},\n  pixels: ({width}, {height}),\n{trim}\
             )[#figure-caption{}]\n\n",
            string_literal(&figure.id),
            string_literal(&figure.source_id),
            string_literal(&figure.anchor),
            string_literal(&figure.layout),
            string_literal(&self.ui("figure")),
            string_literal(&figure.alt_text),
            path_literal(&figure.path),
            self.said(&figure.caption),
        ))
    }

    fn tail_art(&self, article: &Article, path: &Path) -> Result<String> {
        let (width, height) = pixels(path)?;
        let fit = self
            .edition
            .raw
            .get("tail_art_fit")
            .and_then(|v| v.as_str());
        Ok(format!(
            "#tail-art(article: {}, path: {}, pixels: ({width}, {height}), fit: {})\n\n",
            string_literal(&article.id),
            path_literal(path),
            string_literal(fit.unwrap_or("cover").trim()),
        ))
    }

    fn extract(&self, extract: &Extract) -> String {
        let body = if extract.style == "code" {
            format!(
                "  #code-panel(collapse: true, {})",
                raw_block(&fold_reader_characters(&extract.text))
            )
        } else {
            extract
                .text
                .split("\n\n")
                .map(str::trim)
                .filter(|paragraph| !paragraph.is_empty())
                .map(|paragraph| format!("  #quote-line{}\n", self.verbatim_body(paragraph)))
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
            self.body(&extract.caption),
        )
    }

    fn blocks(&self, blocks: &[Block], standfirst: bool, manual: bool) -> Result<String> {
        blocks
            .iter()
            .enumerate()
            .map(|(index, block)| self.markup_block(block, standfirst && index == 0, false, manual))
            .collect()
    }

    fn markup_block(
        &self,
        block: &Block,
        standfirst: bool,
        references: bool,
        manual: bool,
    ) -> Result<String> {
        Ok(match block {
            Block::Heading { level, children } => format!(
                "#doc-heading(level: {level})[{}]\n\n",
                self.inlines(children)
            ),
            Block::Paragraph(children) => {
                let roster = is_name_roster(&inline_text(children));
                format!(
                    "#doc-paragraph(standfirst: {standfirst}, roster: {roster})[{}]\n\n",
                    self.flowing(children, !(standfirst || roster || manual))
                )
            }
            Block::FencedCode { code, info } => {
                let language = info.split_whitespace().next().unwrap_or("");
                let folded = fold_reader_characters(code);
                let shown = folded.trim_end_matches('\n');
                format!(
                    "#doc-code(lang: {}, inks: {}, {})\n\n",
                    string_literal(language),
                    code_inks(&folded, shown.len(), language)?,
                    raw_block(shown),
                )
            }
            Block::Quote(children) => {
                format!(
                    "#doc-quote[\n{}]\n\n",
                    self.blocks(children, false, manual)?
                )
            }
            Block::List {
                ordered,
                start,
                items,
            } => {
                format!(
                "#doc-list(ordered: {ordered}, start: {start}, references: {references})[\n{}]\n\n",
                items
                    .iter()
                    .map(|item| {
                        let manual = manual || (references && !ordered);
                        Ok(format!("  #doc-item[\n{}]\n", self.blocks(item, false, manual)?))
                    })
                    .collect::<Result<String>>()?
            )
            }
            Block::HorizontalRule => "#doc-rule()\n\n".to_string(),
            Block::Table(rows) => format!(
                "#doc-table(\n{})\n\n",
                rows.iter()
                    .map(|row| {
                        let cells: Vec<String> = row
                            .iter()
                            .map(|cell| format!("[{}]", self.inlines(cell)))
                            .collect();
                        format!("  ({},),\n", cells.join(", "))
                    })
                    .collect::<String>()
            ),
        })
    }

    fn inlines(&self, inlines: &[Inline]) -> String {
        self.flowing(inlines, false)
    }

    fn flowing(&self, inlines: &[Inline], hyphens: bool) -> String {
        inlines
            .iter()
            .map(|inline| self.inline(inline, hyphens))
            .collect()
    }

    fn inline(&self, inline: &Inline, hyphens: bool) -> String {
        match inline {
            Inline::Text(value) if hyphens => self.hyphenated(value),
            Inline::Text(value) => self.prose(value),
            Inline::Emphasis(children) => format!("#emph[{}]", self.flowing(children, hyphens)),
            Inline::Strong(children) => format!("#strong[{}]", self.flowing(children, hyphens)),
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
                    .map_or_else(|| "none".to_string(), string_literal),
                self.flowing(children, hyphens)
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

    fn closing_plates(&self) -> Result<String> {
        let target = self
            .edition
            .raw
            .get("format")
            .and_then(|value| value.get("target_pages"))
            .filter(|value| !value.is_null())
            .map_or(Ok(0), |value| {
                value.as_i64().ok_or_else(|| {
                    ValidationError::one(format!(
                        "format.target_pages must be a number, not {}",
                        show(value)
                    ))
                })
            })?;
        let target = if target == 0 {
            "none".to_string()
        } else {
            target.to_string()
        };
        Ok(self
            .edition
            .closing_plates
            .iter()
            .enumerate()
            .map(|(index, plate)| {
                format!(
                    "#closing-plate(index: {}, alt: {}, path: {}, target: {target})\n",
                    index + 1,
                    string_literal(&plate.title),
                    path_literal(&plate.art_path)
                )
            })
            .chain(["#closing-signature(none)\n".to_string()])
            .collect())
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

fn split_segments(inlines: &[Inline], keep: usize) -> Option<(Vec<Inline>, Vec<Inline>)> {
    let (mut seen, mut spaced) = (0, true);
    for (index, inline) in inlines.iter().enumerate() {
        let value = match inline {
            Inline::Text(value) => value.as_str(),
            Inline::LineBreak { hard: false } => " ",
            _ => "\u{fffc}",
        };
        for (at, c) in value.char_indices() {
            let start = spaced && !c.is_whitespace();
            spaced = c.is_whitespace();
            if !start {
                continue;
            }
            if keep > 0 && seen == keep {
                let (head, tail) = inlines.split_at(index);
                let mut kept = head.to_vec();
                let mut moved = tail.to_vec();
                if let Inline::Text(value) = inline {
                    let head = value[..at].trim_end();
                    kept.extend((!head.is_empty()).then(|| Inline::Text(head.to_string())));
                    moved[0] = Inline::Text(value[at..].to_string());
                }
                return Some((kept, moved));
            }
            seen += 1;
        }
    }
    None
}

fn read_manuscript(path: &Path) -> Result<Document> {
    let text = std::fs::read_to_string(path).map_err(|error| {
        ValidationError::one(format!("Cannot read {}: {error}", path.display()))
    })?;
    let document = parse_publication_document(&text).map_err(|error| refusal(&error))?;
    scalar_label(&document.metadata)?;
    Ok(document)
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

fn source_code(article: &Article, url: &str) -> Result<String> {
    Ok(string_array(&source_rows(article, url)?))
}

fn source_rows(article: &Article, url: &str) -> Result<Vec<String>> {
    let refuse = |why: &str| {
        ValidationError::one(format!(
            "No committed source code for article {}: {why}; regenerate editions/<id>/source-codes",
            article.id
        ))
    };
    let index = source_code_directory(&article.manuscript)
        .map(|directory| directory.join("codes.json"))
        .ok_or_else(|| refuse("no edition directory"))?;
    let text = std::fs::read_to_string(&index).map_err(|error| refuse(&error.to_string()))?;
    let codes: serde_json::Value =
        serde_json::from_str(&text).map_err(|error| refuse(&error.to_string()))?;
    let payload = source_code_payload(url);
    let print = codes["codes"]
        .as_array()
        .and_then(|rows| {
            rows.iter()
                .rev()
                .find(|row| row["payload"] == payload.as_str())
        })
        .map(|row| &row["print"])
        .filter(|print| !print["error"].is_null())
        .ok_or_else(|| refuse(&format!("codes.json has no printable code for {payload}")))?;
    let rows: Vec<String> = print["matrix"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|row| row.as_str().map(str::to_string))
        .collect();
    if rows.is_empty() {
        return Err(refuse("its matrix is empty"));
    }
    Ok(rows)
}

fn text_locale(locale: &str) -> String {
    match locale.split_once(['-', '_']) {
        Some((lang, region)) => format!(
            "lang: {}, region: {}",
            string_literal(lang),
            string_literal(region)
        ),
        None => format!("lang: {}", string_literal(locale)),
    }
}

fn path_literal(path: &Path) -> String {
    let absolute = std::path::absolute(path).unwrap_or_else(|_| path.to_path_buf());
    string_literal(&absolute.to_string_lossy())
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

fn class_ink(class: &str) -> Option<&'static str> {
    class.split_whitespace().find_map(|token| {
        CODE_INKS
            .iter()
            .find(|(classes, _)| classes.split(' ').any(|c| c == token))
            .map(|(_, ink)| *ink)
    })
}

fn code_inks(code: &str, shown: usize, language: &str) -> Result<String> {
    let language = crate::highlight::language(code, language);
    let spans = crate::highlight::spans(code, language)
        .map_err(|error| ValidationError::one(format!("code block: {error:#}")))?;
    let Some(spans) = spans else {
        return Ok("()".to_string());
    };
    if spans.iter().map(|(text, _)| text.len()).sum::<usize>() != code.len() {
        return Err(ValidationError::one(format!(
            "the {language} highlighter's spans do not cover the code block"
        )));
    }
    let mut runs: Vec<(usize, Option<&str>)> = Vec::new();
    let mut left = shown;
    for (text, class) in &spans {
        let length = text.len().min(left);
        left -= length;
        let ink = class_ink(class);
        match runs.last_mut() {
            Some((run, last)) if *last == ink => *run += length,
            _ if length > 0 => runs.push((length, ink)),
            _ => {}
        }
    }
    Ok(format!(
        "({})",
        runs.iter()
            .map(|(length, ink)| match ink {
                Some(ink) => format!("({length}, {}), ", ink.replace(' ', ", ")),
                None => format!("({length}, none), "),
            })
            .collect::<String>()
    ))
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
            | SyntaxKind::SetRule
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
    use crate::model::manifest::{load_edition, LoadOptions, Records};
    use crate::model::records::load_records;
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
        repository().join("mag/assets/fonts")
    }

    fn fixtures() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/typeset_fixtures")
    }

    fn corpus() -> PathBuf {
        fixtures().join("corpus")
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
            Ok(_) => panic!("the pipeline accepted inputs the loader refuses"),
            Err(error) => error.to_string(),
        }
    }

    fn projection_of(root: &Path, edition_id: &str) -> Projection {
        let tree = pipeline(&inputs(root, edition_id)).expect("the fixture edition loads");
        project(&tree).expect("the emitted tree projects")
    }

    #[test]
    fn an_illustrated_source_code_is_read_from_the_committed_matrix_or_refused() {
        let root = corpus();
        let records: Records = load_records(&root.join("library/sources"))
            .expect("the fixture records load")
            .into_iter()
            .map(|record| (record.id.clone(), record))
            .collect();
        let known: BTreeSet<String> = records.keys().cloned().collect();
        let edition = load_edition(
            &root,
            "901",
            &known,
            &LoadOptions {
                publication_name: PUBLICATION,
                source_records: Some(&records),
                allow_missing_art: false,
                allow_unanchored_figures: false,
            },
        )
        .expect("the fixture edition loads");
        let article = &edition.articles[0];
        let url = article
            .source_url
            .as_deref()
            .expect("the fixture article has a source");
        let code = source_code(article, url).expect("the committed code reads");
        assert_eq!(code.matches('"').count(), 2 * 21, "{code}");
        assert!(code.starts_with("(\"1111111"), "{code}");
        let refused = source_code(article, "https://example.invalid/uncommitted")
            .expect_err("an uncommitted payload is refused");
        assert!(
            refused.to_string().contains("No committed source code"),
            "{refused}"
        );
    }

    #[test]
    fn every_fixture_edition_projects_to_reader_text() {
        for edition in ["901", "902", "903"] {
            let projection = projection_of(&corpus(), edition);
            assert!(!projection.text.is_empty(), "{edition}");
        }
    }

    #[test]
    fn every_code_run_is_a_contiguous_run_of_its_captured_source() {
        let root = corpus();
        let captured =
            std::fs::read_to_string(root.join("library/sources/fixture-source-c/article.md"))
                .expect("the captured source is readable");
        let runs = projection_of(&root, "902").verbatim;
        assert_eq!(runs.len(), 4, "three fences and one extract: {runs:?}");
        for run in &runs {
            assert!(
                captured.contains(run.as_str()),
                "{run:?} is not a run of the source"
            );
        }
    }

    #[test]
    fn a_fence_in_a_language_mag_does_not_implement_is_refused() {
        let root = mutated("go-fence", "902", &[]);
        let manuscript = root.join("editions/902/articles/code-fixture-article.md");
        let text = std::fs::read_to_string(&manuscript).expect("the manuscript is readable");
        assert!(
            text.contains("```bash\n"),
            "the fixture no longer carries a bash fence"
        );
        std::fs::write(&manuscript, text.replace("```bash\n", "```go\n"))
            .expect("the manuscript is writable");
        let refused = refusal_of(&root, "902");
        assert!(refused.contains("\"go\""), "{refused}");
    }

    #[test]
    fn a_highlighted_fence_carries_one_ink_run_per_ink_change() {
        assert_eq!(
            code_inks("fn x() {}\n", 9, "rust").expect("rust highlights"),
            "((2, rgb(240, 87, 56)), (1, none), (1, rgb(11%, 22%, 55%)), (5, none), )"
        );
        assert_eq!(
            code_inks("fn x() {}\n", 9, "").expect("inferred"),
            code_inks("fn x() {}\n", 9, "rust").expect("rust highlights")
        );
        assert_eq!(code_inks("hello there\n", 11, "").expect("plain"), "()");
        assert_eq!(
            code_inks("fn x() {}\n", 9, "nosuchlang").expect("no lexer"),
            "()"
        );
    }

    #[test]
    fn the_code_inks_are_the_stylesheet_s_own() {
        let css = std::fs::read_to_string(repository().join("mag/tests/code-inks.css"))
            .expect("the stylesheet is readable");
        let mut found: Vec<(String, String)> = vec![];
        for line in css.lines().filter(|l| l.starts_with("pre code .")) {
            let (selectors, rule) = line.split_once('{').expect("a rule opens");
            let colour = rule
                .trim()
                .trim_start_matches("color:")
                .trim_end_matches('}')
                .trim()
                .trim_end_matches(';')
                .trim()
                .to_string();
            for class in selectors
                .split(',')
                .map(|s| s.trim().trim_start_matches("pre code ."))
            {
                found.push((class.to_string(), colour.clone()));
            }
        }
        assert_eq!(found.len(), 41, "{found:?}");
        for (class, colour) in &found {
            let want = (colour != "inherit").then_some(colour.as_str());
            assert_eq!(class_ink(class), want, "class {class}");
        }
        assert_eq!(class_ink("p p-Indicator"), None);
        assert_eq!(class_ink("err"), None);
    }

    #[test]
    fn the_text_locale_carries_the_region_when_the_edition_names_one() {
        assert_eq!(text_locale("en"), "lang: \"en\"");
        assert_eq!(text_locale("es-AR"), "lang: \"es\", region: \"AR\"");
        let root = mutated(
            "spanish",
            "902",
            &[("status: draft\n", "status: draft\nlocale: es\n")],
        );
        let tree = pipeline(&inputs(&root, "902")).expect("the fixture edition loads");
        let main = tree.get(MAIN).expect("the tree has a main file");
        assert!(
            main.source.contains("#set text(lang: \"es\")"),
            "{}",
            main.source
        );
    }

    #[test]
    fn a_translation_sets_its_locale_and_labels_and_breaks_only_body_prose_at_pyphen_points() {
        let root = corpus();
        let base = crate::typeset::layout::edition(&root, "906", PUBLICATION).expect("906 loads");
        let es = crate::model::manifest::load_translation(&root, &base, "es").expect("es loads");
        let tree =
            compose(&es, &fonts(), Hyphenation::PLAIN, &[]).expect("the Spanish edition composes");
        let text: String = tree.files.iter().map(|f| f.source.as_str()).collect();
        assert!(text.contains("#set text(lang: \"es\", region: \"AR\")"));
        assert!(text.contains("[Artículo 01]"));
        assert!(text.contains("res\u{ad}pon\u{ad}sa\u{ad}bi\u{ad}li\u{ad}dad"));
        assert!(text.contains("level: 2)[Dónde se dividen las palabras]"));
        assert!(text.contains("Una columna justificada corta las palabras"));
        let english = compose(&base, &fonts(), Hyphenation::PLAIN, &[])
            .expect("the English edition composes");
        assert!(english.files.iter().all(|f| !f.source.contains('\u{ad}')));
        let native = Hyphenation {
            english: true,
            ..Hyphenation::PLAIN
        };
        let hyphenated = compose(&base, &fonts(), native, &[]).expect("it composes");
        let text: String = hyphenated.files.iter().map(|f| f.source.as_str()).collect();
        assert!(text.contains("#text(hyphenate: true)[A cache budget limits"));
        assert!(text.contains("level: 2)[Budgets]"));
        assert!(!text.contains('\u{ad}'));
        assert!(!english
            .files
            .iter()
            .any(|f| f.source.contains("hyphenate: true")));
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
    fn symbols_reach_typst_and_a_glyph_no_face_carries_is_refused() {
        let root = mutated("unsettable", "900", &[]);
        let manuscript = root.join("editions/900/articles/plain-opener-article.md");
        let text = std::fs::read_to_string(&manuscript).expect("the manuscript is readable");
        let symbols = format!("{text}\nAlways \u{25a1} P, eventually \u{25c7} P, P \u{21dd} Q.\n");
        std::fs::write(&manuscript, &symbols).expect("the manuscript is writable");
        let tree = pipeline(&inputs(&root, "900")).expect("bundled symbols are settable");
        let reached = |run: &str| tree.files.iter().any(|file| file.source.contains(run));
        assert!(["\u{25a1} P", "\u{25c7} P", "P \u{21dd} Q"]
            .into_iter()
            .all(reached));
        std::fs::write(
            &manuscript,
            format!("{symbols}A private \u{f0000} glyph.\n"),
        )
        .expect("the manuscript is writable");
        let message = refusal_of(&root, "900");
        assert!(
            message.contains("U+F0000")
                && message.contains("article plain-opener-article")
                && message.contains("A private"),
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
    fn a_container_label_refuses_the_edition_instead_of_printing_brackets() {
        for (label, refusal) in [
            ("~", None),
            ("[]", Some("Frontmatter label must be text, not []")),
            (
                "{a: 1}",
                Some("Frontmatter label must be text, not {\"a\":1}"),
            ),
        ] {
            let root = mutated("container-label", "900", &[]);
            let manuscript = root.join("editions/900/articles/plain-opener-article.md");
            let text = std::fs::read_to_string(&manuscript).expect("the manuscript is readable");
            assert!(text.contains("label: ARTICLE\n"), "the fixture label moved");
            std::fs::write(
                &manuscript,
                text.replace("label: ARTICLE\n", &format!("label: {label}\n")),
            )
            .expect("the manuscript is writable");
            match (pipeline(&inputs(&root, "900")), refusal) {
                (Ok(_), None) => {}
                (Err(error), Some(want)) => assert!(error.to_string().contains(want), "{error}"),
                (outcome, _) => panic!("label {label}: {:?}", outcome.map(|_| ())),
            }
        }
    }

    #[test]
    fn an_empty_subtitle_prints_nothing_and_a_number_is_refused() {
        let root = mutated(
            "empty-subtitle",
            "900",
            &[(
                "subtitle: A fixture subtitle for the edition header.",
                "subtitle:",
            )],
        );
        let tree = pipeline(&inputs(&root, "900")).expect("an empty subtitle loads");
        let text: String = tree.files.iter().map(|f| f.source.as_str()).collect();
        assert!(!text.contains("edition-subtitle") && !text.contains("None"));
        let root = mutated(
            "numeric-subtitle",
            "900",
            &[(
                "subtitle: A fixture subtitle for the edition header.",
                "subtitle: 5",
            )],
        );
        assert!(refusal_of(&root, "900").contains("Edition subtitle must be text, not 5"));
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
    }

    #[test]
    fn a_string_literal_escapes_quotes_backslashes_and_line_breaks() {
        assert_eq!(
            string_literal("a\"b\\c\nd\re\tf"),
            "\"a\\\"b\\\\c\\nd\\re\\tf\""
        );
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
    fn a_standfirst_splits_at_its_top_level_spaces_and_moves_an_inline_whole() {
        let text = |v: &str| Inline::Text(v.to_string());
        let run = [
            text("one two "),
            Inline::Code("three four".into()),
            text(" five six"),
        ];
        let (kept, moved) = split_segments(&run, 1).expect("one segment splits");
        assert_eq!(
            (kept, moved),
            (
                vec![text("one")],
                vec![text("two "), run[1].clone(), run[2].clone()]
            )
        );
        let (kept, moved) = split_segments(&run, 2).expect("the code moves whole");
        assert_eq!((kept, moved), (run[..1].to_vec(), run[1..].to_vec()));
        let (kept, moved) = split_segments(&run, 3).expect("the code is one segment");
        assert_eq!((kept, moved), (run[..2].to_vec(), vec![text("five six")]));
        let (kept, moved) = split_segments(&run, 4).expect("four of five segments");
        assert_eq!(kept, vec![text("one two "), run[1].clone(), text(" five")]);
        assert_eq!(moved, vec![text("six")]);
        let glued = [text("see "), Inline::Code("x".into()), text("-style runs")];
        let (kept, moved) = split_segments(&glued, 2).expect("glued code joins its word");
        assert_eq!(
            kept,
            vec![glued[0].clone(), glued[1].clone(), text("-style")]
        );
        assert_eq!(moved, vec![text("runs")]);
        assert_eq!(split_segments(&run, 5), None);
        assert_eq!(split_segments(&run, 0), None);
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
