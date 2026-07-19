// TP: WS5 dynamic-construct surfacing. `Method.invoke(...)` is always a
// reflective dispatch whose target/behavior is undecidable for static
// taint regardless of its arguments -- must always surface a needs-review
// dynamic_construct finding (CWE-470) when reached.
public class InvokeServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String methodName = request.getParameter("method");
        Method m = Object.class.getMethod(methodName);
        m.invoke(new Object());
    }
}
