async function proxy(req, res) {
    const data = await fetch(req.params.url);
    res.send(await data.text());
}
