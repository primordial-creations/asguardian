import { Request, Response } from 'express';

app.get('/user', (req: Request, res: Response) => {
    const name = req.query.name;
    const sql = 'SELECT * FROM users WHERE name = ' + name;
    db.query(sql);
    res.send('ok');
});
