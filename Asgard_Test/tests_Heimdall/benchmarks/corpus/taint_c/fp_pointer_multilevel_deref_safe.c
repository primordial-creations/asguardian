/* FP sibling of tp_pointer_multilevel_deref.c: `pp` points at `p`, which
 * points at a SEPARATE, never-tainted buffer (`safe`) -- `system(*pp)`
 * must stay clean. Proves the multi-level deref fix does not over-taint
 * every double-pointer in scope just because SOME buffer nearby was
 * tainted. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    char safe[64] = "echo hi";
    char *p = safe;
    char **pp = &p;
    fgets(buf, 64, stdin);
    system(*pp);
}
