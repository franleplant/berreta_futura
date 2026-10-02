#[path = "../src/highlight/guess.rs"]
mod guess;

use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

fn repo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn family(language: &str) -> Option<&str> {
    match language.to_lowercase().as_str() {
        "ts" | "typescript" | "js" | "javascript" | "tsx" | "jsx" => Some("script"),
        "sh" | "bash" | "shell" | "zsh" | "console" => Some("sh"),
        "json" | "jsonc" | "json5" => Some("json"),
        "py" | "python" | "python3" => Some("python"),
        "yml" | "yaml" => Some("yaml"),
        "rs" | "rust" => Some("rust"),
        "txt" | "text" | "plaintext" | "" => None,
        _ => Some("other"),
    }
    .map(|f| match f {
        "other" => language,
        f => f,
    })
}

fn fenced(article: &str) -> Vec<(String, String)> {
    let mut blocks = Vec::new();
    let mut open: Option<(String, String, Vec<&str>)> = None;
    for line in article.lines() {
        let trimmed = line.trim_start();
        let fence: String = trimmed.chars().take_while(|c| *c == '`').collect();
        match open.as_mut() {
            Some((marker, _, body)) if trimmed.trim_end() != marker.as_str() => body.push(line),
            Some(_) => {
                let (_, info, body) = open.take().unwrap();
                blocks.push((info, body.join("\n")));
            }
            None if fence.len() >= 3 => {
                let info = trimmed[fence.len()..].split_whitespace().next();
                open = Some((fence, info.unwrap_or("").to_owned(), Vec::new()));
            }
            None => {}
        }
    }
    blocks
}

fn labeled() -> Vec<(String, String)> {
    let mut seen = BTreeSet::new();
    let mut corpus = Vec::new();
    let mut articles: Vec<PathBuf> = std::fs::read_dir(repo().join("library/sources"))
        .unwrap()
        .map(|entry| entry.unwrap().path().join("article.md"))
        .filter(|path| path.exists())
        .collect();
    articles.sort();
    for path in articles {
        let text = std::fs::read_to_string(path).unwrap();
        for (info, code) in fenced(&text) {
            if !info.is_empty() && seen.insert(code.clone()) {
                corpus.push((info, code));
            }
        }
    }
    corpus
}

#[test]
fn guesses_label_library_blocks_with_at_least_95_percent_precision() {
    let corpus = labeled();
    let mut table: BTreeMap<String, [usize; 3]> = BTreeMap::new();
    let mut wrong = Vec::new();
    for (info, code) in &corpus {
        let truth = family(info);
        let said = guess::guess(code).and_then(family);
        if let Some(truth) = truth {
            table.entry(truth.to_owned()).or_default()[0] += 1;
        }
        if let Some(said) = said {
            let row = table.entry(said.to_owned()).or_default();
            row[1] += 1;
            if truth == Some(said) {
                row[2] += 1;
            } else {
                wrong.push(format!(
                    "{info} guessed {said}: {}",
                    &code[..code.len().min(60)]
                ));
            }
        }
    }
    let labeled: usize = table.values().map(|row| row[1]).sum();
    let right: usize = table.values().map(|row| row[2]).sum();
    eprintln!("{} blocks, {labeled} labeled, {right} right", corpus.len());
    for (language, [truth, said, hit]) in &table {
        eprintln!("{language:8} blocks {truth:3} guessed {said:3} right {hit:3}");
    }
    assert!(corpus.len() >= 90, "the library corpus shrank");
    assert!(
        right * 100 >= labeled * 95,
        "precision under 95%: {wrong:#?}"
    );
    assert!(right * 100 >= corpus.len() * 70, "recall collapsed");
}

#[test]
fn guesses_each_language_from_its_signatures() {
    let cases = [
        (
            "ts",
            "export async function load(env: Env): Promise<Response> {\n  return new Response(\"ok\");\n}",
        ),
        (
            "js",
            "const app = express();\napp.get(\"/\", (req, res) => {\n  res.send(\"hi\");\n});",
        ),
        (
            "python",
            "from pathlib import Path\n\ndef main() -> None:\n    for p in Path(\".\").iterdir():\n        print(p)",
        ),
        (
            "rust",
            "use std::fs;\n\nfn main() {\n    let mut text = fs::read_to_string(\"a\").unwrap();\n    println!(\"{text}\");\n}",
        ),
        (
            "go",
            "package main\n\nimport \"fmt\"\n\nfunc main() {\n\tx := 1\n\tfmt.Println(x)\n}",
        ),
        (
            "sh",
            "curl -fsSL https://example.com/install.sh | sh\nexport PATH=\"$HOME/.local/bin:$PATH\"",
        ),
        ("json", "{\n  \"name\": \"demo\",\n  \"private\": true\n}"),
        (
            "json",
            "// wrangler.jsonc\n{\n  \"main\": \"src/index.ts\", // entry\n  \"vars\": { \"A\": 1 }\n}",
        ),
        (
            "yaml",
            "name: ci\non:\n  push:\n    branches: [main]\njobs:\n  test:\n    runs-on: ubuntu-latest",
        ),
        (
            "toml",
            "[package]\nname = \"mag\"\nversion = \"0.1.0\"\n\n[dependencies]\nregex = \"1\"",
        ),
        (
            "sql",
            "SELECT id, name\nFROM users\nWHERE active = 1\nORDER BY name;",
        ),
        (
            "html",
            "<!doctype html>\n<html>\n<body>\n  <div class=\"a\">hi</div>\n</body>\n</html>",
        ),
        (
            "css",
            ".card {\n  display: flex;\n  padding: 12px;\n  color: #333;\n}",
        ),
        (
            "dockerfile",
            "FROM node:22-slim\nWORKDIR /app\nCOPY . .\nRUN npm ci\nCMD [\"node\", \"index.js\"]",
        ),
        ("http", "HTTP/1.1 402 Payment Required\nContent-Type: application/json"),
    ];
    for (want, code) in cases {
        assert_eq!(guess::guess(code), Some(want), "{code}");
    }
}

#[test]
fn plain_text_output_and_prose_stay_unlabeled() {
    let cases = [
        "Error: Worker exceeded CPU time limit.",
        "I want you to build a first-person shooter at the level of the most recent games.",
        "\u{250c}\u{2500}\u{2500}\u{2510}\n\u{2502} Clients \u{2502}\n\u{2514}\u{2500}\u{2500}\u{2518}",
        "@misc{key2026,\n  title = {A Title},\n  author = {Doe, Jane}\n}",
        "ms365-live[.]com\nteams.ms365-live[.]com\nm365-owa[.]com",
        "",
        "hello",
    ];
    for code in cases {
        assert_eq!(guess::guess(code), None, "{code}");
    }
}
