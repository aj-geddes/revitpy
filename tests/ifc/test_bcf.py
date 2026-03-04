"""
Tests for the BCF manager.
"""

import json

import pytest

from revitpy.ifc.bcf import BcfManager
from revitpy.ifc.exceptions import BcfError
from revitpy.ifc.types import BcfIssue


class TestBcfManager:
    """Tests for BcfManager."""

    def test_create_issue(self):
        """create_issue should return a BcfIssue with all fields set."""
        manager = BcfManager()
        issue = manager.create_issue(
            title="Test Issue",
            description="A test issue",
            author="Tester",
            status="Open",
            assigned_to="Dev",
            element_ids=["1", "2"],
        )

        assert isinstance(issue, BcfIssue)
        assert issue.title == "Test Issue"
        assert issue.description == "A test issue"
        assert issue.author == "Tester"
        assert issue.status == "Open"
        assert issue.assigned_to == "Dev"
        assert issue.element_ids == ["1", "2"]
        assert issue.guid  # guid should be non-empty

    def test_create_issue_defaults(self):
        """create_issue should set sensible defaults."""
        manager = BcfManager()
        issue = manager.create_issue(title="Minimal Issue")

        assert issue.title == "Minimal Issue"
        assert issue.status == "Open"
        assert issue.description == ""
        assert issue.author == ""
        assert issue.element_ids == []

    def test_issues_property(self):
        """The issues property should list all created issues."""
        manager = BcfManager()
        manager.create_issue(title="Issue 1")
        manager.create_issue(title="Issue 2")

        assert len(manager.issues) == 2
        titles = {i.title for i in manager.issues}
        assert titles == {"Issue 1", "Issue 2"}

    def test_issues_property_returns_copy(self):
        """The issues property should return a copy."""
        manager = BcfManager()
        manager.create_issue(title="Issue 1")

        issues = manager.issues
        issues.clear()

        assert len(manager.issues) == 1

    def test_write_bcf_zip(self, tmp_path, sample_bcf_issues):
        """write_bcf should create a valid BCF ZIP file."""
        manager = BcfManager()
        output = tmp_path / "test.bcf"

        result = manager.write_bcf(sample_bcf_issues, output)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    def test_write_bcf_no_issues_raises(self, tmp_path):
        """write_bcf with no issues should raise BcfError."""
        manager = BcfManager()

        with pytest.raises(BcfError, match="No BCF issues"):
            manager.write_bcf([], tmp_path / "empty.bcf")

    def test_write_bcf_uses_managed_issues(self, tmp_path):
        """write_bcf without explicit issues should use managed issues."""
        manager = BcfManager()
        manager.create_issue(title="Managed Issue")

        result = manager.write_bcf(path=tmp_path / "managed.bcf")

        assert result.exists()

    def test_read_write_round_trip(self, tmp_path, sample_bcf_issues):
        """Issues written to BCF should be readable back."""
        manager = BcfManager()
        bcf_path = tmp_path / "roundtrip.bcf"

        manager.write_bcf(sample_bcf_issues, bcf_path)

        reader = BcfManager()
        loaded = reader.read_bcf(bcf_path)

        assert len(loaded) == len(sample_bcf_issues)
        loaded_titles = {i.title for i in loaded}
        original_titles = {i.title for i in sample_bcf_issues}
        assert loaded_titles == original_titles

    def test_read_bcf_preserves_fields(self, tmp_path, sample_bcf_issues):
        """read_bcf should preserve author, status, and element_ids."""
        manager = BcfManager()
        bcf_path = tmp_path / "fields.bcf"

        manager.write_bcf(sample_bcf_issues, bcf_path)

        reader = BcfManager()
        loaded = reader.read_bcf(bcf_path)

        issue_map = {i.title: i for i in loaded}

        original = sample_bcf_issues[0]
        loaded_issue = issue_map[original.title]
        assert loaded_issue.author == original.author
        assert loaded_issue.status == original.status
        assert loaded_issue.element_ids == original.element_ids

    def test_read_bcf_file_not_found(self, tmp_path):
        """read_bcf should raise BcfError for missing files."""
        manager = BcfManager()

        with pytest.raises(BcfError, match="not found"):
            manager.read_bcf(tmp_path / "missing.bcf")

    def test_read_bcf_unsupported_format(self, tmp_path):
        """read_bcf should raise BcfError for unsupported extensions."""
        manager = BcfManager()
        bad_file = tmp_path / "issues.txt"
        bad_file.write_text("not bcf data")

        with pytest.raises(BcfError, match="Unsupported"):
            manager.read_bcf(bad_file)

    def test_read_json_format(self, tmp_path):
        """read_bcf should support JSON format."""
        manager = BcfManager()

        issues_json = [
            {
                "guid": "json-001",
                "title": "JSON Issue",
                "description": "From JSON",
                "author": "JsonBot",
                "status": "Open",
                "element_ids": ["42"],
            }
        ]

        json_path = tmp_path / "issues.json"
        json_path.write_text(json.dumps(issues_json))

        loaded = manager.read_bcf(json_path)

        assert len(loaded) == 1
        assert loaded[0].title == "JSON Issue"
        assert loaded[0].guid == "json-001"
        assert loaded[0].element_ids == ["42"]

    def test_read_json_adds_to_managed(self, tmp_path):
        """read_bcf should add loaded issues to internal list."""
        manager = BcfManager()
        manager.create_issue(title="Existing")

        json_path = tmp_path / "more.json"
        json_path.write_text(json.dumps([{"title": "Loaded"}]))

        manager.read_bcf(json_path)

        assert len(manager.issues) == 2

    def test_multiple_issues_unique_guids(self):
        """Each created issue should have a unique GUID."""
        manager = BcfManager()
        issues = [manager.create_issue(title=f"Issue {i}") for i in range(10)]
        guids = {issue.guid for issue in issues}
        assert len(guids) == 10

    def test_create_issue_with_element_ids(self):
        """create_issue should store element_ids."""
        manager = BcfManager()
        issue = manager.create_issue(
            title="Linked Issue",
            element_ids=["elem-1", "elem-2", "elem-3"],
        )
        assert len(issue.element_ids) == 3
