"""Tests for Conversation Branching — git for conversations."""

import json
import tempfile
from pathlib import Path

import pytest

from nexus.intelligence.branching import (
    Branch,
    BranchComparison,
    BranchMessage,
    ConversationTree,
)


@pytest.fixture
def workspace(tmp_path):
    return str(tmp_path)


@pytest.fixture
def tree(workspace):
    return ConversationTree(workspace=workspace)


class TestBranchMessage:
    """Test BranchMessage dataclass."""

    def test_create(self):
        msg = BranchMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.timestamp > 0

    def test_to_dict(self):
        msg = BranchMessage(role="assistant", content="hi", metadata={"model": "gpt"})
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "hi"
        assert d["metadata"]["model"] == "gpt"

    def test_from_dict(self):
        msg = BranchMessage.from_dict({
            "role": "user",
            "content": "test",
            "timestamp": 12345.0,
            "metadata": {"tag": "debug"},
        })
        assert msg.role == "user"
        assert msg.content == "test"
        assert msg.timestamp == 12345.0
        assert msg.metadata["tag"] == "debug"

    def test_from_dict_minimal(self):
        msg = BranchMessage.from_dict({"role": "system", "content": "init"})
        assert msg.role == "system"
        assert msg.timestamp == 0


class TestBranch:
    """Test Branch dataclass."""

    def test_create(self):
        branch = Branch(name="main", fork_point=0, parent_branch=None)
        assert branch.name == "main"
        assert branch.message_count == 0
        assert branch.user_turns == 0

    def test_message_count(self):
        branch = Branch(name="test", fork_point=0, parent_branch="main")
        branch.messages.append(BranchMessage(role="user", content="q1"))
        branch.messages.append(BranchMessage(role="assistant", content="a1"))
        branch.messages.append(BranchMessage(role="user", content="q2"))

        assert branch.message_count == 3
        assert branch.user_turns == 2

    def test_serialization(self):
        branch = Branch(name="feature", fork_point=3, parent_branch="main")
        branch.messages.append(BranchMessage(role="user", content="test"))

        d = branch.to_dict()
        restored = Branch.from_dict(d)

        assert restored.name == "feature"
        assert restored.fork_point == 3
        assert restored.parent_branch == "main"
        assert len(restored.messages) == 1


class TestConversationTree:
    """Test ConversationTree operations."""

    def test_initial_state(self, tree):
        assert tree.current_branch == "main"
        assert tree.branch_count == 1
        assert "main" in tree.branch_names

    def test_add_message(self, tree):
        msg = tree.add_message("user", "Hello Nexus")
        assert msg.role == "user"
        assert msg.content == "Hello Nexus"
        assert tree.current.message_count == 1

    def test_get_messages(self, tree):
        tree.add_message("user", "q1")
        tree.add_message("assistant", "a1")

        msgs = tree.get_messages()
        assert len(msgs) == 2
        assert msgs[0].content == "q1"
        assert msgs[1].content == "a1"

    def test_get_history_dicts(self, tree):
        tree.add_message("user", "hello")
        tree.add_message("assistant", "hi")

        dicts = tree.get_history_dicts()
        assert len(dicts) == 2
        assert dicts[0] == {"role": "user", "content": "hello"}


class TestBranchCreation:
    """Test creating and managing branches."""

    def test_create_branch(self, tree):
        tree.add_message("user", "base message")
        branch = tree.create_branch("feature-a")

        assert tree.current_branch == "feature-a"
        assert tree.branch_count == 2
        assert branch.parent_branch == "main"
        assert branch.fork_point == 1

    def test_create_without_switch(self, tree):
        tree.create_branch("bg-branch", switch=False)
        assert tree.current_branch == "main"

    def test_duplicate_name_raises(self, tree):
        tree.create_branch("test")
        with pytest.raises(ValueError, match="already exists"):
            tree.create_branch("test")

    def test_invalid_name_raises(self, tree):
        with pytest.raises(ValueError, match="Invalid"):
            tree.create_branch("")

    def test_branch_inherits_parent_messages(self, tree):
        tree.add_message("user", "shared msg 1")
        tree.add_message("assistant", "shared msg 2")
        tree.create_branch("child")
        tree.add_message("user", "child msg")

        msgs = tree.get_messages("child")
        assert len(msgs) == 3
        assert msgs[0].content == "shared msg 1"
        assert msgs[1].content == "shared msg 2"
        assert msgs[2].content == "child msg"

    def test_parent_not_affected_by_child(self, tree):
        tree.add_message("user", "base")
        tree.create_branch("child")
        tree.add_message("user", "child only")

        main_msgs = tree.get_messages("main")
        assert len(main_msgs) == 1
        assert main_msgs[0].content == "base"


class TestBranchSwitching:
    """Test switching between branches."""

    def test_switch_branch(self, tree):
        tree.create_branch("feature")
        tree.switch_branch("main")
        assert tree.current_branch == "main"

    def test_switch_nonexistent_raises(self, tree):
        with pytest.raises(ValueError, match="not found"):
            tree.switch_branch("nope")

    def test_switch_preserves_messages(self, tree):
        tree.add_message("user", "main msg")
        tree.create_branch("feature")
        tree.add_message("user", "feature msg")

        tree.switch_branch("main")
        assert tree.current.message_count == 1

        tree.switch_branch("feature")
        assert tree.current.message_count == 1  # own messages only


class TestBranchDeletion:
    """Test deleting branches."""

    def test_delete_branch(self, tree):
        tree.create_branch("temp", switch=False)
        assert tree.delete_branch("temp") is True
        assert tree.branch_count == 1

    def test_delete_nonexistent(self, tree):
        assert tree.delete_branch("nope") is False

    def test_cannot_delete_main(self, tree):
        with pytest.raises(ValueError, match="main"):
            tree.delete_branch("main")

    def test_cannot_delete_current(self, tree):
        tree.create_branch("active")
        with pytest.raises(ValueError, match="current"):
            tree.delete_branch("active")

    def test_cannot_delete_with_children(self, tree):
        tree.create_branch("parent")
        tree.create_branch("child")
        tree.switch_branch("main")

        with pytest.raises(ValueError, match="depend"):
            tree.delete_branch("parent")


class TestBranchComparison:
    """Test comparing branches."""

    def test_compare(self, tree):
        tree.add_message("user", "shared")
        tree.add_message("assistant", "response")

        tree.create_branch("approach-a")
        tree.add_message("user", "try approach A")

        tree.switch_branch("main")
        tree.create_branch("approach-b")
        tree.add_message("user", "try approach B")

        comp = tree.compare("approach-a", "approach-b")
        assert isinstance(comp, BranchComparison)
        assert comp.shared_messages >= 2
        assert comp.unique_a >= 1
        assert comp.unique_b >= 1

    def test_compare_nonexistent_raises(self, tree):
        with pytest.raises(ValueError):
            tree.compare("main", "nope")


class TestBranchMerge:
    """Test merging branches."""

    def test_merge_append(self, tree):
        tree.add_message("user", "shared")
        tree.create_branch("feature")
        tree.add_message("user", "feature work")
        tree.add_message("assistant", "feature response")

        tree.switch_branch("main")
        count = tree.merge("feature", strategy="append")

        assert count == 2
        msgs = tree.get_messages("main")
        assert any("feature work" in m.content for m in msgs)

    def test_merge_replace(self, tree):
        tree.add_message("user", "shared")
        tree.create_branch("better")
        tree.add_message("user", "better approach")

        tree.switch_branch("main")
        tree.add_message("user", "old approach")

        count = tree.merge("better", strategy="replace")
        assert count >= 1

    def test_merge_nonexistent_raises(self, tree):
        with pytest.raises(ValueError):
            tree.merge("nope")

    def test_merge_unknown_strategy_raises(self, tree):
        tree.create_branch("src", switch=False)
        with pytest.raises(ValueError, match="strategy"):
            tree.merge("src", strategy="weird")


class TestTreeDisplay:
    """Test tree visualization."""

    def test_display_single_branch(self, tree):
        display = tree.tree_display()
        assert "main" in display
        assert "active" in display

    def test_display_multiple_branches(self, tree):
        tree.add_message("user", "start")
        tree.create_branch("feature-a", switch=False)
        tree.create_branch("feature-b", switch=False)

        display = tree.tree_display()
        assert "main" in display
        assert "feature-a" in display
        assert "feature-b" in display

    def test_display_nested_branches(self, tree):
        tree.create_branch("level1")
        tree.create_branch("level2")

        display = tree.tree_display()
        assert "level1" in display
        assert "level2" in display


class TestListBranches:
    """Test branch listing."""

    def test_list_branches(self, tree):
        tree.create_branch("feature", switch=False)
        branches = tree.list_branches()

        assert len(branches) == 2
        names = [b["name"] for b in branches]
        assert "main" in names
        assert "feature" in names

    def test_active_marker(self, tree):
        branches = tree.list_branches()
        main = next(b for b in branches if b["name"] == "main")
        assert main["active"] is True


class TestPersistence:
    """Test saving and loading the conversation tree."""

    def test_save_and_load(self, workspace):
        # Create tree and add content
        tree1 = ConversationTree(workspace=workspace)
        tree1.add_message("user", "persistent message")
        tree1.create_branch("saved-branch")
        tree1.add_message("assistant", "branch response")
        tree1.save()

        # Load in a new tree
        tree2 = ConversationTree(workspace=workspace)
        assert tree2.load() is True

        assert tree2.current_branch == "saved-branch"
        assert tree2.branch_count == 2
        msgs = tree2.get_messages()
        assert any("persistent" in m.content for m in msgs)

    def test_load_nonexistent(self, workspace):
        tree = ConversationTree(workspace=workspace)
        assert tree.load() is False

    def test_save_creates_directory(self, workspace):
        tree = ConversationTree(workspace=workspace)
        tree.save()

        save_dir = Path(workspace) / ".nexus" / "branches"
        assert save_dir.exists()


class TestSummary:
    """Test tree summary."""

    def test_summary(self, tree):
        tree.add_message("user", "hi")
        tree.create_branch("test", switch=False)

        summary = tree.summary()
        assert summary["current_branch"] == "main"
        assert summary["total_branches"] == 2
        assert "tree" in summary
