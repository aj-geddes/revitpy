"""Integration tests for IfcExporter using a real ifcopenshell installation.

The whole module is skipped when ifcopenshell is not installed. Each test
exports a file, re-opens it with ifcopenshell and inspects the result.
"""

from types import SimpleNamespace

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
import ifcopenshell.util.element as ifc_element  # noqa: E402

from revitpy.ifc import IfcExportConfig, IfcExporter, IfcVersion  # noqa: E402

ALL_VERSIONS = list(IfcVersion)


@pytest.fixture
def elements():
    """Elements on two levels, one without level, and one unmapped."""
    return [
        SimpleNamespace(
            id=1,
            name="Wall A",
            category="WallElement",
            level=SimpleNamespace(name="Level 1", elevation=0.0),
            bounding_box={"min": (0.0, 0.0, 0.0), "max": (5.0, 0.3, 3.0)},
        ),
        SimpleNamespace(id=2, name="Wall B", category="WallElement", level="Level 2"),
        SimpleNamespace(
            id=3, name="Kitchen", category="RoomElement", level_name="Level 1"
        ),
        SimpleNamespace(id=4, name="Door", category="DoorElement"),
        SimpleNamespace(id=5, name="Alien", category="AlienElement"),
    ]


def _export(tmp_path, elements, version=IfcVersion.IFC4, config=None):
    """Export elements and return the re-opened ifcopenshell model."""
    path = tmp_path / f"{version.value}.ifc"
    IfcExporter(config=config).export(elements, path, version=version)
    return ifcopenshell.open(str(path))


def _walls(model):
    return {w.Name: w for w in model.by_type("IfcWall")}


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_spatial_hierarchy(tmp_path, elements, version):
    """Project > Site > Building > Storeys are linked by IfcRelAggregates."""
    model = _export(tmp_path, elements, version)

    (project,) = model.by_type("IfcProject")
    (site,) = model.by_type("IfcSite")
    (building,) = model.by_type("IfcBuilding")

    assert ifc_element.get_aggregate(site) == project
    assert ifc_element.get_aggregate(building) == site

    storeys = model.by_type("IfcBuildingStorey")
    assert {s.Name for s in storeys} == {"Level 1", "Level 2", "Default Storey"}
    for storey in storeys:
        assert ifc_element.get_aggregate(storey) == building


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_elements_contained_in_storeys(tmp_path, elements, version):
    """Physical elements use IfcRelContainedInSpatialStructure."""
    model = _export(tmp_path, elements, version)
    walls = _walls(model)
    (door,) = model.by_type("IfcDoor")

    assert ifc_element.get_container(walls["Wall A"]).Name == "Level 1"
    assert ifc_element.get_container(walls["Wall B"]).Name == "Level 2"
    assert ifc_element.get_container(door).Name == "Default Storey"
    for product in (walls["Wall A"], walls["Wall B"], door):
        assert product.ContainedInStructure


@pytest.mark.parametrize("version", ALL_VERSIONS)
def test_space_aggregated_under_storey(tmp_path, elements, version):
    """Spaces are aggregated (not contained) under their storey."""
    model = _export(tmp_path, elements, version)
    (space,) = model.by_type("IfcSpace")

    assert ifc_element.get_aggregate(space).Name == "Level 1"
    assert ifc_element.get_container(space) is None


def test_unmapped_elements_skipped(tmp_path, elements):
    model = _export(tmp_path, elements)
    assert "Alien" not in {p.Name for p in model.by_type("IfcProduct")}


def test_placements_units_and_context(tmp_path, elements):
    model = _export(tmp_path, elements)

    for product in model.by_type("IfcProduct"):
        assert product.ObjectPlacement is not None
        assert product.ObjectPlacement.is_a("IfcLocalPlacement")

    (project,) = model.by_type("IfcProject")
    assert project.UnitsInContext is not None
    unit_types = {u.UnitType for u in project.UnitsInContext.Units}
    assert {"LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT"} <= unit_types

    assert any(
        c.ContextIdentifier == "Body"
        for c in model.by_type("IfcGeometricRepresentationSubContext")
    )


def test_bounding_box_geometry(tmp_path, elements):
    """Only elements with a bounding_box get a Body representation."""
    model = _export(tmp_path, elements)
    walls = _walls(model)

    representation = walls["Wall A"].Representation
    assert representation is not None
    assert any(
        r.RepresentationIdentifier == "Body" for r in representation.Representations
    )
    assert walls["Wall B"].Representation is None


def test_include_geometry_false(tmp_path, elements):
    model = _export(tmp_path, elements, config=IfcExportConfig(include_geometry=False))
    assert _walls(model)["Wall A"].Representation is None


def test_storey_elevation(tmp_path):
    element = SimpleNamespace(
        id=1,
        name="W",
        category="WallElement",
        level=SimpleNamespace(name="L3", elevation=3.5),
    )
    model = _export(tmp_path, [element])
    (storey,) = model.by_type("IfcBuildingStorey")
    assert storey.Name == "L3"
    assert storey.Elevation == pytest.approx(3.5)


def test_owner_history_ifc2x3(tmp_path, elements):
    """IFC2X3 requires OwnerHistory on every rooted entity."""
    model = _export(tmp_path, elements, IfcVersion.IFC2X3)
    rooted = model.by_type("IfcRoot")
    assert rooted
    for entity in rooted:
        assert entity.OwnerHistory is not None


def test_custom_names(tmp_path, elements):
    config = IfcExportConfig(
        project_name="P",
        site_name="S",
        building_name="B",
        default_storey_name="Ground",
    )
    model = _export(tmp_path, elements, config=config)

    assert model.by_type("IfcProject")[0].Name == "P"
    assert model.by_type("IfcSite")[0].Name == "S"
    assert model.by_type("IfcBuilding")[0].Name == "B"
    (door,) = model.by_type("IfcDoor")
    assert ifc_element.get_container(door).Name == "Ground"


def test_unknown_property_map_goes_to_pset(tmp_path):
    """Mapped properties that are not IFC attributes land in a pset."""
    exporter = IfcExporter()
    exporter.mapper.register_mapping(
        "WallElement", "IfcWall", {"height": "Height", "comment": "Description"}
    )
    element = SimpleNamespace(
        id=1, name="W", category="WallElement", height=3.0, comment="hello"
    )
    path = tmp_path / "psets.ifc"
    exporter.export([element], path)

    (wall,) = ifcopenshell.open(str(path)).by_type("IfcWall")
    assert wall.Description == "hello"
    psets = ifc_element.get_psets(wall)
    assert psets["RevitPy_Properties"]["Height"] == pytest.approx(3.0)
