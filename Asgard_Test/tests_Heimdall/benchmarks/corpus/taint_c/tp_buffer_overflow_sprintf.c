#include <stdio.h>
#include <stdlib.h>

void handler() {
    char *cmd = getenv("MSG");
    char buf[64];
    sprintf(buf, cmd);
}
