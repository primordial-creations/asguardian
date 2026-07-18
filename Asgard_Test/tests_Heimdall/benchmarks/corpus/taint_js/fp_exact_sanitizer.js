app.get('/search', (req, res) => {
    const q = req.query.q;
    const safe = encodeURIComponent(q);
    res.redirect('/results?q=' + safe);
});
