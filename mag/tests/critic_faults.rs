use mag::impose;

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
