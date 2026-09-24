"""Tests for the BCF 2.1 archive layout written/read by BcfManager."""

import zipfile
from xml.etree import ElementTree as ET  # noqa: N817

import pytest

from revitpy.ifc.bcf import BcfManager
from revitpy.ifc.types import BcfIssue

GUID = "3f1c2d3e-4b5a-4c6d-8e7f-9a0b1c2d3e4f"
IFC_GUID = "2O2Fr$t4X7Zf8NOew3FLOH"
VP_GUID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def issue():
    return BcfIssue(
        guid=GUID,
        title="Clash",
        description="Duct hits beam",
        author="alice@example.com",
        status="Open",
        assigned_to="bob@example.com",
        element_ids=[IFC_GUID, "12345"],
        snapshot=b"\x89PNG fake",
    )


@pytest.fixture
def archive(tmp_path, issue):
    path = tmp_path / "a.bcf"
    BcfManager().write_bcf([issue], path)
    return path


def _xml(path, member):
    with zipfile.ZipFile(path) as zf:
        return ET.fromstring(zf.read(member))  # noqa: S314 - test-generated data


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_archive_contains_bcf_version(archive):
    root = _xml(archive, "bcf.version")
    assert root.tag == "Version"
    assert root.get("VersionId") == "2.1"
    assert root.findtext("DetailedVersion") == "2.1"


def test_topic_folder_layout(archive):
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    assert {
        "bcf.version",
        f"{GUID}/markup.bcf",
        f"{GUID}/viewpoint.bcfv",
        f"{GUID}/snapshot.png",
    } == names


def test_markup_structure(archive):
    root = _xml(archive, f"{GUID}/markup.bcf")
    assert root.tag == "Markup"

    topic = root.find("Topic")
    assert topic.get("Guid") == GUID
    assert topic.get("TopicStatus") == "Open"
    # Order mandated by the Topic xs:sequence in BCF 2.1 markup.xsd.
    assert [c.tag for c in topic] == [
        "Title",
        "CreationDate",
        "CreationAuthor",
        "AssignedTo",
        "Description",
    ]

    viewpoints = root.find("Viewpoints")
    assert viewpoints.get("Guid")
    assert viewpoints.findtext("Viewpoint") == "viewpoint.bcfv"
    assert viewpoints.findtext("Snapshot") == "snapshot.png"


def test_viewpoint_components(archive):
    markup = _xml(archive, f"{GUID}/markup.bcf")
    info = _xml(archive, f"{GUID}/viewpoint.bcfv")

    assert info.tag == "VisualizationInfo"
    assert info.get("Guid") == markup.find("Viewpoints").get("Guid")

    first, second = info.findall("Components/Selection/Component")
    assert first.get("IfcGuid") == IFC_GUID
    assert second.get("IfcGuid") is None
    assert second.findtext("OriginatingSystem") == "RevitPy"
    assert second.findtext("AuthoringToolId") == "12345"
    # Visibility is mandatory in BCF 2.1 Components.
    assert info.find("Components/Visibility") is not None


def test_round_trip_preserves_everything(archive, issue):
    (loaded,) = BcfManager().read_bcf(archive)

    assert loaded.guid == issue.guid
    assert loaded.title == issue.title
    assert loaded.description == issue.description
    assert loaded.author == issue.author
    assert loaded.status == issue.status
    assert loaded.assigned_to == issue.assigned_to
    assert loaded.element_ids == [IFC_GUID, "12345"]
    assert loaded.snapshot == b"\x89PNG fake"
    assert loaded.creation_date.tzinfo is not None


def test_issue_without_elements_has_no_viewpoint(tmp_path):
    path = tmp_path / "plain.bcf"
    BcfManager().write_bcf([BcfIssue(guid=GUID, title="t")], path)

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    assert not any(n.endswith(".bcfv") for n in names)
    assert _xml(path, f"{GUID}/markup.bcf").find("Viewpoints") is None


def test_reads_legacy_markup_xml(tmp_path):
    path = _write_zip(
        tmp_path / "legacy.bcf",
        {
            "issue-001/markup.xml": (
                '<Markup><Topic Guid="issue-001"><Title>Old</Title>'
                "<CreationAuthor>A</CreationAuthor>"
                "<CreationDate>2024-01-02T03:04:05</CreationDate>"
                "<TopicStatus>Closed</TopicStatus>"
                "<ReferenceLink>7</ReferenceLink></Topic></Markup>"
            )
        },
    )

    (loaded,) = BcfManager().read_bcf(path)
    assert loaded.title == "Old"
    assert loaded.status == "Closed"
    assert loaded.element_ids == ["7"]


def test_prefers_markup_bcf_over_xml(tmp_path):
    def markup(title):
        return (
            f'<Markup><Topic Guid="{GUID}"><Title>{title}</Title>'
            "<CreationDate>2024-01-02T03:04:05Z</CreationDate>"
            "<CreationAuthor>a</CreationAuthor></Topic></Markup>"
        )

    path = _write_zip(
        tmp_path / "both.bcf",
        {f"{GUID}/markup.xml": markup("Old"), f"{GUID}/markup.bcf": markup("New")},
    )

    loaded = BcfManager().read_bcf(path)
    assert [i.title for i in loaded] == ["New"]


def test_reads_bcf3_topic_viewpoints(tmp_path):
    path = _write_zip(
        tmp_path / "v3.bcf",
        {
            "bcf.version": '<Version VersionId="3.0"/>',
            f"{GUID}/markup.bcf": (
                f'<Markup><Topic Guid="{GUID}" TopicStatus="Open"><Title>V3</Title>'
                "<CreationDate>2024-01-02T03:04:05Z</CreationDate>"
                "<CreationAuthor>a</CreationAuthor>"
                f'<Viewpoints><ViewPoint Guid="{VP_GUID}">'
                "<Viewpoint>vp1.bcfv</Viewpoint></ViewPoint></Viewpoints>"
                "</Topic></Markup>"
            ),
            f"{GUID}/vp1.bcfv": (
                f'<VisualizationInfo Guid="{VP_GUID}"><Components><Selection>'
                f'<Component IfcGuid="{IFC_GUID}"/></Selection>'
                '<Visibility DefaultVisibility="true"/></Components>'
                "</VisualizationInfo>"
            ),
        },
    )

    (loaded,) = BcfManager().read_bcf(path)
    assert loaded.title == "V3"
    assert loaded.element_ids == [IFC_GUID]


def test_entity_expansion_is_rejected(tmp_path):
    """With defusedxml, DTD entity declarations are refused (topic skipped)."""
    pytest.importorskip("defusedxml")
    path = _write_zip(
        tmp_path / "evil.bcf",
        {
            f"{GUID}/markup.bcf": (
                '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
                '<!ENTITY lol2 "&lol;&lol;&lol;">]>'
                f'<Markup><Topic Guid="{GUID}"><Title>&lol2;</Title></Topic>'
                "</Markup>"
            )
        },
    )

    assert BcfManager().read_bcf(path) == []
