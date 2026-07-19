/* TP: the FORMAT-STRING argument itself is attacker-controlled (not just a
 * value argument under a constant format) -- a genuine format-string
 * vulnerability (CWE-134), e.g. `printf(userfmt)` letting an attacker
 * inject `%s`/`%n` specifiers. Must still flag after MAJOR-3's fix. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char *fmt = getenv("FMT");
    printf(fmt);
}
