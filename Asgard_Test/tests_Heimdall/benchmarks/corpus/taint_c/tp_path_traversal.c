#include <stdio.h>
#include <stdlib.h>

void handler() {
    char *path = getenv("FILE");
    FILE *f = fopen(path, "r");
}
