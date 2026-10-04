use crate::model::manifest::Edition;
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
        let author = lead_author(article.author.trim());
        if !author.is_empty() && seen.insert(author.to_lowercase()) {
            authors.push(author);
        }
    }
    if !authors.is_empty() {
        return authors.join(" / ").to_uppercase();
    }
    edition
        .cover
        .deck
        .as_deref()
        .unwrap_or_default()
        .trim()
        .to_string()
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

pub fn cover_tab_issue(edition: &Edition) -> String {
    let label = if edition.language.split('-').next() == Some("en") {
        "ISSUE"
    } else {
        "N\u{da}MERO"
    };
    format!("{label} {:0>3}", edition.issue_number)
}

pub fn cover_tab_identity(edition: &Edition) -> String {
    format!("{} / BUENOS AIRES", edition.publication_name.to_uppercase())
}
