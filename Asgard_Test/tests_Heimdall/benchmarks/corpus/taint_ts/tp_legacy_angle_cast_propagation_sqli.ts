import { Request, Response } from 'express';

app.get('/user', (req: Request, res: Response) => {
    const host = <string>req.query.host;
    const sql = 'SELECT * FROM users WHERE host = ' + host;
    db.query(sql);
    res.send('ok');
});
