# Edition 4 article-opening prototype

Three focused variations of the approved B-family A5 article opener using real
Edition 4 material. Each direction keeps the same reading sequence:

1. article illustration;
2. title;
3. QR, author, and short biography;
4. opening article text.

Run from the repository root:

```sh
uv run --locked python -m http.server 8000
```

Open `http://localhost:8000/prototypes/article-opening-prototype/?variant=A`.
Use the floating switcher or the left and right arrow keys to compare:

- A, quiet ink rules;
- B, muted cobalt and brick-coral accents;
- C, unprinted white paper with no page-wide grain, a quiet gray rule, and one
  compact signal-orange metadata tick.

This is throwaway prototype code. It does not alter the Edition 4 manifest,
semantic HTML, print stylesheet, or renderer. It uses the muted watercolor MCP
opener sample only inside this prototype. Every variation omits the visible QR
label and the duplicated bottom folio.
