const { runShell } = require('../../file3dir/file3');

function forward(cmd) {
    runShell(cmd);
}

module.exports = { forward };
