use anyhow::{bail, Context, Result};
use qrcodegen::{DataTooLong, Mask, QrCode, QrCodeEcc, QrSegment, QrSegmentMode, Version};
use serde_json::{json, Value};
use serde_yaml::Value as Yaml;
use std::path::Path;

const ILLUSTRATED_ROOM: f64 = 41.0;
const PLAIN_ROOM: f64 = 55.5;
const QUIET: usize = 4;
const EPSILON: f64 = 1e-9;
const LEVELS: [(&str, QrCodeEcc); 4] = [
    ("H", QrCodeEcc::High),
    ("Q", QrCodeEcc::Quartile),
    ("M", QrCodeEcc::Medium),
    ("L", QrCodeEcc::Low),
];

pub type Files = Vec<(String, Vec<u8>)>;

pub fn payload(url: &str) -> &str {
    let trimmed = url.trim_matches(|c: char| c.is_whitespace() || ('\x1c'..='\x1f').contains(&c));
    let bare = ["https://", "http://"]
        .iter()
        .find_map(|scheme| trimmed.strip_prefix(scheme))
        .unwrap_or(trimmed);
    bare.strip_prefix("www.").unwrap_or(bare)
}

fn segment(payload: &str) -> Result<(QrSegment, u32, [u8; 3])> {
    if !payload.is_ascii() {
        bail!("source code payload {payload:?} is not ASCII; segno's latin-1/Shift_JIS/UTF-8 fallback is not ported");
    }
    let filled = !payload.is_empty();
    Ok(if filled && QrSegment::is_numeric(payload) {
        (QrSegment::make_numeric(payload), 1, [10, 12, 14])
    } else if filled && QrSegment::is_alphanumeric(payload) {
        (QrSegment::make_alphanumeric(payload), 2, [9, 11, 13])
    } else {
        (QrSegment::make_bytes(payload.as_bytes()), 4, [8, 16, 16])
    })
}

fn capacity_bits(version: Version, ecl: QrCodeEcc) -> usize {
    let oversized = QrSegment::new(QrSegmentMode::Byte, 0, vec![false; 24_000]);
    match QrCode::encode_segments_advanced(&[oversized], ecl, version, version, None, false) {
        Err(DataTooLong::DataOverCapacity(_, bits)) => bits,
        _ => unreachable!("24000 bits exceed every QR capacity"),
    }
}

fn push(bits: &mut Vec<bool>, value: u32, width: u8) {
    bits.extend((0..width).rev().map(|i| (value >> i) & 1 == 1));
}

fn segno_codewords(
    seg: &QrSegment,
    mode: u32,
    counts: [u8; 3],
    version: Version,
    ecl: QrCodeEcc,
) -> Vec<u8> {
    let capacity = capacity_bits(version, ecl);
    let mut bits = Vec::new();
    push(&mut bits, mode, 4);
    push(
        &mut bits,
        seg.num_chars() as u32,
        counts[usize::from((version.value() + 7) / 17)],
    );
    bits.extend_from_slice(seg.data());
    bits.resize(bits.len() + (capacity - bits.len()).min(4), false);
    bits.resize(bits.len() + 8 - bits.len() % 8, false);
    for index in 0..(capacity / 8).saturating_sub(bits.len() / 8) {
        push(&mut bits, [0xEC, 0x11][index % 2], 8);
    }
    let mut words: Vec<u8> = bits
        .chunks(8)
        .map(|byte| byte.iter().fold(0, |acc, &bit| acc << 1 | u8::from(bit)))
        .collect();
    words.truncate(capacity / 8);
    words
}

fn grid(code: &QrCode) -> Vec<Vec<bool>> {
    let size = code.size();
    (0..size)
        .map(|y| (0..size).map(|x| code.get_module(x, y)).collect())
        .collect()
}

fn n3(seq: &[bool]) -> u32 {
    let pattern = [true, false, true, true, true, false, true];
    let size = seq.len();
    let (mut score, mut from) = (0, 0);
    while let Some(found) = (from..(size + 1).saturating_sub(7)).find(|&i| seq[i..i + 7] == pattern)
    {
        let light_before = !seq[found.saturating_sub(4)..found].contains(&true);
        let light_after = !seq[found + 7..(found + 11).min(size)].contains(&true);
        if light_before || light_after {
            score += 40;
            from = found + 7;
        } else {
            from = found + 4;
        }
    }
    score
}

fn n1(seq: &[bool]) -> u32 {
    seq.chunk_by(|a, b| a == b)
        .map(|run| run.len() as u32)
        .filter(|&run| run >= 5)
        .map(|run| run - 2)
        .sum()
}

fn penalty(matrix: &[Vec<bool>]) -> u32 {
    let size = matrix.len();
    let columns: Vec<Vec<bool>> = (0..size)
        .map(|x| matrix.iter().map(|row| row[x]).collect())
        .collect();
    let lines = matrix.iter().chain(&columns);
    let runs: u32 = lines.clone().map(|line| n1(line) + n3(line)).sum();
    let blocks = (1..size)
        .flat_map(|y| (1..size).map(move |x| (y, x)))
        .filter(|&(y, x)| {
            let cell = matrix[y][x];
            matrix[y][x - 1] == cell && matrix[y - 1][x] == cell && matrix[y - 1][x - 1] == cell
        })
        .count() as u32;
    let dark = matrix.iter().flatten().filter(|&&cell| cell).count();
    let percent = dark as f64 / (size * size) as f64;
    runs + 3 * blocks + 10 * ((percent * 100.0 - 50.0).abs() / 5.0) as u32
}

fn unformatted(code: &QrCode) -> Vec<Vec<bool>> {
    let mut matrix = grid(code);
    let size = matrix.len();
    let edge = (0..9).chain(size - 8..size).filter(|&i| i != 6);
    for i in edge {
        matrix[i][8] = false;
        matrix[8][i] = false;
    }
    if code.version().value() >= 7 {
        for (i, j) in (0..6).flat_map(|i| (size - 11..size - 8).map(move |j| (i, j))) {
            matrix[i][j] = false;
            matrix[j][i] = false;
        }
    }
    matrix
}

pub fn codewords(payload: &str, ecl: QrCodeEcc) -> Result<(Version, QrCodeEcc, Vec<u8>)> {
    let (seg, mode, counts) = segment(payload)?;
    let probe = QrCode::encode_segments_advanced(
        std::slice::from_ref(&seg),
        ecl,
        Version::MIN,
        Version::MAX,
        Some(Mask::new(0)),
        true,
    )
    .map_err(|error| anyhow::anyhow!("source code payload {payload:?}: {error}"))?;
    let (version, level) = (probe.version(), probe.error_correction_level());
    Ok((
        version,
        level,
        segno_codewords(&seg, mode, counts, version, level),
    ))
}

pub fn matrix(payload: &str, ecl: QrCodeEcc) -> Result<Vec<Vec<bool>>> {
    let (version, level, words) = codewords(payload, ecl)?;
    let best = (0..8)
        .map(|mask| QrCode::encode_codewords(version, level, &words, Some(Mask::new(mask))))
        .min_by_key(|code| penalty(&unformatted(code)))
        .expect("eight masks");
    Ok(grid(&best))
}

pub fn fitted(payload: &str, room: f64) -> Result<Value> {
    let min_module = 0.35 * 72.0 / 25.4;
    let mut best: Option<(&str, usize, f64, Vec<Vec<bool>>)> = None;
    for (name, ecl) in LEVELS {
        let symbol = matrix(payload, ecl)?;
        let modules = symbol.len() + 2 * QUIET;
        let module = room / modules as f64;
        if module >= min_module && best.as_ref().is_none_or(|kept| module > kept.2 + EPSILON) {
            best = Some((name, modules, module, symbol));
        }
    }
    Ok(best.map_or(Value::Null, |(error, modules, _, symbol)| {
        let rows: Vec<String> = symbol
            .iter()
            .map(|row| {
                row.iter()
                    .map(|&cell| if cell { '1' } else { '0' })
                    .collect()
            })
            .collect();
        json!({"error": error, "modules": modules, "matrix": rows})
    }))
}

fn lines(matrix: &[Vec<bool>]) -> Vec<(usize, usize, usize)> {
    let (mut out, mut last) = (Vec::new(), true);
    for (y, row) in matrix.iter().enumerate() {
        let (mut x1, mut x2) = (QUIET, QUIET);
        for &bit in row {
            if last != bit && !bit {
                out.push((x1, x2, y));
                x1 = x2;
            }
            x2 += 1;
            x1 += usize::from(!bit);
            last = bit;
        }
        if last {
            out.push((x1, x2, y));
            last = false;
        }
    }
    out
}

pub fn web_svg(payload: &str) -> Result<String> {
    let symbol = matrix(payload, QrCodeEcc::Low)?;
    let width = symbol.len() + 2 * QUIET;
    let (mut path, mut at) = (String::new(), (0usize, None::<usize>));
    for (x1, x2, y) in lines(&symbol) {
        let dy =
            at.1.map_or(format!("{}.5", y + QUIET), |last| (y - last).to_string());
        let moveto = if at.1.is_some() { 'm' } else { 'M' };
        path.push_str(&format!(
            "{moveto}{} {dy}h{}",
            x1 as i64 - at.0 as i64,
            x2 - x1
        ));
        at = (x2, Some(y));
    }
    Ok(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{width}\" class=\"segno\">\
         <path fill=\"#fff\" d=\"M0 0h{width}v{width}h-{width}z\"/><path class=\"qrline\" stroke=\"#17191c\" d=\"{path}\"/></svg>"
    ))
}

fn yaml(path: &Path) -> Result<Yaml> {
    let text =
        std::fs::read_to_string(path).with_context(|| format!("cannot read {}", path.display()))?;
    serde_yaml::from_str(&text).with_context(|| format!("cannot parse {}", path.display()))
}

fn sources(root: &Path, edition: &str) -> Result<Vec<(String, String, f64)>> {
    let manifest = yaml(&root.join("editions").join(edition).join("edition.yaml"))?;
    let mut rows: Vec<(String, String, f64)> = Vec::new();
    for article in manifest["articles"]
        .as_sequence()
        .context("edition.yaml carries no articles list")?
    {
        let room = if article["opener_art"].is_null() {
            PLAIN_ROOM
        } else {
            ILLUSTRATED_ROOM
        };
        let first = article["source_ids"]
            .as_sequence()
            .and_then(|ids| ids.first());
        let source_id = first
            .unwrap_or(&article["id"])
            .as_str()
            .context("article without an id")?
            .to_string();
        let record = yaml(
            &root
                .join("library/sources")
                .join(&source_id)
                .join("record.yaml"),
        )?;
        match record["url"].as_str() {
            Some(url) if !url.is_empty() && !rows.iter().any(|row| row.0 == source_id) => {
                rows.push((source_id, url.to_string(), room));
            }
            _ => {}
        }
    }
    Ok(rows)
}

fn py_json(value: &Value, depth: usize, out: &mut String) {
    let pad = |level: usize| format!("\n{}", "  ".repeat(level));
    match value {
        Value::Array(items) if !items.is_empty() => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                out.push_str(if index == 0 { "" } else { "," });
                out.push_str(&pad(depth + 1));
                py_json(item, depth + 1, out);
            }
            out.push_str(&pad(depth));
            out.push(']');
        }
        Value::Object(map) if !map.is_empty() => {
            out.push('{');
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for (index, key) in keys.into_iter().enumerate() {
                out.push_str(if index == 0 { "" } else { "," });
                out.push_str(&pad(depth + 1));
                out.push_str(&format!("{}: ", Value::String(key.clone())));
                py_json(&map[key], depth + 1, out);
            }
            out.push_str(&pad(depth));
            out.push('}');
        }
        other => out.push_str(&other.to_string()),
    }
}

fn ascii(text: &str) -> String {
    text.chars()
        .map(|c| {
            if c.is_ascii() {
                c.to_string()
            } else {
                c.encode_utf16(&mut [0; 2])
                    .iter()
                    .map(|unit| format!("\\u{unit:04x}"))
                    .collect()
            }
        })
        .collect()
}

pub fn build(root: &Path, edition: &str) -> Result<(Files, usize)> {
    let unsafe_chars = regex::Regex::new(r"[^A-Za-z0-9._-]").expect("static regex");
    let (mut files, mut codes) = (Files::new(), Vec::new());
    for (source_id, url, room) in sources(root, edition)? {
        let payload = payload(&url);
        let name = format!(
            "source-code-{}.svg",
            unsafe_chars.replace_all(&source_id, "-")
        );
        files.push((name.clone(), web_svg(payload)?.into_bytes()));
        codes.push(json!({"payload": payload, "source_id": source_id, "svg": name, "print": fitted(payload, room)?}));
    }
    let declines = codes.iter().filter(|code| code["print"].is_null()).count();
    let mut index = String::new();
    py_json(&json!({"codes": codes}), 0, &mut index);
    files.push((
        "codes.json".to_string(),
        format!("{}\n", ascii(&index)).into_bytes(),
    ));
    Ok((files, declines))
}

pub fn differences(files: &Files, directory: &Path) -> Result<Vec<String>> {
    let mut found: Vec<String> = std::fs::read_dir(directory)
        .with_context(|| format!("no committed source codes at {}", directory.display()))?
        .map(|entry| Ok(entry?.file_name().to_string_lossy().into_owned()))
        .collect::<Result<_>>()?;
    found.sort();
    let mut expected: Vec<String> = files.iter().map(|file| file.0.clone()).collect();
    expected.sort();
    if expected != found {
        return Ok(vec![format!(
            "file set differs: expected {expected:?}, found {found:?}"
        )]);
    }
    Ok(files
        .iter()
        .filter(|(name, bytes)| std::fs::read(directory.join(name)).ok().as_ref() != Some(bytes))
        .map(|(name, _)| format!("content differs: {name}"))
        .collect())
}

pub fn run(edition: &str, check: bool) -> Result<i32> {
    let directory = Path::new("editions").join(edition).join("source-codes");
    let (files, declines) = build(Path::new("."), edition)?;
    if check {
        let differences = differences(&files, &directory)?;
        differences.iter().for_each(|line| println!("{line}"));
        if differences.is_empty() {
            println!("{} files reproduce byte-for-byte", files.len());
        }
        return Ok(i32::from(!differences.is_empty()));
    }
    std::fs::create_dir_all(&directory)
        .with_context(|| format!("cannot create {}", directory.display()))?;
    for (name, bytes) in &files {
        std::fs::write(directory.join(name), bytes)
            .with_context(|| format!("cannot write {name}"))?;
    }
    println!(
        "wrote {}; print declines on {declines}",
        directory.display()
    );
    println!("\nnext: mag render {edition}");
    Ok(0)
}
