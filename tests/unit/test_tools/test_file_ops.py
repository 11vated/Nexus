"""Tests for nexus.tools.file_ops — file read/write/list tools."""
import os
import pytest
import tempfile
from nexus.tools.file_ops import FileReadTool, FileWriteTool, FileListTool


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with some files."""
    (tmp_path / "hello.py").write_text("print('hello')")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").write_text("nested content")
    return str(tmp_path)


class TestFileReadTool:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, workspace):
        tool = FileReadTool(workspace=workspace)
        result = await tool.execute(path="hello.py")
        assert "print('hello')" in result

    @pytest.mark.asyncio
    async def test_read_nested_file(self, workspace):
        tool = FileReadTool(workspace=workspace)
        result = await tool.execute(path="subdir/nested.txt")
        assert "nested content" in result

    @pytest.mark.asyncio
    async def test_read_missing_file(self, workspace):
        tool = FileReadTool(workspace=workspace)
        result = await tool.execute(path="nonexistent.py")
        assert "error" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, workspace):
        tool = FileReadTool(workspace=workspace)
        result = await tool.execute(path="../../../etc/passwd")
        assert "error" in result.lower() or "denied" in result.lower() or "outside" in result.lower()


class TestFileWriteTool:
    @pytest.mark.asyncio
    async def test_write_new_file(self, workspace):
        tool = FileWriteTool(workspace=workspace)
        result = await tool.execute(path="new.py", content="x = 1")
        assert os.path.exists(os.path.join(workspace, "new.py"))
        assert open(os.path.join(workspace, "new.py")).read() == "x = 1"

    @pytest.mark.asyncio
    async def test_write_creates_directories(self, workspace):
        tool = FileWriteTool(workspace=workspace)
        result = await tool.execute(path="deep/nested/dir/file.txt", content="hello")
        assert os.path.exists(os.path.join(workspace, "deep/nested/dir/file.txt"))

    @pytest.mark.asyncio
    async def test_write_overwrites(self, workspace):
        tool = FileWriteTool(workspace=workspace)
        await tool.execute(path="hello.py", content="new content")
        assert open(os.path.join(workspace, "hello.py")).read() == "new content"


class TestFileListTool:
    @pytest.mark.asyncio
    async def test_list_root(self, workspace):
        tool = FileListTool(workspace=workspace)
        result = await tool.execute(path=".")
        assert "hello.py" in result
        assert "subdir" in result

    @pytest.mark.asyncio
    async def test_list_subdir(self, workspace):
        tool = FileListTool(workspace=workspace)
        result = await tool.execute(path="subdir")
        assert "nested.txt" in result
