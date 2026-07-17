"""FP sibling: f-string SQL built only from constants."""

TABLE = "users"


def list_users():
    query = f"SELECT * FROM {TABLE} ORDER BY id"
    cursor.execute(query)
