/* TP: WS4 C format-arg generalization. `vsnprintf` is a `v`-prefixed
 * va_list variant not previously in `_C_FORMAT_ARG_INDEX`/`C_SINK_SPECS`;
 * its format-string argument sits at the same index (2) as its non-`v`
 * counterpart `snprintf`. The format string itself is attacker-controlled
 * here (getenv), so this must flag as FORMAT_STRING/CWE-134 -- proving the
 * generalized `_c_format_arg_index()` resolves `v`-prefixed names. */
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

void run(const char *fallback, ...) {
    char buf[128];
    char *fmt = getenv("FMT");
    va_list ap;
    va_start(ap, fallback);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
}
