use lopdf::{dictionary, Document, Object, Stream};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::process::Command;

const PAGES: u32 = 6;
const A5: [f64; 2] = [419.528, 595.276];
const INK: [f64; 3] = [0.055, 0.075, 0.085];
const TEXT: &str = "alpha beta gamma delta epsilon zeta";
const IMAGE_SIDE: usize = 8;

#[derive(Clone)]
struct Spec {
    text: String,
    y_offset: f64,
    image_page: u32,
    inverted_pixels: usize,
    ink: [f64; 3],
    link: bool,
    mediabox_delta: f64,
}

impl Default for Spec {
    fn default() -> Self {
        Spec {
            text: TEXT.into(),
            y_offset: 0.0,
            image_page: 3,
            inverted_pixels: 0,
            ink: INK,
            link: true,
            mediabox_delta: 0.0,
        }
    }
}

fn tounicode() -> Stream {
    let cmap = b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n\
/CMapName /A def /CMapType 2 def\n\
1 begincodespacerange <20> <7e> endcodespacerange\n\
1 beginbfrange <20> <7e> <0020> endbfrange\n\
endcmap end end\n";
    Stream::new(dictionary! {}, cmap.to_vec())
}

fn image(inverted: usize) -> Stream {
    let mut pixels = Vec::new();
    for i in 0..IMAGE_SIDE * IMAGE_SIDE {
        let base = [(i * 3) as u8, 90, 180];
        let flip = i < inverted;
        pixels.extend(base.iter().map(|c| if flip { 255 - c } else { *c }));
    }
    Stream::new(
        dictionary! {
            "Type" => "XObject",
            "Subtype" => "Image",
            "Width" => IMAGE_SIDE as i64,
            "Height" => IMAGE_SIDE as i64,
            "ColorSpace" => "DeviceRGB",
            "BitsPerComponent" => 8,
        },
        pixels,
    )
}

fn content(spec: &Spec, page: u32) -> Vec<u8> {
    let [r, g, b] = spec.ink;
    let text = if page == 4 { &spec.text } else { TEXT };
    let y = 500.0 - if page == 4 { spec.y_offset } else { 0.0 };
    let mut ops = format!(
        "{r} {g} {b} rg\nBT /F1 10 Tf 60 {y} Td ({text}) Tj ET\n\
0.2 0.2 0.2 RG 1 w 60 120 m 300 120 l S\n"
    );
    if page == spec.image_page {
        ops.push_str("q 120 0 0 90 100 300 cm /Im1 Do Q\n");
    }
    ops.into_bytes()
}

fn build(spec: &Spec, path: &Path) {
    let mut doc = Document::with_version("1.7");
    let tounicode_id = doc.add_object(tounicode());
    let font_id = doc.add_object(dictionary! {
        "Type" => "Font",
        "Subtype" => "Type1",
        "BaseFont" => "Helvetica",
        "FirstChar" => 32,
        "LastChar" => 126,
        "Widths" => (32..=126).map(|_| Object::Integer(500)).collect::<Vec<_>>(),
        "ToUnicode" => tounicode_id,
    });
    let image_id = doc.add_object(image(spec.inverted_pixels));
    let pages_id = doc.new_object_id();
    let page_ids: Vec<_> = (0..PAGES).map(|_| doc.new_object_id()).collect();
    for (index, id) in page_ids.iter().enumerate() {
        let page = index as u32 + 1;
        let stream_id = doc.add_object(Stream::new(dictionary! {}, content(spec, page)));
        let delta = if page == 4 { spec.mediabox_delta } else { 0.0 };
        let mut dict = dictionary! {
            "Type" => "Page",
            "Parent" => pages_id,
            "Contents" => stream_id,
            "MediaBox" => vec![0.into(), 0.into(), A5[0].into(), (A5[1] + delta).into()],
            "Resources" => dictionary! {
                "Font" => dictionary! { "F1" => font_id },
                "XObject" => dictionary! { "Im1" => image_id },
            },
        };
        if spec.link && page == 3 {
            let annot = doc.add_object(dictionary! {
                "Type" => "Annot",
                "Subtype" => "Link",
                "Rect" => vec![100.into(), 100.into(), 200.into(), 120.into()],
                "Border" => vec![0.into(), 0.into(), 0.into()],
                "A" => dictionary! {
                    "S" => "GoTo",
                    "D" => vec![page_ids[4].into(), "Fit".into()],
                },
            });
            dict.set("Annots", vec![annot.into()]);
        }
        doc.objects.insert(*id, Object::Dictionary(dict));
    }
    doc.objects.insert(
        pages_id,
        Object::Dictionary(dictionary! {
            "Type" => "Pages",
            "Count" => PAGES as i64,
            "Kids" => page_ids.iter().map(|id| Object::Reference(*id)).collect::<Vec<_>>(),
        }),
    );
    let catalog_id = doc.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
    doc.trailer.set("Root", catalog_id);
    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
    doc.save(path).unwrap();
}

fn root() -> PathBuf {
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/.."))
}

fn tree(dir: &Path, name: &str, spec: &Spec) -> PathBuf {
    let path = dir.join(name).join("en/reader.pdf");
    build(spec, &path);
    dir.join(name)
}

fn failing_clauses(verdict: &serde_json::Value) -> BTreeSet<String> {
    let mut failing = BTreeSet::new();
    let s = &verdict["tier_s"];
    for clause in ["page_count", "boxes", "text", "color", "navigation"] {
        if s[clause]["status"] == "fail" {
            failing.insert(clause.to_string());
        }
    }
    if verdict["tier_e"]["display_list"]["status"] == "fail" {
        failing.insert("display_list".into());
    }
    if verdict["tier_e"]["raster"]["status"] == "fail" {
        failing.insert("raster_guard".into());
    }
    let v = &verdict["tier_v"];
    if !v["dimension_mismatches"]
        .as_array()
        .is_none_or(|a| a.is_empty())
    {
        failing.insert("raster_dimensions".into());
    }
    if v["v1"] == false {
        failing.insert("v1".into());
    }
    if v["v2"] == false {
        failing.insert("v2".into());
    }
    failing
}

fn parity(label: &str, a: &Path, b: &Path) -> (serde_json::Value, i32) {
    let out = Command::new(env!("CARGO_BIN_EXE_mag"))
        .current_dir(root())
        .args(["parity", label, "--pre-rendered"])
        .args([a, b])
        .output()
        .expect("mag parity");
    let verdict = root()
        .join("output/parity")
        .join(label)
        .join("verdict.json");
    let raw = std::fs::read_to_string(&verdict).unwrap_or_else(|e| {
        panic!(
            "{label}: no verdict ({e})\n{}\n{}",
            String::from_utf8_lossy(&out.stdout),
            String::from_utf8_lossy(&out.stderr)
        )
    });
    (
        serde_json::from_str(&raw).expect("verdict json"),
        out.status.code().unwrap_or(-1),
    )
}

fn matrix() -> serde_yaml::Value {
    let raw = std::fs::read_to_string(root().join("meta/verification/parity.yaml")).unwrap();
    let spec: serde_yaml::Value = serde_yaml::from_str(&raw).unwrap();
    spec["fault_suite"]["expected_detections"].clone()
}

fn faults() -> Vec<(&'static str, Spec)> {
    let swapped = TEXT.replace("beta gamma", "gamma beta");
    vec![
        (
            "swapped_words",
            Spec {
                text: swapped,
                ..Spec::default()
            },
        ),
        (
            "line_moved_005",
            Spec {
                y_offset: 0.05,
                ..Spec::default()
            },
        ),
        (
            "line_moved_03",
            Spec {
                y_offset: 0.3,
                ..Spec::default()
            },
        ),
        (
            "figure_shifted_page",
            Spec {
                image_page: 4,
                ..Spec::default()
            },
        ),
        (
            "recolor_30px",
            Spec {
                inverted_pixels: 30,
                ..Spec::default()
            },
        ),
        (
            "body_ink_pure_black",
            Spec {
                ink: [0.0, 0.0, 0.0],
                ..Spec::default()
            },
        ),
        (
            "dropped_link_annotation",
            Spec {
                link: false,
                ..Spec::default()
            },
        ),
        (
            "mediabox_off_05",
            Spec {
                mediabox_delta: 0.5,
                ..Spec::default()
            },
        ),
    ]
}

#[test]
fn seeded_faults_are_detected() {
    let dir = root().join("output/parity-faults");
    let _ = std::fs::remove_dir_all(&dir);
    let clean = tree(&dir, "clean", &Spec::default());
    let (control, control_code) = parity("fault-control", &clean, &clean);
    assert_eq!(control_code, 0, "clean pair must pass");
    assert!(
        failing_clauses(&control).is_empty(),
        "clean pair flagged {:?}",
        failing_clauses(&control)
    );
    let expected = matrix();
    let mut observed = Vec::new();
    let mut want = Vec::new();
    for (name, spec) in faults() {
        let faulty = tree(&dir, name, &spec);
        let (verdict, code) = parity(&format!("fault-{name}"), &clean, &faulty);
        let flags = failing_clauses(&verdict);
        let intended = expected[name]["intended_check"].as_str().unwrap_or("");
        assert!(
            flags.contains(intended),
            "{name} missed {intended}: {flags:?}"
        );
        assert_ne!(
            verdict["tier_e"]["display_list"]["status"], "pass",
            "{name} passed Tier E display list"
        );
        assert_eq!(code, 1, "{name} must exit nonzero");
        observed.push((name.to_string(), flags));
        want.push((
            name.to_string(),
            expected[name]["must_flag"]
                .as_sequence()
                .unwrap_or(&Vec::new())
                .iter()
                .map(|v| v.as_str().unwrap_or_default().to_string())
                .collect::<BTreeSet<String>>(),
        ));
    }
    assert_eq!(observed, want, "expected-detections matrix");
}
