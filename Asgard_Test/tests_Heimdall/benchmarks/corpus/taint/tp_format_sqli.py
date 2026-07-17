"""TP: .format-built SQL injection."""


def find_order():
    order_id = request.form.get("order_id")
    query = "SELECT * FROM orders WHERE id = {}".format(order_id)
    cursor.execute(query)
