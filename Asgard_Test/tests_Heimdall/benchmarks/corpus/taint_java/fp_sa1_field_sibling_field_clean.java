public class UserServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        Ctx ctx = new Ctx();
        ctx.tainted = request.getParameter("name");
        Statement stmt = conn.createStatement();
        stmt.executeQuery(ctx.clean);
    }
}
