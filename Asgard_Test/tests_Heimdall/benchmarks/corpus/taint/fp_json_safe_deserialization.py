"""FP sibling: json.loads is not a deserialization sink (no arbitrary-object
unpickling), so request-controlled input here must not raise a flow."""

import json


def load_session():
    blob = request.args.get("session")
    return json.loads(blob)
