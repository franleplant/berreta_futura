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
        vec![(Some(56), Some(1)), (Some(2), Some(55))],
        "the cover wrap prints both sides: outside covers, then the credits and the inside back"
    );
    for pages in 4..=64 {
        let wrap = impose::cover_wrap_plan(pages).unwrap();
        assert_eq!(wrap[1], (Some(2), Some(pages - 1)), "{pages} pages");
    }
}
