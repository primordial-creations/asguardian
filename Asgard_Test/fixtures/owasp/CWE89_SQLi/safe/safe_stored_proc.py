# Safe: stored procedure with params
def call_proc(db, value):
    db.callproc("GetUser", [value])
