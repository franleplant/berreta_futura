use anyhow::{bail, Context, Result};
use flate2::read::ZlibDecoder;
use lopdf::content::Content;
use lopdf::{Dictionary, Document, Object, ObjectId};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap};
use std::io::Read;
use std::rc::Rc;

pub type M = [f64; 6];

pub const ID: M = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0];

pub fn mul(a: M, b: M) -> M {
    [
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]
}

pub fn apply(m: M, x: f64, y: f64) -> (f64, f64) {
    (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])
}

fn translate(x: f64, y: f64) -> M {
    [1.0, 0.0, 0.0, 1.0, x, y]
}

pub fn qc(v: f64) -> i64 {
    (v * 100.0).round() as i64
}

fn qcolor(v: f64) -> i64 {
    (v * 1_000_000.0).round() as i64
}

#[derive(Serialize, Clone, PartialEq, Eq)]
pub struct Color {
    pub family: String,
    pub rgb: [i64; 3],
}

fn rgb(r: f64, g: f64, b: f64, family: &str) -> Color {
    Color {
        family: family.into(),
        rgb: [qcolor(r), qcolor(g), qcolor(b)],
    }
}

#[derive(Serialize, Clone)]
#[serde(tag = "kind")]
pub enum Element {
    Text {
        s: String,
        font: String,
        size: i64,
        fill: Color,
        glyphs: usize,
        m: [i64; 6],
        clip: Vec<u32>,
    },
    Path {
        d: String,
        paint: String,
        fill: Option<Color>,
        stroke: Option<Color>,
        lw: Option<i64>,
        cap: Option<i64>,
        join: Option<i64>,
        miter: Option<i64>,
        dash: Option<(Vec<i64>, i64)>,
        clip: Vec<u32>,
    },
    Clip {
        d: String,
        evenodd: bool,
        clip: Vec<u32>,
    },
    Image {
        rgba_sha256: String,
        m: [i64; 6],
        clip: Vec<u32>,
    },
}

struct Font {
    name: String,
    two_byte: bool,
    dw: f64,
    widths: HashMap<u32, f64>,
    tounicode: HashMap<u32, String>,
}

#[derive(Clone)]
struct GState {
    ctm: M,
    fill: Color,
    stroke: Color,
    lw: f64,
    cap: i64,
    join: i64,
    miter: f64,
    dash: (Vec<f64>, f64),
    clips: Vec<u32>,
    font: Option<Rc<Font>>,
    size: f64,
    tc: f64,
    tw: f64,
    tz: f64,
    tl: f64,
    ts: f64,
}

impl GState {
    fn new() -> Self {
        GState {
            ctm: ID,
            fill: rgb(0.0, 0.0, 0.0, "rgb"),
            stroke: rgb(0.0, 0.0, 0.0, "rgb"),
            lw: 1.0,
            cap: 0,
            join: 0,
            miter: 10.0,
            dash: (vec![], 0.0),
            clips: vec![],
            font: None,
            size: 0.0,
            tc: 0.0,
            tw: 0.0,
            tz: 100.0,
            tl: 0.0,
            ts: 0.0,
        }
    }
}

pub struct Caches {
    images: HashMap<ObjectId, (String, u32, u32)>,
    fonts: HashMap<ObjectId, Rc<Font>>,
}

impl Caches {
    pub fn new() -> Self {
        Caches {
            images: HashMap::new(),
            fonts: HashMap::new(),
        }
    }
}

struct Tracer<'a> {
    doc: &'a Document,
    font_map: &'a BTreeMap<String, String>,
    caches: &'a mut Caches,
    out: Vec<Element>,
    gs: GState,
    stack: Vec<GState>,
    tm: M,
    tlm: M,
    path: String,
    start: Option<(f64, f64)>,
    cur: Option<(f64, f64)>,
    pending_clip: Option<bool>,
}

pub fn trace_page(
    doc: &Document,
    page_id: ObjectId,
    font_map: &BTreeMap<String, String>,
    caches: &mut Caches,
) -> Result<Vec<Element>> {
    let content = doc.get_page_content(page_id);
    let resources = page_resources(doc, page_id)?;
    let mut tracer = Tracer {
        doc,
        font_map,
        caches,
        out: vec![],
        gs: GState::new(),
        stack: vec![],
        tm: ID,
        tlm: ID,
        path: String::new(),
        start: None,
        cur: None,
        pending_clip: None,
    };
    tracer.run(&content, &resources)?;
    Ok(tracer.out)
}

fn page_resources(doc: &Document, page_id: ObjectId) -> Result<Dictionary> {
    let (maybe, ids) = doc.get_page_resources(page_id)?;
    if let Some(d) = maybe {
        return Ok(d.clone());
    }
    let id = *ids.first().context("page has no resources")?;
    Ok(doc.get_dictionary(id)?.clone())
}

fn num(o: &Object) -> Result<f64> {
    match o {
        Object::Integer(i) => Ok(*i as f64),
        Object::Real(r) => Ok(f64::from(*r)),
        _ => bail!("expected number, got {o:?}"),
    }
}

fn name_str(o: &Object) -> Result<String> {
    match o {
        Object::Name(n) => Ok(String::from_utf8_lossy(n).into_owned()),
        _ => bail!("expected name, got {o:?}"),
    }
}

fn resolve<'a>(doc: &'a Document, o: &'a Object) -> Result<&'a Object> {
    match o {
        Object::Reference(id) => Ok(doc.get_object(*id)?),
        other => Ok(other),
    }
}

impl Tracer<'_> {
    fn run(&mut self, content: &[u8], res: &Dictionary) -> Result<()> {
        let ops = Content::decode(content).context("decoding content stream")?;
        for op in &ops.operations {
            self.op(op.operator.as_str(), &op.operands, res)
                .with_context(|| format!("operator {}", op.operator))?;
        }
        Ok(())
    }

    fn op(&mut self, operator: &str, args: &[Object], res: &Dictionary) -> Result<()> {
        match operator {
            "q" => self.stack.push(self.gs.clone()),
            "Q" => self.gs = self.stack.pop().context("Q without q")?,
            "cm" => {
                let m = matrix(args)?;
                self.gs.ctm = mul(m, self.gs.ctm);
            }
            "gs" => self.ext_gstate(args, res)?,
            "w" => self.gs.lw = num(&args[0])?,
            "J" => self.gs.cap = num(&args[0])? as i64,
            "j" => self.gs.join = num(&args[0])? as i64,
            "M" => self.gs.miter = num(&args[0])?,
            "d" => self.set_dash(args)?,
            "i" | "ri" | "BMC" | "BDC" | "EMC" | "MP" | "DP" => {}
            "m" | "l" | "c" | "v" | "y" | "h" | "re" => self.path_op(operator, args)?,
            "S" | "s" | "f" | "F" | "f*" | "B" | "B*" | "b" | "b*" | "n" => {
                self.paint_op(operator)?;
            }
            "W" => self.pending_clip = Some(false),
            "W*" => self.pending_clip = Some(true),
            "rg" => self.gs.fill = rgb(num(&args[0])?, num(&args[1])?, num(&args[2])?, "rgb"),
            "RG" => self.gs.stroke = rgb(num(&args[0])?, num(&args[1])?, num(&args[2])?, "rgb"),
            "g" => self.gs.fill = gray(num(&args[0])?),
            "G" => self.gs.stroke = gray(num(&args[0])?),
            "k" => self.gs.fill = cmyk(args)?,
            "K" => self.gs.stroke = cmyk(args)?,
            "BT" => {
                self.tm = ID;
                self.tlm = ID;
            }
            "ET" => {}
            "Tf" => self.set_font(args, res)?,
            "Tm" => {
                self.tm = matrix(args)?;
                self.tlm = self.tm;
            }
            "Td" => self.td(num(&args[0])?, num(&args[1])?),
            "TD" => {
                self.gs.tl = -num(&args[1])?;
                self.td(num(&args[0])?, num(&args[1])?);
            }
            "T*" => self.td(0.0, -self.gs.tl),
            "TL" => self.gs.tl = num(&args[0])?,
            "Tc" => self.gs.tc = num(&args[0])?,
            "Tw" => self.gs.tw = num(&args[0])?,
            "Tz" => self.gs.tz = num(&args[0])?,
            "Ts" => self.gs.ts = num(&args[0])?,
            "Tr" => anyhow::ensure!(num(&args[0])? == 0.0, "text render mode != 0 unsupported"),
            "Tj" => self.show(&[args[0].clone()])?,
            "'" => {
                self.td(0.0, -self.gs.tl);
                self.show(&[args[0].clone()])?;
            }
            "\"" => {
                self.gs.tw = num(&args[0])?;
                self.gs.tc = num(&args[1])?;
                self.td(0.0, -self.gs.tl);
                self.show(&[args[2].clone()])?;
            }
            "TJ" => {
                let arr = args[0].as_array().context("TJ operand")?;
                self.show(arr)?;
            }
            "Do" => self.do_xobject(args, res)?,
            other => bail!("unsupported operator {other}"),
        }
        Ok(())
    }

    fn td(&mut self, tx: f64, ty: f64) {
        self.tlm = mul(translate(tx, ty), self.tlm);
        self.tm = self.tlm;
    }

    fn set_dash(&mut self, args: &[Object]) -> Result<()> {
        let arr = args[0].as_array().context("dash array")?;
        let pattern: Result<Vec<f64>> = arr.iter().map(num).collect();
        self.gs.dash = (pattern?, num(&args[1])?);
        Ok(())
    }

    fn ext_gstate(&mut self, args: &[Object], res: &Dictionary) -> Result<()> {
        let name = name_str(&args[0])?;
        let states = resolve(self.doc, res.get(b"ExtGState")?)?.as_dict()?;
        let dict = resolve(self.doc, states.get(name.as_bytes())?)?.as_dict()?;
        for (key, value) in dict.iter() {
            let value = resolve(self.doc, value)?;
            match key.as_slice() {
                b"Type" => {}
                b"ca" | b"CA" => anyhow::ensure!(
                    num(value)? == 1.0,
                    "ExtGState alpha other than 1 unsupported (fail loud per Tier E)"
                ),
                b"SMask" => anyhow::ensure!(
                    matches!(value, Object::Name(n) if n == b"None"),
                    "ExtGState SMask unsupported"
                ),
                other => bail!(
                    "ExtGState key {} unsupported",
                    String::from_utf8_lossy(other)
                ),
            }
        }
        Ok(())
    }

    fn set_font(&mut self, args: &[Object], res: &Dictionary) -> Result<()> {
        let name = name_str(&args[0])?;
        self.gs.size = num(&args[1])?;
        let fonts = resolve(self.doc, res.get(b"Font")?)?.as_dict()?;
        let font_ref = fonts.get(name.as_bytes())?;
        let id = match font_ref {
            Object::Reference(id) => *id,
            _ => bail!("font {name} not a reference"),
        };
        if !self.caches.fonts.contains_key(&id) {
            let dict = self.doc.get_dictionary(id)?.clone();
            let font = load_font(self.doc, &dict, self.font_map)
                .with_context(|| format!("loading font {name}"))?;
            self.caches.fonts.insert(id, Rc::new(font));
        }
        self.gs.font = Some(Rc::clone(&self.caches.fonts[&id]));
        Ok(())
    }

    fn show(&mut self, items: &[Object]) -> Result<()> {
        let font = self.gs.font.clone().context("show without Tf")?;
        let th = self.gs.tz / 100.0;
        let params = [self.gs.size * th, 0.0, 0.0, self.gs.size, 0.0, self.gs.ts];
        let trm = mul(params, mul(self.tm, self.gs.ctm));
        let size_eff = (trm[2] * trm[2] + trm[3] * trm[3]).sqrt();
        let mut s = String::new();
        let mut tx = 0.0;
        let mut glyphs = 0;
        for item in items {
            match item {
                Object::String(bytes, _) => {
                    let (dx, n) = self.decode_show(&font, bytes, &mut s)?;
                    tx += dx;
                    glyphs += n;
                }
                other => tx -= num(other)? / 1000.0 * self.gs.size * (self.gs.tz / 100.0),
            }
        }
        self.out.push(Element::Text {
            s,
            font: font.name.clone(),
            size: qc(size_eff),
            fill: self.gs.fill.clone(),
            glyphs,
            m: trm.map(qc),
            clip: self.gs.clips.clone(),
        });
        self.tm = mul(translate(tx, 0.0), self.tm);
        Ok(())
    }

    fn decode_show(&self, font: &Font, bytes: &[u8], s: &mut String) -> Result<(f64, usize)> {
        let th = self.gs.tz / 100.0;
        let mut tx = 0.0;
        let codes: Vec<u32> = if font.two_byte {
            anyhow::ensure!(bytes.len().is_multiple_of(2), "odd-length 2-byte string");
            bytes
                .chunks(2)
                .map(|c| u32::from(c[0]) << 8 | u32::from(c[1]))
                .collect()
        } else {
            bytes.iter().map(|b| u32::from(*b)).collect()
        };
        let count = codes.len();
        for code in codes {
            let uni = font
                .tounicode
                .get(&code)
                .with_context(|| format!("font {} lacks ToUnicode for code {code}", font.name))?;
            s.push_str(uni);
            let w = font.widths.get(&code).copied().unwrap_or(font.dw);
            let word = if !font.two_byte && code == 32 {
                self.gs.tw
            } else {
                0.0
            };
            tx += (w / 1000.0 * self.gs.size + self.gs.tc + word) * th;
        }
        Ok((tx, count))
    }

    fn path_op(&mut self, operator: &str, args: &[Object]) -> Result<()> {
        let nums: Result<Vec<f64>> = args.iter().map(num).collect();
        let nums = nums?;
        let dev = |i: usize| apply(self.gs.ctm, nums[i], nums[i + 1]);
        match operator {
            "m" => {
                let p = dev(0);
                self.start = Some(p);
                self.cur = Some(p);
                self.push_seg("m", &[p]);
            }
            "l" => {
                let p = dev(0);
                self.cur = Some(p);
                self.push_seg("l", &[p]);
            }
            "c" => {
                let (a, b, e) = (dev(0), dev(2), dev(4));
                self.cur = Some(e);
                self.push_seg("c", &[a, b, e]);
            }
            "v" => {
                let cur = self.cur.context("v without current point")?;
                let (b, e) = (dev(0), dev(2));
                self.cur = Some(e);
                self.push_seg("c", &[cur, b, e]);
            }
            "y" => {
                let (a, e) = (dev(0), dev(2));
                self.cur = Some(e);
                self.push_seg("c", &[a, e, e]);
            }
            "h" => {
                self.cur = self.start;
                self.path.push_str("h ");
            }
            "re" => {
                let (x, y, w, h) = (nums[0], nums[1], nums[2], nums[3]);
                let corners = [
                    apply(self.gs.ctm, x, y),
                    apply(self.gs.ctm, x + w, y),
                    apply(self.gs.ctm, x + w, y + h),
                    apply(self.gs.ctm, x, y + h),
                ];
                self.start = Some(corners[0]);
                self.cur = Some(corners[0]);
                self.push_seg("re", &corners);
            }
            _ => unreachable!(),
        }
        Ok(())
    }

    fn push_seg(&mut self, op: &str, points: &[(f64, f64)]) {
        self.path.push_str(op);
        for (x, y) in points {
            self.path.push_str(&format!(" {} {}", qc(*x), qc(*y)));
        }
        self.path.push(' ');
    }

    fn paint_op(&mut self, operator: &str) -> Result<()> {
        let d = std::mem::take(&mut self.path).trim_end().to_string();
        self.start = None;
        self.cur = None;
        let scale = (self.gs.ctm[0] * self.gs.ctm[3] - self.gs.ctm[1] * self.gs.ctm[2])
            .abs()
            .sqrt();
        let (fills, strokes, paint) = paint_kind(operator)?;
        if fills || strokes {
            self.out.push(Element::Path {
                d: d.clone(),
                paint: paint.into(),
                fill: fills.then(|| self.gs.fill.clone()),
                stroke: strokes.then(|| self.gs.stroke.clone()),
                lw: strokes.then(|| qc(self.gs.lw * scale)),
                cap: strokes.then_some(self.gs.cap),
                join: strokes.then_some(self.gs.join),
                miter: strokes.then(|| qc(self.gs.miter)),
                dash: strokes.then(|| {
                    (
                        self.gs.dash.0.iter().map(|v| qc(v * scale)).collect(),
                        qc(self.gs.dash.1 * scale),
                    )
                }),
                clip: self.gs.clips.clone(),
            });
        }
        if let Some(evenodd) = self.pending_clip.take() {
            let index = self.out.len() as u32;
            self.out.push(Element::Clip {
                d,
                evenodd,
                clip: self.gs.clips.clone(),
            });
            self.gs.clips.push(index);
        }
        Ok(())
    }

    fn do_xobject(&mut self, args: &[Object], res: &Dictionary) -> Result<()> {
        let name = name_str(&args[0])?;
        let xobjects = resolve(self.doc, res.get(b"XObject")?)?.as_dict()?;
        let id = match xobjects.get(name.as_bytes())? {
            Object::Reference(id) => *id,
            _ => bail!("XObject {name} not a reference"),
        };
        let stream = self.doc.get_object(id)?.as_stream()?.clone();
        let subtype = name_str(stream.dict.get(b"Subtype")?)?;
        match subtype.as_str() {
            "Image" => self.image(id, &stream),
            "Form" => self.form(&stream),
            other => bail!("XObject subtype {other} unsupported"),
        }
    }

    fn image(&mut self, id: ObjectId, stream: &lopdf::Stream) -> Result<()> {
        if !self.caches.images.contains_key(&id) {
            let decoded = decode_image(self.doc, stream).context("decoding image")?;
            self.caches.images.insert(id, decoded);
        }
        let (hash, _, _) = self.caches.images[&id].clone();
        self.out.push(Element::Image {
            rgba_sha256: hash,
            m: self.gs.ctm.map(qc),
            clip: self.gs.clips.clone(),
        });
        Ok(())
    }

    fn form(&mut self, stream: &lopdf::Stream) -> Result<()> {
        self.stack.push(self.gs.clone());
        if let Ok(m) = stream.dict.get(b"Matrix") {
            let arr = resolve(self.doc, m)?.as_array()?.clone();
            self.gs.ctm = mul(matrix(&arr)?, self.gs.ctm);
        }
        if let Ok(bbox) = stream.dict.get(b"BBox") {
            let arr = resolve(self.doc, bbox)?.as_array()?.clone();
            let nums: Result<Vec<f64>> = arr.iter().map(num).collect();
            let nums = nums?;
            self.path_op(
                "re",
                &to_objects(&[nums[0], nums[1], nums[2] - nums[0], nums[3] - nums[1]]),
            )?;
            self.pending_clip = Some(false);
            self.paint_op("n")?;
        }
        let res = match stream.dict.get(b"Resources") {
            Ok(r) => resolve(self.doc, r)?.as_dict()?.clone(),
            Err(_) => Dictionary::new(),
        };
        let content = decode_stream(self.doc, stream)?;
        self.run(&content, &res)?;
        self.gs = self.stack.pop().context("form state")?;
        Ok(())
    }
}

fn to_objects(nums: &[f64]) -> Vec<Object> {
    nums.iter().map(|n| Object::Real(*n as f32)).collect()
}

fn paint_kind(operator: &str) -> Result<(bool, bool, &'static str)> {
    Ok(match operator {
        "S" => (false, true, "stroke"),
        "s" => (false, true, "close_stroke"),
        "f" | "F" => (true, false, "fill"),
        "f*" => (true, false, "eofill"),
        "B" => (true, true, "fill_stroke"),
        "B*" => (true, true, "eofill_stroke"),
        "b" => (true, true, "close_fill_stroke"),
        "b*" => (true, true, "close_eofill_stroke"),
        "n" => (false, false, "none"),
        other => bail!("paint operator {other}"),
    })
}

fn gray(v: f64) -> Color {
    Color {
        family: "gray".into(),
        rgb: [qcolor(v), qcolor(v), qcolor(v)],
    }
}

fn cmyk(args: &[Object]) -> Result<Color> {
    let (c, m, y, k) = (
        num(&args[0])?,
        num(&args[1])?,
        num(&args[2])?,
        num(&args[3])?,
    );
    Ok(Color {
        family: "cmyk".into(),
        rgb: [
            qcolor((1.0 - c) * (1.0 - k)),
            qcolor((1.0 - m) * (1.0 - k)),
            qcolor((1.0 - y) * (1.0 - k)),
        ],
    })
}

fn matrix(args: &[Object]) -> Result<M> {
    let nums: Result<Vec<f64>> = args.iter().map(num).collect();
    let nums = nums?;
    anyhow::ensure!(nums.len() == 6, "matrix needs 6 numbers");
    Ok([nums[0], nums[1], nums[2], nums[3], nums[4], nums[5]])
}

fn load_font(doc: &Document, dict: &Dictionary, map: &BTreeMap<String, String>) -> Result<Font> {
    let base = name_str(resolve(doc, dict.get(b"BaseFont")?)?)?;
    let stripped = strip_subset_tag(&base);
    let name = map.get(&stripped).cloned().unwrap_or(stripped);
    let subtype = name_str(dict.get(b"Subtype")?)?;
    let tounicode = match dict.get(b"ToUnicode") {
        Ok(o) => parse_tounicode(&decode_stream(doc, resolve(doc, o)?.as_stream()?)?)?,
        Err(_) => bail!("font {base} lacks ToUnicode"),
    };
    if subtype == "Type0" {
        let enc = name_str(dict.get(b"Encoding")?)?;
        anyhow::ensure!(enc == "Identity-H", "Type0 encoding {enc} unsupported");
        let descendants = resolve(doc, dict.get(b"DescendantFonts")?)?.as_array()?;
        let desc = resolve(doc, &descendants[0])?.as_dict()?;
        let dw = match desc.get(b"DW") {
            Ok(o) => num(resolve(doc, o)?)?,
            Err(_) => 1000.0,
        };
        let widths = match desc.get(b"W") {
            Ok(o) => parse_cid_widths(resolve(doc, o)?.as_array()?, doc)?,
            Err(_) => HashMap::new(),
        };
        return Ok(Font {
            name,
            two_byte: true,
            dw,
            widths,
            tounicode,
        });
    }
    let first = num(resolve(doc, dict.get(b"FirstChar")?)?)? as u32;
    let arr = resolve(doc, dict.get(b"Widths")?)?.as_array()?;
    let mut widths = HashMap::new();
    for (i, w) in arr.iter().enumerate() {
        widths.insert(first + i as u32, num(resolve(doc, w)?)?);
    }
    Ok(Font {
        name,
        two_byte: false,
        dw: 0.0,
        widths,
        tounicode,
    })
}

fn strip_subset_tag(base: &str) -> String {
    let bytes = base.as_bytes();
    if bytes.len() > 7 && bytes[6] == b'+' && bytes[..6].iter().all(u8::is_ascii_uppercase) {
        return base[7..].to_string();
    }
    base.to_string()
}

fn parse_cid_widths(arr: &[Object], doc: &Document) -> Result<HashMap<u32, f64>> {
    let mut widths = HashMap::new();
    let mut i = 0;
    while i < arr.len() {
        let start = num(resolve(doc, &arr[i])?)? as u32;
        let next = resolve(doc, &arr[i + 1])?;
        if let Ok(list) = next.as_array() {
            for (j, w) in list.iter().enumerate() {
                widths.insert(start + j as u32, num(resolve(doc, w)?)?);
            }
            i += 2;
        } else {
            let end = num(next)? as u32;
            let w = num(resolve(doc, &arr[i + 2])?)?;
            for code in start..=end {
                widths.insert(code, w);
            }
            i += 3;
        }
    }
    Ok(widths)
}

fn parse_tounicode(bytes: &[u8]) -> Result<HashMap<u32, String>> {
    let text = String::from_utf8_lossy(bytes);
    let tokens = cmap_tokens(&text);
    let mut map = HashMap::new();
    let mut i = 0;
    while i < tokens.len() {
        match tokens[i].as_str() {
            "beginbfchar" => i = parse_bfchar(&tokens, i + 1, &mut map)?,
            "beginbfrange" => i = parse_bfrange(&tokens, i + 1, &mut map)?,
            _ => i += 1,
        }
    }
    Ok(map)
}

fn cmap_tokens(text: &str) -> Vec<String> {
    let mut tokens = vec![];
    let mut rest = text;
    while let Some(start) = rest.find(|c: char| !c.is_whitespace()) {
        rest = &rest[start..];
        let token = if rest.starts_with('<') {
            let end = rest.find('>').map_or(rest.len(), |e| e + 1);
            &rest[..end]
        } else if rest.starts_with('[') || rest.starts_with(']') {
            &rest[..1]
        } else {
            let end = rest
                .find(|c: char| c.is_whitespace() || c == '<' || c == '[' || c == ']')
                .unwrap_or(rest.len());
            &rest[..end]
        };
        tokens.push(token.to_string());
        rest = &rest[token.len()..];
    }
    tokens
}

fn parse_bfchar(tokens: &[String], mut i: usize, map: &mut HashMap<u32, String>) -> Result<usize> {
    while tokens[i] != "endbfchar" {
        let code = hex_u32(&tokens[i])?;
        map.insert(code, hex_utf16(&tokens[i + 1])?);
        i += 2;
    }
    Ok(i + 1)
}

fn parse_bfrange(tokens: &[String], mut i: usize, map: &mut HashMap<u32, String>) -> Result<usize> {
    while tokens[i] != "endbfrange" {
        let lo = hex_u32(&tokens[i])?;
        let hi = hex_u32(&tokens[i + 1])?;
        if tokens[i + 2] == "[" {
            i += 3;
            for code in lo..=hi {
                map.insert(code, hex_utf16(&tokens[i])?);
                i += 1;
            }
            anyhow::ensure!(tokens[i] == "]", "bfrange array unterminated");
            i += 1;
        } else {
            let base = hex_u32(&tokens[i + 2])?;
            for code in lo..=hi {
                let ch = char::from_u32(base + (code - lo)).context("bfrange codepoint")?;
                map.insert(code, ch.to_string());
            }
            i += 3;
        }
    }
    Ok(i + 1)
}

fn hex_body(token: &str) -> Result<String> {
    anyhow::ensure!(
        token.starts_with('<') && token.ends_with('>'),
        "expected hex string, got {token}"
    );
    Ok(token[1..token.len() - 1]
        .chars()
        .filter(|c| !c.is_whitespace())
        .collect())
}

fn hex_u32(token: &str) -> Result<u32> {
    Ok(u32::from_str_radix(&hex_body(token)?, 16)?)
}

fn hex_utf16(token: &str) -> Result<String> {
    let body = hex_body(token)?;
    let units: Result<Vec<u16>> = body
        .as_bytes()
        .chunks(4)
        .map(|c| Ok(u16::from_str_radix(std::str::from_utf8(c)?, 16)?))
        .collect();
    Ok(String::from_utf16(&units?)?)
}

pub fn decode_stream(doc: &Document, stream: &lopdf::Stream) -> Result<Vec<u8>> {
    let filters: Vec<String> = match stream.dict.get(b"Filter") {
        Ok(o) => match resolve(doc, o)? {
            Object::Name(n) => vec![String::from_utf8_lossy(n).into_owned()],
            Object::Array(a) => a.iter().map(name_str).collect::<Result<_>>()?,
            other => bail!("Filter {other:?}"),
        },
        Err(_) => vec![],
    };
    let mut data = stream.content.clone();
    for filter in &filters {
        data = match filter.as_str() {
            "FlateDecode" => inflate(&data)?,
            "ASCII85Decode" => ascii85(&data)?,
            other => bail!("filter {other} unsupported"),
        };
    }
    Ok(data)
}

fn inflate(data: &[u8]) -> Result<Vec<u8>> {
    let mut out = vec![];
    ZlibDecoder::new(data).read_to_end(&mut out)?;
    Ok(out)
}

fn ascii85(data: &[u8]) -> Result<Vec<u8>> {
    let mut out = vec![];
    let mut group = vec![];
    for &b in data.iter().filter(|b| !b.is_ascii_whitespace()) {
        if b == b'~' {
            break;
        }
        if b == b'z' && group.is_empty() {
            out.extend_from_slice(&[0, 0, 0, 0]);
            continue;
        }
        anyhow::ensure!((b'!'..=b'u').contains(&b), "ascii85 byte {b}");
        group.push(u32::from(b - b'!'));
        if group.len() == 5 {
            let v = group.iter().fold(0u32, |acc, d| acc * 85 + d);
            out.extend_from_slice(&v.to_be_bytes());
            group.clear();
        }
    }
    if !group.is_empty() {
        let n = group.len();
        anyhow::ensure!(n >= 2, "ascii85 trailing group");
        let mut padded = group.clone();
        padded.resize(5, 84);
        let v = padded.iter().fold(0u32, |acc, d| acc * 85 + d);
        out.extend_from_slice(&v.to_be_bytes()[..n - 1]);
    }
    Ok(out)
}

fn predictor_undo(data: &[u8], parms: &Dictionary, doc: &Document) -> Result<Vec<u8>> {
    let get = |key: &[u8], default: i64| -> Result<i64> {
        match parms.get(key) {
            Ok(o) => Ok(num(resolve(doc, o)?)? as i64),
            Err(_) => Ok(default),
        }
    };
    let predictor = get(b"Predictor", 1)?;
    if predictor == 1 {
        return Ok(data.to_vec());
    }
    anyhow::ensure!(predictor >= 10, "TIFF predictor unsupported");
    let colors = get(b"Colors", 1)? as usize;
    let bpc = get(b"BitsPerComponent", 8)? as usize;
    anyhow::ensure!(bpc == 8, "predictor bpc {bpc} unsupported");
    let columns = get(b"Columns", 1)? as usize;
    let bpp = colors;
    let row_len = columns * colors;
    let mut out = vec![0u8; 0];
    let mut prev = vec![0u8; row_len];
    for chunk in data.chunks(row_len + 1) {
        anyhow::ensure!(chunk.len() == row_len + 1, "predictor row truncated");
        let ftype = chunk[0];
        let mut row = chunk[1..].to_vec();
        unfilter_row(ftype, &mut row, &prev, bpp)?;
        out.extend_from_slice(&row);
        prev = row;
    }
    Ok(out)
}

fn unfilter_row(ftype: u8, row: &mut [u8], prev: &[u8], bpp: usize) -> Result<()> {
    for i in 0..row.len() {
        let left = if i >= bpp { row[i - bpp] } else { 0 };
        let up = prev[i];
        let ul = if i >= bpp { prev[i - bpp] } else { 0 };
        row[i] = match ftype {
            0 => row[i],
            1 => row[i].wrapping_add(left),
            2 => row[i].wrapping_add(up),
            3 => row[i].wrapping_add(((u16::from(left) + u16::from(up)) / 2) as u8),
            4 => row[i].wrapping_add(paeth(left, up, ul)),
            other => bail!("png filter {other}"),
        };
    }
    Ok(())
}

fn paeth(a: u8, b: u8, c: u8) -> u8 {
    let p = i32::from(a) + i32::from(b) - i32::from(c);
    let (pa, pb, pc) = (
        (p - i32::from(a)).abs(),
        (p - i32::from(b)).abs(),
        (p - i32::from(c)).abs(),
    );
    if pa <= pb && pa <= pc {
        a
    } else if pb <= pc {
        b
    } else {
        c
    }
}

fn image_pixels(doc: &Document, stream: &lopdf::Stream) -> Result<(Vec<u8>, u32, u32, usize)> {
    let dict = &stream.dict;
    let width = num(resolve(doc, dict.get(b"Width")?)?)? as u32;
    let height = num(resolve(doc, dict.get(b"Height")?)?)? as u32;
    let bpc = num(resolve(doc, dict.get(b"BitsPerComponent")?)?)? as u32;
    anyhow::ensure!(bpc == 8, "image bpc {bpc} unsupported");
    if dict.get(b"Decode").is_ok() {
        bail!("image Decode array unsupported");
    }
    let cs = name_str(resolve(doc, dict.get(b"ColorSpace")?)?)?;
    let channels = match cs.as_str() {
        "DeviceRGB" => 3,
        "DeviceGray" => 1,
        other => bail!("image color space {other} unsupported"),
    };
    let mut data = decode_stream(doc, stream)?;
    if let Ok(parms) = dict.get(b"DecodeParms") {
        let parms = resolve(doc, parms)?;
        let parms = match parms {
            Object::Array(a) => resolve(doc, a.last().context("empty DecodeParms")?)?.as_dict()?,
            other => other.as_dict()?,
        };
        data = predictor_undo(&data, parms, doc)?;
    }
    let expected = width as usize * height as usize * channels;
    anyhow::ensure!(
        data.len() == expected,
        "image data {} != expected {expected}",
        data.len()
    );
    Ok((data, width, height, channels))
}

fn decode_image(doc: &Document, stream: &lopdf::Stream) -> Result<(String, u32, u32)> {
    let (data, width, height, channels) = image_pixels(doc, stream)?;
    let alpha = match stream.dict.get(b"SMask") {
        Ok(o) => {
            let smask = resolve(doc, o)?.as_stream()?;
            let (sdata, sw, sh, sc) = image_pixels(doc, smask).context("decoding SMask")?;
            anyhow::ensure!(
                sw == width && sh == height && sc == 1,
                "SMask geometry mismatch"
            );
            Some(sdata)
        }
        Err(_) => None,
    };
    let pixels = width as usize * height as usize;
    let mut rgba = Vec::with_capacity(pixels * 4);
    for i in 0..pixels {
        let (r, g, b) = if channels == 3 {
            (data[i * 3], data[i * 3 + 1], data[i * 3 + 2])
        } else {
            (data[i], data[i], data[i])
        };
        let a = alpha.as_ref().map_or(255, |s| s[i]);
        rgba.extend_from_slice(&[r, g, b, a]);
    }
    Ok((hex::encode(Sha256::digest(&rgba)), width, height))
}
