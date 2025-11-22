"""Template management utilities."""

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml
from rich.console import Console

from ..core.config import get_config
from ..core.exceptions import TemplateError
from ..core.logging import get_logger
from .git import clone_repository, is_git_url

logger = get_logger(__name__)
console = Console()


@dataclass
class TemplateInfo:
    """Information about a template."""

    name: str
    description: str
    type: str
    source: str
    path: Path | None = None
    version: str | None = None


class TemplateManager:
    """Manages project templates for RevitPy CLI."""

    def __init__(self) -> None:
        """Initialize template manager."""
        self.config = get_config()
        self.cache_dir = Path(
            self.config.template.template_cache_dir
            or (self.config.cache_dir / "templates")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> list[TemplateInfo]:
        """List all available templates.

        Returns:
            List of template information
        """
        templates = []

        # Built-in templates
        builtin_templates = self._get_builtin_templates()
        templates.extend(builtin_templates)

        # Cached templates
        cached_templates = self._get_cached_templates()
        templates.extend(cached_templates)

        return templates

    def get_template(self, name: str) -> Path:
        """Get template by name.

        Args:
            name: Template name

        Returns:
            Path to template directory

        Raises:
            TemplateError: If template not found or invalid
        """
        # Check built-in templates first
        builtin_path = self._get_builtin_template_path(name)
        if builtin_path and builtin_path.exists():
            return builtin_path

        # Check cached templates
        cached_path = self.cache_dir / name
        if cached_path.exists():
            return cached_path

        # Try to download from template sources
        for source in self.config.template.template_sources:
            try:
                template_path = self._download_template(name, source)
                if template_path:
                    return template_path
            except Exception as e:
                logger.debug(f"Failed to download template {name} from {source}: {e}")

        raise TemplateError(name, "Template not found")

    def add_template(
        self, source: str, name: str | None = None, update: bool = False
    ) -> None:
        """Add a template from a source.

        Args:
            source: Template source (URL or path)
            name: Optional custom name for the template
            update: Whether to update existing template

        Raises:
            TemplateError: If template addition fails
        """
        if not name:
            # Extract name from source
            if is_git_url(source):
                name = Path(urlparse(source).path).stem.replace(".git", "")
            else:
                name = Path(source).name

        template_dir = self.cache_dir / name

        if template_dir.exists() and not update:
            raise TemplateError(
                name, "Template already exists (use --update to overwrite)"
            )

        try:
            if template_dir.exists():
                shutil.rmtree(template_dir)

            if is_git_url(source):
                # Clone git repository
                clone_repository(source, template_dir)
            elif Path(source).exists():
                # Copy local directory
                shutil.copytree(source, template_dir)
            else:
                raise TemplateError(name, f"Invalid template source: {source}")

            # Validate template
            self._validate_template(template_dir)

            logger.info(f"Added template '{name}' from {source}")

        except Exception as e:
            if template_dir.exists():
                shutil.rmtree(template_dir)
            raise TemplateError(name, f"Failed to add template: {e}") from e

    def remove_template(self, name: str) -> None:
        """Remove a cached template.

        Args:
            name: Template name to remove

        Raises:
            TemplateError: If template removal fails
        """
        template_dir = self.cache_dir / name

        if not template_dir.exists():
            raise TemplateError(name, "Template not found in cache")

        try:
            shutil.rmtree(template_dir)
            logger.info(f"Removed template '{name}'")
        except Exception as e:
            raise TemplateError(name, f"Failed to remove template: {e}") from e

    def _get_builtin_templates(self) -> list[TemplateInfo]:
        """Get list of built-in templates.

        Returns:
            List of built-in template information
        """
        builtin_dir = Path(__file__).parent.parent / "templates"
        if not builtin_dir.exists():
            return []

        templates = []
        for template_dir in builtin_dir.iterdir():
            if template_dir.is_dir():
                info = self._load_template_info(template_dir)
                if info:
                    info.source = "built-in"
                    templates.append(info)

        return templates

    def _get_cached_templates(self) -> list[TemplateInfo]:
        """Get list of cached templates.

        Returns:
            List of cached template information
        """
        templates = []
        for template_dir in self.cache_dir.iterdir():
            if template_dir.is_dir():
                info = self._load_template_info(template_dir)
                if info:
                    info.source = "cached"
                    templates.append(info)

        return templates

    def _get_builtin_template_path(self, name: str) -> Path | None:
        """Get path to built-in template.

        Args:
            name: Template name

        Returns:
            Path to template or None if not found
        """
        builtin_dir = Path(__file__).parent.parent / "templates"
        template_path = builtin_dir / name

        if template_path.exists() and template_path.is_dir():
            return template_path

        return None

    def _download_template(self, name: str, source: str) -> Path | None:
        """Download template from source.

        Args:
            name: Template name
            source: Template source URL

        Returns:
            Path to downloaded template or None if not found
        """
        if not is_git_url(source):
            return None

        # Try to clone the entire template repository
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                temp_path = Path(temp_dir)
                clone_repository(source, temp_path / "repo")

                repo_path = temp_path / "repo"

                # Look for template by name in the repository
                possible_paths = [
                    repo_path / name,
                    repo_path / "templates" / name,
                    repo_path,  # Entire repo is the template
                ]

                for template_path in possible_paths:
                    if template_path.exists() and self._is_valid_template(
                        template_path
                    ):
                        # Copy to cache
                        cache_path = self.cache_dir / name
                        if cache_path.exists():
                            shutil.rmtree(cache_path)
                        shutil.copytree(template_path, cache_path)
                        return cache_path

            except Exception as e:
                logger.debug(f"Failed to download template from {source}: {e}")

        return None

    def _load_template_info(self, template_path: Path) -> TemplateInfo | None:
        """Load template information from directory.

        Args:
            template_path: Path to template directory

        Returns:
            Template information or None if invalid
        """
        if not self._is_valid_template(template_path):
            return None

        # Try to load template metadata
        metadata_files = [
            template_path / "template.yaml",
            template_path / "template.yml",
            template_path / "cookiecutter.json",
            template_path / ".template.yaml",
        ]

        name = template_path.name
        description = "RevitPy project template"
        template_type = "basic"
        version = None

        for metadata_file in metadata_files:
            if metadata_file.exists():
                try:
                    if metadata_file.suffix in (".yaml", ".yml"):
                        with open(metadata_file) as f:
                            data = yaml.safe_load(f)
                    else:  # JSON
                        with open(metadata_file) as f:
                            data = json.load(f)

                    if isinstance(data, dict):
                        name = data.get("name", name)
                        description = data.get("description", description)
                        template_type = data.get("type", template_type)
                        version = data.get("version", version)
                        break
                except Exception as e:
                    logger.debug(
                        f"Failed to load template metadata from {metadata_file}: {e}"
                    )

        return TemplateInfo(
            name=name,
            description=description,
            type=template_type,
            source="",
            path=template_path,
            version=version,
        )

    def _is_valid_template(self, path: Path) -> bool:
        """Check if path contains a valid template.

        Args:
            path: Path to check

        Returns:
            True if path contains a valid template
        """
        if not path.is_dir():
            return False

        # Check for template indicators
        indicators = [
            "cookiecutter.json",
            "{{cookiecutter.project_name}}",
            "template.yaml",
            "template.yml",
            ".template.yaml",
        ]

        for indicator in indicators:
            if (path / indicator).exists():
                return True

            # Check for cookiecutter-style directory
            for item in path.iterdir():
                if item.is_dir() and item.name.startswith("{{"):
                    return True

        # Check if it looks like a Python project template
        python_indicators = [
            "setup.py",
            "pyproject.toml",
            "requirements.txt",
        ]

        if any((path / indicator).exists() for indicator in python_indicators):
            return True

        return False

    def _validate_template(self, template_path: Path) -> None:
        """Validate template structure.

        Args:
            template_path: Path to template directory

        Raises:
            TemplateError: If template is invalid
        """
        if not self._is_valid_template(template_path):
            raise TemplateError(template_path.name, "Invalid template structure")

        # Additional validation can be added here
        # For example, check required files, validate cookiecutter.json, etc.
