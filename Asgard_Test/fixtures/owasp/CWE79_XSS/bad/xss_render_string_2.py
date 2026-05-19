from flask import render_template_string, request
def display_page():
    content = request.params.page
    html = render_template_string(f"<html>{content}</html>")
    return html
