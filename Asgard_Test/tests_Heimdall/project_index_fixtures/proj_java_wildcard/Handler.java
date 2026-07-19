import java.util.*;

public class Handler {
    public void handle(HttpServletRequest request) {
        String userInput = request.getParameter("cmd");
        Runtime.exec(userInput);
    }
}
