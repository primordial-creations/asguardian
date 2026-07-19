// TP: WS5 dynamic-construct surfacing. `Class.forName(userVar)` loads and
// initializes an attacker-influenced class name -- undecidable for static
// taint (arbitrary static initializers could execute) -- must surface a
// needs-review dynamic_construct finding (CWE-470).
public class ReflectionServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String className = request.getParameter("class");
        Class<?> clazz = Class.forName(className);
        response.getWriter().write(clazz.getName());
    }
}
