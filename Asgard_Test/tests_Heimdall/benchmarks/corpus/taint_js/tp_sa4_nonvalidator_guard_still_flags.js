const { exec } = require('child_process');

// SA4 path-sensitivity (mute-bug guard case): `host !== null` is NOT a
// catalog-verified value-domain predicate -- it proves nothing about the
// character content of `host`. The engine must NOT invent a semantic
// validator here; the guarded path must still flag.
app.post('/ping', (req, res) => {
    const host = req.body.host;
    if (host !== null) {
        exec('ping -c 1 ' + host, (err, stdout) => {
            res.send(stdout);
        });
    }
});
