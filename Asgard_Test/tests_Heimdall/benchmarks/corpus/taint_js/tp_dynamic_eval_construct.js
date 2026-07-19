// TP: WS5 dynamic-construct surfacing. `eval(x)` reached with a tainted,
// non-constant operand is undecidable for static taint (could run
// anything) -- must surface an explicit needs-review dynamic_construct
// finding (CWE-470), independent of whatever the normal sink pass does.
app.get('/run', (req, res) => {
    const code = req.query.code;
    eval(code);
    res.send('done');
});
