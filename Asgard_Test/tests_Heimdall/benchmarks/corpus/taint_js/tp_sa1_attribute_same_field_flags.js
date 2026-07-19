// SA1 field sensitivity, positive: x.a = taint; sink(x.a) -- same field,
// must flag.
const x = {};

function handler(req) {
    x.a = req.query.name;
    db.query(x.a);
}
