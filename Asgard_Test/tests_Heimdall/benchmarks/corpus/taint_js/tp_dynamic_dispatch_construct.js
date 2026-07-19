// TP: WS5 dynamic-construct surfacing. `obj[userKey](...)` -- a computed
// member expression used AS THE CALLEE ITSELF -- means the function being
// invoked is dynamic/attacker-influenced, independent of what taint
// reaches its arguments. Must surface a needs-review dynamic_construct
// finding (CWE-470).
app.get('/run', (req, res) => {
    const action = req.query.action;
    handlers[action](req, res);
});
