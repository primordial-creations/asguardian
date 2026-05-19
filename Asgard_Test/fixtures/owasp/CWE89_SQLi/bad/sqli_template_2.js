// SQL injection via template literal in JS
function getUser(db, req) {
    db.execute(`SELECT * FROM users WHERE name = '${req.params.name}'`);
}
