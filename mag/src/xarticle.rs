use anyhow::{bail, Context, Result};
use regex::Regex;
use serde_json::Value;
use std::fmt::Write as _;
use std::sync::LazyLock;

static STATUS_URL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/(?:article|status)/(\d+)")
        .unwrap()
});
static ARTICLE_ID_URL: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^https?://(?:www\.)?(?:x|twitter)\.com/i/article/\d+").unwrap());

pub fn page_for(url: &str) -> Result<Option<String>> {
    if ARTICLE_ID_URL.is_match(url) {
        bail!(
            "{url} is an X article id, not a status: open it in a browser, let it redirect \
             to x.com/<user>/article/<status id>, and capture that URL"
        );
    }
    let Some(c) = STATUS_URL.captures(url) else {
        return Ok(None);
    };
    let api = format!("https://api.fxtwitter.com/{}/status/{}", &c[1], &c[2]);
    let body = crate::capture::curl_text(&api)?;
    let doc: Value = serde_json::from_str(&body).with_context(|| format!("parsing {api}"))?;
    let tweet = &doc["tweet"];
    if tweet["article"].is_null() {
        return Ok(None);
    }
    Ok(Some(article_html(tweet)))
}

fn escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn entity<'a>(entities: &'a Value, key: &Value) -> Option<&'a Value> {
    let key = key
        .as_u64()
        .map_or_else(|| key.to_string(), |k| k.to_string());
    match entities {
        Value::Array(list) => list
            .iter()
            .find(|e| e["key"].as_str() == Some(key.as_str()))
            .map(|e| &e["value"]),
        Value::Object(map) => map.get(&key),
        _ => None,
    }
}

fn inline(block: &Value, entities: &Value, styled: bool) -> String {
    let chars: Vec<char> = block["text"].as_str().unwrap_or("").chars().collect();
    let mut marks: Vec<(Vec<String>, Vec<String>)> =
        vec![(Vec::new(), Vec::new()); chars.len() + 1];
    let ranges = |name: &str| block[name].as_array().cloned().unwrap_or_default();
    let span = |r: &Value| {
        let start = usize::try_from(r["offset"].as_u64().unwrap_or(0)).unwrap_or(0);
        let end = start + usize::try_from(r["length"].as_u64().unwrap_or(0)).unwrap_or(0);
        (start.min(chars.len()), end.min(chars.len()))
    };
    for r in ranges("inlineStyleRanges").iter().filter(|_| styled) {
        let tag = match r["style"].as_str() {
            Some("Bold") => "strong",
            Some("Italic") => "em",
            Some("Code") => "code",
            _ => continue,
        };
        let (start, end) = span(r);
        marks[start].1.push(format!("<{tag}>"));
        marks[end].0.insert(0, format!("</{tag}>"));
    }
    for r in &ranges("entityRanges") {
        let Some(e) = entity(entities, &r["key"]).filter(|e| e["type"] == "LINK") else {
            continue;
        };
        let (start, end) = span(r);
        let href = escape(e["data"]["url"].as_str().unwrap_or(""));
        marks[start].1.push(format!("<a href=\"{href}\">"));
        marks[end].0.insert(0, "</a>".to_string());
    }
    let mut out = String::new();
    for (i, mark) in marks.iter().enumerate() {
        out += &mark.0.concat();
        out += &mark.1.concat();
        if let Some(c) = chars.get(i) {
            out += &escape(&c.to_string());
        }
    }
    out
}

fn atomic(block: &Value, entities: &Value, media: &Value) -> String {
    let mut out = String::new();
    for r in block["entityRanges"].as_array().into_iter().flatten() {
        let Some(e) = entity(entities, &r["key"]) else {
            continue;
        };
        if e["type"] == "MARKDOWN" {
            let markdown = e["data"]["markdown"].as_str().unwrap_or("");
            let _ = write!(out, "<pre class=\"markdown\">{}</pre>", escape(markdown));
            continue;
        }
        let caption = escape(e["data"]["caption"].as_str().unwrap_or(""));
        for item in e["data"]["mediaItems"].as_array().into_iter().flatten() {
            let src = media
                .as_array()
                .into_iter()
                .flatten()
                .find(|m| m["media_id"] == item["mediaId"])
                .and_then(|m| m["media_info"]["original_img_url"].as_str());
            if let Some(src) = src {
                let _ = write!(
                    out,
                    "<figure><img src=\"{src}\" alt=\"{caption}\"><figcaption>{caption}</figcaption></figure>"
                );
            }
        }
    }
    out
}

fn is_title_tail(block: &Value) -> bool {
    let text = block["text"].as_str().unwrap_or("").trim();
    (text.starts_with("...") || text.starts_with('\u{2026}'))
        && text.split_whitespace().count() <= 8
}

fn article_html(tweet: &Value) -> String {
    let article = &tweet["article"];
    let entities = &article["content"]["entityMap"];
    let media = &article["media_entities"];
    let mut body = String::new();
    let mut list: Option<&str> = None;
    let blocks = article["content"]["blocks"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let skip = usize::from(blocks.first().is_some_and(is_title_tail));
    for block in &blocks[skip..] {
        let kind = block["type"].as_str().unwrap_or("unstyled");
        let item = match kind {
            "unordered-list-item" => Some("ul"),
            "ordered-list-item" => Some("ol"),
            _ => None,
        };
        if let Some(open) = list.filter(|open| Some(*open) != item) {
            let _ = write!(body, "</{open}>");
            list = None;
        }
        if let Some(tag) = item {
            if list.is_none() {
                let _ = write!(body, "<{tag}>");
                list = Some(tag);
            }
            let _ = write!(body, "<li>{}</li>", inline(block, entities, true));
            continue;
        }
        let (tag, styled) = match kind {
            "atomic" => {
                body += &atomic(block, entities, media);
                continue;
            }
            "header-one" | "header-two" => ("h2", false),
            "header-three" => ("h3", false),
            "blockquote" => ("blockquote", true),
            _ => ("p", true),
        };
        if !block["text"].as_str().unwrap_or("").trim().is_empty() {
            let _ = write!(body, "<{tag}>{}</{tag}>", inline(block, entities, styled));
        }
    }
    if let Some(open) = list {
        let _ = write!(body, "</{open}>");
    }
    let title = escape(article["title"].as_str().unwrap_or(""));
    let author = escape(tweet["author"]["name"].as_str().unwrap_or(""));
    let published = article["created_at"].as_str().unwrap_or("");
    format!(
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>{title}</title>\
         <meta name=\"author\" content=\"{author}\">\
         <meta property=\"article:published_time\" content=\"{published}\"></head>\
         <body><article><h1>{title}</h1><p>By {author}</p>{body}</article></body></html>"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn article_blocks_become_html_without_cover_or_styled_headings() {
        let tweet = serde_json::json!({
            "author": {"name": "Ada"},
            "article": {
                "title": "On Things",
                "created_at": "2026-10-25T00:00:00.000Z",
                "cover_media": {"media_info": {"original_img_url": "https://x/cover.jpg"}},
                "media_entities": [{"media_id": "9", "media_info": {"original_img_url": "https://x/fig.png"}}],
                "content": {
                    "entityMap": [
                        {"key": "0", "value": {"type": "LINK", "data": {"url": "https://a.b"}}},
                        {"key": "1", "value": {"type": "MEDIA", "data": {"caption": "Fig", "mediaItems": [{"mediaId": "9"}]}}}
                    ],
                    "blocks": [
                        {"type": "unstyled", "text": "... as of October 2026.", "entityRanges": [], "inlineStyleRanges": []},
                        {"type": "header-two", "text": "Head", "entityRanges": [], "inlineStyleRanges": [{"offset": 0, "length": 4, "style": "Bold"}]},
                        {"type": "unstyled", "text": "See this.", "entityRanges": [{"key": 0, "offset": 4, "length": 4}], "inlineStyleRanges": []},
                        {"type": "unordered-list-item", "text": "one", "entityRanges": [], "inlineStyleRanges": []},
                        {"type": "atomic", "text": " ", "entityRanges": [{"key": 1, "offset": 0, "length": 1}], "inlineStyleRanges": []}
                    ]
                }
            }
        });
        let html = article_html(&tweet);
        assert!(!html.contains("cover.jpg"));
        assert!(!html.contains("October 2026"));
        assert!(html.contains("<h2>Head</h2>"));
        assert!(html.contains("See <a href=\"https://a.b\">this</a>."));
        assert!(html.contains("<ul><li>one</li></ul>"));
        assert!(html.contains("src=\"https://x/fig.png\""));
    }
}
