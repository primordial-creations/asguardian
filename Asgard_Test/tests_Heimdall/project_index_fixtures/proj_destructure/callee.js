function handle({ id }) {
    db.query("SELECT * FROM t WHERE id = " + id);
}

module.exports = { handle };
