const { forward } = require('../file2dir/nested/file2');

app.get('/x', (req, res) => {
    forward(req.query.cmd);
    res.send('ok');
});
