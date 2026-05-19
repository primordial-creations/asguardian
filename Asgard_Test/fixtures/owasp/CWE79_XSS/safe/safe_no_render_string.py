from flask import render_template_string
def show():
    return render_template_string("<h1>Hello World</h1>")
