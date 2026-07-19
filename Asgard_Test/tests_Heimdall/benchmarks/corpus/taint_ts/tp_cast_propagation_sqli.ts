import { Request, Response } from 'express';

app.get('/user', (req: Request, res: Response) => {
    const host = req.query.host as string;
    const sql = 'SELECT * FROM users WHERE host = ' + host;
    db.query(sql);
    res.send('ok');
});
