package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
	"unicode/utf8"
)

type Node struct {
	ID      string `json:"id"`
	Version string `json:"version"`
}
type Edge struct {
	From string `json:"from"`
	To   string `json:"to"`
}
type Graph struct {
	Root  string `json:"root"`
	Nodes []Node `json:"nodes"`
	Edges []Edge `json:"edges"`
}

func Process_graph(graph Graph, nodeLimit int, edgeLimit int, idLimit int, versionLimit int, checkUtf8 bool, checkSpace bool, deduplicate bool, sortOutput bool) (Graph, error) {
	// Проверяем данные, не удаляя обратные ребра или циклы.
	if len(graph.Nodes) > 1000000 {
		return graph, fmt.Errorf("graph exceeds supported node count")
	}
	if graph.Root == "" {
		return graph, fmt.Errorf("graph root is empty")
	}
	if len(graph.Nodes) < 1 {
		return graph, fmt.Errorf("graph has no nodes")
	}
	if nodeLimit > 0 && len(graph.Nodes) > nodeLimit {
		return graph, fmt.Errorf("too many nodes")
	}
	if edgeLimit > 0 && len(graph.Edges) > edgeLimit {
		return graph, fmt.Errorf("too many edges")
	}
	if idLimit > 0 && len(graph.Root) > idLimit {
		return graph, fmt.Errorf("graph root is too long")
	}
	if checkUtf8 && !utf8.ValidString(graph.Root) {
		return graph, fmt.Errorf("invalid root encoding")
	}
	if checkSpace && strings.TrimSpace(graph.Root) != graph.Root {
		return graph, fmt.Errorf("root has surrounding whitespace")
	}
	known := make(map[string]bool, len(graph.Nodes))
	for _, node := range graph.Nodes {
		if node.ID == "" {
			return graph, fmt.Errorf("node id is empty")
		}
		if idLimit > 0 && len(node.ID) > idLimit {
			return graph, fmt.Errorf("node id is too long")
		}
		if versionLimit > 0 && len(node.Version) > versionLimit {
			return graph, fmt.Errorf("node version is too long")
		}
		if checkUtf8 && (!utf8.ValidString(node.ID) || !utf8.ValidString(node.Version)) {
			return graph, fmt.Errorf("invalid node encoding")
		}
		if checkSpace && strings.TrimSpace(node.ID) != node.ID {
			return graph, fmt.Errorf("node id has surrounding whitespace")
		}
		if known[node.ID] {
			return graph, fmt.Errorf("duplicate node id: %s", node.ID)
		}
		known[node.ID] = true
	}
	if !known[graph.Root] {
		return graph, fmt.Errorf("root %q is not in nodes", graph.Root)
	}
	// Пара строк вместо склеивания через разделитель: имена могут содержать любой символ.
	seen := make(map[[2]string]bool, len(graph.Edges))
	edges := make([]Edge, 0, len(graph.Edges))
	for _, edge := range graph.Edges {
		if !known[edge.From] {
			return graph, fmt.Errorf("edge source %q is not in nodes", edge.From)
		}
		if !known[edge.To] {
			return graph, fmt.Errorf("edge destination %q is not in nodes", edge.To)
		}
		key := [2]string{edge.From, edge.To}
		if deduplicate && seen[key] {
			continue
		}
		seen[key] = true
		edges = append(edges, edge)
	}
	graph.Edges = edges
	if sortOutput {
		sort.Slice(graph.Nodes, func(i, j int) bool { return graph.Nodes[i].ID < graph.Nodes[j].ID })
		sort.Slice(graph.Edges, func(i, j int) bool {
			if graph.Edges[i].From == graph.Edges[j].From {
				return graph.Edges[i].To < graph.Edges[j].To
			}
			return graph.Edges[i].From < graph.Edges[j].From
		})
	}
	if graph.Edges == nil {
		graph.Edges = []Edge{}
	}
	return graph, nil
}

func main() {
	decoder := json.NewDecoder(io.LimitReader(os.Stdin, 67108864))
	var graph Graph
	if err := decoder.Decode(&graph); err != nil {
		fmt.Fprintln(os.Stderr, "invalid graph JSON:", err)
		os.Exit(1)
	}
	var extra interface{}
	if err := decoder.Decode(&extra); err != io.EOF {
		fmt.Fprintln(os.Stderr, "expected exactly one JSON value")
		os.Exit(1)
	}
	result, err := Process_graph(graph, 1000000, 5000000, 65536, 65536, true, true, true, true)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := json.NewEncoder(os.Stdout).Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
