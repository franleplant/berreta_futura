use super::html::Page;
use crate::model::doc::educate_reader_quotes;
use crate::util::escape_html;
use anyhow::{Context, Result};
use serde::Deserialize;
use std::fs;
use std::path::Path;

#[derive(Deserialize)]
struct Text {
    title: String,
    paragraphs: Vec<String>,
    creed: Vec<String>,
}

#[derive(Deserialize)]
struct Texts {
    #[serde(flatten)]
    en: Text,
    es: Option<Text>,
}

#[derive(Deserialize)]
struct Credits {
    maker: String,
    email: String,
}

#[derive(Deserialize)]
pub struct About {
    about: Texts,
    credits: Credits,
}

pub fn load(root: &Path) -> Result<About> {
    let text = fs::read_to_string(root.join("magazine.toml")).context("reading magazine.toml")?;
    toml::from_str(&text)
        .context("magazine.toml needs [about] (title, paragraphs, creed) and [credits]")
}

pub fn label(language: &str) -> &'static str {
    match language {
        "es" => "Acerca de",
        _ => "About",
    }
}

fn made(language: &str) -> &'static str {
    match language {
        "es" => "Hecha por",
        _ => "Made by",
    }
}

pub fn path(language: &str) -> String {
    match language {
        "en" => "about/".to_string(),
        other => format!("{other}/about/"),
    }
}

fn prose(value: &str) -> String {
    escape_html(&educate_reader_quotes(value))
}

pub fn page(language: &str, about: &About, name: &str, other: Option<&str>) -> Result<Page> {
    let text = match language {
        "es" => about
            .about
            .es
            .as_ref()
            .context("magazine.toml needs [about.es] for the Spanish about page")?,
        _ => &about.about.en,
    };
    let (lede, rest) = text
        .paragraphs
        .split_first()
        .context("magazine.toml [about] paragraphs is empty")?;
    let paragraphs: String = rest
        .iter()
        .map(|p| format!("<p>{}</p>\n", prose(p)))
        .collect();
    let creed: String = text
        .creed
        .iter()
        .map(|line| format!("<li>{}</li>", prose(line)))
        .collect();
    let email = escape_html(&about.credits.email);
    Ok(Page {
        path: path(language),
        language: language.to_string(),
        title: text.title.clone(),
        description: educate_reader_quotes(lede),
        image: None,
        alternate: other.map(|o| (o.to_string(), path(o))),
        crumb: String::new(),
        body: format!(
            "<section class=\"about\">\n<p class=\"kicker\">{}</p>\n<h1>{}</h1>\n<p class=\"lede\">{}</p>\n{paragraphs}<ul class=\"creed\">{creed}</ul>\n<p class=\"credits\">{} {} · <a href=\"mailto:{email}\">{email}</a></p>\n</section>",
            label(language),
            escape_html(name),
            prose(lede),
            made(language),
            escape_html(&about.credits.maker),
        ),
    })
}
