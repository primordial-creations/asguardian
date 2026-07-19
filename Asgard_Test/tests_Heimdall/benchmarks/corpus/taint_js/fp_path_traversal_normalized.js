const fs = require('fs');
const path = require('path');

app.get('/download', (req, res) => {
    const filename = path.basename(req.query.file);
    fs.readFile(filename, (err, data) => {
        res.send(data);
    });
});
