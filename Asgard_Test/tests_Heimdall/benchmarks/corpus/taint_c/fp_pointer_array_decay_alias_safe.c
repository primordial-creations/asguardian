/* FP sibling of tp_pointer_array_decay_alias.c: `p` decays from a
 * SEPARATE, never-tainted array -- must stay clean. */
#include <stdio.h>
#include <stdlib.h>

void run(void) {
    char arr[64];
    char safe[64] = "echo hi";
    char *p = safe;
    fgets(arr, 64, stdin);
    system(p);
}
