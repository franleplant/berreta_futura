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

#[test]
fn the_interior_opens_with_the_credits_on_a_sheet_of_their_own_and_splits_on_a_sheet() {
    let plan = impose::section_plan(108, "interior").unwrap();
    assert_eq!(
        plan[0],
        (None, Some(2)),
        "the outermost sheet carries only the credits"
    );
    assert_eq!(plan[1], (None, None), "and nothing on its inside");
    let mut printed: Vec<usize> = plan.iter().flat_map(|(l, r)| [*l, *r]).flatten().collect();
    printed.sort_unstable();
    assert_eq!(
        printed,
        std::iter::once(2).chain(3..=106).collect::<Vec<_>>()
    );
    let [first, second] = impose::split_sheets(&plan, |_| 1);
    assert!(first.len() % 2 == 0 && first.len().abs_diff(second.len()) <= 2);
    assert_eq!([first, second].concat(), plan);
    let [heavy, rest] = impose::split_sheets(&plan, |page| if page == 2 { 10_000 } else { 1 });
    assert_eq!(heavy.len(), 2, "one heavy sheet weighs as much as the rest");
    assert_eq!(rest.len(), plan.len() - 2);
}
