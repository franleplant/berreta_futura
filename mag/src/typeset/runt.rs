use crate::typeset::content::{File, Tree};
use crate::typeset::estimate::Metrics;
use crate::typeset::template::{document, world};
use crate::typeset::world::PRELUDE;
use anyhow::{bail, Result};
use std::path::Path;
use typst::introspection::{Location, Tag};
use typst::layout::{FrameItem, Point, Transform};
use typst::text::TextItem;
use typst::{World, WorldExt};
use typst_layout::PagedDocument;
use typst_syntax::{FileId, Span};

const PROSE: [(&str, f64); 3] = [
    ("mag-prose", 0.0),
    ("mag-prose-band", 4.00395),
    ("mag-prose-compact", -32.5),
];
const COLUMN_RIGHT: f64 = 4.00395 + 325.0;
const RUNT_MEASURE_FRACTION: f64 = 0.15;
const RUNT_MAX_RAG_FRACTION: f64 = 0.33;
const PASSES: usize = 3;
const LINE_SLACK: f64 = 4.0;
const NO_BREAK: &str = "\\u{a0}";

type Anchor = (Span, usize);

#[derive(Default)]
struct Line {
    x0: f64,
    x1: f64,
    words: Vec<(f64, String)>,
    first: Option<(f64, Anchor)>,
    last: Option<(f64, Anchor)>,
}

#[derive(Default)]
struct Block {
    lines: Vec<(usize, f64, Line)>,
    right: f64,
    size: f64,
    hyphenates: bool,
}

fn glyph_anchor(text: &TextItem, index: usize) -> Anchor {
    let glyph = &text.glyphs[index];
    (glyph.span.0, usize::from(glyph.span.1))
}

fn take(block: &mut Block, page: usize, at: Point, text: &TextItem) {
    let (x, y) = (at.x.to_pt(), at.y.to_pt());
    let at = match block
        .lines
        .iter()
        .position(|(p, ly, _)| *p == page && (ly - y).abs() < LINE_SLACK)
    {
        Some(index) => index,
        None => {
            let fresh = Line {
                x0: f64::MAX,
                ..Line::default()
            };
            block.lines.push((page, y, fresh));
            block.lines.len() - 1
        }
    };
    let line = &mut block.lines[at].2;
    let end = x + text.width().to_pt();
    line.x0 = line.x0.min(x);
    line.x1 = line.x1.max(end);
    line.words.push((x, text.text.to_string()));
    if !text.glyphs.is_empty() && line.first.as_ref().is_none_or(|(fx, _)| x < *fx) {
        line.first = Some((x, glyph_anchor(text, 0)));
    }
    let inked = text
        .glyphs
        .iter()
        .rposition(|g| !text.text[g.range()].trim().is_empty());
    if let Some(index) = inked.filter(|_| line.last.as_ref().is_none_or(|(lx, _)| end >= *lx)) {
        let glyph = &text.glyphs[index];
        line.last = Some((
            end,
            (
                glyph.span.0,
                usize::from(glyph.span.1) + glyph.range().len(),
            ),
        ));
    }
    block.size = block.size.max(text.size.to_pt());
    block.hyphenates |= text.lang.as_str() != "en";
}

fn walk(
    items: &[(Point, FrameItem)],
    at: Point,
    page: usize,
    right: f64,
    open: &mut Vec<Location>,
    blocks: &mut Vec<(Location, Block)>,
) {
    for (pos, item) in items {
        let here = at + *pos;
        match item {
            FrameItem::Tag(Tag::Start(content, _)) => {
                let edge = content
                    .label()
                    .and_then(|l| PROSE.iter().find(|(name, _)| *name == l.resolve().as_str()));
                if let (Some((_, shift)), Some(loc)) = (edge, content.location()) {
                    open.push(loc);
                    if !blocks.iter().any(|(l, _)| *l == loc) {
                        let right = right + shift;
                        blocks.push((
                            loc,
                            Block {
                                right,
                                ..Block::default()
                            },
                        ));
                    }
                }
            }
            FrameItem::Tag(Tag::End(loc, ..)) => open.retain(|l| l != loc),
            FrameItem::Group(group) => {
                let t = group.transform;
                let plain = Transform {
                    tx: Default::default(),
                    ty: Default::default(),
                    ..t
                }
                .is_identity();
                if plain {
                    let shift = here + Point::new(t.tx, t.ty);
                    walk(
                        group.frame.items().as_slice(),
                        shift,
                        page,
                        right,
                        open,
                        blocks,
                    );
                }
            }
            FrameItem::Text(text) => {
                if let Some(block) = open
                    .last()
                    .and_then(|loc| blocks.iter_mut().find(|(l, _)| l == loc))
                {
                    take(&mut block.1, page, here, text);
                }
            }
            _ => {}
        }
    }
}

fn words(line: &Line) -> Vec<String> {
    let mut parts = line.words.clone();
    parts.sort_by(|a, b| a.0.total_cmp(&b.0));
    parts
        .iter()
        .map(|(_, t)| t.as_str())
        .collect::<String>()
        .split_whitespace()
        .map(str::to_string)
        .collect()
}

fn runt(block: &Block, metrics: &Metrics) -> Option<(Anchor, Anchor)> {
    let mut lines: Vec<_> = block.lines.iter().collect();
    lines.sort_by(|a, b| {
        (a.0, a.1)
            .partial_cmp(&(b.0, b.1))
            .expect("finite baselines")
    });
    let lines: Vec<&Line> = lines.into_iter().map(|(_, _, l)| l).collect();
    let [.., previous, last] = lines.as_slice() else {
        return None;
    };
    let (runt, before) = (words(last), words(previous));
    let measure = block.right - lines.iter().map(|l| l.x0).fold(f64::MAX, f64::min);
    let size = block.size;
    let prior = before.last()?;
    let hyphen = block.hyphenates && prior.ends_with(['-', '\u{2010}']);
    let width = last.x1 - last.x0;
    let pair = metrics.width("serif", &format!("{prior}\u{a0}{}", runt.first()?), size);
    let opened =
        measure - (previous.x1 - previous.x0 - metrics.width("serif", &format!(" {prior}"), size));
    (runt.len() == 1
        && !hyphen
        && width <= measure * RUNT_MEASURE_FRACTION
        && pair <= measure
        && opened <= measure * RUNT_MAX_RAG_FRACTION)
        .then_some((previous.last.as_ref()?.1, last.first.as_ref()?.1))
}

fn gap(sources: &dyn World, (from, to): (Anchor, Anchor)) -> Option<(FileId, usize, usize)> {
    let file = from.0.id()?;
    (to.0.id()? == file).then_some(())?;
    let source = sources.source(file).ok()?;
    let start = sources.range(from.0)?.start + from.1;
    let end = sources.range(to.0)?.start + to.1;
    let text = source.text().get(start..end)?;
    let open = text.find(char::is_whitespace)?;
    let run = text[open..]
        .find(|c: char| !c.is_whitespace())
        .unwrap_or(text.len() - open);
    Some((file, start + open, start + open + run))
}

fn binds(
    doc: &PagedDocument,
    sources: &dyn World,
    metrics: &Metrics,
) -> Vec<(FileId, usize, usize)> {
    let mut blocks = vec![];
    let mut open = vec![];
    for (page, p) in doc.pages().iter().enumerate() {
        let items = p.frame.items().as_slice();
        let body = items
            .iter()
            .rposition(|(_, i)| matches!(i, FrameItem::Group(_)))
            .unwrap_or(items.len());
        let margin = items[..body]
            .iter()
            .find(|(_, i)| matches!(i, FrameItem::Group(_)))
            .map_or(0.0, |(pos, _)| pos.x.to_pt());
        walk(
            &items[..body],
            Point::zero(),
            page,
            margin + COLUMN_RIGHT,
            &mut open,
            &mut blocks,
        );
    }
    blocks
        .iter()
        .filter_map(|(_, block)| runt(block, metrics))
        .filter_map(|anchors| gap(sources, anchors))
        .collect()
}

fn bind(tree: Tree, found: &[(FileId, usize, usize)]) -> Tree {
    let files = tree.files.into_iter().map(|file| {
        let path = format!("/{}", file.path);
        let mut source = file.source;
        let mut here: Vec<_> = found
            .iter()
            .filter(|(id, ..)| id.vpath().get_with_slash() == path)
            .map(|(_, a, b)| (a - PRELUDE.len(), b - PRELUDE.len()))
            .collect();
        here.sort_unstable_by(|a, b| b.cmp(a));
        for (a, b) in here {
            source.replace_range(a..b, NO_BREAK);
        }
        File { source, ..file }
    });
    Tree {
        files: files.collect(),
    }
}

pub fn bound(mut tree: Tree, font_dir: &Path) -> Result<(Tree, PagedDocument)> {
    let metrics = Metrics::load(font_dir).map_err(|e| anyhow::anyhow!("{e}"))?;
    for _ in 0..PASSES {
        let sources = world(&tree, font_dir)?;
        let doc = document(&sources)?;
        let found = binds(&doc, &sources, &metrics);
        if found.is_empty() {
            return Ok((tree, doc));
        }
        tree = bind(tree, &found);
    }
    bail!("the Typst reader's runt binds did not settle within {PASSES} passes")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::template::FONT_DIR;
    use std::path::PathBuf;

    const RUNT: &str = "7\\:10\\:25 AM EST\\, July 30\\. A malformed BMP from a RIPE address\\, \
        presenting as Chrome 131\\.0\\.0 on Windows 10\\. We initially assumed whoever built it had \
        patch\\-diffed the fix themselves\\. A public PoC was committed to GitHub at 9\\:47\\:30 PM \
        UTC on July 29\\, over five hours before our patch was fully deployed at 11\\:09 PM EDT\\, \
        and 13 hours\\, 22 minutes\\, and 55 seconds before that attempt\\. André Baptista of \
        Ethiack\\, one of the vulnerability’s discoverers\\, pointed out in a public exchange with \
        me on X that this PoC was the first to use a malformed BMP\\.";
    const FULL: &str = "A closing line that ends well inside the measure\\.";

    fn reader_fonts() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("the crate sits in the repository")
            .join(FONT_DIR)
    }

    fn piece() -> Tree {
        Tree {
            files: vec![File {
                path: "main.typ".into(),
                source: format!(
                    "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                     #doc-paragraph[{RUNT}]\n\n#doc-paragraph[{FULL}]\n]\n"
                ),
            }],
        }
    }

    fn last_lines(doc: &PagedDocument) -> Vec<String> {
        let (mut blocks, mut open) = (vec![], vec![]);
        for (page, p) in doc.pages().iter().enumerate() {
            walk(
                p.frame.items().as_slice(),
                Point::zero(),
                page,
                0.0,
                &mut open,
                &mut blocks,
            );
        }
        blocks
            .iter()
            .map(|(_, b)| {
                let mut lines: Vec<_> = b.lines.iter().collect();
                lines.sort_by(|a, b| (a.0, a.1).partial_cmp(&(b.0, b.1)).expect("finite"));
                words(&lines.last().expect("a line").2).join(" ")
            })
            .collect()
    }

    const CAPTION: &str =
        "Total spend decomposed into six terms that multiply\\; the middle three \
        are where the optimization effort goes\\.";

    fn captioned(layout: &str) -> Tree {
        let image = format!(
            "{}/tests/typeset_fixtures/media/landscape.png",
            env!("CARGO_MANIFEST_DIR")
        );
        Tree {
            files: vec![File {
                path: "main.typ".into(),
                source: format!(
                    "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                     #doc-heading(level: 3)[Anchor]\n#figure-block(id: \"f\", source-id: \"s\", \
                     anchor: \"Anchor\", layout: \"{layout}\", word: \"Figure\", alt: \"a\", \
                     path: \"{image}\", pixels: (40, 25))[#figure-caption[{CAPTION}]#figure-credit[Chart by Uber\\.]]\n]\n"
                ),
            }],
        }
    }

    #[test]
    fn a_band_caption_is_bound_on_the_band_s_own_measure() {
        let fonts = reader_fonts();
        let (band, _) = bound(captioned("evidence_band_prose"), &fonts).expect("the binds settle");
        assert!(
            !band.files[0].source.contains("effort goes\\.")
                && band.files[0]
                    .source
                    .contains(&format!("effort{NO_BREAK}goes")),
            "{}",
            band.files[0].source
        );
        assert!(
            band.files[0].source.contains("Chart by Uber"),
            "the one-line credit was bound"
        );
        let (column, _) = bound(captioned("column_plate"), &fonts).expect("the binds settle");
        assert!(
            column.files[0].source.contains("effort goes\\."),
            "{}",
            column.files[0].source
        );
    }

    #[test]
    fn a_one_word_last_line_is_bound_to_its_neighbour_as_the_adapter_binds_it() {
        let fonts = reader_fonts();
        let bare =
            document(&world(&piece(), &fonts).expect("the world builds")).expect("it compiles");
        assert_eq!(
            last_lines(&bare),
            ["BMP.", "A closing line that ends well inside the measure."]
        );
        let (tree, doc) = bound(piece(), &fonts).expect("the binds settle");
        let source = &tree.files[0].source;
        assert!(source.contains("malformed\\u{a0}BMP\\."), "{source}");
        assert_eq!(source.matches(NO_BREAK).count(), 1, "{source}");
        assert_eq!(last_lines(&doc)[0], "malformed BMP.");
    }
}
