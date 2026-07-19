// FP sibling of tp_reflection_class_forname_construct.java: a
// statically-constant class name must NOT flag -- there is nothing
// attacker-influenced about it.
public class ReflectionConstantServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        Class<?> clazz = Class.forName("java.lang.String");
        response.getWriter().write(clazz.getName());
    }
}
