use mag::critic::metrics;

#[test]
fn ordered_map_preserves_order_and_reports_the_first_failure() {
    let items: Vec<usize> = (0..25).collect();
    let doubled = metrics::ordered_map(|value| Ok(value * 2), &items, None).expect("no item fails");
    assert_eq!(
        doubled,
        items.iter().map(|value| value * 2).collect::<Vec<_>>()
    );
    let failed = metrics::ordered_map(
        |value| {
            if *value == 7 || *value == 19 {
                anyhow::bail!("item {value}")
            }
            Ok(*value)
        },
        &items,
        None,
    );
    let error = failed.expect_err("two items fail");
    assert_eq!(error.to_string(), "item 7");
}
