from flask import render_template_string, request
def page():
    user_input = request.params.content
    return render_template_string(user_input)
