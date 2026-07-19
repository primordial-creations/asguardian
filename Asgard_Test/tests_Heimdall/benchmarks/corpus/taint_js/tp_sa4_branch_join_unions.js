const { exec } = require('child_process');

// SA4 branch-join generalization: one arm assigns the tainted value, the
// other assigns a constant -- the join must UNION (taint on ANY reaching
// path survives), never intersect. This must still flag.
app.post('/ping', (req, res) => {
    const host = req.body.host;
    let cmd;
    if (req.query.flag) {
        cmd = host;
    } else {
        cmd = 'localhost';
    }
    exec('ping -c 1 ' + cmd, (err, stdout) => {
        res.send(stdout);
    });
});
