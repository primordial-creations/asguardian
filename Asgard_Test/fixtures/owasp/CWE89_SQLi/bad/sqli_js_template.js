// SQL injection via template literal
function search(db, req) {
    return db.execute(`SELECT * FROM orders WHERE user = '${req.params.user}'`);
}
