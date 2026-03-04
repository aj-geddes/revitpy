"""
CI/CD configuration generators for RevitPy cloud workflows.

This module generates GitHub Actions and GitLab CI pipeline YAML files
that automate Revit model validation using Design Automation jobs.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from loguru import logger

_GITHUB_TEMPLATE = dedent("""\
    name: {name}

    on:
      push:
        branches: [{branches}]
      pull_request:
        branches: [{branches}]

    jobs:
      validate:
        runs-on: {runner}
        steps:
          - uses: actions/checkout@v4

          - name: Set up Python
            uses: actions/setup-python@v5
            with:
              python-version: "{python_version}"

          - name: Install dependencies
            run: |
              python -m pip install --upgrade pip
              pip install revitpy[cloud]

          - name: Run Revit validation
            env:
              APS_CLIENT_ID: ${{{{ secrets.APS_CLIENT_ID }}}}
              APS_CLIENT_SECRET: ${{{{ secrets.APS_CLIENT_SECRET }}}}
              REVIT_VERSION: "{revit_version}"
            run: |
              python {script_path}
""")

_GITLAB_TEMPLATE = dedent("""\
    stages:
      - validate

    {name}:
      stage: validate
      image: python:{python_version}-slim
      variables:
        APS_CLIENT_ID: $APS_CLIENT_ID
        APS_CLIENT_SECRET: $APS_CLIENT_SECRET
        REVIT_VERSION: "{revit_version}"
      before_script:
        - pip install revitpy[cloud]
      script:
        - python {script_path}
      rules:
        - if: $CI_PIPELINE_SOURCE == "merge_request_event"
        - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
""")


class CIHelper:
    """Generates CI/CD pipeline configurations for RevitPy workflows."""

    def __init__(self) -> None:
        pass

    def generate_github_workflow(
        self,
        name: str = "revitpy-validation",
        script_path: str = "validate.py",
        revit_version: str = "2024",
        *,
        branches: str = "main",
        runner: str = "ubuntu-latest",
        python_version: str = "3.11",
    ) -> str:
        """Generate a GitHub Actions workflow YAML string.

        Args:
            name: Workflow name.
            script_path: Path to the validation script.
            revit_version: Target Revit version.
            branches: Comma-separated branch triggers.
            runner: GitHub Actions runner label.
            python_version: Python version to use.

        Returns:
            Complete GitHub Actions YAML as a string.
        """
        return _GITHUB_TEMPLATE.format(
            name=name,
            script_path=script_path,
            revit_version=revit_version,
            branches=branches,
            runner=runner,
            python_version=python_version,
        )

    def generate_gitlab_ci(
        self,
        name: str = "revitpy-validation",
        script_path: str = "validate.py",
        revit_version: str = "2024",
        *,
        python_version: str = "3.11",
    ) -> str:
        """Generate a GitLab CI pipeline YAML string.

        Args:
            name: Job name.
            script_path: Path to the validation script.
            revit_version: Target Revit version.
            python_version: Python version for the Docker image.

        Returns:
            Complete GitLab CI YAML as a string.
        """
        return _GITLAB_TEMPLATE.format(
            name=name,
            script_path=script_path,
            revit_version=revit_version,
            python_version=python_version,
        )

    def save_workflow(
        self,
        content: str,
        output_path: str | Path,
    ) -> Path:
        """Write a workflow/pipeline configuration to disk.

        Args:
            content: YAML content string.
            output_path: Destination file path.

        Returns:
            Resolved ``Path`` of the written file.
        """
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        logger.info("Saved CI config to {}", dest)
        return dest
