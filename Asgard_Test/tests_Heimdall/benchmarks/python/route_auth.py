"""Benchmark fixture — python.route-missing-auth (not imported; scanned as text)."""


@app.route("/admin")
def admin_panel():  # ruleid: python.route-missing-auth
    return render("admin")


@app.route("/dashboard")
@login_required
def dashboard():
    return render("dash")


def docs_example():
    """Usage:

    @app.route("/example")
    def example_handler():  # ok: python.route-missing-auth
        pass
    """
    return None
