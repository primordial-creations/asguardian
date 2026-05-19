from Crypto.Cipher import DES
def encrypt(key, data):
    cipher = DES.new(key)
    return cipher.encrypt(data)
