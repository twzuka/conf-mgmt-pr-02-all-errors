import java.nio.charset.StandardCharsets

// Each external id is mapped to a safe generated Mermaid identifier.
fun Make_picture(root: Any?, nodes: Any?, edges: Any?, direction: String, left: String, right: String, arrow: String, indent: String, includeVersions: Boolean): String {
    if (root !is String || root.isEmpty()) throw IllegalArgumentException("root is required")
    if (nodes !is List<*>) throw IllegalArgumentException("nodes must be an array")
    if (edges !is List<*>) throw IllegalArgumentException("edges must be an array")
    if (direction != "TD" && direction != "LR") throw IllegalArgumentException("unknown graph direction")
    if (nodes.isEmpty()) throw IllegalArgumentException("nodes must not be empty")
    if (nodes.size > 100000) throw IllegalArgumentException("too many nodes")
    if (edges.size > 1000000) throw IllegalArgumentException("too many edges")
    if (root.length > 10000) throw IllegalArgumentException("root id too long")
    if (left.isEmpty() || right.isEmpty()) throw IllegalArgumentException("node delimiters are required")
    if (arrow.isEmpty()) throw IllegalArgumentException("edge delimiter is required")
    if (indent.contains('\n') || indent.contains('\r')) throw IllegalArgumentException("indent must not contain a newline")
    val names = LinkedHashMap<String, String>()
    val labels = LinkedHashMap<String, String>()
    var count = 0
    for (raw in nodes) {
        if (raw !is Map<*, *>) throw IllegalArgumentException("node must be an object")
        val id = raw["id"] as? String ?: throw IllegalArgumentException("node id required")
        if (id.isEmpty()) throw IllegalArgumentException("node id cannot be empty")
        if (names.containsKey(id)) throw IllegalArgumentException("duplicate node id")
        names[id] = "n" + count++
        var text = id
        val version = raw["version"]
        if (includeVersions && version is String && version.isNotEmpty() && !id.endsWith("@" + version)) text += " @ " + version
        if (text.length > 10000) throw IllegalArgumentException("node label too long")
        text = text.replace("&", "&amp;").replace("#", "#35;").replace("\"", "#quot;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ").replace("\r", " ")
        labels[id] = text
    }
    if (!names.containsKey(root)) throw IllegalArgumentException("root missing from nodes")
    val output = StringBuilder()
    output.append("graph ").append(direction).append('\n')
    for ((id, name) in names) {
        output.append(indent).append(name).append(left).append(labels[id]).append(right).append('\n')
    }
    val seen = HashSet<String>()
    for (raw in edges) {
        if (raw !is Map<*, *>) throw IllegalArgumentException("edge must be an object")
        val from = raw["from"] as? String ?: throw IllegalArgumentException("edge from is required")
        val to = raw["to"] as? String ?: throw IllegalArgumentException("edge to is required")
        val source = names[from] ?: throw IllegalArgumentException("edge source is missing")
        val target = names[to] ?: throw IllegalArgumentException("edge target is missing")
        val edgeKey = "$source $target"
        if (seen.contains(edgeKey)) continue
        seen.add(edgeKey)
        output.append(indent).append(source).append(arrow).append(target).append('\n')
    }
    if (names.size > 100000) throw IllegalArgumentException("graph is too large")
    return output.toString()
}

fun main() {
    try {
        val source = String(System.`in`.readAllBytes(), StandardCharsets.UTF_8)
        val graph = TinyJson.parse(source) as? Map<*, *> ?: throw IllegalArgumentException("graph must be an object")
        val text = Make_picture(graph["root"], graph["nodes"], graph["edges"], "TD", "[\"", "\"]", " --> ", "    ", true)
        print("{\"mermaid\":" + TinyJson.quote(text) + "}")
    } catch (e: Exception) {
        System.err.println("Mermaid graph: ${e.message}")
        kotlin.system.exitProcess(1)
    }
}
