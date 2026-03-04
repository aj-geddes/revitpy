"""
BCF (BIM Collaboration Format) manager for RevitPy.

This module provides the BcfManager class for creating, reading, and
writing BCF issues, supporting simplified XML serialization within ZIP
archives.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree as ET  # noqa: N817

from loguru import logger

from .exceptions import BcfError
from .types import BcfIssue


class BcfManager:
    """Manage BCF issues: create, read, and write.

    Provides a simplified BCF 2.1 compatible workflow for creating
    issues, serializing them to BCF ZIP files, and reading them back.
    """

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
            guid=str(uuid4()),
            title=title,
            description=description,
            author=author,
            creation_date=datetime.now(),
            status=status,
            assigned_to=assigned_to,
            element_ids=element_ids or [],
        )
        self._issues.append(issue)
        logger.debug("Created BCF issue: {} ({})", title, issue.guid)
        return issue

    def read_bcf(self, path: str | Path) -> list[BcfIssue]:
        """Read BCF issues from a file.

        Supports ``.bcf`` / ``.bcfzip`` ZIP archives containing
        ``markup.xml`` per topic, and ``.json`` files as a simplified
        alternative.

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
        """Write BCF issues to a file.

        Creates a BCF ZIP archive containing an XML ``markup.xml`` for
        each issue.

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
                for issue in issues:
                    markup = self._issue_to_xml(issue)
                    topic_dir = issue.guid
                    zf.writestr(
                        f"{topic_dir}/markup.xml",
                        ET.tostring(markup, encoding="unicode"),
                    )

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
    # Internal helpers
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
                guid=entry.get("guid", str(uuid4())),
                title=entry.get("title", ""),
                description=entry.get("description", ""),
                author=entry.get("author", ""),
                creation_date=datetime.fromisoformat(entry["creation_date"])
                if "creation_date" in entry
                else datetime.now(),
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
                for name in zf.namelist():
                    if name.endswith("markup.xml"):
                        xml_data = zf.read(name).decode("utf-8")
                        issue = self._xml_to_issue(xml_data)
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
    def _issue_to_xml(issue: BcfIssue) -> ET.Element:
        """Serialize a BcfIssue to an XML Element."""
        markup = ET.Element("Markup")

        topic = ET.SubElement(markup, "Topic")
        topic.set("Guid", issue.guid)

        title_el = ET.SubElement(topic, "Title")
        title_el.text = issue.title

        desc_el = ET.SubElement(topic, "Description")
        desc_el.text = issue.description

        author_el = ET.SubElement(topic, "CreationAuthor")
        author_el.text = issue.author

        date_el = ET.SubElement(topic, "CreationDate")
        date_el.text = issue.creation_date.isoformat()

        status_el = ET.SubElement(topic, "TopicStatus")
        status_el.text = issue.status

        if issue.assigned_to:
            assigned_el = ET.SubElement(topic, "AssignedTo")
            assigned_el.text = issue.assigned_to

        for eid in issue.element_ids:
            ref = ET.SubElement(topic, "ReferenceLink")
            ref.text = str(eid)

        return markup

    @staticmethod
    def _xml_to_issue(xml_data: str) -> BcfIssue | None:
        """Deserialize a BcfIssue from XML string."""
        try:
            root = ET.fromstring(xml_data)  # noqa: S314
        except ET.ParseError:
            return None

        topic = root.find("Topic")
        if topic is None:
            return None

        guid = topic.get("Guid", str(uuid4()))
        title = _text(topic, "Title")
        description = _text(topic, "Description")
        author = _text(topic, "CreationAuthor")
        status = _text(topic, "TopicStatus", "Open")
        assigned_to = _text(topic, "AssignedTo")

        date_str = _text(topic, "CreationDate")
        try:
            creation_date = (
                datetime.fromisoformat(date_str) if date_str else datetime.now()
            )
        except ValueError:
            creation_date = datetime.now()

        element_ids = [ref.text for ref in topic.findall("ReferenceLink") if ref.text]

        return BcfIssue(
            guid=guid,
            title=title,
            description=description,
            author=author,
            creation_date=creation_date,
            status=status,
            assigned_to=assigned_to,
            element_ids=element_ids,
        )


def _text(parent: ET.Element, tag: str, default: str = "") -> str:
    """Extract text from a child element safely."""
    child = parent.find(tag)
    if child is not None and child.text:
        return child.text
    return default
