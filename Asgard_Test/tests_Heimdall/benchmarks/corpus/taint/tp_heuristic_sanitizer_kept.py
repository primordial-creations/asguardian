"""TP (downgraded): custom sanitize_* cannot be verified statically --
the flow is kept at the 'possible' bucket instead of silently dropped."""


def find_user():
    username = request.args.get("username")
    safe = sanitize_username(username)
    cursor.execute("SELECT * FROM users WHERE name = '" + safe + "'")
