"""Package validation and linting system."""

import ast
import re
import tarfile
import zipfile
from pathlib import Path

import toml
from packaging.specifiers import SpecifierSet
from packaging.version import Version


class ValidationError:
    """Represents a validation error or warning."""

    def __init__(
        self,
        level: str,  # error, warning, info
        code: str,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ):
        self.level = level
        self.code = code
        self.message = message
        self.file_path = file_path
        self.line_number = line_number

    def __str__(self) -> str:
        location = ""
        if self.file_path:
            location = f" in {self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"

        return f"{self.level.upper()}: {self.code}: {self.message}{location}"


class PackageValidator:
    """Validates RevitPy packages for quality, security, and compatibility."""

    # Supported Revit versions
    SUPPORTED_REVIT_VERSIONS = ["2021", "2022", "2023", "2024", "2025"]

    # Required files for a RevitPy package
    REQUIRED_FILES = {
        "pyproject.toml": "Package configuration file",
        "README.md": "Package documentation",
    }

    # Recommended files
    RECOMMENDED_FILES = {
        "LICENSE": "License file",
        "CHANGELOG.md": "Changelog file",
        "tests/": "Test directory",
    }

    # Dangerous patterns in Python code
    DANGEROUS_PATTERNS = [
        (
            re.compile(r"\b__import__\s*\("),
            "DANGER_001",
            "Dynamic imports can be dangerous",
        ),
        (re.compile(r"\beval\s*\("), "DANGER_002", "eval() function usage"),
        (re.compile(r"\bexec\s*\("), "DANGER_003", "exec() function usage"),
        (re.compile(r"\bsubprocess\b"), "DANGER_004", "subprocess module usage"),
        (re.compile(r"\bos\.system\b"), "DANGER_005", "os.system() usage"),
        (
            re.compile(r"\bshell\s*=\s*True"),
            "DANGER_006",
            "shell=True in subprocess calls",
        ),
    ]

    def __init__(self):
        self.errors: list[ValidationError] = []

    def validate_package_structure(self, package_path: Path) -> list[ValidationError]:
        """Validate the overall package structure."""
        self.errors = []

        if not package_path.exists():
            self.errors.append(
                ValidationError(
                    "error",
                    "STRUCT_001",
                    f"Package path does not exist: {package_path}",
                )
            )
            return self.errors

        # Check if it's a directory or archive
        if package_path.is_file():
            return self._validate_archive_structure(package_path)
        elif package_path.is_dir():
            return self._validate_directory_structure(package_path)
        else:
            self.errors.append(
                ValidationError(
                    "error",
                    "STRUCT_002",
                    "Package path is neither a file nor directory",
                )
            )

        return self.errors

    def _validate_directory_structure(self, package_dir: Path) -> list[ValidationError]:
        """Validate a package directory structure."""
        # Check for required files
        for required_file, description in self.REQUIRED_FILES.items():
            file_path = package_dir / required_file
            if not file_path.exists():
                self.errors.append(
                    ValidationError(
                        "error",
                        "STRUCT_003",
                        f"Missing required file: {required_file} ({description})",
                    )
                )

        # Check for recommended files
        for recommended_file, description in self.RECOMMENDED_FILES.items():
            file_path = package_dir / recommended_file
            if not file_path.exists():
                self.errors.append(
                    ValidationError(
                        "warning",
                        "STRUCT_004",
                        f"Missing recommended file: {recommended_file} ({description})",
                    )
                )

        # Validate pyproject.toml if it exists
        pyproject_path = package_dir / "pyproject.toml"
        if pyproject_path.exists():
            self._validate_pyproject_toml(pyproject_path)

        # Validate Python files
        self._validate_python_files(package_dir)

        # Check package structure
        self._validate_package_layout(package_dir)

        return self.errors

    def _validate_archive_structure(self, archive_path: Path) -> list[ValidationError]:
        """Validate an archive (tar.gz or zip) package structure."""
        try:
            if archive_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    file_list = zf.namelist()
            elif (
                archive_path.name.endswith(".tar.gz")
                or archive_path.suffix.lower() == ".tar"
            ):
                with tarfile.open(archive_path, "r:*") as tf:
                    file_list = tf.getnames()
            else:
                self.errors.append(
                    ValidationError(
                        "error",
                        "STRUCT_005",
                        "Unsupported archive format. Use .zip or .tar.gz",
                    )
                )
                return self.errors

            # Check for required files in archive
            for required_file, description in self.REQUIRED_FILES.items():
                if not any(f.endswith(required_file) for f in file_list):
                    self.errors.append(
                        ValidationError(
                            "error",
                            "STRUCT_003",
                            f"Missing required file in archive: {required_file} ({description})",
                        )
                    )

            # Check for Python files
            python_files = [f for f in file_list if f.endswith(".py")]
            if not python_files:
                self.errors.append(
                    ValidationError(
                        "warning", "STRUCT_006", "No Python files found in package"
                    )
                )

        except Exception as e:
            self.errors.append(
                ValidationError("error", "STRUCT_007", f"Failed to read archive: {e}")
            )

        return self.errors

    def _validate_pyproject_toml(self, toml_path: Path) -> None:
        """Validate the pyproject.toml file."""
        try:
            with open(toml_path) as f:
                config = toml.load(f)

            # Check for required sections
            if "project" not in config:
                self.errors.append(
                    ValidationError(
                        "error",
                        "TOML_001",
                        "Missing [project] section in pyproject.toml",
                    )
                )
                return

            project = config["project"]

            # Check required fields
            required_fields = ["name", "version", "description"]
            for field in required_fields:
                if field not in project:
                    self.errors.append(
                        ValidationError(
                            "error",
                            "TOML_002",
                            f"Missing required field '{field}' in [project] section",
                        )
                    )

            # Validate version format
            if "version" in project:
                try:
                    Version(project["version"])
                except Exception:
                    self.errors.append(
                        ValidationError(
                            "error",
                            "TOML_003",
                            f"Invalid version format: {project['version']}",
                        )
                    )

            # Check for RevitPy-specific metadata
            if "revitpy" in config:
                self._validate_revitpy_metadata(config["revitpy"])
            else:
                self.errors.append(
                    ValidationError(
                        "warning",
                        "TOML_004",
                        "Missing [revitpy] section with RevitPy-specific metadata",
                    )
                )

            # Validate dependencies
            if "dependencies" in project:
                self._validate_dependencies(project["dependencies"])

        except toml.TomlDecodeError as e:
            self.errors.append(
                ValidationError("error", "TOML_005", f"Invalid TOML syntax: {e}")
            )
        except Exception as e:
            self.errors.append(
                ValidationError(
                    "error", "TOML_006", f"Error reading pyproject.toml: {e}"
                )
            )

    def _validate_revitpy_metadata(self, revitpy_config: dict) -> None:
        """Validate RevitPy-specific metadata."""
        # Check supported Revit versions
        if "supported_revit_versions" in revitpy_config:
            versions = revitpy_config["supported_revit_versions"]
            if not isinstance(versions, list):
                self.errors.append(
                    ValidationError(
                        "error", "REVIT_001", "supported_revit_versions must be a list"
                    )
                )
            else:
                for version in versions:
                    if version not in self.SUPPORTED_REVIT_VERSIONS:
                        self.errors.append(
                            ValidationError(
                                "warning",
                                "REVIT_002",
                                f"Unsupported Revit version: {version}",
                            )
                        )

        # Check entry points
        if "entry_points" in revitpy_config:
            entry_points = revitpy_config["entry_points"]
            if not isinstance(entry_points, dict):
                self.errors.append(
                    ValidationError(
                        "error", "REVIT_003", "entry_points must be a dictionary"
                    )
                )

        # Check minimum Python version
        if "python_version" in revitpy_config:
            try:
                python_ver = revitpy_config["python_version"]
                SpecifierSet(python_ver)

                # Warn if not Python 3.11+
                if not any(
                    Version("3.11.0") in SpecifierSet(spec) for spec in [python_ver]
                ):
                    self.errors.append(
                        ValidationError(
                            "warning",
                            "REVIT_004",
                            "Consider supporting Python 3.11+ for best RevitPy compatibility",
                        )
                    )
            except Exception:
                self.errors.append(
                    ValidationError(
                        "error",
                        "REVIT_005",
                        f"Invalid python_version specifier: {revitpy_config['python_version']}",
                    )
                )

    def _validate_dependencies(self, dependencies: list[str]) -> None:
        """Validate package dependencies."""
        for dep in dependencies:
            try:
                # Basic validation - more sophisticated parsing could be added
                if not re.match(
                    r"^[a-zA-Z0-9_.-]+([<>=!~]+[0-9a-zA-Z._-]+)?$", dep.strip()
                ):
                    self.errors.append(
                        ValidationError(
                            "warning",
                            "DEP_001",
                            f"Potentially invalid dependency format: {dep}",
                        )
                    )
            except Exception:
                self.errors.append(
                    ValidationError(
                        "error", "DEP_002", f"Error parsing dependency: {dep}"
                    )
                )

    def _validate_python_files(self, package_dir: Path) -> None:
        """Validate Python files in the package."""
        python_files = list(package_dir.rglob("*.py"))

        if not python_files:
            self.errors.append(
                ValidationError("warning", "PY_001", "No Python files found in package")
            )
            return

        for py_file in python_files:
            self._validate_python_file(py_file)

    def _validate_python_file(self, py_file: Path) -> None:
        """Validate a single Python file."""
        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()

            # Try to parse the Python code
            try:
                ast.parse(content)
            except SyntaxError as e:
                self.errors.append(
                    ValidationError(
                        "error",
                        "PY_002",
                        f"Syntax error: {e}",
                        file_path=str(py_file),
                        line_number=e.lineno,
                    )
                )
                return

            # Check for dangerous patterns
            lines = content.splitlines()
            for line_num, line in enumerate(lines, 1):
                for pattern, code, message in self.DANGEROUS_PATTERNS:
                    if pattern.search(line):
                        self.errors.append(
                            ValidationError(
                                "warning",
                                code,
                                message,
                                file_path=str(py_file),
                                line_number=line_num,
                            )
                        )

            # Check for common issues
            self._check_python_code_quality(py_file, content)

        except UnicodeDecodeError:
            self.errors.append(
                ValidationError(
                    "error", "PY_003", "File is not valid UTF-8", file_path=str(py_file)
                )
            )
        except Exception as e:
            self.errors.append(
                ValidationError(
                    "error",
                    "PY_004",
                    f"Error reading file: {e}",
                    file_path=str(py_file),
                )
            )

    def _check_python_code_quality(self, py_file: Path, content: str) -> None:
        """Check Python code quality issues."""
        lines = content.splitlines()

        for line_num, line in enumerate(lines, 1):
            stripped_line = line.strip()

            # Check for TODO/FIXME comments
            if any(
                keyword in line.upper() for keyword in ["TODO", "FIXME", "HACK", "BUG"]
            ):
                self.errors.append(
                    ValidationError(
                        "info",
                        "QUALITY_001",
                        f"Found TODO/FIXME comment: {stripped_line}",
                        file_path=str(py_file),
                        line_number=line_num,
                    )
                )

            # Check for print statements (debugging)
            if re.search(r"\bprint\s*\(", line):
                self.errors.append(
                    ValidationError(
                        "warning",
                        "QUALITY_002",
                        "Print statement found (consider using logging)",
                        file_path=str(py_file),
                        line_number=line_num,
                    )
                )

            # Check for long lines
            if len(line) > 120:
                self.errors.append(
                    ValidationError(
                        "warning",
                        "QUALITY_003",
                        f"Line too long ({len(line)} characters)",
                        file_path=str(py_file),
                        line_number=line_num,
                    )
                )

    def _validate_package_layout(self, package_dir: Path) -> None:
        """Validate the package layout and structure."""
        # Look for main package directory
        py_files = list(package_dir.rglob("*.py"))
        if not py_files:
            return

        # Check if there's an __init__.py file
        init_files = list(package_dir.rglob("__init__.py"))
        if not init_files:
            self.errors.append(
                ValidationError(
                    "warning",
                    "LAYOUT_001",
                    "No __init__.py files found - package may not be importable",
                )
            )

        # Check for common directory structure issues
        src_dirs = [
            d for d in package_dir.iterdir() if d.is_dir() and d.name in ["src", "lib"]
        ]
        if len(src_dirs) > 1:
            self.errors.append(
                ValidationError(
                    "warning",
                    "LAYOUT_002",
                    "Multiple source directories found (src, lib) - may cause confusion",
                )
            )

        # Check for tests
        test_indicators = ["test", "tests", "testing"]
        has_tests = any(
            any(indicator in part.lower() for indicator in test_indicators)
            for part in package_dir.rglob("*")
            if part.is_dir() or (part.is_file() and part.suffix == ".py")
        )

        if not has_tests:
            self.errors.append(
                ValidationError(
                    "warning", "LAYOUT_003", "No test files or directories found"
                )
            )


class PackageLinter:
    """Advanced linting for RevitPy packages."""

    def __init__(self):
        self.validator = PackageValidator()

    def lint_package(
        self, package_path: Path, strict: bool = False, include_info: bool = False
    ) -> tuple[list[ValidationError], bool]:
        """Lint a package and return errors and success status.

        Args:
            package_path: Path to package directory or archive
            strict: If True, treat warnings as errors
            include_info: If True, include informational messages

        Returns:
            Tuple of (errors_list, success_status)
        """
        errors = self.validator.validate_package_structure(package_path)

        # Filter errors based on options
        if not include_info:
            errors = [e for e in errors if e.level != "info"]

        # Determine success
        has_errors = any(e.level == "error" for e in errors)
        has_warnings = any(e.level == "warning" for e in errors)

        success = not has_errors and (not strict or not has_warnings)

        return errors, success

    def generate_report(self, errors: list[ValidationError], package_path: Path) -> str:
        """Generate a human-readable validation report."""
        lines = ["Package Validation Report", f"Package: {package_path}", "=" * 50, ""]

        if not errors:
            lines.append("✅ No issues found!")
            return "\n".join(lines)

        # Group errors by level
        error_count = len([e for e in errors if e.level == "error"])
        warning_count = len([e for e in errors if e.level == "warning"])
        info_count = len([e for e in errors if e.level == "info"])

        lines.append(
            f"Summary: {error_count} errors, {warning_count} warnings, {info_count} info"
        )
        lines.append("")

        # Group by level
        for level in ["error", "warning", "info"]:
            level_errors = [e for e in errors if e.level == level]
            if not level_errors:
                continue

            lines.append(f"{level.upper()}S:")
            for error in level_errors:
                lines.append(f"  {error}")
            lines.append("")

        return "\n".join(lines)
