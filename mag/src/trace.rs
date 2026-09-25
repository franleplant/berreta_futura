mod elements;
mod exact;
mod streams;

use std::collections::BTreeMap;

pub(crate) use elements::trace_elements;
pub(crate) use exact::{authored, num};
#[allow(unused_imports)]
pub(crate) use streams::{qc, qo, Color};
pub(crate) use streams::{Element, Face as TextFace, GLYPH_QUANTUM};

const FONT_ALIASES: [(&str, &str, &str); 11] = [
    (
        "Magazine-Serif",
        "SourceSerif4SmText-Regular",
        "source-serif-4/SourceSerif4SmText-Regular.ttf",
    ),
    (
        "Magazine-Serif-Italic",
        "SourceSerif4SmText-It",
        "source-serif-4/SourceSerif4SmText-It.ttf",
    ),
    (
        "Magazine-Serif-Bold",
        "SourceSerif4SmText-Bold",
        "source-serif-4/SourceSerif4SmText-Bold.ttf",
    ),
    (
        "Magazine-Serif-Display-Semi-Bold",
        "SourceSerif4Display-Semibold",
        "source-serif-4/SourceSerif4Display-Semibold.ttf",
    ),
    ("Magazine-Sans", "Inter-Regular", "inter/Inter-Regular.ttf"),
    (
        "Magazine-Sans-Medium",
        "Inter-Medium",
        "inter/Inter-Medium.ttf",
    ),
    (
        "Magazine-Sans-Semi-Bold",
        "Inter-SemiBold",
        "inter/Inter-SemiBold.ttf",
    ),
    ("Magazine-Sans-Bold", "Inter-Bold", "inter/Inter-Bold.ttf"),
    (
        "Magazine-Mono",
        "GeistMono-Regular",
        "geist-mono/GeistMono-Regular.ttf",
    ),
    (
        "Magazine-Mono-Medium",
        "GeistMono-Medium",
        "geist-mono/GeistMono-Medium.ttf",
    ),
    (
        "Magazine-Mono-Semi-Bold",
        "GeistMono-SemiBold",
        "geist-mono/GeistMono-SemiBold.ttf",
    ),
];

pub(crate) fn text_font_map() -> BTreeMap<String, TextFace> {
    FONT_ALIASES
        .iter()
        .map(|(alias, face, file)| {
            let face = TextFace {
                face: face.to_string(),
                file: format!("{}/{file}", crate::typeset::template::FONT_DIR),
            };
            (alias.to_string(), face)
        })
        .collect()
}
