/* FP sibling of tp_pointer_struct_field_alias.c: `s` and `t` point at
 * DISTINCT struct instances (`t` is never assigned from `s`), so `s`'s
 * tainted field must not be visible through `t->field`. */
#include <stdio.h>
#include <stdlib.h>

struct cmd_ctx {
    char *field;
};

void run(void) {
    struct cmd_ctx rec_s;
    struct cmd_ctx rec_t;
    struct cmd_ctx *s = &rec_s;
    struct cmd_ctx *t = &rec_t;
    char buf[64];
    char safe[64] = "echo hi";
    fgets(buf, 64, stdin);
    s->field = buf;
    t->field = safe;
    system(t->field);
}
