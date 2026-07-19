/* TP: SA3 struct-pointer field aliasing. `s->field = tainted;` then
 * `t = s;` (a plain pointer copy, unioning t and s's alias groups) then
 * `system(t->field);` must flag -- Wave 1's field-sensitivity already
 * handled `s->field` read straight back through `s`, but a field write
 * recorded before the alias union was, before SA3, keyed under the
 * NON-canonical root and invisible through the aliased name `t`. */
#include <stdio.h>
#include <stdlib.h>

struct cmd_ctx {
    char *field;
};

void run(void) {
    struct cmd_ctx rec;
    struct cmd_ctx *s = &rec;
    char buf[64];
    fgets(buf, 64, stdin);
    s->field = buf;
    struct cmd_ctx *t = s;
    system(t->field);
}
