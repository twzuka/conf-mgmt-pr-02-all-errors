import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

// This program constructs the ASCII tree even when printing it is disabled.
public class ascii_bad {
    static class Item {
        String id, prefix;
        boolean last, exit;
        Item(String i, String p, boolean l, boolean e) { id = i; prefix = p; last = l; exit = e; }
    }

    // Walk edges while keeping the current path and already expanded nodes.
    @SuppressWarnings("unchecked")
    static String Build_Tree(Object rootValue, Object nodeValues, Object edgeValues, String prefix, String branch, String lastBranch, String vertical, String space, int maxSteps) {
        if (!(rootValue instanceof String)) throw new IllegalArgumentException("root is required");
        if (!(nodeValues instanceof List)) throw new IllegalArgumentException("nodes must be an array");
        if (!(edgeValues instanceof List)) throw new IllegalArgumentException("edges must be an array");
        if (((List<?>) nodeValues).size() > 1000000) throw new IllegalArgumentException("too many nodes");
        String root = (String) rootValue;
        Map<String, String> labels = new LinkedHashMap<>();
        Map<String, List<String>> adj = new LinkedHashMap<>();
        for (Object value : (List<?>) nodeValues) {
            if (!(value instanceof Map)) throw new IllegalArgumentException("node must be an object");
            Map<String, Object> node = (Map<String, Object>) value;
            Object rawId = node.get("id");
            if (!(rawId instanceof String)) throw new IllegalArgumentException("node id is required");
            String id = (String) rawId;
            Object version = node.get("version");
            String text = id;
            if (version instanceof String && !((String) version).isEmpty() && !id.endsWith("@" + version)) text += " @ " + version;
            labels.put(id, text);
            adj.putIfAbsent(id, new ArrayList<>());
        }
        if (!labels.containsKey(root)) throw new IllegalArgumentException("root missing from nodes");
        for (Object value : (List<?>) edgeValues) {
            if (!(value instanceof Map)) throw new IllegalArgumentException("edge must be an object");
            Map<String, Object> edge = (Map<String, Object>) value;
            Object from = edge.get("from"), to = edge.get("to");
            if (!(from instanceof String) || !(to instanceof String)) throw new IllegalArgumentException("edge endpoints are required");
            if (!adj.containsKey(from) || !adj.containsKey(to)) throw new IllegalArgumentException("edge endpoint missing from nodes");
            adj.get(from).add((String) to);
        }
        StringBuilder result = new StringBuilder();
        Set<String> expanded = new HashSet<>(), active = new HashSet<>();
        Deque<Item> pending = new ArrayDeque<>();
        pending.push(new Item(root, prefix, true, false));
        int steps = 0;
        while (!pending.isEmpty()) {
            Item item = pending.pop();
            if (item.exit) { active.remove(item.id); continue; }
            if (++steps > maxSteps) throw new IllegalArgumentException("tree is too large");
            boolean isRoot = steps == 1;
            if (isRoot) result.append(labels.get(item.id));
            else result.append(item.prefix).append(item.last ? lastBranch : branch).append(labels.get(item.id));
            if (active.contains(item.id)) { result.append(" [cycle]\n"); continue; }
            if (expanded.contains(item.id)) { result.append(" [shared]\n"); continue; }
            result.append('\n');
            expanded.add(item.id);
            active.add(item.id);
            pending.push(new Item(item.id, "", true, true));
            List<String> children = adj.get(item.id);
            String childPrefix = isRoot ? prefix : item.prefix + (item.last ? space : vertical);
            for (int i = children.size() - 1; i >= 0; i--) {
                pending.push(new Item(children.get(i), childPrefix, i == children.size() - 1, false));
            }
        }
        return result.toString();
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        try {
            String input = new String(System.in.readAllBytes(), StandardCharsets.UTF_8);
            Map<String, Object> graph = (Map<String, Object>) TinyJson.parse(input);
            String tree = Build_Tree(graph.get("root"), graph.get("nodes"), graph.get("edges"), "", "+-- ", "`-- ", "|   ", "    ", 1000000);
            System.out.print("{\"ascii\":" + TinyJson.quote(tree) + "}");
        } catch (Exception e) { System.err.println("ASCII graph: " + e.getMessage()); System.exit(1); }
    }
}
