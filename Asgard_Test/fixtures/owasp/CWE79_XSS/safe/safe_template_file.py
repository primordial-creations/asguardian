from jinja2 import Environment, FileSystemLoader
def render():
    env = Environment(loader=FileSystemLoader("/templates"))
    template = env.get_template("page.html")
    return template.render(name="World")
