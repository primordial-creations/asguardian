public class FileServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        File target = new File("/srv/app/static/welcome.txt");
    }
}
