use crate::typeset::content::Tree;
use crate::typeset::world::Sources;
use anyhow::{bail, Result};
use std::path::Path;
use typst::foundations::Smart;
use typst_layout::PagedDocument;
use typst_pdf::{PdfOptions, PdfStandards};

pub const TEMPLATE_TYP: &str = include_str!("../../assets/typeset/template.typ");
pub const ROOT_TYP: &str = include_str!("../../assets/typeset/root.typ");
pub const FONT_DIR: &str = "src/magazine/assets/fonts";
const IDENT: &str = "mag-typeset-reader";

pub fn world(tree: &Tree, font_dir: &Path) -> Result<Sources> {
    Sources::new(tree, TEMPLATE_TYP, ROOT_TYP, font_dir)
}

fn joined(messages: Vec<String>) -> String {
    messages.join("\n  ")
}

#[cfg(test)]
pub fn compile(world: &Sources) -> Result<Vec<u8>> {
    pdf(&document(world)?)
}

pub fn document(world: &Sources) -> Result<PagedDocument> {
    match typst::compile::<PagedDocument>(world).output {
        Ok(document) => Ok(document),
        Err(errors) => bail!(
            "the Typst reader template did not compile:\n  {}",
            joined(
                errors
                    .iter()
                    .map(|e| format!(
                        "{}{}",
                        e.message,
                        if e.hints.is_empty() {
                            String::new()
                        } else {
                            format!(
                                " (hint: {})",
                                joined(e.hints.iter().map(|h| h.v.to_string()).collect())
                            )
                        }
                    ))
                    .collect()
            )
        ),
    }
}

pub fn pdf(document: &PagedDocument) -> Result<Vec<u8>> {
    let options = PdfOptions {
        ident: Smart::Custom(IDENT.to_string()),
        creator: Smart::Custom(Some(IDENT.to_string())),
        timestamp: None,
        page_ranges: None,
        standards: PdfStandards::default(),
        tagged: false,
        pretty: false,
    };
    typst_pdf::pdf(document, &options).map_err(|errors| {
        anyhow::anyhow!(
            "PDF export failed:\n  {}",
            joined(errors.iter().map(|e| e.message.to_string()).collect())
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::{pipeline, File, Inputs};
    use lopdf::{Document, Object};
    use std::collections::BTreeSet;
    use std::path::PathBuf;

    const OLD_QUOTE_RULE: &str = "grid(\n      columns: (QUOTE-RULE, QUOTE-PAD, 1fr),\n      \
        rect(width: QUOTE-RULE, height: 100%, fill: VIOLET, stroke: none),\n      [],\n      \
        body,\n    )";

    const A5: [f64; 4] = [0.0, 0.0, 419.527_559_055_118_1, 595.275_590_551_181_1];
    const BOX_TOLERANCE_PT: f64 = 0.05;
    const MEASURE_FLOOR_PT: f64 = 325.010_000;
    const MEASURE_CEILING_PT: f64 = 325.040_000;

    fn roots() -> (&'static Path, &'static Path) {
        let crate_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo = crate_dir
            .parent()
            .expect("the crate sits inside the repository");
        (
            Box::leak(
                crate_dir
                    .join("tests/typeset_fixtures/corpus")
                    .into_boxed_path(),
            ),
            Box::leak(repo.join(FONT_DIR).into_boxed_path()),
        )
    }

    fn fixture_tree(edition_id: &'static str) -> Tree {
        let (root, font_dir) = roots();
        pipeline(&Inputs {
            root,
            edition_id,
            publication_name: "Fixture Press",
            fonts: font_dir,
            allow_missing_art: false,
            allow_unanchored_figures: false,
        })
        .expect("the fixture edition loads")
    }

    fn fixture_pdf(edition_id: &'static str) -> Vec<u8> {
        let (_, font_dir) = roots();
        let tree = fixture_tree(edition_id);
        compile(&world(&tree, font_dir).expect("the world builds")).expect("the fixture compiles")
    }

    fn media_boxes(pdf: &[u8]) -> Vec<[f64; 4]> {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        doc.get_pages()
            .values()
            .map(|id| {
                let array = doc
                    .get_dictionary(*id)
                    .and_then(|page| page.get(b"MediaBox"))
                    .and_then(Object::as_array)
                    .expect("every page carries a MediaBox")
                    .clone();
                let mut out = [0.0; 4];
                for (slot, value) in out.iter_mut().zip(&array) {
                    *slot = value.as_float().map(f64::from).unwrap_or_else(|_| {
                        value.as_i64().expect("a box coordinate is a number") as f64
                    });
                }
                out
            })
            .collect()
    }

    fn pages_off_the_box(pdf: &[u8], expected: [f64; 4], tolerance: f64) -> usize {
        media_boxes(pdf)
            .into_iter()
            .filter(|found| {
                found
                    .iter()
                    .zip(&expected)
                    .any(|(a, b)| (a - b).abs() > tolerance)
            })
            .count()
    }

    fn synthetic(main: String) -> Tree {
        Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: main,
            }],
        }
    }

    fn pages_of(tree: &Tree, template: &str) -> Result<usize> {
        let (_, font_dir) = roots();
        let world = Sources::new(tree, template, ROOT_TYP, font_dir)?;
        Ok(media_boxes(&compile(&world)?).len())
    }

    fn prose(lines: usize) -> String {
        (0..lines)
            .map(|n| format!("#doc-paragraph(standfirst: false, roster: false)[Line {n}.]\n"))
            .collect()
    }

    fn heading_run(paragraphs: usize) -> Tree {
        synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             {}#doc-heading(level: 2)[A heading]\n]\n",
            prose(paragraphs)
        ))
    }

    fn zeroed_clearance() -> String {
        TEMPLATE_TYP.replace(
            "#let HEADING-CLEARANCE = 25pt",
            "#let HEADING-CLEARANCE = 0pt",
        )
    }

    fn declared(name: &str) -> f64 {
        let needle = format!("#let {name} = ");
        let line = TEMPLATE_TYP
            .lines()
            .find(|line| line.starts_with(&needle))
            .unwrap_or_else(|| panic!("template.typ declares no {name}"));
        line[needle.len()..]
            .trim_end_matches("pt")
            .parse()
            .unwrap_or_else(|error| panic!("{name} is not a plain pt constant: {error}"))
    }

    fn called(tree: &Tree) -> BTreeSet<String> {
        let mut out = BTreeSet::new();
        for file in &tree.files {
            let mut rest = file.source.as_str();
            while let Some(at) = rest.find('#') {
                rest = &rest[at + 1..];
                let name: String = rest
                    .chars()
                    .take_while(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == '-')
                    .collect();
                if name.len() > 1 {
                    out.insert(name);
                }
            }
        }
        for own in ["include", "import", "strong", "emph"] {
            out.remove(own);
        }
        out
    }

    fn undefined(names: &BTreeSet<String>) -> Vec<String> {
        names
            .iter()
            .filter(|name| !TEMPLATE_TYP.contains(&format!("#let {name}(")))
            .cloned()
            .collect()
    }

    #[test]
    fn the_template_defines_every_function_the_fixture_editions_call() {
        let mut names = BTreeSet::new();
        for edition_id in ["900", "901"] {
            names.extend(called(&fixture_tree(edition_id)));
        }
        assert!(
            names.len() >= 20,
            "the fixtures only call {} functions, too few to cover the seam",
            names.len()
        );
        assert_eq!(undefined(&names), Vec::<String>::new());
        let mut invented = names.clone();
        invented.insert("no-such-template-function".to_string());
        assert_eq!(
            undefined(&invented),
            vec!["no-such-template-function".to_string()],
            "the missing-function check cannot discriminate"
        );
    }

    #[test]
    fn the_fixture_editions_compile_to_a5_pages() {
        for edition_id in ["900", "901"] {
            let pdf = fixture_pdf(edition_id);
            let boxes = media_boxes(&pdf);
            assert!(
                !boxes.is_empty(),
                "edition {edition_id} compiled to no pages"
            );
            assert_eq!(
                pages_off_the_box(&pdf, A5, BOX_TOLERANCE_PT),
                0,
                "edition {edition_id} has pages off the A5 box; first is {:?}",
                boxes[0]
            );
        }
    }

    #[test]
    fn the_a5_page_box_check_discriminates() {
        let pdf = fixture_pdf("900");
        let pages = media_boxes(&pdf).len();
        let one_point_wider = [A5[0], A5[1], A5[2] + 1.0, A5[3]];
        assert_eq!(
            pages_off_the_box(&pdf, one_point_wider, BOX_TOLERANCE_PT),
            pages,
            "a 1pt-wider expectation must fail on every page"
        );
        let a4 = [0.0, 0.0, 595.275_590_551_181_1, 841.889_763_779_527_5];
        assert_eq!(
            pages_off_the_box(&pdf, a4, BOX_TOLERANCE_PT),
            pages,
            "an A4 expectation must fail on every page"
        );
    }

    #[test]
    fn the_body_measure_straddles_wp17s_admissible_window() {
        let measure = declared("MEASURE");
        let delta = declared("MEASURE-DELTA");
        assert_eq!(measure, 325.0);
        assert_eq!(delta, 0.025);
        let widened = measure + delta;
        assert!(
            (MEASURE_FLOOR_PT..MEASURE_CEILING_PT).contains(&widened),
            "{widened} is outside WP-1.7's admissible window"
        );
        assert!(measure < MEASURE_FLOOR_PT, "the unwidened column must fail");
        assert!(
            measure + 0.05 >= MEASURE_CEILING_PT,
            "a 0.05pt widening must fail"
        );
    }

    #[test]
    fn the_heading_clearance_reserves_twenty_five_points_below_a_heading() {
        let moved: Vec<usize> = (24..40)
            .filter(|paragraphs| {
                let tree = heading_run(*paragraphs);
                pages_of(&tree, TEMPLATE_TYP).expect("the reserved run compiles")
                    > pages_of(&tree, &zeroed_clearance()).expect("the zeroed run compiles")
            })
            .collect();
        assert!(
            !moved.is_empty(),
            "no paragraph count put a heading inside the 25pt reservation"
        );
        assert_eq!(
            declared("HEADING-CLEARANCE"),
            25.0,
            "the reservation drifted from weasyprint-a5.css:522"
        );
    }

    #[test]
    fn a_short_quote_does_not_swallow_the_rest_of_its_page() {
        let tree = synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             #doc-quote[#doc-paragraph(standfirst: false, roster: false)[Quoted.]]\n{}]\n",
            prose(10)
        ));
        assert_eq!(
            pages_of(&tree, TEMPLATE_TYP).expect("the ruled quote compiles"),
            5,
            "a two-line quote and ten short lines must fit the four blank outer pages plus one"
        );
        let swallowing = TEMPLATE_TYP.replace("ruled(QUOTE-PAD, 0pt, none, body)", OLD_QUOTE_RULE);
        assert_ne!(swallowing, TEMPLATE_TYP, "the quote call site moved");
        assert!(
            pages_of(&tree, &swallowing).expect("the swallowing quote compiles") > 5,
            "the 100% rule must fail this test, or it does not discriminate"
        );
    }

    #[test]
    fn the_page_cap_refuses_an_article_past_seven_reader_pages() {
        let (_, font_dir) = roots();
        let tree = fixture_tree("901");
        let capped = TEMPLATE_TYP.replace("#let ARTICLE-PAGE-CAP = 7", "#let ARTICLE-PAGE-CAP = 1");
        assert_ne!(capped, TEMPLATE_TYP, "the cap constant moved");
        let world = Sources::new(&tree, &capped, ROOT_TYP, font_dir).expect("the world builds");
        let error = compile(&world).expect_err("a one-page cap must refuse the fixture");
        assert!(
            error.to_string().contains("the hard cap is 1"),
            "the refusal names something else: {error}"
        );
        assert_eq!(declared("ARTICLE-PAGE-CAP"), 7.0);
        assert_eq!(declared("VERBATIM-PAGE-CAP"), 10.0);
    }

    #[test]
    fn a_verbatim_piece_is_not_refused_by_the_article_cap() {
        let (_, font_dir) = roots();
        let tree = synthetic(format!(
            "#piece(id: \"p\", kind: \"verbatim\", short-title: \"P\", opener: \"plain\")[\n{}]\n",
            prose(400)
        ));
        let capped = TEMPLATE_TYP.replace("#let ARTICLE-PAGE-CAP = 7", "#let ARTICLE-PAGE-CAP = 1");
        let world = Sources::new(&tree, &capped, ROOT_TYP, font_dir).expect("the world builds");
        assert!(
            compile(&world).is_ok(),
            "a verbatim overrun is a warning in render.py:2085-2091, never a refusal"
        );
        let article = synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n{}]\n",
            prose(400)
        ));
        let world = Sources::new(&article, &capped, ROOT_TYP, font_dir).expect("the world builds");
        assert!(
            compile(&world).is_err(),
            "the same run under kind article must be refused, or the branch is vacuous"
        );
    }

    #[test]
    fn the_opener_title_is_set_with_its_tracking() {
        let (_, font_dir) = roots();
        let tree = fixture_tree("901");
        let untracked = TEMPLATE_TYP.replace(
            "#let OPENER-TITLE-TRACKING = -0.045",
            "#let OPENER-TITLE-TRACKING = 0",
        );
        assert_ne!(untracked, TEMPLATE_TYP, "the tracking constant moved");
        let render = |template: &str| {
            compile(&Sources::new(&tree, template, ROOT_TYP, font_dir).expect("the world builds"))
                .expect("the opener run compiles")
        };
        assert_ne!(
            render(TEMPLATE_TYP),
            render(&untracked),
            "OPENER-TITLE-TRACKING reaches no glyph on the illustrated opener"
        );
    }

    #[test]
    fn the_illustrated_opener_owns_its_own_page() {
        let (_, font_dir) = roots();
        let tree = fixture_tree("901");
        let plain = TEMPLATE_TYP.replace(
            "#let ILLUSTRATED = \"illustrated_paper_spots_v1\"",
            "#let ILLUSTRATED = \"never-matched-opener\"",
        );
        assert_ne!(plain, TEMPLATE_TYP, "the opener name moved");
        let illustrated = pages_of(&tree, TEMPLATE_TYP).expect("the illustrated run compiles");
        let flowed = Sources::new(&tree, &plain, ROOT_TYP, font_dir)
            .and_then(|world| compile(&world))
            .map(|pdf| media_boxes(&pdf).len())
            .expect("the flowed run compiles");
        assert!(
            illustrated > flowed,
            "break-after: page on the opener header must cost a page ({illustrated} vs {flowed})"
        );
    }

    fn phase(step: usize) -> (usize, usize) {
        (4 + step / 4, (step % 4) * 5)
    }

    fn figure_run(step: usize, layout: &str, figure: Option<&str>) -> Tree {
        let (paragraphs, lift) = phase(step);
        let figure = figure.map_or(String::new(), |pixels| {
            format!(
                "#figure-block(id: \"f\", source-id: \"s\", anchor: \"Anchor\", layout: \"{layout}\", \
                 word: \"Figure\", alt: \"a\"{pixels})[#figure-caption[Cap.]#figure-credit[Credit.]]\n"
            )
        });
        synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             {}#v({lift}pt)\n#doc-heading(level: 2)[Anchor]\n{figure}{}]\n",
            prose(paragraphs),
            prose(27)
        ))
    }

    fn sweep(range: std::ops::Range<usize>, make: impl Fn(usize) -> (Tree, Tree)) -> Vec<usize> {
        let mut moved = Vec::new();
        for n in range {
            let (more, less) = make(n);
            let (a, b) = (
                pages_of(&more, TEMPLATE_TYP).expect("the first run compiles"),
                pages_of(&less, TEMPLATE_TYP).expect("the second run compiles"),
            );
            assert!(
                a >= b,
                "at step {n} the run expected to be taller took fewer pages"
            );
            if a > b {
                moved.push(n);
            }
        }
        moved
    }

    #[test]
    fn a_figure_reserves_the_image_height_its_pixel_ratio_fits() {
        let wide = Some(", pixels: (2400, 1350)");
        let tall = Some(", pixels: (2000, 1418)");
        let band = "evidence_band";
        let costs = sweep(0..64, |n| {
            (figure_run(n, band, wide), figure_run(n, band, None))
        });
        assert!(
            !costs.is_empty(),
            "no paragraph count made the figure cost a page"
        );
        let ratio = sweep(0..64, |n| {
            (figure_run(n, band, tall), figure_run(n, band, wide))
        });
        assert!(
            !ratio.is_empty(),
            "a height-limited and a width-limited figure never paginated differently"
        );
        let refused = pages_of(&figure_run(3, band, Some("")), TEMPLATE_TYP)
            .expect_err("a figure with no pixel size must refuse");
        assert!(
            refused.to_string().contains("carries no pixel size"),
            "{refused}"
        );
    }

    #[test]
    fn a_band_anchor_heading_follows_its_paragraph_on_the_space_after_alone() {
        let square = Some(", pixels: (1000, 1000)");
        let moved = sweep(0..64, |n| {
            (
                figure_run(n, "column_plate", square),
                figure_run(n, "evidence_band", square),
            )
        });
        assert!(
            !moved.is_empty(),
            "dropping the anchor heading's space-before never changed the pagination"
        );
    }

    fn blank_pages(pdf: &[u8]) -> Vec<usize> {
        let doc = Document::load_mem(pdf).expect("the emitted bytes are a PDF");
        doc.get_pages()
            .into_iter()
            .filter(|(_, id)| doc.get_page_content(*id).len() < 16)
            .map(|(number, _)| number as usize)
            .collect()
    }

    fn plated(articles: usize, plates: usize) -> Tree {
        let pieces: String = (1..=articles)
            .map(|n| {
                format!(
                    "#piece(id: \"p{n}\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
                     #doc-paragraph(standfirst: false, roster: false)[Piece {n}.]\n]\n"
                )
            })
            .collect();
        let plates: String = (1..=plates)
            .map(|n| format!("#closing-plate(index: {n}, alt: \"Plate {n}\")\n"))
            .collect();
        synthetic(pieces + &plates)
    }

    #[test]
    fn closing_plates_interleave_after_the_articles_the_adapter_names() {
        let (_, font_dir) = roots();
        let pdf = compile(&Sources::new(&plated(9, 6), TEMPLATE_TYP, ROOT_TYP, font_dir).unwrap())
            .expect("the plated run compiles");
        let bankers = vec![1, 2, 5, 7, 9, 12, 15, 17, 18, 19];
        let half_up = vec![1, 2, 5, 7, 10, 12, 15, 17, 18, 19];
        assert_ne!(bankers, half_up);
        assert_eq!(blank_pages(&pdf), bankers);
        let trailing =
            compile(&Sources::new(&plated(9, 5), TEMPLATE_TYP, ROOT_TYP, font_dir).unwrap())
                .expect("five plates compile");
        assert_eq!(blank_pages(&trailing), vec![1, 2, 5, 8, 10, 13, 16, 17, 18]);
    }

    fn straddling_run(before: usize) -> Tree {
        synthetic(format!(
            "#piece(id: \"p\", kind: \"article\", short-title: \"P\", opener: \"plain\")[\n\
             {}#doc-paragraph(standfirst: false, roster: false)[{}]\n{}]\n",
            prose(before),
            "A long paragraph that runs on and on across the column. ".repeat(12),
            prose(26)
        ))
    }

    #[test]
    fn typst_prevents_orphans_and_widows_by_default_as_the_stylesheet_does() {
        let allowed = TEMPLATE_TYP.replace(
            "    hyphenate: false,\n    ..edges(BODY-SIZE, BODY-LEADING, HALF-SERIF),\n  )",
            "    hyphenate: false,\n    costs: (widow: 0%, orphan: 0%),\n    \
             ..edges(BODY-SIZE, BODY-LEADING, HALF-SERIF),\n  )",
        );
        assert_ne!(
            allowed, TEMPLATE_TYP,
            "the reader's text rule was not found"
        );
        let moved: Vec<usize> = (16..30)
            .filter(|before| {
                let tree = straddling_run(*before);
                let prevented = pages_of(&tree, TEMPLATE_TYP).expect("the default compiles");
                let permitted = pages_of(&tree, &allowed).expect("the zero-cost run compiles");
                assert!(prevented >= permitted);
                prevented > permitted
            })
            .collect();
        assert!(
            !moved.is_empty(),
            "no paragraph position made the default widow and orphan prevention move a line"
        );
    }

    #[test]
    fn the_architecture_constants_are_the_stylesheet_s_own() {
        for (name, value) in [
            ("RUNNING-BASELINE", 20.0),
            ("RUNNING-RULE", 0.55),
            ("RUNNING-RULE-TOP", 27.725),
            ("RUNNING-TICK", 1.15),
            ("RUNNING-TICK-TOP", 27.425),
            ("RUNNING-TICK-WIDTH", 14.0),
            ("CONTENTS-KICKER-TOP", -13.46915),
            ("CONTENTS-TITLE-TOP", 32.54098),
            ("CONTENTS-BAND-TOP", 74.2802),
            ("CONTENTS-BAND", 393.0),
            ("CONTENTS-ROW-MAX", 65.5),
            ("CONTENTS-RULE", 0.7),
            ("CONTENTS-ENTRY-LEFT", 47.0),
            ("OPENER-RAIL", 348.0),
            ("OPENER-ESCAPE", 11.5),
            ("OPENER-ART-HEIGHT", 207.1),
            ("OPENER-ART-LIFT", 12.0004),
            ("OPENER-FRAME-HEIGHT", 203.0),
            ("OPENER-OFFSET", 4.1),
            ("OPENER-BORDER", 2.4),
            ("OPENER-QR", 41.0),
            ("OPENER-META-MEASURE", 293.0),
        ] {
            assert_eq!(
                declared(name),
                value,
                "{name} drifted from weasyprint-a5.css"
            );
        }
        let band = declared("CONTENTS-BAND-TOP") + declared("CONTENTS-BAND");
        assert!(
            (band - 467.2802).abs() < 1e-9,
            "the contents band ends at {band}, not the stylesheet's 467.2802pt ol height"
        );
        let measure = declared("OPENER-RAIL") - declared("OPENER-QR") - declared("OPENER-GAP");
        assert!(
            (measure - declared("OPENER-META-MEASURE")).abs() < 1e-9,
            "the credit column measures {measure}, not the adapter's 293pt"
        );
        let escape = declared("MEASURE") + 2.0 * declared("OPENER-ESCAPE");
        assert!(
            (escape - declared("OPENER-RAIL")).abs() < 1e-9,
            "the 325pt measure escaped by 11.5pt a side is {escape}, not 348pt"
        );
    }

    #[test]
    fn the_page_frame_constants_are_the_stylesheet_s_own() {
        for (name, value) in [
            ("MARGIN-TOP", 42.0004),
            ("MARGIN-OUTER", 42.5197),
            ("MARGIN-BOTTOM", 54.9996),
            ("MARGIN-INNER", 44.0),
            ("DATUM", 10.0046),
            ("FOLIO-BASELINE", 19.5),
        ] {
            assert_eq!(
                declared(name),
                value,
                "{name} drifted from weasyprint-a5.css"
            );
        }
        let live = 419.527_559_055_118_1 - declared("MARGIN-INNER") - declared("MARGIN-OUTER");
        assert!(
            (live - 333.007_859_055_118_1).abs() < 1e-9,
            "the live width is {live}, not the stylesheet's 333.0079pt"
        );
        let content_height =
            595.275_590_551_181_1 - declared("MARGIN-TOP") - declared("MARGIN-BOTTOM");
        assert!(
            (content_height - 498.275_590_551_181_1).abs() < 1e-9,
            "the content height is {content_height}, not the reader's 498.2756pt"
        );
    }
}
