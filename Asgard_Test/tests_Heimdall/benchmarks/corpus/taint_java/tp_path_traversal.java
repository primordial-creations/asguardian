public class FileServlet extends HttpServlet {
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws Exception {
        String filename = request.getParameter("file");
        File target = new File(filename);
    }
}
