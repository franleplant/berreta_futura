# Pages that complete a model card

A trading card for the AI model {model}, made by {lab}, is missing these
facts because the launch post does not state them: {missing}.

Search the web and find at most three pages on the lab's own sites
({domains}) that state those facts for {model}: an API pricing page, a model
overview or models list in the developer docs, a model card or system card
page, a release notes or changelog entry. Prefer the page that states the
most missing facts at once. Open each page and check that it really names
{model} and states at least one missing fact before you list it. Never list
news coverage, third-party sites, forums, or social media.

Answer with one JSON object and nothing else, no code fence:

{"urls": ["https://...", ...]}

An empty list when no such page exists.
