const { runQuery } = require('../b/sub/util');

app.get('/user', (req, res) => {
  runQuery(req.query.id);
  res.send('ok');
});
