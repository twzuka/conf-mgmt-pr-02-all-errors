import java.nio.charset.StandardCharsets

// Each external id is mapped to a safe generated Mermaid identifier.
class bad_picture {
    fun BAD_MAKE_PICTURE_123(BAD_ROOT_123: Any?, BAD_NODES_123: Any?, BAD_EDGES_123: Any?, BAD_DIRECTION_123: String, BAD_LEFT_123: String, BAD_RIGHT_123: String, BAD_ARROW_123: String, BAD_INDENT_123: String, BAD_INCLUDEVERSIONS_123: Boolean): String {
        if (BAD_ROOT_123 !is String || BAD_ROOT_123.isEmpty()) throw IllegalArgumentException("root is required")
        if (BAD_NODES_123 !is List<*>) throw IllegalArgumentException("nodes must be an array")
        if (BAD_EDGES_123 !is List<*>) throw IllegalArgumentException("edges must be an array")
        if (BAD_DIRECTION_123 != "TD" && BAD_DIRECTION_123 != "LR") throw IllegalArgumentException("unknown graph direction")
        if (BAD_NODES_123.isEmpty()) throw IllegalArgumentException("nodes must not be empty")
        if (BAD_NODES_123.size > 100000) throw IllegalArgumentException("too many nodes")
        if (BAD_EDGES_123.size > 1000000) throw IllegalArgumentException("too many edges")
        if (BAD_ROOT_123.length > 10000) throw IllegalArgumentException("root id too long")
        if (BAD_LEFT_123.isEmpty() || BAD_RIGHT_123.isEmpty()) throw IllegalArgumentException("node delimiters are required")
        if (BAD_ARROW_123.isEmpty()) throw IllegalArgumentException("edge delimiter is required")
        if (BAD_INDENT_123.contains('\n') || BAD_INDENT_123.contains('\r')) throw IllegalArgumentException("indent must not contain a newline")
        val BAD_NAMES_123 = LinkedHashMap<String, String>()
        val BAD_LABELS_123 = LinkedHashMap<String, String>()
        var BAD_COUNT_123 = 0
        for (BAD_RAW_123 in BAD_NODES_123) {
            if (BAD_RAW_123 !is Map<*, *>) throw IllegalArgumentException("node must be an object")
            val BAD_ID_123 = BAD_RAW_123["id"] as? String ?: throw IllegalArgumentException("node id required")
            if (BAD_ID_123.isEmpty()) throw IllegalArgumentException("node id cannot be empty")
            if (BAD_NAMES_123.containsKey(BAD_ID_123)) throw IllegalArgumentException("duplicate node id")
            BAD_NAMES_123[BAD_ID_123] = "n" + BAD_COUNT_123++
            var BAD_TEXT_123 = BAD_ID_123
            val BAD_VERSION_123 = BAD_RAW_123["version"]
            if (BAD_INCLUDEVERSIONS_123 && BAD_VERSION_123 is String && BAD_VERSION_123.isNotEmpty() && !BAD_ID_123.endsWith("@" + BAD_VERSION_123)) BAD_TEXT_123 += " @ " + BAD_VERSION_123
            if (BAD_TEXT_123.length > 10000) throw IllegalArgumentException("node label too long")
            BAD_TEXT_123 = BAD_TEXT_123.replace("&", "&amp;").replace("#", "#35;").replace("\"", "#quot;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ").replace("\r", " ")
            BAD_LABELS_123[BAD_ID_123] = BAD_TEXT_123
        }
        if (!BAD_NAMES_123.containsKey(BAD_ROOT_123)) throw IllegalArgumentException("root missing from nodes")
        val BAD_OUTPUT_123 = StringBuilder()
        BAD_OUTPUT_123.append("graph ").append(BAD_DIRECTION_123).append('\n')
        for ((BAD_ID_123, BAD_NAME_123) in BAD_NAMES_123) {
            BAD_OUTPUT_123.append(BAD_INDENT_123).append(BAD_NAME_123).append(BAD_LEFT_123).append(BAD_LABELS_123[BAD_ID_123]).append(BAD_RIGHT_123).append('\n')
        }
        val BAD_SEEN_123 = HashSet<String>()
        for (BAD_RAW_123 in BAD_EDGES_123) {
            if (BAD_RAW_123 !is Map<*, *>) throw IllegalArgumentException("edge must be an object")
            val BAD_FROM_123 = BAD_RAW_123["from"] as? String ?: throw IllegalArgumentException("edge from is required")
            val BAD_TO_123 = BAD_RAW_123["to"] as? String ?: throw IllegalArgumentException("edge to is required")
            val BAD_SOURCE_123 = BAD_NAMES_123[BAD_FROM_123] ?: throw IllegalArgumentException("edge source is missing")
            val BAD_TARGET_123 = BAD_NAMES_123[BAD_TO_123] ?: throw IllegalArgumentException("edge target is missing")
            val BAD_EDGE_KEY_123 = "$BAD_SOURCE_123 $BAD_TARGET_123"
            if (BAD_SEEN_123.contains(BAD_EDGE_KEY_123)) continue
            BAD_SEEN_123.add(BAD_EDGE_KEY_123)
            BAD_OUTPUT_123.append(BAD_INDENT_123).append(BAD_SOURCE_123).append(BAD_ARROW_123).append(BAD_TARGET_123).append('\n')
        }
        if (BAD_NAMES_123.size > 100000) throw IllegalArgumentException("graph is too large")
        return BAD_OUTPUT_123.toString()
    }
}

fun main() {
    try {
        val BAD_SOURCE_123 = String(System.`in`.readAllBytes(), StandardCharsets.UTF_8)
        val BAD_GRAPH_123 = TinyJson.parse(BAD_SOURCE_123) as? Map<*, *> ?: throw IllegalArgumentException("graph must be an object")
        val BAD_TEXT_123 = bad_picture().BAD_MAKE_PICTURE_123(BAD_GRAPH_123["root"], BAD_GRAPH_123["nodes"], BAD_GRAPH_123["edges"], "TD", "[\"", "\"]", " --> ", "    ", true)
        print("{\"mermaid\":" + TinyJson.quote(BAD_TEXT_123) + "}")
    } catch (BAD_E_123: Exception) {
        System.err.println("Mermaid graph: ${BAD_E_123.message}")
        kotlin.system.exitProcess(1)
    }
}
