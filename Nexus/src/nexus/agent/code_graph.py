"""CodeGraph — structural intelligence via AST analysis.

Builds a dependency graph of the codebase: call graphs, inheritance,
import relationships, and test coverage mapping.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class NodeType(Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    TEST = "test"
    IMPORT = "import"


class EdgeType(Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    CONTAINS = "contains"
    TESTS = "tests"
    MUTATES = "mutates"
    REFERENCES = "references"


@dataclass
class GraphNode:
    """A node in the code graph."""
    id: str
    node_type: NodeType
    name: str
    file_path: str = ""
    line_number: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "name": self.name,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphNode":
        return cls(
            id=data["id"],
            node_type=NodeType(data["node_type"]),
            name=data["name"],
            file_path=data.get("file_path", ""),
            line_number=data.get("line_number", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class GraphEdge:
    """An edge in the code graph."""
    source: str
    target: str
    edge_type: EdgeType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphEdge":
        return cls(
            source=data["source"],
            target=data["target"],
            edge_type=EdgeType(data["edge_type"]),
            metadata=data.get("metadata", {}),
        )


class CodeGraph:
    """Dependency graph built via AST analysis.

    Supports queries for callers, affected functions, inheritance chains,
    and test coverage.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._adjacency: Dict[str, Set[str]] = {}
        self._reverse_adjacency: Dict[str, Set[str]] = {}

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = set()
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = set()

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)
        if edge.source not in self._adjacency:
            self._adjacency[edge.source] = set()
        if edge.target not in self._reverse_adjacency:
            self._reverse_adjacency[edge.target] = set()
        self._adjacency[edge.source].add(edge.target)
        self._reverse_adjacency[edge.target].add(edge.source)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def get_nodes_by_file(self, file_path: str) -> List[GraphNode]:
        return [n for n in self.nodes.values() if n.file_path == file_path]

    def get_edges_by_type(self, edge_type: EdgeType) -> List[GraphEdge]:
        return [e for e in self.edges if e.edge_type == edge_type]

    def callers_of(self, function_id: str) -> List[str]:
        """Find all functions that call this function."""
        return list(self._reverse_adjacency.get(function_id, set()))

    def calls_of(self, function_id: str) -> List[str]:
        """Find all functions this function calls."""
        return list(self._adjacency.get(function_id, set()))

    def affected_by(self, node_id: str) -> List[str]:
        """Transitive closure: all nodes affected by changes to this node."""
        visited: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self._reverse_adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        visited.discard(node_id)
        return list(visited)

    def depends_on(self, node_id: str) -> List[str]:
        """Transitive closure: all nodes this node depends on."""
        visited: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self._adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        visited.discard(node_id)
        return list(visited)

    def test_coverage(self, function_id: str) -> List[str]:
        """Find all tests that exercise this function."""
        tests = []
        for edge in self.edges:
            if edge.target == function_id and edge.edge_type == EdgeType.TESTS:
                tests.append(edge.source)
        return tests

    def inheritance_chain(self, class_id: str) -> List[str]:
        """Get the inheritance chain for a class."""
        chain = []
        current = class_id
        visited: Set[str] = set()
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            parent = self._find_parent_class(current)
            current = parent
        return chain

    def subclasses_of(self, class_id: str) -> List[str]:
        """Find all classes that inherit from this class."""
        subclasses = []
        for edge in self.edges:
            if edge.target == class_id and edge.edge_type == EdgeType.INHERITS:
                subclasses.append(edge.source)
        return subclasses

    def find_by_name(self, name: str) -> List[GraphNode]:
        """Find nodes by name (case-insensitive partial match)."""
        lower = name.lower()
        return [n for n in self.nodes.values() if lower in n.name.lower()]

    def get_file_dependencies(self, file_path: str) -> List[str]:
        """Get all files that this file imports."""
        file_nodes = self.get_nodes_by_file(file_path)
        deps: Set[str] = set()
        for node in file_nodes:
            for edge in self.edges:
                if edge.source == node.id and edge.edge_type == EdgeType.IMPORTS:
                    target_node = self.nodes.get(edge.target)
                    if target_node:
                        deps.add(target_node.file_path)
        return list(deps)

    def file_depended_by(self, file_path: str) -> List[str]:
        """Get all files that import this file."""
        file_nodes = self.get_nodes_by_file(file_path)
        file_ids = {n.id for n in file_nodes}
        deps: Set[str] = set()
        for edge in self.edges:
            if edge.target in file_ids and edge.edge_type == EdgeType.IMPORTS:
                source_node = self.nodes.get(edge.source)
                if source_node:
                    deps.add(source_node.file_path)
        return list(deps)

    def stats(self) -> Dict[str, Any]:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "files": len(self.get_nodes_by_type(NodeType.FILE)),
            "classes": len(self.get_nodes_by_type(NodeType.CLASS)),
            "functions": len(self.get_nodes_by_type(NodeType.FUNCTION)),
            "tests": len(self.get_nodes_by_type(NodeType.TEST)),
            "call_edges": len(self.get_edges_by_type(EdgeType.CALLS)),
            "import_edges": len(self.get_edges_by_type(EdgeType.IMPORTS)),
            "inheritance_edges": len(self.get_edges_by_type(EdgeType.INHERITS)),
            "test_edges": len(self.get_edges_by_type(EdgeType.TESTS)),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeGraph":
        graph = cls()
        for nid, ndata in data.get("nodes", {}).items():
            graph.add_node(GraphNode.from_dict(ndata))
        for edata in data.get("edges", []):
            graph.add_edge(GraphEdge.from_dict(edata))
        return graph

    def _find_parent_class(self, class_id: str) -> Optional[str]:
        """Find the parent class via inheritance edge."""
        for edge in self.edges:
            if edge.source == class_id and edge.edge_type == EdgeType.INHERITS:
                return edge.target
        return None


class PythonASTAnalyzer:
    """Builds a CodeGraph from Python source files using AST analysis."""

    def __init__(self) -> None:
        self.graph = CodeGraph()

    def analyze_file(self, file_path: str) -> CodeGraph:
        """Analyze a single Python file and add to graph."""
        path = Path(file_path)
        if not path.exists():
            return self.graph

        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            logger.warning(f"Syntax error in {file_path}, skipping")
            return self.graph

        self._add_file_node(file_path)
        self._process_imports(tree, file_path)
        self._process_classes(tree, file_path, source)
        self._process_functions(tree, file_path, source)

        return self.graph

    def analyze_directory(self, dir_path: str, pattern: str = "*.py") -> CodeGraph:
        """Analyze all Python files in a directory."""
        path = Path(dir_path)
        for py_file in sorted(path.rglob(pattern)):
            self.analyze_file(str(py_file))
        self._link_tests_to_functions()
        return self.graph

    def get_graph(self) -> CodeGraph:
        return self.graph

    def _node_id(self, file_path: str, name: str, node_type: NodeType) -> str:
        return f"{node_type.value}:{file_path}:{name}"

    def _add_file_node(self, file_path: str) -> None:
        node_id = f"file:{file_path}"
        if node_id not in self.graph.nodes:
            self.graph.add_node(GraphNode(
                id=node_id,
                node_type=NodeType.FILE,
                name=Path(file_path).name,
                file_path=file_path,
            ))

    def _process_imports(self, tree: ast.Module, file_path: str) -> None:
        file_node_id = f"file:{file_path}"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target_id = f"import:{alias.name}"
                    if target_id not in self.graph.nodes:
                        self.graph.add_node(GraphNode(
                            id=target_id,
                            node_type=NodeType.IMPORT,
                            name=alias.name,
                            file_path=file_path,
                        ))
                    self.graph.add_edge(GraphEdge(
                        source=file_node_id,
                        target=target_id,
                        edge_type=EdgeType.IMPORTS,
                    ))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    target_id = f"import:{node.module}"
                    if target_id not in self.graph.nodes:
                        self.graph.add_node(GraphNode(
                            id=target_id,
                            node_type=NodeType.IMPORT,
                            name=node.module,
                            file_path=file_path,
                        ))
                    self.graph.add_edge(GraphEdge(
                        source=file_node_id,
                        target=target_id,
                        edge_type=EdgeType.IMPORTS,
                    ))

    def _process_classes(self, tree: ast.Module, file_path: str, source: str) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_id = self._node_id(file_path, node.name, NodeType.CLASS)
                self.graph.add_node(GraphNode(
                    id=class_id,
                    node_type=NodeType.CLASS,
                    name=node.name,
                    file_path=file_path,
                    line_number=node.lineno,
                    metadata={
                        "methods": [
                            n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        ]
                    },
                ))

                for base in node.bases:
                    if isinstance(base, ast.Name):
                        parent_id = self._node_id(file_path, base.id, NodeType.CLASS)
                        self.graph.add_edge(GraphEdge(
                            source=class_id,
                            target=parent_id,
                            edge_type=EdgeType.INHERITS,
                        ))

                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = self._node_id(file_path, f"{node.name}.{method.name}", NodeType.METHOD)
                        self.graph.add_node(GraphNode(
                            id=method_id,
                            node_type=NodeType.METHOD,
                            name=method.name,
                            file_path=file_path,
                            line_number=method.lineno,
                        ))
                        self.graph.add_edge(GraphEdge(
                            source=class_id,
                            target=method_id,
                            edge_type=EdgeType.CONTAINS,
                        ))
                        self._extract_calls(method, method_id, file_path)

    def _process_functions(self, tree: ast.Module, file_path: str, source: str) -> None:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = self._node_id(file_path, node.name, NodeType.FUNCTION)
                is_test = node.name.startswith("test_") or node.name.startswith("Test")
                node_type = NodeType.TEST if is_test else NodeType.FUNCTION

                self.graph.add_node(GraphNode(
                    id=func_id,
                    node_type=node_type,
                    name=node.name,
                    file_path=file_path,
                    line_number=node.lineno,
                ))
                self._extract_calls(node, func_id, file_path)

    def _extract_calls(self, func_node: ast.FunctionDef, func_id: str, file_path: str) -> None:
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    target_id = self._node_id(file_path, node.func.id, NodeType.FUNCTION)
                    self.graph.add_edge(GraphEdge(
                        source=func_id,
                        target=target_id,
                        edge_type=EdgeType.CALLS,
                    ))
                elif isinstance(node.func, ast.Attribute):
                    target_name = node.func.attr
                    target_id = self._node_id(file_path, target_name, NodeType.FUNCTION)
                    self.graph.add_edge(GraphEdge(
                        source=func_id,
                        target=target_id,
                        edge_type=EdgeType.CALLS,
                    ))

    def _link_tests_to_functions(self) -> None:
        """Heuristically link test functions to the functions they test."""
        tests = self.graph.get_nodes_by_type(NodeType.TEST)
        functions = self.graph.get_nodes_by_type(NodeType.FUNCTION)

        func_names = {f.name: f.id for f in functions}

        for test in tests:
            for func_name, func_id in func_names.items():
                if func_name in test.name or test.name.replace("test_", "") == func_name:
                    self.graph.add_edge(GraphEdge(
                        source=test.id,
                        target=func_id,
                        edge_type=EdgeType.TESTS,
                    ))


def build_graph_from_files(file_paths: List[str]) -> CodeGraph:
    """Convenience function to build a graph from a list of files."""
    analyzer = PythonASTAnalyzer()
    for path in file_paths:
        analyzer.analyze_file(path)
    analyzer._link_tests_to_functions()
    return analyzer.graph
