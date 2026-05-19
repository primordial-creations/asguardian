const express = require('express');
const app = express();
// Safe: serve from static directory
app.use('/files', express.static('/safe/public'));
