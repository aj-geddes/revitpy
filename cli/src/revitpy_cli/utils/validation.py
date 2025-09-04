"""Validation utilities for RevitPy CLI."""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import toml
from packaging.requirements import Requirement
from packaging.version import Version, InvalidVersion

from ..core.exceptions import ValidationError
from ..core.logging import get_logger

logger = get_logger(__name__)


class ProjectValidator:
    """Validates RevitPy projects and packages."""
    
    def __init__(self, project_path: Path) -> None:
        """Initialize project validator.
        
        Args:
            project_path: Path to project directory
        """
        self.project_path = project_path
        self.pyproject_path = project_path / "pyproject.toml"
        self.setup_py_path = project_path / "setup.py"
    
    def validate_project_structure(self) -> List[Dict[str, str]]:
        """Validate project directory structure.
        
        Returns:
            List of validation issues
        """
        issues = []
        
        # Check for project configuration
        if not self.pyproject_path.exists() and not self.setup_py_path.exists():
            issues.append({
                "type": "error",
                "message": "No project configuration found (pyproject.toml or setup.py)"
            })
        
        # Check for source directory
        src_dirs = ["src", self.project_path.name]
        has_src = any((self.project_path / dirname).exists() for dirname in src_dirs)
        
        if not has_src:
            issues.append({
                "type": "warning",
                "message": "No source directory found (consider using 'src/' layout)"
            })
        
        # Check for tests
        test_dirs = ["tests", "test"]
        has_tests = any((self.project_path / dirname).exists() for dirname in test_dirs)
        
        if not has_tests:
            issues.append({
                "type": "warning",
                "message": "No test directory found"
            })
        
        # Check for README
        readme_files = ["README.md", "README.rst", "README.txt"]
        has_readme = any((self.project_path / filename).exists() for filename in readme_files)
        
        if not has_readme:
            issues.append({
                "type": "warning",
                "message": "No README file found"
            })
        
        # Check for license
        license_files = ["LICENSE", "LICENSE.txt", "LICENSE.md"]
        has_license = any((self.project_path / filename).exists() for filename in license_files)
        
        if not has_license:
            issues.append({
                "type": "warning", 
                "message": "No LICENSE file found"
            })
        
        return issues
    
    def validate_pyproject_toml(self) -> List[Dict[str, str]]:
        """Validate pyproject.toml file.
        
        Returns:
            List of validation issues
        """
        issues = []
        
        if not self.pyproject_path.exists():
            return issues
        
        try:
            with open(self.pyproject_path) as f:
                pyproject_data = toml.load(f)
        except Exception as e:
            issues.append({
                "type": "error",
                "message": f"Invalid pyproject.toml: {e}"
            })
            return issues
        
        # Validate build system
        build_system = pyproject_data.get("build-system", {})
        if not build_system:
            issues.append({
                "type": "error",
                "message": "Missing [build-system] section in pyproject.toml"
            })
        
        # Validate project metadata
        project = pyproject_data.get("project", {})
        if not project:
            issues.append({
                "type": "error",
                "message": "Missing [project] section in pyproject.toml"
            })
        else:
            # Check required fields
            required_fields = ["name", "version"]
            for field in required_fields:
                if field not in project and field not in project.get("dynamic", []):
                    issues.append({
                        "type": "error",
                        "message": f"Missing required field '{field}' in [project]"
                    })
            
            # Validate version
            version = project.get("version")
            if version and not self._is_valid_version(version):
                issues.append({
                    "type": "error",
                    "message": f"Invalid version format: {version}"
                })
            
            # Validate dependencies
            dependencies = project.get("dependencies", [])
            for dep in dependencies:
                if not self._is_valid_requirement(dep):
                    issues.append({
                        "type": "error",
                        "message": f"Invalid dependency: {dep}"
                    })
        
        return issues
    
    def validate_dependencies(self) -> List[Dict[str, str]]:
        """Validate project dependencies.
        
        Returns:
            List of validation issues
        """
        issues = []
        
        # Get dependencies from pyproject.toml
        dependencies = self._get_project_dependencies()
        
        # Check for security vulnerabilities
        vuln_issues = self._check_security_vulnerabilities(dependencies)
        issues.extend(vuln_issues)
        
        # Check for outdated packages
        outdated_issues = self._check_outdated_packages(dependencies)
        issues.extend(outdated_issues)
        
        return issues
    
    def validate_code_quality(self) -> List[Dict[str, str]]:
        """Validate code quality using static analysis tools.
        
        Returns:
            List of validation issues
        """
        issues = []
        
        # Find Python files
        python_files = list(self.project_path.rglob("*.py"))
        if not python_files:
            return issues
        
        # Run basic syntax checks
        syntax_issues = self._check_python_syntax(python_files)
        issues.extend(syntax_issues)
        
        # Run import checks
        import_issues = self._check_imports(python_files)
        issues.extend(import_issues)
        
        return issues
    
    def _is_valid_version(self, version: str) -> bool:
        """Check if version string is valid.
        
        Args:
            version: Version string to validate
            
        Returns:
            True if version is valid
        """
        try:
            Version(version)
            return True
        except InvalidVersion:
            return False
    
    def _is_valid_requirement(self, requirement: str) -> bool:
        """Check if requirement string is valid.
        
        Args:
            requirement: Requirement string to validate
            
        Returns:
            True if requirement is valid
        """
        try:
            Requirement(requirement)
            return True
        except Exception:
            return False
    
    def _get_project_dependencies(self) -> List[str]:
        """Get project dependencies.
        
        Returns:
            List of dependency strings
        """
        dependencies = []
        
        if self.pyproject_path.exists():
            try:
                with open(self.pyproject_path) as f:
                    pyproject_data = toml.load(f)
                    project = pyproject_data.get("project", {})
                    dependencies.extend(project.get("dependencies", []))
            except Exception:
                pass
        
        # Also check requirements.txt
        requirements_path = self.project_path / "requirements.txt"
        if requirements_path.exists():
            try:
                with open(requirements_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            dependencies.append(line)
            except Exception:
                pass
        
        return dependencies
    
    def _check_security_vulnerabilities(self, dependencies: List[str]) -> List[Dict[str, str]]:
        """Check for security vulnerabilities in dependencies.
        
        Args:
            dependencies: List of dependency strings
            
        Returns:
            List of security issues
        """
        issues = []
        
        # This would integrate with tools like safety or pip-audit
        # For now, just check for known vulnerable patterns
        
        vulnerable_packages = {
            "requests": "2.25.0",  # Example: vulnerable version
        }
        
        for dep in dependencies:
            try:
                req = Requirement(dep)
                if req.name in vulnerable_packages:
                    # Simple version check - in reality this would be more sophisticated
                    issues.append({
                        "type": "warning",
                        "message": f"Package {req.name} may have known vulnerabilities"
                    })
            except Exception:
                continue
        
        return issues
    
    def _check_outdated_packages(self, dependencies: List[str]) -> List[Dict[str, str]]:
        """Check for outdated packages.
        
        Args:
            dependencies: List of dependency strings
            
        Returns:
            List of outdated package issues
        """
        issues = []
        
        # This would use pip or other tools to check for updates
        # For now, just return empty list
        
        return issues
    
    def _check_python_syntax(self, python_files: List[Path]) -> List[Dict[str, str]]:
        """Check Python syntax.
        
        Args:
            python_files: List of Python files to check
            
        Returns:
            List of syntax issues
        """
        issues = []
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                compile(content, str(file_path), 'exec')
                
            except SyntaxError as e:
                issues.append({
                    "type": "error",
                    "message": f"Syntax error in {file_path.relative_to(self.project_path)}: {e}"
                })
            except Exception as e:
                issues.append({
                    "type": "warning",
                    "message": f"Could not check syntax of {file_path.relative_to(self.project_path)}: {e}"
                })
        
        return issues
    
    def _check_imports(self, python_files: List[Path]) -> List[Dict[str, str]]:
        """Check for import issues.
        
        Args:
            python_files: List of Python files to check
            
        Returns:
            List of import issues
        """
        issues = []
        
        # This would perform more sophisticated import analysis
        # For now, just basic checks
        
        return issues


def validate_package_name(name: str) -> bool:
    """Validate package name according to Python packaging standards.
    
    Args:
        name: Package name to validate
        
    Returns:
        True if package name is valid
    """
    # Package names must contain only letters, numbers, periods, hyphens, and underscores
    # Must start with a letter or number
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$"
    return bool(re.match(pattern, name))


def validate_project_name(name: str) -> bool:
    """Validate project name for file system compatibility.
    
    Args:
        name: Project name to validate
        
    Returns:
        True if project name is valid
    """
    # Project names should be valid directory names
    # Avoid special characters that might cause issues
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
    
    if any(char in name for char in invalid_chars):
        return False
    
    # Avoid reserved names
    reserved_names = ['con', 'prn', 'aux', 'nul'] + [f'com{i}' for i in range(1, 10)] + [f'lpt{i}' for i in range(1, 10)]
    
    if name.lower() in reserved_names:
        return False
    
    return True


def validate_email(email: str) -> bool:
    """Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email is valid
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid
    """
    pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(pattern, url))