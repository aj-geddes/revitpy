"""Unit tests of the RevitPy-side bridge analyses (pure functions of element dicts)."""

from __future__ import annotations

import json
import tomllib
from importlib import metadata
from typing import Any

import pytest
from bridge_support import BRIDGE_DIR
from revitpy_bridge_analyses import (
    bounding_box_clashes,
    element_summary,
    embodied_carbon,
    parameter_statistics,
    quantity_takeoff,
)
from revitpy_bridge_analyses._elements import FT2_TO_M2, FT3_TO_M3, FT_TO_M

from revitpy.sustainability import EpdDatabase


def param(
    value: Any,
    storage: str = "Double",
    builtin: str | None = None,
    display: str | None = None,
) -> dict[str, Any]:
    return {
        "storage_type": storage,
        "value": value,
        "display": display,
        "builtin": builtin,
        "data_type": None,
        "read_only": False,
    }


def wall(
    element_id: int,
    area: float = 300.0,
    volume: float = 200.0,
    length: float = 30.0,
    level: str = "Level 1",
    **extra: Any,
) -> dict[str, Any]:
    element = {
        "id": element_id,
        "name": "Generic - 8in",
        "category": "Walls",
        "type_name": "Generic - 8in",
        "level": level,
        "units": "ft",
        "parameters": {
            "Area": param(area, builtin="HOST_AREA_COMPUTED"),
            "Volume": param(volume, builtin="HOST_VOLUME_COMPUTED"),
            "Length": param(length, builtin="CURVE_ELEM_LENGTH"),
            "Mark": param(f"W-{element_id}", "String"),
        },
    }
    element.update(extra)
    return element


def room(element_id: int, area: float, volume: float, level: str) -> dict[str, Any]:
    # German Revit: parameter names are localized, built-in names are not.
    return {
        "id": element_id,
        "name": f"Office {element_id}",
        "category": "Rooms",
        "level": level,
        "parameters": {
            "Fläche": param(area, builtin="ROOM_AREA"),
            "Volumen": param(volume, builtin="ROOM_VOLUME"),
        },
    }


def box(element_id: int, low: list[float], high: list[float], category: str = "Ducts"):
    return {
        "id": element_id,
        "name": f"E{element_id}",
        "category": category,
        "bounding_box": {"min": low, "max": high},
    }


def assert_json(result: Any) -> None:
    json.dumps(result, allow_nan=False)


class TestElementSummary:
    def test_counts(self) -> None:
        elements = [
            wall(1),
            wall(2, level="Level 2"),
            room(3, 100, 900, "Level 1"),
            {"id": 4},
        ]
        result = element_summary(elements, {})
        assert result["element_count"] == 4
        assert result["by_category"] == {"Walls": 2, "<No Category>": 1, "Rooms": 1}
        assert list(result["by_category"]) == ["Walls", "<No Category>", "Rooms"]
        assert result["by_level"] == {"Level 1": 2, "<No Level>": 1, "Level 2": 1}
        assert result["by_type"]["Walls"] == {"Generic - 8in": 2}
        assert result["by_type"]["Rooms"] == {"<No Type>": 1}
        assert_json(result)

    def test_category_filter_is_case_insensitive(self) -> None:
        result = element_summary(
            [wall(1), room(2, 1, 1, "L")], {"categories": ["walls"]}
        )
        assert result["element_count"] == 1
        assert result["by_category"] == {"Walls": 1}

    def test_bad_option(self) -> None:
        with pytest.raises(ValueError):
            element_summary([wall(1)], {"categories": "Walls"})


class TestParameterStatistics:
    def test_numeric_and_text(self) -> None:
        elements = [wall(1, area=100), wall(2, area=300), wall(3, area=200)]
        elements[2]["parameters"]["Mark"]["value"] = "W-1"
        result = parameter_statistics(elements, {})
        area = result["parameters"]["Area"]
        assert area["kind"] == "numeric"
        assert (area["count"], area["min"], area["max"]) == (3, 100, 300)
        assert area["mean"] == pytest.approx(200)
        assert area["sum"] == pytest.approx(600)
        assert "feet" in area["units"]
        mark = result["parameters"]["Mark"]
        assert mark["kind"] == "text"
        assert mark["distinct"] == 2
        assert mark["top"][0] == {"value": "W-1", "count": 2}
        assert_json(result)

    def test_requested_parameters_and_not_found(self) -> None:
        result = parameter_statistics(
            [wall(1)], {"parameters": ["Volume", "Fire Rating"], "top": 1}
        )
        assert list(result["parameters"]) == ["Volume"]
        assert result["not_found"] == ["Fire Rating"]

    def test_missing_values(self) -> None:
        element = wall(1)
        element["parameters"]["Comments"] = param(None, "String")
        assert "Comments" not in parameter_statistics([element], {})["parameters"]
        kept = parameter_statistics([element], {"include_empty": True})
        assert kept["parameters"]["Comments"]["missing"] == 1

    def test_invalid_top(self) -> None:
        with pytest.raises(ValueError):
            parameter_statistics([wall(1)], {"top": 0})


class TestQuantityTakeoff:
    def test_walls_by_category_in_metric_and_imperial(self) -> None:
        result = quantity_takeoff([wall(1), wall(2)], {})
        walls = result["groups"]["Walls"]
        assert walls["count"] == 2
        assert walls["area_m2"] == pytest.approx(600 * FT2_TO_M2, abs=1e-4)
        assert walls["volume_m3"] == pytest.approx(400 * FT3_TO_M3, abs=1e-4)
        assert walls["length_m"] == pytest.approx(60 * FT_TO_M, abs=1e-4)
        assert walls["area_ft2"] == pytest.approx(600, abs=1e-3)
        assert walls["volume_ft3"] == pytest.approx(400, abs=1e-3)
        assert walls["length_ft"] == pytest.approx(60, abs=1e-3)
        assert result["totals"]["count"] == 2
        assert result["group_by"] == "category"
        assert_json(result)

    def test_rooms_by_level_use_builtin_parameters(self) -> None:
        elements = [
            room(1, 100, 900, "Level 1"),
            room(2, 50, 450, "Level 1"),
            room(3, 80, 720, "Level 2"),
        ]
        result = quantity_takeoff(elements, {"group_by": "level"})
        assert set(result["groups"]) == {"Level 1", "Level 2"}
        assert result["groups"]["Level 1"]["area_ft2"] == pytest.approx(150, abs=1e-3)
        assert result["groups"]["Level 2"]["volume_ft3"] == pytest.approx(720, abs=1e-3)
        assert result["totals"]["area_m2"] == pytest.approx(230 * FT2_TO_M2, abs=1e-3)

    def test_length_from_location_curve(self) -> None:
        element = {
            "id": 9,
            "category": "Pipes",
            "parameters": {},
            "location": {
                "type": "curve",
                "start": [0, 0, 0],
                "end": [10, 0, 0],
                "length": 10.0,
            },
        }
        result = quantity_takeoff([element], {})
        assert result["groups"]["Pipes"]["length_ft"] == pytest.approx(10, abs=1e-3)

    def test_elements_without_quantities_and_filter(self) -> None:
        door = {
            "id": 7,
            "category": "Doors",
            "parameters": {"Mark": param("D1", "String")},
        }
        result = quantity_takeoff([wall(1), door], {})
        assert result["elements_without_quantities"] == [7]
        assert result["groups"]["Doors"]["count"] == 1
        only_walls = quantity_takeoff([wall(1), door], {"categories": ["Walls"]})
        assert set(only_walls["groups"]) == {"Walls"}

    def test_invalid_group_by(self) -> None:
        with pytest.raises(ValueError, match="group_by"):
            quantity_takeoff([wall(1)], {"group_by": "phase"})


class TestEmbodiedCarbon:
    def test_concrete_volume_based(self) -> None:
        materials = [
            {
                "id": 1,
                "name": "Concrete, Cast-in-Place",
                "material_class": "Concrete",
                "volume": 100.0,
                "area": 300.0,
            }
        ]
        elements = [wall(1, materials=materials), wall(2, materials=materials)]
        result = embodied_carbon(elements, {})
        (row,) = result["materials"]
        epd = EpdDatabase().lookup("Concrete, Cast-in-Place", "Concrete")
        expected = 200 * FT3_TO_M3 * epd.gwp_per_m3
        assert row["kgco2e"] == pytest.approx(expected, abs=0.01)
        assert row["volume_m3"] == pytest.approx(200 * FT3_TO_M3, abs=1e-4)
        assert row["element_count"] == 2
        assert row["method"] == "volume_based"
        assert result["total_kgco2e"] == pytest.approx(expected, abs=0.01)
        assert result["total_tco2e"] == pytest.approx(expected / 1000, abs=0.001)
        assert result["lifecycle_stages"] == ["A1", "A2", "A3"]
        assert result["benchmark"] is None
        assert "ICE" in result["basis"]
        assert_json(result)

    def test_unmatched_unquantified_and_missing(self) -> None:
        elements = [
            wall(
                1,
                materials=[
                    {
                        "id": 2,
                        "name": "Unobtainium",
                        "material_class": None,
                        "volume": 10.0,
                        "area": 5.0,
                    },
                    {
                        "id": 3,
                        "name": "Paint - White",
                        "material_class": "Paint",
                        "volume": 0.0,
                        "area": 50.0,
                    },
                    {
                        "id": 4,
                        "name": "Structural Steel",
                        "material_class": "Metal",
                        "volume": 1.0,
                        "area": 2.0,
                    },
                ],
            ),
            wall(2),
        ]
        result = embodied_carbon(elements, {})
        assert [row["material"] for row in result["materials"]] == ["Structural Steel"]
        assert [u["material"] for u in result["unmatched"]] == ["Unobtainium"]
        assert [u["material"] for u in result["unquantified"]] == ["Paint - White"]
        assert result["elements_without_materials"] == 1

    def test_benchmark(self) -> None:
        materials = [
            {
                "id": 1,
                "name": "Concrete",
                "material_class": "Concrete",
                "volume": 1000.0,
                "area": 0.0,
            }
        ]
        result = embodied_carbon(
            [wall(1, materials=materials)],
            {"gross_floor_area_m2": 10, "building_type": "office"},
        )
        benchmark = result["benchmark"]
        assert benchmark["kgco2e_per_m2"] == pytest.approx(
            result["total_kgco2e"] / 10, abs=0.01
        )
        assert benchmark["target_kgco2e_per_m2"] == 350.0
        assert benchmark["rating"]

    def test_invalid_area(self) -> None:
        with pytest.raises(ValueError):
            embodied_carbon([wall(1)], {"gross_floor_area_m2": 0})


class TestBoundingBoxClashes:
    def test_overlap_touching_and_tolerance(self) -> None:
        elements = [
            box(1, [0, 0, 0], [10, 1, 1]),
            box(2, [9, 0.5, 0.5], [12, 2, 2], "Pipes"),  # overlaps 1 x 0.5 x 0.5
            box(3, [12, 0, 0], [13, 1, 1]),  # touches 2 only
            {"id": 4, "category": "Ducts"},  # no box
            box(5, [0, 0, 0], [1, 1], "Ducts"),  # malformed
        ]
        result = bounding_box_clashes(elements, {})
        assert result["clash_count"] == 1
        (clash,) = result["clashes"]
        assert {clash["a_id"], clash["b_id"]} == {1, 2}
        assert clash["overlap_ft3"] == pytest.approx(0.25)
        assert clash["overlap_m3"] == pytest.approx(0.25 * FT3_TO_M3, abs=1e-4)
        assert result["by_category_pair"] == {"Ducts x Pipes": 1}
        assert (result["checked"], result["skipped_without_box"]) == (3, 2)
        assert "bounding-box" in result["method"]
        assert_json(result)

        assert bounding_box_clashes(elements, {"tolerance_ft": 0.5})["clash_count"] == 0

    def test_same_category_and_truncation(self) -> None:
        elements = [box(i, [i * 0.1, 0, 0], [5 + i * 0.1, 1, 1]) for i in range(5)]
        result = bounding_box_clashes(elements, {"max_results": 3})
        assert result["clash_count"] == 10
        assert len(result["clashes"]) == 3
        assert result["truncated"] is True
        volumes = [c["overlap_ft3"] for c in result["clashes"]]
        assert volumes == sorted(volumes, reverse=True)
        ignored = bounding_box_clashes(elements, {"ignore_same_category": True})
        assert ignored["clash_count"] == 0

    @pytest.mark.parametrize(
        "options", [{"tolerance_ft": -1}, {"max_results": 0}, {"tolerance_ft": "x"}]
    )
    def test_invalid_options(self, options: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            bounding_box_clashes([], options)


class TestRegistration:
    NAMES = {
        "element_summary",
        "parameter_statistics",
        "quantity_takeoff",
        "embodied_carbon",
        "bounding_box_clashes",
    }

    def test_import_registers_all(self) -> None:
        from revitpy_bridge_analyses import analyses

        from revitpy.revit import live

        assert set(analyses.register_all()) == self.NAMES
        assert self.NAMES <= set(live.registered_analyses())

    def test_entry_point_declared(self) -> None:
        pyproject = tomllib.loads(
            (BRIDGE_DIR / "analyses" / "pyproject.toml").read_text(encoding="utf-8")
        )
        project = pyproject["project"]
        assert project["entry-points"]["revitpy.analyses"] == {
            "bridge": "revitpy_bridge_analyses.analyses"
        }
        assert project["requires-python"] == ">=3.11"
        assert "revitpy" in project["dependencies"]

    def test_entry_point_installed(self) -> None:
        from revitpy.revit import live

        try:
            metadata.distribution("revitpy-bridge-analyses")
        except metadata.PackageNotFoundError:
            pytest.skip("revitpy-bridge-analyses is not installed")
        assert "bridge" in live.load_analysis_plugins()
