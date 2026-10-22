---
source_ids:
- introducing-clairic-a-new-system-one-class-of-ex-40634a33
content_mode: article
label: ARTICLE
---

Today we're announcing a preview of a new class of System One model: extraction models. The first, Clairic, is hosted on Workers AI as `@cf/cloudflare/clairic`, and we intend to release it open-weights soon. It reads unstructured input and returns typed values: extracted, computed, estimated, or forecast. It answers in one forward pass and charges only for input. It's more accurate, faster, and cheaper than traditional LLMs. It generates no tokens, so every answer is a value of the type you asked for, or null. It can still be wrong, which is why each answer carries a confidence score.

## Why another kind of model

TypeSafe introduced System One models a month ago with Jev. A System One model is fast and precise. A System Two model, like an LLM, reasons deliberately. Until now every System One model was a decision model: Jev and Clef take an input and a list of options and return a probability for each. But many structured-output calls sent to frontier LLMs have answers no one can list in advance. What's the invoice total? How many days late is it? What will this repair cost? Clairic answers those.

Clairic returns numbers and typed values. Clef picks among options. LLMs write open-ended text. Extraction models turn raw input into typed values, decision models turn values into decisions, and LLMs turn decisions into words.

## How a request works

A request is a `state` (text, plus up to four optional images) and a map of named, typed `fields`, each with optional plain-language instructions. The types are:

- `text` spans with offsets
- `number`, `date`, `time`, `datetime`, `duration`, and `list`
- `estimate`, a distribution inside your `[min, max]` on your step grid
- `forecast`

Every scalar answer comes with `p_null` and `confidence`. Every estimate comes with a median and an 80% interval. There's no limit on fields. If they don't fit beside the input in one pass, the server splits them into parallel passes and merges the answers. Asking for thirty fields costs about the same as asking for three.

## Extracting

Take this support email: "Hi, order A-88412 arrived on Sept 28, 2026 with a cracked screen and a dented corner. I paid $649.00 plus $52.10 tax. It's now Oct 9, 2026 and I'd like this fixed or refunded."

Clairic returned the order ID as a span with offsets, the delivery date, and the damage as a list of exact spans. It also returned values the email never states:

- `amount_paid` of 701.1, adding the price and the tax in the same pass.
- `days_since_delivery` of 11, worked out from two dates.

Asked for a tracking number the email doesn't contain, it returned `null`. Its `guess` field shows what it would otherwise have picked: $52.10, at confidence 0.42.

It works on images too. We gave it a real photo of a receipt, badly angled and hard to read. It extracted the order number, datetime, quantity, prices, tax, and tip, each with a confidence score. It correctly returned null for a discount the receipt didn't show.

## Estimating

Ask an LLM for an estimate and you usually get one number with no sense of how sure it is. Downstream code can't tell a confident $180 from an unconfident one. A decision model can choose among buckets instead, but buckets are coarse, and each one adds input tokens and confusion.

Clairic returns a distribution inside your bounds. Given five comparable home sales and a subject property, it estimated $418,000, with a median of $415,000 and an 80% interval of $370,000 to $470,000. A narrow interval signals high certainty. A wide one tells you to route another check.

## Forecasting

Clairic isn't claiming to replace a dedicated time-series model. It's a little faster and cheaper than your regular LLM, and it returns an interval for every step ahead.

Each morning for 21 days, we asked it for the next day's count of people screened at TSA checkpoints. Its forecasts were off by 3.3% on average, and 17 of the 21 actual counts landed inside the 80% interval. It picked up the weekly rhythm from the numbers alone. Three of the four misses fell on the Columbus Day weekend. Clairic forecasts from the patterns in the series and doesn't account for events the series doesn't show.

## Fast and slow together

We ran the damaged-product claim through two pipelines:

- **Cascade:** Clairic extracts, Clef decides, and GLM-5.3 writes the reply.
- **All-LLM:** GLM-5.3 does every step.

In the cascade, Clef decides from five lines of typed values instead of a free-form email, which can be susceptible to prompt injection. The LLM never sees the email at all.

| | Cascade | All-LLM |
|---|---|---|
| Time, end to end | 19.3 s | 61.7 s |
| Extract and decide | under 1 s combined | 38 s |
| Cost per million claims | $6,032 | $11,740 |

The cascade was about 3.2 times faster and cost 49% less. Both pipelines got the facts and the decision right in every run. Clairic's repair estimate was identical each time, while GLM-5.3's changed ($250, $250, $220). Gemma 4 and Qwen failed the all-LLM version, unable to deduce values like `repair_cost`.

## Preview caveats

The endpoint is an early checkpoint, and we expect it to get better.

- **Arithmetic:** one- and two-step arithmetic seems reliable. Longer chains, and aggregating across many table rows, are hard for any one-pass model. For now, have Clairic predict the value and let code do the math.
- **Estimates:** they need evidence such as comparables, history, or descriptive text.
- **Calibration:** intervals are trained to be calibrated and are on most held-out sets, but they can run narrow on unfamiliar data.
- **Forecasting:** it's basic. Use it for non-critical, general pattern matching, not detailed long-horizon forecasting.
- **Correctness:** every answer is well formed, not necessarily correct. Use `confidence`, `p_null`, and the intervals to decide what to automate and what to send for review.

Clairic is available now as a preview, through `env.AI.run()` or the REST API. The name is short for [Cl]oudflare's [AI R]egression model, with *clerical*, *clearly*, and *clairvoyance* folded in.
