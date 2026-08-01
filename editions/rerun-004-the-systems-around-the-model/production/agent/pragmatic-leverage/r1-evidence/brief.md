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

- Article id: `pragmatic-leverage`
- content_mode: `faithful_edit`
- Byline: Dex Horthy

## Manuscript

```
---
source_ids:
- pragmatic-leverage-in-the-software-factory-09879736
content_mode: faithful_edit
label: FAITHFUL EDIT
---

This one is a bit of an addendum / side-quest to the recent series. It didn't fit cleanly into the main post so I'm publishing it standalone. It is referenced briefly in *Why Software Factories Fail part 2: Turning the lights back on*.

## Seeking leverage

Even before AI, only 25–50% of the time to ship a feature was writing the code itself. The rest was aligning/planning, code-review/rework, and testing/verifying the solution.

If you're only using AI to write the code, then you're taking the 2–4 hours of coding time down to 10–20 minutes, but you haven't accelerated anything else here.

But if you use AI to help you plan and align, then you actually get closer to 2–3x faster.

## The 80/20 rule in AI coding leverage

Let's assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50%.

Now let's say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

**note** For this example I'm gonna blur

> "chance you'll have to change something" weighted by "how painful the change will be"

into a single percentage number but obviously they're two separate variables. If the model is 50% likely to get a button style wrong, but the fix is one cheap prompt, then our combined "expected pain" is low.

> expected pain = P(you'll have to change it) × how painful the change is

If you draw this out, there's an inverse relationship between effort invested up front and expected pain.

What you don't want to do is spend 6 hours planning a task for which you could have eliminated 80% of the expected pain in the first 10 minutes.

You need to do this without overindexing on questions you won't be able to answer without going down a level. For example, if you've done some work at the "Product" level and have not answered all the open questions yet, it's possible you may need to end it where you are and zoom down a level to the technical details to understand what's feasible. There's no perfect process for this.

This is what we mean by leverage, and it requires being pragmatic. If you're doing multiple phases of planning, zooming in from 50kft view all the way to the 10kft view, you want to do a little bit of steering at each phase to ensure you are eliminating as much expected pain as possible.

Good luck.
```

## Pinned extraction `pragmatic-leverage-in-the-software-factory-09879736` (complete)

```
dex
@dexhorthy

# Pragmatic Leverage in the Software Factory

This one is a bit of an addendum / side-quest to the recent series. It didn't fit cleanly into the main post so I'm publishing it standalone. It is referenced briefly in Why Software Factories Fail part 2: Turning the lights back on.

## Seeking Leverage

Even before AI, only 25-50% of the time to ship a feature was writing the code itself. The rest was aligning/planning, code-review/rework, and testing/verifying the solution.

If you're only using AI to write the code, then you're taking the 2-4 hours of coding time down to 10-20 minutes, but you haven't accelerated anything else here.

But if you use AI to help you plan and align, then you actually get closer to 2-3x faster.

## The 80/20 rule in AI coding leverage

Lets assume if you yolo a two-sentence prompt into your factory, your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50%.

Now lets say you are a principal engineer with 10 years of experience. You have the whole codebase across 100 repos downloaded into your head. So you spend an afternoon writing a perfectly detailed spec by hand. Now your odds are better, but you probably still have about a 10% chance that you'll have to redo *something* significant.

And at the far end: write every line yourself. Nothing's left for the agent to get wrong, so the rework chance goes to zero.

**note** For this example I'm gonna blur

> "chance you'll have to change something" weighted by "how painful the change will be"

into a single percentage number but obviously they're two separate variables. If the model is 50% likely to get a button style wrong, but the fix is one cheap prompt, then our combined "expected pain" is low.

> expected pain = P(you'll have to change it) × how painful the change is

If you draw this out, there's an inverse relationship between effort invested up front and expected pain.

What you don't want to do is spend 6 hours planning a task for which you could have eliminated 80% of the expected pain in the first 10 minutes.

You need to do this without overindexing on questions you won't be able to answer without going down a level. For example, if you've done some work at the "Product" level and have not answered all the open questions yet, its possible you may need to end it where you are and zoom down a level to the technical details to understand what's feasible. There's no perfect process for this.

This is what we mean by leverage - and it requires being pragmatic. If you're doing multiple phases of planning, zooming in from 50kft view all the way to the 10kft view, you want to do a little bit of steering at each phase to ensure you are eliminating as much expected pain as possible.

good luck.
```

## Output contract

Return one YAML document and nothing else, in exactly the shape the evidence review prompt above specifies. No preamble, no commentary after it. The document may carry only `result`, `findings`, `scores`, `notes`: any other key is refused by the recorder.
