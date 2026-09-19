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

pub fn compile(world: &Sources) -> Result<Vec<u8>> {
    let compiled = typst::compile::<PagedDocument>(world);
    let document = match compiled.output {
        Ok(document) => document,
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
    };
    let options = PdfOptions {
        ident: Smart::Custom(IDENT.to_string()),
        creator: Smart::Custom(Some(IDENT.to_string())),
        timestamp: None,
        page_ranges: None,
        standards: PdfStandards::default(),
        tagged: false,
        pretty: false,
    };
    typst_pdf::pdf(&document, &options).map_err(|errors| {
        anyhow::anyhow!(
            "PDF export failed:\n  {}",
            joined(errors.iter().map(|e| e.message.to_string()).collect())
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::typeset::content::{pipeline, Inputs};
    use lopdf::{Document, Object};
    use std::collections::BTreeSet;
    use std::path::PathBuf;

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
