import jinja2
def render_dynamic(request):
    env = jinja2.Environment()
    template = jinja2.Template(request.params.template)
    return template.render(name="world")
