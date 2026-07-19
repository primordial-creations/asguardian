import { Request, Response } from 'express';

app.get('/ping', (req: Request, res: Response) => {
    child_process.exec('ping -c 1 localhost');
    res.send('ok');
});
