import { Request, Response } from 'express';

app.get('/user', (req: Request, res: Response) => {
    const name = req.query.name;
    db.query('SELECT * FROM users WHERE name = ?', [name]);
    res.send('ok');
});
