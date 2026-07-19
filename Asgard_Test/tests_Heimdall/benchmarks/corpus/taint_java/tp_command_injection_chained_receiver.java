public class ChainedExecServlet extends HttpServlet {
    // Java sink fix (bonus): `Runtime rt = Runtime.getRuntime(); rt.exec(...)`
    // -- the chained getRuntime().exec idiom via a LOCAL VARIABLE receiver
    // (not the inline `Runtime.getRuntime().exec(...)` form already covered
    // by tp_command_injection.java) must still resolve to the SHELL_COMMAND
    // sink via the generic ".exec" catalog fallback.
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String host = request.getParameter("host");
        Runtime rt = Runtime.getRuntime();
        rt.exec("ping -c 1 " + host);
    }
}
