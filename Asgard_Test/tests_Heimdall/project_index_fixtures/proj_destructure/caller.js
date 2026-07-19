const { handle } = require('./callee');

app.get('/x', (req, res) => {
    handle(req.query);
    res.send('ok');
});
