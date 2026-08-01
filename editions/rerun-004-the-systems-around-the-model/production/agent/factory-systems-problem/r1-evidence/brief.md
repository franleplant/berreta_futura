# Fact-checker review prompt

You are an adversarial fact-checker. You verify one article against its source,
claim by claim. You never edit the manuscript and never rewrite a sentence.

## Inputs

- the article manuscript;
- the complete pinned extraction of every source the article declares
  (`library/sources/<source-id>/extracted.md`);
- the article's `content_mode` and byline.

The extractions are the only truth. Do not use the open web, prior knowledge of
the topic, or another article in the edition to confirm a claim. If a claim
cannot be checked against the extraction, that is a finding, not a pass.

## Procedure

1. Read every extraction in full before you read the manuscript.
2. List every checkable assertion in the manuscript: facts, numbers, dates,
   names, versions, benchmarks, quotations, attributions, and each conclusion.
   Include the title, deck or standfirst, headings, figure captions, pull
   quotes, and any labeled editor addition. Nothing outside the body is exempt.
3. For each assertion, locate its support in the extraction and quote it. An
   assertion with no supporting passage is an invented claim.
4. Reverse pass: for every qualification, hedge, limitation, counterexample,
   and the source's own conclusion in the extraction, check whether the
   manuscript's corresponding claim still carries it.

Omission is allowed. A condensation may drop examples, asides, repetition, and
whole sections. Omission is a finding only when what is dropped is (a) a
qualification or hedge that changes how strong the remaining claim reads,
(b) a counterargument the source raises against its own case, or (c) the
source's own conclusion.

`content_mode` sets the bar for wording, not for truth: `faithful_edit` keeps
the source's sentences, `faithful_synthesis` may compress but may not introduce
a thesis the source does not reach, and every mode must ground every claim.

## Categories

`invented_claim`, `qualification_loss`, `quote_accuracy` (text presented as
verbatim that is not; quote both versions), `number_or_name_error` (altered or
transposed numbers, dates, names, versions, benchmarks),
`attribution_error`, `overstated_furniture` (caption, title, deck, or pull
quote stronger than the source), `unreached_conclusion`.

Severity: `blocking` when a reader would come away believing something false:
invented claim, fabricated quote, wrong number, misattribution, reversed
conclusion. `major` when the claim's strength or scope is distorted. `minor`
when the wording is loose but the meaning survives.

## Output

Return one YAML document and nothing else. The operator records it with
`mag review record <edition-id> --kind evidence`.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: blocking
    article: eval-engineering   # article id from edition.yaml
    locator: "Cost and latency | cuts eval cost by 40% | 1"
    repair_from: "The examiner you already own | Evals cut cost | 1"
    category: number_or_name_error
    note: |
      The source says "roughly a third in our two pilot teams". The manuscript
      raises the figure and drops the pilot scope.
scores:
  claim_support: 3
  qualification_survival: 4
  quote_accuracy: 5
  attribution: 5
notes: One paragraph on what you checked and what you could not check.
```

- `locator` is one string, `"<section heading> | <exact quote> | <1-based
  occurrence index>"`. Normalize curly quotes and apostrophes (U+2018, U+2019,
  U+201C, U+201D) to straight ones on both sides before matching; edition 004
  manuscripts contain U+2019. Use `-` for the heading when the quote precedes
  the first one, and omit `locator` for an edition-wide finding.
- Where the defect is STRUCTURAL, meaning its cause sits earlier than the
  sentence it shows in, add `repair_from`: a second locator on the earliest
  sentence at which it could be repaired.
- `note` is always a YAML block scalar (`note: |`), since it quotes sentences.
- Use `findings: []` when nothing is wrong; `changes_required` needs at least
  one finding, and any `blocking` finding forces it.
- Scores are integers 1-5 and ADVISORY. They never gate a release, and no
  finding is ever softened or dropped to protect one.

---

# The article under audit

- Article id: `factory-systems-problem`
- content_mode: `faithful_edit`
- Byline: Geoffrey Huntley

## Manuscript

```
---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

i must stress that factories is not a token or llm problem. it's a systems engineering and corporate culture problem. it won't be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.

**Editor's note.** Three short posts by one author, published separately. The reading order is this magazine's and not a sequence Huntley wrote: the paragraph above, then the two sections below. The captures carry no dates, so the order they were written in cannot be recovered here. The longer post promised above is not one of the three.

## Software factories are super real

software factories[^1] are super real but we need to be realistic. the factory aspects haven't been cracked yet, the innovators[^3] are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren't in the super small cohort (ie. they are likely startups created in last six months!) or circa <10 people in the who's-who, who have been trying (and realistically failing) over the last two years. they are selling bullshit.

it isn't cracked but it's a puzzle that's being solved daily. the best practices right now are to build abstractions/pieces needed which entails solving non-agent topics.[^2]

[^1]: almost lights out.

[^2]: sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents.

[^3]: at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.

## Don't make the service bus non-deterministic

**Editor's note.** The first hot take is a separate post and is not one of the three collected here.

second hot take, as it seems the first hot take landed. n8n was a silly idea, which i've always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn't have the knowledge that service busses are a solved problem and there's deep prior art in the spooky land of enterprise.

look up anything in the @dotnet space such as mass transit, nservicebus, wcf[^4] if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don't make the entire service bus non-deterministic.

[^4]: lots of bad memories here, not great tech impl but the theory / education is generally on point.
```

## Pinned extraction `software-factories-are-super-real-but-the-factor-ab8ad3ab` (complete)

```
[1] software factories are super real but we need to be realistic. the factory aspects haven’t been cracked yet, the [3] innovators are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren’t in the super small cohort (ie. they are likely startups created in last six months!) or circa <10 people in the who’s-who, who have been trying (and realistically failing) over the last two years. they are selling bullshit. it isn’t cracked but it’s a puzzle that’s being solved daily. the best practices right now are to build abstractions/pieces needed which entails solving [2] non-agent topics. [1] almost lights out. [2] sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents. [3] at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.
```

## Pinned extraction `factories-are-not-a-token-or-llm-problem-ba5fabbf` (complete)

```
i must stress that factories is not a token or llm problem. it’s a systems engineering and corporate culture problem. it won’t be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.
```

## Pinned extraction `do-not-make-the-service-bus-non-deterministic-3a92442c` (complete)

```
second hot take, as it seems the first hot take landed. n8n was a silly idea, which i’ve always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn’t have the knowledge that service busses are a solved problem and there’s deep prior art in the spooky land of enterprise. look up anything in the @dotnet space such as mass transit, nservicebus, [1] wcf if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don’t make the entire service bus non-deterministic. [1] lots of bad memories here, not great tech impl but the theory / education is generally on point.
```

## Output contract

Return one YAML document and nothing else, in exactly the shape the evidence review prompt above specifies. No preamble, no commentary after it. The document may carry only `result`, `findings`, `scores`, `notes`: any other key is refused by the recorder.
