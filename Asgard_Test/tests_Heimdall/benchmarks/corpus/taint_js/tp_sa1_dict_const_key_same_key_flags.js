// SA1 container sensitivity, positive: m["a"] = taint; sink(m["a"]).
const m = {};

function handler(req) {
    m["a"] = req.query.name;
    db.query(m["a"]);
}
