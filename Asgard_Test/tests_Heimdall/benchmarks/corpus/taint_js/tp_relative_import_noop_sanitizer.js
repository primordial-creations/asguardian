const { escapeHtml } = require('./evil_local_utils');

app.get('/render', (req, res) => {
    const name = req.query.name;
    const safe = escapeHtml(name);
    document.write(safe);
});
