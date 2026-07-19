/* TP: SA3 multi-level pointer dereference. `char **pp = &p;` then
 * `system(*pp);` -- before SA3, `_eval` had no case for tree-sitter-c's
 * `pointer_expression` node type (used for BOTH `&x` and `*p`), so `*pp`
 * silently evaluated to no taint at all regardless of the alias union
 * already linking `pp`/`p`/`buf` -- a false negative on a real double-
 * pointer command-injection idiom. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    char *p = buf;
    char **pp = &p;
    fgets(buf, 64, stdin);
    system(*pp);
}
