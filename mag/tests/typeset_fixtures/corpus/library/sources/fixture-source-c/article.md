# Budget Tooling

Captured prose for the tooling source.

```rust
fn budget(tokens: u32) -> u32 {
    // four characters per token
    let spare = tokens.rem_euclid(4);
    tokens.div_ceil(spare)
}
```

```typescript
export const ceiling = (limit: number): string =>
  `cap ${limit} tokens`;
```

```bash
echo "spent $SPENT of 4096" # report
```

EXTRACT-BEGIN
let spent = budget(4096);
assert!(spent <= 1024, "over budget");
EXTRACT-END
