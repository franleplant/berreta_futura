#[allow(dead_code)]
mod oracle;

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

const TARGETS: [&str; 2] = ["mag/src", "tools"];
const COMPOUND: [&str; 14] = [
    "if", "elif", "else", "for", "while", "with", "try", "except", "finally", "def", "class",
    "async", "match", "case",
];
const PREFIXES: [&str; 9] = ["r", "u", "b", "f", "br", "rb", "fr", "rf", ""];

type Toks = [(usize, Tok)];

#[derive(Clone, PartialEq)]
enum Tok {
    Str(bool),
    Word(String),
    Op(char),
}

struct Logical {
    col: usize,
    toks: Vec<(usize, Tok)>,
}

fn column(line: &[char]) -> usize {
    line.iter().fold(
        0,
        |col, c| if *c == '\t' { col / 8 * 8 + 8 } else { col + 1 },
    )
}

fn string_end(src: &[char], start: usize) -> usize {
    let quote = src[start];
    let triple = src.get(start..start + 3) == Some(&[quote; 3][..]);
    let mut j = start + if triple { 3 } else { 1 };
    while j < src.len() {
        if src[j] == '\\' {
            j += 2;
        } else if triple && src.get(j..j + 3) == Some(&[quote; 3][..]) {
            return j + 3;
        } else if !triple && src[j] == quote {
            return j + 1;
        } else {
            j += 1;
        }
    }
    src.len()
}

fn python_tokens(src: &[char]) -> (Vec<(usize, String)>, Vec<Logical>) {
    let (mut comments, mut lines) = (Vec::new(), Vec::new());
    let (mut i, mut line, mut start, mut depth) = (0, 1, 0, 0usize);
    let mut cur = Logical {
        col: 0,
        toks: Vec::new(),
    };
    while i < src.len() {
        let c = src[i];
        let push = |tok: Tok, line: usize, at: usize, start: usize, cur: &mut Logical| {
            if cur.toks.is_empty() {
                cur.col = column(&src[start..at]);
            }
            cur.toks.push((line, tok));
        };
        if c == '\n' {
            (line, start, i) = (line + 1, i + 1, i + 1);
            if depth == 0 && !cur.toks.is_empty() {
                let next = Logical {
                    col: 0,
                    toks: Vec::new(),
                };
                lines.push(std::mem::replace(&mut cur, next));
            }
        } else if c == '\\' && src.get(i + 1) == Some(&'\n') {
            (line, start, i) = (line + 1, i + 2, i + 2);
        } else if c == '#' {
            let end = src[i..]
                .iter()
                .position(|c| *c == '\n')
                .map_or(src.len(), |n| i + n);
            comments.push((line, src[i..end].iter().collect()));
            i = end;
        } else if c.is_whitespace() {
            i += 1;
        } else if c.is_alphanumeric() || c == '_' || c == '"' || c == '\'' {
            let mut j = i;
            while j < src.len() && (src[j].is_alphanumeric() || src[j] == '_') {
                j += 1;
            }
            let word: String = src[i..j].iter().collect();
            let prefix = word.to_lowercase();
            if matches!(src.get(j), Some('"' | '\'')) && PREFIXES.contains(&prefix.as_str()) {
                let end = string_end(src, j);
                let plain = !prefix.contains(['f', 'b']);
                push(Tok::Str(plain), line, i, start, &mut cur);
                for (k, _) in src
                    .iter()
                    .enumerate()
                    .take(end)
                    .skip(j)
                    .filter(|(_, c)| **c == '\n')
                {
                    (line, start) = (line + 1, k + 1);
                }
                i = end;
            } else {
                push(Tok::Word(word), line, i, start, &mut cur);
                i = j;
            }
        } else {
            depth = match c {
                '(' | '[' | '{' => depth + 1,
                ')' | ']' | '}' => depth.saturating_sub(1),
                _ => depth,
            };
            let walrus = c == ':' && src.get(i + 1) == Some(&'=');
            push(
                Tok::Op(if walrus { '=' } else { c }),
                line,
                i,
                start,
                &mut cur,
            );
            i += if walrus { 2 } else { 1 };
        }
    }
    if !cur.toks.is_empty() {
        lines.push(cur);
    }
    (comments, lines)
}

fn split_at_depth_zero(toks: &Toks, sep: char, once: bool) -> Vec<&Toks> {
    let (mut depth, mut from, mut parts) = (0usize, 0, Vec::new());
    for (k, (_, tok)) in toks.iter().enumerate() {
        if depth == 0 && *tok == Tok::Op(sep) && (!once || parts.is_empty()) {
            parts.push(&toks[from..k]);
            from = k + 1;
        }
        match tok {
            Tok::Op('(' | '[' | '{') => depth += 1,
            Tok::Op(')' | ']' | '}') => depth = depth.saturating_sub(1),
            _ => {}
        }
    }
    parts.push(&toks[from..]);
    parts
}

fn is_docstring(stmt: &Toks) -> bool {
    let mut s = stmt;
    while s.len() >= 2 && s[0].1 == Tok::Op('(') && s[s.len() - 1].1 == Tok::Op(')') {
        s = &s[1..s.len() - 1];
    }
    !s.is_empty() && s.iter().all(|(_, t)| *t == Tok::Str(true))
}

fn header(toks: &Toks) -> Option<(&str, &Toks)> {
    let Tok::Word(word) = &toks[0].1 else {
        return None;
    };
    let parts = split_at_depth_zero(toks, ':', true);
    (COMPOUND.contains(&word.as_str()) && parts.len() == 2).then(|| (word.as_str(), parts[1]))
}

fn python_offenses(src: &str) -> Vec<(usize, &'static str)> {
    let chars: Vec<char> = src.chars().collect();
    let (comments, lines) = python_tokens(&chars);
    let pragma = regex::Regex::new(r"#\s*(pragma|noqa|type:|fmt:)").unwrap();
    let mut out: Vec<(usize, &str)> = comments
        .iter()
        .filter(|(l, t)| !(pragma.is_match(t) || *l == 1 && t.starts_with("#!")))
        .map(|(l, _)| (*l, "comment"))
        .collect();
    let (mut docs, mut stack) = (Vec::new(), Vec::<(usize, usize, bool)>::new());
    let (mut last_at, mut first) = (BTreeMap::new(), true);
    for logical in &lines {
        let col = logical.col;
        while stack.last().is_some_and(|b| b.0 >= col) {
            stack.pop();
        }
        last_at.retain(|at, _| *at <= col);
        let (owner, flagged) = stack.last().map_or((0, true), |b| (b.1, b.2));
        let (body, context) = match header(&logical.toks) {
            None => (&logical.toks[..], (owner, flagged)),
            Some((word, rest)) => {
                let sibling = last_at.get(&col).copied().unwrap_or(owner + 1);
                let context = match word {
                    "elif" | "except" => (sibling + 1, true),
                    "else" | "finally" => (sibling, false),
                    _ => (owner + 1, true),
                };
                if !matches!(word, "except" | "else" | "finally") {
                    last_at.insert(col, context.0);
                }
                if rest.is_empty() {
                    stack.push((col, context.0, context.1));
                }
                first = false;
                (rest, context)
            }
        };
        for stmt in split_at_depth_zero(body, ';', false) {
            if stmt.is_empty() {
                continue;
            }
            let exempt = first && src.contains("__doc__");
            if context.1 && is_docstring(stmt) && !exempt {
                docs.push((context.0, stmt[0].0));
            }
            first = false;
        }
    }
    docs.sort();
    out.extend(docs.into_iter().map(|(_, line)| (line, "docstring")));
    out
}

fn rust_offenses(text: &str) -> Vec<(usize, &'static str)> {
    let src: Vec<char> = text.chars().collect();
    let help = text.contains("#[derive(Parser") || text.contains("#[derive(Subcommand");
    let at = |i: usize, s: &str| src[i..].iter().take(s.len()).copied().eq(s.chars());
    let find = |s: &str, from: usize| (from..src.len()).find(|&k| at(k, s));
    let count = |from: usize, to: usize| {
        src[from..to.min(src.len())]
            .iter()
            .filter(|c| **c == '\n')
            .count()
    };
    let (mut out, mut i, n, mut line) = (Vec::new(), 0, src.len(), 1);
    while i < n {
        let c = src[i];
        if c == '\n' {
            line += 1;
        } else if at(i, "//") || at(i, "/*") {
            if !(help && at(i, "///")) {
                out.push((line, "comment"));
            }
            i = find(if src[i + 1] == '/' { "\n" } else { "*/" }, i).unwrap_or(n);
            continue;
        } else if c == 'r'
            && i + 1 < n
            && matches!(src[i + 1], '"' | '#')
            && !(i > 0 && (src[i - 1].is_alphanumeric() || src[i - 1] == '_'))
        {
            let mut j = i + 1;
            while j < n && src[j] == '#' {
                j += 1;
            }
            if j < n && src[j] == '"' {
                let close = format!("\"{}", "#".repeat(j - i - 1));
                let k = find(&close, j + 1).map_or(n, |k| k + close.len());
                line += count(i, k);
                i = k;
                continue;
            }
        } else if c == '"' {
            let mut j = i + 1;
            while j < n && src[j] != '"' {
                j += if src[j] == '\\' { 2 } else { 1 };
            }
            line += count(i, j);
            i = j + 1;
            continue;
        } else if c == '\'' && i + 2 < n && (src[i + 1] == '\\' || src[i + 2] == '\'') {
            let from = if src[i + 1] == '\\' { i + 2 } else { i + 1 };
            i = (from..n).find(|&k| src[k] == '\'').map_or(n, |k| k + 1);
            continue;
        }
        i += 1;
    }
    out
}

fn shell_offenses(text: &str) -> Vec<(usize, &'static str)> {
    let lines = text.split('\n').enumerate().map(|(k, l)| (k + 1, l));
    lines
        .filter(|(no, l)| l.trim_start().starts_with('#') && !(*no == 1 && l.starts_with("#!")))
        .map(|(no, _)| (no, "comment"))
        .collect()
}

fn suffix(name: &str) -> &str {
    match name.rfind('.') {
        Some(i) if i > 0 && i < name.len() - 1 => &name[i..],
        _ => "",
    }
}

fn walk(dir: &Path, into: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries {
        let path = entry.expect("an entry").path();
        if path.is_dir() {
            walk(&path, into);
        }
        into.push(path);
    }
}

fn offenses(path: &Path) -> Vec<(usize, &'static str)> {
    let name = path.file_name().unwrap().to_string_lossy();
    let bytes = std::fs::read(path).expect("the file reads");
    let text = || {
        let text = String::from_utf8(bytes.clone()).expect("utf-8");
        text.replace("\r\n", "\n").replace('\r', "\n")
    };
    match suffix(&name) {
        ".py" => python_offenses(&text()),
        ".rs" => rust_offenses(&text()),
        "" if bytes.starts_with(b"#!/bin/sh") => shell_offenses(&text()),
        _ => Vec::new(),
    }
}

fn scan(root: &Path, targets: &[&str]) -> String {
    let mut found = Vec::new();
    for target in targets {
        let mut paths = Vec::new();
        walk(&root.join(target), &mut paths);
        paths.sort();
        for path in paths {
            if !path.is_file() || path.file_name().is_some_and(|n| n == "nocomments.py") {
                continue;
            }
            let rel = path
                .strip_prefix(root)
                .unwrap()
                .to_string_lossy()
                .into_owned();
            let rows = offenses(&path).into_iter();
            found.extend(rows.map(|(line, kind)| format!("{rel}:{line}: {kind}")));
        }
    }
    if found.is_empty() {
        "no comments".into()
    } else {
        found.join("\n")
    }
}

fn repo() -> PathBuf {
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/.."))
}

fn stage_cases() -> PathBuf {
    let root = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join("nocomments-cases");
    if root.exists() {
        std::fs::remove_dir_all(&root).expect("the old stage is removable");
    }
    let cases = std::fs::read_to_string(repo().join("mag/tests/nocomments_cases.txt")).unwrap();
    for case in cases.split("\n=== ").skip(1) {
        let (head, body) = case.split_once('\n').expect("a case has a header line");
        let (name, crlf) = head
            .strip_prefix("crlf ")
            .map_or((head, false), |n| (n, true));
        let path = root.join(name);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        let body = format!("{body}\n");
        let body = if crlf {
            body.replace('\n', "\r\n")
        } else {
            body
        };
        std::fs::write(&path, body).unwrap();
    }
    root
}

#[test]
fn no_comments_in_codebase() {
    let found = scan(&repo(), &TARGETS);
    assert_eq!(found, "no comments");
}

#[test]
fn crafted_cases_flag_what_the_script_flags() {
    let root = stage_cases();
    let want = oracle::expectation("nocomments_cases_expected.txt");
    assert_eq!(scan(&root, &TARGETS) + "\n", want);
}
