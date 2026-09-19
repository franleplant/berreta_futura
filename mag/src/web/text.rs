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
