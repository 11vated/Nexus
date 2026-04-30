"""Tests for nexus.tools.registry — BaseTool and ToolRegistry."""
import pytest
from nexus.tools.registry import BaseTool, ToolRegistry


class DummyTool(BaseTool):
    name = "dummy"
    description = "A test tool"
    aliases = ["d", "test_tool"]
    schema = {"input": "The input value"}

    async def execute(self, **kwargs):
        return f"executed with {kwargs}"


class AnotherTool(BaseTool):
    name = "another"
    description = "Another test tool"

    async def execute(self, **kwargs):
        return "another result"


class TestBaseTool:
    def test_prompt_description(self):
        tool = DummyTool()
        desc = tool.to_prompt_description()
        assert "dummy" in desc
        assert "A test tool" in desc
        assert "input" in desc

    def test_default_workspace(self):
        tool = DummyTool()
        assert tool.workspace == "."

    def test_custom_workspace(self):
        tool = DummyTool(workspace="/tmp/test")
        assert tool.workspace == "/tmp/test"


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = DummyTool()
        reg.register(tool)
        assert reg.get("dummy") is tool

    def test_get_by_alias(self):
        reg = ToolRegistry()
        tool = DummyTool()
        reg.register(tool)
        assert reg.get("d") is tool
        assert reg.get("test_tool") is tool

    def test_get_missing(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_list_tools_no_duplicates(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        names = reg.list_tools()
        assert names == ["dummy"]

    def test_multiple_tools(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        names = reg.list_tools()
        assert set(names) == {"dummy", "another"}

    def test_as_dict(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        d = reg.as_dict()
        assert len(d) == 2
        assert "dummy" in d
        assert "another" in d

    def test_get_prompt_descriptions(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        reg.register(AnotherTool())
        desc = reg.get_prompt_descriptions()
        assert "dummy" in desc
        assert "another" in desc

    def test_register_class(self):
        reg = ToolRegistry()
        reg.register_class(DummyTool, workspace="/test")
        tool = reg.get("dummy")
        assert tool is not None
        assert tool.workspace == "/test"
