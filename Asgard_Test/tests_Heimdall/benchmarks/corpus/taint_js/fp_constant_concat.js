app.get('/status', (req, res) => {
    const sql = 'SELECT * FROM ' + 'status_table';
    db.query(sql);
});
