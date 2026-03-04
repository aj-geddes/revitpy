"""
Unit tests for PromptLibrary template management and rendering.
"""

import pytest

from revitpy.ai.exceptions import PromptError
from revitpy.ai.prompts import PromptLibrary


class TestPromptLibrary:
    """Tests for prompt template registration and rendering."""

    # ----------------------------------------------------------
    # Built-in templates
    # ----------------------------------------------------------

    def test_builtin_templates_registered(self, prompt_library):
        """All expected built-in templates exist."""
        names = prompt_library.list_templates()
        assert "element_summary" in names
        assert "quantity_takeoff" in names
        assert "validation_report" in names
        assert "natural_language_query" in names
        assert "safety_preview" in names

    def test_render_element_summary(self, prompt_library):
        """Render element_summary with sample data."""
        result = prompt_library.render(
            "element_summary",
            element_id=42,
            name="TestWall",
            category="Walls",
            parameters={"Height": "10.0", "Width": "0.5"},
        )
        assert "42" in result
        assert "TestWall" in result
        assert "Height" in result
        assert "0.5" in result

    def test_render_quantity_takeoff(self, prompt_library):
        """Render quantity_takeoff template."""
        result = prompt_library.render(
            "quantity_takeoff",
            category="Walls",
        )
        assert "Walls" in result
        assert "type" in result  # default group_by

    def test_render_validation_report_no_issues(self, prompt_library):
        """Render validation_report with empty issues."""
        result = prompt_library.render(
            "validation_report",
            issues=[],
        )
        assert "No issues found" in result

    def test_render_validation_report_with_issues(self, prompt_library):
        """Render validation_report with issues."""
        result = prompt_library.render(
            "validation_report",
            issues=[
                {"severity": "WARNING", "message": "Missing room tag"},
            ],
        )
        assert "WARNING" in result
        assert "Missing room tag" in result

    def test_render_natural_language_query(self, prompt_library):
        """Render natural_language_query template."""
        result = prompt_library.render(
            "natural_language_query",
            user_query="Find all walls on Level 1",
            categories=["Walls", "Doors", "Windows"],
        )
        assert "Find all walls" in result
        assert "Walls, Doors, Windows" in result

    def test_render_safety_preview(self, prompt_library):
        """Render safety_preview template."""
        result = prompt_library.render(
            "safety_preview",
            tool_name="modify_parameter",
            category="modify",
            arguments={"element_id": 1, "value": "10"},
            safety_mode="cautious",
            requires_confirmation=True,
        )
        assert "modify_parameter" in result
        assert "cautious" in result

    # ----------------------------------------------------------
    # Custom templates
    # ----------------------------------------------------------

    def test_register_and_render_custom_template(self, prompt_library):
        """Custom templates can be registered and rendered."""
        prompt_library.register_template("greeting", "Hello, {{ name }}!")
        result = prompt_library.render("greeting", name="RevitPy")
        assert result == "Hello, RevitPy!"

    def test_register_overwrites_existing(self, prompt_library):
        """Re-registering a template replaces it."""
        prompt_library.register_template("custom", "v1: {{ x }}")
        prompt_library.register_template("custom", "v2: {{ x }}")
        result = prompt_library.render("custom", x="test")
        assert result.startswith("v2:")

    def test_get_template_returns_source(self, prompt_library):
        """get_template returns the raw Jinja2 source string."""
        prompt_library.register_template("simple", "{{ a }} + {{ b }}")
        source = prompt_library.get_template("simple")
        assert "{{ a }}" in source

    def test_get_template_returns_none_for_unknown(self, prompt_library):
        """get_template returns None for non-existent templates."""
        assert prompt_library.get_template("nonexistent") is None

    def test_list_templates_sorted(self, prompt_library):
        """list_templates returns names in sorted order."""
        names = prompt_library.list_templates()
        assert names == sorted(names)

    # ----------------------------------------------------------
    # Error handling
    # ----------------------------------------------------------

    def test_render_missing_template_raises_prompt_error(self, prompt_library):
        """Rendering a non-existent template raises PromptError."""
        with pytest.raises(PromptError, match="not found"):
            prompt_library.render("no_such_template")

    def test_render_missing_variable_raises_prompt_error(self, prompt_library):
        """Missing required variables raise PromptError."""
        prompt_library.register_template("strict", "Hello {{ name }}!")
        with pytest.raises(PromptError, match="Failed to render"):
            prompt_library.render("strict")

    def test_prompt_error_has_template_name(self, prompt_library):
        """PromptError carries the template_name attribute."""
        with pytest.raises(PromptError) as exc_info:
            prompt_library.render("missing_template")
        assert exc_info.value.template_name == "missing_template"

    # ----------------------------------------------------------
    # MCP format
    # ----------------------------------------------------------

    def test_to_mcp_prompts_list_structure(self, prompt_library):
        """MCP prompts list has correct structure."""
        mcp_list = prompt_library.to_mcp_prompts_list()
        assert isinstance(mcp_list, list)
        assert len(mcp_list) >= 5  # built-ins

        first = mcp_list[0]
        assert "name" in first
        assert "description" in first
        assert "arguments" in first

    def test_to_mcp_prompts_list_includes_custom(self, prompt_library):
        """Custom templates appear in MCP prompts list."""
        prompt_library.register_template("custom_prompt", "{{ x }}")
        mcp_list = prompt_library.to_mcp_prompts_list()
        names = {p["name"] for p in mcp_list}
        assert "custom_prompt" in names

    def test_to_mcp_prompts_list_sorted(self, prompt_library):
        """MCP prompts list is sorted by name."""
        mcp_list = prompt_library.to_mcp_prompts_list()
        names = [p["name"] for p in mcp_list]
        assert names == sorted(names)
