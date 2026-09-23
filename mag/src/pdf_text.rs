use anyhow::{bail, Context, Result};
use lopdf::content::Content;
use lopdf::{Dictionary, Document, Object, ObjectId};
use std::collections::BTreeMap;
use std::path::Path;
use std::rc::Rc;
use unicode_normalization::UnicodeNormalization;

type M = [f64; 6];
const ID: M = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0];

#[derive(Clone, Debug)]
pub struct Glyph {
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub size: f64,
    pub text: String,
    pub mono: bool,
    pub spaced: bool,
    pub dir: u8,
}

#[derive(Clone, Copy, Debug)]
pub struct Rule {
    pub x0: f64,
    pub x1: f64,
    pub y: f64,
}

pub fn transcribe(pdf: &Path) -> Result<String> {
    let bytes = std::fs::read(pdf).with_context(|| format!("reading {}", pdf.display()))?;
    transcribe_bytes(&bytes).with_context(|| format!("transcribing {}", pdf.display()))
}

pub fn transcribe_bytes(bytes: &[u8]) -> Result<String> {
    let doc = Document::load_mem(bytes).context("parsing the PDF")?;
    if doc.trailer.has(b"Encrypt") || doc.is_encrypted() || doc.was_encrypted() {
        bail!(
            "the PDF is encrypted; decrypt it first, the text is not transcribed from ciphertext"
        );
    }
    let mut fonts = BTreeMap::new();
    let mut out = Vec::new();
    for (n, id) in doc.get_pages() {
        let page = read_page(&doc, id, &mut fonts).with_context(|| format!("page {n}"))?;
        out.extend(page);
    }
    Ok(out.join("\n\n") + "\n")
}

fn read_page(doc: &Document, id: ObjectId, fonts: &mut FontCache) -> Result<Vec<String>> {
    let mut it = Interp {
        doc,
        fonts,
        glyphs: Vec::new(),
        rules: Vec::new(),
        voids: Vec::new(),
        invisible: 0,
        images: 0,
        gs: Gs::fresh(),
        stack: Vec::new(),
        depth: 0,
        pending_space: false,
    };
    let res = page_resources(doc, id);
    it.interpret(&doc.get_page_content_with_limit(id, usize::MAX)?, &res)?;
    if let Some((_, what)) = it
        .voids
        .iter()
        .find(|(v, _)| it.glyphs.iter().any(|g| touches(v, g)))
    {
        bail!("{what} is declared textless (ToUnicode U+0000) yet sits inside a word");
    }
    if it.invisible > 0 && (it.images > 0 || it.invisible > it.glyphs.len()) {
        bail!(
            "the page carries invisible text (render mode 3: {} invisible glyphs, {} printed, {} images), an OCR layer over a scan?; OCR is not transcription",
            it.invisible,
            it.glyphs.len(),
            it.images
        );
    }
    if it.glyphs.is_empty() && it.images > 0 {
        bail!("the page is an image with no text layer (a scan?); OCR is not transcription");
    }
    Ok(layout(it.glyphs, &it.rules))
}

fn touches(v: &Glyph, g: &Glyph) -> bool {
    let reach = 0.3 * v.size.max(g.size);
    v.dir == g.dir
        && (v.y - g.y).abs() < reach
        && g.x < v.x + v.w + reach
        && v.x < g.x + g.w + reach
}

fn page_resources(doc: &Document, id: ObjectId) -> Dictionary {
    let mut node = doc.get_dictionary(id).ok();
    while let Some(d) = node {
        if let Ok(r) = d.get(b"Resources") {
            return deref(doc, r).as_dict().cloned().unwrap_or_default();
        }
        node = d
            .get(b"Parent")
            .ok()
            .and_then(|p| deref(doc, p).as_dict().ok());
    }
    Dictionary::new()
}

fn deref<'a>(doc: &'a Document, o: &'a Object) -> &'a Object {
    match o {
        Object::Reference(id) => doc.get_object(*id).unwrap_or(o),
        _ => o,
    }
}

fn num(o: &Object) -> f64 {
    match o {
        Object::Integer(i) => *i as f64,
        Object::Real(r) => *r as f64,
        _ => 0.0,
    }
}

fn concat(a: &M, b: &M) -> M {
    let lin = |p: f64, q: f64| (p * b[0] + q * b[2], p * b[1] + q * b[3]);
    let ((m0, m1), (m2, m3), (x, y)) = (lin(a[0], a[1]), lin(a[2], a[3]), lin(a[4], a[5]));
    [m0, m1, m2, m3, x + b[4], y + b[5]]
}

fn point(m: &M, x: f64, y: f64) -> (f64, f64) {
    let lin = (x * m[0] + y * m[2], x * m[1] + y * m[3]);
    (lin.0 + m[4], lin.1 + m[5])
}

pub struct Font {
    name: String,
    cid: bool,
    type3: bool,
    scale: f64,
    widths: BTreeMap<u32, f64>,
    missing: f64,
    codes: BTreeMap<u32, String>,
    mono: bool,
}

type FontCache = BTreeMap<ObjectId, Rc<Font>>;

fn name_of(o: &Object) -> String {
    o.as_name()
        .map(|n| String::from_utf8_lossy(n).into_owned())
        .unwrap_or_default()
}

fn load_font(doc: &Document, f: &Dictionary) -> Result<Font> {
    let name = f.get(b"BaseFont").map(name_of).unwrap_or_default();
    let subtype = f.get(b"Subtype").map(name_of).unwrap_or_default();
    if subtype == "Type0" {
        return cid_font(doc, f, name);
    }
    let desc = f
        .get(b"FontDescriptor")
        .ok()
        .and_then(|d| deref(doc, d).as_dict().ok());
    let type3 = subtype == "Type3";
    let matrix: Vec<f64> = f
        .get(b"FontMatrix")
        .ok()
        .and_then(|m| deref(doc, m).as_array().ok())
        .map(|m| m.iter().map(num).collect())
        .filter(|m: &Vec<f64>| type3 && m.len() == 6)
        .unwrap_or_else(|| vec![0.001, 0.0, 0.0, 0.001]);
    let first = f.get(b"FirstChar").map(num).unwrap_or(0.0) as u32;
    let widths: BTreeMap<u32, f64> = f
        .get(b"Widths")
        .ok()
        .and_then(|w| deref(doc, w).as_array().ok())
        .map(|a| {
            a.iter()
                .enumerate()
                .map(|(i, w)| (first + i as u32, num(deref(doc, w)) * matrix[0] * 1000.0))
                .collect()
        })
        .unwrap_or_default();
    let missing = match (
        widths.is_empty(),
        desc.and_then(|d| d.get(b"MissingWidth").ok()),
    ) {
        (_, Some(m)) => num(m),
        (true, None) => 500.0,
        (false, None) => 0.0,
    };
    Ok(Font {
        mono: is_mono(desc, &widths),
        codes: match type3 {
            true => to_unicode(doc, f),
            false => simple_codes(doc, f, desc),
        },
        scale: matrix[3].abs() * 1000.0,
        type3,
        cid: false,
        name,
        widths,
        missing,
    })
}

fn is_mono(desc: Option<&Dictionary>, widths: &BTreeMap<u32, f64>) -> bool {
    let flag = desc
        .and_then(|d| d.get(b"Flags").ok())
        .map(|f| num(f) as i64 & 1 == 1)
        .unwrap_or(false);
    let mut seen = widths.values().filter(|w| **w > 0.0);
    let first = seen.next().copied();
    let uniform = first.is_some() && widths.len() > 20 && seen.all(|w| Some(*w) == first);
    flag || uniform
}

fn cid_font(doc: &Document, f: &Dictionary, name: String) -> Result<Font> {
    let enc = f.get(b"Encoding").map(name_of).unwrap_or_default();
    if enc != "Identity-H" {
        bail!("font {name}: CID encoding {enc:?} is not supported (only Identity-H with a ToUnicode map)");
    }
    let codes = to_unicode(doc, f);
    if codes.is_empty() {
        bail!("font {name}: a CID font with no usable /ToUnicode map, its glyphs cannot be read as text");
    }
    let desc = f
        .get(b"DescendantFonts")
        .ok()
        .and_then(|d| deref(doc, d).as_array().ok())
        .and_then(|a| a.first())
        .and_then(|d| deref(doc, d).as_dict().ok())
        .with_context(|| format!("font {name}: no descendant font"))?;
    let widths = cid_widths(doc, desc);
    let fd = desc
        .get(b"FontDescriptor")
        .ok()
        .and_then(|d| deref(doc, d).as_dict().ok());
    Ok(Font {
        mono: is_mono(fd, &BTreeMap::new()),
        missing: desc.get(b"DW").map(num).unwrap_or(1000.0),
        cid: true,
        type3: false,
        scale: 1.0,
        name,
        widths,
        codes,
    })
}

fn cid_widths(doc: &Document, desc: &Dictionary) -> BTreeMap<u32, f64> {
    let mut out = BTreeMap::new();
    let Some(w) = desc
        .get(b"W")
        .ok()
        .and_then(|w| deref(doc, w).as_array().ok())
    else {
        return out;
    };
    let items: Vec<&Object> = w.iter().map(|o| deref(doc, o)).collect();
    let mut i = 0;
    while i + 1 < items.len() {
        let start = num(items[i]) as u32;
        if let Ok(list) = items[i + 1].as_array() {
            for (k, v) in list.iter().enumerate() {
                out.insert(start + k as u32, num(deref(doc, v)));
            }
            i += 2;
        } else if i + 2 < items.len() {
            for c in start..=num(items[i + 1]) as u32 {
                out.insert(c, num(items[i + 2]));
            }
            i += 3;
        } else {
            break;
        }
    }
    out
}

fn usable(s: &str) -> bool {
    !s.is_empty()
        && s.chars().all(|c| {
            !c.is_control()
                && c != '\u{FFFD}'
                && !('\u{E000}'..='\u{F8FF}').contains(&c)
                && (c as u32) < 0xF0000
        })
}

fn simple_codes(
    doc: &Document,
    f: &Dictionary,
    desc: Option<&Dictionary>,
) -> BTreeMap<u32, String> {
    let tu = to_unicode(doc, f);
    let enc = f.get(b"Encoding").ok().map(|e| deref(doc, e));
    let base_name = match enc {
        Some(Object::Name(n)) => Some(String::from_utf8_lossy(n).into_owned()),
        Some(Object::Dictionary(d)) => d.get(b"BaseEncoding").ok().map(name_of),
        _ => None,
    };
    let diffs = enc
        .and_then(|e| e.as_dict().ok())
        .map(|d| differences(doc, d))
        .unwrap_or_default();
    let base = base_name.as_deref().and_then(named_encoding);
    let builtin = if base.is_none() {
        desc.map(|d| builtin_encoding(doc, d)).unwrap_or_default()
    } else {
        BTreeMap::new()
    };
    let fallback = if base.is_none() && builtin.is_empty() {
        Some(&pdf_encoding::STANDARD)
    } else {
        base
    };
    (0..256u32)
        .filter_map(|c| {
            let from_tu = || tu.get(&c).cloned();
            match diffs.get(&c) {
                Some(n) => agl(n).or_else(from_tu),
                None => builtin
                    .get(&c)
                    .cloned()
                    .or_else(from_tu)
                    .or_else(|| fallback.and_then(|m| m.get(c as u8)).map(String::from)),
            }
            .filter(|s| s.is_empty() || usable(s))
            .map(|s| (c, s))
        })
        .collect()
}

fn named_encoding(name: &str) -> Option<&'static pdf_encoding::ForwardMap> {
    match name {
        "WinAnsiEncoding" => Some(&pdf_encoding::WINANSI),
        "MacRomanEncoding" => Some(&pdf_encoding::MACROMAN),
        "MacExpertEncoding" => Some(&pdf_encoding::MACEXPERT),
        "StandardEncoding" => Some(&pdf_encoding::STANDARD),
        _ => None,
    }
}

fn differences(doc: &Document, d: &Dictionary) -> BTreeMap<u32, String> {
    let mut out = BTreeMap::new();
    let mut code = 0u32;
    for o in d
        .get(b"Differences")
        .ok()
        .and_then(|a| deref(doc, a).as_array().ok())
        .into_iter()
        .flatten()
    {
        match deref(doc, o) {
            Object::Integer(i) => code = *i as u32,
            Object::Name(n) => {
                out.insert(code, String::from_utf8_lossy(n).into_owned());
                code += 1;
            }
            _ => {}
        }
    }
    out
}

const TEX_GLYPHS: &str =
    "angbracketleft;27E8 angbracketright;27E9 angleleftbig;2329 angleleftBig;2329 \
    angleleftbigg;2329 angleleftBigg;2329 anglerightbig;232A anglerightBig;232A \
    anglerightbigg;232A anglerightBigg;232A arrowbothv;2195 arrowbt;2193 arrowdblbothv;21D5 \
    arrowdbltp;21D1 arrowdblvertex;21D5 arrowleftbothalf;21BD arrowlefttophalf;21BC \
    arrownortheast;2197 arrownorthwest;2196 arrowrightbothalf;21C1 arrowrighttophalf;21C0 \
    arrowsoutheast;2198 arrowsouthwest;2199 arrowtp;2191 arrowvertex;2195 asteriskcentered;2217 \
    backslashbig;005C backslashBig;005C backslashbigg;005C backslashBigg;005C bardbl;2225 \
    bardblex;2016 barex;007C braceex;007C braceleftbig;007B braceleftBig;007B \
    braceleftbigg;007B braceleftBigg;007B braceleftmid;007C bracerightbig;007D \
    bracerightBig;007D bracerightbigg;007D bracerightBigg;007D bracerightmid;2016 \
    bracketleftbig;005B bracketleftBig;005B bracketleftbigg;005B bracketleftBigg;005B \
    bracketrightbig;005D bracketrightBig;005D bracketrightbigg;005D bracketrightBigg;005D \
    ceilingleft;2308 ceilingleftbig;2308 ceilingleftBig;2308 ceilingleftbigg;2308 \
    ceilingleftBigg;2308 ceilingright;2309 ceilingrightbig;2309 ceilingrightBig;2309 \
    ceilingrightbigg;2309 ceilingrightBigg;2309 circlecopyrt;20DD circledivide;2298 \
    circledot;2299 circledotdisplay;2299 circledottext;2299 circleminus;2296 \
    circlemultiplydisplay;2297 circlemultiplytext;2297 circleplusdisplay;2295 \
    circleplustext;2295 compwordmark;200C contintegraldisplay;222E contintegraltext;222E \
    coproduct;2A3F coproductdisplay;2210 coproducttext;2210 cwm;200C dbar;0111 Dbar;0110 \
    dblbracketleft;27E6 dblbracketright;27E7 Delta;2206 diamond;2662 diamondmath;22C4 \
    dotlessj;0237 emptyset;2205 epsilon1;03F5 equivasymptotic;224D flat;266D floorleft;230A \
    floorleftbig;230A floorleftBig;230A floorleftbigg;230A floorleftBigg;230A floorright;230B \
    floorrightbig;230B floorrightBig;230B floorrightbigg;230B floorrightBigg;230B follows;227B \
    followsequal;227D greatermuch;226B harpoonleftdown;21BD harpoonleftup;21BC \
    harpoonrightdown;21C1 harpoonrightup;21C0 hatwide;0302 hatwider;0302 hatwiderr;0302 \
    heart;2661 hookleftchar;21A9 hookrightchar;21AA hyphen.alt;2010 hyphenchar;002D \
    Ifractur;2111 integraldisplay;222B integraltext;222B interrobang;203D \
    intersectiondisplay;22C2 intersectionsq;2293 intersectiontext;22C2 latticetop;22A4 \
    lessmuch;226A logicalanddisplay;22C0 logicalandtext;22C0 logicalordisplay;22C1 \
    logicalortext;22C1 lscript;2113 natural;266E negationslash;0338 ng;014B Ng;014A Omega;2126 \
    owner;220B parenleftbig;0028 parenleftBig;0028 parenleftbigg;0028 parenleftBigg;0028 \
    parenleftex;007C parenrightbig;0029 parenrightBig;0029 parenrightbigg;0029 \
    parenrightBigg;0029 parenrightex;007C pertenthousand;2031 phi;03D5 phi1;03C6 pi1;03D6 \
    precedesequal;227C prime;2032 productdisplay;220F producttext;220F punctdash;2014 \
    radicalbig;221A radicalBig;221A radicalbigg;221A radicalBigg;221A radicalbt;221A \
    rangedash;2013 Rfractur;211C rho1;03F1 sharp;266F similarequal;2243 slashbig;2215 \
    slashBig;2215 slashbigg;2215 slashBigg;2215 slurabove;2322 slurbelow;2323 star;22C6 \
    subsetsqequal;2291 summationdisplay;2211 summationtext;2211 supersetsqequal;2292 tie;2040 \
    tildewide;0303 tildewider;0303 tildewiderr;0303 triangle;25B3 triangleinv;25BD \
    triangleleft;25B9 triangleright;25C3 turnstileleft;22A2 turnstileright;22A3 \
    uniondisplay;22C3 unionmulti;228E unionmultidisplay;228E unionmultitext;228E unionsq;2294 \
    unionsqdisplay;2294 unionsqtext;2294 uniontext;22C3 vector;20D7 visiblespace;2423 \
    visualspace;2423 wreathproduct;2240";

pub fn agl(name: &str) -> Option<String> {
    let base = name.split('.').next().unwrap_or(name);
    if base.contains('_') {
        return base.split('_').map(agl).collect();
    }
    let hex = |h: &str| u32::from_str_radix(h, 16).ok().and_then(char::from_u32);
    if let Some(s) = pdf_encoding::glyphname_to_unicode(base) {
        return Some(s.to_string());
    }
    let tex = TEX_GLYPHS
        .split_whitespace()
        .filter_map(|e| e.split_once(';'));
    if let Some((_, h)) = tex.clone().find(|(n, _)| *n == base) {
        return hex(h).map(String::from);
    }
    if let Some(h) = base
        .strip_prefix("uni")
        .filter(|h| h.len() % 4 == 0 && !h.is_empty())
    {
        return (0..h.len() / 4)
            .map(|i| hex(&h[i * 4..i * 4 + 4]))
            .collect();
    }
    base.strip_prefix('u')
        .filter(|h| (4..=6).contains(&h.len()))
        .and_then(hex)
        .map(String::from)
}

fn builtin_encoding(doc: &Document, desc: &Dictionary) -> BTreeMap<u32, String> {
    let stream = |k: &[u8]| {
        desc.get(k)
            .ok()
            .and_then(|s| deref(doc, s).as_stream().ok())
            .and_then(|s| {
                s.decompressed_content()
                    .ok()
                    .or_else(|| Some(s.content.clone()))
            })
    };
    if let Some(data) = stream(b"FontFile") {
        return type1_encoding(&data);
    }
    if let Some(data) = stream(b"FontFile3") {
        return cff_encoding(&data);
    }
    BTreeMap::new()
}

fn type1_encoding(data: &[u8]) -> BTreeMap<u32, String> {
    let end = data
        .windows(5)
        .position(|w| w == b"eexec")
        .unwrap_or(data.len());
    let text = String::from_utf8_lossy(&data[..end]);
    if text.contains("/Encoding StandardEncoding") {
        return (0..256u32)
            .filter_map(|c| {
                pdf_encoding::STANDARD
                    .get(c as u8)
                    .map(|ch| (c, ch.to_string()))
            })
            .collect();
    }
    let re = regex::Regex::new(r"dup\s+(\d+)\s*/([^\s/\[\]{}()<>]+)\s+put").unwrap();
    re.captures_iter(&text)
        .filter_map(|c| Some((c[1].parse().ok()?, agl(&c[2])?)))
        .collect()
}

fn cff_encoding(data: &[u8]) -> BTreeMap<u32, String> {
    let Some(table) = ttf_parser::cff::Table::parse(data) else {
        return BTreeMap::new();
    };
    (0..256u32)
        .filter_map(|c| {
            let gid = table.glyph_index(c as u8)?;
            if gid.0 == 0 {
                return None;
            }
            Some((c, agl(table.glyph_name(gid)?)?))
        })
        .collect()
}

fn to_unicode(doc: &Document, f: &Dictionary) -> BTreeMap<u32, String> {
    let Some(data) = f
        .get(b"ToUnicode")
        .ok()
        .and_then(|s| deref(doc, s).as_stream().ok())
        .and_then(|s| {
            s.decompressed_content()
                .ok()
                .or_else(|| Some(s.content.clone()))
        })
    else {
        return BTreeMap::new();
    };
    parse_cmap(&String::from_utf8_lossy(&data))
        .into_iter()
        .filter_map(|(c, s)| match s.trim_matches('\0') {
            "" => Some((c, String::new())),
            _ if usable(&s) => Some((c, s)),
            _ => None,
        })
        .collect()
}

fn utf16(hex: &str) -> String {
    let units: Vec<u16> = (0..hex.len() / 4)
        .filter_map(|i| u16::from_str_radix(&hex[i * 4..i * 4 + 4], 16).ok())
        .collect();
    String::from_utf16_lossy(&units)
}

fn parse_cmap(text: &str) -> BTreeMap<u32, String> {
    let mut out = BTreeMap::new();
    let tok = regex::Regex::new(r"<([0-9A-Fa-f\s]*)>|\[|\]|[A-Za-z]+").unwrap();
    let toks: Vec<String> = tok
        .find_iter(text)
        .map(|m| m.as_str().chars().filter(|c| !c.is_whitespace()).collect())
        .collect();
    let mut mode = "";
    let mut i = 0;
    while i < toks.len() {
        match toks[i].as_str() {
            "beginbfchar" => mode = "char",
            "beginbfrange" => mode = "range",
            "endbfchar" | "endbfrange" => mode = "",
            _ if mode == "char" && i + 1 < toks.len() => {
                out.insert(hexnum(&toks[i]), utf16(hexbody(&toks[i + 1])));
                i += 1;
            }
            _ if mode == "range" && i + 2 < toks.len() => i = bfrange(&toks, i, &mut out),
            _ => {}
        }
        i += 1;
    }
    out
}

fn hexbody(t: &str) -> &str {
    t.trim_start_matches('<').trim_end_matches('>')
}

fn hexnum(t: &str) -> u32 {
    u32::from_str_radix(hexbody(t), 16).unwrap_or(0)
}

fn bfrange(toks: &[String], i: usize, out: &mut BTreeMap<u32, String>) -> usize {
    let (lo, hi) = (hexnum(&toks[i]), hexnum(&toks[i + 1]));
    if toks[i + 2] == "[" {
        let mut j = i + 3;
        let mut c = lo;
        while j < toks.len() && toks[j] != "]" {
            out.insert(c, utf16(hexbody(&toks[j])));
            c += 1;
            j += 1;
        }
        return j;
    }
    let dst = hexbody(&toks[i + 2]);
    let mut units: Vec<u16> = (0..dst.len() / 4)
        .filter_map(|k| u16::from_str_radix(&dst[k * 4..k * 4 + 4], 16).ok())
        .collect();
    for c in lo..=hi.min(lo + 0xFFFF) {
        out.insert(c, String::from_utf16_lossy(&units));
        if let Some(last) = units.last_mut() {
            *last = last.wrapping_add(1);
        }
    }
    i + 2
}

#[derive(Clone)]
struct Gs {
    ctm: M,
    font: Option<Rc<Font>>,
    size: f64,
    tc: f64,
    tw: f64,
    th: f64,
    tl: f64,
    rise: f64,
    mode: i64,
    tm: M,
    tlm: M,
}

impl Gs {
    fn fresh() -> Self {
        Gs {
            ctm: ID,
            font: None,
            size: 0.0,
            tc: 0.0,
            tw: 0.0,
            th: 1.0,
            tl: 0.0,
            rise: 0.0,
            mode: 0,
            tm: ID,
            tlm: ID,
        }
    }
}

struct Interp<'a> {
    doc: &'a Document,
    fonts: &'a mut FontCache,
    glyphs: Vec<Glyph>,
    rules: Vec<Rule>,
    voids: Vec<(Glyph, String)>,
    invisible: usize,
    images: usize,
    gs: Gs,
    stack: Vec<Gs>,
    depth: usize,
    pending_space: bool,
}

impl Interp<'_> {
    fn interpret(&mut self, content: &[u8], res: &Dictionary) -> Result<()> {
        let ops = Content::decode(content).context("decoding the content stream")?;
        let mut path: Vec<[f64; 5]> = Vec::new();
        let mut cur = (0.0, 0.0);
        for op in &ops.operations {
            let a: Vec<f64> = op.operands.iter().map(num).collect();
            let ctm = self.gs.ctm;
            let seg = |x0: f64, y0: f64, x1: f64, y1: f64, kind: f64| {
                let (p, q) = (point(&ctm, x0, y0), point(&ctm, x1, y1));
                [p.0, p.1, q.0, q.1, kind]
            };
            match (op.operator.as_str(), a.len()) {
                ("m", 2) => cur = (a[0], a[1]),
                ("l", 2) => {
                    path.push(seg(cur.0, cur.1, a[0], a[1], 0.0));
                    cur = (a[0], a[1]);
                }
                ("re", 4) => path.push(seg(a[0], a[1], a[0] + a[2], a[1] + a[3], 1.0)),
                ("S" | "s" | "B" | "B*" | "b" | "b*", _) => {
                    self.paint(&std::mem::take(&mut path), true)
                }
                ("f" | "F" | "f*", _) => self.paint(&std::mem::take(&mut path), false),
                ("n", _) => path.clear(),
                _ => self.op(&op.operator, &op.operands, &a, res)?,
            }
        }
        Ok(())
    }

    fn paint(&mut self, path: &[[f64; 5]], stroke: bool) {
        for p in path {
            let (x0, x1, y0, y1) = (
                p[0].min(p[2]),
                p[0].max(p[2]),
                p[1].min(p[3]),
                p[1].max(p[3]),
            );
            let thin = y1 - y0 < 2.0 && x1 - x0 > 10.0 * (y1 - y0).max(0.5);
            let edges = if thin && (p[4] == 1.0 || stroke) {
                vec![(y0 + y1) / 2.0]
            } else if stroke && p[4] == 1.0 && x1 - x0 > 10.0 {
                vec![y0, y1]
            } else {
                vec![]
            };
            self.rules
                .extend(edges.into_iter().map(|y| Rule { x0, x1, y }));
        }
    }

    fn op(&mut self, name: &str, raw: &[Object], a: &[f64], res: &Dictionary) -> Result<()> {
        let g = &mut self.gs;
        match (name, a.len()) {
            ("q", _) => self.stack.push(self.gs.clone()),
            ("Q", _) => self.gs = self.stack.pop().unwrap_or_else(Gs::fresh),
            ("cm", 6) => g.ctm = concat(&[a[0], a[1], a[2], a[3], a[4], a[5]], &g.ctm),
            ("BT", _) => (g.tm, g.tlm) = (ID, ID),
            ("Tc", 1) => g.tc = a[0],
            ("Tw", 1) => g.tw = a[0],
            ("Tz", 1) => g.th = a[0] / 100.0,
            ("TL", 1) => g.tl = a[0],
            ("Ts", 1) => g.rise = a[0],
            ("Tr", 1) => g.mode = a[0] as i64,
            ("Td", 2) => self.td(a[0], a[1]),
            ("TD", 2) => {
                g.tl = -a[1];
                self.td(a[0], a[1]);
            }
            ("Tm", 6) => {
                g.tm = [a[0], a[1], a[2], a[3], a[4], a[5]];
                g.tlm = g.tm;
            }
            ("T*", _) => self.td(0.0, -self.gs.tl),
            ("Tf", 2) => self.set_font(raw, a[1], res)?,
            ("Tj", _) => self.show_obj(raw.first())?,
            ("'", _) => {
                self.td(0.0, -self.gs.tl);
                self.show_obj(raw.first())?;
            }
            ("\"", 3) => {
                (self.gs.tw, self.gs.tc) = (a[0], a[1]);
                self.td(0.0, -self.gs.tl);
                self.show_obj(raw.get(2))?;
            }
            ("TJ", _) => self.show_array(raw.first())?,
            ("Do", _) => self.xobject(raw, res)?,
            ("BI" | "EI", _) => self.images += 1,
            _ => {}
        }
        Ok(())
    }

    fn td(&mut self, x: f64, y: f64) {
        self.gs.tlm = concat(&[1.0, 0.0, 0.0, 1.0, x, y], &self.gs.tlm);
        self.gs.tm = self.gs.tlm;
    }

    fn set_font(&mut self, raw: &[Object], size: f64, res: &Dictionary) -> Result<()> {
        let key = raw.first().and_then(|o| o.as_name().ok()).unwrap_or(b"");
        let dict = res
            .get(b"Font")
            .ok()
            .and_then(|f| deref(self.doc, f).as_dict().ok())
            .and_then(|f| f.get(key).ok());
        let font = match dict {
            Some(Object::Reference(id)) => match self.fonts.get(id) {
                Some(f) => f.clone(),
                None => {
                    let d = self.doc.get_dictionary(*id)?;
                    let f = Rc::new(load_font(self.doc, d)?);
                    self.fonts.insert(*id, f.clone());
                    f
                }
            },
            Some(Object::Dictionary(d)) => Rc::new(load_font(self.doc, d)?),
            _ => bail!("font resource /{} is missing", String::from_utf8_lossy(key)),
        };
        self.gs.font = Some(font);
        self.gs.size = size;
        Ok(())
    }

    fn show_obj(&mut self, o: Option<&Object>) -> Result<()> {
        match o {
            Some(Object::String(s, _)) => self.show(&s.clone()),
            _ => Ok(()),
        }
    }

    fn show_array(&mut self, o: Option<&Object>) -> Result<()> {
        let Some(Object::Array(items)) = o else {
            return Ok(());
        };
        for item in items.clone() {
            match item {
                Object::String(s, _) => self.show(&s)?,
                other => {
                    let g = &self.gs;
                    let tx = -num(&other) / 1000.0 * g.size * g.th;
                    self.gs.tm = concat(&[1.0, 0.0, 0.0, 1.0, tx, 0.0], &g.tm);
                }
            }
        }
        Ok(())
    }

    fn show(&mut self, bytes: &[u8]) -> Result<()> {
        let font = self
            .gs
            .font
            .clone()
            .context("text shown with no font selected")?;
        let codes: Vec<u32> = if font.cid {
            bytes
                .chunks(2)
                .map(|c| c.iter().fold(0u32, |a, b| a * 256 + *b as u32))
                .collect()
        } else {
            bytes.iter().map(|b| *b as u32).collect()
        };
        for code in codes {
            self.glyph(&font, code)?;
        }
        Ok(())
    }

    fn glyph(&mut self, font: &Font, code: u32) -> Result<()> {
        let g = &self.gs;
        let w0 = font.widths.get(&code).copied().unwrap_or(font.missing) / 1000.0;
        let trm = concat(
            &[g.size * g.th, 0.0, 0.0, g.size * font.scale, 0.0, g.rise],
            &concat(&g.tm, &g.ctm),
        );
        let text = font.codes.get(&code).with_context(|| match font.type3 {
            true => format!(
                "Type3 font {}: code {code:#x} is a drawn glyph with no ToUnicode entry",
                font.name
            ),
            false => format!("font {}: code {code:#x} has no Unicode mapping", font.name),
        })?;
        let text: String = text.chars().flat_map(expand).collect();
        if text.chars().any(rtl) {
            bail!(
                "font {}: right-to-left text ({text:?}) needs bidi reordering, not read",
                font.name
            );
        }
        if matches!(g.mode, 3 | 7) {
            self.invisible += 1;
        } else if text.is_empty() {
            let at = place(&trm, w0, text, false, false)?;
            self.voids
                .push((at, format!("font {}: code {code:#x}", font.name)));
        } else if text.trim().is_empty() {
            self.pending_space = true;
        } else {
            let glyph = place(&trm, w0, text, font.mono, self.pending_space)?;
            self.glyphs.push(glyph);
            self.pending_space = false;
        }
        let space = if !font.cid && code == 32 { g.tw } else { 0.0 };
        let tx = (w0 * g.size + g.tc + space) * g.th;
        self.gs.tm = concat(&[1.0, 0.0, 0.0, 1.0, tx, 0.0], &self.gs.tm);
        Ok(())
    }

    fn xobject(&mut self, raw: &[Object], res: &Dictionary) -> Result<()> {
        let key = raw.first().and_then(|o| o.as_name().ok()).unwrap_or(b"");
        let Some(stream) = res
            .get(b"XObject")
            .ok()
            .and_then(|x| deref(self.doc, x).as_dict().ok())
            .and_then(|x| x.get(key).ok())
            .and_then(|s| deref(self.doc, s).as_stream().ok())
        else {
            bail!(
                "XObject /{} is invoked but missing from the resources",
                String::from_utf8_lossy(key)
            );
        };
        match stream.dict.get(b"Subtype").map(name_of).as_deref() {
            Ok("Image") => self.images += 1,
            Ok("Form") => {
                if self.depth > 16 {
                    bail!("form XObjects nest deeper than 16 levels");
                }
                let content = stream
                    .decompressed_content()
                    .unwrap_or(stream.content.clone());
                let inner = stream
                    .dict
                    .get(b"Resources")
                    .ok()
                    .and_then(|r| deref(self.doc, r).as_dict().ok())
                    .cloned()
                    .unwrap_or_else(|| res.clone());
                let m: Vec<f64> = stream
                    .dict
                    .get(b"Matrix")
                    .ok()
                    .and_then(|m| m.as_array().ok())
                    .map(|m| m.iter().map(num).collect())
                    .unwrap_or_else(|| ID.to_vec());
                let saved = (self.gs.clone(), self.stack.len());
                if m.len() == 6 {
                    self.gs.ctm = concat(&[m[0], m[1], m[2], m[3], m[4], m[5]], &self.gs.ctm);
                }
                self.depth += 1;
                self.interpret(&content, &inner)?;
                self.depth -= 1;
                self.gs = saved.0;
                self.stack.truncate(saved.1);
            }
            _ => {}
        }
        Ok(())
    }
}

fn rtl(c: char) -> bool {
    matches!(c as u32, 0x590..=0x8FF | 0xFB1D..=0xFDFF | 0xFE70..=0xFEFF | 0x10800..=0x10FFF | 0x1E800..=0x1EFFF)
}

fn expand(c: char) -> Vec<char> {
    match c {
        '\u{FB00}'..='\u{FB06}' => c.to_string().nfkc().collect(),
        _ => vec![c],
    }
}

fn place(trm: &M, w0: f64, text: String, mono: bool, spaced: bool) -> Result<Glyph> {
    let angle = trm[1].atan2(trm[0]).to_degrees();
    let q = (angle / 90.0).round();
    if (angle - q * 90.0).abs() > 1.0 {
        bail!("text set at {angle:.1} degrees; only horizontal and right-angle text is read");
    }
    if trm[0] * trm[3] - trm[1] * trm[2] < 0.0 {
        bail!("mirrored text (a negative text matrix) is not read");
    }
    let dir = (q as i64).rem_euclid(4) as u8;
    let (ox, oy) = point(trm, 0.0, 0.0);
    let (ex, ey) = point(trm, w0, 0.0);
    let rot = |x: f64, y: f64| match dir {
        0 => (x, y),
        1 => (y, -x),
        2 => (-x, -y),
        _ => (-y, x),
    };
    let (x, y) = rot(ox, oy);
    let (x2, _) = rot(ex, ey);
    Ok(Glyph {
        x,
        y,
        w: (x2 - x).max(0.0),
        size: trm[2].hypot(trm[3]),
        text,
        mono,
        spaced,
        dir,
    })
}

fn combining(c: char) -> Option<char> {
    let pairs = [
        ('\u{A8}', '\u{308}'),
        ('\u{B4}', '\u{301}'),
        ('`', '\u{300}'),
        ('\u{2C6}', '\u{302}'),
        ('\u{2DC}', '\u{303}'),
        ('\u{AF}', '\u{304}'),
        ('\u{2D8}', '\u{306}'),
        ('\u{2D9}', '\u{307}'),
        ('\u{2DA}', '\u{30A}'),
        ('\u{2DD}', '\u{30B}'),
        ('\u{2C7}', '\u{30C}'),
        ('\u{B8}', '\u{327}'),
        ('\u{2DB}', '\u{328}'),
    ];
    pairs.iter().find(|(s, _)| *s == c).map(|(_, m)| *m)
}

fn overlap(a0: f64, a1: f64, b0: f64, b1: f64) -> f64 {
    (a1.min(b1) - a0.max(b0)).max(0.0)
}

fn compose_accents(mut gs: Vec<Glyph>) -> Vec<Glyph> {
    let mut drop = vec![false; gs.len()];
    for i in 0..gs.len() {
        let mut chars = gs[i].text.chars();
        let (Some(accent), None) = (chars.next().and_then(combining), chars.next()) else {
            continue;
        };
        let a = &gs[i];
        let base = (0..gs.len()).find(|&j| {
            let b = &gs[j];
            j != i
                && !drop[j]
                && b.dir == a.dir
                && b.text.chars().all(char::is_alphabetic)
                && (b.y - a.y).abs() < b.size
                && overlap(a.x, a.x + a.w, b.x, b.x + b.w) >= 0.5 * a.w.min(b.w)
        });
        if let Some(j) = base {
            gs[j].text = format!("{}{accent}", gs[j].text).nfc().collect();
            drop[i] = true;
        }
    }
    gs.into_iter()
        .zip(drop)
        .filter(|(_, d)| !d)
        .map(|(g, _)| g)
        .collect()
}

fn dedupe(gs: Vec<Glyph>) -> Vec<Glyph> {
    let key = |g: &Glyph| (g.dir, g.text.clone(), (g.y * 2.0).round() as i64);
    let mut order: Vec<usize> = (0..gs.len()).collect();
    order.sort_by(|&a, &b| {
        key(&gs[a])
            .cmp(&key(&gs[b]))
            .then(gs[a].x.total_cmp(&gs[b].x))
            .then(a.cmp(&b))
    });
    let mut keep = vec![true; gs.len()];
    for w in order.windows(2) {
        let (a, b) = (&gs[w[0]], &gs[w[1]]);
        if key(a) == key(b) && (b.x - a.x).abs() < 0.15 * a.size {
            keep[w[1].max(w[0])] = false;
        }
    }
    gs.into_iter()
        .zip(keep)
        .filter(|(_, k)| *k)
        .map(|(g, _)| g)
        .collect()
}

fn layout(glyphs: Vec<Glyph>, rules: &[Rule]) -> Vec<String> {
    let glyphs = dedupe(compose_accents(glyphs));
    let body = median(glyphs.iter().map(|g| g.size).collect());
    let mut paras = Vec::new();
    for dir in 0..4u8 {
        let group: Vec<Glyph> = glyphs.iter().filter(|g| g.dir == dir).cloned().collect();
        if group.is_empty() {
            continue;
        }
        let ruled = if dir == 0 { rules } else { &[] };
        let mut leaves = Vec::new();
        xycut(&group, (0..group.len()).collect(), ruled, &mut leaves);
        let lines: Vec<Line> = leaves.iter().map(|l| line(&group, l)).collect();
        paras.extend(paragraphs(&lines, body));
    }
    paras
}

fn ybox(g: &Glyph) -> (f64, f64) {
    (g.y - 0.2 * g.size, g.y + 0.7 * g.size)
}

fn xbox(g: &Glyph) -> (f64, f64) {
    (g.x, g.x + g.w)
}

fn gaps(mut spans: Vec<(f64, f64)>) -> Vec<(f64, f64)> {
    spans.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut out = Vec::new();
    let mut end = f64::NEG_INFINITY;
    for (lo, hi) in spans {
        if lo > end && end.is_finite() {
            out.push((end, lo));
        }
        end = end.max(hi);
    }
    out
}

fn median(mut v: Vec<f64>) -> f64 {
    v.sort_by(f64::total_cmp);
    v.get(v.len() / 2).copied().unwrap_or(0.0)
}

fn single_line(gs: &[Glyph], idx: &[usize]) -> bool {
    let size = median(idx.iter().map(|&i| gs[i].size).collect());
    let main = || {
        idx.iter()
            .map(|&i| &gs[i])
            .filter(|g| g.size >= 0.85 * size)
    };
    let lo = main().map(|g| g.y).fold(f64::INFINITY, f64::min);
    let hi = main().map(|g| g.y).fold(f64::NEG_INFINITY, f64::max);
    let band = (lo - 0.2 * size, hi + 0.7 * size);
    hi - lo <= 0.3 * size
        && idx.iter().all(|&i| {
            let (y0, y1) = ybox(&gs[i]);
            overlap(y0, y1, band.0, band.1) > 0.0
        })
}

fn xycut(gs: &[Glyph], idx: Vec<usize>, rules: &[Rule], out: &mut Vec<Vec<usize>>) {
    if idx.len() <= 1 || single_line(gs, &idx) {
        out.push(idx);
        return;
    }
    let size = median(idx.iter().map(|&i| gs[i].size).collect());
    let (x0, x1) = idx
        .iter()
        .fold((f64::INFINITY, f64::NEG_INFINITY), |(a, b), &i| {
            (a.min(gs[i].x), b.max(gs[i].x + gs[i].w))
        });
    let hgaps = gaps(idx.iter().map(|&i| ybox(&gs[i])).collect());
    let ruled: Vec<f64> = hgaps
        .iter()
        .filter(|(lo, hi)| {
            rules
                .iter()
                .any(|r| r.y > *lo && r.y < *hi && overlap(r.x0, r.x1, x0, x1) >= 0.8 * (x1 - x0))
        })
        .map(|(lo, hi)| (lo + hi) / 2.0)
        .collect();
    let vgaps: Vec<f64> = gaps(idx.iter().map(|&i| xbox(&gs[i])).collect())
        .into_iter()
        .filter(|(lo, hi)| hi - lo >= size)
        .map(|(lo, hi)| (lo + hi) / 2.0)
        .collect();
    let core = || {
        gaps(
            idx.iter()
                .map(|&i| (gs[i].y, gs[i].y + 0.45 * gs[i].size))
                .collect(),
        )
    };
    let widest = [hgaps.clone(), core()].into_iter().find_map(|g| {
        g.iter()
            .max_by(|a, b| (a.1 - a.0).total_cmp(&(b.1 - b.0)))
            .map(|(lo, hi)| vec![(lo + hi) / 2.0])
    });
    let pieces = if !ruled.is_empty() {
        split(gs, &idx, &ruled, |g| -g.y - 0.25 * g.size, true)
    } else if !vgaps.is_empty() {
        split(gs, &idx, &vgaps, |g| g.x + g.w / 2.0, false)
    } else if let Some(cut) = widest {
        split(gs, &idx, &cut, |g| -g.y - 0.2 * g.size, true)
    } else {
        out.extend(rows(gs, idx));
        return;
    };
    for p in pieces {
        xycut(gs, p, rules, out);
    }
}

fn rows(gs: &[Glyph], mut idx: Vec<usize>) -> Vec<Vec<usize>> {
    let size = median(idx.iter().map(|&i| gs[i].size).collect());
    idx.sort_by(|&a, &b| gs[b].y.total_cmp(&gs[a].y).then(a.cmp(&b)));
    let mut out: Vec<Vec<usize>> = Vec::new();
    for i in idx {
        match out.last_mut() {
            Some(row) if gs[row[0]].y - gs[i].y <= 0.3 * size => row.push(i),
            _ => out.push(vec![i]),
        }
    }
    out
}

fn split(
    gs: &[Glyph],
    idx: &[usize],
    cuts: &[f64],
    at: impl Fn(&Glyph) -> f64,
    flip: bool,
) -> Vec<Vec<usize>> {
    let mut keys: Vec<f64> = cuts.iter().map(|c| if flip { -c } else { *c }).collect();
    keys.sort_by(f64::total_cmp);
    let mut pieces = vec![Vec::new(); keys.len() + 1];
    for &i in idx {
        let k = keys.iter().filter(|c| at(&gs[i]) > **c).count();
        pieces[k].push(i);
    }
    pieces.into_iter().filter(|p| !p.is_empty()).collect()
}

struct Line {
    glyphs: Vec<Glyph>,
    text: String,
    x0: f64,
    x1: f64,
    y: f64,
    size: f64,
    mono: bool,
    tabular: bool,
}

fn line(gs: &[Glyph], idx: &[usize]) -> Line {
    let mut glyphs: Vec<Glyph> = idx.iter().map(|&i| gs[i].clone()).collect();
    glyphs.sort_by(|a, b| a.x.total_cmp(&b.x).then(b.y.total_cmp(&a.y)));
    let size = glyphs.iter().map(|g| g.size).fold(0.0, f64::max);
    let mut text = String::new();
    let mut tabular = false;
    for (k, g) in glyphs.iter().enumerate() {
        if k > 0 {
            let p = &glyphs[k - 1];
            let gap = g.x - (p.x + p.w);
            tabular |= gap >= 2.5 * size;
            if g.spaced || gap > 0.15 * p.size.max(g.size) {
                text.push(' ');
            }
        }
        let last = k + 1 == glyphs.len();
        match g.text.as_str() {
            "\u{AD}" if last && !text.ends_with('-') => text.push('-'),
            "\u{AD}" => {}
            t => text.push_str(t),
        }
    }
    let mono = glyphs.iter().filter(|g| g.mono).count() * 5 >= glyphs.len() * 4;
    Line {
        x0: glyphs.first().map(|g| g.x).unwrap_or(0.0),
        x1: glyphs
            .iter()
            .map(|g| g.x + g.w)
            .fold(f64::NEG_INFINITY, f64::max),
        y: median(glyphs.iter().map(|g| g.y).collect()),
        text: text.trim().to_string(),
        glyphs,
        size,
        mono,
        tabular,
    }
}

fn near(prev: &Line, next: &Line) -> bool {
    let dy = prev.y - next.y;
    dy > 0.0
        && dy <= 1.7 * prev.size
        && (next.size / prev.size - 1.0).abs() <= 0.15
        && overlap(prev.x0, prev.x1, next.x0, next.x1) > 0.0
}

fn continues(prev: &Line, next: &Line) -> bool {
    !prev.tabular && !next.tabular && near(prev, next)
}

fn code_continues(prev: &Line, next: &Line) -> bool {
    let dy = prev.y - next.y;
    let reach = overlap(prev.x0 - 20.0 * prev.size, prev.x1, next.x0, next.x1);
    prev.mono && next.mono && dy > 0.0 && dy <= 4.0 * prev.size && reach > 0.0
}

fn new_paragraph(prev: &Line, next: &Line, right: f64) -> bool {
    next.x0 - prev.x0 > 0.6 * prev.size && prev.x1 < right - 1.5 * prev.size
}

fn is_code(lines: &[Line], i: usize) -> bool {
    let (l, prev, next) = (
        &lines[i],
        i.checked_sub(1).map(|p| &lines[p]),
        lines.get(i + 1),
    );
    let run =
        prev.is_some_and(|p| code_continues(p, l)) || next.is_some_and(|n| code_continues(l, n));
    let inline = prev.is_some_and(|p| near(p, l)) || next.is_some_and(|n| near(l, n));
    l.mono && (run || !inline)
}

fn paragraphs(lines: &[Line], body: f64) -> Vec<String> {
    let kinds: Vec<bool> = (0..lines.len()).map(|i| is_code(lines, i)).collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < lines.len() {
        let mut j = i + 1;
        let mut right = lines[i].x1;
        while j < lines.len()
            && kinds[j] == kinds[i]
            && if kinds[i] {
                code_continues(&lines[j - 1], &lines[j])
            } else {
                continues(&lines[j - 1], &lines[j])
                    && !new_paragraph(&lines[j - 1], &lines[j], right)
            }
        {
            right = right.max(lines[j].x1);
            j += 1;
        }
        let block = &lines[i..j];
        let text = match (kinds[i], block) {
            (true, _) => code(block),
            (false, [l]) if l.size >= 1.15 * body && l.text.len() <= 120 => {
                format!("## {}", l.text)
            }
            _ => prose(block),
        };
        if !text.trim().is_empty() {
            out.push(text);
        }
        i = j;
    }
    out
}

fn prose(block: &[Line]) -> String {
    let mut out = String::new();
    for l in block {
        let glue = out.chars().rev().take(2).collect::<Vec<_>>();
        let joined = matches!(glue.as_slice(), [d, w, ..] if matches!(d, '-' | '\u{2013}' | '\u{2014}') && w.is_alphanumeric());
        if !out.is_empty() && !joined {
            out.push(' ');
        }
        out.push_str(&l.text);
    }
    out
}

fn code(block: &[Line]) -> String {
    let all: Vec<&Glyph> = block.iter().flat_map(|l| &l.glyphs).collect();
    let cw = median(
        all.iter()
            .filter(|g| g.mono)
            .map(|g| g.w / g.text.chars().count().max(1) as f64)
            .collect(),
    )
    .max(0.01);
    let x0 = all.iter().map(|g| g.x).fold(f64::INFINITY, f64::min);
    let pitch = block
        .windows(2)
        .map(|w| w[0].y - w[1].y)
        .filter(|d| *d > 0.0)
        .fold(f64::INFINITY, f64::min);
    let mut out = vec!["```".to_string()];
    for (k, l) in block.iter().enumerate() {
        if k > 0 {
            let blanks = ((block[k - 1].y - l.y) / pitch).round() as usize;
            out.extend(std::iter::repeat_n(String::new(), blanks.saturating_sub(1)));
        }
        let mut s = String::new();
        for g in &l.glyphs {
            let col = ((g.x - x0) / cw).round().max(0.0) as usize;
            while s.chars().count() < col {
                s.push(' ');
            }
            s.push_str(&g.text);
        }
        out.push(s.trim_end().to_string());
    }
    out.push("```".to_string());
    out.join("\n")
}
