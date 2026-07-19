function q(id) {
    db.query('SELECT * FROM users WHERE id=' + id);
}

module.exports = { q };
