app.get('/run', (req, res) => {
    const cmd = req.query.cmd;
    require('child_process').exec(cmd);
    res.send('done');
});
