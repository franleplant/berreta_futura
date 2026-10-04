use std::path::Path;

#[test]
fn the_brand_files_are_committed_and_themeable() {
    let brand = Path::new(env!("CARGO_MANIFEST_DIR")).join("assets/brand");
    for file in ["wordmark.svg", "mark.svg", "mark-square.svg"] {
        let svg = std::fs::read_to_string(brand.join(file)).expect("brand file exists");
        assert!(
            svg.contains("var(--paper, #ffffff)") && !svg.contains("stroke"),
            "{file}"
        );
    }
    assert!(std::fs::read_to_string(brand.join("README.md"))
        .expect("the brand spec exists")
        .contains("tools/logo.py"));
}
