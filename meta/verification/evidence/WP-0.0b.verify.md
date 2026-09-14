# WP-0.0b verification

## Verdict

ACCEPTED

## Base and commit

- Diff base: db18e0a
- WP commit: 8f9596d (evidence ## Base names 06bc764; the bridge file is
  identical at both, db18e0a only added WP-0.0.verify.md)

## Owns check

`git diff --name-only db18e0a..8f9596d` lists exactly
`src/magazine/engine_render_bridge.py` and
`meta/verification/evidence/WP-0.0b.md`. No `*.verify.md`, no
`baseline.json`. Pass.

## Replay

Fresh worktree at 8f9596d, run dir
`editions/010/run-2026-09-13T01-34-51` copied in. Before leg rendered with
the bridge file restored from `git show db18e0a:...`, after leg with the
committed file. Every command from evidence ## Commands replayed:

- `uvx ruff format --check` / `uvx ruff check` on the bridge file: clean
  (claimed clean).
- Before render `render-2026-09-14T01-48-41`, after render
  `render-2026-09-14T01-49-48`, both `pending anchors: 0`.
- Manifest leaf diff: 9 new `.layout.toc.*` leaves, 0 removed, 0 changed;
  new key set exactly `['article_opener_fits', 'toc']` (claimed exactly
  this). toc pages observed: government-rails 4, countering-misuse 7,
  alignment-assessment 11, dario-amodei 17, scenarios 31, third-era 36,
  self-driving 40, deepseek 46, rapidly-scaling 50 (claimed pages match).
  `article_opener_fits` observed `{}` (claimed `{}`).
- pdftotext dumps and pdfinfo boxes byte-equal for reader.pdf,
  booklet-a4.pdf, booklet-a4-interior.pdf, booklet-a4-cover.pdf;
  request.json byte-equal (claimed identical).
- Critic result pass/pass; differing leaves exactly 2 `_sha256` and 4
  stage `.path` noise leaves, zero unexpected (claimed exactly this,
  matching WP-0.0 Residuals).

## Notes

The evidence Residuals flag that `article_opener_fits` is `{}` on every
full render (html_edition.py:393 omits `data-article-id` on the opener
header; weasyprint_adapter.py:2303 requires it), so WP-2.3's
`article_opener_fits` comparison and WP-3.2's opener-fit clause are
vacuous until a plan revision sanctions the oracle fix. Recorded; the
WP's own verify clauses are all green, so this does not block acceptance.
