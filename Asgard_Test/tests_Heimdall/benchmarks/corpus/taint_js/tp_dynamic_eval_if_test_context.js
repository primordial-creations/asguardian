// Regression fixture (adversarial review, context-coverage): `if
// (eval(req.query.x))` -- a dynamic construct used directly as an `if`
// TEST expression. Confirms the CST walker's generic child-recursion
// (unlike the Python ast.NodeVisitor path, which needed an explicit fix)
// already reaches call_expression nodes inside a condition -- this
// fixture pins that behavior against regression.
app.get('/run', (req, res) => {
    if (eval(req.query.x)) {
        res.send('ok');
    }
});
