// TP: source-detection precision regression (adversarial-review repro).
// Source recognition previously matched ONLY the literal identifier chain
// "request.getParameter" -- i.e. it silently missed a HttpServletRequest
// parameter declared under any OTHER name (`r`, `req`, ...) and/or with a
// FULLY-QUALIFIED type (`javax.servlet.http.HttpServletRequest`), a false
// negative on a routine Java web-input pattern. The type-based fallback
// (`servlet_request_params`, see cst_taint_visitor.py) recognizes any
// HttpServletRequest-typed parameter by TYPE, not by hardcoded name, so
// this exact repro must now flag as command injection (CWE-78).
class J {
    void h(javax.servlet.http.HttpServletRequest r) {
        Runtime.getRuntime().exec(r.getParameter("c"));
    }
}
