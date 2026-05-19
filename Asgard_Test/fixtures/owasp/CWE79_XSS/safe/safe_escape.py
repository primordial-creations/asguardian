from markupsafe import escape
def render(user_input):
    safe = escape(user_input)
    return f"<p>{safe}</p>"
