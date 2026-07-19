/* FP: constant/safe format literal with only a VALUE argument tainted is
 * not a format-string vulnerability (adversarial review MAJOR-3).
 * snprintf is bounded (size-limited), so it must not be treated as a
 * buffer_overflow sink either. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char *msg = getenv("MSG");
    char buf[128];
    printf("%s", msg);
    snprintf(buf, sizeof buf, "%s", msg);
}
