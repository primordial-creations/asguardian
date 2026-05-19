import jwt
def decode_token(token):
    return jwt.decode(token, algorithms=["none"], options={"verify_signature": False})
