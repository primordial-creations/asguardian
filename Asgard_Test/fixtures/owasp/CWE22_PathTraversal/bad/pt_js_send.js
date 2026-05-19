// Path traversal via res.sendFile
function download(req, res) {
    res.sendFile(req.params.path);
}
