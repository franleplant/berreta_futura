mod checks;

use checks::{load, verdicts, Fixture, Verdicts};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const TOOLS: [(&str, &str); 4] = [
    ("pdf2md", "pdf2md.md"),
    ("pypdf", "pypdf.txt"),
    ("poppler", "poppler.txt"),
    ("poppler-layout", "poppler-layout.txt"),
];

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/pdf_fixtures")
}

fn fixtures() -> Vec<Fixture> {
    let mut dirs: Vec<PathBuf> = std::fs::read_dir(root())
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.join("source.pdf").exists())
        .collect();
    dirs.sort();
    dirs.iter().map(|d| load(d)).collect()
}

fn failing(v: &Verdicts) -> Vec<&str> {
    v.iter()
        .filter(|(_, ok)| !ok)
        .map(|(id, _)| id.as_str())
        .collect()
}

fn verdict(v: &Verdicts, id: &str) -> bool {
    v.iter()
        .find(|(k, _)| k == id)
        .unwrap_or_else(|| panic!("no check {id}"))
        .1
}

fn table() -> String {
    let mut out = String::new();
    for f in fixtures() {
        for (tool, file) in TOOLS {
            let text = std::fs::read_to_string(root().join(&f.name).join(file)).unwrap();
            for (id, ok) in verdicts(&f, &text) {
                let mark = if ok { "PASS" } else { "FAIL" };
                out.push_str(&format!("{}\t{tool}\t{id}\t{mark}\n", f.name));
            }
        }
    }
    out
}

#[test]
fn fixtures_are_the_pinned_real_pdfs() {
    let all = fixtures();
    assert!(all.len() >= 5, "the corpus holds {} fixtures", all.len());
    for f in all {
        let bytes = std::fs::read(root().join(&f.name).join("source.pdf")).unwrap();
        assert!(bytes.starts_with(b"%PDF-"), "{} is a PDF", f.name);
        assert_eq!(
            hex::encode(Sha256::digest(&bytes)),
            f.spec.sha256,
            "{}",
            f.name
        );
        assert!(
            f.spec.source.starts_with("http"),
            "{} names where it came from",
            f.name
        );
        assert!(!f.spec.retrieved.is_empty() && !f.spec.producer.is_empty());
        assert!(!f.spec.shape.is_empty() && !f.spec.review.is_empty());
        assert!(f.spec.review.iter().all(|r| !r.at.is_empty()
            && !r.pypdf.is_empty()
            && !r.poppler.is_empty()
            && !r.truth.is_empty()));
        assert!(f.passages.len() >= 4, "{} has few passages", f.name);
        assert!(f.spec.order.iter().all(|g| g.len() >= 2), "{}", f.name);
        assert!(f.spec.line_end_hyphens.iter().all(|h| h.contains("-|")));
    }
}

#[test]
fn ground_truth_passes_every_check() {
    for f in fixtures() {
        let v = verdicts(&f, &f.truth);
        assert!(failing(&v).is_empty(), "{}: {:?}", f.name, failing(&v));
    }
}

#[test]
fn recorded_verdicts_match() {
    let path = root().join("verdicts.tsv");
    let actual = table();
    if std::env::var("MAG_PDF_FIXTURES_BLESS").is_ok() {
        std::fs::write(&path, &actual).unwrap();
    }
    assert_eq!(std::fs::read_to_string(&path).unwrap(), actual);
}

#[test]
fn every_check_family_discriminates_on_real_output() {
    let mut families: BTreeMap<String, (usize, usize)> = BTreeMap::new();
    for line in table().lines() {
        let cols: Vec<&str> = line.split('\t').collect();
        let family = cols[2].split(':').next().unwrap().to_string();
        let entry = families.entry(family).or_default();
        if cols[3] == "PASS" {
            entry.0 += 1;
        } else {
            entry.1 += 1;
        }
    }
    for (family, (pass, fail)) in &families {
        assert!(*pass > 0 && *fail > 0, "{family}: {pass} pass, {fail} fail");
    }
}

fn mutated(f: &Fixture, text: String, id: &str) -> bool {
    verdict(&verdicts(f, &text), id)
}

#[test]
fn each_defect_trips_its_check() {
    for f in fixtures() {
        let t = &f.truth;
        let first = f.passages[0].as_str();
        let flat = t.replace('\n', " ");
        assert!(
            flat.contains(first),
            "{}: first passage sits on one line",
            f.name
        );
        assert!(!mutated(&f, flat.replacen(first, "", 1), "passage:0"));
        assert!(!mutated(&f, format!("{flat}\n{first}"), "passage:0"));
        let (a, b) = (&f.spec.order[0][0], &f.spec.order[0][1]);
        assert!(!mutated(&f, format!("{b}\n{a}"), "order:0.0"), "{}", f.name);
        assert!(
            !mutated(&f, flat.replacen(a.as_str(), "", 1), "order:0.0"),
            "{}",
            f.name
        );
        let soft = f
            .spec
            .line_end_hyphens
            .iter()
            .enumerate()
            .map(|(i, h)| (format!("hyphen:{i}"), h));
        let real = f
            .spec
            .real_hyphens
            .iter()
            .enumerate()
            .map(|(i, h)| (format!("real-hyphen:{i}"), h));
        for (id, h) in soft.chain(real).filter(|(_, h)| h.contains("-|")) {
            let welded = t.replace(&h.replace('|', ""), &h.replace("-|", ""));
            assert!(!mutated(&f, welded, &id), "{} {h}", f.name);
            let spaced = t.replace(&h.replace('|', ""), &h.replace("-|", " -"));
            assert!(!mutated(&f, spaced, &id), "{} {h}", f.name);
        }
        for (i, a) in f.spec.absent.iter().enumerate() {
            assert!(!mutated(&f, format!("{t}{a}"), &format!("absent:{i}")));
        }
        assert!(!mutated(
            &f,
            t.replacen("fi", "\u{FB01}", 1),
            "chars:ligature"
        ));
        assert!(!mutated(&f, t.replacen("f", "\u{0}", 1), "chars:control"));
        assert!(!mutated(&f, format!("{t}\u{AD}"), "chars:soft-hyphen"));
        assert!(!mutated(&f, format!("{t}\u{FFFD}"), "chars:replacement"));
        for (i, block) in f.code.iter().enumerate() {
            let line = block.iter().rfind(|l| l.starts_with(' ')).unwrap();
            let shifted = t.replacen(&format!("\n{line}\n"), &format!("\n {line}\n"), 1);
            assert!(!mutated(&f, shifted.clone(), &format!("code-exact:{i}")));
            assert!(
                mutated(&f, shifted, &format!("code:{i}")),
                "{} code {i}",
                f.name
            );
            let cut = t.replacen(&format!("\n{line}\n"), "\n", 1);
            assert!(
                !mutated(&f, cut, &format!("code:{i}")),
                "{} code {i}",
                f.name
            );
        }
    }
}
