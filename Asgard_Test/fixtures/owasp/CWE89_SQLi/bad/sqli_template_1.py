# SQL injection via template literal
def delete_item(db, request):
    item_id = request.params.id
    db.execute(f"DELETE FROM items WHERE id = {request.params.id}")
