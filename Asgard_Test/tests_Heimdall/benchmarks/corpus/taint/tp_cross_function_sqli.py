"""TP: source in one function, sink in another (1 hop)."""


def run_query(sql):
    cursor.execute(sql)


def handler():
    q = request.args.get("q")
    run_query(q)
