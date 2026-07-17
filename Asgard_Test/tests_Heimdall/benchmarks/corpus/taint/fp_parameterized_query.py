"""FP sibling: parameterized query -- driver binds the user data."""


def find_user():
    username = request.args.get("username")
    cursor.execute("SELECT * FROM users WHERE name = %s", (username,))
