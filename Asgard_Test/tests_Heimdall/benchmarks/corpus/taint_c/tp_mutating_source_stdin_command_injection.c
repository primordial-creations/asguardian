/* TP: fgets() writes untrusted stdin data INTO the buf output-argument
 * (mutating source), which then reaches system() unsanitized -- textbook
 * C command injection (regression fixture for adversarial-review BLOCKER:
 * mutating sources were previously silently muted entirely). */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char buf[64];
    fgets(buf, 64, stdin);
    system(buf);
}
