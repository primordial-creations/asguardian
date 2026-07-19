// FP sibling of tp_dynamic_dispatch_construct.js: a statically-constant
// property key (`handlers["create"](...)`) is ordinary, decidable code --
// must NOT flag as a dynamic construct.
app.get('/run', (req, res) => {
    handlers["create"](req, res);
});
