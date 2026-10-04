#[path = "../src/model/shared.rs"]
#[allow(dead_code)]
pub mod shared;

mod model {
    pub use super::shared;
}

#[path = "../src/trace/exact.rs"]
#[allow(dead_code)]
pub mod exact;
#[path = "../src/trace/streams.rs"]
#[allow(dead_code, clippy::new_without_default)]
pub mod streams;

#[path = "../src/trace/elements.rs"]
#[allow(dead_code)]
pub mod elements;

mod trace {
    pub use super::elements::trace_elements;
    pub use super::exact::{authored, num};
    #[allow(unused_imports)]
    pub use super::streams::{Color, Element, Face as TextFace, GLYPH_QUANTUM};
}

#[path = "../src/impose.rs"]
#[allow(dead_code)]
pub mod impose;

#[path = "../src/critic/metrics.rs"]
#[allow(dead_code)]
pub mod metrics;

#[path = "../src/critic/text.rs"]
#[allow(dead_code)]
pub mod text;

#[path = "../src/critic/inspect.rs"]
#[allow(dead_code)]
pub mod inspect;

mod critic {
    #[allow(unused_imports)]
    pub use super::inspect;
    pub use super::{metrics, text};
}

#[allow(dead_code)]
mod oracle;
#[path = "../src/critic/rules.rs"]
#[allow(dead_code)]
mod rules;

#[test]
fn authored_expectations_follow_the_imposition_plan() {
    let all = impose::imposed_reader_page_plan(&(1..=56).collect::<Vec<_>>());
    assert_eq!(all[0], (Some(56), Some(1)));
    assert_eq!(
        all[1],
        (Some(2), Some(55)),
        "booklet side 2 carries both inside covers"
    );
    let cover = impose::cover_wrap_plan(56).unwrap();
    assert_eq!(
        cover,
        vec![(Some(56), Some(1))],
        "the cover wrap is one outside side"
    );
    for pages in 4..=64 {
        let wrap = impose::cover_wrap_plan(pages).unwrap();
        let inside = [Some(2), Some(pages - 1)];
        assert!(
            wrap.iter()
                .all(|(l, r)| !(inside.contains(l) && inside.contains(r))),
            "cover-booklet-inside-not-blank is unreachable at {pages} pages"
        );
    }
}
