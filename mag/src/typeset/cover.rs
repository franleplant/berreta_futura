use crate::cover::art::{art_zones, extreme_pixels, graded_art, luminance};
use crate::cover::text::{cover_contributors, cover_date, cover_tab_identity, cover_tab_issue};
use crate::model::manifest::Edition;
use crate::typeset::content::string_literal;
use anyhow::{bail, ensure, Context, Result};
use serde_json::{json, Value};
use std::path::Path;
use typst::layout::{Frame, FrameItem, Point, Transform};
use typst_layout::PagedDocument;

pub fn confine(document: &PagedDocument) -> Result<()> {
    let pages = document.pages();
    for (number, page) in [(1, pages.first()), (pages.len(), pages.last())] {
        let page = page.context("the document has no cover page")?;
        let bounds = (page.frame.width().to_pt(), page.frame.height().to_pt());
        let mut boxes = vec![];
        ink(&page.frame, Transform::identity(), &mut boxes);
        for (index, (text, at)) in boxes.iter().enumerate() {
            ensure!(
                at[0] >= -0.5
                    && at[1] >= -0.5
                    && at[2] <= bounds.0 + 0.5
                    && at[3] <= bounds.1 + 0.5,
                "Cover page {number} text leaves the page: {text}"
            );
            for (other, to) in &boxes[index + 1..] {
                let across = at[2].min(to[2]) - at[0].max(to[0]);
                let down = at[3].min(to[3]) - at[1].max(to[1]);
                let least = (at[3] - at[1]).min(to[3] - to[1]);
                ensure!(
                    across <= 0.5 || down <= least / 3.0,
                    "Cover page {number} text overprints: {text} / {other}"
                );
            }
        }
    }
    Ok(())
}

fn ink(frame: &Frame, base: Transform, out: &mut Vec<(String, [f64; 4])>) {
    for (at, item) in frame.items() {
        let ts = base.pre_concat(Transform::translate(at.x, at.y));
        match item {
            FrameItem::Group(group) => ink(&group.frame, ts.pre_concat(group.transform), out),
            FrameItem::Text(text) => {
                let (width, size) = (text.width(), text.size);
                let corners = [(0.0, -0.7), (1.0, -0.7), (0.0, 0.0), (1.0, 0.0)]
                    .map(|(x, y)| Point::new(width * x, size * y).transform(ts));
                let low = |f: fn(&Point) -> f64| corners.iter().map(f).fold(f64::MAX, f64::min);
                let high = |f: fn(&Point) -> f64| corners.iter().map(f).fold(f64::MIN, f64::max);
                out.push((
                    text.text.to_string(),
                    [
                        low(|p| p.x.to_pt()),
                        low(|p| p.y.to_pt()),
                        high(|p| p.x.to_pt()),
                        high(|p| p.y.to_pt()),
                    ],
                ));
            }
            _ => {}
        }
    }
}

pub const DESIGN_TOML: &str = "design/covers/canto-vivo/design.toml";
const BUILT_IN: &str = include_str!("../../../design/covers/canto-vivo/design.toml");
const PAGE: (f64, f64) = (419.527_559, 595.275_591);
const TABLES: [&str; 8] = [
    "color", "tab", "wordmark", "headline", "art", "deck", "footer", "back",
];

fn layout_defaults() -> [(&'static str, Value); 2] {
    [
        (
            "footer_caption",
            json!({"margin": 25.0, "wordmark_scale": 0.8, "wordmark_dy": 6.0, "title_size": 26.0}),
        ),
        (
            "honored_plate",
            json!({"margin": 17.0, "footer": 64.0, "wordmark_scale": 0.5, "title_size": 19.0}),
        ),
    ]
}

pub fn design(root: &Path) -> Result<Value> {
    let path = root.join(DESIGN_TOML);
    let text = match path.is_file() {
        true => {
            std::fs::read_to_string(&path).with_context(|| format!("reading {}", path.display()))?
        }
        false => BUILT_IN.to_string(),
    };
    let parsed: toml::Value =
        toml::from_str(&text).with_context(|| format!("parsing {}", path.display()))?;
    let mut doc = serde_json::to_value(parsed)?;
    for table in TABLES {
        ensure!(
            doc.get(table).is_some_and(Value::is_object),
            "{DESIGN_TOML} has no [{table}] table"
        );
    }
    for (name, mut table) in layout_defaults() {
        if let Some(given) = doc.pointer(&format!("/layout/{name}")).cloned() {
            table.as_object_mut().into_iter().for_each(|defaults| {
                defaults.extend(given.as_object().cloned().unwrap_or_default());
            });
        }
        doc["layout"][name] = table;
    }
    Ok(doc)
}

fn number(design: &Value, pointer: &str) -> Result<f64> {
    design
        .pointer(pointer)
        .and_then(Value::as_f64)
        .with_context(|| format!("{DESIGN_TOML} {pointer} is not a number"))
}

fn text(design: &Value, pointer: &str) -> Result<String> {
    design
        .pointer(pointer)
        .and_then(Value::as_str)
        .map(str::to_string)
        .with_context(|| format!("{DESIGN_TOML} {pointer} is not a string"))
}

fn language_copy(
    edition: &Edition,
) -> (&'static str, [&'static str; 2], &'static str, &'static str) {
    match edition.language.split('-').next() {
        Some("es") => (
            "N\u{da}MERO",
            ["CICLO", "CERRADO"],
            "FIN",
            "Una antolog\u{ed}a independiente de textos que vale la pena conservar.",
        ),
        _ => (
            "ISSUE",
            ["LOOP", "CLOSED"],
            "END",
            "An independent anthology of writing worth keeping.",
        ),
    }
}

fn channels(design: &Value, name: &str) -> Result<[f64; 3]> {
    let colour = text(design, &format!("/color/{name}"))?;
    let channel = |at: usize| {
        u8::from_str_radix(colour.get(at..at + 2).unwrap_or(""), 16)
            .map(|value| f64::from(value) / 255.0)
            .with_context(|| format!("cover colour {colour} is not #rrggbb"))
    };
    Ok([channel(1)?, channel(3)?, channel(5)?])
}

fn scrim_alpha(text: [f64; 3], scrim: [f64; 3], pixel: [f64; 3]) -> f64 {
    let ink = luminance(text);
    (0..=50)
        .map(|step| f64::from(step) / 50.0)
        .find(|alpha| {
            let ground = luminance([0, 1, 2].map(|c| alpha * scrim[c] + (1.0 - alpha) * pixel[c]));
            (ink.max(ground) + 0.05) / (ink.min(ground) + 0.05) >= 7.0
        })
        .unwrap_or(1.0)
}

fn scrim(design: &Value, art: &Path) -> Result<Value> {
    let band = PAGE.0 - number(design, "/tab/width")?;
    let margin = number(design, "/layout/footer_caption/margin")?;
    let title_top = PAGE.1 - 46.0 - number(design, "/layout/footer_caption/title_size")?;
    let (top, _) = art_zones(art, band, PAGE.1)?;
    let area = [margin, title_top, band - margin, PAGE.1 - 18.0];
    let (darkest, brightest) = extreme_pixels(art, band, PAGE.1, area)?;
    let (paper, ink) = (channels(design, "paper")?, channels(design, "ink")?);
    let on_paper = scrim_alpha(ink, paper, darkest);
    let on_ink = scrim_alpha(paper, ink, brightest);
    let (fill, scrim, alpha) = match on_ink < on_paper {
        true => ("paper", "ink", on_ink),
        false => ("ink", "paper", on_paper),
    };
    let colour = |name| text(design, &format!("/color/{name}"));
    Ok(json!({
        "fill": colour(fill)?,
        "scrim": colour(scrim)?,
        "alpha": alpha,
        "top_gradient": top.stddev > 52.0 && top.mean < 150.0,
        "on_dark": top.mean < 118.0,
    }))
}

fn front(design: &Value, edition: &Edition, work: &Path) -> Result<Value> {
    let layout = edition
        .cover
        .layout
        .clone()
        .filter(|layout| !layout.is_empty())
        .unwrap_or_else(|| "framed".to_string());
    let (art, scrim) = match (edition.cover_art.as_deref(), layout.as_str()) {
        (Some(art), layout) => {
            ensure!(art.is_file(), "Cover art is missing: {}", art.display());
            std::fs::create_dir_all(work)?;
            let graded = work.join("cover-art.jpg");
            std::fs::write(&graded, graded_art(art)?)?;
            let scrim = match layout {
                "footer_caption" => scrim(design, art)?,
                _ => Value::Null,
            };
            (
                json!(std::path::absolute(&graded)?.to_string_lossy()),
                scrim,
            )
        }
        (None, "framed") => (Value::Null, Value::Null),
        (None, _) => {
            bail!("Cover art is missing: the {layout} cover places art and the edition names none")
        }
    };
    Ok(json!({
        "layout": layout,
        "design": design,
        "art": art,
        "scrim": scrim,
        "text": {
            "headline": edition.cover.headline.as_deref().unwrap_or(&edition.title),
            "date_line": cover_date(&edition.publication_date),
            "contributors": cover_contributors(edition),
            "tab_issue": cover_tab_issue(edition),
            "tab_identity": cover_tab_identity(edition),
        },
    }))
}

fn back(design: &Value, edition: &Edition) -> Value {
    let (issue, mass, end, statement) = language_copy(edition);
    json!({
        "design": design,
        "text": {
            "mass": mass,
            "statement": edition.cover.back_text.as_deref().unwrap_or(statement).trim(),
            "slug": format!("{end} / {}", cover_date(&edition.publication_date)),
            "identity": format!(
                "{} / {issue} {:0>3} / BUENOS AIRES",
                edition.publication_name.to_uppercase(),
                edition.issue_number
            ),
        },
    })
}

fn literal(value: &Value) -> String {
    match value {
        Value::Null => "none".to_string(),
        Value::String(text) => string_literal(text),
        Value::Array(items) if items.is_empty() => "()".to_string(),
        Value::Array(items) => format!(
            "({},)",
            items.iter().map(literal).collect::<Vec<_>>().join(", ")
        ),
        Value::Object(map) if map.is_empty() => "(:)".to_string(),
        Value::Object(map) => format!(
            "({})",
            map.iter()
                .map(|(key, value)| format!("{}: {}", string_literal(key), literal(value)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        other => other.to_string(),
    }
}

pub fn source(root: &Path, edition: &Edition, work: &Path) -> Result<String> {
    let design = design(root)?;
    Ok(format!(
        "#cover-front({})\n#cover-back({})\n",
        literal(&front(&design, edition, work)?),
        literal(&back(&design, edition))
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::spec::Cover;
    use crate::typeset::content::{Emitted, File, Tree};
    use crate::typeset::runs;
    use crate::typeset::template::{self, ROOT_TYP, TEMPLATE_TYP};
    use crate::typeset::world::Sources;
    use std::path::PathBuf;

    fn root() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
    }

    fn art() -> PathBuf {
        root().join("mag/tests/cover_fixtures/cover-wildcard-sign-punched-v3.png")
    }

    fn edition(language: &str, layout: Option<&str>, cover_art: Option<PathBuf>) -> Edition {
        Edition {
            id: "010".into(),
            publication_name: "Berreta Futura".into(),
            issue_number: "010".into(),
            title: "The Speed Limit".into(),
            publication_date: "2026-09-13".into(),
            language: language.into(),
            locale: language.into(),
            cover: Cover {
                layout: layout.map(str::to_string),
                ..Cover::default()
            },
            cover_art,
            ..Edition::default()
        }
    }

    fn scratch(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("mag-cover-{name}-{}", std::process::id()))
    }

    fn pages(edition: &Edition) -> Result<Vec<Vec<String>>> {
        let source = source(&root(), edition, &scratch("work"))?;
        let main = format!("#import \"/template.typ\": *\n{source}");
        let tree = Tree {
            files: vec![File {
                path: "main.typ".into(),
                source: main,
            }],
            figures: vec![Emitted {
                piece: "p".into(),
                id: "f".into(),
                hole: 0,
            }],
            ..Tree::default()
        };
        let document = template::document(&Sources::fixture(&tree, TEMPLATE_TYP, ROOT_TYP)?)?;
        confine(&document)?;
        Ok(runs::pages(&document)
            .into_iter()
            .map(|page| page.into_iter().map(|run| run.text).collect())
            .collect())
    }

    fn refusal(edition: &Edition) -> String {
        format!("{:#}", pages(edition).expect_err("the cover is refused"))
    }

    #[test]
    fn a_missing_design_toml_or_layout_table_takes_the_built_in_defaults() {
        let bare = scratch("no-design");
        let design = design(&bare).expect("the built-in design loads");
        assert_eq!(number(&design, "/art/top").expect("art"), 221.85);
        assert_eq!(text(&design, "/color/violet").expect("violet"), "#4b21c0");
        let partial = bare.join(DESIGN_TOML);
        std::fs::create_dir_all(partial.parent().expect("nested")).expect("temp dir");
        let text = std::fs::read_to_string(root().join(DESIGN_TOML)).expect("design.toml");
        let cut = text
            .find("[layout.footer_caption]")
            .expect("the layout tables");
        std::fs::write(
            &partial,
            format!("{}[layout.honored_plate]\nfooter = 60.0\n", &text[..cut]),
        )
        .expect("write");
        let design = super::design(&bare).expect("a partial design loads");
        let layout = &design["layout"];
        assert_eq!(layout["footer_caption"]["title_size"], 26.0);
        assert_eq!(layout["honored_plate"]["footer"], 60.0);
        assert_eq!(layout["honored_plate"]["margin"], 17.0);
        std::fs::remove_file(&partial).expect("clean up");
    }

    #[test]
    fn every_layout_sets_both_covers_as_pages_of_the_reader_with_real_text() {
        for layout in ["framed", "footer_caption", "honored_plate"] {
            let pages = pages(&edition("en", Some(layout), Some(art()))).expect(layout);
            assert_eq!(pages.len(), 4, "{layout}");
            let front = pages[0].join("|");
            assert!(
                front.contains("THE SPEED LIMIT") || front.contains("SPEED"),
                "{layout}"
            );
            assert!(
                front.contains("ISSUE 010") && front.contains("2026 09 13"),
                "{layout}"
            );
            assert!(pages[1].is_empty() && pages[2].is_empty(), "{layout}");
            let back = pages[3].join("|");
            assert!(
                back.contains("LOOP") && back.contains("END / 2026 09 13"),
                "{layout}"
            );
        }
    }

    #[test]
    fn a_roster_wider_than_the_cover_is_cut_to_one_line_inside_the_page() {
        let names = (1..40)
            .map(|n| format!("AUTHOR NUMBER {n}"))
            .collect::<Vec<_>>();
        for layout in ["footer_caption", "honored_plate"] {
            let mut long = edition("en", Some(layout), Some(art()));
            long.cover.deck = Some(names.join(" / "));
            let front = pages(&long).expect(layout)[0].join("|");
            assert!(front.contains("AUTHOR NUMBER 1 /"), "{layout}");
            assert!(!front.contains("AUTHOR NUMBER 39"), "{layout}");
        }
    }

    #[test]
    fn the_back_cover_carries_each_languages_copy() {
        let back = back_of("es-AR");
        assert_eq!(back["text"]["mass"], json!(["CICLO", "CERRADO"]));
        assert_eq!(back["text"]["slug"], "FIN / 2026 09 13");
        assert_eq!(
            back["text"]["identity"],
            "BERRETA FUTURA / N\u{da}MERO 010 / BUENOS AIRES"
        );
        let english = back_of("en");
        assert_eq!(
            english["text"]["statement"],
            "An independent anthology of writing worth keeping."
        );
    }

    fn back_of(language: &str) -> Value {
        back(
            &design(&root()).expect("design"),
            &edition(language, None, None),
        )
    }

    #[test]
    fn cover_text_is_not_limited_to_win_ansi() {
        let mut polish = edition("en", Some("honored_plate"), Some(art()));
        polish.cover.headline = Some("\u{141}\u{f3}d\u{17a} \u{2192} \u{15a}wiat".into());
        let front = pages(&polish).expect("a non-WinAnsi title sets")[0].join("|");
        assert!(front.contains('\u{141}') && front.contains('\u{15a}'));
    }

    #[test]
    fn a_framed_cover_without_art_draws_the_placeholder_and_other_layouts_refuse() {
        assert_eq!(
            pages(&edition("es", Some("framed"), None))
                .expect("no art is fine")
                .len(),
            4
        );
        for layout in ["footer_caption", "honored_plate"] {
            let message = refusal(&edition("es", Some(layout), None));
            assert!(message.contains("Cover art is missing"), "{message}");
        }
    }

    #[test]
    fn an_unknown_layout_or_missing_art_file_is_refused() {
        assert!(
            refusal(&edition("en", Some("spread"), Some(art()))).contains(
                "Unknown cover layout 'spread': expected framed, footer_caption, or honored_plate"
            )
        );
        let absent = root().join("editions/010/art/does-not-exist.png");
        let message = refusal(&edition("en", Some("framed"), Some(absent.clone())));
        assert!(message.contains(&format!("Cover art is missing: {}", absent.display())));
    }

    #[test]
    fn titles_decks_and_headlines_that_cannot_fit_are_refused() {
        let stem = "The Speed Limit And Its Apostle";
        let mut plate = edition("en", Some("honored_plate"), Some(art()));
        plate.cover.headline = Some(format!("{stem}l"));
        pages(&plate).expect("the size floor still fits");
        plate.cover.headline = Some(format!("{stem}s"));
        assert!(refusal(&plate)
            .contains("Cover title cannot fit on one line: THE SPEED LIMIT AND ITS APOSTLES"));
        let mut framed = edition("en", Some("framed"), Some(art()));
        let deck = |count: usize| {
            (0..count)
                .map(|i| format!("CONTRIBUTOR NAME NUMBER {i} WITH EXTRA WORDS"))
                .collect::<Vec<_>>()
                .join(" / ")
        };
        framed.cover.deck = Some(deck(6));
        pages(&framed).expect("five wrapped lines fit");
        framed.cover.deck = Some(deck(7));
        assert!(refusal(&framed).contains("Cover deck cannot fit"));
        framed.cover.deck = None;
        framed.cover.headline = Some(
            "Antidisestablishmentarianism Floccinaucinihilipilification Pneumonoultramicroscopic Is"
                .into(),
        );
        pages(&framed).expect("three lines at the floor fit");
        framed.cover.headline = Some(
            "Antidisestablishmentarianism Floccinaucinihilipilification Pneumonoultramicroscopic As"
                .into(),
        );
        assert!(refusal(&framed).contains("Cover headline cannot fit"));
    }
}
