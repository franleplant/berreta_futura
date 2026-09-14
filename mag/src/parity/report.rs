use anyhow::{ensure, Context, Result};
use serde_json::Value;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const PREVIEW_DPI: u32 = 54;
const LINE_ROW_CAP: usize = 200;

pub fn write(
    out_dir: &Path,
    verdict: &Value,
    pdfs: Option<(&Path, &Path)>,
    domain: Option<(u32, u32)>,
    g2: f64,
) -> Result<PathBuf> {
    let assets = out_dir.join("report");
    fs::create_dir_all(&assets)?;
    let mut html = String::from(
        "<!doctype html><meta charset=\"utf-8\"><title>mag parity report</title><style>\
         body{font-family:system-ui;margin:2rem}table{border-collapse:collapse}\
         td,th{border:1px solid #999;padding:2px 8px;font-size:13px;text-align:left}\
         .pass{color:#2a7}.fail{color:#c22}img{border:1px solid #ccc;max-width:320px}\
         .page{display:flex;gap:8px;margin:12px 0;align-items:flex-start}</style>",
    );
    write!(html, "<h1>mag parity report</h1>{}", summary_table(verdict))?;
    push_clause_tables(&mut html, verdict)?;
    if let (Some((pdf_a, pdf_b)), Some((first, last))) = (pdfs, domain) {
        push_line_table(&mut html, pdf_a, pdf_b, first, last, g2)?;
        render_previews(pdf_a, first, last, &assets, "a")?;
        render_previews(pdf_b, first, last, &assets, "b")?;
        push_gallery(&mut html, verdict, first, last, &assets)?;
    }
    let path = out_dir.join("report.html");
    fs::write(&path, html).with_context(|| format!("writing {}", path.display()))?;
    Ok(path)
}

fn esc(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn status_cell(v: &Value, path: &[&str]) -> String {
    let mut node = v;
    for key in path {
        node = &node[*key];
    }
    let status = node["status"].as_str().unwrap_or("null");
    format!("<td class=\"{status}\">{status}</td>")
}

fn summary_table(v: &Value) -> String {
    let rows: [(&str, &[&str]); 10] = [
        ("S page_count", &["tier_s", "page_count"]),
        ("S boxes", &["tier_s", "boxes"]),
        ("S text", &["tier_s", "text"]),
        ("S code_blocks", &["tier_s", "code_blocks"]),
        ("S color", &["tier_s", "color"]),
        ("S navigation", &["tier_s", "navigation"]),
        ("S critic", &["tier_s", "critic"]),
        ("V raster meters", &["tier_v"]),
        ("E display_list", &["tier_e", "display_list"]),
        ("E raster", &["tier_e", "raster"]),
    ];
    let body: String = rows
        .iter()
        .map(|(name, path)| format!("<tr><td>{name}</td>{}</tr>", status_cell(v, path)))
        .collect();
    let (v1, v2) = (v["tier_v"]["v1"].as_str(), v["tier_v"]["v2"].as_str());
    let meters = match (v1, v2) {
        (Some(v1), Some(v2)) => format!(
            "<p>V1 {v1}, V2 {v2}, worst page fraction {}, max channel delta {}</p>",
            v["tier_v"]["worst_page_fraction"], v["tier_v"]["max_channel_delta"]
        ),
        _ => String::new(),
    };
    format!("<table>{body}</table>{meters}")
}

fn push_clause_tables(html: &mut String, v: &Value) -> Result<()> {
    let diffs = v["tier_e"]["display_list"]["pages_differing"]
        .as_array()
        .filter(|d| !d.is_empty());
    if let Some(diffs) = diffs {
        write!(
            html,
            "<h2>display list diffs</h2><table><tr><th>page</th><th>detail</th></tr>"
        )?;
        for d in diffs {
            write!(
                html,
                "<tr><td>{}</td><td>{}</td></tr>",
                d["page"],
                esc(d["detail"].as_str().unwrap_or(""))
            )?;
        }
        html.push_str("</table>");
    }
    let mismatches = v["tier_s"]["boxes"]["mismatches"]
        .as_array()
        .filter(|m| !m.is_empty());
    if let Some(mismatches) = mismatches {
        write!(
            html,
            "<h2>box mismatches</h2><table><tr><th>page</th><th>box</th><th>a</th><th>b</th></tr>"
        )?;
        for m in mismatches {
            write!(
                html,
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
                m["page"],
                m["name"].as_str().unwrap_or(""),
                m["a"],
                m["b"]
            )?;
        }
        html.push_str("</table>");
    }
    for (title, path) in [
        (
            "text pages differing",
            ["tier_s", "text", "pages_differing"],
        ),
        (
            "color pages differing",
            ["tier_s", "color", "pages_differing"],
        ),
        (
            "navigation mismatches",
            ["tier_s", "navigation", "mismatches"],
        ),
    ] {
        let node = &v[path[0]][path[1]][path[2]];
        if let Some(items) = node.as_array().filter(|i| !i.is_empty()) {
            let list: Vec<String> = items.iter().map(|i| esc(&i.to_string())).collect();
            write!(html, "<h2>{title}</h2><p>{}</p>", list.join(", "))?;
        }
    }
    Ok(())
}

struct Line {
    y: f64,
    x: f64,
    text: String,
}

fn push_line_table(
    html: &mut String,
    pdf_a: &Path,
    pdf_b: &Path,
    first: u32,
    last: u32,
    g2: f64,
) -> Result<()> {
    let (a, b) = (lines(pdf_a, first, last)?, lines(pdf_b, first, last)?);
    let mut rows = String::new();
    let mut count = 0;
    for (page, (la, lb)) in a.iter().zip(&b).enumerate() {
        for (i, (line_a, line_b)) in la.iter().zip(lb).enumerate() {
            let (dx, dy) = (line_b.x - line_a.x, line_b.y - line_a.y);
            if (dx.abs() > g2 || dy.abs() > g2) && count < LINE_ROW_CAP {
                count += 1;
                write!(
                    rows,
                    "<tr><td>{}</td><td>{i}</td><td>{dx:.2}</td><td>{dy:.2}</td><td>{}</td></tr>",
                    first + page as u32,
                    esc(&line_a.text)
                )?;
            }
        }
        if la.len() != lb.len() && count < LINE_ROW_CAP {
            count += 1;
            write!(
                rows,
                "<tr><td>{}</td><td colspan=\"4\">line count {} vs {}</td></tr>",
                first + page as u32,
                la.len(),
                lb.len()
            )?;
        }
    }
    if !rows.is_empty() {
        write!(
            html,
            "<h2>lines beyond G2 ({g2} pt, first {LINE_ROW_CAP})</h2>\
             <table><tr><th>page</th><th>line</th><th>dx</th><th>dy</th><th>text</th></tr>{rows}</table>"
        )?;
    }
    Ok(())
}

fn lines(pdf: &Path, first: u32, last: u32) -> Result<Vec<Vec<Line>>> {
    let out = Command::new("pdftotext")
        .args([
            "-bbox-layout",
            "-f",
            &first.to_string(),
            "-l",
            &last.to_string(),
        ])
        .arg(pdf)
        .arg("-")
        .output()
        .context("running pdftotext -bbox-layout")?;
    ensure!(
        out.status.success(),
        "pdftotext failed on {}",
        pdf.display()
    );
    let xml = String::from_utf8_lossy(&out.stdout);
    let mut pages = vec![];
    let mut words = vec![];
    let mut line: Option<Line> = None;
    for raw in xml.lines() {
        let tag = raw.trim_start();
        if tag.starts_with("<page ") {
            pages.push(vec![]);
        } else if tag.starts_with("<line ") {
            line = Some(Line {
                y: attr(tag, "yMin")?,
                x: attr(tag, "xMin")?,
                text: String::new(),
            });
            words.clear();
        } else if tag.starts_with("<word ") {
            if let Some(text) = tag.split('>').nth(1).and_then(|t| t.split('<').next()) {
                words.push(text.to_string());
            }
        } else if tag.starts_with("</line>") {
            if let (Some(mut l), Some(page)) = (line.take(), pages.last_mut()) {
                l.text = words.join(" ");
                page.push(l);
            }
        }
    }
    Ok(pages)
}

fn attr(tag: &str, name: &str) -> Result<f64> {
    let rest = tag
        .split(&format!("{name}=\""))
        .nth(1)
        .with_context(|| format!("bbox line tag missing {name}"))?;
    Ok(rest.split('"').next().unwrap_or_default().parse()?)
}

fn render_previews(pdf: &Path, first: u32, last: u32, assets: &Path, tag: &str) -> Result<()> {
    let status = Command::new("pdftoppm")
        .args(["-png", "-r", &PREVIEW_DPI.to_string()])
        .args(["-f", &first.to_string(), "-l", &last.to_string()])
        .arg(pdf)
        .arg(assets.join(tag))
        .status()
        .context("running pdftoppm -png")?;
    ensure!(
        status.success(),
        "pdftoppm -png failed on {}",
        pdf.display()
    );
    Ok(())
}

fn push_gallery(
    html: &mut String,
    verdict: &Value,
    first: u32,
    last: u32,
    assets: &Path,
) -> Result<()> {
    let digits = (last + 1).to_string().len();
    html.push_str("<h2>pages (A, B, diff heatmap)</h2>");
    for page in first..=last {
        let frac = &verdict["tier_v"]["pages"][page.to_string()]["differing_fraction"];
        write!(
            html,
            "<h3>page {page} (differing fraction {frac})</h3><div class=\"page\">"
        )?;
        for tag in ["a", "b"] {
            write!(
                html,
                "<img src=\"report/{tag}-{page:0digits$}.png\" alt=\"{tag} {page}\">"
            )?;
        }
        if assets.join(format!("heatmap-{page:03}.bmp")).exists() {
            write!(
                html,
                "<img src=\"report/heatmap-{page:03}.bmp\" alt=\"heatmap {page}\">"
            )?;
        }
        html.push_str("</div>");
    }
    Ok(())
}
