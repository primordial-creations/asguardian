const fs = require('fs');

app.get('/download', (req, res) => {
    const filename = req.query.file;
    fs.readFile(filename, (err, data) => {
        res.send(data);
    });
});
