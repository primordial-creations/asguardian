// Path traversal via fs.readFile
const fs = require('fs');
function readFile(req, res) {
    fs.readFile(req.params.file, (err, data) => res.send(data));
}
