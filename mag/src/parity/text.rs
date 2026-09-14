use anyhow::{Context, Result};
use serde::Serialize;
use std::path::Path;
use std::process::Command;
use unicode_normalization::UnicodeNormalization;

#[derive(Serialize)]
pub struct TextClause {
    pub status: String,
    pub pages_differing: Vec<u32>,
}

pub fn page_texts(pdf: &Path, first: u32, last: u32) -> Result<Vec<String>> {
    let out = Command::new("pdftotext")
        .args(["-f", &first.to_string(), "-l", &last.to_string()])
        .args(["-enc", "UTF-8"])
        .arg(pdf)
        .arg("-")
        .output()
        .context("running pdftotext")?;
    anyhow::ensure!(
        out.status.success(),
        "pdftotext failed on {}",
        pdf.display()
    );
    let text = String::from_utf8(out.stdout).context("pdftotext output not UTF-8")?;
    let pages: Vec<String> = text
        .split('\u{c}')
        .take((last - first + 1) as usize)
        .map(str::to_string)
        .collect();
    anyhow::ensure!(
        pages.len() == (last - first + 1) as usize,
        "pdftotext returned {} pages for {}..{} of {}",
        pages.len(),
        first,
        last,
        pdf.display()
    );
    Ok(pages)
}

pub fn normalize(raw: &str) -> String {
    let nfc: String = raw.nfc().collect();
    let rejoined = rejoin_line_end_hyphens(&nfc);
    let no_soft: String = rejoined.chars().filter(|c| *c != '\u{ad}').collect();
    no_soft.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn rejoin_line_end_hyphens(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::with_capacity(s.len());
    let mut i = 0;
    while i < chars.len() {
        if is_hyphenate(chars[i])
            && i > 0
            && chars[i - 1].is_alphabetic()
            && chars.get(i + 1) == Some(&'\n')
            && chars.get(i + 2).is_some_and(|c| c.is_alphabetic())
        {
            i += 2;
            continue;
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

fn is_hyphenate(c: char) -> bool {
    matches!(c, '-' | '\u{ad}' | '\u{2010}')
}

pub fn compare(a: &[String], b: &[String], first_page: u32) -> TextClause {
    let pages_differing: Vec<u32> = a
        .iter()
        .zip(b)
        .enumerate()
        .filter(|(_, (pa, pb))| normalize(pa) != normalize(pb))
        .map(|(i, _)| first_page + i as u32)
        .collect();
    TextClause {
        status: if pages_differing.is_empty() {
            "pass".into()
        } else {
            "fail".into()
        },
        pages_differing,
    }
}
