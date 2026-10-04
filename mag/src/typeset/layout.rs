use crate::model::kinds::{ContentMode, RenderOperation};
use crate::model::manifest::{load_edition, Edition, LoadOptions, Records};
use crate::model::records::load_records;
use crate::typeset::content::Tree;
use crate::typeset::legible::{ENLARGED, ENLARGED_MIN_PPI};
use crate::typeset::media::pixels;
use crate::typeset::template::TEMPLATE_TYP;
use anyhow::{bail, Context, Result};
use serde_json::{json, Map, Value};
use std::path::Path;
use typst::foundations::Value as Typed;
use typst::introspection::{Location, MetadataElem, StateUpdateElem, Tag};
use typst::layout::{Frame, FrameItem};
use typst_layout::PagedDocument;

pub const DESIGN: &str = "Typst / A5 fold proof";
const OPENER_STATE: &str = "opener-parts";
const FIT_TOLERANCE_PT: f64 = 0.01;
const RASTER_NUDGE_PT: f64 = 0.005;
const MIN_FIGURE_PPI: f64 = 300.0;

#[derive(Debug, Default)]
pub struct Piece {
    pub id: String,
    pub head: usize,
    pub mark: Option<Location>,
    pub foot: Option<usize>,
    pub illustrated: bool,
    pub opener_bottom: Option<f64>,
    pub opener_end: Option<usize>,
    pub figures: Vec<usize>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Placed {
    pub id: String,
    pub page: usize,
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
    pub turned: bool,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Tail {
    pub article: String,
    pub printed: bool,
    pub height: f64,
    pub room: f64,
}

#[derive(Debug)]
pub struct Measured {
    pub pieces: Vec<Piece>,
    pub boxes: Vec<Placed>,
    pub tails: Vec<Tail>,
    pub total_pages: usize,
    pub page_height: f64,
    pub content_bottom: f64,
}

pub(crate) fn declared_pt(name: &str) -> Result<f64> {
    let prefix = format!("#let {name} = ");
    TEMPLATE_TYP
        .lines()
        .find_map(|line| line.strip_prefix(&prefix)?.strip_suffix("pt")?.parse().ok())
        .with_context(|| format!("the template declares no {name} in points"))
}

fn placed(value: &Typed, page: usize, x: f64, y: f64) -> Result<Placed> {
    let id = text(value, "id").context("a figure box carries no id")?;
    let width = points(value, "width").context("a figure box carries no width")?;
    let height = points(value, "height").context("a figure box carries no height")?;
    let turned =
        matches!(value, Typed::Dict(d) if matches!(d.get("turned"), Ok(Typed::Bool(true))));
    Ok(match turned {
        true => Placed {
            id,
            page,
            x,
            y: y - width,
            width: height,
            height: width,
            turned,
        },
        false => Placed {
            id,
            page,
            x,
            y,
            width,
            height,
            turned,
        },
    })
}

fn text(value: &Typed, key: &str) -> Option<String> {
    match value {
        Typed::Str(s) => Some(s.to_string()),
        Typed::Dict(d) => d.get(key).ok().and_then(|v| text(v, "")),
        _ => None,
    }
}

fn points(value: &Typed, key: &str) -> Option<f64> {
    match value {
        Typed::Dict(d) => match d.get(key).ok()? {
            Typed::Length(length) => Some(length.abs.to_pt()),
            _ => None,
        },
        _ => None,
    }
}

fn tail(value: &Typed) -> Option<Tail> {
    let Typed::Dict(d) = value else { return None };
    Some(Tail {
        article: text(value, "article")?,
        printed: matches!(d.get("printed").ok()?, Typed::Bool(true)),
        height: points(value, "height")?,
        room: points(value, "room")?,
    })
}

fn ink_bottom(frame: &Frame, top: f64) -> f64 {
    frame
        .items()
        .fold(top + frame.height().to_pt(), |low, (at, item)| {
            let y = top + at.y.to_pt();
            match item {
                FrameItem::Group(group) => low.max(ink_bottom(&group.frame, y)),
                FrameItem::Text(text) => {
                    low.max(y - text.font.metrics().descender.at(text.size).to_pt())
                }
                _ => low,
            }
        })
}

fn block_after(frame: &Frame, mark: Location, top: f64) -> Option<f64> {
    let mut armed = false;
    for (at, item) in frame.items() {
        let y = top + at.y.to_pt();
        match item {
            FrameItem::Tag(Tag::Start(content, _)) => armed |= content.location() == Some(mark),
            FrameItem::Group(group) if armed => return Some(ink_bottom(&group.frame, y)),
            FrameItem::Group(group) => {
                if let Some(bottom) = block_after(&group.frame, mark, y) {
                    return Some(bottom);
                }
            }
            _ => {}
        }
    }
    None
}

pub fn measure(document: &PagedDocument) -> Result<Measured> {
    let introspector = document.introspector();
    let mut pieces: Vec<Piece> = Vec::new();
    let (mut boxes, mut tails) = (Vec::new(), Vec::new());
    for content in introspector.elements().all() {
        let Some(at) = content.location().and_then(|l| introspector.position(l)) else {
            continue;
        };
        let page = at.page.get();
        let open = pieces.last_mut().filter(|p| p.foot.is_none());
        if content.to_packed::<StateUpdateElem>().is_some() {
            if let Some(piece) = open {
                piece.illustrated |=
                    content.get_by_name("key").ok() == Some(Typed::Str(OPENER_STATE.into()));
            }
            continue;
        }
        let Some(meta) = content.to_packed::<MetadataElem>() else {
            continue;
        };
        let label = content.label().map(|l| l.resolve().as_str().to_string());
        match (label.as_deref(), open) {
            (Some("mag-piece"), _) => pieces.push(Piece {
                id: text(&meta.value, "id").context("a mag-piece mark carries no id")?,
                head: page,
                mark: content.location(),
                ..Piece::default()
            }),
            (Some("mag-piece-end"), Some(piece)) => piece.foot = Some(page),
            (Some("mag-opener-end"), Some(piece)) => piece.opener_end = Some(page),
            (Some("mag-figure-box"), _) => boxes.push(placed(
                &meta.value,
                page,
                at.point.x.to_pt(),
                at.point.y.to_pt(),
            )?),
            (Some("mag-tail"), _) => {
                tails.push(tail(&meta.value).context("a tail mark is malformed")?);
            }
            (Some("mag-flow"), Some(piece))
                if text(&meta.value, "kind").as_deref() == Some("figure") =>
            {
                piece.figures.push(page);
            }
            _ => {}
        }
    }
    if let Some(piece) = pieces.iter().find(|p| p.foot.is_none()) {
        bail!("piece {} has no end mark in the typst document", piece.id);
    }
    if let Some(piece) = pieces
        .iter()
        .find(|p| p.article().is_some() && !p.illustrated && p.opener_end.is_none())
    {
        bail!("the plain opener of {} has no opener-end mark", piece.id);
    }
    for piece in pieces.iter_mut().filter(|p| p.illustrated) {
        let frame = &document.pages()[piece.head - 1].frame;
        piece.opener_bottom = piece.mark.and_then(|mark| block_after(frame, mark, 0.0));
        anyhow::ensure!(
            piece.opener_bottom.is_some(),
            "the illustrated opener of {} has no block after its piece mark on page {}",
            piece.id,
            piece.head
        );
    }
    let page_height = document
        .pages()
        .first()
        .context("the typst document has no pages")?
        .frame
        .height()
        .to_pt();
    Ok(Measured {
        pieces,
        boxes,
        tails,
        total_pages: document.pages().len(),
        page_height,
        content_bottom: page_height - declared_pt("MARGIN-BOTTOM")?,
    })
}

impl Piece {
    fn span(&self) -> usize {
        self.foot.unwrap_or(self.head) - self.head + 1
    }

    fn article(&self) -> Option<&str> {
        self.id.strip_prefix("article-")
    }

    fn opener_fits(&self, bottom: f64) -> Option<bool> {
        self.opener_bottom.map(|y| y <= bottom + FIT_TOLERANCE_PT)
    }
}

impl Measured {
    fn articles(&self) -> impl Iterator<Item = (&str, &Piece)> {
        self.pieces.iter().filter_map(|p| Some((p.article()?, p)))
    }

    pub fn article_pages(&self) -> Map<String, Value> {
        self.articles()
            .map(|(id, p)| (id.to_string(), json!(p.span())))
            .collect()
    }

    pub fn opener_fits(&self) -> Map<String, Value> {
        self.articles()
            .filter_map(|(id, p)| {
                Some((id.to_string(), json!(p.opener_fits(self.content_bottom)?)))
            })
            .collect()
    }

    pub fn plain_opener_fits(&self) -> Map<String, Value> {
        self.articles()
            .filter_map(|(id, p)| Some((id.to_string(), json!(p.opener_end? == p.head))))
            .collect()
    }

    pub fn editorial_pages(&self) -> Option<usize> {
        self.pieces
            .iter()
            .find(|p| p.id == "editorial")
            .map(Piece::span)
    }

    pub fn toc(&self) -> Map<String, Value> {
        self.pieces
            .iter()
            .map(|p| (p.article().unwrap_or(&p.id).to_string(), json!(p.head)))
            .collect()
    }

    pub fn row(&self, language: &str, figures: usize, critic: &str) -> Value {
        json!({
            "language": language,
            "totalPages": self.total_pages,
            "editorialPages": self.editorial_pages().unwrap_or(0),
            "articlePages": self.article_pages(),
            "articleOpenerFits": self.opener_fits(),
            "figureCount": figures,
            "criticResult": critic,
        })
    }
}

pub fn edition(root: &Path, edition_id: &str, publication_name: &str) -> Result<Edition> {
    let records: Records = load_records(&root.join("library").join("sources"))?
        .into_iter()
        .map(|record| (record.id.clone(), record))
        .collect();
    let known = records.keys().cloned().collect();
    Ok(load_edition(
        root,
        edition_id,
        &known,
        &LoadOptions {
            publication_name,
            source_records: Some(&records),
            allow_missing_art: false,
            allow_unanchored_figures: false,
        },
    )?)
}

fn literal_after<'a>(line: &'a str, key: &str) -> Option<&'a str> {
    line.trim().strip_prefix(key)?.strip_suffix(',')
}

pub fn emitted_figures(tree: &Tree) -> Vec<(String, String)> {
    let mut out = Vec::new();
    for file in &tree.files {
        let (mut piece, mut wanted) = (String::new(), "");
        for line in file.source.lines() {
            match line {
                "#piece(" | "#figure-block(" => wanted = line,
                _ => {
                    let Some(id) = literal_after(line, "id: ")
                        .and_then(|l| serde_json::from_str::<String>(l).ok())
                    else {
                        continue;
                    };
                    match std::mem::take(&mut wanted) {
                        "#piece(" => piece = id,
                        "#figure-block(" => out.push((piece.clone(), id)),
                        _ => {}
                    }
                }
            }
        }
    }
    out
}

fn page_cap(mode: ContentMode) -> usize {
    if mode == ContentMode::Verbatim {
        10
    } else {
        7
    }
}

fn figures(edition: &Edition, measured: &Measured, tree: &Tree, root: &Path) -> Result<Vec<Value>> {
    let mut pages = measured
        .pieces
        .iter()
        .flat_map(|p| p.figures.iter().map(move |page| (p.id.as_str(), *page)));
    let mut out = Vec::new();
    for (piece, id) in emitted_figures(tree) {
        let (placed_in, page) = pages
            .next()
            .with_context(|| format!("figure {id} has no placement mark in the typst document"))?;
        let article = piece.strip_prefix("article-").unwrap_or(&piece);
        anyhow::ensure!(
            placed_in == piece,
            "figure {id} of {piece} was marked inside {placed_in}"
        );
        let figure = edition
            .articles
            .iter()
            .filter(|a| a.id == article)
            .flat_map(|a| &a.figures)
            .find(|f| f.id == id)
            .with_context(|| format!("figure {id} is not declared by article {article}"))?;
        let (width, height) = pixels(&figure.path)?;
        let placed = measured
            .boxes
            .iter()
            .find(|b| b.id == id && b.page >= page)
            .with_context(|| format!("figure {id} placed no image box"))?;
        let ppi = match placed.turned {
            true => effective_ppi((width, height), placed.height, placed.width),
            false => effective_ppi((width, height), placed.width, placed.height),
        };
        let floor = match ENLARGED.contains(&figure.layout) {
            true => ENLARGED_MIN_PPI,
            false => MIN_FIGURE_PPI,
        };
        if ppi < floor {
            bail!(
                "Curated figure {id} resolves to {ppi:.1} ppi at its Quiet Standard placement; \
                 the minimum is {floor:.0} ppi"
            );
        }
        let bottom = measured.page_height - placed.y - placed.height + RASTER_NUDGE_PT;
        out.push(json!({
            "id": id,
            "article_id": article,
            "page": placed.page,
            "path": figure.path.strip_prefix(root).unwrap_or(&figure.path).to_string_lossy().replace('\\', "/"),
            "pixel_dimensions": [width, height],
            "box_points": ([placed.x, bottom, placed.width, placed.height].map(|v| rounded(v, 3))),
            "effective_ppi": rounded(ppi, 1),
            "caption": figure.caption,
            "credit": figure.credit,
        }));
    }
    anyhow::ensure!(
        pages.next().is_none(),
        "the typst document marks more figures than the tree emits"
    );
    Ok(out)
}

fn rounded(value: f64, places: i32) -> f64 {
    let scale = 10f64.powi(places);
    (value * scale).round() / scale
}

fn effective_ppi(pixels: (u32, u32), width: f64, height: f64) -> f64 {
    (f64::from(pixels.0) / (width / 72.0)).min(f64::from(pixels.1) / (height / 72.0))
}

fn tail_art(article: &crate::model::manifest::Article, measured: &Measured) -> Result<Value> {
    let tail = match article.tail_art {
        None => None,
        Some(_) => Some(
            measured
                .tails
                .iter()
                .find(|t| t.article == article.id)
                .with_context(|| format!("the tail art of {} left no mark", article.id))?,
        ),
    };
    let printed = tail.is_some_and(|t| t.printed);
    if let (Some(path), Some(t)) = (&article.tail_art, tail.filter(|t| t.printed)) {
        let ppi = effective_ppi(pixels(path)?, declared_pt("MEASURE")?, t.height);
        if ppi < MIN_FIGURE_PPI {
            bail!(
                "Article tail art {} resolves to {ppi:.1} ppi; the minimum is {MIN_FIGURE_PPI:.0} ppi",
                path.display()
            );
        }
    }
    Ok(json!({
        "article": article.id,
        "declared": tail.is_some(),
        "printed": printed,
        "height_points": tail.filter(|t| t.printed).map(|t| rounded(t.height, 4)),
        "drop_reason": tail.filter(|t| !t.printed).map(|t| format!(
            "the article's last page leaves {:.1}pt of open tail room below the end mark's \
             12pt clearance; the strip prints at its one {:.1}pt size or not at all",
            t.room, t.height
        )),
    }))
}

pub fn manifest_layout(
    edition: &Edition,
    measured: &Measured,
    tree: &Tree,
    root: &Path,
) -> Result<Value> {
    let by_article = |f: &dyn Fn(&crate::model::manifest::Article) -> Value| -> Map<String, Value> {
        edition
            .articles
            .iter()
            .map(|a| (a.id.clone(), f(a)))
            .collect()
    };
    Ok(json!({
        "design_direction": DESIGN,
        "cover_art_size_points": null,
        "article_terminal_balance": {},
        "maximum_article_pages": edition.format.max_article_pages.unwrap_or(7),
        "article_pages": measured.article_pages(),
        "toc": measured.toc(),
        "article_opener_fits": measured.opener_fits(),
        "article_page_caps": by_article(&|a| json!(page_cap(a.content_mode))),
        "article_content_modes": by_article(&|a| json!(a.content_mode.as_str())),
        "maximum_editorial_pages": edition.format.max_editorial_pages.unwrap_or(2),
        "editorial_pages": measured.editorial_pages(),
        "figures": figures(edition, measured, tree, root)?,
        "tail_arts": edition
            .articles
            .iter()
            .map(|a| tail_art(a, measured))
            .collect::<Result<Vec<_>>>()?,
    }))
}

pub struct Request<'a> {
    pub operation: &'a str,
    pub article: Option<&'a str>,
    pub edition: &'a Edition,
    pub staged: &'a Path,
    pub out_dir: &'a Path,
    pub render_dir: &'a Path,
    pub work: &'a Path,
    pub assets: &'a Path,
    pub raw: &'a Value,
}

pub fn cap_warnings(layout: &Value) -> Vec<String> {
    let pages = layout["article_pages"]
        .as_object()
        .cloned()
        .unwrap_or_default();
    pages
        .iter()
        .filter(|(id, _)| layout["article_content_modes"][id.as_str()] == ContentMode::Verbatim.as_str())
        .filter_map(|(id, count)| {
            let (count, cap) = (count.as_u64()?, layout["article_page_caps"][id].as_u64()?);
            (count > cap).then(|| {
                format!("WARNING: verbatim article past the page cap, rendering anyway: {id} ({count} pages, cap {cap})")
            })
        })
        .collect()
}

fn written(path: &Path, bytes: &[u8], kind: &str) -> Result<Value> {
    std::fs::write(path, bytes).with_context(|| format!("writing {}", path.display()))?;
    Ok(json!({"kind": kind, "path": path.display().to_string()}))
}

pub fn report(request: &Request, document: &PagedDocument, tree: &Tree) -> Result<Value> {
    let measured = measure(document)?;
    for (id, _) in measured
        .plain_opener_fits()
        .iter()
        .filter(|(_, fits)| fits.as_bool() == Some(false))
    {
        eprintln!("warning: the plain opener of {id} runs past its first page");
    }
    if let Some(article) = request.article {
        anyhow::ensure!(
            measured.article_pages().contains_key(article),
            "unknown measured article: {article}"
        );
    }
    let edition = request.edition;
    let layout = manifest_layout(edition, &measured, tree, request.staged)?;
    let figures = layout["figures"].as_array().map_or(0, Vec::len);
    let row = |critic: &str| measured.row(&edition.language, figures, critic);
    let warnings = cap_warnings(&layout);
    if request.operation != RenderOperation::RenderEdition.as_str() {
        let file = written(
            &request.out_dir.join("layout.json"),
            (serde_json::to_string_pretty(&json!({ "layout": layout }))? + "\n").as_bytes(),
            "render_layout",
        )?;
        return Ok(
            json!({"operation": request.operation, "layouts": [row("not_run")], "files": [file], "warnings": warnings}),
        );
    }
    let (files, critic) = super::release::publish(&super::release::Publish {
        request: request.raw,
        edition,
        layout,
        interior: crate::typeset::template::pdf(document)?,
        staged: request.staged,
        assets: request.assets,
        render_dir: request.render_dir,
        work: request.work,
        out_dir: request.out_dir,
    })?;
    Ok(
        json!({"operation": request.operation, "layouts": [row(&critic)], "files": files, "warnings": warnings}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::{pipeline, File, Inputs};
    use crate::typeset::template::{self, FONT_DIR, ROOT_TYP};
    use crate::typeset::world::Sources;
    use std::collections::BTreeSet;
    use std::path::PathBuf;

    fn roots() -> (PathBuf, PathBuf) {
        let crate_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo = crate_dir
            .parent()
            .expect("the crate sits inside the repository")
            .to_path_buf();
        (
            crate_dir.join("tests/typeset_fixtures/corpus"),
            repo.join(FONT_DIR),
        )
    }

    fn compiled(tree: &Tree) -> PagedDocument {
        let (_, fonts) = roots();
        let world =
            Sources::new(tree, template::TEMPLATE_TYP, ROOT_TYP, &fonts).expect("the world builds");
        template::document(&world).expect("the tree compiles")
    }

    fn fixture(edition_id: &str) -> (Tree, PagedDocument, Edition, PathBuf) {
        let (root, fonts) = roots();
        let tree = pipeline(&Inputs {
            root: &root,
            edition_id,
            publication_name: "Fixture Press",
            fonts: &fonts,
            allow_missing_art: false,
            allow_unanchored_figures: false,
        })
        .expect("the fixture loads");
        let document = compiled(&tree);
        let edition =
            edition(&root, edition_id, "Fixture Press").expect("the fixture edition loads");
        (tree, document, edition, root)
    }

    fn opener_run(words: usize) -> Tree {
        titled_run("A Fixture Title", words)
    }

    fn titled_run(title: &str, words: usize) -> Tree {
        let standfirst = vec!["standfirst"; words].join(" ");
        Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: format!(
                    "#piece(id: \"article-a\", kind: \"article\", short-title: \"A\", \
                     opener: \"illustrated_paper_spots_v1\", \
                     titles: ((size: 32.5pt, lines: 1), (size: 30pt, lines: 1)))[\n\
                     #content-label[#label-primary[Feature 01]]\n\
                     #piece-title[{title}]\n\
                     #byline[#byline-prefix[By]#byline-name[ Ada]]\n\
                     #doc-paragraph(standfirst: true, roster: false)[{standfirst}]\n\
                     #doc-paragraph(standfirst: false, roster: false)[Body.]\n]\n"
                ),
            }],
        }
    }

    fn fits(words: usize) -> bool {
        let measured = measure(&compiled(&opener_run(words))).expect("the run measures");
        measured.opener_fits()["a"]
            .as_bool()
            .expect("the illustrated opener is measured")
    }

    #[test]
    fn the_opener_fit_flips_between_two_standfirsts_one_word_apart() {
        let (mut fitting, mut spilling) = (10, 1000);
        assert!(
            fits(fitting) && !fits(spilling),
            "the sweep bounds must straddle the fit"
        );
        while spilling - fitting > 1 {
            let middle = usize::midpoint(fitting, spilling);
            if fits(middle) {
                fitting = middle;
            } else {
                spilling = middle;
            }
        }
        println!("the opener fits at {fitting} standfirst words and spills at {spilling}");
        assert_eq!(spilling, fitting + 1);
    }

    #[test]
    fn the_template_keeps_the_longest_standfirst_prefix_that_fits_the_page() {
        let [Some(keep)] = keeps(1000)[..] else {
            panic!("a spilling standfirst reports the words it keeps");
        };
        assert!(
            split("A Fixture Title", keep) && !split("A Fixture Title", keep + 1),
            "{keep} words is the exact fit"
        );
        assert_eq!(
            keeps(keep),
            vec![None],
            "a standfirst that fits whole never splits"
        );
    }

    #[test]
    fn a_short_standfirst_carry_squeezes_the_opener_or_grows_to_two_lines() {
        let branches: BTreeSet<bool> = (0..16).step_by(3).map(short_carry_branch).collect();
        assert_eq!(branches.len(), 2, "some titles squeeze and some pull back");
    }

    fn short_carry_branch(extra: usize) -> bool {
        let title = format!("A Fixture Title{}", " Word".repeat(extra));
        let keeps = |words| template::standfirst_keeps(&compiled(&titled_run(&title, words)));
        let [Some(keep)] = keeps(1000)[..] else {
            panic!("a spilling standfirst reports the words it keeps");
        };
        let sweep: Vec<_> = (keep + 1..)
            .map(|words| (words, keeps(words)[0]))
            .take_while(|(_, kept)| *kept != Some(keep))
            .collect();
        let line = sweep.len();
        for &(words, kept) in &sweep {
            let fitted = match kept {
                None => opener_fits(&titled_run(&title, words)),
                Some(kept) => kept < keep && words - kept > line && split(&title, kept),
            };
            assert!(
                fitted,
                "{words} words keep {kept:?} of {keep}, {line} per line"
            );
        }
        sweep[0].1.is_none()
    }

    fn keeps(words: usize) -> Vec<Option<usize>> {
        template::standfirst_keeps(&compiled(&opener_run(words)))
    }

    fn split(title: &str, words: usize) -> bool {
        let mut tree = titled_run(title, words);
        tree.files[0].source = tree.files[0].source.replace(
            "roster: false)[standfirst",
            "roster: false, split: true)[standfirst",
        );
        opener_fits(&tree)
    }

    fn opener_fits(tree: &Tree) -> bool {
        let measured = measure(&compiled(tree)).expect("the run measures");
        measured.opener_fits()["a"].as_bool().expect("measured")
    }

    fn plain_fits(note_words: usize) -> bool {
        let note = vec!["note"; note_words].join(" ");
        let tree = Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: format!(
                    "#piece(id: \"article-a\", kind: \"article\", short-title: \"A\")[\n\
                     #piece-title[A Fixture Title]\n\
                     #byline[#byline-prefix[By]#byline-name[ Ada]]\n\
                     #author-note[{note}]\n\
                     #opener-end()\n\
                     #doc-paragraph(standfirst: true, roster: false)[Body.]\n]\n"
                ),
            }],
        };
        let measured = measure(&compiled(&tree)).expect("the run measures");
        measured.plain_opener_fits()["a"]
            .as_bool()
            .expect("measured")
    }

    fn links(document: &PagedDocument) -> Vec<(u32, String)> {
        let pdf = template::pdf(document).expect("the pdf exports");
        let doc = lopdf::Document::load_mem(&pdf).expect("the pdf parses");
        let mut out = Vec::new();
        for (number, id) in doc.get_pages() {
            for annot in doc.get_page_annotations(id).expect("annotations read") {
                let target = match annot.get_deref(b"A", &doc).and_then(|a| a.as_dict()) {
                    Ok(action) => action
                        .get(b"URI")
                        .and_then(lopdf::Object::as_str)
                        .map_or("goto".into(), |u| String::from_utf8_lossy(u).into_owned()),
                    Err(_) => "dest".into(),
                };
                out.push((number, target));
            }
        }
        out
    }

    #[test]
    fn the_contents_and_the_opener_code_carry_their_links() {
        let (_, document, _, _) = fixture("900");
        let contents: Vec<_> = links(&document)
            .into_iter()
            .filter(|(p, _)| *p == 3)
            .collect();
        assert_eq!(
            contents.len(),
            12,
            "three links per contents entry: {contents:?}"
        );
        let mut tree = opener_run(10);
        tree.files[0].source = tree.files[0].source.replace(
            "#doc-paragraph(standfirst: true",
            "#source-link(destination: \"https://example.com/a\", source-id: \"a\")[a]\n\
             #doc-paragraph(standfirst: true",
        );
        let opener = links(&compiled(&tree));
        assert_eq!(opener, vec![(3, "https://example.com/a".to_string()); 2]);
        assert!(links(&compiled(&opener_run(10))).is_empty());
    }

    fn link_rects(body: &str) -> Vec<Vec<f32>> {
        let tree = Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: format!(
                    "#piece(id: \"a\", kind: \"article\", short-title: \"A\")[\n\
                     #piece-title[A Fixture Title]\n\
                     #opener-end()\n\
                     #doc-paragraph(standfirst: false, roster: false)[#doc-link(destination: \
                     \"https://x.org/\", title: none)[{body}]]\n]\n"
                ),
            }],
        };
        let pdf = template::pdf(&compiled(&tree)).expect("the pdf exports");
        let doc = lopdf::Document::load_mem(&pdf).expect("the pdf parses");
        let mut out = Vec::new();
        for (_, id) in doc.get_pages() {
            for annot in doc.get_page_annotations(id).expect("annotations read") {
                let rect = annot.get(b"Rect").and_then(lopdf::Object::as_array);
                let rect = rect.expect("a link has a rect").iter();
                out.push(rect.map(|v| v.as_float().expect("a number")).collect());
            }
        }
        out
    }

    #[test]
    fn an_inline_inside_a_link_adds_no_second_link() {
        assert_eq!(link_rects("plain").len(), 1);
        assert_eq!(link_rects("#emph[pacing the frontier]").len(), 1);
        let part = link_rects("a #strong[bold] b");
        assert!(part.windows(2).all(|pair| pair[0][2] <= pair[1][0] + 1e-3));
        let wrapped = link_rects(&format!("#emph[{}]", vec!["frontier"; 20].join(" ")));
        assert_eq!(wrapped.len(), 3, "one link per line over three lines");
        assert!(wrapped[0][1] > wrapped[1][1] && wrapped[1][1] > wrapped[2][1]);
    }

    #[test]
    fn the_plain_opener_fit_is_read_from_its_end_mark() {
        assert!(plain_fits(10));
        assert!(!plain_fits(4000));
    }

    #[test]
    fn the_fixture_pieces_measure_as_emitted() {
        let (tree, document, edition, root) = fixture("900");
        let measured = measure(&document).expect("the fixture measures");
        let layout = manifest_layout(&edition, &measured, &tree, &root).expect("the layout builds");
        assert_eq!(measured.total_pages, 11);
        assert_eq!(
            layout["toc"],
            json!({"editorial": 4, "plain-opener-article": 5, "second-fixture-article": 8, "section-0": 9})
        );
        assert_eq!(
            layout["article_pages"],
            json!({"plain-opener-article": 3, "second-fixture-article": 1})
        );
        assert_eq!(layout["editorial_pages"], json!(1));
        assert_eq!(layout["article_opener_fits"], json!({}));
        assert_eq!(
            measured.plain_opener_fits(),
            json!({"plain-opener-article": true, "second-fixture-article": true})
                .as_object()
                .cloned()
                .unwrap()
        );
        assert_eq!(layout["figures"][0]["id"], "budget-diagram");
        assert_eq!(layout["figures"][0]["page"], 6);
        assert_eq!(
            layout["figures"][0]["pixel_dimensions"],
            json!([1200, 1000])
        );
        assert_eq!(layout["tail_arts"][1]["declared"], true);
        let figure = &layout["figures"][0];
        assert_eq!(figure["box_points"][0], json!(87.504));
        assert_eq!(figure["box_points"][2], json!(246.0));
        assert_eq!(figure["box_points"][3], json!(205.0));
        assert_eq!(figure["effective_ppi"], json!(351.2));
        assert_eq!(layout["tail_arts"][1]["printed"], true);
        assert_eq!(layout["tail_arts"][1]["height_points"], json!(108.3333));
        let row = measured.row("en", 1, "not_run");
        assert_eq!(row["totalPages"], 11);
        assert_eq!(row["editorialPages"], 1);
    }

    #[test]
    fn a_figure_or_printed_tail_below_300_ppi_is_refused_with_the_adapter_wording() {
        let (tree, document, mut edition, root) = fixture("900");
        let measured = measure(&document).expect("the fixture measures");
        let small = PathBuf::from(media(
            "corpus/library/sources/fixture-source-a/media/diagram-2.png",
        ));
        edition.articles[0].figures[0].path = small;
        let refused = manifest_layout(&edition, &measured, &tree, &root).unwrap_err();
        assert_eq!(
            refused.to_string(),
            "Curated figure budget-diagram resolves to 14.0 ppi at its Quiet Standard placement; \
             the minimum is 300 ppi"
        );
        let (_, _, mut edition, _) = fixture("900");
        let strip = PathBuf::from(media("media/landscape.png"));
        edition.articles[1].tail_art = Some(strip.clone());
        let refused = manifest_layout(&edition, &measured, &tree, &root).unwrap_err();
        assert_eq!(
            refused.to_string(),
            format!(
                "Article tail art {} resolves to 8.9 ppi; the minimum is 300 ppi",
                strip.display()
            )
        );
    }

    fn media(name: &str) -> String {
        format!(
            "{}/tests/typeset_fixtures/{name}",
            env!("CARGO_MANIFEST_DIR")
        )
    }

    fn piece_run(body: &str) -> Tree {
        Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: format!(
                    "#piece(id: \"article-a\", kind: \"article\", short-title: \"A\")[\n\
                     #opener-end()\n{body}]\n"
                ),
            }],
        }
    }

    fn tail_after(gap: usize) -> Tail {
        let tail = media("corpus/editions/900/art/tail.png");
        let run = piece_run(&format!(
            "#v({gap}pt)\n#end-mark[End / 01]\n\
             #tail-art(article: \"a\", path: \"{tail}\", pixels: (1500, 500), fit: \"cover\")\n"
        ));
        let measured = measure(&compiled(&run)).expect("the run measures");
        measured.tails[0].clone()
    }

    #[test]
    fn the_tail_art_prints_only_when_its_strip_fits_the_room_under_the_end_mark() {
        let spill = (0..500).find(|gap| !tail_after(*gap).printed);
        let first = spill.expect("some gap leaves no room for the strip");
        let (fits, spills) = (tail_after(first - 1), tail_after(first));
        assert!(fits.printed);
        assert!(!spills.printed);
        assert!((fits.height - 325.0 / 3.0).abs() < 1e-9);
        assert!(fits.room >= fits.height && spills.room < spills.height);
        assert!((fits.room - spills.room - 1.0).abs() < 1e-6);
    }

    fn anchor_gap(lead: &str) -> f64 {
        let run = piece_run(&format!(
            "{lead}#doc-heading(level: 2)[Anchor]\n\
             #figure-block(id: \"f\", source-id: \"s\", anchor: \"Anchor\", \
             layout: \"evidence_band\", word: \"Figure\", alt: \"a\", \
             path: \"{}\", pixels: (40, 25))[#figure-caption[Cap.]]\n",
            media("media/landscape.png")
        ));
        let document = compiled(&run);
        let measured = measure(&document).expect("the run measures");
        let placed = &measured.boxes[0];
        let frame = &document.pages()[placed.page - 1].frame;
        placed.y - glyph_top(frame, "Anchor", 0.0).expect("the heading is set")
    }

    fn glyph_top(frame: &Frame, word: &str, top: f64) -> Option<f64> {
        frame.items().find_map(|(at, item)| match item {
            FrameItem::Group(group) => glyph_top(&group.frame, word, top + at.y.to_pt()),
            FrameItem::Text(text) if text.text.as_str() == word => Some(top + at.y.to_pt()),
            _ => None,
        })
    }

    #[test]
    fn a_midpage_band_anchor_is_painted_down_by_its_dropped_space_before() {
        let midpage = anchor_gap("#doc-paragraph(standfirst: false, roster: false)[Bridge.]\n");
        let page_top =
            anchor_gap("#doc-paragraph(standfirst: false, roster: false)[Bridge.]\n#colbreak()\n");
        assert!(
            (page_top - midpage - 15.0).abs() < 1e-6,
            "{page_top} against {midpage}"
        );
    }

    #[test]
    fn the_illustrated_fixture_opener_fits_its_page() {
        let (_, document, _, _) = fixture("901");
        let measured = measure(&document).expect("the fixture measures");
        assert_eq!(
            measured.opener_fits(),
            json!({"illustrated-fixture-article": true})
                .as_object()
                .cloned()
                .unwrap()
        );
        let bottom = measured.pieces[0]
            .opener_bottom
            .expect("the opener is measured");
        assert!(
            bottom < measured.content_bottom,
            "{bottom} against {}",
            measured.content_bottom
        );
    }

    #[test]
    fn only_a_verbatim_article_past_its_cap_warns() {
        let layout = json!({
            "article_pages": {"long": 13, "fits": 10, "prose": 9},
            "article_page_caps": {"long": 10, "fits": 10, "prose": 7},
            "article_content_modes": {"long": "verbatim", "fits": "verbatim", "prose": "article"},
        });
        assert_eq!(
            super::cap_warnings(&layout),
            vec!["WARNING: verbatim article past the page cap, rendering anyway: long (13 pages, cap 10)"]
        );
    }

    type Laid = Vec<(f64, f64, FrameItem)>;

    fn laid(body: &str) -> Laid {
        let document = compiled(&piece_run(body));
        let mut out = vec![];
        for (index, page) in document.pages().iter().enumerate() {
            flatten(&page.frame, 0.0, 1e4 * index as f64, &mut out);
        }
        out
    }

    fn flatten(frame: &Frame, x: f64, y: f64, out: &mut Laid) {
        for (at, item) in frame.items() {
            let (x, y) = (x + at.x.to_pt(), y + at.y.to_pt());
            match item {
                FrameItem::Group(group) => flatten(&group.frame, x, y, out),
                _ => out.push((x, y, item.clone())),
            }
        }
    }

    fn word(items: &Laid, word: &str) -> (f64, f64, f64) {
        items
            .iter()
            .find_map(|(x, y, item)| match item {
                FrameItem::Text(text) if text.text.as_str() == word => {
                    Some((*x, *y, text.width().to_pt()))
                }
                _ => None,
            })
            .unwrap_or_else(|| panic!("no text item {word:?}"))
    }

    fn gap(body: &str, above: &str, below: &str) -> f64 {
        let items = laid(body);
        word(&items, below).1 - word(&items, above).1
    }

    fn para(text: &str) -> String {
        format!("#doc-paragraph(standfirst: false, roster: false)[{text}]\n")
    }

    fn bullets(text: &str) -> String {
        format!(
            "#doc-list(ordered: false, start: 1, references: false)[\n  #doc-item[\n{}]\n]\n",
            para(text)
        )
    }

    fn near(found: f64, want: f64) {
        assert!((found - want).abs() < 1e-3, "{found} against {want}");
    }

    #[test]
    fn body_blocks_collapse_their_margins() {
        let line = 13.0;
        near(
            gap(&(para("Alpha.") + &bullets("Beta.")), "Alpha.", "Beta."),
            line + 5.4,
        );
        near(
            gap(&(bullets("Beta.") + &para("Gamma.")), "Beta.", "Gamma."),
            line + 6.0,
        );
        let heading = "#doc-heading(level: 2)[Head]\n".to_string();
        near(
            gap(&(heading.clone() + &bullets("Delta.")), "Head", "Delta."),
            gap(&(heading + &para("Delta.")), "Head", "Delta."),
        );
        let mark = "#end-mark[End / 01]\n";
        let to_mark = line - 10.0046 - 20.0 + 2.47375 + 28.53085;
        near(
            gap(&(para("Alpha.") + mark), "Alpha.", "END / 01"),
            to_mark + 5.4,
        );
        near(
            gap(&(bullets("Beta.") + mark), "Beta.", "END / 01"),
            to_mark + 6.0,
        );
    }

    #[test]
    fn the_running_furniture_paints_after_the_body() {
        let items = laid(&para(&vec!["words"; 900].join(" ")));
        let page = |y: f64| (y / 1e4).floor();
        let rules: Vec<usize> = (0..items.len())
            .filter(|&i| match &items[i].2 {
                FrameItem::Shape(shape, _) => (bounds(&shape.geometry).3 - 0.55).abs() < 1e-6,
                _ => false,
            })
            .collect();
        assert!(
            !rules.is_empty(),
            "the piece runs onto a page with a running head"
        );
        for rule in rules {
            let texts = |range: std::ops::Range<usize>| {
                items[range]
                    .iter()
                    .filter(|(_, y, item)| {
                        page(*y) == page(items[rule].1) && matches!(item, FrameItem::Text(_))
                    })
                    .map(|(_, y, _)| y - 1e4 * page(*y))
                    .collect::<Vec<_>>()
            };
            let (before, after) = (texts(0..rule), texts(rule..items.len()));
            assert!(
                before.iter().any(|y| *y > 100.0),
                "body text precedes the running rule"
            );
            assert!(!after.is_empty(), "the folio follows the running rule");
            for y in &after {
                near(*y, 595.2756 - 19.5);
            }
        }
    }

    #[test]
    fn inline_code_carries_its_padding_chip_and_line_box() {
        let items = laid(&(para("Alpha #inline-code[beta] gamma") + &para("Omega.")));
        let (x, y, width) = word(&items, "beta");
        let pads: Vec<f64> = items
            .iter()
            .filter_map(|(_, _, item)| match item {
                FrameItem::Text(text) if text.text.as_str() == "\u{a0}" => {
                    Some(text.width().to_pt())
                }
                _ => None,
            })
            .collect();
        assert_eq!(pads.len(), 2);
        for pad in &pads {
            near(*pad, 3.0);
        }
        let chip = items
            .iter()
            .find_map(|(cx, cy, item)| match item {
                FrameItem::Shape(shape, _) if shape.fill.is_some() => {
                    let (x0, y0, x1, y1) = bounds(&shape.geometry);
                    Some((cx + x0, cy + y0, x1 - x0, y1 - y0))
                }
                _ => None,
            })
            .expect("the code chip is painted");
        let size = 8.2;
        near(chip.0, x - 3.0);
        near(chip.1, y - (0.855 * size + 1.2));
        near(chip.2, width + 6.0);
        near(chip.3, size + 2.4);
        let grown = (6.5 - 0.355 * size) - (13.0 - 10.0046);
        near(word(&items, "Omega.").1 - y, 13.0 + 5.4 + grown);
    }

    fn bounds(geometry: &typst::visualize::Geometry) -> (f64, f64, f64, f64) {
        use typst::visualize::{CurveItem, Geometry};
        let points: Vec<_> = match geometry {
            Geometry::Curve(curve) => curve
                .0
                .iter()
                .flat_map(|item| match item {
                    CurveItem::Move(p) | CurveItem::Line(p) => vec![*p],
                    CurveItem::Cubic(a, b, c) => vec![*a, *b, *c],
                    CurveItem::Close => vec![],
                })
                .collect(),
            Geometry::Rect(size) => vec![typst::layout::Point::zero(), size.to_point()],
            Geometry::Line(p) => vec![typst::layout::Point::zero(), *p],
        };
        let fold = |f: fn(f64, f64) -> f64, pick: fn(&typst::layout::Point) -> f64, start| {
            points.iter().map(pick).fold(start, f)
        };
        (
            fold(f64::min, |p| p.x.to_pt(), f64::MAX),
            fold(f64::min, |p| p.y.to_pt(), f64::MAX),
            fold(f64::max, |p| p.x.to_pt(), f64::MIN),
            fold(f64::max, |p| p.y.to_pt(), f64::MIN),
        )
    }

    #[test]
    fn the_list_disc_takes_the_bezier_constant() {
        let items = laid(&bullets("Beta."));
        let controls: Vec<f64> = items
            .iter()
            .filter_map(|(_, _, item)| match item {
                FrameItem::Shape(shape, _) => match &shape.geometry {
                    typst::visualize::Geometry::Curve(curve) => Some(curve),
                    _ => None,
                },
                _ => None,
            })
            .flat_map(|curve| curve.0.iter())
            .filter_map(|item| match item {
                typst::visualize::CurveItem::Cubic(a, b, _) => Some(a.y.to_pt() + b.x.to_pt()),
                _ => None,
            })
            .collect();
        assert_eq!(controls.len(), 4, "{controls:?}");
        near(controls[0], 2.0 * 2.5 * (1.0 - 0.55));
        assert!((controls[0] - 2.0 * 2.5 * (1.0 - 0.552_284_75)).abs() > 8e-3);
    }
}
