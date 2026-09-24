---
source_ids:
- fixture-source-c
content_mode: article
label: ARTICLE
---

The standfirst paragraph opens the code fixture and names `budget()` inline.

## Setup

A paragraph before the first fence, in the ordinary reading measure.

```rust
fn budget(tokens: u32) -> u32 {
    // four characters per token
    let spare = tokens.rem_euclid(4);
    tokens.div_ceil(spare)
}
```

## Tooling

A paragraph between the fences.

```typescript
export const ceiling = (limit: number): string =>
  `cap ${limit} tokens`;
```

```bash
echo "spent $SPENT of 4096" # report
```

A closing paragraph after the fences.

## References

- Ada Fixture. Cache Budgets in Practice. A reference entry long enough to wrap onto a second line so that its hanging indent shows on the page.
- Bo Fixture. Storage Tiers. A second, shorter entry.
