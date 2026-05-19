# Safe: ORM usage
def get_items(session, item_id):
    return session.query(Item).filter(Item.id == item_id).all()
