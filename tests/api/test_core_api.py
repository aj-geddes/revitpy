"""Tests for the core API: transactions, typed queries, parameters, exports, CLI."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pydantic
import pytest
from click.testing import CliRunner

import revitpy
from revitpy import RevitAPI
from revitpy.api import Door, Element, Wall
from revitpy.api.element import ParameterValue, element_id_value
from revitpy.api.exceptions import TransactionError
from revitpy.api.wrapper import RevitDocumentProvider
from revitpy.cli import main
from revitpy.testing.mock_revit import MockApplication, MockDocument, MockElement


@pytest.fixture
def api_and_doc() -> tuple[RevitAPI, MockDocument, list[MockElement], MockElement]:
    app = MockApplication()
    doc = app.CreateDocument()
    walls = [doc.CreateElement(name=n, category="Walls") for n in ("W1", "W2")]
    door = doc.CreateElement(name="D1", category="Doors")
    api = RevitAPI()
    api.connect(app)
    return api, doc, walls, door


def comments(element: MockElement) -> Any:
    return element.GetParameterValue("Comments").value


class TestTypedQueries:
    def test_query_walls(self, api_and_doc: Any) -> None:
        api, _, walls, _ = api_and_doc
        result = api.query(Wall).execute()
        assert {e.id.value for e in result} == {w.Id.Value for w in walls}
        assert all(isinstance(e, Wall) for e in result)

    def test_query_doors(self, api_and_doc: Any) -> None:
        api, _, _, door = api_and_doc
        result = api.query(Door).execute()
        assert [e.id.value for e in result] == [door.Id.Value]

    def test_untyped_query_wraps_subclasses(self, api_and_doc: Any) -> None:
        api, _, _, _ = api_and_doc
        result = api.elements.execute()
        assert len(result) == 3
        assert sum(isinstance(e, Wall) for e in result) == 2

    def test_get_element_by_id_is_typed(self, api_and_doc: Any) -> None:
        api, _, walls, _ = api_and_doc
        element = api.get_element_by_id(walls[0].Id.Value)
        assert isinstance(element, Wall)
        assert element.category == "Walls"


class TestParameters:
    def test_set_after_get(self, api_and_doc: Any) -> None:
        api, _, walls, _ = api_and_doc
        element = api.get_element_by_id(walls[0].Id.Value)
        assert element.get_parameter_value("Comments") == ""
        with api.transaction("t"):
            element.set_parameter_value("Comments", "x")
        assert element.changes == {"Comments": {"old": "", "new": "x"}}
        assert comments(walls[0]) == "x"

    @pytest.mark.parametrize(
        ("storage", "raw", "expected"),
        [("Double", "12.5", 12.5), ("Integer", "7", 7), ("String", "a", "a")],
    )
    def test_parameter_value_coercion(
        self, storage: str, raw: str, expected: Any
    ) -> None:
        value = ParameterValue(name="p", value=raw, type_name="x", storage_type=storage)
        assert value.value == expected
        assert type(value.value) is type(expected)

    def test_parameter_value_invalid(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            ParameterValue(name="p", value="abc", type_name="x", storage_type="Double")

    def test_parameter_value_none(self) -> None:
        value = ParameterValue(
            name="p", value=None, type_name="x", storage_type="Double"
        )
        assert value.value is None

    def test_element_id_value(self) -> None:
        assert element_id_value(5) == 5
        assert element_id_value(SimpleNamespace(Value=9)) == 9
        assert element_id_value(SimpleNamespace(IntegerValue=3)) == 3

    @pytest.mark.parametrize(
        ("category", "expected"),
        [("Walls", Wall), ("OST_Walls", Wall), ("Doors", Door), ("Generic", Element)],
    )
    def test_wrap_by_category(self, category: str, expected: type) -> None:
        wrapped = Element.wrap(MockElement(element_id=1, category=category))
        assert type(wrapped) is expected


class TestTransactions:
    def test_commit_persists(self, api_and_doc: Any) -> None:
        api, _, walls, _ = api_and_doc
        with api.transaction("t"):
            api.get_element_by_id(walls[0].Id.Value).set_parameter_value(
                "Comments", "x"
            )
        assert comments(walls[0]) == "x"

    def test_exception_rolls_back_and_propagates(self, api_and_doc: Any) -> None:
        api, _, walls, _ = api_and_doc
        with pytest.raises(RuntimeError, match="boom"):
            with api.transaction("t"):
                api.get_element_by_id(walls[0].Id.Value).set_parameter_value(
                    "Comments", "x"
                )
                raise RuntimeError("boom")
        assert comments(walls[0]) == ""

    def test_rollback_refreshes_held_wrappers(self, api_and_doc: Any) -> None:
        api, _, walls, _ = api_and_doc
        element = api.get_element_by_id(walls[0].Id.Value)
        with pytest.raises(RuntimeError):
            with api.transaction("t"):
                element.set_parameter_value("Comments", "x")
                raise RuntimeError
        assert element.get_parameter_value("Comments") == ""
        assert not element.is_dirty

    def test_rollback_restores_deleted_elements(self, api_and_doc: Any) -> None:
        api, doc, walls, _ = api_and_doc
        with pytest.raises(RuntimeError):
            with api.transaction("t"):
                api.delete_elements(api.get_element_by_id(walls[0].Id.Value))
                assert doc.GetElementCount() == 2
                raise RuntimeError
        assert doc.GetElementCount() == 3

    def test_document_without_transactions(self) -> None:
        provider = RevitDocumentProvider(SimpleNamespace(Title="t", PathName=""))
        assert provider.supports_transactions is False
        with pytest.raises(TransactionError):
            provider.start_transaction("t")

    def test_transaction_duration_outside_event_loop(self, api_and_doc: Any) -> None:
        api, _, _, _ = api_and_doc
        with api.transaction("t") as txn:
            pass
        assert txn.duration is not None and txn.duration >= 0

    def test_document_info(self, api_and_doc: Any) -> None:
        api, _, _, _ = api_and_doc
        info = api.get_document_info()
        assert info.is_modified is True
        assert info.is_read_only is False


class TestExports:
    def test_documented_imports(self) -> None:
        from revitpy import EventPriority, EventType, FilterOperator
        from revitpy.orm import create_context

        assert callable(create_context)
        assert FilterOperator.EQUALS
        assert EventType.ELEMENT_MODIFIED
        assert EventPriority.HIGH

    def test_version(self) -> None:
        assert isinstance(revitpy.__version__, str)
        assert revitpy.__version__

    def test_star_import(self) -> None:
        namespace: dict[str, Any] = {}
        exec("from revitpy import *", namespace)  # noqa: S102
        assert "RevitAPI" in namespace

    def test_performance_package_imports(self) -> None:
        from revitpy.performance import (
            BenchmarkSuite,
            MemoryManager,
            MetricsCollector,
            OptimizationConfig,
            PerformanceOptimizer,
        )

        assert all(
            (
                BenchmarkSuite,
                MemoryManager,
                MetricsCollector,
                OptimizationConfig,
                PerformanceOptimizer,
            )
        )


class TestCli:
    def test_version(self) -> None:
        result = CliRunner().invoke(main, ["version"])
        assert result.exit_code == 0
        assert result.output.startswith("revitpy ")

    def test_doctor_json(self) -> None:
        result = CliRunner().invoke(main, ["doctor", "--json"])
        assert result.exit_code == 0
        checks = json.loads(result.output)["checks"]
        assert all(set(c) == {"name", "status", "detail"} for c in checks)
        assert any(c["name"] == "Revit API" for c in checks)

    def test_help_lists_commands(self) -> None:
        result = CliRunner().invoke(main, ["--help"])
        assert result.exit_code == 0
        for command in ("version", "doctor", "mcp-serve"):
            assert command in result.output
