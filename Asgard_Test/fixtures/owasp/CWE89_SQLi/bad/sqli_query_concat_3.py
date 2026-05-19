# SQL injection in login function
def login(db, request):
    user = request.params.username
    pwd = request.params.password
    db.query("SELECT * FROM auth WHERE user='" + request.params.username + "'")
