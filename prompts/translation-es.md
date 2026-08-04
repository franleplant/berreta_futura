# Spanish translation

Translate the approved English Markdown into educated castellano. Use restrained Argentine preferences only when natural; otherwise use neutral Spain-compatible Spanish. Do not use slang or generic regionalisms.

Preserve the English Markdown structure exactly: headings, paragraph order, lists, links, emphasis, tables, block quotes, and fenced code blocks. A fenced code block must remain one contiguous exact block. Do not add CommonMark footnotes.

Return an object with the exact SHA-256 pin of the English input as `english_sha256` and the translated Markdown as `markdown`. Do not change, omit, or invent an English hash pin.