use anyhow::{bail, Result};
use pulldown_cmark::{CodeBlockKind, Event, HeadingLevel, Options, Parser, Tag, TagEnd};
use serde_yaml::{Mapping, Value};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq)]
pub enum Inline {
    Text(String),
    Emphasis(Vec<Inline>),
    Strong(Vec<Inline>),
    Code(String),
    Link {
        destination: String,
        title: Option<String>,
        children: Vec<Inline>,
    },
    LineBreak {
        hard: bool,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub enum Block {
    Heading {
        level: u8,
        children: Vec<Inline>,
    },
    Paragraph(Vec<Inline>),
    FencedCode {
        code: String,
        info: String,
    },
    Quote(Vec<Block>),
    List {
        ordered: bool,
        start: u64,
        items: Vec<Vec<Block>>,
    },
    HorizontalRule,
}

#[derive(Debug, Clone)]
pub struct Document {
    pub metadata: Mapping,
    pub blocks: Vec<Block>,
}

#[derive(Clone, Copy, PartialEq)]
enum Until {
    Heading,
    Paragraph,
    BlockQuote,
    List,
    Item,
    CodeBlock,
    Emphasis,
    Strong,
    Link,
}

pub fn parse_publication_document(markdown: &str) -> Result<Document> {
    let (metadata, body) = split_frontmatter(markdown)?;
    let body = fallback_glyphs(&body);
    let events: Vec<Event> = Parser::new_ext(&body, Options::empty()).collect();
    let mut index = 0;
    let blocks = parse_blocks(&events, &mut index, None)?;
    if index != events.len() {
        bail!("Markdown parser left unconsumed block tokens");
    }
    Ok(Document { metadata, blocks })
}

fn fallback_glyphs(body: &str) -> String {
    body.chars()
        .filter(|c| *c != '\u{ad}')
        .map(|c| match c {
            '\u{2011}' | '\u{2212}' => '-',
            other => other,
        })
        .collect()
}

pub fn split_frontmatter(markdown: &str) -> Result<(Mapping, String)> {
    let lines = split_lines_keepends(markdown);
    if lines.is_empty() || trim_eol(lines[0]) != "---" {
        return Ok((Mapping::new(), markdown.to_string()));
    }
    for (index, line) in lines.iter().enumerate().skip(1) {
        let marker = trim_eol(line);
        if marker != "---" && marker != "..." {
            continue;
        }
        let header: String = lines[1..index].concat();
        let parsed: Value = serde_yaml::from_str(&header)
            .map_err(|exc| anyhow::anyhow!("Invalid YAML frontmatter: {exc}"))?;
        return Ok((frontmatter_mapping(parsed)?, lines[index + 1..].concat()));
    }
    Ok((Mapping::new(), markdown.to_string()))
}

fn frontmatter_mapping(parsed: Value) -> Result<Mapping> {
    match parsed {
        Value::Null => Ok(Mapping::new()),
        Value::Mapping(mapping) => {
            for key in mapping.keys() {
                if !key.is_string() {
                    bail!("YAML frontmatter must be a mapping with string keys");
                }
            }
            for value in mapping.values() {
                check_frozen(value)?;
            }
            Ok(mapping)
        }
        _ => bail!("YAML frontmatter must be a mapping with string keys"),
    }
}

fn check_frozen(value: &Value) -> Result<()> {
    match value {
        Value::Mapping(mapping) => {
            for key in mapping.keys() {
                if !key.is_string() {
                    bail!("YAML frontmatter mappings must use string keys");
                }
            }
            mapping.values().try_for_each(check_frozen)
        }
        Value::Sequence(items) => items.iter().try_for_each(check_frozen),
        _ => Ok(()),
    }
}

fn split_lines_keepends(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = text.char_indices().peekable();
    while let Some((position, character)) = chars.next() {
        if !is_line_boundary(character) {
            continue;
        }
        let mut end = position + character.len_utf8();
        if character == '\r' && chars.peek().map(|(_, next)| *next) == Some('\n') {
            chars.next();
            end += 1;
        }
        lines.push(&text[start..end]);
        start = end;
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

fn is_line_boundary(character: char) -> bool {
    matches!(
        character,
        '\n' | '\r'
            | '\u{b}'
            | '\u{c}'
            | '\u{1c}'
            | '\u{1d}'
            | '\u{1e}'
            | '\u{85}'
            | '\u{2028}'
            | '\u{2029}'
    )
}

fn trim_eol(line: &str) -> &str {
    line.trim_end_matches(['\r', '\n'])
}

fn parse_blocks(events: &[Event], index: &mut usize, until: Option<Until>) -> Result<Vec<Block>> {
    let mut blocks = Vec::new();
    while *index < events.len() {
        if let (Event::End(end), Some(boundary)) = (&events[*index], until) {
            if closes(end, boundary) {
                *index += 1;
                return Ok(blocks);
            }
        }
        if is_inline_start(&events[*index]) {
            blocks.push(Block::Paragraph(parse_loose_inlines(events, index)?));
            continue;
        }
        blocks.push(parse_block(events, index)?);
    }
    match until {
        Some(_) => bail!("Unclosed Markdown block"),
        None => Ok(blocks),
    }
}

fn is_inline_start(event: &Event) -> bool {
    matches!(
        event,
        Event::Text(_)
            | Event::Code(_)
            | Event::SoftBreak
            | Event::HardBreak
            | Event::Start(Tag::Emphasis | Tag::Strong | Tag::Link { .. })
    )
}

fn parse_loose_inlines(events: &[Event], index: &mut usize) -> Result<Vec<Inline>> {
    let mut inlines = Vec::new();
    while *index < events.len() && is_inline_start(&events[*index]) {
        inlines.push(parse_inline(events, index)?);
    }
    Ok(inlines)
}

fn parse_block(events: &[Event], index: &mut usize) -> Result<Block> {
    let event = &events[*index];
    *index += 1;
    match event {
        Event::Start(Tag::Heading { level, .. }) => Ok(Block::Heading {
            level: heading_level(*level),
            children: parse_inlines(events, index, Until::Heading)?,
        }),
        Event::Start(Tag::Paragraph) => Ok(Block::Paragraph(parse_inlines(
            events,
            index,
            Until::Paragraph,
        )?)),
        Event::Start(Tag::BlockQuote(_)) => Ok(Block::Quote(parse_blocks(
            events,
            index,
            Some(Until::BlockQuote),
        )?)),
        Event::Start(Tag::List(start)) => parse_list(events, index, *start),
        Event::Start(Tag::CodeBlock(kind)) => parse_code_block(events, index, kind),
        Event::Rule => Ok(Block::HorizontalRule),
        other => bail!("Unsupported Markdown block token: {other:?}"),
    }
}

fn parse_list(events: &[Event], index: &mut usize, start: Option<u64>) -> Result<Block> {
    let mut items = Vec::new();
    while *index < events.len() {
        match &events[*index] {
            Event::End(end) if closes(end, Until::List) => {
                *index += 1;
                return Ok(Block::List {
                    ordered: start.is_some(),
                    start: start.unwrap_or(1),
                    items,
                });
            }
            Event::Start(Tag::Item) => {
                *index += 1;
                items.push(parse_blocks(events, index, Some(Until::Item))?);
            }
            other => bail!("Unsupported Markdown list token: {other:?}"),
        }
    }
    bail!("Unclosed Markdown list")
}

fn parse_code_block(events: &[Event], index: &mut usize, kind: &CodeBlockKind) -> Result<Block> {
    let info = match kind {
        CodeBlockKind::Fenced(info) => info.to_string(),
        CodeBlockKind::Indented => String::new(),
    };
    let mut code = String::new();
    while *index < events.len() {
        match &events[*index] {
            Event::End(end) if closes(end, Until::CodeBlock) => {
                *index += 1;
                return Ok(Block::FencedCode { code, info });
            }
            Event::Text(text) => {
                code.push_str(text);
                *index += 1;
            }
            other => bail!("Unsupported Markdown code token: {other:?}"),
        }
    }
    bail!("Unclosed Markdown code block")
}

fn parse_inlines(events: &[Event], index: &mut usize, until: Until) -> Result<Vec<Inline>> {
    let mut inlines = Vec::new();
    while *index < events.len() {
        if let Event::End(end) = &events[*index] {
            if closes(end, until) {
                *index += 1;
                return Ok(inlines);
            }
        }
        inlines.push(parse_inline(events, index)?);
    }
    bail!("Unclosed Markdown inline span")
}

fn parse_inline(events: &[Event], index: &mut usize) -> Result<Inline> {
    let event = &events[*index];
    *index += 1;
    match event {
        Event::Text(text) => Ok(Inline::Text(text.to_string())),
        Event::Code(text) => Ok(Inline::Code(text.to_string())),
        Event::SoftBreak => Ok(Inline::LineBreak { hard: false }),
        Event::HardBreak => Ok(Inline::LineBreak { hard: true }),
        Event::Start(Tag::Emphasis) => Ok(Inline::Emphasis(parse_inlines(
            events,
            index,
            Until::Emphasis,
        )?)),
        Event::Start(Tag::Strong) => {
            Ok(Inline::Strong(parse_inlines(events, index, Until::Strong)?))
        }
        Event::Start(Tag::Link {
            dest_url, title, ..
        }) => Ok(Inline::Link {
            destination: dest_url.to_string(),
            title: (!title.is_empty()).then(|| title.to_string()),
            children: parse_inlines(events, index, Until::Link)?,
        }),
        other => bail!("Unsupported Markdown inline token: {other:?}"),
    }
}

fn closes(end: &TagEnd, until: Until) -> bool {
    matches!(
        (end, until),
        (TagEnd::Heading(_), Until::Heading)
            | (TagEnd::Paragraph, Until::Paragraph)
            | (TagEnd::BlockQuote(_), Until::BlockQuote)
            | (TagEnd::List(_), Until::List)
            | (TagEnd::Item, Until::Item)
            | (TagEnd::CodeBlock, Until::CodeBlock)
            | (TagEnd::Emphasis, Until::Emphasis)
            | (TagEnd::Strong, Until::Strong)
            | (TagEnd::Link, Until::Link)
    )
}

fn heading_level(level: HeadingLevel) -> u8 {
    match level {
        HeadingLevel::H1 => 1,
        HeadingLevel::H2 => 2,
        HeadingLevel::H3 => 3,
        HeadingLevel::H4 => 4,
        HeadingLevel::H5 => 5,
        HeadingLevel::H6 => 6,
    }
}

pub fn visible_blocks(blocks: &[Block]) -> Vec<(String, String)> {
    let mut flattened = Vec::new();
    flatten(blocks, &mut flattened, None);
    flattened
}

fn flatten(blocks: &[Block], into: &mut Vec<(String, String)>, container: Option<&str>) {
    for block in blocks {
        match block {
            Block::Heading { level, children } => {
                into.push((format!("h{level}"), inline_visible(children)))
            }
            Block::Paragraph(children) => into.push((
                container.unwrap_or("p").to_string(),
                inline_visible(children),
            )),
            Block::FencedCode { code, .. } => into.push(("code".to_string(), code.clone())),
            Block::Quote(children) => flatten(children, into, Some("quote")),
            Block::List { ordered, items, .. } => {
                let kind = if *ordered { "ordered" } else { "bullet" };
                for item in items {
                    flatten(item, into, Some(kind));
                }
            }
            Block::HorizontalRule => {}
        }
    }
}

fn inline_visible(inlines: &[Inline]) -> String {
    let mut buffer = String::new();
    for inline in inlines {
        match inline {
            Inline::Text(value) | Inline::Code(value) => buffer.push_str(value),
            Inline::Emphasis(children)
            | Inline::Strong(children)
            | Inline::Link { children, .. } => buffer.push_str(&inline_visible(children)),
            Inline::LineBreak { .. } => buffer.push(' '),
        }
    }
    buffer
        .split(is_python_space)
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn block_signature(blocks: &[Block]) -> Vec<String> {
    blocks.iter().map(descriptor).collect()
}

fn descriptor(block: &Block) -> String {
    match block {
        Block::Heading { level, .. } => format!("h{level}"),
        Block::Paragraph(_) => "body".to_string(),
        Block::FencedCode { .. } => "code".to_string(),
        Block::HorizontalRule => "rule".to_string(),
        Block::Quote(children) => format!("quote[{}]", joined(children, ",")),
        Block::List {
            ordered,
            start,
            items,
        } => {
            let name = if *ordered { "ol" } else { "ul" };
            let start = if *ordered && *start != 1 {
                format!("@{start}")
            } else {
                String::new()
            };
            let items: Vec<String> = items.iter().map(|item| joined(item, ",")).collect();
            format!("{name}{start}[{}]", items.join(";"))
        }
    }
}

fn joined(blocks: &[Block], separator: &str) -> String {
    blocks
        .iter()
        .map(descriptor)
        .collect::<Vec<_>>()
        .join(separator)
}

const OPENING_CONTEXT: [char; 13] = [
    '(', '[', '{', '\u{2018}', '\u{201c}', '\u{ab}', '\u{a1}', '\u{bf}', '-', '\u{2010}',
    '\u{2013}', '\u{2014}', '/',
];

pub fn educate_reader_quotes(text: &str) -> String {
    if !text.contains('\'') && !text.contains('"') {
        return text.to_string();
    }
    let mut characters: Vec<char> = text.chars().collect();
    for index in 0..characters.len() {
        let character = characters[index];
        if character != '\'' && character != '"' {
            continue;
        }
        let previous = if index > 0 {
            Some(characters[index - 1])
        } else {
            None
        };
        let following = characters.get(index + 1).copied();
        let opens = previous.is_none_or(|c| is_python_space(c) || OPENING_CONTEXT.contains(&c));
        characters[index] = educated(character, previous, following, opens);
    }
    characters.into_iter().collect()
}

fn educated(character: char, previous: Option<char>, following: Option<char>, opens: bool) -> char {
    if character == '"' {
        return if opens { '\u{201c}' } else { '\u{201d}' };
    }
    if previous.is_some_and(char::is_alphanumeric) {
        return '\u{2019}';
    }
    if opens && following.is_some_and(char::is_alphabetic) {
        return '\u{2018}';
    }
    '\u{2019}'
}

pub fn fold_reader_characters(text: &str, settable: &BTreeSet<u32>) -> String {
    let text = text.replace('\u{a0}', " ");
    if text.is_ascii() {
        return text;
    }
    text.chars()
        .map(|character| {
            let code = character as u32;
            if is_python_space(character) || code < 0x20 || settable.contains(&code) {
                character
            } else {
                '?'
            }
        })
        .collect()
}

fn is_python_space(character: char) -> bool {
    character.is_whitespace() || matches!(character, '\u{1c}'..='\u{1f}')
}

pub fn settable_codepoints(fonts: &Path) -> Result<BTreeSet<u32>> {
    let mut faces = Vec::new();
    collect_faces(fonts, &mut faces)?;
    faces.sort();
    if faces.is_empty() {
        bail!(
            "The publication ships no reader faces under {}",
            fonts.display()
        );
    }
    let mut settable: Option<BTreeSet<u32>> = None;
    for face in &faces {
        let codepoints = face_codepoints(face)?;
        settable = Some(match settable {
            None => codepoints,
            Some(previous) => previous.intersection(&codepoints).copied().collect(),
        });
    }
    Ok(settable.unwrap_or_default())
}

fn collect_faces(directory: &Path, into: &mut Vec<PathBuf>) -> Result<()> {
    for entry in std::fs::read_dir(directory)? {
        let path = entry?.path();
        if path.is_dir() {
            collect_faces(&path, into)?;
        } else if path.extension().is_some_and(|extension| extension == "ttf") {
            into.push(path);
        }
    }
    Ok(())
}

const CMAP_PREFERENCES: [(u16, u16); 8] = [
    (3, 10),
    (0, 6),
    (0, 4),
    (3, 1),
    (0, 3),
    (0, 2),
    (0, 1),
    (0, 0),
];

fn face_codepoints(face: &Path) -> Result<BTreeSet<u32>> {
    let data = std::fs::read(face)?;
    let parsed = ttf_parser::Face::parse(&data, 0)?;
    let Some(cmap) = parsed.tables().cmap else {
        bail!("{} carries no cmap table", face.display());
    };
    for (platform, encoding) in CMAP_PREFERENCES {
        for subtable in cmap.subtables {
            if platform_id(subtable.platform_id) != platform || subtable.encoding_id != encoding {
                continue;
            }
            let mut codepoints = BTreeSet::new();
            subtable.codepoints(|codepoint| {
                if subtable
                    .glyph_index(codepoint)
                    .is_some_and(|glyph| glyph.0 != 0)
                {
                    codepoints.insert(codepoint);
                }
            });
            return Ok(codepoints);
        }
    }
    bail!("{} carries no Unicode cmap subtable", face.display())
}

fn platform_id(platform: ttf_parser::PlatformId) -> u16 {
    match platform {
        ttf_parser::PlatformId::Unicode => 0,
        ttf_parser::PlatformId::Macintosh => 1,
        ttf_parser::PlatformId::Iso => 2,
        ttf_parser::PlatformId::Windows => 3,
        ttf_parser::PlatformId::Custom => 4,
    }
}
