# SQL injection via execute with concat
def search(db, request):
    term = request.params.q
    db.execute("SELECT * FROM products WHERE name = '" + request.params.q + "'")
