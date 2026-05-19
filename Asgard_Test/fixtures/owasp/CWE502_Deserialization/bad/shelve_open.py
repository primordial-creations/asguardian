import shelve
def read_store(path):
    db = shelve.open(path)
    return db["key"]
