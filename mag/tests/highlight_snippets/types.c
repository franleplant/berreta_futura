enum color { RED, GREEN = 2, BLUE };
volatile atomic_int counter;
pid_t pid = fork();
FILE *fp = fopen("out.txt", "w");
_Bool ok = true;
_Static_assert(sizeof(int) == 4, "int");
extern inline int64_t add(int64_t a, int64_t b) { return a + b; }
#pragma once
#ifdef DEBUG
#  define LOG(fmt, ...) fprintf(stderr, fmt, __VA_ARGS__)
#else
#  define LOG(fmt, ...)
#endif
