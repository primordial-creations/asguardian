const axios = require('axios');
async function forward(req, res) {
    const response = await axios.get(req.params.target);
    res.json(response.data);
}
