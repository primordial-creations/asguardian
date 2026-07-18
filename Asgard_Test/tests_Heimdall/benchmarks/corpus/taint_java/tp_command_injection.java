public class PingServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String host = request.getParameter("host");
        Runtime.getRuntime().exec("ping -c 1 " + host);
    }
}
