import hashlib
def compute_hash(data):
    return hashlib.sha1(data).hexdigest()
