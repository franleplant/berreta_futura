# Edition front matter: title, deck, back cover

Guidance for whoever drafts `edition.yaml`'s title, subtitle, cover deck,
and `cover.back_text`. These are written AFTER the articles are final and
are never derived from the opening editorial: the editorial is one voice in
the issue, not its name. An editorial title that happens to be great cover
copy is a coincidence to enjoy, not a pipeline.

## The edition title

The title belongs to the whole issue, never to one piece. Read every article
below, find what they have in common when you look past their topics (the
same pressure, the same move, the same kind of trouble), and spin a title
out of that. Draft at least five before choosing.

Tests, all of which must pass:

- Every article fits under it. Hold it against each article in turn; if one
  of them has nothing to do with it, it is the wrong title.
- It is not any article's title, headline, coinage, or catchphrase, and not
  a phrase lifted from one article.
- You can picture it: an image or a thing, not a quality of the issue
  ("small", "new", "future", "signals").
- It would survive being shouted across a newsstand.
- It is not a formula. Banned shapes: paired abstractions ("X, Named",
  "X and Y"), gerund openers ("Building...", "Naming..."), "The Age of X",
  "The X Issue", anything a language model would produce for a generic
  tech anthology.

The subtitle/deck may then do the inventory work plainly: what is actually
inside, concretely, without theme-speak.

## The back cover

`cover.back_text` is what someone reads after turning the magazine over in
a shop. Its only job is to make them open it. Make it fun: a dare, a joke,
a riddle, a provocation, a question they suddenly need answered.

- Never mention the issue, the magazine, the articles, their titles, their
  authors, or the companies that published them, and never describe what is
  inside. No retelling of an article's anecdote, no numbers from it.
- It may play on the world the articles live in (agents, code, machines,
  the people who build them), but it stands alone: a reader who knows none
  of the articles gets it at once.
- One idea. Short beats complete: 40 words at most, ideally under 25.
- Playful beats solemn. A grin or a raised eyebrow is the goal.

## The cover deck

One line under the headline, concrete inventory or a second punch; never a
restatement of the title in different abstractions.

## Output

Reply with YAML only, no fences and no commentary, with exactly these keys,
each a single-line string:

title: the edition title
subtitle: the deck (inventory line)
back_text: the back cover

Never use the em dash character (U+2014).
