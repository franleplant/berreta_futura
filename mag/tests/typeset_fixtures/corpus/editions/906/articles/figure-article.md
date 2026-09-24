---
source_ids:
- fixture-source-a
content_mode: article
label: ARTICLE
---

A figure keeps its image in every language, while its caption, its alternative text, and its anchor are translated.

The image itself is shared: both editions point at the same captured file inside the source directory, at the same resolution. What changes is the text around it. The caption is set in the edition's language, the alternative text describes the image to a reader who cannot see it, and the anchor names the heading the figure follows, which is a translated heading.

## Budgets

A cache budget limits how much memory a service may spend on remembered answers. The budget is small enough that the service stays predictable and large enough that the common questions are answered without recomputation. The diagram shows the budget as a band that the service fills and then holds.

Once the budget is full, each new answer must displace an older one, and the rule that chooses which answer leaves is the whole design. Some services evict the oldest answer, some evict the least used, and some keep counts that decay over time.

## Closing

The article ends after its figure with a short paragraph, so that the figure's page and the closing text can be compared across both languages.
