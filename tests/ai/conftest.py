"""
Pytest configuration and fixtures for AI module tests.
"""

from types import SimpleNamespace
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


# ----------------------------------------------------------------------
# Fake RevitPy API context (satisfies revitpy.ai.tools.RevitContext)
# ----------------------------------------------------------------------


class FakeElement:
    """Minimal stand-in for ``revitpy.api.Element``."""

    def __init__(
        self,
        element_id: int,
        name: str,
        category: str,
        log: list[tuple[Any, ...]],
        **params: Any,
    ) -> None:
        self.id = element_id
        self.name = name
        self.category = category
        self.params: dict[str, Any] = dict(params)
        self.fail_on_set = False
        self._log = log

    def get_parameter_value(self, name: str) -> Any:
        if name not in self.params:
            raise KeyError(name)
        return self.params[name]

    def set_parameter_value(self, name: str, value: Any) -> None:
        self._log.append(("set", self.id, name, value))
        if self.fail_on_set:
            raise ValueError(f"Parameter {name} is read-only")
        self.params[name] = value

    def get_all_parameters(self) -> dict[str, Any]:
        return {k: SimpleNamespace(value=v) for k, v in self.params.items()}


class FakeTransaction:
    """Records start/commit/rollback into the shared log."""

    def __init__(self, name: str | None, log: list[tuple[Any, ...]]) -> None:
        self.name = name
        self._log = log

    def __enter__(self) -> "FakeTransaction":
        self._log.append(("start", self.name))
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        self._log.append(("commit",) if exc_type is None else ("rollback",))
        return False


class FakeDocument:
    def __init__(self, elements: list[FakeElement]) -> None:
        self.elements = elements

    def get_all_elements(self) -> list[FakeElement]:
        return list(self.elements)


class FakeRevitAPI:
    """Duck-typed ``revitpy.api.RevitAPI`` with an in-memory document."""

    def __init__(self) -> None:
        self.log: list[tuple[Any, ...]] = []
        self.elements = [
            FakeElement(1, "Wall A", "Walls", self.log, Type="Generic 200", Mark="W1"),
            FakeElement(2, "Wall B", "Walls", self.log, Type="Generic 200", Mark="W1"),
            FakeElement(3, "Wall C", "Walls", self.log, Type="Brick 300"),
            FakeElement(4, "", "Doors", self.log, Type="Single", Mark="D1"),
        ]
        self.active_document: FakeDocument | None = FakeDocument(self.elements)

    def get_element_by_id(self, element_id: Any) -> FakeElement | None:
        return next((e for e in self.elements if e.id == element_id), None)

    def transaction(self, name: str | None = None, **kwargs: Any) -> FakeTransaction:
        return FakeTransaction(name, self.log)


@pytest.fixture
def fake_api() -> FakeRevitAPI:
    """An in-memory Revit API context with walls and a door."""
    return FakeRevitAPI()


@pytest.fixture
def connected_tools(fake_api: FakeRevitAPI) -> RevitTools:
    """RevitTools bound to the fake API context."""
    return RevitTools(fake_api)
