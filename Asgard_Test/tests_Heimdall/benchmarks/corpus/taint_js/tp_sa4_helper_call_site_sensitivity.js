function lookupUser(id) {
    db.query('SELECT * FROM users WHERE id=' + id);
}

// SA4 context-sensitivity: the SAME helper is called from a clean call
// site (a literal) and a sinking call site (tainted param). These must
// NOT be conflated -- exactly one flow (from the tainted call site).
app.get('/safe', (req, res) => {
    lookupUser('admin');
    res.send('ok');
});

app.get('/user', (req, res) => {
    const id = req.query.id;
    lookupUser(id);
    res.send('ok');
});
