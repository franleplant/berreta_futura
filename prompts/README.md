# prompts/

The writer prompts are **verbatim by design**. They came out of side-by-side
experiments (2026-08-06): short style-mix prompts against a strong model beat
the old prompt-pack + five-lens judge loop on writing quality, at a fraction
of the cost. Do not add instructions, style docs, format contracts, or
examples to them — if a prompt needs to change, change it from new
side-by-side evidence, not by accretion. The judge system they replaced is
recorded in `meta/judge-inventory.md` and lives in git history.

## Writer prompts (used by `mag produce`)

| file | content_mode | notes |
|---|---|---|
| `article.md` | `faithful_synthesis`, `faithful_edit` | general articles |
| `in-a-nutshell.md` | `in_a_nutshell` | `{topic}` is replaced with the article title from the plan row |
| `opening-editorial.md` | editorial | prompt is preceded by the accepted articles wrapped in `<articles><article N>…` |

How a writer call is assembled — this is the *whole* prompt:

```
<sources>

{source extraction(s), pasted}

</sources>

{prompt file, verbatim}
```

The writer's reply is the manuscript body, taken as-is. Frontmatter never
comes from the writer: article frontmatter (`source_ids`, `content_mode`,
`label`) is assembled deterministically from the plan row, and the
editorial's `title` is extracted from the finished manuscript by the cheap
`--frontmatter-model` (default `haiku`).

Default writer model: `opus` (`--writer-model`, `<backend>:<model>[@effort]`
specs per `mag/src/caller.rs`).

## Other prompts

- `translation-es.md` (+ output schema) — `mag translate`
- `cover-art-candidates.md` — `mag art`
