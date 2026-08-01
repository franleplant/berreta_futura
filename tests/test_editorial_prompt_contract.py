from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_opening_editorial_prompt_keeps_the_house_contract() -> None:
    prompt = (ROOT / "prompts" / "opening-editorial.md").read_text(encoding="utf-8")
    normalized = " ".join(prompt.lower().split())

    assert "`docs/writing_rules.md`" in normalized
    assert "emergent narrative" in normalized
    assert "prose table of contents" in normalized
    assert "never summarize the articles one by one" in normalized
    assert "visible title" in normalized
    assert "byline" in normalized
    assert "original editor text" in normalized
    assert "one rendered a5 page" in normalized


def test_editorial_policy_and_writing_method_assign_the_same_default() -> None:
    policy = (ROOT / "docs" / "EDITORIAL_POLICY.md").read_text(encoding="utf-8")
    rules = (ROOT / "docs" / "WRITING_RULES.md").read_text(encoding="utf-8")
    normalized_policy = " ".join(policy.lower().split())
    normalized_rules = " ".join(rules.lower().split())

    assert "`docs/WRITING_RULES.md`" in policy
    # The writing method is no longer an opt-in default for two piece kinds: it
    # governs everything the magazine publishes, and a mode's prompt may only
    # add to it.  The scope sentence is pinned so a later narrowing of it has to
    # be a deliberate edit here too.
    assert (
        "it applies to everything the magazine publishes: source articles in "
        "every content mode, in-a-nutshell explainers, opening editorials, "
        "captions, and social posts."
    ) in normalized_rules
    assert "none may suspend these." in normalized_rules
    assert "must not summarize the articles one by one" in normalized_policy
    assert "prose table of contents" in normalized_policy
    assert "a human must approve" in normalized_policy

    expected_rules = (
        "avoid clichés and familiar figures of speech.",
        "prefer short, common words.",
        "cut every word that does no work.",
        "use the active voice.",
        "prefer plain english to jargon.",
        "break any rule when breaking it makes the writing clearer.",
    )
    for number, rule in enumerate(expected_rules, start=1):
        assert f"{number}. {rule}" in normalized_rules
