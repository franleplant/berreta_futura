# Model launch post?

The text below the line is one captured web page. Decide whether it is a
model launch post: the company or team that built a new AI model announcing
that model's release to the public, with what it can do. Typical signs: "today
we're releasing / introducing / announcing" a named model, its benchmark
results, its price or availability, how to access it.

Not a launch post: a research paper or technical report about a model, a
post about someone else's model, a comparison or guide across models, a
product feature or tool built on a model, a case study, news coverage, or a
safety or incident report that mentions a model.

Answer with one JSON object and nothing else, no code fence:

{"launch": true or false, "models": ["every launched model's name as the page writes it", "..."] or null, "evidence": "the one sentence from the page that announces the release, copied character for character, or null"}

When the page launches a family of models (for example a flagship and a
smaller sibling released together), list every one, the most capable first.
List only models this post releases as products people can use, never earlier
models it compares against, and never research checkpoints or ablation models
the post shares alongside the product (for example a model trained only to
study a technique, even when its weights are published).

---

