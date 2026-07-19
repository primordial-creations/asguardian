app.get('/health', (req, res) => {
    fetch('https://internal.example.com/health').then((r) => res.send(r.status));
});
