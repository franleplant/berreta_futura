use anyhow::{bail, ensure, Context, Result};
use lopdf::content::Operation;
use lopdf::xref::XrefEntry;
use lopdf::{Document, Object};
use std::cell::RefCell;
use std::collections::HashMap;
use std::marker::PhantomData;

thread_local! {
    static EXACT: RefCell<HashMap<usize, f64>> = RefCell::new(HashMap::new());
}

pub struct Scope<'a> {
    keys: Vec<usize>,
    life: PhantomData<&'a Object>,
}

impl Drop for Scope<'_> {
    fn drop(&mut self) {
        EXACT.with(|m| {
            let mut m = m.borrow_mut();
            for k in &self.keys {
                m.remove(k);
            }
        });
    }
}

fn key(o: &Object) -> usize {
    std::ptr::from_ref(o) as usize
}

pub fn num(o: &Object) -> Result<f64> {
    match o {
        Object::Integer(i) => Ok(*i as f64),
        Object::Real(r) => EXACT
            .with(|m| m.borrow().get(&key(o)).copied())
            .with_context(|| {
                format!("real {r} has no authored decimal: lopdf holds it as f32 and the exact path never bound its token")
            }),
        other => bail!("expected number, got {other:?}"),
    }
}

fn scope<'a>(pairs: Vec<(usize, f64)>) -> Scope<'a> {
    EXACT.with(|m| m.borrow_mut().extend(pairs.iter().copied()));
    Scope {
        keys: pairs.into_iter().map(|(k, _)| k).collect(),
        life: PhantomData,
    }
}

fn reals_in<'o>(o: &'o Object, out: &mut Vec<&'o Object>) {
    match o {
        Object::Real(_) => out.push(o),
        Object::Array(a) => a.iter().for_each(|x| reals_in(x, out)),
        Object::Dictionary(d) => d.iter().for_each(|(_, x)| reals_in(x, out)),
        Object::Stream(s) => s.dict.iter().for_each(|(_, x)| reals_in(x, out)),
        _ => {}
    }
}

fn bind(reals: &[&Object], text: &[u8], object: bool, what: &str) -> Result<Vec<(usize, f64)>> {
    let tokens = tokens(text, object).with_context(|| what.to_string())?;
    ensure!(
        tokens.len() == reals.len(),
        "{what}: lopdf holds {} reals, the authored text carries {}",
        reals.len(),
        tokens.len()
    );
    reals
        .iter()
        .zip(tokens)
        .map(|(o, t)| {
            let exact: f64 = t.parse()?;
            ensure!(
                matches!(o, Object::Real(r) if r.to_bits() == t.parse::<f32>()?.to_bits()),
                "{what}: authored {t} is not the real lopdf parsed there ({o:?})"
            );
            Ok((key(o), exact))
        })
        .collect()
}

pub fn content<'a>(ops: &'a [Operation], text: &[u8]) -> Result<Scope<'a>> {
    let mut reals = vec![];
    ops.iter()
        .flat_map(|op| &op.operands)
        .for_each(|o| reals_in(o, &mut reals));
    Ok(scope(bind(&reals, text, false, "content stream")?))
}

pub fn authored<'a>(doc: &'a Document, raw: &[u8]) -> Result<Scope<'a>> {
    let mut pairs = vec![];
    let mut containers = HashMap::new();
    for (&(n, g), o) in &doc.objects {
        let mut reals = vec![];
        reals_in(o, &mut reals);
        if reals.is_empty() {
            continue;
        }
        let what = format!("object {n} {g}");
        pairs.extend(match doc.reference_table.get(n) {
            Some(XrefEntry::Normal { offset, .. }) => {
                let text = raw
                    .get(*offset as usize..)
                    .context("xref offset past the file")?;
                bind(&reals, text, true, &what)?
            }
            Some(XrefEntry::Compressed { container, index }) => {
                if !containers.contains_key(container) {
                    containers.insert(*container, object_stream(doc, *container)?);
                }
                let (bytes, spans): &Spans = &containers[container];
                let (a, b) = *spans.get(usize::from(*index)).with_context(|| {
                    format!("{what}: object stream {container} has no index {index}")
                })?;
                bind(&reals, &bytes[a..b], true, &what)?
            }
            _ => bail!("{what} carries reals but no xref entry locates its authored text"),
        });
    }
    Ok(scope(pairs))
}

type Spans = (Vec<u8>, Vec<(usize, usize)>);

fn object_stream(doc: &Document, id: u32) -> Result<Spans> {
    let stream = doc
        .get_object((id, 0))
        .and_then(Object::as_stream)
        .with_context(|| format!("object stream {id} was not retained by lopdf, so the authored decimals of its objects cannot be recovered"))?;
    let bytes = super::streams::decode_stream(doc, stream)?;
    let first = usize::try_from(stream.dict.get(b"First")?.as_i64()?)?;
    let head = std::str::from_utf8(bytes.get(..first).context("object stream /First")?)?;
    let offsets: Vec<usize> = head
        .split_ascii_whitespace()
        .skip(1)
        .step_by(2)
        .map(|t| Ok(first + t.parse::<usize>()?))
        .collect::<Result<_>>()?;
    let ends = offsets.iter().skip(1).copied().chain([bytes.len()]);
    let spans = offsets.iter().copied().zip(ends).collect::<Vec<_>>();
    ensure!(
        spans.iter().all(|(a, b)| a <= b && *b <= bytes.len()),
        "object stream {id}: offsets out of order"
    );
    Ok((bytes, spans))
}

fn regular(c: u8) -> bool {
    !c.is_ascii_whitespace() && c != 0 && !b"()<>[]{}/%".contains(&c)
}

fn is_real(t: &[u8]) -> bool {
    t.contains(&b'.') && t.iter().all(|c| c.is_ascii_digit() || b".+-".contains(c))
}

fn tokens(b: &[u8], object: bool) -> Result<Vec<&str>> {
    let (mut out, mut i) = (vec![], 0);
    while i < b.len() {
        let skip = |i: usize, stop: &dyn Fn(u8) -> bool| {
            i + b[i..].iter().position(|c| stop(*c)).unwrap_or(b.len() - i)
        };
        i = match b[i] {
            b'%' => skip(i, &|c| c == b'\r' || c == b'\n'),
            b'(' => string_end(b, i)?,
            b'<' if b.get(i + 1) == Some(&b'<') => i + 2,
            b'<' => skip(i, &|c| c == b'>') + 1,
            b'/' => skip(i + 1, &|c| !regular(c)),
            c if !regular(c) => i + 1,
            _ => {
                let end = skip(i, &|c| !regular(c));
                match &b[i..end] {
                    b"stream" | b"endobj" if object => break,
                    b"BI" => bail!("inline image: the exact path does not lex BI ... ID ... EI"),
                    t if is_real(t) => out.push(std::str::from_utf8(t)?),
                    _ => {}
                }
                end
            }
        };
    }
    Ok(out)
}

fn string_end(b: &[u8], start: usize) -> Result<usize> {
    let (mut depth, mut i) = (0, start);
    while i < b.len() {
        match b[i] {
            b'\\' => i += 1,
            b'(' => depth += 1,
            b')' => {
                depth -= 1;
                if depth == 0 {
                    return Ok(i + 1);
                }
            }
            _ => {}
        }
        i += 1;
    }
    bail!("unterminated literal string at byte {start}")
}

#[cfg(test)]
pub fn parsed(text: &str) -> &'static Object {
    let text = format!("{text} x");
    let ops = lopdf::content::Content::decode(text.as_bytes()).unwrap();
    let ops: &'static [Operation] = Box::leak(ops.operations.into_boxed_slice());
    std::mem::forget(content(ops, text.as_bytes()).unwrap());
    &ops[0].operands[0]
}

#[cfg(test)]
mod tests {
    use super::*;

    const OBJECTS: [&str; 4] = [
        "<</Type/Catalog/Pages 2 0 R>>",
        "<</Type/Pages/Kids[3 0 R 4 0 R]/Count 2>>",
        "<</Type/Page/Parent 2 0 R/MediaBox [ 0 0 419.527559 595.275591 ]>>",
        "<</Type/Page/Parent 2 0 R/MediaBox [ 0 0 419.5276 595.2756 ]/Note (1.5 [2.5])>>",
    ];

    fn classic() -> Vec<u8> {
        let mut out = b"%PDF-1.7\n".to_vec();
        let mut offsets = vec![];
        for (i, o) in OBJECTS.iter().enumerate() {
            offsets.push(out.len());
            out.extend(format!("{} 0 obj\n{o}\nendobj\n", i + 1).bytes());
        }
        let xref = out.len();
        out.extend(b"xref\n0 5\n0000000000 65535 f \n");
        for o in offsets {
            out.extend(format!("{o:010} 00000 n \n").bytes());
        }
        out.extend(format!("trailer\n<</Size 5/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n").bytes());
        out
    }

    fn compressed() -> Vec<u8> {
        let (mut head, mut body) = (String::new(), String::new());
        for (i, o) in OBJECTS.iter().enumerate() {
            head.push_str(&format!("{} {} ", i + 1, body.len()));
            body.push_str(&format!("{o}\n"));
        }
        let data = format!("{head}\n{body}");
        let mut out = b"%PDF-1.7\n".to_vec();
        let container = out.len();
        out.extend(
            format!(
                "5 0 obj\n<</Type/ObjStm/N 4/First {}/Length {}>>\nstream\n{data}\nendstream\nendobj\n",
                head.len() + 1,
                data.len()
            )
            .bytes(),
        );
        let xref = out.len();
        let mut rows = vec![[0u8, 0, 0, 0, 0, 255, 255]];
        for i in 0..4u8 {
            rows.push([2, 0, 0, 0, 5, 0, i]);
        }
        for at in [container, xref] {
            let b = u32::try_from(at).unwrap().to_be_bytes();
            rows.push([1, b[0], b[1], b[2], b[3], 0, 0]);
        }
        let rows = rows.concat();
        out.extend(
            format!(
                "6 0 obj\n<</Type/XRef/Size 7/W[1 4 2]/Root 1 0 R/Length {}>>\nstream\n",
                rows.len()
            )
            .bytes(),
        );
        out.extend(rows);
        out.extend(format!("\nendstream\nendobj\nstartxref\n{xref}\n%%EOF\n").bytes());
        out
    }

    fn media_boxes(raw: &[u8]) -> Result<Vec<Vec<f64>>> {
        let doc = Document::load_mem(raw)?;
        let _exact = authored(&doc, raw)?;
        doc.get_pages()
            .values()
            .map(|id| {
                let b = doc.get_dictionary(*id)?.get(b"MediaBox")?.as_array()?;
                b.iter().map(num).collect()
            })
            .collect()
    }

    #[test]
    fn the_010_media_boxes_keep_their_authored_decimals_in_plain_and_object_streams() {
        let doc = Document::load_mem(&compressed()).unwrap();
        assert!(matches!(
            doc.reference_table.get(3),
            Some(XrefEntry::Compressed { container: 5, .. })
        ));
        for raw in [classic(), compressed()] {
            let boxes = media_boxes(&raw).unwrap();
            assert_eq!(boxes[0], [0.0, 0.0, 419.527559, 595.275591]);
            assert_eq!(boxes[1], [0.0, 0.0, 419.5276, 595.2756]);
            let scale = 595.2756 / boxes[0][3];
            assert!((scale - 1.000_000_015_1).abs() < 1e-10, "{scale}");
        }
        let f32 = |t: &str| f64::from(t.parse::<f32>().unwrap());
        let f32_scale = f32("595.2756") / f32("595.275591");
        assert_eq!(f32_scale, 1.0, "the known-bad f32 path must still diverge");
        assert_ne!(f32("419.527559"), 419.527559);
    }

    #[test]
    fn a_real_whose_f32_crosses_a_quantum_boundary_keeps_its_exact_quantum() {
        let exact = num(parsed("300.004999")).unwrap();
        assert_eq!(super::super::streams::qc(exact), 30000);
        let f32 = f64::from("300.004999".parse::<f32>().unwrap());
        assert_eq!(super::super::streams::qc(f32), 30001);
    }

    #[test]
    fn a_real_the_exact_path_never_bound_fails_loud() {
        let e = num(&Object::Real(1.5)).unwrap_err().to_string();
        assert!(e.contains("no authored decimal"), "{e}");
        let doc = Document::load_mem(&classic()).unwrap();
        let e = authored(&doc, b"%PDF-1.7\n").err().unwrap().to_string();
        assert!(e.contains("xref offset past the file"), "{e}");
        let moved = String::from_utf8(classic())
            .unwrap()
            .replace("419.527559", "419.600000");
        let e = authored(&doc, moved.as_bytes()).err().unwrap().to_string();
        assert!(e.contains("is not the real lopdf parsed there"), "{e}");
    }
}
