import pickle
def deserialize(data):
    obj = pickle.loads(data)
    return obj
