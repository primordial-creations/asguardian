app.get('/proxy', (req, res) => {
    const target = req.query.url;
    fetch(target).then((r) => r.text()).then((body) => res.send(body));
});
