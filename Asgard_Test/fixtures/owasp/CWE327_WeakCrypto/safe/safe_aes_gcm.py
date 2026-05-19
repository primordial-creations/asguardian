from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
def encrypt(key, data):
    nonce = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.encrypt(data)
