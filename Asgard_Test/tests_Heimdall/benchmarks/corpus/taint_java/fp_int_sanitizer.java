public class IdServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String raw = request.getParameter("id");
        int id = Integer.parseInt(raw);
        Statement stmt = conn.createStatement();
        stmt.executeQuery("SELECT * FROM items WHERE id = " + id);
    }
}
