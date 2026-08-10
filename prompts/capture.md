# Source capture

The page above (inside the <page> block) is the raw HTML of {url}.

Transcribe the page's substantive content into Markdown, VERBATIM. This is a
capture, not a rewrite: every sentence you output must appear in the page,
word for word. You choose what to include (the article) and what to drop
(the site chrome); you never change wording, order, or punctuation.

Output format, exactly:

1. `# <the article's title>`
2. One byline line, built from what the page states: author, publication,
   date, separated by " · " (for example `By Jane Doe · Example Blog ·
   March 4, 2021`). Omit parts the page does not state.
3. The article body, verbatim and in source order:
   - Keep headings (at their levels), paragraphs, lists, blockquotes,
     emphasis (use asterisks), inline code, and tables.
   - Keep links as Markdown, resolving relative hrefs against {url}.
   - Every fenced code block must be a contiguous, exact run of code from
     the page. If you cannot preserve a block exactly, drop it whole.
   - Keep the page's own typography (em dashes, curly quotes, ellipses)
     exactly as written. Never introduce an em dash of your own.
   - For each substantive body image, place an image reference at its
     original position: `![alt](absolute-image-url)`, using the page's alt
     text when it is meaningful and empty alt otherwise. Pick the
     largest/original resolution URL (resolve srcset). Skip tracking
     pixels, avatars, icons, and decorative placeholders. Keep embeds that
     are not images (video iframes, GIF embeds) as plain links with the
     page's own attribution text.
   - Drop chrome only: navigation, sidebars, share buttons, newsletter and
     product CTAs, comments, related-post lists, footers.
4. A line containing exactly `===META===`
5. A small YAML block:
   - `synopsis:` one factual sentence stating what the article says.
   - `author:` the author name(s) as the page states them, or empty.
   - `published:` the publish date as YYYY-MM-DD, or empty.

No commentary, no preamble, nothing outside this structure.
