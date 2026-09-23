use crate::model::manifest::{load_edition, Edition, LoadOptions, Records};
use crate::model::records::load_records;
use crate::typeset::content::Tree;
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
const TAIL_DROP: &str = "the typst template sets no tail art";

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

#[derive(Debug)]
pub struct Measured {
    pub pieces: Vec<Piece>,
    pub total_pages: usize,
    pub content_bottom: f64,
}

fn declared_pt(name: &str) -> Result<f64> {
    let prefix = format!("#let {name} = ");
    TEMPLATE_TYP
        .lines()
        .find_map(|line| line.strip_prefix(&prefix)?.strip_suffix("pt")?.parse().ok())
        .with_context(|| format!("the template declares no {name} in points"))
}

fn text(value: &Typed, key: &str) -> Option<String> {
    match value {
        Typed::Str(s) => Some(s.to_string()),
        Typed::Dict(d) => d.get(key).ok().and_then(|v| text(v, "")),
        _ => None,
    }
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
            (Some("mag-flow"), Some(piece))
                if text(&meta.value, "kind").as_deref() == Some("figure") =>
            {
                piece.figures.push(page)
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
        total_pages: document.pages().len(),
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

fn format_int(edition: &Edition, key: &str, default: i64) -> i64 {
    edition
        .raw
        .get("format")
        .and_then(|f| f.get(key))
        .and_then(serde_yaml::Value::as_i64)
        .unwrap_or(default)
}

fn page_cap(mode: &str) -> usize {
    if mode == "verbatim" {
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
        out.push(json!({
            "id": id,
            "article_id": article,
            "page": page,
            "path": figure.path.strip_prefix(root).unwrap_or(&figure.path).to_string_lossy().replace('\\', "/"),
            "pixel_dimensions": [width, height],
            "box_points": null,
            "effective_ppi": null,
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
        "maximum_article_pages": format_int(edition, "max_article_pages", 7),
        "article_pages": measured.article_pages(),
        "toc": measured.toc(),
        "article_opener_fits": measured.opener_fits(),
        "article_page_caps": by_article(&|a| json!(page_cap(&a.content_mode))),
        "article_content_modes": by_article(&|a| json!(a.content_mode)),
        "maximum_editorial_pages": format_int(edition, "max_editorial_pages", 2),
        "editorial_pages": measured.editorial_pages(),
        "figures": figures(edition, measured, tree, root)?,
        "tail_arts": edition.articles.iter().map(|a| json!({
            "article": a.id,
            "declared": a.tail_art.is_some(),
            "printed": false,
            "height_points": null,
            "drop_reason": a.tail_art.as_ref().map(|_| TAIL_DROP),
        })).collect::<Vec<_>>(),
    }))
}

pub struct Request<'a> {
    pub operation: &'a str,
    pub article: Option<&'a str>,
    pub edition_id: &'a str,
    pub publication_name: &'a str,
    pub language: &'a str,
    pub staged: &'a Path,
    pub out_dir: &'a Path,
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
    let edition = edition(request.staged, request.edition_id, request.publication_name)?;
    let layout = manifest_layout(&edition, &measured, tree, request.staged)?;
    let figures = layout["figures"].as_array().map_or(0, Vec::len);
    let mut files = vec![written(
        &request.out_dir.join("layout.json"),
        (serde_json::to_string_pretty(&json!({ "layout": layout }))? + "\n").as_bytes(),
        "render_layout",
    )?];
    if request.operation == "render_edition" {
        let pdf = crate::typeset::template::pdf(document)?;
        files.push(written(
            &request.out_dir.join("reader.pdf"),
            &pdf,
            "reader_pdf",
        )?);
    }
    Ok(json!({
        "operation": request.operation,
        "layouts": [measured.row(request.language, figures, "not_run")],
        "files": files,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::{pipeline, File, Inputs};
    use crate::typeset::template::{self, FONT_DIR, ROOT_TYP};
    use crate::typeset::world::Sources;
    use std::path::PathBuf;

    const TARGET: [&str; 3] = ["article_pages", "editorial_pages", "article_opener_fits"];
    const ENGINE_METADATA: [&str; 1] = ["design_direction"];
    const OWNERS: [(&str, &str); 12] = [
        ("article_pages", "WP-3.1"),
        ("editorial_pages", "WP-3.1"),
        ("article_opener_fits", "WP-3.2"),
        ("toc", "WP-3.2"),
        ("figures", "WP-3.4"),
        ("tail_arts", "WP-3.4"),
        ("cover_art_size_points", "WP-2.3"),
        ("article_terminal_balance", "WP-2.3"),
        ("maximum_article_pages", "WP-2.3"),
        ("maximum_editorial_pages", "WP-2.3"),
        ("article_page_caps", "WP-2.3"),
        ("article_content_modes", "WP-2.3"),
    ];

    struct Row {
        field: String,
        key: String,
        oracle: Value,
        typst: Value,
    }

    fn cells(field: &str, key: String, oracle: &Value, typst: &Value, out: &mut Vec<Row>) {
        let keys: Vec<String> = match (oracle, typst) {
            (Value::Object(o), Value::Object(t)) => {
                let mut keys: Vec<String> = o.keys().chain(t.keys()).cloned().collect();
                keys.sort();
                keys.dedup();
                keys
            }
            (Value::Array(o), Value::Array(t)) => {
                (0..o.len().max(t.len())).map(|i| i.to_string()).collect()
            }
            _ => Vec::new(),
        };
        if keys.is_empty() {
            let (oracle, typst) = (oracle.clone(), typst.clone());
            return out.push(Row {
                field: field.to_string(),
                key,
                oracle,
                typst,
            });
        }
        for k in keys {
            let pick = |v: &Value| {
                v.get(&k)
                    .or_else(|| v.get(k.parse::<usize>().unwrap_or(usize::MAX)))
                    .cloned()
            };
            let (o, t) = (
                pick(oracle).unwrap_or(Value::Null),
                pick(typst).unwrap_or(Value::Null),
            );
            let nested = if key.is_empty() {
                k
            } else {
                format!("{key}.{k}")
            };
            cells(field, nested, &o, &t, out);
        }
    }

    fn table(oracle: &Value, typst: &Value) -> Vec<Row> {
        let mut fields: Vec<&String> = oracle
            .as_object()
            .into_iter()
            .chain(typst.as_object())
            .flat_map(|m| m.keys())
            .collect();
        fields.sort();
        fields.dedup();
        fields.retain(|f| !ENGINE_METADATA.contains(&f.as_str()));
        let mut rows = Vec::new();
        for field in fields {
            let (o, t) = (&oracle[field.as_str()], &typst[field.as_str()]);
            cells(field, String::new(), o, t, &mut rows);
        }
        rows
    }

    fn owner(field: &str) -> Option<&'static str> {
        OWNERS.iter().find(|(f, _)| *f == field).map(|(_, o)| *o)
    }

    fn verdict(oracle: &Value, rows: &[Row]) -> std::result::Result<(), String> {
        if oracle["article_opener_fits"]
            .as_object()
            .is_none_or(Map::is_empty)
        {
            return Err("the oracle's article_opener_fits is empty: the comparison would pass vacuously (WP-0.0c)".into());
        }
        let unequal: Vec<&Row> = rows.iter().filter(|r| r.oracle != r.typst).collect();
        let unowned: Vec<String> = unequal
            .iter()
            .filter(|r| owner(&r.field).is_none())
            .map(|r| r.field.clone())
            .collect();
        if !unowned.is_empty() {
            return Err(format!("non-equal fields with no owner: {unowned:?}"));
        }
        let missed: Vec<String> = unequal
            .iter()
            .filter(|r| TARGET.contains(&r.field.as_str()))
            .map(|r| {
                format!(
                    "{}.{} oracle {} typst {}",
                    r.field, r.key, r.oracle, r.typst
                )
            })
            .collect();
        if missed.is_empty() {
            Ok(())
        } else {
            Err(format!(
                "{} target cell(s) differ:\n  {}",
                missed.len(),
                missed.join("\n  ")
            ))
        }
    }

    fn print_table(oracle: &Value, typst: &Value, rows: &[Row]) {
        for field in ENGINE_METADATA {
            println!(
                "excluded as engine metadata: {field} (oracle {}, typst {})",
                oracle[field], typst[field]
            );
        }
        println!("| field | key | oracle | typst | verdict |\n|---|---|---|---|---|");
        for r in rows {
            let verdict = if r.oracle == r.typst {
                "equal".to_string()
            } else {
                format!("DIFFERS, owner {}", owner(&r.field).unwrap_or("UNOWNED"))
            };
            let short = |v: &Value| {
                v.to_string()
                    .chars()
                    .take(60)
                    .collect::<String>()
                    .replace('|', "/")
            };
            println!(
                "| {} | {} | {} | {} | {verdict} |",
                r.field,
                r.key,
                short(&r.oracle),
                short(&r.typst)
            );
        }
        let unequal = rows.iter().filter(|r| r.oracle != r.typst).count();
        println!(
            "cells: {}, equal: {}, differing: {unequal}",
            rows.len(),
            rows.len() - unequal
        );
    }

    #[test]
    fn the_live_field_by_field_table() {
        let (Ok(oracle), Ok(typst)) = (
            std::env::var("MAG_LAYOUT_ORACLE"),
            std::env::var("MAG_LAYOUT_TYPST"),
        ) else {
            println!("skipped, env not set: MAG_LAYOUT_ORACLE (oracle edition-manifest.json) and MAG_LAYOUT_TYPST (typst layout.json)");
            return;
        };
        let read = |p: &str| -> Value {
            serde_json::from_str(&std::fs::read_to_string(p).expect("the layout file reads"))
                .expect("the layout file parses")
        };
        let (oracle, typst) = (
            read(&oracle)["layout"].clone(),
            read(&typst)["layout"].clone(),
        );
        let rows = table(&oracle, &typst);
        print_table(&oracle, &typst, &rows);
        if let Err(message) = verdict(&oracle, &rows) {
            panic!("{message}");
        }
    }

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
        let standfirst = vec!["standfirst"; words].join(" ");
        Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: format!(
                    "#piece(id: \"article-a\", kind: \"article\", short-title: \"A\", \
                     opener: \"illustrated_paper_spots_v1\")[\n\
                     #content-label[#label-primary[Feature 01]]\n\
                     #piece-title[A Fixture Title]\n\
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
            let middle = (fitting + spilling) / 2;
            if fits(middle) {
                fitting = middle;
            } else {
                spilling = middle;
            }
        }
        println!("the opener fits at {fitting} standfirst words and spills at {spilling}");
        assert_eq!(spilling, fitting + 1);
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
        assert_eq!(measured.total_pages, 13);
        assert_eq!(
            layout["toc"],
            json!({"editorial": 4, "plain-opener-article": 6, "second-fixture-article": 8, "section-0": 10})
        );
        assert_eq!(
            layout["article_pages"],
            json!({"plain-opener-article": 2, "second-fixture-article": 1})
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
        assert_eq!(layout["figures"][0]["pixel_dimensions"], json!([48, 40]));
        assert_eq!(layout["tail_arts"][1]["declared"], true);
        let row = measured.row("en", 1, "not_run");
        assert_eq!(row["totalPages"], 13);
        assert_eq!(row["editorialPages"], 1);
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

    fn sample() -> Value {
        json!({
            "article_pages": {"a": 3},
            "editorial_pages": null,
            "article_opener_fits": {"a": true},
            "design_direction": "X",
            "figures": [{"page": 2, "box_points": [1.0, 2.0, 3.0, 4.0]}],
        })
    }

    #[test]
    fn the_verdict_discriminates_each_rule() {
        let oracle = sample();
        let rows = table(&oracle, &oracle);
        assert_eq!(rows.len(), 8);
        assert!(rows.iter().all(|r| r.field != "design_direction"));
        assert_eq!(verdict(&oracle, &rows), Ok(()));
        let mut owned = sample();
        owned["figures"][0]["box_points"] = Value::Null;
        owned["design_direction"] = json!("Y");
        assert_eq!(verdict(&oracle, &table(&oracle, &owned)), Ok(()));
        for (field, value) in [
            ("article_pages", json!({"a": 4})),
            ("article_opener_fits", json!({"a": false})),
            ("editorial_pages", json!(1)),
        ] {
            let mut typst = sample();
            typst[field] = value;
            let error = verdict(&oracle, &table(&oracle, &typst)).expect_err(field);
            assert!(error.contains(field), "{error}");
        }
        let mut unowned = sample();
        unowned["surprise"] = json!(1);
        assert!(verdict(&oracle, &table(&oracle, &unowned))
            .expect_err("unowned")
            .contains("surprise"));
        let mut vacuous = sample();
        vacuous["article_opener_fits"] = json!({});
        assert!(verdict(&vacuous, &table(&vacuous, &vacuous))
            .expect_err("vacuous")
            .contains("WP-0.0c"));
    }
}
