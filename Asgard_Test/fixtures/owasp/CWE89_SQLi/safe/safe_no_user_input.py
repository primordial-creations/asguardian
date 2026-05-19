# Safe: hardcoded query, no user input
def get_all_users(db):
    return db.query("SELECT * FROM users ORDER BY id")
