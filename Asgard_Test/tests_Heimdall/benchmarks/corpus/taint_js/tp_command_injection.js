const { exec } = require('child_process');

app.post('/ping', (req, res) => {
    const host = req.body.host;
    exec('ping -c 1 ' + host, (err, stdout) => {
        res.send(stdout);
    });
});
