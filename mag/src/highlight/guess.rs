use regex::Regex;
use std::sync::LazyLock;
use std::sync::OnceLock;

static JSON_LINE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"^(//.*|"[^"]*"\s*:.*|[\[\]{},]+|"[^"]*",?|[-\d.eE+]+,?|(true|false|null),?|\{\s*".*\}),?$"#).unwrap()
});
static HTTP_LINE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^(HTTP/[\d.]+ \d{3}\b|(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \S+ HTTP/[\d.]+$)")
        .unwrap()
});
static BIBTEX_ENTRY: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^@\w+\{").unwrap());

type Signatures = &'static [(&'static str, i32)];
type Compiled = Vec<(&'static str, Vec<(Regex, i32)>)>;

const SCRIPT: Signatures = &[
    (r#"^import\b.*\bfrom\s+['"]"#, 5),
    (r#"^import\s+(\{|\*|['"])"#, 4),
    (r"^(export\s+)?(const|let|var)\s+[\w{\[]", 3),
    (r"^export\s+(default|class|function|async|const|let|\{)", 4),
    (r"^(export\s+)?(default\s+)?(async\s+)?function\b", 3),
    (r"=>", 2),
    (r"\bawait\b", 1),
    (r"\bthis\.", 2),
    (r"===|!==", 3),
    (r"\?\.\w|\s\?\?\s", 2),
    (r"\bconsole\.\w+\(", 3),
    (r"^\}\)+;?$", 1),
    (r"\brequire\(['\x22]", 3),
    (r"^(async\s+)?[a-z]\w*\([\w, {}]*\)\s*\{$", 2),
    (r"\bnew\s+[A-Z]\w*\(", 1),
    (r"\w\(\{$", 2),
    (r";$", 1),
];

const TYPED: Signatures = &[
    (r"^(export\s+)?(declare\s+)?(interface|type)\s+[A-Z]\w*", 4),
    (r":\s*(string|number|boolean|void|unknown|any|never)\b", 3),
    (r":\s*(Promise|Record|Array|Map|Set|Partial|Readonly)<", 3),
    (r"\)\s*:\s*[\w<>\[\]|, ]+\s*(\{|=>)\s*$", 3),
    (r"\bas\s+(const|string|number|unknown|any)\b", 2),
    (r"\b(implements|readonly|private|protected|public)\s", 2),
    (r"\bsatisfies\b", 3),
    (r"^(const|let|var)\s+\w+\s*:\s*[A-Z]\w*", 3),
];

const LANGUAGES: &[(&str, Signatures)] = &[
    ("js", SCRIPT),
    (
        "python",
        &[
            (r"^(async\s+)?def\s+\w+\(.*\)(\s*->\s*.+)?:$", 5),
            (r"^class\s+\w+(\(.*\))?:$", 5),
            (r"^from\s+[\w.]+\s+import\s", 5),
            (r"^import\s+[\w.]+(\s+as\s+\w+)?(,\s*[\w.]+)*$", 3),
            (
                r"^(if|elif|while|for|with|try|except|else|finally)\b.*:$",
                3,
            ),
            (r"\bself\.\w", 2),
            (r"\b(None|True|False)\b", 1),
            (r"^print\(", 2),
            (r"\bf['\x22]", 1),
        ],
    ),
    (
        "rust",
        &[
            (
                r"^pub(\(\w+\))?\s+(async\s+)?(fn|struct|enum|impl|trait|mod|const|type|use)\s",
                5,
            ),
            (r"^(async\s+)?(fn|impl|trait|mod)\s", 4),
            (r"^use\s+[\w:]+(::\{.*\})?;$", 5),
            (r"\blet\s+mut\b", 4),
            (r"::", 1),
            (r"&(mut\s|self\b|str\b|'\w)", 3),
            (r"->", 1),
            (
                r"\b(Vec|Option|Result|Arc|Box|HashMap|Mutex|RwLock|DashMap)<",
                3,
            ),
            (r"\b[a-z_]+!\(", 2),
            (r"^#\[", 4),
            (r"\.unwrap\(\)|\?;$", 2),
        ],
    ),
    (
        "go",
        &[
            (r"^package\s+\w+$", 6),
            (r"^func\s", 4),
            (r":=", 3),
            (r"^import\s+\($", 4),
            (r"\bfmt\.\w", 3),
            (r"\berr\s*!=\s*nil\b", 4),
            (r"^(go|defer)\s", 2),
        ],
    ),
    (
        "sh",
        &[
            (
                r"^(sudo\s+)?(npm|npx|pnpm|yarn|bun|bunx|pip3?|uv|uvx|cargo|rustup|git|curl|wget|cd|ls|mkdir|rm|cp|mv|echo|brew|apt|apt-get|docker|kubectl|wrangler|make|python3?|node|deno|chmod|cat|grep|sed|tar|ssh|source|just|gh|helm|terraform|celld)(\s|$)",
                4,
            ),
            (r"^go\s+(run|build|test|get|install|mod)\s", 4),
            (r"^export\s+[A-Za-z_]\w*=", 4),
            (r"^\$\s", 2),
            (
                r"\|\s*(sh|bash|zsh|grep|sed|awk|xargs|tee|jq|head|tail)\b",
                3,
            ),
            (r"&&", 1),
            (r"\s--?[a-zA-Z][\w-]*", 1),
            (r"\\$", 2),
            (r#""\$\{?[A-Za-z_]"#, 2),
            (r"^#!/", 5),
            (r"^[A-Z_][A-Z0-9_]*=\S", 3),
            (r"^\.\s+\S", 2),
        ],
    ),
    (
        "yaml",
        &[
            (r"^[\w.-]+:$", 2),
            (r#"^[\w.-]+:\s+[\w"'./${}-]+$"#, 1),
            (r"^-\s+[\w.-]+:\s", 3),
            (r"^---$", 2),
        ],
    ),
    (
        "toml",
        &[
            (r#"^\[[\w.\-"]+\]$"#, 4),
            (r"^\[\[[\w.\-]+\]\]$", 5),
            (
                r#"^[\w.\-"$]+\s*=\s*(".*"|'.*'|[\d_.]+|true|false|\[.*|\{.*)$"#,
                2,
            ),
        ],
    ),
    (
        "sql",
        &[
            (
                r"^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH|COPY|INSTALL|LOAD)\b",
                3,
            ),
            (r"(?i)^select\b.*\bfrom\b", 3),
            (
                r"\b(FROM|WHERE|JOIN|GROUP BY|ORDER BY|VALUES|LIMIT|INTO|TABLE|NOT NULL|PRIMARY KEY)\b",
                2,
            ),
        ],
    ),
    (
        "html",
        &[
            (
                r"(?i)^<(!doctype|html|head|body|div|span|p|a|script|style|meta|link|ul|ol|li|section|article|header|footer|nav|main|button|form|input|img|table|tr|td|h[1-6])\b",
                3,
            ),
            (r"</[a-z][\w-]*>", 1),
        ],
    ),
    (
        "css",
        &[
            (r"^[.#@:]?[\w\-\[\]=\x22:., >+~*]+\{$", 1),
            (
                r"^(color|background(-\w+)?|margin(-\w+)?|padding(-\w+)?|display|font(-\w+)?|(max-|min-)?(width|height)|border(-\w+)?|position|flex(-\w+)?|grid(-\w+)?|top|left|right|bottom|z-index|opacity|transition|transform|align-items|justify-content|gap|line-height|text-\w+|overflow|cursor|box-shadow|content)\s*:\s*[^;]+;$",
                3,
            ),
            (r"^@(media|import|keyframes|font-face|supports)\b", 4),
            (r"^--[\w-]+\s*:", 3),
            (r"\b\d+(px|rem|em|vh|vw)\b", 1),
        ],
    ),
    (
        "dockerfile",
        &[(
            r"^(FROM\s+([\w.-]+[:/@][\w./:@-]*|scratch)(\s+AS\s+\w+)?$|(RUN|COPY|ADD|WORKDIR|ENV|EXPOSE|CMD|ENTRYPOINT|ARG|USER|LABEL|VOLUME|HEALTHCHECK)\s)",
            4,
        )],
    ),
    (
        "c",
        &[
            (r#"^#include\s*[<"]"#, 5),
            (r"^#(define|ifn?def|endif|pragma)\b", 4),
            (
                r"\b(int|void|char|unsigned|size_t|uint\d+_t|volatile|struct)\s+\**\w+",
                2,
            ),
            (r"^(static\s+)?(int|void|char|unsigned)\s+\**\w+\(", 3),
            (r"\bprintf\(|\bmalloc\(|\bsizeof\(", 2),
        ],
    ),
    (
        "text",
        &[
            (r"[\x{2500}-\x{257f}]", 5),
            (r"^@\w+\{", 6),
            (r"^[\w-]+(\[\.\][\w-]+)+$", 3),
            (r"^\w+(\s+\w+){0,2}:\s+[A-Z]\w*(\s+\w+)+[.!]$", 3),
            (r"[\x{1f300}-\x{1faff}]", 3),
            (
                r"^[A-Z\x22'(\[]?[\w'\x{2019},\x22()-]+(\s+[\w'\x{2019},.;\x22()-]+){7,}[.?!:]?$",
                3,
            ),
            (r"^\d+\.\s+[A-Z]", 1),
            (r"^\[[A-Z]{3,}( [A-Z]+)*\]$", 3),
        ],
    ),
];

fn compiled() -> &'static Compiled {
    static COMPILED: OnceLock<Compiled> = OnceLock::new();
    COMPILED.get_or_init(|| {
        let build = |list: Signatures| {
            list.iter()
                .map(|(pattern, weight)| (Regex::new(pattern).unwrap(), *weight))
                .collect()
        };
        LANGUAGES
            .iter()
            .map(|(name, list)| (*name, build(list)))
            .chain([("ts", build(TYPED))])
            .collect()
    })
}

fn json(lines: &[&str]) -> bool {
    let body: Vec<&&str> = lines.iter().filter(|l| !l.starts_with("//")).collect();
    body.first().is_some_and(|l| l.starts_with(['{', '[']))
        && body.last().is_some_and(|l| l.ends_with(['}', ']']))
        && lines.iter().any(|l| l.contains("\":"))
        && lines.iter().all(|l| JSON_LINE.is_match(l))
}

fn http(first: &str) -> bool {
    HTTP_LINE.is_match(first)
}

pub fn guess(code: &str) -> Option<&'static str> {
    let lines: Vec<&str> = code
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .collect();
    let first = lines.first()?;
    if BIBTEX_ENTRY.is_match(first) {
        return None;
    }
    if http(first) {
        return Some("http");
    }
    if json(&lines) {
        return Some("json");
    }
    let mut scores: Vec<(&str, (i32, i32))> = compiled()
        .iter()
        .map(|(name, signatures)| {
            let hits = lines.iter().map(|line| {
                signatures
                    .iter()
                    .filter(|(pattern, _)| pattern.is_match(line))
                    .map(|(_, weight)| (*weight, i32::from(*weight > 1) * weight))
                    .fold((0, 0), |a, b| (a.0 + b.0, a.1 + b.1))
            });
            (*name, hits.fold((0, 0), |a, b| (a.0 + b.0, a.1 + b.1)))
        })
        .collect();
    let typed = scores.pop().map_or((0, 0), |(_, score)| score);
    if let Some(script) = scores.iter_mut().find(|(name, _)| *name == "js") {
        script.1 = (script.1 .0 + typed.0, script.1 .1 + typed.1);
        if typed.0 > 0 {
            script.0 = "ts";
        }
    }
    scores.sort_by_key(|(_, (total, _))| -total);
    let ((best, (top, strong)), second) = (scores[0], scores[1].1 .0);
    (best != "text" && strong >= 3 && top >= 2 * second).then_some(best)
}
