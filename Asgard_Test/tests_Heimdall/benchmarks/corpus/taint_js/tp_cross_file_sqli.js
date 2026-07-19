const { q } = require('./tp_cross_file_helper');

app.get('/user', (req, res) => {
    q(req.query.id);
    res.send('ok');
});
