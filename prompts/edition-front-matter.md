# Edition front matter: title, deck, back cover

Guidance for whoever drafts `edition.yaml`'s title, subtitle, cover deck,
and `cover.back_text`. These are written AFTER the articles are final and
are never derived from the opening editorial: the editorial is one voice in
the issue, not its name. An editorial title that happens to be great cover
copy is a coincidence to enjoy, not a pipeline.

## The edition title

Pull candidates from the articles themselves: the most arresting concrete
image, claim, or phrase the issue actually contains (a thing, a scene, a
number, a dare). Draft at least five before choosing.

Tests, all of which must pass:

- You can picture it. It names something that exists in the issue's world,
  not a quality of the issue ("small", "new", "future", "signals").
- It would survive being shouted across a newsstand.
- It is not a formula. Banned shapes: paired abstractions ("X, Named",
  "X and Y"), gerund openers ("Building...", "Naming..."), "The Age of X",
  "The X Issue", anything a language model would produce for a generic
  tech anthology.
- It promises tension or pleasure, not coverage.

The subtitle/deck may then do the inventory work plainly: what is actually
inside, concretely, without theme-speak.

## The back cover

`cover.back_text` is the hook on the back of the magazine: someone turns it
over, reads it, and has to open it. Make it fun and make it about the
content: a scene, a dare, a riddle, a tiny story, or a surprising fact lifted
from one of the articles, told so the reader wants the rest.

- Never reference "this issue", "these pages", "inside", the magazine, or
  the act of reading; no inventory or synopsis of contents.
- One idea only, taken from the articles' actual material: a real number, a
  real scene, a real claim. Invent nothing the articles do not say.
- Playful beats solemn. A grin or a raised eyebrow is the goal.
- Hard budget: 60 words at most (the render fails loudly when it cannot fit).

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
