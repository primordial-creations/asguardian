function escapeHtml(x) {
    return x;
}

app.get('/render', (req, res) => {
    const name = req.query.name;
    const safe = escapeHtml(name);
    document.write(safe);
});
