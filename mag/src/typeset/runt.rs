use crate::typeset::content::Tree;
use crate::typeset::decisions::{locate, Splice};
use crate::typeset::geometry::geometry;
use crate::typeset::hyphen::Hyphenation;
use crate::typeset::measure::Metrics;
use crate::typeset::template::{document, world};
use anyhow::{bail, ensure, Result};
use typst::introspection::{Location, Tag};
use typst::layout::{FrameItem, Point, Transform};
use typst::text::TextItem;
use typst::{World, WorldExt};
use typst_layout::PagedDocument;
use typst_syntax::{FileId, Span};

const PROSE: [&str; 3] = ["mag-prose", "mag-prose-band", "mag-prose-compact"];
const RUNT_MEASURE_FRACTION: f64 = 0.15;
const RUNT_MAX_RAG_FRACTION: f64 = 0.33;
const PASSES: usize = 6;
const LADDER_LIMIT: usize = 2;
const UNHYPHENATED: &str = "#text(hyphenate: false)[";
const LINE_SLACK: f64 = 4.0;
const NO_BREAK: &str = "\\u{a0}";
const SHY: &str = "\u{ad}";

type Anchor = (Span, usize);

#[derive(Default)]
struct Line {
    x0: f64,
    x1: f64,
    words: Vec<(f64, String, String)>,
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
    let style = format!("{:?}/{}/{:?}", text.font, text.size.to_pt(), text.fill);
    line.words.push((x, text.text.to_string(), style));
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
                    .and_then(|l| PROSE.iter().position(|name| *name == l.resolve().as_str()));
                if let (Some(edge), Some(loc)) = (edge, content.location()) {
                    open.push(loc);
                    if !blocks.iter().any(|(l, _)| *l == loc) {
                        let right = right + [0.0, geometry().rail, -geometry().compact_inset][edge];
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
                    tx: typst::layout::Abs::default(),
                    ty: typst::layout::Abs::default(),
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
        .map(|(_, t, _)| t.as_str())
        .collect::<String>()
        .split_whitespace()
        .map(str::to_string)
        .collect()
}

fn runt(block: &Block, metrics: &Metrics, english: bool) -> Result<Option<(Anchor, Anchor)>> {
    let mut lines: Vec<_> = block.lines.iter().collect();
    lines.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.total_cmp(&b.1)));
    let lines: Vec<&Line> = lines.into_iter().map(|(_, _, l)| l).collect();
    let [.., previous, last] = lines.as_slice() else {
        return Ok(None);
    };
    let (runt, before) = (words(last), words(previous));
    let (Some(prior), Some(first)) = (before.last(), runt.first()) else {
        return Ok(None);
    };
    let measure = block.right - lines.iter().map(|l| l.x0).fold(f64::MAX, f64::min);
    let size = block.size;
    let hyphen = (block.hyphenates || english) && prior.ends_with(['-', '\u{2010}', '\u{ad}']);
    let width = last.x1 - last.x0;
    let pair = metrics.width("serif", &format!("{prior}\u{a0}{first}"), size)?;
    let opened = measure
        - (previous.x1 - previous.x0 - metrics.width("serif", &format!(" {prior}"), size)?);
    let fits = runt.len() == 1
        && !hyphen
        && width <= measure * RUNT_MEASURE_FRACTION
        && pair <= measure
        && opened <= measure * RUNT_MAX_RAG_FRACTION;
    Ok(fits
        .then(|| previous.last.as_ref().zip(last.first.as_ref()))
        .flatten()
        .map(|(start, end)| (start.1, end.1)))
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

fn prose_blocks(doc: &PagedDocument) -> Vec<(Location, Block)> {
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
            margin + geometry().rail + geometry().measure,
            &mut open,
            &mut blocks,
        );
    }
    blocks
}

fn binds(
    doc: &PagedDocument,
    sources: &dyn World,
    metrics: &Metrics,
    english: bool,
) -> Result<Vec<(FileId, usize, usize)>> {
    let mut gaps = Vec::new();
    for (_, block) in &prose_blocks(doc) {
        gaps.extend(runt(block, metrics, english)?.and_then(|anchors| gap(sources, anchors)));
    }
    Ok(gaps)
}

type Row = (f64, Vec<(f64, String, String)>, Option<Anchor>);

fn ordered(block: &Block) -> Vec<Row> {
    let mut lines: Vec<_> = block.lines.iter().collect();
    lines.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.total_cmp(&b.1)));
    lines
        .into_iter()
        .map(|(_, _, line)| {
            let mut items = line.words.clone();
            items.sort_by(|a, b| a.0.total_cmp(&b.0));
            (
                line.x0,
                items,
                line.last.as_ref().map(|(_, anchor)| *anchor),
            )
        })
        .collect()
}

fn word(
    sources: &dyn World,
    (span, offset): Anchor,
    bound: impl Fn(char) -> bool,
) -> Option<(FileId, usize, String)> {
    let file = span.id()?;
    let (source, range) = (sources.source(file).ok()?, sources.range(span)?);
    let text = source.text();
    let mut at = (range.start + offset).min(text.len());
    while !text.is_char_boundary(at) {
        at -= 1;
    }
    let from = text[..at].rfind(&bound).map_or(0, |i| i + 1);
    let to = text[at..].find(&bound).map_or(text.len(), |i| at + i);
    Some((file, from, text[from..to].to_string()))
}

fn unhyphenated(sources: &dyn World, anchor: Anchor) -> Vec<(FileId, usize, usize)> {
    let bound = |c: char| c.is_whitespace() || "[]#\\".contains(c);
    let Some((file, from, text)) = word(sources, anchor, bound) else {
        return vec![];
    };
    text.match_indices(SHY)
        .map(|(i, m)| (file, from + i, from + i + m.len()))
        .collect()
}

fn unladdered(sources: &dyn World, anchor: Anchor) -> Vec<Edit> {
    let shy = unhyphenated(sources, anchor);
    if !shy.is_empty() {
        return shy.into_iter().map(|(f, a, b)| (f, a, b, "")).collect();
    }
    let Some((file, from, text)) = word(sources, anchor, |c| !c.is_alphanumeric()) else {
        return vec![];
    };
    let to = from + text.len();
    vec![(file, from, from, UNHYPHENATED), (file, to, to, "]")]
}

fn hyphen_ended(row: &Row) -> Option<char> {
    let mut chars = row.1.iter().rev().flat_map(|(_, t, _)| t.chars().rev());
    chars
        .find(|c| !c.is_whitespace())
        .filter(|c| ['-', '\u{2010}', '\u{ad}'].contains(c))
}

fn ladders(rows: &[Row]) -> Vec<std::ops::Range<usize>> {
    let mut start = 0;
    let mut found = vec![];
    for i in 0..=rows.len() {
        if i < rows.len() && hyphen_ended(&rows[i]).is_some() {
            continue;
        }
        if i - start > LADDER_LIMIT {
            found.push(start..i);
        }
        start = i + 1;
    }
    found
}

fn laddered(doc: &PagedDocument, sources: &dyn World) -> Vec<Edit> {
    prose_blocks(doc)
        .iter()
        .flat_map(|(_, block)| {
            let rows = ordered(block);
            ladders(&rows)
                .into_iter()
                .filter_map(|run| {
                    run.skip(LADDER_LIMIT)
                        .find(|&i| hyphen_ended(&rows[i]) == Some('\u{ad}'))
                })
                .filter_map(|i| rows[i].2)
                .flat_map(|anchor| unladdered(sources, anchor))
                .collect::<Vec<_>>()
        })
        .collect()
}

pub fn ladder_warnings(doc: &PagedDocument, edition: &str) -> Vec<String> {
    prose_blocks(doc)
        .iter()
        .enumerate()
        .flat_map(|(key, (_, block))| {
            let mut pages: Vec<_> = block.lines.iter().map(|(p, y, _)| (*p, *y)).collect();
            pages.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.total_cmp(&b.1)));
            let rows = ordered(block);
            ladders(&rows).into_iter().map(move |run| {
                let sample: String = rows[run.start].1.iter().map(|(_, t, _)| t.as_str()).collect();
                format!(
                    "hyphen ladder: edition {edition} reader page {} sets {} consecutive \
                     hyphen-ended lines in prose block {key} (allowed {LADDER_LIMIT}), starting {:?}",
                    pages[run.start].0 + 1,
                    run.len(),
                    sample.chars().take(60).collect::<String>()
                )
            })
        })
        .collect()
}

type Edit = (FileId, usize, usize, &'static str);

pub fn bound(mut tree: Tree, hyphenation: Hyphenation) -> Result<(Tree, PagedDocument)> {
    for _ in 0..PASSES {
        let sources = world(&tree)?;
        let doc = document(&sources)?;
        let runts = binds(&doc, &sources, &Metrics, hyphenation.english)?;
        let stuck = runts.len();
        let ladders = match hyphenation.limit_ladders {
            true => laddered(&doc, &sources),
            false => Vec::new(),
        };
        let edits: Vec<Edit> = runts
            .into_iter()
            .map(|(f, a, b)| (f, a, b, NO_BREAK))
            .chain(ladders)
            .collect();
        let before = tree.decisions.clone();
        for (file, a, b, with) in edits {
            let (unit, from, to) = locate(sources.marks(file), a, b)?;
            tree.decisions.splice(unit, Splice { from, to, with });
        }
        for choice in crate::typeset::flow::choices(&doc, &sources, &tree) {
            tree.decisions.choose(choice);
        }
        if tree.decisions == before {
            ensure!(
                stuck == 0,
                "the Typst reader's runt binds did not settle: {stuck} runts remain after binding"
            );
            return Ok((tree, doc));
        }
    }
    bail!("the Typst reader's runt binds did not settle within {PASSES} passes")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::File;
    use crate::typeset::decisions::unit;

    const RUNT: &str = "7\\:10\\:25 AM EST\\, July 30\\. A malformed BMP from a RIPE address\\, \
        presenting as Chrome 131\\.0\\.0 on Windows 10\\. We initially assumed whoever built it had \
        patch\\-diffed the fix themselves\\. A public PoC was committed to GitHub at 9\\:47\\:30 PM \
        UTC on July 29\\, over five hours before our patch was fully deployed at 11\\:09 PM EDT\\, \
        and 13 hours\\, 22 minutes\\, and 55 seconds before that attempt\\. André Baptista of \
        Ethiack\\, one of the vulnerability’s discoverers\\, pointed out in a public exchange with \
        me on X that this PoC was the first to use a malformed BMP\\.";
    const FULL: &str = "A closing line that ends well inside the measure\\.";

    fn piece() -> Tree {
        Tree {
            files: vec![File {
                path: "main.typ".into(),
                source: format!(
                    "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                     #doc-paragraph[{}]\n\n#doc-paragraph[{}]\n]\n",
                    unit(0, RUNT),
                    unit(1, FULL)
                ),
            }],
            ..Tree::default()
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
                lines.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.total_cmp(&b.1)));
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
                     path: \"{image}\", pixels: (40, 25))[#figure-caption[{}]]\n]\n",
                    unit(0, CAPTION)
                ),
            }],
            ..Tree::default()
        }
    }

    #[test]
    fn a_ladder_is_more_than_two_consecutive_hyphen_ended_lines() {
        let row = |end: &str| (0.0, vec![(0.0, format!("word{end}"), String::new())], None);
        let rows: Vec<Row> = ["\u{ad}", "-", "\u{2010}", "", "\u{ad}", "\u{ad}", ""]
            .iter()
            .map(|end| row(end))
            .collect();
        assert_eq!(ladders(&rows), vec![0..3]);
        assert_eq!(ladders(&rows[1..]), Vec::<std::ops::Range<usize>>::new());
        assert_eq!(hyphen_ended(&rows[0]), Some('\u{ad}'));
    }

    #[test]
    fn a_band_caption_is_bound_on_the_band_s_own_measure() {
        let (band, _) =
            bound(captioned("evidence_band_prose"), Hyphenation::PLAIN).expect("the binds settle");
        let band = band
            .flat()
            .expect("the tree renders")
            .files
            .remove(0)
            .source;
        assert!(
            !band.contains("effort goes\\.") && band.contains(&format!("effort{NO_BREAK}goes")),
            "{band}"
        );
        let (column, _) =
            bound(captioned("column_plate"), Hyphenation::PLAIN).expect("the binds settle");
        let column = column
            .flat()
            .expect("the tree renders")
            .files
            .remove(0)
            .source;
        assert!(column.contains("effort goes\\."), "{column}");
    }

    #[test]
    fn a_one_word_last_line_is_bound_to_its_neighbour_as_the_adapter_binds_it() {
        let bare = document(&world(&piece()).expect("the world builds")).expect("it compiles");
        assert_eq!(
            last_lines(&bare),
            ["BMP.", "A closing line that ends well inside the measure."]
        );
        let (tree, doc) = bound(piece(), Hyphenation::PLAIN).expect("the binds settle");
        let source = &tree.flat().expect("the tree renders").files[0]
            .source
            .clone();
        assert!(source.contains("malformed\\u{a0}BMP\\."), "{source}");
        assert_eq!(source.matches(NO_BREAK).count(), 1, "{source}");
        assert_eq!(last_lines(&doc)[0], "malformed BMP.");
    }
}
