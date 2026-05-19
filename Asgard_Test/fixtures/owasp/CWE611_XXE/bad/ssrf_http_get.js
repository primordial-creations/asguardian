const http = require('http');
function proxy(req, res) {
    http.get(req.params.url, (r) => r.pipe(res));
}
