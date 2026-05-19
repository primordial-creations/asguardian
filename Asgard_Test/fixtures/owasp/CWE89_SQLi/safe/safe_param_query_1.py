# Safe: parameterized query
def get_user(db, user_id):
    result = db.query("SELECT * FROM users WHERE id = ?", (user_id,))
    return result
