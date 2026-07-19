/* TP: WS2 pointer-alias fixture. `p` is a simple pointer alias of `buf`
 * (`char *p = buf;`); fgets() then taints `buf` (mutating source) BEFORE
 * `p` is used at the sink. Without alias tracking, `system(p)` would look
 * clean because the taint was recorded against the identifier `buf`, not
 * `p` -- a false negative on a textbook C RCE idiom. This is the exact
 * case named in the WS2 task spec. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    char *p = buf;
    fgets(buf, 64, stdin);
    system(p);
}
