import msgpack
def decode(data):
    return msgpack.unpackb(data, raw=False)
