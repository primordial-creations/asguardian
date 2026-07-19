import org.owasp.encoder.*;

public class Handler {
    // Locally-declared no-op that happens to share a name+method with a
    // real allow-listed sanitizer class (org.owasp.encoder.Encode.forHtml).
    // Static analysis has no classpath, so it cannot tell this apart from
    // the genuine wildcard-imported class -- it must stay a HEURISTIC
    // sanitizer (partial confidence downgrade), never a full clear.
    static class Encode {
        static String forHtml(String s) {
            return s; // no-op: does not actually sanitize anything
        }
    }

    public void handle(HttpServletRequest request) {
        String userInput = request.getParameter("cmd");
        String safe = Encode.forHtml(userInput);
        Runtime.exec(safe);
    }
}
