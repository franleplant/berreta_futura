pub struct Tag<'a> {
    pub name: &'a str,
    pub attrs: Vec<(&'a str, &'a str)>,
}

impl<'a> Tag<'a> {
    pub fn attr(&self, name: &str) -> Option<&'a str> {
        self.attrs
            .iter()
            .find(|(key, _)| *key == name)
            .map(|(_, value)| *value)
    }

    pub fn has_class(&self, class: &str) -> bool {
        self.attr("class")
            .is_some_and(|value| value.split_whitespace().any(|item| item == class))
    }
}

pub fn indent_of(line: &str) -> &str {
    &line[..line.len() - line.trim_start().len()]
}

pub fn first_tag(line: &str) -> Option<Tag<'_>> {
    let rest = line.trim_start();
    let rest = rest.strip_prefix('<')?;
    let name_end = rest.find(|c: char| c.is_whitespace() || c == '>' || c == '/')?;
    let name = &rest[..name_end];
    if name.is_empty() || !name.chars().all(|c| c.is_ascii_alphanumeric()) {
        return None;
    }
    let mut attrs = Vec::new();
    let mut cursor = &rest[name_end..];
    loop {
        cursor = cursor.trim_start();
        if cursor.is_empty() || cursor.starts_with('>') || cursor.starts_with("/>") {
            break;
        }
        let key_end = match cursor.find(['=', '>', ' ']) {
            Some(index) => index,
            None => break,
        };
        let key = &cursor[..key_end];
        cursor = &cursor[key_end..];
        if !cursor.starts_with('=') {
            if !key.is_empty() {
                attrs.push((key, ""));
            }
            continue;
        }
        cursor = &cursor[1..];
        let quote = match cursor.chars().next() {
            Some(c @ ('"' | '\'')) => c,
            _ => break,
        };
        cursor = &cursor[1..];
        let value_end = match cursor.find(quote) {
            Some(index) => index,
            None => break,
        };
        attrs.push((key, &cursor[..value_end]));
        cursor = &cursor[value_end + 1..];
    }
    Some(Tag { name, attrs })
}

pub fn is_print_only(line: &str) -> bool {
    let Some(tag) = first_tag(line) else {
        return false;
    };
    match tag.name {
        "figure" => tag.has_class("article-tail") || tag.has_class("closing-plate"),
        "a" => tag.has_class("source-link") && !tag.has_class("opener-source-link"),
        _ => false,
    }
}

pub struct SourceLink<'a> {
    pub indent: &'a str,
    pub source_id: &'a str,
    pub href: &'a str,
}

pub fn source_link(line: &str) -> Option<SourceLink<'_>> {
    let tag = first_tag(line)?;
    if tag.name != "a" || !tag.has_class("source-link") || tag.has_class("opener-source-link") {
        return None;
    }
    if tag.attr("data-source-link") != Some("primary") {
        return None;
    }
    Some(SourceLink {
        indent: indent_of(line),
        source_id: tag.attr("data-source-id")?,
        href: tag.attr("href")?,
    })
}

pub struct PieceOpening<'a> {
    pub kind: &'a str,
    pub id: &'a str,
}

pub fn piece_opening(line: &str) -> Option<PieceOpening<'_>> {
    let tag = first_tag(line)?;
    if tag.name != "article" && tag.name != "section" {
        return None;
    }
    Some(PieceOpening {
        kind: tag.name,
        id: tag.attr("id")?,
    })
}

pub fn is_illustrated_opener_header(line: &str) -> bool {
    first_tag(line).is_some_and(|tag| tag.name == "header" && tag.has_class("article-opener"))
}
