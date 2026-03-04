"""
Pytest configuration and fixtures for IFC tests.
"""

from types import SimpleNamespace

import pytest

from revitpy.ifc._compat import _HAS_IFCOPENSHELL
from revitpy.ifc.types import (
    BcfIssue,
    IdsRequirement,
    IfcMapping,
)


@pytest.fixture
def skip_without_ifcopenshell():
    """Skip the test if ifcopenshell is not installed."""
    if not _HAS_IFCOPENSHELL:
        pytest.skip("ifcopenshell is not installed")


@pytest.fixture
def sample_elements():
    """Provide a list of mock elements with id/name/category attributes."""
    return [
        SimpleNamespace(
            id=1,
            name="Exterior Wall",
            category="WallElement",
            height=3.0,
            width=0.3,
            length=10.0,
            material="Concrete",
        ),
        SimpleNamespace(
            id=2,
            name="Interior Wall",
            category="WallElement",
            height=2.8,
            width=0.15,
            length=5.0,
            material="Drywall",
        ),
        SimpleNamespace(
            id=3,
            name="Main Door",
            category="DoorElement",
            height=2.1,
            width=0.9,
        ),
        SimpleNamespace(
            id=4,
            name="Living Room Window",
            category="WindowElement",
            height=1.5,
            width=1.2,
        ),
        SimpleNamespace(
            id=5,
            name="Kitchen",
            category="RoomElement",
            area=15.0,
            volume=40.5,
        ),
    ]


@pytest.fixture
def sample_ifc_mapping():
    """Provide a sample IfcMapping instance."""
    return IfcMapping(
        revitpy_type="WallElement",
        ifc_entity_type="IfcWall",
        property_map={"height": "Height", "width": "Width"},
        bidirectional=True,
    )


@pytest.fixture
def sample_ids_requirements():
    """Provide a list of sample IDS requirements."""
    return [
        IdsRequirement(
            name="Wall height check",
            description="All walls must have a height",
            entity_type="WallElement",
            property_name="height",
            required=True,
        ),
        IdsRequirement(
            name="Wall material check",
            description="All walls must be Concrete",
            entity_type="WallElement",
            property_name="material",
            property_value="Concrete",
            required=True,
        ),
        IdsRequirement(
            name="Room area check",
            description="All rooms must have an area",
            entity_type="RoomElement",
            property_name="area",
            required=True,
        ),
        IdsRequirement(
            name="Door width check",
            description="Doors must be 0.9m wide",
            entity_type="DoorElement",
            property_name="width",
            property_value="0.9",
            required=True,
        ),
    ]


@pytest.fixture
def sample_bcf_issues():
    """Provide a list of sample BCF issues."""
    return [
        BcfIssue(
            guid="issue-001",
            title="Missing fire rating",
            description="Wall W-101 is missing its fire rating property.",
            author="Alice",
            status="Open",
            assigned_to="Bob",
            element_ids=["1"],
        ),
        BcfIssue(
            guid="issue-002",
            title="Incorrect door width",
            description="Door D-001 does not match specification.",
            author="Bob",
            status="In Progress",
            assigned_to="Alice",
            element_ids=["3"],
        ),
    ]
