import java.util.regex.*;
public class Safe {
    static Pattern p = Pattern.compile("^[a-zA-Z0-9]{1,50}$");
    static boolean check(String s) {
        return p.matcher(s).matches();
    }
}
