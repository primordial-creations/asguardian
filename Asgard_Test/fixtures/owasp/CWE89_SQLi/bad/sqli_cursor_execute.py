# SQL injection via cursor.execute
def fetch_data(cursor, request):
    name = request.params.name
    cursor.execute("SELECT * FROM data WHERE col='" + request.params.name + "'")
    return cursor.fetchall()
