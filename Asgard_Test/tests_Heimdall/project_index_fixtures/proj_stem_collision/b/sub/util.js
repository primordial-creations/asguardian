function runQuery(id) {
  db.query("SELECT * FROM users WHERE id = " + id);
}
module.exports = { runQuery };
