const { exec } = require('child_process');

function runShell(cmd) {
    exec(cmd);
}

module.exports = { runShell };
