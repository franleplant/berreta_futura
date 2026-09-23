use crate::model::doc::{educate_reader_quotes, fold_reader_characters};
use std::collections::BTreeSet;

pub fn escape(value: &str, quote: bool) -> String {
    let mut out = value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;");
    if quote {
        out = out.replace('"', "&quot;").replace('\'', "&#x27;");
    }
    out
}

pub fn text(value: &str, settable: &BTreeSet<u32>) -> String {
    escape(
        &fold_reader_characters(&educate_reader_quotes(value), settable),
        false,
    )
}

pub fn verbatim(value: &str, settable: &BTreeSet<u32>) -> String {
    escape(&fold_reader_characters(value, settable), false)
}

pub fn attr(value: &str, settable: &BTreeSet<u32>) -> String {
    escape(&fold_reader_characters(value, settable), true)
}

#[derive(Clone, Copy)]
pub struct Escaper<'a>(pub &'a BTreeSet<u32>);

impl Escaper<'_> {
    pub fn text(self, value: &str) -> String {
        text(value, self.0)
    }

    pub fn verbatim(self, value: &str) -> String {
        verbatim(value, self.0)
    }

    pub fn attr(self, value: &str) -> String {
        attr(value, self.0)
    }
}
