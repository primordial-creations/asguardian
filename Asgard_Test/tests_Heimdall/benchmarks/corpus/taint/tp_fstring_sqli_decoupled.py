"""TP: f-string SQL injection with source and sink decoupled across lines."""


def find_user():
    username = request.args.get("username")
    greeting = "unrelated"
    query = f"SELECT * FROM users WHERE name = '{username}'"
    print(greeting)
    cursor.execute(query)
