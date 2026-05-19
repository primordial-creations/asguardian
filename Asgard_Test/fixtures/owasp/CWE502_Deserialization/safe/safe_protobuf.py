from myproto import MyMessage
def parse(data):
    msg = MyMessage()
    msg.ParseFromString(data)
    return msg
