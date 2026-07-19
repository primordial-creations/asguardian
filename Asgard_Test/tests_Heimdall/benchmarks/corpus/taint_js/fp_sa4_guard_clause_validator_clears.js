const { exec } = require('child_process');

// SA4 path-sensitivity: a classic early-return guard clause built on a
// REAL, catalog-whitelisted value-domain predicate (Number.isInteger --
// receiver-qualified, unshadowable). Every path that reaches the exec()
// call below has been proven to have a finite-number `host`, which cannot
// carry a shell-injection payload -- the guarded/validated path is clean.
app.post('/ping', (req, res) => {
    const host = req.body.host;
    if (!Number.isInteger(host)) {
        return res.status(400).send('invalid');
    }
    exec('ping -c 1 ' + host, (err, stdout) => {
        res.send(stdout);
    });
});
