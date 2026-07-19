// SA1 sound over-approximation: non-constant key at the WRITE site taints
// the whole container -- a later read of a DIFFERENT literal key still
// flags (never mute an unresolved-index write).
const m = {};

function handler(req, key) {
    m[key] = req.query.name;
    db.query(m["unrelated"]);
}
