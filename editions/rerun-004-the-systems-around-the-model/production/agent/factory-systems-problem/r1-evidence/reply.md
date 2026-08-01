result: changes_required
findings:
  - severity: major
    article: factory-systems-problem
    locator: "Don't make the service bus non-deterministic | The first hot take is a separate post and is not one of the three collected here. | 1"
    repair_from: "- | The captures carry no dates, so the order they were written in cannot be recovered here. | 1"
    category: invented_claim
    note: |
      The extraction supports only that a first hot take exists and had landed:
      "second hot take, as it seems the first hot take landed." Nothing in any of
      the three extractions identifies that first hot take or rules out the two
      other collected posts as candidates for it. Neither collected post is
      dated, neither self-identifies, and both are short opinion posts of the
      kind the phrase describes. The editor's note nonetheless asserts a
      definite negative - that it "is not one of the three collected here" -
      which the pinned sources cannot establish. It also contradicts the
      article's own earlier disclosure that "the order they were written in
      cannot be recovered here": a magazine that cannot recover the order cannot
      know that an earlier collected post was not the first hot take. The defect
      is structural, since the certainty it borrows is set up in the first
      editor's note, which is where a hedge belongs.
  - severity: minor
    article: factory-systems-problem
    locator: "- | The longer post promised above is not one of the three. | 1"
    category: invented_claim
    note: |
      The source's only relevant words are "ugh. blog post time." The
      extractions carry no date, no title, and no link for the promised post, so
      whether it is among the three captures cannot be checked. The claim is not
      baseless - all three captures are short, and "blog post time" reads as
      prospective - but the software-factories post is on exactly the promised
      subject ("the best practices right now are to build abstractions/pieces
      needed which entails solving non-agent topics"), is the longest of the
      three, and carries footnotes. On the pinned evidence it cannot be excluded,
      and the note excludes it flatly.
  - severity: minor
    article: factory-systems-problem
    locator: "Don't make the service bus non-deterministic | Don't make the service bus non-deterministic | 1"
    category: overstated_furniture
    note: |
      The source's imperative is "don't make the entire service bus
      non-deterministic." The magazine-supplied heading drops "entire", and the
      word is load-bearing: the sentence before it in the same source tells the
      reader to "have a job invoke an agent as a process", that is, to keep the
      non-deterministic agent inside an otherwise deterministic bus. Read alone,
      the heading is a blanket prohibition on non-determinism in the bus, which
      is stronger advice than the source gives. Mitigated by the full sentence
      appearing verbatim at the end of the same section.
scores:
  claim_support: 4
  qualification_survival: 4
  quote_accuracy: 5
  attribution: 5
notes: |
  I read all three extractions in full before the manuscript, then diffed each
  manuscript passage against its extraction word by word after normalising curly
  quotes and stripping footnote markers. The three body passages - the opening
  paragraph, the software-factories section with its three footnotes, and the
  service-bus section with its footnote - are word-for-word identical to
  `factories-are-not-a-token-or-llm-problem-ba5fabbf`,
  `software-factories-are-super-real-but-the-factor-ab8ad3ab`, and
  `do-not-make-the-service-bus-non-deterministic-3a92442c` respectively. No
  sentence is invented, rewritten, or reordered within a post; every number and
  name checks out ("last six months", "<10 people", "the last two years", n8n,
  @dotnet, mass transit, nservicebus, wcf, @temporalio); footnote text and
  attachment points match; every hedge in the body survives, including "but we
  need to be realistic", "(but it is a piece of the puzzle)", "(and
  realistically failing)", and "not great tech impl but the theory / education
  is generally on point". Nothing was omitted from any extraction. Everything I
  flagged sits in editorially added furniture rather than in the author's prose.
  What I could not check: authorship and the byline, since the extractions carry
  no byline and Huntley's name comes from the brief's inputs rather than the
  sources; publication dates and ordering, which the extractions genuinely do
  not carry, as the article itself says; and the existence, length, and identity
  of the two posts referred to but not collected - the promised blog post and
  the first hot take - which is the basis of the two invented_claim findings. I
  did not flag the heading "Software factories are super real" for dropping "but
  we need to be realistic": the source asserts that clause on its own terms and
  the hedge follows in the section's first sentence.
