import jinja2
def user_page(request):
    t = jinja2.Template(request.params.body)
    return t.render()
