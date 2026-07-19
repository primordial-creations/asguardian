/* TP: SA3 never-mute guard on an "unknown"/unresolved pointer. `char *p =
 * buf + 1;` is pointer ARITHMETIC -- not a bare identifier/address-of, so
 * it is outside the "simple pointer aliases only" shape the WS2 baseline
 * tracked. Per the SA3 mandate ("unresolved/unknown pointer ->
 * over-approximate, never assert clean"), `p` is conservatively unioned
 * with every identifier in the RHS (here, `buf`) rather than left
 * completely untracked -- `system(p)` must still flag `buf`'s taint. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    fgets(buf, 64, stdin);
    char *p = buf + 1;
    system(p);
}
