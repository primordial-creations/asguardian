function lookupUser(id) {
    db.query('SELECT * FROM users WHERE id=' + id);
}

app.get('/user', (req, res) => {
    const id = req.query.id;
    lookupUser(id);
    res.send('ok');
});
