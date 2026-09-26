pub mod inspect;
pub mod metrics;
pub mod rules;
pub mod text;

#[cfg(test)]
mod parity_seam_is_reachable_from_critic {
    use crate::critic::text::page_text;
    use crate::trace::{qc, qo, trace_elements, Color, Element, TextFace, GLYPH_QUANTUM};
    use std::collections::BTreeMap;
    use std::path::Path;

    fn show(s: &str, x_pt: f64, y_pt: f64, size_pt: f64, advance_pt: f64) -> Element {
        let glyphs = s.chars().count().max(2);
        let step = advance_pt / (glyphs as f64 - 1.0);
        let offs = (0..glyphs).map(|i| [qo(step * i as f64), 0]).collect();
        Element::Text {
            s: s.into(),
            font: "seam".into(),
            size: qc(size_pt),
            fill: Color {
                family: "DeviceGray".into(),
                rgb: [0, 0, 0],
            },
            glyphs,
            gids: vec![],
            m: [qc(size_pt), 0, 0, qc(size_pt), qc(x_pt), qc(y_pt)],
            tr: 0,
            clip: vec![],
            origin: [qo(x_pt), qo(y_pt)],
            offs,
            units: s.chars().map(String::from).collect(),
            pen: [qo(step * glyphs as f64), 0],
        }
    }

    #[test]
    fn the_quantizers_reached_through_the_seam_are_the_tracers_own() {
        assert_eq!(qc(1.0), 100);
        assert_eq!(qo(GLYPH_QUANTUM * 8.0), 8);
    }

    #[test]
    fn critic_joins_elements_built_with_the_seams_quantizers() {
        let apart = [
            show("ab", 0.0, 700.0, 10.0, 6.0),
            show("cd", 20.0, 700.0, 10.0, 6.0),
        ];
        let touching = [
            show("ab", 0.0, 700.0, 10.0, 6.0),
            show("cd", 13.0, 700.0, 10.0, 6.0),
        ];
        assert_eq!(page_text(&apart), "ab cd");
        assert_eq!(page_text(&touching), "abcd");
    }

    #[test]
    fn the_trace_entry_point_is_callable_from_critic() {
        let fonts: BTreeMap<String, TextFace> = BTreeMap::new();
        let Err(err) = trace_elements(Path::new("no-such-seam.pdf"), 1, 1, &fonts) else {
            panic!("a missing pdf must fail rather than succeed");
        };
        assert!(format!("{err:#}").contains("no-such-seam.pdf"));
    }
}
