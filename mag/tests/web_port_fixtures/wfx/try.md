Try the following steps.

1. Step one.
2. Step two.

```python title="budget.py"
@dataclass
class Budget:
    limit: int = 1_000  # “cap”
    def left(self, spent: float) -> str:
        return f"{self.limit - spent:.2f} left…"
```

```c
#include <stdio.h>
int main(void) { size_t n = sizeof(int); printf("%zu\n", n); return 0; }
```

```http
POST /mcp HTTP/1.1
Content-Type: application/json

{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
```

```ts
const total: number = items.reduce((a, b) => a + b, 0);
```

```YAML
steps:
  - run: cargo test # all
```

```jsonc
{ "a": 1 /* unknown to pygments */ }
```
