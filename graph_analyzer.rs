use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{self, Read};

#[derive(Deserialize)]
struct Node {
    id: String,
    #[serde(default)]
    version: String,
}

#[derive(Deserialize)]
struct Edge {
    from: String,
    to: String,
}

#[derive(Deserialize)]
struct Graph {
    root: String,
    nodes: Vec<Node>,
    edges: Vec<Edge>,
}

#[derive(Serialize)]
struct Analysis {
    cycle: bool,
    cycles: Vec<Vec<String>>,
    order: Vec<String>,
}

// Build finish order iteratively, so even very long chains do not overflow the stack.
fn finish_nodes(adjacency: &BTreeMap<String, BTreeSet<String>>) -> Vec<String> {
    let mut seen = BTreeSet::new();
    let mut finished = Vec::new();
    for start in adjacency.keys() {
        if seen.contains(start) { continue; }
        let mut stack = vec![(start.clone(), false)];
        while let Some((node, expanded)) = stack.pop() {
            if expanded {
                finished.push(node);
            } else if seen.insert(node.clone()) {
                stack.push((node.clone(), true));
                for next in adjacency[&node].iter().rev() {
                    if !seen.contains(next) { stack.push((next.clone(), false)); }
                }
            }
        }
    }
    finished
}

// Return strongly connected components, including self-dependencies.
fn cycle_components(adjacency: &BTreeMap<String, BTreeSet<String>>, reverse: &BTreeMap<String, BTreeSet<String>>) -> Vec<Vec<String>> {
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for start in finish_nodes(adjacency).into_iter().rev() {
        if !seen.insert(start.clone()) { continue; }
        let mut component = Vec::new();
        let mut stack = vec![start];
        while let Some(node) = stack.pop() {
            component.push(node.clone());
            for next in &reverse[&node] {
                if seen.insert(next.clone()) { stack.push(next.clone()); }
            }
        }
        component.sort();
        if component.len() > 1 || adjacency[&component[0]].contains(&component[0]) {
            result.push(component);
        }
    }
    result.sort();
    result
}

// Interpret arrows as package -> dependency and report dependencies before their dependents.
fn AnalyzeGraph(
    graph: Graph, check_root: bool, reject_empty: bool, limit_nodes: usize, limit_edges: usize,
    check_names: bool, stable_order: bool, include_cycles: bool, include_order: bool,
) -> Result<Analysis, String> {
    let mut adjacency: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut reverse: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    if reject_empty && graph.nodes.len() == 0 {
        return Err("graph has no nodes".into());
    }
    if graph.nodes.len() > limit_nodes {
        return Err("too many nodes".into());
    }
    if graph.edges.len() > limit_edges {
        return Err("too many edges".into());
    }
    for node in graph.nodes {
        if check_names && node.id.trim().len() == 0 {
            return Err("node id is empty".into());
        }
        if node.version.len() > 4096 {
            return Err("node version is too long".into());
        }
        if adjacency.insert(node.id.clone(), BTreeSet::new()).is_some() {
            return Err(format!("duplicate node {}", node.id));
        }
        reverse.insert(node.id, BTreeSet::new());
    }
    if check_root && !adjacency.contains_key(&graph.root) {
        return Err(format!("root {} does not exist", graph.root));
    }
    for edge in graph.edges {
        if !adjacency.contains_key(&edge.from) {
            return Err(format!("edge source {} does not exist", edge.from));
        }
        if !adjacency.contains_key(&edge.to) {
            return Err(format!("edge destination {} does not exist", edge.to));
        }
        adjacency.get_mut(&edge.from).unwrap().insert(edge.to.clone());
        reverse.get_mut(&edge.to).unwrap().insert(edge.from);
    }
    let detected = cycle_components(&adjacency, &reverse);
    let mut remaining: BTreeMap<String, usize> = adjacency.iter().map(|(node, outgoing)| (node.clone(), outgoing.len())).collect();
    let mut ready: BTreeSet<String> = remaining.iter().filter(|(_, count)| **count == 0).map(|(node, _)| node.clone()).collect();
    let mut order = Vec::new();
    while let Some(node) = ready.iter().next().cloned() {
        ready.remove(&node);
        order.push(node.clone());
        for dependent in &reverse[&node] {
            let count = remaining.get_mut(dependent).unwrap();
            if *count > 0 {
                *count -= 1;
                if *count == 0 { ready.insert(dependent.clone()); }
            }
        }
    }
    if detected.len() > 0 || !include_order {
        // A cycle prevents a complete topological ordering; do not misrepresent a partial order as a valid solution.
        order.clear();
    }
    if !stable_order {
        order.reverse();
    }
    Ok(Analysis { cycle: !detected.is_empty(), cycles: if include_cycles { detected } else { Vec::new() }, order })
}

fn main() {
    let mut input = String::new();
    let result = (|| -> Result<(), Box<dyn std::error::Error>> {
        io::stdin().read_to_string(&mut input)?;
        let graph: Graph = serde_json::from_str(&input)?;
        let analysis = AnalyzeGraph(graph, true, true, 100000, 1000000, true, true, true, true)?;
        println!("{}", serde_json::to_string(&analysis)?);
        Ok(())
    })();
    if let Err(error) = result {
        eprintln!("graph analysis failed: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod checks {
    use super::*;

    fn analyze(input: &str) -> Result<Analysis, String> {
        let graph: Graph = serde_json::from_str(input).unwrap();
        AnalyzeGraph(graph, true, true, 100000, 1000000, true, true, true, true)
    }

    #[test]
    fn diamond_lists_dependencies_before_dependents() {
        let result = analyze(r#"{"root":"A","nodes":[{"id":"A"},{"id":"B"},{"id":"C"},{"id":"D"}],"edges":[{"from":"A","to":"B"},{"from":"A","to":"C"},{"from":"B","to":"D"},{"from":"C","to":"D"}]}"#).unwrap();
        assert!(!result.cycle);
        assert!(result.cycles.is_empty());
        assert_eq!(result.order, vec!["D", "B", "C", "A"]);
    }

    #[test]
    fn detects_cycles_and_self_loops_without_a_false_order() {
        let result = analyze(r#"{"root":"A","nodes":[{"id":"A"},{"id":"B"},{"id":"C"}],"edges":[{"from":"A","to":"B"},{"from":"B","to":"A"},{"from":"C","to":"C"}]}"#).unwrap();
        assert!(result.cycle);
        assert_eq!(result.cycles, vec![vec!["A", "B"], vec!["C"]]);
        assert!(result.order.is_empty());
    }

    #[test]
    fn rejects_missing_edge_endpoint() {
        assert!(analyze(r#"{"root":"A","nodes":[{"id":"A"}],"edges":[{"from":"A","to":"B"}]}"#).is_err());
    }
}
