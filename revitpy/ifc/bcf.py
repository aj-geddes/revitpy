"""
BCF (BIM Collaboration Format) manager for RevitPy.

This module provides the BcfManager class for creating, reading, and
writing BCF issues as buildingSMART BCF-XML 2.1 archives.

Archive layout written by :meth:`BcfManager.write_bcf` (BCF-XML 2.1)::

    issues.bcf (ZIP)
    +-- bcf.version                 <Version VersionId="2.1">
    +-- <topic-guid>/
        +-- markup.bcf              <Markup><Topic .../><Viewpoints .../></Markup>
        +-- viewpoint.bcfv          <VisualizationInfo> (when elements/snapshot)
        +-- snapshot.png            (when the issue carries a snapshot)

Element ids referenced by an issue are stored as viewpoint
``Components/Selection/Component`` entries: 22-character IFC GlobalIds
use the ``IfcGuid`` attribute, anything else (e.g. Revit element ids) is
written as ``AuthoringToolId`` with ``OriginatingSystem`` ``RevitPy``.
No camera is written, so viewers will select/highlight the components
but will not restore a view.

Reading accepts BCF 2.1 archives, BCF 3.0 topic folders
(``markup.bcf`` / ``*.bcfv``) and legacy RevitPy archives that used
``markup.xml`` with element ids stored as ``ReferenceLink``. XML from
archives is parsed with ``defusedxml`` when it is installed (it is part
of the ``ifc`` extra), falling back to :mod:`xml.etree.ElementTree`.
"""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: N817

from loguru import logger

from .exceptions import BcfError
from .types import BcfIssue

try:
    from defusedxml import DefusedXmlException
    from defusedxml.ElementTree import fromstring as _safe_fromstring

    _HAS_DEFUSEDXML = True
    _XML_ERRORS: tuple[type[Exception], ...] = (ET.ParseError, DefusedXmlException)
except ImportError:  # pragma: no cover - optional dependency
    _HAS_DEFUSEDXML = False
    _safe_fromstring = None
    _XML_ERRORS = (ET.ParseError,)

_IFC_GUID_RE = re.compile(r"[0-9A-Za-z_$]{22}")
_SUPPORTED_READ_VERSIONS = {"2.1", "3.0"}
_MARKUP_NAMES = ("markup.bcf", "markup.xml")
_VIEWPOINT_FILE = "viewpoint.bcfv"
_SNAPSHOT_FILE = "snapshot.png"


def _parse_xml(data: bytes | str) -> ET.Element:
    """Parse untrusted XML, using defusedxml when available."""
    if _safe_fromstring is not None:
        return _safe_fromstring(data)
    return ET.fromstring(data)  # noqa: S314 - defusedxml not installed


def _to_bytes(element: ET.Element) -> bytes:
    """Serialize an element as UTF-8 XML with declaration."""
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _text(parent: ET.Element, tag: str, default: str = "") -> str:
    """Extract text from a child element safely."""
    child = parent.find(tag)
    if child is not None and child.text:
        return child.text
    return default


def _iso(dt: datetime) -> str:
    """Format a datetime as xs:dateTime, assuming UTC for naive values."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def _parse_datetime(value: str | None) -> datetime:
    """Parse an ISO 8601 timestamp, falling back to the current UTC time."""
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)


class BcfManager:
    """Manage BCF issues: create, read, and write.

    Writes BCF-XML 2.1 archives (``bcf.version``, ``markup.bcf``,
    ``viewpoint.bcfv``, ``snapshot.png``) and reads BCF 2.1/3.0 as well
    as legacy RevitPy ``markup.xml`` archives.
    """

    BCF_VERSION = "2.1"

    def __init__(self) -> None:
        self._issues: list[BcfIssue] = []

    @property
    def issues(self) -> list[BcfIssue]:
        """Return all managed issues."""
        return list(self._issues)

    def create_issue(
        self,
        title: str,
        description: str = "",
        *,
        author: str = "",
        status: str = "Open",
        assigned_to: str = "",
        element_ids: list[str] | None = None,
    ) -> BcfIssue:
        """Create a new BCF issue.

        Args:
            title: Short title for the issue.
            description: Detailed description.
            author: Author name.
            status: Issue status string (e.g. ``"Open"``, ``"Closed"``).
            assigned_to: Person assigned to resolve the issue.
            element_ids: List of element IDs referenced by the issue.

        Returns:
            The newly created BcfIssue.
        """
        issue = BcfIssue(
            guid=str(uuid.uuid4()),
            title=title,
            description=description,
            author=author,
            creation_date=datetime.now(UTC),
            status=status,
            assigned_to=assigned_to,
            element_ids=element_ids or [],
        )
        self._issues.append(issue)
        logger.debug("Created BCF issue: {} ({})", title, issue.guid)
        return issue

    def read_bcf(self, path: str | Path) -> list[BcfIssue]:
        """Read BCF issues from a file.

        Supports ``.bcf`` / ``.bcfzip`` / ``.zip`` archives (BCF 2.1,
        BCF 3.0 and legacy RevitPy ``markup.xml``) and ``.json`` files
        as a simplified alternative.

        Args:
            path: Path to the BCF file.

        Returns:
            List of BcfIssue objects.

        Raises:
            BcfError: If the file cannot be read or parsed.
        """
        path = Path(path)

        if not path.exists():
            raise BcfError(
                f"BCF file not found: {path}",
                bcf_path=str(path),
            )

        suffix = path.suffix.lower()

        if suffix == ".json":
            return self._read_json(path)

        if suffix in {".bcf", ".bcfzip", ".zip"}:
            return self._read_zip(path)

        raise BcfError(
            f"Unsupported BCF file format: {suffix}",
            bcf_path=str(path),
        )

    def write_bcf(
        self,
        issues: list[BcfIssue] | None = None,
        path: str | Path = "issues.bcf",
    ) -> Path:
        """Write BCF issues to a BCF-XML 2.1 archive.

        Args:
            issues: Issues to write. Defaults to all managed issues.
            path: Destination file path.

        Returns:
            Path to the created file.

        Raises:
            BcfError: If no issues are provided or writing fails.
        """
        issues = issues if issues is not None else self._issues
        path = Path(path)

        if not issues:
            raise BcfError(
                "No BCF issues to write",
                bcf_path=str(path),
            )

        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                version = ET.Element("Version", {"VersionId": self.BCF_VERSION})
                ET.SubElement(version, "DetailedVersion").text = self.BCF_VERSION
                zf.writestr("bcf.version", _to_bytes(version))

                for issue in issues:
                    self._write_topic(zf, issue)

            logger.info("Wrote {} BCF issues to {}", len(issues), path)
            return path

        except BcfError:
            raise
        except Exception as exc:
            raise BcfError(
                f"Failed to write BCF file: {exc}",
                bcf_path=str(path),
                cause=exc,
            ) from exc

    # ------------------------------------------------------------------
    # Writing helpers
    # ------------------------------------------------------------------

    def _write_topic(self, zf: zipfile.ZipFile, issue: BcfIssue) -> None:
        """Write one topic folder (markup, viewpoint, snapshot)."""
        try:
            uuid.UUID(issue.guid)
        except ValueError:
            logger.warning(
                "BCF 2.1 requires UUID topic guids; writing non-UUID guid {!r}",
                issue.guid,
            )

        has_viewpoint = bool(issue.element_ids) or issue.snapshot is not None
        viewpoint_guid = (
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{issue.guid}/viewpoint"))
            if has_viewpoint
            else None
        )

        folder = issue.guid
        zf.writestr(
            f"{folder}/markup.bcf",
            _to_bytes(self._issue_to_markup(issue, viewpoint_guid)),
        )
        if viewpoint_guid is not None:
            zf.writestr(
                f"{folder}/{_VIEWPOINT_FILE}",
                _to_bytes(self._issue_to_viewpoint(issue, viewpoint_guid)),
            )
        if issue.snapshot is not None:
            zf.writestr(f"{folder}/{_SNAPSHOT_FILE}", issue.snapshot)

    @staticmethod
    def _issue_to_markup(issue: BcfIssue, viewpoint_guid: str | None) -> ET.Element:
        """Serialize a BcfIssue to a BCF 2.1 ``Markup`` element."""
        markup = ET.Element("Markup")

        topic = ET.SubElement(markup, "Topic", {"Guid": issue.guid})
        if issue.status:
            topic.set("TopicStatus", issue.status)

        # Child order follows the Topic sequence in markup.xsd.
        ET.SubElement(topic, "Title").text = issue.title
        ET.SubElement(topic, "CreationDate").text = _iso(issue.creation_date)
        ET.SubElement(topic, "CreationAuthor").text = issue.author
        if issue.assigned_to:
            ET.SubElement(topic, "AssignedTo").text = issue.assigned_to
        if issue.description:
            ET.SubElement(topic, "Description").text = issue.description

        if viewpoint_guid is not None:
            viewpoints = ET.SubElement(markup, "Viewpoints", {"Guid": viewpoint_guid})
            ET.SubElement(viewpoints, "Viewpoint").text = _VIEWPOINT_FILE
            if issue.snapshot is not None:
                ET.SubElement(viewpoints, "Snapshot").text = _SNAPSHOT_FILE

        return markup

    @staticmethod
    def _issue_to_viewpoint(issue: BcfIssue, viewpoint_guid: str) -> ET.Element:
        """Serialize the issue's element selection to a ``VisualizationInfo``."""
        info = ET.Element("VisualizationInfo", {"Guid": viewpoint_guid})
        components = ET.SubElement(info, "Components")

        if issue.element_ids:
            selection = ET.SubElement(components, "Selection")
            for element_id in issue.element_ids:
                value = str(element_id)
                if _IFC_GUID_RE.fullmatch(value):
                    ET.SubElement(selection, "Component", {"IfcGuid": value})
                else:
                    component = ET.SubElement(selection, "Component")
                    ET.SubElement(component, "OriginatingSystem").text = "RevitPy"
                    ET.SubElement(component, "AuthoringToolId").text = value

        # Visibility is mandatory in BCF 2.1 Components.
        ET.SubElement(components, "Visibility", {"DefaultVisibility": "true"})
        return info

    # ------------------------------------------------------------------
    # Reading helpers
    # ------------------------------------------------------------------

    def _read_json(self, path: Path) -> list[BcfIssue]:
        """Read issues from a JSON file."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise BcfError(
                f"Failed to parse BCF JSON file: {exc}",
                bcf_path=str(path),
                cause=exc,
            ) from exc

        issues: list[BcfIssue] = []
        for entry in data:
            issue = BcfIssue(
                guid=entry.get("guid", str(uuid.uuid4())),
                title=entry.get("title", ""),
                description=entry.get("description", ""),
                author=entry.get("author", ""),
                creation_date=_parse_datetime(entry.get("creation_date")),
                status=entry.get("status", "Open"),
                assigned_to=entry.get("assigned_to", ""),
                element_ids=entry.get("element_ids", []),
            )
            issues.append(issue)

        self._issues.extend(issues)
        logger.info("Read {} BCF issues from {}", len(issues), path)
        return issues

    def _read_zip(self, path: Path) -> list[BcfIssue]:
        """Read issues from a BCF ZIP archive."""
        try:
            issues: list[BcfIssue] = []
            with zipfile.ZipFile(path, "r") as zf:
                names = set(zf.namelist())

                if "bcf.version" in names:
                    self._check_version(zf.read("bcf.version"))

                for folder, markup_name in self._topic_markups(names).items():
                    try:
                        root = _parse_xml(zf.read(markup_name))
                    except _XML_ERRORS as exc:
                        logger.warning("Skipping unreadable {}: {}", markup_name, exc)
                        continue
                    issue = self._markup_to_issue(root, zf, folder, names)
                    if issue is not None:
                        issues.append(issue)

            self._issues.extend(issues)
            logger.info("Read {} BCF issues from {}", len(issues), path)
            return issues

        except BcfError:
            raise
        except Exception as exc:
            raise BcfError(
                f"Failed to read BCF ZIP: {exc}",
                bcf_path=str(path),
                cause=exc,
            ) from exc

    @staticmethod
    def _check_version(data: bytes) -> None:
        """Log a warning for BCF versions this reader was not written for."""
        try:
            version_id = _parse_xml(data).get("VersionId")
        except _XML_ERRORS as exc:
            logger.warning("Could not parse bcf.version: {}", exc)
            return
        if version_id not in _SUPPORTED_READ_VERSIONS:
            logger.warning("Unsupported BCF version {!r}; reading anyway", version_id)

    @staticmethod
    def _topic_markups(names: set[str]) -> dict[str, str]:
        """Map topic folder -> markup member, preferring ``markup.bcf``."""
        result: dict[str, str] = {}
        for name in sorted(names):
            if "/" not in name:
                continue
            folder, filename = name.rsplit("/", 1)
            if filename not in _MARKUP_NAMES:
                continue
            if folder not in result or filename == "markup.bcf":
                result[folder] = name
        return result

    @staticmethod
    def _markup_to_issue(
        root: ET.Element,
        zf: zipfile.ZipFile,
        folder: str,
        names: set[str],
    ) -> BcfIssue | None:
        """Build a BcfIssue from a parsed markup plus its topic folder."""
        topic = root.find("Topic")
        if topic is None:
            return None

        status = topic.get("TopicStatus") or _text(topic, "TopicStatus") or "Open"

        element_ids: list[str] = []
        snapshot: bytes | None = None
        # BCF 2.1: Markup/Viewpoints; BCF 3.0: Markup/Topic/Viewpoints/ViewPoint.
        viewpoints = root.find("Viewpoints")
        if viewpoints is None:
            viewpoints = topic.find("Viewpoints/ViewPoint")
        if viewpoints is not None:
            vp_name = f"{folder}/{_text(viewpoints, 'Viewpoint', _VIEWPOINT_FILE)}"
            if vp_name in names:
                try:
                    info = _parse_xml(zf.read(vp_name))
                except _XML_ERRORS as exc:
                    logger.warning("Skipping unreadable viewpoint {}: {}", vp_name, exc)
                else:
                    for component in info.iterfind("Components/Selection/Component"):
                        component_id = component.get("IfcGuid") or _text(
                            component, "AuthoringToolId"
                        )
                        if component_id:
                            element_ids.append(component_id)

            snapshot_file = _text(viewpoints, "Snapshot")
            if snapshot_file and f"{folder}/{snapshot_file}" in names:
                snapshot = zf.read(f"{folder}/{snapshot_file}")

        if not element_ids:
            # Legacy RevitPy archives stored element ids as ReferenceLink.
            element_ids = [
                ref.text for ref in topic.findall("ReferenceLink") if ref.text
            ]

        return BcfIssue(
            guid=topic.get("Guid") or str(uuid.uuid4()),
            title=_text(topic, "Title"),
            description=_text(topic, "Description"),
            author=_text(topic, "CreationAuthor"),
            creation_date=_parse_datetime(_text(topic, "CreationDate")),
            status=status,
            assigned_to=_text(topic, "AssignedTo"),
            element_ids=element_ids,
            snapshot=snapshot,
        )
