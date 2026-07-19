import { exec } from 'child_process';
import { Request, Response } from 'express';

app.get('/ping', (req: Request, res: Response) => {
    const host = req.query.host;
    child_process.exec('ping -c 1 ' + host);
    res.send('ok');
});
