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

{"launch": true or false, "model": "the launched model's name as the page writes it, or null", "evidence": "the one sentence from the page that announces the release, copied character for character, or null"}

When the page launches several models, name the most capable one.

---

