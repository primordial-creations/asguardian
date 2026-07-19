// SA1 container sensitivity, negative: m["a"] = taint; sink(m["b"]).
const m = {};

function handler(req) {
    m["a"] = req.query.name;
    db.query(m["b"]);
}
