"""FP sibling: the request value is coerced through int() (an exact
sanitizer -- value-domain restriction to digits only) before being used to
build the path, so path traversal via '../' is impossible."""

import os

BASE = "/srv/uploads"


def download():
    file_id = int(request.args.get("file_id"))
    return open(os.path.join(BASE, str(file_id))).read()
