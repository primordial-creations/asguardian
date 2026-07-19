// SA1 field sensitivity, negative: x.a = taint; sink(x.b) -- a DIFFERENT
// field, must NOT flag.
const x = {};

function handler(req) {
    x.a = req.query.name;
    db.query(x.b);
}
