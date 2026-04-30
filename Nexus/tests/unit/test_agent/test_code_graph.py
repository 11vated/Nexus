"""Tests for CodeGraph module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nexus.agent.code_graph import (
    CodeGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    PythonASTAnalyzer,
    build_graph_from_files,
)


@pytest.fixture
def graph():
    return CodeGraph()


@pytest.fixture
def sample_nodes():
    return [
        GraphNode(id="file:a.py", node_type=NodeType.FILE, name="a.py", file_path="a.py"),
        GraphNode(id="file:b.py", node_type=NodeType.FILE, name="b.py", file_path="b.py"),
        GraphNode(id="function:a.py:foo", node_type=NodeType.FUNCTION, name="foo", file_path="a.py", line_number=1),
        GraphNode(id="function:a.py:bar", node_type=NodeType.FUNCTION, name="bar", file_path="a.py", line_number=10),
        GraphNode(id="function:b.py:baz", node_type=NodeType.FUNCTION, name="baz", file_path="b.py", line_number=1),
        GraphNode(id="class:a.py:MyClass", node_type=NodeType.CLASS, name="MyClass", file_path="a.py", line_number=5),
        GraphNode(id="test:a.py:test_foo", node_type=NodeType.TEST, name="test_foo", file_path="a.py", line_number=20),
    ]


@pytest.fixture
def sample_edges():
    return [
        GraphEdge(source="function:a.py:foo", target="function:a.py:bar", edge_type=EdgeType.CALLS),
        GraphEdge(source="function:a.py:bar", target="function:b.py:baz", edge_type=EdgeType.CALLS),
        GraphEdge(source="file:a.py", target="file:b.py", edge_type=EdgeType.IMPORTS),
        GraphEdge(source="class:a.py:MyClass", target="function:a.py:foo", edge_type=EdgeType.CONTAINS),
        GraphEdge(source="test:a.py:test_foo", target="function:a.py:foo", edge_type=EdgeType.TESTS),
    ]


class TestNodeType:
    def test_enum_values(self):
        assert NodeType.FILE.value == "file"
        assert NodeType.CLASS.value == "class"
        assert NodeType.FUNCTION.value == "function"
        assert NodeType.METHOD.value == "method"
        assert NodeType.VARIABLE.value == "variable"
        assert NodeType.TEST.value == "test"
        assert NodeType.IMPORT.value == "import"


class TestEdgeType:
    def test_enum_values(self):
        assert EdgeType.IMPORTS.value == "imports"
        assert EdgeType.CALLS.value == "calls"
        assert EdgeType.INHERITS.value == "inherits"
        assert EdgeType.CONTAINS.value == "contains"
        assert EdgeType.TESTS.value == "tests"
        assert EdgeType.MUTATES.value == "mutates"
        assert EdgeType.REFERENCES.value == "references"


class TestGraphNode:
    def test_to_dict(self):
        node = GraphNode(id="1", node_type=NodeType.FUNCTION, name="foo", file_path="a.py", line_number=5)
        d = node.to_dict()
        assert d["id"] == "1"
        assert d["node_type"] == "function"
        assert d["name"] == "foo"

    def test_from_dict_roundtrip(self):
        node = GraphNode(
            id="2",
            node_type=NodeType.CLASS,
            name="MyClass",
            file_path="b.py",
            line_number=10,
            metadata={"methods": ["__init__"]},
        )
        d = node.to_dict()
        restored = GraphNode.from_dict(d)
        assert restored.id == node.id
        assert restored.node_type == node.node_type
        assert restored.metadata == node.metadata


class TestGraphEdge:
    def test_to_dict(self):
        edge = GraphEdge(source="a", target="b", edge_type=EdgeType.CALLS)
        d = edge.to_dict()
        assert d["source"] == "a"
        assert d["edge_type"] == "calls"

    def test_from_dict_roundtrip(self):
        edge = GraphEdge(
            source="x",
            target="y",
            edge_type=EdgeType.INHERITS,
            metadata={"line": 5},
        )
        d = edge.to_dict()
        restored = GraphEdge.from_dict(d)
        assert restored.source == edge.source
        assert restored.edge_type == edge.edge_type
        assert restored.metadata == edge.metadata


class TestCodeGraphBasic:
    def test_add_node(self, graph):
        node = GraphNode(id="1", node_type=NodeType.FUNCTION, name="foo")
        graph.add_node(node)
        assert graph.get_node("1") is node

    def test_add_edge(self, graph):
        graph.add_node(GraphNode(id="a", node_type=NodeType.FUNCTION, name="a"))
        graph.add_node(GraphNode(id="b", node_type=NodeType.FUNCTION, name="b"))
        edge = GraphEdge(source="a", target="b", edge_type=EdgeType.CALLS)
        graph.add_edge(edge)
        assert len(graph.edges) == 1

    def test_get_nodes_by_type(self, graph, sample_nodes):
        for node in sample_nodes:
            graph.add_node(node)
        functions = graph.get_nodes_by_type(NodeType.FUNCTION)
        assert len(functions) == 3

    def test_get_nodes_by_file(self, graph, sample_nodes):
        for node in sample_nodes:
            graph.add_node(node)
        a_nodes = graph.get_nodes_by_file("a.py")
        assert len(a_nodes) == 5

    def test_get_edges_by_type(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)
        call_edges = graph.get_edges_by_type(EdgeType.CALLS)
        assert len(call_edges) == 2


class TestCodeGraphQueries:
    def test_callers_of(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        callers = graph.callers_of("function:a.py:bar")
        assert "function:a.py:foo" in callers

    def test_calls_of(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        calls = graph.calls_of("function:a.py:foo")
        assert "function:a.py:bar" in calls

    def test_affected_by(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        affected = graph.affected_by("function:b.py:baz")
        assert "function:a.py:foo" in affected
        assert "function:a.py:bar" in affected

    def test_affected_by_no_dependents(self, graph):
        graph.add_node(GraphNode(id="x", node_type=NodeType.FUNCTION, name="x"))
        affected = graph.affected_by("x")
        assert affected == []

    def test_depends_on(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        deps = graph.depends_on("function:a.py:foo")
        assert "function:a.py:bar" in deps
        assert "function:b.py:baz" in deps

    def test_test_coverage(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        tests = graph.test_coverage("function:a.py:foo")
        assert "test:a.py:test_foo" in tests

    def test_test_coverage_no_tests(self, graph):
        graph.add_node(GraphNode(id="f", node_type=NodeType.FUNCTION, name="f"))
        tests = graph.test_coverage("f")
        assert tests == []

    def test_find_by_name(self, graph, sample_nodes):
        for node in sample_nodes:
            graph.add_node(node)

        results = graph.find_by_name("foo")
        assert len(results) >= 1
        assert any("foo" in n.name.lower() for n in results)

    def test_find_by_name_case_insensitive(self, graph):
        graph.add_node(GraphNode(id="1", node_type=NodeType.FUNCTION, name="MyFunction"))
        results = graph.find_by_name("myfunction")
        assert len(results) == 1


class TestCodeGraphInheritance:
    def test_inheritance_chain(self, graph):
        graph.add_node(GraphNode(id="A", node_type=NodeType.CLASS, name="A"))
        graph.add_node(GraphNode(id="B", node_type=NodeType.CLASS, name="B"))
        graph.add_node(GraphNode(id="C", node_type=NodeType.CLASS, name="C"))
        graph.add_edge(GraphEdge(source="C", target="B", edge_type=EdgeType.INHERITS))
        graph.add_edge(GraphEdge(source="B", target="A", edge_type=EdgeType.INHERITS))

        chain = graph.inheritance_chain("C")
        assert chain == ["C", "B", "A"]

    def test_inheritance_chain_no_parent(self, graph):
        graph.add_node(GraphNode(id="A", node_type=NodeType.CLASS, name="A"))
        chain = graph.inheritance_chain("A")
        assert chain == ["A"]

    def test_subclasses_of(self, graph):
        graph.add_node(GraphNode(id="Base", node_type=NodeType.CLASS, name="Base"))
        graph.add_node(GraphNode(id="Child1", node_type=NodeType.CLASS, name="Child1"))
        graph.add_node(GraphNode(id="Child2", node_type=NodeType.CLASS, name="Child2"))
        graph.add_edge(GraphEdge(source="Child1", target="Base", edge_type=EdgeType.INHERITS))
        graph.add_edge(GraphEdge(source="Child2", target="Base", edge_type=EdgeType.INHERITS))

        subclasses = graph.subclasses_of("Base")
        assert len(subclasses) == 2
        assert "Child1" in subclasses
        assert "Child2" in subclasses


class TestCodeGraphFileDependencies:
    def test_get_file_dependencies(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        deps = graph.get_file_dependencies("a.py")
        assert "b.py" in deps

    def test_file_depended_by(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        dependents = graph.file_depended_by("b.py")
        assert "a.py" in dependents


class TestCodeGraphStats:
    def test_stats(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        stats = graph.stats()
        assert stats["nodes"] == 7
        assert stats["edges"] == 5
        assert stats["files"] == 2
        assert stats["classes"] == 1
        assert stats["functions"] == 3
        assert stats["tests"] == 1


class TestCodeGraphSerialization:
    def test_to_dict(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        data = graph.to_dict()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 7

    def test_from_dict_roundtrip(self, graph, sample_nodes, sample_edges):
        for node in sample_nodes:
            graph.add_node(node)
        for edge in sample_edges:
            graph.add_edge(edge)

        data = graph.to_dict()
        restored = CodeGraph.from_dict(data)

        assert len(restored.nodes) == 7
        assert len(restored.edges) == 5

    def test_from_dict_empty(self):
        restored = CodeGraph.from_dict({})
        assert len(restored.nodes) == 0
        assert len(restored.edges) == 0


class TestPythonASTAnalyzer:
    def test_analyze_simple_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "simple.py"
            file_path.write_text(
                "def foo():\n"
                "    return bar()\n"
                "\n"
                "def bar():\n"
                "    return 42\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_file(str(file_path))
            graph = analyzer.get_graph()

            assert len(graph.get_nodes_by_type(NodeType.FUNCTION)) == 2
            assert len(graph.get_edges_by_type(EdgeType.CALLS)) >= 1

    def test_analyze_class_with_inheritance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "classes.py"
            file_path.write_text(
                "class Animal:\n"
                "    def speak(self):\n"
                "        pass\n"
                "\n"
                "class Dog(Animal):\n"
                "    def speak(self):\n"
                "        return 'woof'\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_file(str(file_path))
            graph = analyzer.get_graph()

            classes = graph.get_nodes_by_type(NodeType.CLASS)
            assert len(classes) == 2
            assert len(graph.get_edges_by_type(EdgeType.INHERITS)) == 1

    def test_analyze_imports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "imports.py"
            file_path.write_text(
                "import os\n"
                "from pathlib import Path\n"
                "\n"
                "def use_imports():\n"
                "    os.getcwd()\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_file(str(file_path))
            graph = analyzer.get_graph()

            import_edges = graph.get_edges_by_type(EdgeType.IMPORTS)
            assert len(import_edges) >= 2

    def test_analyze_test_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_module.py"
            file_path.write_text(
                "def compute(x):\n"
                "    return x * 2\n"
                "\n"
                "def test_compute():\n"
                "    assert compute(2) == 4\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_file(str(file_path))
            graph = analyzer.get_graph()

            tests = graph.get_nodes_by_type(NodeType.TEST)
            assert len(tests) == 1
            assert tests[0].name == "test_compute"

    def test_analyze_nonexistent_file(self):
        analyzer = PythonASTAnalyzer()
        graph = analyzer.analyze_file("/nonexistent/file.py")
        assert len(graph.nodes) == 0

    def test_analyze_syntax_error_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "broken.py"
            file_path.write_text("def foo(\n")

            analyzer = PythonASTAnalyzer()
            graph = analyzer.analyze_file(str(file_path))
            assert len(graph.nodes) == 0

    def test_analyze_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.py").write_text(
                "def foo():\n"
                "    return bar()\n"
                "\n"
                "def bar():\n"
                "    return 1\n"
            )
            (Path(tmpdir) / "test_a.py").write_text(
                "def test_foo():\n"
                "    assert foo() == 1\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_directory(tmpdir)
            graph = analyzer.get_graph()

            assert len(graph.get_nodes_by_type(NodeType.FUNCTION)) >= 2
            assert len(graph.get_nodes_by_type(NodeType.TEST)) >= 1

    def test_async_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "async.py"
            file_path.write_text(
                "async def fetch_data():\n"
                "    return await process()\n"
                "\n"
                "async def process():\n"
                "    return 42\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_file(str(file_path))
            graph = analyzer.get_graph()

            functions = graph.get_nodes_by_type(NodeType.FUNCTION)
            assert len(functions) == 2

    def test_class_methods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "methods.py"
            file_path.write_text(
                "class Service:\n"
                "    def __init__(self):\n"
                "        self.data = []\n"
                "\n"
                "    def process(self):\n"
                "        return self.transform()\n"
                "\n"
                "    def transform(self):\n"
                "        return [x * 2 for x in self.data]\n"
            )

            analyzer = PythonASTAnalyzer()
            analyzer.analyze_file(str(file_path))
            graph = analyzer.get_graph()

            methods = graph.get_nodes_by_type(NodeType.METHOD)
            assert len(methods) == 3


class TestBuildGraphFromFiles:
    def test_build_from_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = Path(tmpdir) / "a.py"
            file_a.write_text(
                "def foo():\n"
                "    return bar()\n"
                "\n"
                "def bar():\n"
                "    return 1\n"
            )

            graph = build_graph_from_files([str(file_a)])
            assert len(graph.get_nodes_by_type(NodeType.FUNCTION)) == 2

    def test_build_from_empty_list(self):
        graph = build_graph_from_files([])
        assert len(graph.nodes) == 0
