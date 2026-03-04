"""
Pytest configuration and fixtures for AI module tests.
"""

from typing import Any

import pytest

from revitpy.ai.prompts import PromptLibrary
from revitpy.ai.safety import SafetyGuard
from revitpy.ai.tools import RevitTools
from revitpy.ai.types import (
    ParameterType,
    SafetyConfig,
    SafetyMode,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
)


@pytest.fixture
def sample_tool_definition() -> ToolDefinition:
    """A simple tool definition for testing."""
    return ToolDefinition(
        name="test_tool",
        description="A test tool",
        category=ToolCategory.QUERY,
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="Search query",
            ),
            ToolParameter(
                name="limit",
                type=ParameterType.INTEGER,
                description="Max results",
                required=False,
                default=10,
            ),
        ],
        returns_description="Query results",
    )


@pytest.fixture
def modify_tool_definition() -> ToolDefinition:
    """A modify-category tool definition for testing."""
    return ToolDefinition(
        name="modify_tool",
        description="A modify tool",
        category=ToolCategory.MODIFY,
        parameters=[
            ToolParameter(
                name="element_id",
                type=ParameterType.INTEGER,
                description="Element ID",
            ),
            ToolParameter(
                name="value",
                type=ParameterType.STRING,
                description="New value",
            ),
        ],
        returns_description="Modification result",
    )


@pytest.fixture
def read_only_safety_config() -> SafetyConfig:
    """Safety config in READ_ONLY mode."""
    return SafetyConfig(mode=SafetyMode.READ_ONLY)


@pytest.fixture
def cautious_safety_config() -> SafetyConfig:
    """Safety config in CAUTIOUS mode."""
    return SafetyConfig(
        mode=SafetyMode.CAUTIOUS,
        require_confirmation_for=[ToolCategory.MODIFY],
    )


@pytest.fixture
def full_access_safety_config() -> SafetyConfig:
    """Safety config in FULL_ACCESS mode."""
    return SafetyConfig(mode=SafetyMode.FULL_ACCESS)


@pytest.fixture
def blocked_safety_config() -> SafetyConfig:
    """Safety config with blocked tools."""
    return SafetyConfig(
        mode=SafetyMode.FULL_ACCESS,
        blocked_tools=["dangerous_tool"],
    )


@pytest.fixture
def revit_tools() -> RevitTools:
    """A RevitTools instance with built-in tools."""
    return RevitTools()


@pytest.fixture
def prompt_library() -> PromptLibrary:
    """A PromptLibrary instance with built-in templates."""
    return PromptLibrary()
