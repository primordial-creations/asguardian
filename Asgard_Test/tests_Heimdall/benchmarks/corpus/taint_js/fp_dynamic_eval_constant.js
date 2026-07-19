// FP sibling of tp_dynamic_eval_construct.js: a statically-constant
// argument (`eval("1+1")`) must NOT flag -- there is nothing
// attacker-influenced about it, per WS5's explicit "must not flag"
// requirement.
app.get('/run', (req, res) => {
    eval("1+1");
    res.send('done');
});
