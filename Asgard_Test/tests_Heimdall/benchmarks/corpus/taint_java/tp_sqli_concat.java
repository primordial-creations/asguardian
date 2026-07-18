public class UserServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String name = request.getParameter("name");
        String sql = "SELECT * FROM users WHERE name = " + name;
        Statement stmt = conn.createStatement();
        stmt.executeQuery(sql);
    }
}
