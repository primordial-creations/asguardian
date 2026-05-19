# SQL injection via string concatenation
def get_user(db, request):
    uid = request.params.user_id
    result = db.query("SELECT * FROM users WHERE id = " + request.params.user_id)
    return result
