use crate::typeset::content::{File, Tree};
use anyhow::{bail, ensure, Context, Result};
use std::collections::{BTreeMap, BTreeSet, HashSet};

const OPEN: char = '\u{fdd0}';
const CLOSE: char = '\u{fdd1}';
const END: char = '\u{fdd2}';
const CUT: &str = "#colbreak()\n";
const FLOAT: &str = "\n  float: true,";
const KEPT: &str = "\n  float: false,";

pub fn hole(kind: char, id: usize) -> String {
    format!("{OPEN}{kind}{id}{CLOSE}")
}

pub fn unit(id: usize, text: &str) -> String {
    format!("{}{text}{END}", hole('t', id))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Splice {
    pub from: usize,
    pub to: usize,
    pub with: &'static str,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Decisions {
    pub closing: Option<usize>,
    pub floats: BTreeMap<usize, bool>,
    pub cuts: BTreeSet<usize>,
    pub text: BTreeMap<usize, BTreeSet<Splice>>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Mark {
    pub kind: char,
    pub id: usize,
    pub at: usize,
    pub end: usize,
    pub splices: Vec<Splice>,
}

pub struct Rendered {
    pub text: String,
    pub marks: Vec<Mark>,
}

fn spliced(base: &str, splices: &[Splice]) -> Result<String> {
    let mut out = String::with_capacity(base.len());
    let mut at = 0;
    for s in splices {
        ensure!(
            at <= s.from && s.from <= s.to && s.to <= base.len(),
            "layout decisions overlap in the text {base:?}"
        );
        out.push_str(&base[at..s.from]);
        out.push_str(s.with);
        at = s.to;
    }
    out.push_str(&base[at..]);
    Ok(out)
}

fn clean(segment: &str) -> Result<&str> {
    if let Some(at) = segment.find([OPEN, CLOSE, END]) {
        let found = segment[at..].chars().next().map_or(0, |c| c as u32);
        let near: String = segment[at..].chars().take(40).collect();
        bail!("the reserved layout character U+{found:04X} appears in the text, near {near:?}");
    }
    Ok(segment)
}

pub fn render(source: &str, lead: &str, d: &Decisions) -> Result<Rendered> {
    let mut text = String::from(lead);
    let mut marks = Vec::new();
    let mut rest = source;
    while let Some(i) = rest.find(OPEN) {
        text.push_str(clean(&rest[..i])?);
        let (token, tail) = rest[i + OPEN.len_utf8()..]
            .split_once(CLOSE)
            .context("an unterminated hole in the emitted markup")?;
        rest = tail;
        let (kind, id) = token
            .split_at_checked(1)
            .filter(|(_, id)| !id.is_empty() && id.bytes().all(|b| b.is_ascii_digit()))
            .with_context(|| {
                format!(
                    "the reserved layout character U+FDD0 appears in the text, before {:?}",
                    rest.chars().take(40).collect::<String>()
                )
            })?;
        let id: usize = id.parse().with_context(|| format!("hole {token:?}"))?;
        let at = text.len();
        let mut splices = Vec::new();
        match kind {
            "t" => {
                let (base, tail) = rest
                    .split_once(END)
                    .context("an unterminated text unit in the emitted markup")?;
                rest = tail;
                splices = d.text.get(&id).into_iter().flatten().copied().collect();
                text.push_str(&spliced(clean(base)?, &splices)?);
            }
            "c" if d.cuts.contains(&id) => text.push_str(CUT),
            "f" => text.push_str(match d.floats.get(&id) {
                Some(true) => FLOAT,
                Some(false) => KEPT,
                None => "",
            }),
            "g" => text.push_str(&d.closing.map_or("none".to_string(), |n| n.to_string())),
            "c" => {}
            other => bail!("unknown hole kind {other:?}"),
        }
        let kind = kind.chars().next().unwrap_or(' ');
        let end = text.len();
        marks.push(Mark {
            kind,
            id,
            at,
            end,
            splices,
        });
    }
    text.push_str(clean(rest)?);
    ensure!(
        !text.contains([OPEN, CLOSE, END]),
        "a layout sentinel survived rendering"
    );
    Ok(Rendered { text, marks })
}

#[derive(Clone, Copy)]
pub enum Choice {
    Cut(usize),
    Float(usize, bool),
}

impl Decisions {
    pub fn splice(&mut self, unit: usize, splice: Splice) {
        self.text.entry(unit).or_default().insert(splice);
    }

    pub fn choose(&mut self, choice: Choice) {
        match choice {
            Choice::Cut(id) => {
                self.cuts.insert(id);
            }
            Choice::Float(id, on) => {
                self.floats.insert(id, on);
            }
        }
    }

    fn missing(&self, found: &HashSet<(char, usize)>) -> Vec<String> {
        let wanted = self
            .cuts
            .iter()
            .map(|id| ('c', *id))
            .chain(self.floats.keys().map(|id| ('f', *id)))
            .chain(self.text.keys().map(|id| ('t', *id)));
        let mut out: Vec<String> = wanted
            .filter(|key| !found.contains(key))
            .map(|(kind, id)| format!("{kind}{id}"))
            .collect();
        if self.closing.is_some() && !found.iter().any(|(kind, _)| *kind == 'g') {
            out.push("the closing signature".to_string());
        }
        out
    }
}

pub fn render_tree(tree: &Tree, lead: &str) -> Result<Vec<(String, Rendered)>> {
    let files = tree
        .files
        .iter()
        .map(|file| {
            Ok((
                file.path.clone(),
                render(&file.source, lead, &tree.decisions)
                    .with_context(|| format!("in {}", file.path))?,
            ))
        })
        .collect::<Result<Vec<_>>>()?;
    let found = files
        .iter()
        .flat_map(|(_, r)| r.marks.iter().map(|m| (m.kind, m.id)))
        .collect();
    let missing = tree.decisions.missing(&found);
    ensure!(
        missing.is_empty(),
        "layout decisions with no anchor in the emitted markup: {}",
        missing.join(", ")
    );
    Ok(files)
}

impl Tree {
    pub fn flat(&self) -> Result<Tree> {
        let files = render_tree(self, "")?
            .into_iter()
            .map(|(path, r)| File {
                path,
                source: r.text,
            })
            .collect();
        Ok(Tree {
            files,
            figures: self.figures.clone(),
            decisions: Decisions::default(),
        })
    }
}

fn base_offset(mark: &Mark, at: usize) -> usize {
    let mut delta = 0isize;
    for s in &mark.splices {
        let start = mark.at.saturating_add_signed(delta) + s.from;
        let end = start + s.with.len();
        if at >= end {
            delta += s.with.len().cast_signed() - (s.to - s.from).cast_signed();
        } else if at >= start {
            return s.from;
        } else {
            break;
        }
    }
    at.saturating_add_signed(-delta) - mark.at
}

pub fn locate(marks: &[Mark], a: usize, b: usize) -> Result<(usize, usize, usize)> {
    let unit = marks
        .iter()
        .find(|m| m.kind == 't' && m.at <= a && b <= m.end)
        .with_context(|| format!("the edit at {a}..{b} lies outside any text unit"))?;
    Ok((unit.id, base_offset(unit, a), base_offset(unit, b)))
}

pub fn cut_before(marks: &[Mark], at: usize) -> Option<usize> {
    marks
        .iter()
        .rfind(|m| m.kind == 'c' && m.at <= at)
        .map(|m| m.id)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn block(cut: usize, text: usize, words: &str) -> String {
        format!("{}#doc-paragraph[{}]", hole('c', cut), unit(text, words))
    }

    fn layouts() -> [String; 2] {
        let (a, b) = (block(1, 2, "alpha beta"), block(3, 4, "gamma delta"));
        [
            format!("{a}\n\n{b}\n"),
            format!("\n\n  {a}   \n\n\n\t{b}\n\n\n"),
        ]
    }

    fn tree(source: &str, decisions: Decisions) -> Tree {
        Tree {
            files: vec![File {
                path: "main.typ".to_string(),
                source: source.to_string(),
            }],
            decisions,
            ..Tree::default()
        }
    }

    fn decided() -> Decisions {
        Decisions {
            cuts: BTreeSet::from([3]),
            text: BTreeMap::from([(
                4,
                BTreeSet::from([Splice {
                    from: 5,
                    to: 6,
                    with: "~",
                }]),
            )]),
            ..Decisions::default()
        }
    }

    #[test]
    fn a_decision_lands_on_its_block_whatever_the_emitted_formatting() {
        for source in layouts() {
            let rendered = &render_tree(&tree(&source, decided()), "").expect("renders")[0].1;
            assert_eq!(rendered.text.matches("#colbreak()").count(), 1);
            assert!(rendered
                .text
                .contains("#colbreak()\n#doc-paragraph[gamma~delta]"));
            assert!(rendered.text.contains("#doc-paragraph[alpha beta]"));
        }
    }

    #[test]
    fn a_rendered_offset_maps_back_to_its_unit_and_base_offset_whatever_the_formatting() {
        for source in layouts() {
            let rendered = &render_tree(&tree(&source, decided()), "").expect("renders")[0].1;
            let at = |needle: &str| rendered.text.find(needle).expect("the text is there");
            let (tilde, delta) = (at("~"), at("delta"));
            assert_eq!(
                locate(&rendered.marks, tilde, tilde + 1).unwrap(),
                (4, 5, 6)
            );
            assert_eq!(
                locate(&rendered.marks, delta, delta + 5).unwrap(),
                (4, 6, 11)
            );
            assert!(locate(&rendered.marks, 0, 1).is_err());
            assert_eq!(cut_before(&rendered.marks, tilde), Some(3));
            assert_eq!(cut_before(&rendered.marks, at("beta")), Some(1));
        }
    }

    #[test]
    fn a_decision_with_no_anchor_in_the_markup_is_an_error_not_a_silent_no_op() {
        let [source, _] = layouts();
        for stray in [
            Decisions {
                closing: Some(4),
                ..Decisions::default()
            },
            Decisions {
                cuts: BTreeSet::from([99]),
                ..Decisions::default()
            },
            Decisions {
                floats: BTreeMap::from([(99, true)]),
                ..Decisions::default()
            },
            Decisions {
                text: BTreeMap::from([(99, BTreeSet::new())]),
                ..Decisions::default()
            },
        ] {
            let error = render_tree(&tree(&source, stray), "")
                .err()
                .expect("refused");
            assert!(error.to_string().contains("no anchor"), "{error}");
        }
        let signed = format!("#closing-signature({})\n", hole('g', 7));
        let closing = Decisions {
            closing: Some(4),
            ..Decisions::default()
        };
        let rendered = &render_tree(&tree(&signed, closing), "").expect("anchored")[0].1;
        assert_eq!(rendered.text, "#closing-signature(4)\n");
    }

    #[test]
    fn overlapping_splices_are_refused() {
        let overlap = BTreeSet::from([
            Splice {
                from: 0,
                to: 4,
                with: "",
            },
            Splice {
                from: 2,
                to: 3,
                with: "x",
            },
        ]);
        let decisions = Decisions {
            text: BTreeMap::from([(2, overlap)]),
            ..Decisions::default()
        };
        assert!(render_tree(&tree(&layouts()[0], decisions), "").is_err());
    }

    fn refusal(source: &str) -> String {
        let error = render_tree(&tree(source, Decisions::default()), "")
            .err()
            .expect("refused");
        format!("{error:#}")
    }

    #[test]
    fn a_reserved_character_in_prose_or_alt_text_is_refused_naming_the_file() {
        for bad in ['\u{fdd0}', '\u{fdd2}'] {
            for text in [format!("alpha {bad} beta"), format!("{bad}")] {
                let prose = format!("{}#p[{}]", hole('c', 1), unit(2, &text));
                let alt = format!("#figure(alt: \"{text}\")\n{}", unit(3, "caption"));
                let bare = format!("#figure(alt: \"{text}\")\n");
                for source in [prose, alt, bare] {
                    let message = refusal(&source);
                    assert!(message.contains("in main.typ"), "{message}");
                    assert!(
                        message.contains("reserved layout character")
                            || message.contains("unterminated"),
                        "{message}"
                    );
                }
            }
        }
    }

    #[test]
    fn private_use_characters_in_prose_render_verbatim() {
        let text = "a\u{e000}b\u{e002}c";
        let source = format!("{}#p[{}]", hole('c', 1), unit(2, text));
        let rendered =
            &render_tree(&tree(&source, Decisions::default()), "").expect("renders")[0].1;
        assert_eq!(rendered.text, format!("#p[{text}]"));
        let flat = tree(&source, Decisions::default()).flat().expect("flat");
        assert_eq!(flat.files[0].source, format!("#p[{text}]"));
    }

    #[test]
    fn a_sentinel_smuggled_in_by_a_splice_does_not_survive_rendering() {
        let source = unit(2, "alpha");
        let smuggle = Decisions {
            text: BTreeMap::from([(
                2,
                BTreeSet::from([Splice {
                    from: 0,
                    to: 0,
                    with: "\u{fdd2}",
                }]),
            )]),
            ..Decisions::default()
        };
        let error = render_tree(&tree(&source, smuggle), "")
            .err()
            .expect("refused");
        assert!(format!("{error:#}").contains("survived"), "{error:#}");
    }
}
