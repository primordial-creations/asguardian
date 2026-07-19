/* TP: SA3 array-decay aliasing (already covered by the WS2 baseline --
 * asserted explicitly here as part of the SA3 acceptance matrix). `char
 * arr[N];` decays to a pointer on `char *p = arr;`; `fgets(arr, ...)`
 * taints `arr` and must flow to `p` through the alias union. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char arr[64];
    char *p = arr;
    fgets(arr, 64, stdin);
    system(p);
}
