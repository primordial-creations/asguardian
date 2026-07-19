#include <stdio.h>
#include <stdlib.h>

void handler() {
    char *raw = getenv("N");
    int n = atoi(raw);
    printf("%d", n);
}
