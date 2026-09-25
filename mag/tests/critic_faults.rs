#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/trace/exact.rs"]
#[allow(dead_code)]
pub mod exact;
#[path = "../src/trace/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

#[path = "../src/trace/elements.rs"]
#[allow(dead_code)]
pub mod elements;

mod trace {
    pub use super::elements::trace_elements;
    pub use super::exact::{authored, num};
    #[allow(unused_imports)]
    pub use super::streams::{Color, Element, Face as TextFace, GLYPH_QUANTUM};
}

#[path = "../src/impose.rs"]
#[allow(dead_code)]
pub mod impose;

#[path = "../src/critic/metrics.rs"]
#[allow(dead_code)]
pub mod metrics;

#[path = "../src/critic/text.rs"]
#[allow(dead_code)]
pub mod text;

#[path = "../src/critic/inspect.rs"]
#[allow(dead_code)]
pub mod inspect;

mod critic {
    #[allow(unused_imports)]
    pub use super::inspect;
    pub use super::{metrics, text};
}

#[allow(dead_code)]
mod oracle;
#[path = "../src/critic/rules.rs"]
#[allow(dead_code)]
mod rules;

use lopdf::{dictionary, Dictionary, Document, Object, ObjectId, Stream};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

type Row = (&'static str, &'static str, Option<usize>);
type Probe = (&'static str, usize, &'static str, fn() -> Value);

const LEGS: [&str; 4] = [
    "reader.pdf",
    "booklet-a4.pdf",
    "booklet-a4-interior.pdf",
    "booklet-a4-cover.pdf",
];

const BASELINE: [Row; 4] = [
    ("whitespace-void", "review", Some(17)),
    ("article-stub-last-page", "review", Some(29)),
    ("tail-art-dropped", "review", None),
    ("article-page-cap", "review", None),
];

const ORDER: [Row; 3] = [
    ("booklet-page-order", "error", None),
    ("interior-booklet-page-order", "error", None),
    ("cover-booklet-page-order", "error", None),
];

struct Pdf {
    doc: Document,
}

impl Pdf {
    fn page(&self, number: usize) -> ObjectId {
        self.doc.get_pages()[&(number as u32)]
    }

    fn content(&self, number: usize) -> String {
        self.doc
            .get_page_content(self.page(number))
            .iter()
            .map(|&byte| byte as char)
            .collect()
    }

    fn set(&mut self, number: usize, content: &str) {
        let page = self.page(number);
        let bytes = content.chars().map(|c| c as u8).collect();
        let stream = self.doc.add_object(Stream::new(Dictionary::new(), bytes));
        self.doc
            .get_dictionary_mut(page)
            .expect("a page dictionary")
            .set("Contents", stream);
    }

    fn edit(&mut self, number: usize, change: impl FnOnce(String) -> String) {
        let changed = change(self.content(number));
        self.set(number, &changed);
    }

    fn swap(&mut self, a: usize, b: usize) {
        let (first, second) = (self.page(a), self.page(b));
        for key in ["Contents", "Resources"] {
            let take = |doc: &Document, id| {
                doc.get_dictionary(id)
                    .and_then(|page| page.get(key.as_bytes()))
                    .expect("the page carries the key")
                    .clone()
            };
            let (x, y) = (take(&self.doc, first), take(&self.doc, second));
            self.doc.get_dictionary_mut(first).unwrap().set(key, y);
            self.doc.get_dictionary_mut(second).unwrap().set(key, x);
        }
    }

    fn helvetica(&mut self, number: usize) {
        let page = self.page(number);
        let font = self.doc.add_object(dictionary! {
            "Type" => "Font",
            "Subtype" => "Type1",
            "BaseFont" => "Helvetica",
            "Encoding" => "WinAnsiEncoding",
            "FirstChar" => 32,
            "LastChar" => 255,
            "Widths" => (32..=255).map(|code| Object::Integer(if code == 32 { 278 } else { 556 })).collect::<Vec<_>>(),
        });
        let resources = self
            .doc
            .get_or_create_resources(page)
            .and_then(Object::as_dict_mut)
            .expect("page resources");
        let shared = resources
            .get(b"Font")
            .ok()
            .and_then(|fonts| fonts.as_reference().ok());
        match shared {
            Some(id) => self
                .doc
                .get_dictionary_mut(id)
                .expect("a font dictionary")
                .set("FaultHelv", font),
            None => match resources.get_mut(b"Font").and_then(Object::as_dict_mut) {
                Ok(fonts) => fonts.set("FaultHelv", font),
                Err(_) => resources.set("Font", dictionary! {"FaultHelv" => font}),
            },
        }
    }

    fn hide(&mut self, number: usize, text: &str, y: f64) {
        self.helvetica(number);
        self.edit(number, |content| {
            format!(
                "q\n{content}\nQ\nBT\n3 Tr\n/FaultHelv 10 Tf\n1 0 0 1 60 {y} Tm\n({text}) Tj\nET\n"
            )
        });
    }

    fn ink(&mut self, number: usize) {
        self.edit(number, |content| {
            format!("q\n{content}\nQ\n0 0 0 rg\n150 300 10 10 re\nf\n")
        });
    }

    fn downsample(&mut self, number: usize, factor: usize) -> [usize; 2] {
        let content = self.content(number);
        let draws: Vec<&str> = content
            .lines()
            .filter(|line| line.ends_with(" Do"))
            .collect();
        assert_eq!(draws.len(), 1, "page {number} draws exactly one image");
        let name = draws[0].trim_start_matches('/').trim_end_matches(" Do");
        let page = self.doc.get_dictionary(self.page(number)).unwrap();
        let resources = deref(&self.doc, page.get(b"Resources").expect("page resources"));
        let id = deref(&self.doc, resources.get(b"XObject").expect("xobjects"))
            .get(name.as_bytes())
            .and_then(Object::as_reference)
            .expect("the drawn image is an indirect object");
        let mask = self
            .doc
            .get_object(id)
            .and_then(Object::as_stream)
            .and_then(|stream| stream.dict.get(b"SMask"))
            .and_then(Object::as_reference)
            .ok();
        if let Some(mask) = mask {
            self.shrink(mask, factor);
        }
        self.shrink(id, factor)
    }

    fn shrink(&mut self, id: ObjectId, factor: usize) -> [usize; 2] {
        let stream = self.doc.get_object(id).and_then(Object::as_stream).unwrap();
        let dimension =
            |key: &[u8]| stream.dict.get(key).and_then(Object::as_i64).unwrap() as usize;
        let (width, height) = (dimension(b"Width"), dimension(b"Height"));
        let pixels = stream.decompressed_content().expect("the image decodes");
        let channels = pixels.len() / (width * height);
        assert_eq!(pixels.len(), width * height * channels, "an 8-bit image");
        let (small_width, small_height) = (width / factor, height / factor);
        let mut small = Vec::with_capacity(small_width * small_height * channels);
        for row in 0..small_height {
            for column in 0..small_width {
                for channel in 0..channels {
                    let total: usize = (0..factor * factor)
                        .map(|cell| {
                            let (y, x) = (
                                row * factor + cell / factor,
                                column * factor + cell % factor,
                            );
                            pixels[(y * width + x) * channels + channel] as usize
                        })
                        .sum();
                    small.push((total / (factor * factor)) as u8);
                }
            }
        }
        let mut dict = stream.dict.clone();
        dict.set("Width", small_width as i64);
        dict.set("Height", small_height as i64);
        dict.remove(b"DecodeParms");
        dict.remove(b"Filter");
        let mut replacement = Stream::new(dict, small);
        replacement.compress().expect("the image compresses");
        self.doc.objects.insert(id, Object::Stream(replacement));
        [small_width, small_height]
    }
}

fn deref<'a>(doc: &'a Document, value: &'a Object) -> &'a Dictionary {
    match value {
        Object::Reference(id) => doc.get_dictionary(*id).expect("a dictionary"),
        other => other.as_dict().expect("a dictionary"),
    }
}

fn drop_image(content: String) -> String {
    let draws = content.lines().filter(|line| line.ends_with(" Do")).count();
    assert_eq!(draws, 1, "the tail page draws exactly one image");
    content
        .lines()
        .filter(|line| !line.ends_with(" Do"))
        .collect::<Vec<_>>()
        .join("\n")
}

fn keep_lines(content: String, keep: usize) -> String {
    let mut seen: Vec<String> = Vec::new();
    let mut y = String::new();
    let mut out = Vec::new();
    for line in content.lines() {
        let tokens: Vec<&str> = line.split_whitespace().collect();
        if tokens.last() == Some(&"Tm") {
            y = tokens[tokens.len() - 2].to_string();
        }
        let shows = tokens.last() == Some(&"TJ") || tokens.last() == Some(&"Tj");
        if shows && !seen.contains(&y) {
            seen.push(y.clone());
        }
        let kept = !shows || seen.iter().position(|seen_y| *seen_y == y) < Some(keep);
        out.push(if kept { line } else { "[] TJ" });
    }
    assert!(
        seen.len() > keep,
        "the page has more than {keep} text lines"
    );
    out.join("\n")
}

fn halves(content: &str) -> (Vec<String>, [Vec<String>; 2], Vec<String>) {
    let lines: Vec<String> = content.lines().map(String::from).collect();
    let placement = |line: &String| {
        let tokens: Vec<&str> = line.split_whitespace().collect();
        tokens.len() == 7 && tokens[6] == "cm" && tokens[2] == "0.0" && tokens[5] == "0.0"
    };
    let starts: Vec<usize> = (1..lines.len())
        .filter(|&i| lines[i - 1] == "q" && placement(&lines[i]))
        .map(|i| i - 1)
        .collect();
    let [left, right]: [usize; 2] = starts.try_into().expect("a side carries two halves");
    (
        lines[..left].to_vec(),
        [lines[left..right].to_vec(), lines[right..].to_vec()],
        Vec::new(),
    )
}

fn placed(block: &[String], x: &str) -> Vec<String> {
    let mut tokens: Vec<String> = block[1].split_whitespace().map(String::from).collect();
    tokens[4] = x.to_string();
    let mut moved = block.to_vec();
    moved[1] = tokens.join(" ");
    moved
}

fn rearrange(content: String, mirror: bool, repaint: bool) -> String {
    let (prefix, [left, right], suffix) = halves(&content);
    let x = |block: &[String]| block[1].split_whitespace().nth(4).unwrap().to_string();
    let (left_x, right_x) = (x(&left), x(&right));
    let (left, right) = if mirror {
        (placed(&left, &right_x), placed(&right, &left_x))
    } else {
        (left, right)
    };
    let painted = if repaint {
        [right, left]
    } else {
        [left, right]
    };
    [prefix, painted.concat(), suffix].concat().join("\n")
}

struct Variant {
    legs: Vec<Pdf>,
    manifest: Value,
}

impl Variant {
    fn leg(&mut self, name: &str) -> &mut Pdf {
        &mut self.legs[LEGS.iter().position(|leg| *leg == name).unwrap()]
    }
}

struct Fault {
    name: &'static str,
    edit: fn(&mut Variant),
    added: &'static [Row],
    removed: &'static [Row],
    python_missed: &'static [Row],
    python_spurious: &'static [Row],
    probes: &'static [Probe],
    python_probes: &'static [Probe],
}

fn resaved(_: &mut Variant) {}

fn swapped_sheets(v: &mut Variant) {
    v.leg("booklet-a4.pdf").swap(5, 7);
    v.leg("booklet-a4-interior.pdf").swap(3, 5);
    v.leg("booklet-a4-cover.pdf")
        .edit(1, |c| rearrange(c, true, true));
}

fn half_swaps(v: &mut Variant) {
    v.leg("booklet-a4.pdf")
        .edit(5, |c| rearrange(c, true, false));
    v.leg("booklet-a4-interior.pdf")
        .edit(3, |c| rearrange(c, false, true));
    v.leg("booklet-a4-cover.pdf")
        .edit(1, |c| rearrange(c, true, false));
}

fn missing_tail_band(v: &mut Variant) {
    v.leg("reader.pdf").edit(44, drop_image);
}

fn low_ppi_figure(v: &mut Variant) {
    let [width, height] = v.leg("reader.pdf").downsample(42, 16);
    assert_eq!([width, height], [150, 84], "2400x1350 at a sixteenth");
    let figure = v.manifest["layout"]["figures"]
        .as_array_mut()
        .unwrap()
        .iter_mut()
        .find(|figure| figure["page"] == 42)
        .expect("the page-42 figure");
    let box_width = figure["box_points"][2].as_f64().unwrap();
    figure["pixel_dimensions"] = json!([width, height]);
    figure["effective_ppi"] = json!((width as f64 * 72.0 / box_width * 10.0).round() / 10.0);
}

fn text_fields(v: &mut Variant) {
    let reader = v.leg("reader.pdf");
    reader.hide(2, "Inside cover", 300.0);
    reader.ink(55);
    reader.set(13, "");
    reader.set(14, "");
    reader.hide(14, "Hidden", 300.0);
    reader.hide(19, ".", 5.0);
    reader.hide(20, "a.", 5.0);
    reader.hide(21, "\u{85}", 5.0);
    reader.edit(44, |c| keep_lines(c, 5));
    reader.edit(49, |c| keep_lines(c, 4));
    let booklet = v.leg("booklet-a4.pdf");
    booklet.hide(2, "Inside cover", 300.0);
    booklet.set(9, "");
    booklet.set(11, "");
    booklet.hide(11, "Hidden", 300.0);
    v.leg("booklet-a4-cover.pdf").set(1, "");
}

fn raster_halves(v: &mut Variant) {
    v.leg("booklet-a4.pdf").ink(2);
    let cover = v.leg("booklet-a4-cover.pdf");
    cover.set(1, "");
    cover.hide(1, "Hidden", 300.0);
}

const FAULTS: [Fault; 7] = [
    Fault {
        name: "resaved",
        edit: resaved,
        added: &[],
        removed: &[],
        python_missed: &[],
        python_spurious: &[],
        probes: &[
            ("reader", 2, "blank", || json!(true)),
            ("reader", 13, "ink_free", || json!(false)),
            ("reader", 44, "body_text_lines", || json!(18)),
            ("reader", 49, "body_text_lines", || json!(18)),
            ("booklet", 2, "blank", || json!(true)),
            ("cover", 1, "ink_free", || json!(false)),
            ("spreads", 5, "text_order_matches", || json!(true)),
        ],
        python_probes: &[],
    },
    Fault {
        name: "swapped-sheets",
        edit: swapped_sheets,
        added: &ORDER,
        removed: &[],
        python_missed: &[],
        python_spurious: &[],
        probes: &[
            ("spreads", 5, "text_order_matches", || json!(false)),
            ("spreads", 6, "text_order_matches", || json!(true)),
            ("spreads", 7, "text_order_matches", || json!(false)),
            ("interior_spreads", 3, "text_order_matches", || json!(false)),
            ("interior_spreads", 5, "text_order_matches", || json!(false)),
            ("cover_spreads", 1, "text_order_matches", || json!(false)),
        ],
        python_probes: &[],
    },
    Fault {
        name: "half-swaps",
        edit: half_swaps,
        added: &[ORDER[0], ORDER[2]],
        removed: &[],
        python_missed: &[ORDER[0], ORDER[2]],
        python_spurious: &[ORDER[1]],
        probes: &[
            ("spreads", 5, "text_order_matches", || json!(false)),
            ("interior_spreads", 3, "text_order_matches", || json!(true)),
            ("cover_spreads", 1, "text_order_matches", || json!(false)),
        ],
        python_probes: &[
            ("spreads", 5, "text_order_matches", || json!(true)),
            ("interior_spreads", 3, "text_order_matches", || json!(false)),
            ("cover_spreads", 1, "text_order_matches", || json!(true)),
        ],
    },
    Fault {
        name: "missing-tail-band",
        edit: missing_tail_band,
        added: &[("article-tail-gap", "review", Some(44))],
        removed: &[],
        python_missed: &[],
        python_spurious: &[],
        probes: &[
            ("reader", 44, "tail_band", || Value::Null),
            ("reader", 44, "body_text_lines", || json!(18)),
        ],
        python_probes: &[],
    },
    Fault {
        name: "low-ppi-figure",
        edit: low_ppi_figure,
        added: &[],
        removed: &[],
        python_missed: &[],
        python_spurious: &[],
        probes: &[],
        python_probes: &[],
    },
    Fault {
        name: "text-fields",
        edit: text_fields,
        added: &[
            ("inside-cover-reader-not-blank", "error", Some(2)),
            ("inside-cover-reader-not-blank", "error", Some(55)),
            ("blank-page", "error", Some(13)),
            ("orphan-punctuation", "error", Some(19)),
            ("orphan-punctuation", "error", Some(21)),
            ("article-stub-last-page", "review", Some(49)),
            ("inside-cover-booklet-not-blank", "error", Some(2)),
            ("blank-booklet-side", "error", Some(9)),
            ("blank-cover-booklet-side", "error", Some(1)),
            ORDER[0],
            ORDER[1],
            ORDER[2],
        ],
        removed: &[],
        python_missed: &[],
        python_spurious: &[],
        probes: &[
            ("reader", 2, "text_characters", || json!(12)),
            ("reader", 2, "ink_ratio", || json!(0.0)),
            ("reader", 55, "blank", || json!(false)),
            ("reader", 55, "text_characters", || json!(0)),
            ("reader", 13, "ink_free", || json!(true)),
            ("reader", 14, "ink_free", || json!(false)),
            ("reader", 14, "ink_ratio", || json!(0.0)),
            ("reader", 14, "text_characters", || json!(6)),
            ("reader", 19, "standalone_punctuation_lines", || {
                json!(["."])
            }),
            ("reader", 20, "standalone_punctuation_lines", || json!([])),
            ("reader", 21, "standalone_punctuation_lines", || {
                json!(["\u{2026}"])
            }),
            ("reader", 44, "body_text_lines", || json!(5)),
            ("reader", 49, "body_text_lines", || json!(4)),
            ("booklet", 2, "blank", || json!(false)),
            ("booklet", 2, "ink_ratio", || json!(0.0)),
            ("booklet", 9, "ink_free", || json!(true)),
            ("booklet", 11, "ink_free", || json!(false)),
            ("booklet", 11, "ink_ratio", || json!(0.0)),
            ("cover", 1, "ink_free", || json!(true)),
        ],
        python_probes: &[],
    },
    Fault {
        name: "raster-halves",
        edit: raster_halves,
        added: &[
            ("inside-cover-booklet-not-blank", "error", Some(2)),
            ORDER[2],
        ],
        removed: &[],
        python_missed: &[],
        python_spurious: &[],
        probes: &[
            ("booklet", 2, "blank", || json!(false)),
            ("booklet", 2, "text_characters", || json!(0)),
            ("cover", 1, "ink_free", || json!(false)),
            ("cover", 1, "ink_ratio", || json!(0.0)),
            ("cover", 1, "text_characters", || json!(6)),
        ],
        python_probes: &[],
    },
];

fn key(row: &Value) -> (String, String, Option<u64>) {
    (
        row["code"].as_str().unwrap().to_string(),
        row["severity"].as_str().unwrap().to_string(),
        row.get("page").and_then(Value::as_u64),
    )
}

fn keys(rows: &[Row]) -> Vec<(String, String, Option<u64>)> {
    let mut out: Vec<_> = rows
        .iter()
        .map(|(code, severity, page)| {
            (
                code.to_string(),
                severity.to_string(),
                page.map(|p| p as u64),
            )
        })
        .collect();
    out.sort();
    out
}

fn by_rule(fault: &Fault) -> Vec<Row> {
    BASELINE
        .iter()
        .chain(fault.added)
        .filter(|row| !fault.removed.contains(row))
        .copied()
        .collect()
}

fn python_expectation(fault: &Fault) -> Vec<Row> {
    by_rule(fault)
        .into_iter()
        .filter(|row| !fault.python_missed.contains(row))
        .chain(fault.python_spurious.iter().copied())
        .collect()
}

fn python_want(fault: &Fault, probe: &Probe) -> Value {
    let (leg, number, field, want) = probe;
    fault
        .python_probes
        .iter()
        .find(|(l, n, f, _)| (l, n, f) == (leg, number, field))
        .map_or_else(want, |(_, _, _, python)| python())
}

fn shared_rows(value: &Value, gaps: &[Row]) -> Vec<Value> {
    let gaps = keys(gaps);
    value["issues"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|row| !gaps.contains(&key(row)))
        .cloned()
        .collect()
}

fn font_map() -> BTreeMap<String, streams::Face> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let spec: serde_yaml::Value = serde_yaml::from_str(
        &std::fs::read_to_string(root.join("meta/verification/parity.yaml"))
            .expect("parity.yaml is readable"),
    )
    .expect("parity.yaml is yaml");
    spec["normalization"]["font_name_map"]["entries"]
        .as_mapping()
        .expect("the font name map has entries")
        .iter()
        .map(|(alias, value)| {
            let file = root.join(value["file"].as_str().expect("a file"));
            let face = streams::Face {
                face: value["face"].as_str().expect("a face").to_string(),
                file: file.to_string_lossy().to_string(),
            };
            (alias.as_str().expect("an alias").to_string(), face)
        })
        .collect()
}

fn counts(layout: &Value, key: &str) -> BTreeMap<String, usize> {
    layout[key]
        .as_object()
        .map(|map| {
            map.iter()
                .filter_map(|(slug, value)| Some((slug.clone(), value.as_u64()? as usize)))
                .collect()
        })
        .unwrap_or_default()
}

fn rust_observed(destination: &Path, fonts: &BTreeMap<String, streams::Face>) -> Value {
    let layout = rules::manifest_layout(destination);
    let critique = rules::inspect_render(&rules::Inputs {
        reader_pdf: &destination.join(LEGS[0]),
        booklet_pdf: &destination.join(LEGS[1]),
        interior_booklet_pdf: &destination.join(LEGS[2]),
        cover_booklet_pdf: &destination.join(LEGS[3]),
        destination,
        toc: &counts(&layout, "toc"),
        article_pages: &counts(&layout, "article_pages"),
        editorial_pages: layout.get("editorial_pages").and_then(Value::as_i64),
        fonts,
    })
    .expect("the rust critic runs");
    let spreads =
        |rows: &[rules::Spread]| rows.iter().map(rules::Spread::as_row).collect::<Value>();
    let sides = |rows: &[inspect::PageInspection]| {
        rows.iter()
            .map(inspect::PageInspection::row)
            .collect::<Value>()
    };
    let mut observed = critique.decisions();
    observed["reader"] = critique
        .pages
        .iter()
        .map(rules::PageAnnotation::as_row)
        .collect();
    observed["booklet"] = sides(&critique.booklet_pages);
    observed["cover"] = sides(&critique.cover_booklet_pages);
    observed["spreads"] = spreads(&critique.spreads);
    observed["interior_spreads"] = spreads(&critique.interior_spreads);
    observed["cover_spreads"] = spreads(&critique.cover_spreads);
    observed
}

fn stage(render: &Path, root: &Path, fault: &Fault) -> [PathBuf; 2] {
    let mut variant = Variant {
        legs: LEGS
            .iter()
            .map(|leg| Pdf {
                doc: Document::load(render.join(leg)).expect("the leg loads"),
            })
            .collect(),
        manifest: serde_json::from_str(
            &std::fs::read_to_string(render.join("edition-manifest.json")).unwrap(),
        )
        .unwrap(),
    };
    (fault.edit)(&mut variant);
    let dirs = ["py", "rs"].map(|side| root.join(fault.name).join(side));
    for dir in &dirs {
        std::fs::create_dir_all(dir).unwrap();
        for (leg, pdf) in LEGS.iter().zip(variant.legs.iter_mut()) {
            pdf.doc.save(dir.join(leg)).expect("the faulted leg saves");
        }
        std::fs::write(
            dir.join("edition-manifest.json"),
            serde_json::to_string_pretty(&variant.manifest).unwrap(),
        )
        .unwrap();
    }
    dirs
}

fn inputs(dir: &Path) -> Value {
    let mut names: Vec<String> = LEGS.iter().map(|leg| leg.to_string()).collect();
    names.push("edition-manifest.json".into());
    let digest = |name: &String| oracle::sha256(&std::fs::read(dir.join(name)).unwrap());
    json!(names
        .iter()
        .map(|name| (name.clone(), digest(name)))
        .collect::<BTreeMap<_, _>>())
}

fn probe_key((leg, number, field, _): &Probe) -> String {
    format!("{leg} {number} {field}")
}

fn committed_python(_staged: &[[PathBuf; 2]]) -> Value {
    let text = oracle::expectation("critic_faults_expected.json");
    serde_json::from_str(&text).expect("the expectation parses")
}

#[test]
fn authored_expectations_follow_the_imposition_plan() {
    let all = impose::imposed_reader_page_plan(&(1..=56).collect::<Vec<_>>());
    assert_eq!(all[0], (Some(56), Some(1)));
    assert_eq!(
        all[1],
        (Some(2), Some(55)),
        "booklet side 2 carries both inside covers"
    );
    let cover = impose::cover_wrap_plan(56).unwrap();
    assert_eq!(
        cover,
        vec![(Some(56), Some(1))],
        "the cover wrap is one outside side"
    );
    for pages in 4..=64 {
        let wrap = impose::cover_wrap_plan(pages).unwrap();
        let inside = [Some(2), Some(pages - 1)];
        assert!(
            wrap.iter()
                .all(|(l, r)| !(inside.contains(l) && inside.contains(r))),
            "cover-booklet-inside-not-blank is unreachable at {pages} pages"
        );
    }
    for fault in &FAULTS {
        assert!(
            fault
                .python_missed
                .iter()
                .all(|row| by_rule(fault).contains(row)),
            "{}: a missed row must be expected by the rule",
            fault.name
        );
        assert!(
            fault
                .python_spurious
                .iter()
                .all(|row| !by_rule(fault).contains(row)),
            "{}: a spurious row must not be expected by the rule",
            fault.name
        );
    }
}

#[test]
fn rust_decides_every_fault_by_the_rule() {
    let Ok(render) = std::env::var("MAG_CRITIC_FAULTS_RENDER_DIR") else {
        println!("MODE: skipped, MAG_CRITIC_FAULTS_RENDER_DIR unset");
        return;
    };
    let render = PathBuf::from(render);
    println!("MODE: full, faulting {}", render.display());
    let root = std::env::temp_dir().join(format!("wp53c-faults-{}", std::process::id()));
    let staged: Vec<[PathBuf; 2]> = FAULTS.iter().map(|f| stage(&render, &root, f)).collect();
    let committed = committed_python(&staged);
    let fonts = font_map();
    let rust: Vec<Value> = staged
        .iter()
        .map(|[_, rs]| rust_observed(rs, &fonts))
        .collect();
    let mut failures = Vec::new();
    for (([py, _], fault), produced) in staged.iter().zip(&FAULTS).zip(rust) {
        let recorded = &committed[fault.name];
        assert_eq!(
            recorded["inputs"],
            inputs(py),
            "{}: the staged legs differ from the ones the committed Python verdict read",
            fault.name
        );
        let expected = recorded["python"].clone();
        let rows = |value: &Value| value["issues"].as_array().unwrap().clone();
        let sorted = |value: &Value| {
            let mut out: Vec<_> = rows(value).iter().map(key).collect();
            out.sort();
            out
        };
        println!(
            "FAULT: {} python {} rust {} issues, result {} / {}",
            fault.name,
            rows(&expected).len(),
            rows(&produced).len(),
            expected["result"],
            produced["result"]
        );
        for row in rows(&produced) {
            println!("  ISSUE: {:?}", key(&row));
        }
        for row in fault.python_missed {
            println!("  PYTHON GAP missed: {row:?}");
        }
        for row in fault.python_spurious {
            println!("  PYTHON GAP spurious: {row:?}");
        }
        let python_shared = shared_rows(&expected, fault.python_spurious);
        let rust_shared = shared_rows(&produced, fault.python_missed);
        if expected["result"] != produced["result"] || python_shared != rust_shared {
            failures.push(format!(
                "{}: the critics disagree beyond the declared python gaps\n python {}\n rust   {}",
                fault.name, expected["issues"], produced["issues"]
            ));
        }
        for probe in fault.probes {
            let (leg, number, field, want) = probe;
            let python_value = expected["probes"][probe_key(probe)].clone();
            let rust_value = produced[*leg][number - 1][*field].clone();
            println!("  PROBE: {leg} {number} {field} python {python_value} rust {rust_value}");
            if python_value != python_want(fault, probe) || rust_value != want() {
                failures.push(format!(
                    "{}: {leg} {number} {field} wants rust {} python {}",
                    fault.name,
                    want(),
                    python_want(fault, probe)
                ));
            }
        }
        if sorted(&produced) != keys(&by_rule(fault)) {
            failures.push(format!(
                "{}: rust decided {:?}\n  the rule wants {:?}",
                fault.name,
                sorted(&produced),
                keys(&by_rule(fault))
            ));
        }
        if sorted(&expected) != keys(&python_expectation(fault)) {
            failures.push(format!(
                "{}: python decided {:?}\n  its declared gaps want {:?}",
                fault.name,
                sorted(&expected),
                keys(&python_expectation(fault))
            ));
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n"));
    std::fs::remove_dir_all(&root).expect("the scratch tree is removable");
}
