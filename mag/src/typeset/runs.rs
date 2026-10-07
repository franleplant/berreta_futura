use crate::critic::text::Run;
use typst::layout::{Frame, FrameItem, Point, Transform};
use typst_layout::PagedDocument;

pub fn pages(document: &PagedDocument) -> Vec<Vec<Run>> {
    document
        .pages()
        .iter()
        .map(|page| {
            let mut out = vec![];
            collect(
                &page.frame,
                Transform::identity(),
                page.frame.height().to_pt(),
                &mut out,
            );
            out
        })
        .collect()
}

fn collect(frame: &Frame, base: Transform, height: f64, out: &mut Vec<Run>) {
    for (at, item) in frame.items() {
        let ts = base.pre_concat(Transform::translate(at.x, at.y));
        match item {
            FrameItem::Group(group) => {
                collect(&group.frame, ts.pre_concat(group.transform), height, out);
            }
            FrameItem::Text(text) => {
                let origin = Point::zero().transform(ts);
                out.push(Run {
                    text: text.text.to_string(),
                    x: origin.x.to_pt(),
                    y: height - origin.y.to_pt(),
                    width: text.width().to_pt(),
                    size: text.size.to_pt() * ts.kx.get().hypot(ts.sy.get()),
                    mono: text.font.info().family == "Geist Mono",
                });
            }
            _ => {}
        }
    }
}
