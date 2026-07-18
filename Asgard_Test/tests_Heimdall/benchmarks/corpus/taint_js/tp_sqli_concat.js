const express = require('express');
const app = express();

app.get('/user', (req, res) => {
    const name = req.query.name;
    const sql = 'SELECT * FROM users WHERE name = ' + name;
    db.query(sql);
    res.send('ok');
});
