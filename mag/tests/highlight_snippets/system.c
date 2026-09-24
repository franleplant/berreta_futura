#include <stdio.h>
#include "local.h"
#define MAX(a, b) ((a) > (b) ? (a) : (b))

#if 0
dead code here
#endif

typedef struct node {
    size_t len;
    uint8_t *data;
    struct node *next;
} node_t;

static const char *names[] = { "alpha", "beta", NULL };

/* Allocate a node.
   Returns NULL on failure. */
[[nodiscard]] node_t *node_new(size_t len)
{
    node_t *n = malloc(sizeof *n);
    if (!n) return NULL;
    n->len = len;
    n->data = calloc(len, 1);
    return n;
}

int main(int argc, char **argv) {
    unsigned long total = 0UL;
    float ratio = 1.5f;
    char c = '\n';
    for (int i = 0; i < argc; ++i) {
        total += strlen(argv[i]);  // count
    }
    printf("%lu %.2f %c\n", total, ratio, c);
    goto done;
done:
    return total > 0x10 ? 0 : -1;
}
