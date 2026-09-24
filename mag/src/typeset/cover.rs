use crate::cover::back::{back_svg, Back, BackText, Serif};
use crate::cover::pdf::{self, Face, Line};
use crate::cover::raster;
use crate::cover::svg::{
    Art, Builder, CoverText, Deck, Design, Fonts, Footer, FooterCaption, Headline, HonoredPlate,
    Palette, Tab, Wordmark, PAGE_HEIGHT, PAGE_WIDTH,
};
use crate::cover::text::{cover_contributors, cover_date, cover_tab_identity, cover_tab_issue};
use crate::model::manifest::Edition;
use crate::model::shared::{py_str, py_strip, py_upper, py_zfill, raw_or};
use anyhow::{bail, Context, Result};
use lopdf::{Document, Object, StringFormat};
use std::path::Path;

pub const DESIGN_TOML: &str = "design/covers/canto-vivo/design.toml";

struct Table<'a>(&'a toml::Value, &'a str);

impl Table<'_> {
    fn at<'b>(root: &'b toml::Value, path: &'b str) -> Result<Table<'b>> {
        let mut node = root;
        for key in path.split('.') {
            node = node
                .get(key)
                .with_context(|| format!("{DESIGN_TOML} has no [{path}] table"))?;
        }
        Ok(Table(node, path))
    }

    fn f(&self, key: &str) -> Result<f64> {
        match self.0.get(key) {
            Some(toml::Value::Float(value)) => Ok(*value),
            Some(toml::Value::Integer(value)) => Ok(*value as f64),
            _ => bail!("{DESIGN_TOML} [{}] {key} is not a number", self.1),
        }
    }

    fn s(&self, key: &str) -> Result<String> {
        self.0
            .get(key)
            .and_then(toml::Value::as_str)
            .map(str::to_string)
            .with_context(|| format!("{DESIGN_TOML} [{}] {key} is not a string", self.1))
    }
}

pub fn design(root: &Path) -> Result<(Design, Back)> {
    let path = root.join(DESIGN_TOML);
    let text =
        std::fs::read_to_string(&path).with_context(|| format!("reading {}", path.display()))?;
    let doc: toml::Value =
        toml::from_str(&text).with_context(|| format!("parsing {}", path.display()))?;
    let t = |name| Table::at(&doc, name);
    let (color, tab, wordmark) = (t("color")?, t("tab")?, t("wordmark")?);
    let (caption, headline, art) = (t("layout.footer_caption")?, t("headline")?, t("art")?);
    let (deck, footer, plate, back) = (
        t("deck")?,
        t("footer")?,
        t("layout.honored_plate")?,
        t("back")?,
    );
    let design = Design {
        id: doc
            .get("id")
            .and_then(toml::Value::as_str)
            .context("design id")?
            .to_string(),
        colors: Palette {
            paper: color.s("paper")?,
            ink: color.s("ink")?,
            orange: color.s("orange")?,
            violet: color.s("violet")?,
        },
        tab: Tab {
            width: tab.f("width")?,
            edge_reveal: tab.f("edge_reveal")?,
            issue_top: tab.f("issue_top")?,
            identity_top: tab.f("identity_top")?,
            overdraw: tab.f("overdraw")?,
        },
        wordmark: Wordmark {
            x: wordmark.f("x")?,
            top: wordmark.f("top")?,
            right_reserve: wordmark.f("right_reserve")?,
        },
        footer_caption: FooterCaption {
            margin: caption.f("margin")?,
            wordmark_scale: caption.f("wordmark_scale")?,
            wordmark_dy: caption.f("wordmark_dy")?,
            title_size: caption.f("title_size")?,
        },
        headline: Headline {
            x: headline.f("x")?,
            top: headline.f("top")?,
            width: headline.f("width")?,
        },
        art: Art {
            x: art.f("x")?,
            top: art.f("top")?,
            width: art.f("width")?,
            height: art.f("height")?,
        },
        deck: Deck {
            top: deck.f("top")?,
            size: deck.f("size")?,
            wrap_size: deck.f("wrap_size")?,
            leading: deck.f("leading")?,
            horizontal_scale: deck.f("horizontal_scale")?,
            tracking: deck.f("tracking")?,
        },
        footer: Footer {
            x: footer.f("x")?,
            bottom: footer.f("bottom")?,
            size: footer.f("size")?,
            tracking: footer.f("tracking")?,
        },
        honored_plate: HonoredPlate {
            margin: plate.f("margin")?,
            footer: plate.f("footer")?,
            wordmark_scale: plate.f("wordmark_scale")?,
            title_size: plate.f("title_size")?,
        },
    };
    Ok((design, back_design(&back)?))
}

fn back_design(back: &Table) -> Result<Back> {
    let b = |key| back.f(key);
    Ok(Back {
        overdraw: b("overdraw")?,
        rail_width: b("rail_width")?,
        rail_top: b("rail_top")?,
        rail_size: b("rail_size")?,
        rail_tracking: b("rail_tracking")?,
        mass_x: b("mass_x")?,
        mass_top: b("mass_top")?,
        mass_size: b("mass_size")?,
        mass_leading: b("mass_leading")?,
        mass_tracking: b("mass_tracking")?,
        panel_x: b("panel_x")?,
        panel_top: b("panel_top")?,
        panel_right: b("panel_right")?,
        panel_bottom: b("panel_bottom")?,
        panel_padding: b("panel_padding")?,
        statement_max_size: b("statement_max_size")?,
        statement_min_size: b("statement_min_size")?,
        statement_leading_ratio: b("statement_leading_ratio")?,
        slug_x: b("slug_x")?,
        slug_bottom: b("slug_bottom")?,
        slug_size: b("slug_size")?,
        slug_tracking: b("slug_tracking")?,
    })
}

struct Copy {
    mass: [&'static str; 2],
    issue: &'static str,
    end: &'static str,
    statement: &'static str,
}

fn copy(edition: &Edition) -> Copy {
    if edition.language.split('-').next() == Some("es") {
        Copy {
            mass: ["CICLO", "CERRADO"],
            issue: "N\u{da}MERO",
            end: "FIN",
            statement: "Una antolog\u{ed}a independiente de textos que vale la pena conservar.",
        }
    } else {
        Copy {
            mass: ["LOOP", "CLOSED"],
            issue: "ISSUE",
            end: "END",
            statement: "An independent anthology of writing worth keeping.",
        }
    }
}

fn cover_field(edition: &Edition, key: &str, fallback: &str) -> String {
    edition
        .cover
        .get(key)
        .map_or_else(|| fallback.to_string(), py_str)
}

fn rgb(hex: &str) -> Result<(f64, f64, f64)> {
    let channel = |at: usize| {
        u8::from_str_radix(hex.get(at..at + 2).unwrap_or(""), 16)
            .map(|value| f64::from(value) / 255.0)
            .with_context(|| format!("{DESIGN_TOML} colour {hex} is not #rrggbb"))
    };
    Ok((channel(1)?, channel(3)?, channel(5)?))
}

fn line(
    value: String,
    x: f64,
    y: f64,
    size: f64,
    horizontal_scale: f64,
    tracking: Option<f64>,
) -> Line {
    Line {
        value,
        x,
        y,
        size,
        horizontal_scale,
        tracking,
    }
}

fn front(design: &Design, fonts: &mut Fonts, edition: &Edition) -> Result<(String, Face)> {
    let art = edition
        .cover_art
        .as_deref()
        .context("the typst cover step needs cover art; the edition names none")?;
    let headline = cover_field(edition, "headline", &edition.title);
    let text = CoverText {
        publication_name: edition.publication_name.clone(),
        headline: headline.clone(),
        date_line: cover_date(&edition.publication_date),
        contributors: cover_contributors(edition),
        tab_issue: cover_tab_issue(edition),
        tab_identity: cover_tab_identity(edition),
    };
    let layout = raw_or(edition.cover.get("layout"), "framed");
    let svg = Builder { design, fonts }.materialize(&layout, &text, art)?;
    let (deck, footer) = (&design.deck, &design.footer);
    let mut lines = vec![
        line(
            py_upper(&edition.publication_name),
            38.0,
            PAGE_HEIGHT - 55.0,
            22.0,
            100.0,
            Some(0.0),
        ),
        line(
            py_upper(&headline),
            44.0,
            PAGE_HEIGHT - 151.0,
            16.0,
            100.0,
            Some(0.0),
        ),
    ];
    let baseline = deck.top + deck.size;
    for (index, value) in fonts
        .regular
        .wrap(&text.contributors, deck.wrap_size, design.art.width)?
        .into_iter()
        .enumerate()
    {
        let y = PAGE_HEIGHT - (baseline + index as f64 * deck.leading);
        lines.push(line(
            value,
            design.art.x,
            y,
            deck.size,
            deck.horizontal_scale,
            Some(deck.tracking),
        ));
    }
    lines.push(line(
        text.date_line,
        footer.x,
        footer.bottom,
        footer.size,
        100.0,
        Some(footer.tracking),
    ));
    let band_x = PAGE_WIDTH - design.tab.width;
    let face = Face {
        title: "Berreta Futura front cover".into(),
        fills: pdf::front_fills(
            band_x,
            design.tab.width - design.tab.edge_reveal,
            design.tab.overdraw,
            rgb(&design.colors.orange)?,
        ),
        text: lines,
    };
    Ok((svg, face))
}

fn back(
    design: &Design,
    back: &Back,
    fonts: &mut Fonts,
    serif: &mut Serif,
    edition: &Edition,
) -> Result<(String, Face)> {
    let copy = copy(edition);
    let statement = py_strip(&cover_field(edition, "back_text", copy.statement)).to_string();
    let text = BackText {
        mass: copy.mass.map(str::to_string),
        statement: statement.clone(),
        slug: format!("{} / {}", copy.end, cover_date(&edition.publication_date)),
        identity: format!(
            "{} / {} {} / BUENOS AIRES",
            py_upper(&edition.publication_name),
            copy.issue,
            py_zfill(&edition.issue_number, 3)
        ),
    };
    let svg = back_svg(design, back, fonts, serif, &text)?;
    let mut lines = vec![
        line(
            text.mass[0].clone(),
            6.0,
            PAGE_HEIGHT - 90.0,
            20.0,
            100.0,
            None,
        ),
        line(
            text.mass[1].clone(),
            6.0,
            PAGE_HEIGHT - 170.0,
            20.0,
            100.0,
            None,
        ),
    ];
    for (index, value) in fonts
        .regular
        .wrap(&statement, 10.0, 260.0)?
        .into_iter()
        .enumerate()
    {
        lines.push(line(
            value,
            68.0,
            PAGE_HEIGHT - 300.0 - index as f64 * 12.0,
            10.0,
            100.0,
            None,
        ));
    }
    lines.push(line(text.slug, 38.0, 26.0, 7.0, 100.0, None));
    lines.push(line(text.identity, 38.0, 10.0, 5.5, 88.0, None));
    let face = Face {
        title: "Berreta Futura back cover".into(),
        fills: pdf::back_fills(back.overdraw, rgb(&design.colors.orange)?),
        text: lines,
    };
    Ok((svg, face))
}

pub fn faces(
    root: &Path,
    assets: &Path,
    edition: &Edition,
    work: &Path,
) -> Result<(Vec<u8>, Vec<u8>)> {
    let (design, back_design) = design(root)?;
    let mut fonts = Fonts::load(assets)?;
    let inter = std::fs::read(assets.join("fonts/inter/Inter-Regular.ttf"))?;
    let front = front(&design, &mut fonts, edition)?;
    let back = back(
        &design,
        &back_design,
        &mut fonts,
        &mut Serif::open(assets)?,
        edition,
    )?;
    let mut out = Vec::new();
    for (name, (svg, face)) in [("front", front), ("back", back)] {
        std::fs::write(work.join(format!("{name}.svg")), &svg)?;
        let pixmap = raster::render(&raster::raster_svg(&svg, 300))?;
        let bytes = pdf::write(&face, &pixmap, &inter)?;
        std::fs::write(work.join(format!("{name}.pdf")), &bytes)?;
        out.push(bytes);
    }
    let back = out.pop().context("two faces")?;
    Ok((out.pop().context("two faces")?, back))
}

fn cover_page(reader: &mut Document, face: &[u8]) -> Result<lopdf::Dictionary> {
    let mut cover = Document::load_mem(face).context("reading a compiled cover face")?;
    cover.renumber_objects_with(reader.max_id + 1);
    let pages = cover.get_pages();
    let (&_, &id) = pages.iter().next().context("a cover face has no page")?;
    let page = cover.get_dictionary(id)?.clone();
    reader.max_id = reader.max_id.max(cover.max_id);
    reader.objects.extend(cover.objects);
    Ok(page)
}

pub fn replace_outer_pages(interior: &[u8], front: &[u8], back: &[u8]) -> Result<Vec<u8>> {
    let mut reader = Document::load_mem(interior).context("reading the typst interior")?;
    let pages: Vec<_> = reader.get_pages().into_values().collect();
    if pages.len() < 4 {
        bail!("Reader must have at least four pages and each cover PDF exactly one page");
    }
    for (target, face) in [(pages[0], front), (pages[pages.len() - 1], back)] {
        let face = cover_page(&mut reader, face)?;
        let page = reader.get_dictionary_mut(target)?;
        let parent = page.get(b"Parent")?.clone();
        *page = face;
        page.set("Parent", parent);
    }
    let info = reader
        .trailer
        .get(b"Info")
        .and_then(Object::as_reference)
        .ok();
    let info = match info {
        Some(id) => id,
        None => {
            let id = reader.add_object(lopdf::Dictionary::new());
            reader.trailer.set("Info", id);
            id
        }
    };
    let info = reader.get_dictionary_mut(info)?;
    for key in ["Creator", "Producer"] {
        info.set(
            key,
            Object::String(b"magazine-compiler".to_vec(), StringFormat::Literal),
        );
    }
    reader.prune_objects();
    let mut bytes = Vec::new();
    reader.save_to(&mut bytes).context("writing reader.pdf")?;
    Ok(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use lopdf::{dictionary, Stream};
    use sha2::{Digest, Sha256};
    use std::path::PathBuf;

    fn root() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
    }

    fn edition(language: &str) -> Edition {
        Edition {
            id: "010".into(),
            publication_name: "Berreta Futura".into(),
            issue_number: "010".into(),
            title: "The Speed Limit".into(),
            publication_date: "2026-09-13".into(),
            language: language.into(),
            locale: language.into(),
            editorial: None,
            articles: vec![],
            sections: vec![],
            cover: serde_yaml::Mapping::new(),
            cover_art: None,
            closing_plates: vec![],
            raw: serde_yaml::Value::Null,
        }
    }

    fn back_face(language: &str, cover: serde_yaml::Mapping) -> (String, Face) {
        let assets = root().join("src/magazine/assets");
        let (design, back_design) = design(&root()).expect("design.toml loads");
        let mut fonts = Fonts::load(&assets).expect("cover faces load");
        let mut serif = Serif::open(&assets).expect("serif loads");
        back(
            &design,
            &back_design,
            &mut fonts,
            &mut serif,
            &Edition {
                cover,
                ..edition(language)
            },
        )
        .expect("back builds")
    }

    #[test]
    fn the_back_cover_text_layer_carries_each_languages_copy() {
        let values = |language| {
            back_face(language, serde_yaml::Mapping::new())
                .1
                .text
                .into_iter()
                .map(|l| l.value)
                .collect::<Vec<_>>()
        };
        assert_eq!(
            values("en"),
            [
                "LOOP",
                "CLOSED",
                "An independent anthology of writing worth keeping.",
                "END / 2026 09 13",
                "BERRETA FUTURA / ISSUE 010 / BUENOS AIRES"
            ]
        );
        let spanish = values("es-AR");
        assert_eq!(spanish[..2], ["CICLO", "CERRADO"]);
        assert_eq!(
            spanish[spanish.len() - 2..],
            [
                "FIN / 2026 09 13",
                "BERRETA FUTURA / N\u{da}MERO 010 / BUENOS AIRES"
            ]
        );
    }

    #[test]
    fn the_010_back_cover_rasterizes_to_the_pixels_the_python_compiler_printed() {
        let yaml = std::fs::read_to_string(root().join("editions/010/edition.yaml")).expect("010");
        let raw: serde_yaml::Value = serde_yaml::from_str(&yaml).expect("010 parses");
        let cover = raw["cover"].as_mapping().expect("010 has a cover").clone();
        let (svg, _) = back_face("en", cover);
        let pixmap = raster::render(&raster::raster_svg(&svg, 300)).expect("back rasterizes");
        let straight: Vec<u8> = pixmap
            .pixels()
            .iter()
            .flat_map(|pixel| {
                let c = pixel.demultiply();
                [c.red(), c.green(), c.blue(), c.alpha()]
            })
            .collect();
        let digest = hex::encode(Sha256::digest(straight));
        assert_eq!((pixmap.width(), pixmap.height()), (1748, 2480));
        assert_eq!(
            digest,
            "beb601e1ff00de843e8a43b6a4a46d0b0e45178bd52ba55c06df2740c94ce100"
        );
    }

    fn page(document: &mut Document, parent: lopdf::ObjectId, marker: &str) -> Object {
        let contents = document.add_object(Stream::new(
            lopdf::Dictionary::new(),
            marker.as_bytes().to_vec(),
        ));
        document
            .add_object(dictionary! {"Type" => "Page", "Parent" => parent, "Contents" => contents, "MediaBox" => vec![0.into(), 0.into(), 419.527559.into(), 595.275591.into()]})
            .into()
    }

    fn interior() -> Vec<u8> {
        let mut document = Document::with_version("1.7");
        let pages = document.new_object_id();
        let kids: Vec<Object> = (1..=4)
            .map(|n| page(&mut document, pages, &format!("% page {n}")))
            .collect();
        document.objects.insert(
            pages,
            Object::Dictionary(
                dictionary! {"Type" => "Pages", "Kids" => kids.clone(), "Count" => 4},
            ),
        );
        let outline = document.new_object_id();
        let entry = document.add_object(dictionary! {"Title" => Object::string_literal("Contents"), "Parent" => outline, "Dest" => vec![kids[1].clone(), "Fit".into()]});
        document.objects.insert(
            outline,
            Object::Dictionary(
                dictionary! {"Type" => "Outlines", "First" => entry, "Last" => entry, "Count" => 1},
            ),
        );
        let catalog = document.add_object(dictionary! {"Type" => "Catalog", "Pages" => pages, "Outlines" => outline, "Lang" => Object::string_literal("en")});
        let info = document.add_object(
            dictionary! {"Title" => Object::string_literal("Berreta Futura: The Speed Limit")},
        );
        document.trailer.set("Root", catalog);
        document.trailer.set("Info", info);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).expect("interior writes");
        bytes
    }

    fn face(title: &str) -> Vec<u8> {
        let inter = std::fs::read(root().join("src/magazine/assets/fonts/inter/Inter-Regular.ttf"))
            .expect("inter");
        let face = Face {
            title: title.into(),
            fills: pdf::back_fills(1.5, (1.0, 0.0, 0.0)),
            text: vec![],
        };
        pdf::write(
            &face,
            &tiny_skia::Pixmap::new(4, 4).expect("pixmap"),
            &inter,
        )
        .expect("face writes")
    }

    #[test]
    fn outer_pages_take_the_cover_faces_and_keep_the_interiors_catalog() {
        let merged =
            replace_outer_pages(&interior(), &face("front"), &face("back")).expect("merges");
        let document = Document::load_mem(&merged).expect("reader parses");
        let pages: Vec<_> = document.get_pages().into_values().collect();
        assert_eq!(pages.len(), 4);
        let content = |id| String::from_utf8_lossy(&document.get_page_content(id)).into_owned();
        assert!(content(pages[0]).contains("/Cover Do") && content(pages[3]).contains("/Cover Do"));
        assert_eq!(
            (content(pages[1]), content(pages[2])),
            ("% page 2\n".into(), "% page 3\n".into())
        );
        let catalog = document.catalog().expect("catalog");
        assert_eq!(
            catalog.get(b"Lang").and_then(Object::as_str).ok(),
            Some(&b"en"[..])
        );
        let outline = document
            .get_dictionary(
                catalog
                    .get(b"Outlines")
                    .and_then(Object::as_reference)
                    .expect("outline"),
            )
            .expect("outline dict");
        let first = document
            .get_dictionary(
                outline
                    .get(b"First")
                    .and_then(Object::as_reference)
                    .expect("entry"),
            )
            .expect("entry dict");
        let target = first.get(b"Dest").and_then(Object::as_array).expect("dest")[0]
            .as_reference()
            .expect("page ref");
        assert_eq!(target, pages[1]);
        let info = document
            .get_dictionary(
                document
                    .trailer
                    .get(b"Info")
                    .and_then(Object::as_reference)
                    .expect("info"),
            )
            .expect("info dict");
        let text = |key: &[u8]| {
            info.get(key)
                .and_then(Object::as_str)
                .map(<[u8]>::to_vec)
                .ok()
        };
        assert_eq!(
            text(b"Title"),
            Some(b"Berreta Futura: The Speed Limit".to_vec())
        );
        assert_eq!(
            (text(b"Creator"), text(b"Producer")),
            (
                Some(b"magazine-compiler".to_vec()),
                Some(b"magazine-compiler".to_vec())
            )
        );
        for id in [pages[0], pages[3]] {
            assert_eq!(
                document
                    .get_dictionary(id)
                    .expect("page")
                    .get(b"Parent")
                    .and_then(Object::as_reference)
                    .ok(),
                document
                    .catalog()
                    .expect("c")
                    .get(b"Pages")
                    .and_then(Object::as_reference)
                    .ok()
            );
        }
    }
}
