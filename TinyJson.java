import java.util.*;

// Small JSON reader and writer shared by the two JVM components.
class TinyJson {
    private final String s;
    private int p;
    TinyJson(String source) { s = source; }
    static Object parse(String s) { TinyJson j = new TinyJson(s); Object x = j.read(); j.ws(); if (j.p != s.length()) throw new IllegalArgumentException("trailing JSON"); return x; }
    void ws() { while (p < s.length() && Character.isWhitespace(s.charAt(p))) p++; }
    Object read() {
        ws(); if (p >= s.length()) throw new IllegalArgumentException("unexpected end of JSON");
        char c = s.charAt(p);
        if (c == '"') return string();
        if (c == '{') { p++; Map<String,Object> m = new LinkedHashMap<>(); ws(); if (p < s.length() && s.charAt(p) == '}') { p++; return m; } while (true) { ws(); String k = string(); ws(); if (p >= s.length() || s.charAt(p++) != ':') throw new IllegalArgumentException("expected colon"); m.put(k, read()); ws(); if (p >= s.length()) throw new IllegalArgumentException("unterminated object"); char d = s.charAt(p++); if (d == '}') return m; if (d != ',') throw new IllegalArgumentException("expected comma"); } }
        if (c == '[') { p++; List<Object> a = new ArrayList<>(); ws(); if (p < s.length() && s.charAt(p) == ']') { p++; return a; } while (true) { a.add(read()); ws(); if (p >= s.length()) throw new IllegalArgumentException("unterminated array"); char d = s.charAt(p++); if (d == ']') return a; if (d != ',') throw new IllegalArgumentException("expected comma"); } }
        if (s.startsWith("true", p)) { p += 4; return true; } if (s.startsWith("false", p)) { p += 5; return false; } if (s.startsWith("null", p)) { p += 4; return null; }
        int start = p; while (p < s.length() && "-+0123456789.eE".indexOf(s.charAt(p)) >= 0) p++; if (start == p) throw new IllegalArgumentException("invalid JSON value"); return Double.valueOf(s.substring(start, p));
    }
    String string() { if (p >= s.length() || s.charAt(p++) != '"') throw new IllegalArgumentException("expected string"); StringBuilder b = new StringBuilder(); while (p < s.length()) { char c = s.charAt(p++); if (c == '"') return b.toString(); if (c == '\\') { if (p >= s.length()) throw new IllegalArgumentException("bad escape"); char e = s.charAt(p++); switch (e) { case '"': case '\\': case '/': b.append(e); break; case 'b': b.append('\b'); break; case 'f': b.append('\f'); break; case 'n': b.append('\n'); break; case 'r': b.append('\r'); break; case 't': b.append('\t'); break; case 'u': if (p + 4 > s.length()) throw new IllegalArgumentException("bad unicode"); b.append((char)Integer.parseInt(s.substring(p, p + 4), 16)); p += 4; break; default: throw new IllegalArgumentException("bad escape"); } } else b.append(c); } throw new IllegalArgumentException("unterminated string"); }
    static String quote(String s) { StringBuilder b = new StringBuilder("\""); for (int i = 0; i < s.length(); i++) { char c = s.charAt(i); switch (c) { case '"': b.append("\\\""); break; case '\\': b.append("\\\\"); break; case '\n': b.append("\\n"); break; case '\r': b.append("\\r"); break; case '\t': b.append("\\t"); break; default: if (c < 32) b.append(String.format("\\u%04x", (int)c)); else b.append(c); } } return b.append('"').toString(); }
}
