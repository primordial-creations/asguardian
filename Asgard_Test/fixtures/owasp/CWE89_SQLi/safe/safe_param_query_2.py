# Safe: named parameter placeholders
def search_products(db, search_term):
    db.execute("SELECT * FROM products WHERE name = :term", {"term": search_term})
