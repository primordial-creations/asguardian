const cp = require('child_process');

app.get('/run', (req, res) => {
    const cmd = req.query.cmd;
    cp.exec(cmd);
    res.send('done');
});
