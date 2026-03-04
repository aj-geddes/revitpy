"""
Tests for the CI/CD configuration generator module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from revitpy.cloud.ci import CIHelper


class TestCIHelper:
    """Tests for CIHelper."""

    def test_generate_github_workflow_valid_yaml(self):
        """Generated GitHub workflow should be valid YAML."""
        helper = CIHelper()
        content = helper.generate_github_workflow()
        parsed = yaml.safe_load(content)

        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "jobs" in parsed

    def test_generate_github_workflow_default_values(self):
        """Default GitHub workflow should use sensible defaults."""
        helper = CIHelper()
        content = helper.generate_github_workflow()
        parsed = yaml.safe_load(content)

        assert parsed["name"] == "revitpy-validation"
        assert "validate" in parsed["jobs"]

        validate_job = parsed["jobs"]["validate"]
        assert validate_job["runs-on"] == "ubuntu-latest"

    def test_generate_github_workflow_custom_values(self):
        """GitHub workflow should accept custom parameter values."""
        helper = CIHelper()
        content = helper.generate_github_workflow(
            name="custom-validation",
            script_path="scripts/validate.py",
            revit_version="2025",
            branches="main, develop",
            runner="self-hosted",
            python_version="3.12",
        )
        parsed = yaml.safe_load(content)

        assert parsed["name"] == "custom-validation"

    def test_generate_github_workflow_contains_secrets(self):
        """GitHub workflow should reference APS secrets."""
        helper = CIHelper()
        content = helper.generate_github_workflow()

        assert "APS_CLIENT_ID" in content
        assert "APS_CLIENT_SECRET" in content
        assert "secrets." in content

    def test_generate_github_workflow_has_python_setup(self):
        """GitHub workflow should include Python setup step."""
        helper = CIHelper()
        content = helper.generate_github_workflow()

        assert "actions/setup-python" in content
        assert "pip install" in content

    def test_generate_gitlab_ci_valid_yaml(self):
        """Generated GitLab CI should be valid YAML."""
        helper = CIHelper()
        content = helper.generate_gitlab_ci()
        parsed = yaml.safe_load(content)

        assert isinstance(parsed, dict)
        assert "stages" in parsed

    def test_generate_gitlab_ci_default_values(self):
        """Default GitLab CI should use sensible defaults."""
        helper = CIHelper()
        content = helper.generate_gitlab_ci()
        parsed = yaml.safe_load(content)

        assert "validate" in parsed["stages"]
        assert "revitpy-validation" in parsed

    def test_generate_gitlab_ci_custom_values(self):
        """GitLab CI should accept custom parameter values."""
        helper = CIHelper()
        content = helper.generate_gitlab_ci(
            name="my-validation",
            script_path="ci/validate.py",
            revit_version="2025",
            python_version="3.12",
        )
        parsed = yaml.safe_load(content)

        assert "my-validation" in parsed

    def test_generate_gitlab_ci_contains_variables(self):
        """GitLab CI should reference APS CI/CD variables."""
        helper = CIHelper()
        content = helper.generate_gitlab_ci()

        assert "APS_CLIENT_ID" in content
        assert "APS_CLIENT_SECRET" in content

    def test_generate_gitlab_ci_has_pip_install(self):
        """GitLab CI should include pip install step."""
        helper = CIHelper()
        content = helper.generate_gitlab_ci()

        assert "pip install" in content

    def test_save_workflow_creates_file(self, tmp_output_dir):
        """save_workflow() should write content to disk."""
        helper = CIHelper()
        content = helper.generate_github_workflow()

        output_path = tmp_output_dir / ".github" / "workflows" / "validate.yml"
        result = helper.save_workflow(content, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_text() == content

    def test_save_workflow_creates_parent_dirs(self, tmp_output_dir):
        """save_workflow() should create parent directories."""
        helper = CIHelper()
        output_path = tmp_output_dir / "nested" / "dir" / "ci.yml"
        helper.save_workflow("content: true", output_path)

        assert output_path.exists()

    def test_save_workflow_returns_path(self, tmp_output_dir):
        """save_workflow() should return the resolved Path."""
        helper = CIHelper()
        output_path = tmp_output_dir / "workflow.yml"
        result = helper.save_workflow("test", output_path)

        assert isinstance(result, Path)
