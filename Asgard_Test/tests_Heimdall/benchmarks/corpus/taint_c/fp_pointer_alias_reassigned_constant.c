/* FP regression, MAJOR-1 (adversarial review, reviewer's exact repro):
 * `p` starts aliased to `buf` and would inherit `buf`'s taint after
 * fgets() -- but `p` is then DIRECTLY reassigned to a constant string
 * literal, in straight-line code, before the sink. This provably clears
 * `p`'s taint (a "strong update" on direct reassignment-to-constant,
 * distinct from the general sticky/never-mute policy used for
 * non-constant reassignments elsewhere) -- `system(p)` here is genuinely
 * clean and must NOT flag, let alone at CERTAIN confidence. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    char *p = buf;
    fgets(buf, 64, stdin);
    p = "ls";
    system(p);
}
