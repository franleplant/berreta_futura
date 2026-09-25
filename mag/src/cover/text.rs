use crate::model::manifest::Edition;
use crate::model::shared::{py_casefold, py_str, py_strip, py_upper, py_zfill};
use serde_yaml::Mapping;
use std::collections::BTreeSet;

pub fn cover_date(value: &str) -> String {
    let parts: Vec<&str> = value.split('-').collect();
    if parts.len() == 3 && parts.iter().all(|part| !part.is_empty()) {
        parts.join(" ")
    } else {
        value.to_string()
    }
}

pub fn cover_contributors(edition: &Edition) -> String {
    let mut authors: Vec<String> = Vec::new();
    let mut seen: BTreeSet<String> = BTreeSet::new();
    for article in &edition.articles {
        let author = lead_author(py_strip(&article.author));
        if !author.is_empty() && seen.insert(py_casefold(&author)) {
            authors.push(author);
        }
    }
    if !authors.is_empty() {
        return py_upper(&authors.join(" / "));
    }
    py_strip(&deck(&edition.cover)).to_string()
}

fn lead_author(author: &str) -> String {
    let names: Vec<&str> = author
        .split([',', '&'])
        .flat_map(|part| part.split(" and "))
        .map(str::trim)
        .filter(|name| !name.is_empty())
        .collect();
    match names.as_slice() {
        [first, _, ..] => format!("{first} et al."),
        _ => author.to_string(),
    }
}

fn deck(cover: &Mapping) -> String {
    cover.get("deck").map(py_str).unwrap_or_default()
}

pub fn cover_tab_issue(edition: &Edition) -> String {
    let label = if edition.language.split('-').next() == Some("en") {
        "ISSUE"
    } else {
        "N\u{da}MERO"
    };
    format!("{label} {}", py_zfill(&edition.issue_number, 3))
}

pub fn cover_tab_identity(edition: &Edition) -> String {
    format!("{} / BUENOS AIRES", py_upper(&edition.publication_name))
}
