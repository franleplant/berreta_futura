# Figure curation

A printed magazine reprints this article. Each attached image appears in the
article at the place shown in its context. Decide for every image whether it
earns a place on paper.

Keep an image when a reader learns something from it that the text alone does
not give them: a chart, a diagram, a table, a screenshot of a result, an
interface, terminal output, or code the article discusses, or a photograph of
the actual thing the article is about.

Drop an image when it is:

- decoration: mood art, a generated illustration, a stock photo, a banner,
  a title card or cover that repeats the headline, a logo, an avatar, a meme;
- redundant: a picture of text the article already states or that a reader
  does not need (a license, a tweet, a quote card, a book cover next to a
  link), or a near-duplicate of another kept image;
- unreadable as print: a video still, an animation frame that is blank or
  mid-transition, a thumbnail too small to read.

When unsure, keep it. Reply with exactly one fenced yaml block and nothing
else of consequence:

```yaml
images:
- file: 001.png
  verdict: keep | drop
  reason: one short factual sentence
```

with exactly one entry for every attached image, in the order given.
