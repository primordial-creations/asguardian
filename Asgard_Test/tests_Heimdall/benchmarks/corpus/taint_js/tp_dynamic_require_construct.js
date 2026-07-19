// TP: WS5 dynamic-construct surfacing. `require(userVar)` -- a dynamic
// module load whose target module name is attacker-influenced -- is
// undecidable for static taint (arbitrary module code could execute) and
// must surface a needs-review dynamic_construct finding (CWE-470).
app.get('/run', (req, res) => {
    const mod = req.query.mod;
    const m = require(mod);
    res.send(String(m));
});
