/* FP guard: the SA3 unresolved-RHS alias fallback is gated on
 * `is_pointer_decl` and must NEVER fire for plain scalar (non-pointer)
 * arithmetic -- `int total = a + b;` must not become "aliased" with `a`/
 * `b` and must not cause any spurious cross-contamination. Also proves
 * the fallback doesn't fire on constant-only pointer arithmetic. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    fgets(buf, 64, stdin);
    int a = 1;
    int b = 2;
    int total = a + b;
    char safe[64] = "echo hi";
    char *p = safe + total;
    system(p);
}
