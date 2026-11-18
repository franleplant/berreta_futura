# Model card

The text below the line is a lab's launch post for a new AI model. Fill in a
trading card for one model in it: the post's headline model. If the post
launches two or more models, the card is for the most capable one.

A reader looks at the card for ten seconds before the article and should come
away knowing: what this model is, what it costs, how to run it, when to reach
for it, what it is best and worst at, and what it refuses. Those are the
basics of the model. Product features, demos, and anecdotes belong to the
article, not the card. The card picks; it never summarizes the post.

## Slots

- `name`: the model's full name as the post writes it.
- `model_id`: the API identifier exactly as the post prints it. Null if the
  post prints none.
- `lab`: the company that made it.
- `cost`: the standard per-million-token API prices, in the order input,
  cached input, output, each as `{"label": "in"|"cached"|"out", "value": "$8"}`.
  Leave out a price the post does not state. Only the standard price goes
  here.
- `type_line`: `{"kind": ..., "roles": [...]}`. Kind is "Frontier Model"
  unless the post positions the model as something else (small, fast,
  open-weight, specialist). Roles are one or two single nouns for the work
  the post says the model is for: Coder, Scientist, Analyst, Designer,
  Researcher, Agent.
- `traits`: two or three plain sentences that describe the model itself:
  how it behaves and works, what kind of model it is, and what changed
  from the model it replaces, as the post states it. Examples of the kind:
  "Uses fewer output tokens on demanding tasks.", "Communicates more
  clearly than past Fable models.", "Same underlying model as Mythos 5.2,
  with cyber and biology safeguards.", "Matches its tools and effort to
  the workflow." Each at most 90 characters, ending with a period. Not a
  marketing line about its tier or lineup ("our most capable model", "built
  for complex work"), not a benchmark score, not a price, not where it is
  available, not a product or feature built on it, not a tester's claim.
- `effort`: the names of the selectable effort or reasoning levels, in the
  post's order, as a list of single words or short names, with no caveats
  or defaults. Null when the post names none.
- `advice`: one or two rows, `{"key": ..., "value": ...}`, the post's own
  recommendations to the reader about using this model. Keys from this list
  only: "Use it for", "Start with", "Tip". "Use it for" is the work the lab
  says the model is best for; "Start with" is a model the lab tells readers
  to try first instead; "Tip" is a concrete usage practice the lab
  recommends (how to prompt it, cache, or set it up). The value continues
  the key as one phrase, lower-case start, at most 80 characters, no final
  period. Only recommendations the post addresses to the reader, never your
  own.
- `strength`: the area of work where the post shows this model doing best,
  in plain words a manager understands, at most 55 characters, for example
  "Hardware design and robot control" or "Spreadsheets, slides and 3D web
  pages". An area, not a benchmark name or a number.
- `weakness`: at most 55 characters, a shortcoming the post itself states or
  shows about this model: a behavior that got worse, a test it did poorly
  on, a rival it trails, a limit the lab admits. Plain words, at most one
  number. Null when the post shows none. Never infer one from an absence,
  never use a safeguard, never use a price.
- `resistance`: at most 55 characters, what the model refuses or blocks by
  design, or its safety rating, in plain words.
- `benchmark`: the one score for the corner box: `{"name": ..., "score": ...,
  "unit": ...}`. Pick the benchmark the post leads with where this model has
  an absolute score (not a delta) and ranks first among the models compared.
  Name at most 22 characters, as the post names it, shortened only by
  dropping a subtitle. Score exactly as printed, without the unit. Unit is
  "%", "Elo", or "" for a plain score.
- `flavor`: `{"quote": ..., "who": ...}`. One sentence or less from a quoted
  tester in the post, copied character for character, cut only at a sentence
  or clause boundary, at most 120 characters. Pick the most specific,
  surprising claim, not praise. `who` is "Name, Company". Null when the post
  quotes nobody.
- `released`: the post's date as YYYY-MM-DD, null if the post has none.
- `art_briefs`: two different subjects for the card's painting, each one
  paragraph of at most 90 words: [the subject, what it is made of],
  [what it is doing], [three or four concrete things the post shows the
  model doing, drawn as physical objects in or around the scene].
  Background: [one simple, surreal setting]. [three colours] palette.

  The subject is always a beautiful, majestic giant: the model as a
  colossal being with a face, a body, and a calm, noble presence, the kind a
  player would name. A titan, a giant knight, a colossal stag, heron, bear,
  or owl, a giant sea serpent, a dragon the size of a mountain, a stone
  colossus, a giant spirit. Graceful and awe-inspiring, never grotesque,
  menacing, or cute. Open the brief with the word giant, colossal, colossus,
  or titan. Never a building, a tower, a vehicle, a tree, a city, or an
  object. Pick the giant from what the post is about, so cards differ from
  model to model, and make the two briefs two different kinds of giant in
  two different settings. No many-armed figures.

  One example of the shape, for another model:

  "a colossal copper dragon with paper wings covered in handwritten
  equations, resting serenely on a floating island of books, one claw
  soldering a tiny circuit board, its tail holding a protein model up to the
  light, a small robot arm perched on its horn like a bird. Background: a
  teal desert under a pale sky. Copper, teal and cream palette."

  No text, letters, numbers, screens with writing, logos, the lab's name,
  or the model's name. Avoid the generic glowing sun disk behind a centred
  figure.

## Rules

- Every number on the card appears in the post exactly as you write it.
  Every claim is one the post makes about this model. Add no purpose,
  contrast, cause, or consequence the post does not state. Shorten by
  cutting words, never by generalizing.
- Each fact appears once on the whole card. A number, benchmark, price,
  mode, platform, or model name used in one slot never appears in another.
  If two slots want the same fact, give it to the more specific slot and
  choose something else for the other.
- Plain words. No hype words (powerful, revolutionary, state-of-the-art,
  cutting-edge, unprecedented, best-in-class), no exclamation marks.
- Write numbers and model names as the post does.
- Never use the em dash character (U+2014) outside the flavor quote.

## Output

One JSON object with exactly the keys above, nothing else, no code fence.

---

