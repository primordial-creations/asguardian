/* FP sibling of tp_pointer_alias_command_injection.c: `p` points at a
 * SEPARATE, never-tainted local buffer (`safe`), not at `buf` (the
 * fgets() target). Alias tracking must not over-taint every pointer in
 * scope just because SOME buffer nearby was tainted -- `system(p)` here
 * is genuinely clean. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    char safe[64] = "echo hi";
    char *p = safe;
    fgets(buf, 64, stdin);
    system(p);
}
