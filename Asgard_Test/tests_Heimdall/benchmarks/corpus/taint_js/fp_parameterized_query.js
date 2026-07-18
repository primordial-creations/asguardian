app.get('/user', (req, res) => {
    const name = req.query.name;
    db.query('SELECT * FROM users WHERE name = ?', [name]);
    res.send('ok');
});
