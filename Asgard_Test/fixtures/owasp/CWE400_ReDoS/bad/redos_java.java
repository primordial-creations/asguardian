import java.util.regex.*;
public class Bad {
    static Pattern p = Pattern.compile("(a+)+$");
    static Pattern q = Pattern.compile("([ab]+)+");
}
