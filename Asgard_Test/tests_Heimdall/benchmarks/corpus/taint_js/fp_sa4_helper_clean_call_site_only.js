function lookupUser(id) {
    db.query('SELECT * FROM users WHERE id=' + id);
}

// SA4 context-sensitivity sibling: this file only exercises the CLEAN call
// site (literal argument) -- a sinking call site elsewhere must not leak
// taint into this one via a flow-insensitive/summary-conflated resolution.
app.get('/safe', (req, res) => {
    lookupUser('admin');
    res.send('ok');
});
