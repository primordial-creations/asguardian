from flask import render_template
def page():
    return render_template("index.html", title="Welcome")
