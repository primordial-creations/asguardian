function renderProfile(req) {
    const bio = req.query.bio;
    document.getElementById('bio').innerHTML = bio;
}
