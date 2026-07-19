"""TP: unsafe deserialization -- attacker-controlled bytes passed to pickle.loads."""

import pickle


def load_session():
    blob = request.args.get("session")
    obj = pickle.loads(blob)
    return obj
