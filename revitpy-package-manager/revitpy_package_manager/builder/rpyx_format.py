"""RevitPy package format (.rpyx) handler for desktop distribution.

The .rpyx format is optimized for desktop Revit add-ins with metadata,
dependencies, and installation instructions bundled in a single file.
"""

import json
import zipfile
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
import yaml
import toml
from datetime import datetime
import shutil

from ..registry.desktop_registry import PackageMetadata, RevitVersionCompatibility


@dataclass
class RPYXManifest:
    """RPYX package manifest structure."""
    
    # Package identity
    name: str
    version: str
    description: str
    summary: str
    
    # Author information
    author: str
    author_email: str
    license: str
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    
    # Desktop-specific metadata
    package_type: str = "addon"  # addon, library, template, tool
    revit_compatibility: Dict[str, Any] = None
    performance_impact: str = "low"
    requires_admin: bool = False
    
    # Entry points and installation
    entry_points: Dict[str, str] = None  # Command/ribbon entries
    install_hooks: Dict[str, str] = None  # Installation scripts
    uninstall_hooks: Dict[str, str] = None  # Cleanup scripts
    file_associations: List[str] = None  # File extensions
    
    # Dependencies
    dependencies: List[Dict[str, str]] = None
    revit_dependencies: List[str] = None  # Required Revit APIs
    python_version: str = ">=3.8"
    
    # Security and validation
    digital_signature: Optional[str] = None
    security_policy: Optional[str] = None
    
    # Metadata
    keywords: List[str] = None
    categories: List[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.entry_points is None:
            self.entry_points = {}
        if self.install_hooks is None:
            self.install_hooks = {}
        if self.uninstall_hooks is None:
            self.uninstall_hooks = {}
        if self.file_associations is None:
            self.file_associations = []
        if self.dependencies is None:
            self.dependencies = []
        if self.revit_dependencies is None:
            self.revit_dependencies = []
        if self.keywords is None:
            self.keywords = []
        if self.categories is None:
            self.categories = []
        if self.revit_compatibility is None:
            self.revit_compatibility = {}


class RPYXBuilder:
    """Builder for .rpyx package format."""
    
    def __init__(self, source_directory: Union[str, Path]):
        self.source_dir = Path(source_directory)
        self.manifest = None
        
        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_directory}")
    
    def load_manifest(self, manifest_file: Optional[Union[str, Path]] = None) -> RPYXManifest:
        """Load package manifest from various formats."""
        
        if manifest_file:
            manifest_path = Path(manifest_file)
        else:
            # Try common manifest file names
            for name in ["revitpy.toml", "pyproject.toml", "package.json", "manifest.json", "manifest.yaml"]:
                candidate = self.source_dir / name
                if candidate.exists():
                    manifest_path = candidate
                    break
            else:
                raise ValueError("No manifest file found in source directory")
        
        if not manifest_path.exists():
            raise ValueError(f"Manifest file not found: {manifest_path}")
        
        # Parse based on file extension
        if manifest_path.suffix.lower() == ".toml":
            data = toml.load(manifest_path)
            
            # Handle pyproject.toml format
            if "project" in data:
                project_data = data["project"]
                revitpy_data = data.get("tool", {}).get("revitpy", {})
                
                manifest_dict = {
                    "name": project_data["name"],
                    "version": project_data["version"],
                    "description": project_data["description"],
                    "summary": project_data.get("summary", project_data["description"]),
                    "author": project_data.get("authors", [{}])[0].get("name", "Unknown"),
                    "author_email": project_data.get("authors", [{}])[0].get("email", ""),
                    "license": project_data.get("license", {}).get("text", "Unknown"),
                    "homepage_url": project_data.get("urls", {}).get("Homepage"),
                    "repository_url": project_data.get("urls", {}).get("Repository"),
                    "documentation_url": project_data.get("urls", {}).get("Documentation"),
                    "keywords": project_data.get("keywords", []),
                    "dependencies": [{"name": dep} for dep in project_data.get("dependencies", [])],
                    **revitpy_data
                }
            else:
                # Direct TOML format
                manifest_dict = data
                
        elif manifest_path.suffix.lower() in [".json"]:
            with open(manifest_path) as f:
                manifest_dict = json.load(f)
                
        elif manifest_path.suffix.lower() in [".yaml", ".yml"]:
            with open(manifest_path) as f:
                manifest_dict = yaml.safe_load(f)
        
        else:
            raise ValueError(f"Unsupported manifest format: {manifest_path.suffix}")
        
        self.manifest = RPYXManifest(**manifest_dict)
        return self.manifest
    
    def validate_structure(self) -> List[str]:
        """Validate package structure and return list of issues."""
        issues = []
        
        if not self.manifest:
            issues.append("No manifest loaded")
            return issues
        
        # Required files/directories
        required_checks = [
            ("README.md", "README file", False),
            ("LICENSE", "License file", False),
        ]
        
        for path, description, is_dir in required_checks:
            full_path = self.source_dir / path
            
            if is_dir:
                if not full_path.is_dir():
                    issues.append(f"Missing required directory: {description} ({path})")
            else:
                if not full_path.is_file():
                    issues.append(f"Missing recommended file: {description} ({path})")
        
        # Validate Python files
        python_files = list(self.source_dir.rglob("*.py"))
        if not python_files:
            issues.append("No Python files found in package")
        
        # Check entry points
        for entry_point, script_path in self.manifest.entry_points.items():
            script_file = self.source_dir / script_path
            if not script_file.exists():
                issues.append(f"Entry point script not found: {script_path}")
        
        # Validate Revit compatibility
        if not self.manifest.revit_compatibility:
            issues.append("No Revit compatibility information specified")
        
        # Check for security-sensitive files
        sensitive_patterns = ["*.key", "*.pem", "*.p12", "*.pfx", "password*", "secret*"]
        for pattern in sensitive_patterns:
            matches = list(self.source_dir.rglob(pattern))
            if matches:
                issues.append(f"Potentially sensitive files found: {', '.join(str(m) for m in matches)}")
        
        return issues
    
    def build_package(self, output_path: Union[str, Path], include_dev: bool = False) -> Dict[str, Any]:
        """Build the .rpyx package."""
        
        if not self.manifest:
            raise ValueError("No manifest loaded. Call load_manifest() first.")
        
        output_path = Path(output_path)
        if output_path.suffix != ".rpyx":
            output_path = output_path.with_suffix(".rpyx")
        
        # Validation
        issues = self.validate_structure()
        critical_issues = [issue for issue in issues if "Missing required" in issue]
        if critical_issues:
            raise ValueError(f"Package validation failed: {'; '.join(critical_issues)}")
        
        build_info = {
            "package_name": self.manifest.name,
            "version": self.manifest.version,
            "build_timestamp": datetime.now().isoformat(),
            "validation_issues": issues,
            "files_included": [],
            "package_size": 0,
            "file_hash": ""
        }
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            
            # Write manifest as JSON
            manifest_json = json.dumps(asdict(self.manifest), indent=2, default=str)
            zf.writestr("rpyx-manifest.json", manifest_json)
            build_info["files_included"].append("rpyx-manifest.json")
            
            # Include source files
            for file_path in self.source_dir.rglob("*"):
                if file_path.is_file():
                    # Skip certain files
                    skip_patterns = [
                        ".git*", "__pycache__*", "*.pyc", "*.pyo", 
                        ".DS_Store", "Thumbs.db", "*.tmp", "*.log"
                    ]
                    
                    if include_dev:
                        skip_patterns = [".git*", "__pycache__*", "*.pyc", "*.pyo"]
                    
                    if any(file_path.match(pattern) for pattern in skip_patterns):
                        continue
                    
                    relative_path = file_path.relative_to(self.source_dir)
                    zf.write(file_path, str(relative_path))
                    build_info["files_included"].append(str(relative_path))
            
            # Add build metadata
            build_metadata = {
                "builder_version": "2.0.0",
                "build_info": build_info,
                "validation_issues": issues
            }
            zf.writestr("rpyx-build.json", json.dumps(build_metadata, indent=2, default=str))
        
        # Calculate package hash and size
        with open(output_path, "rb") as f:
            package_data = f.read()
            build_info["package_size"] = len(package_data)
            build_info["file_hash"] = hashlib.sha256(package_data).hexdigest()
        
        return build_info


class RPYXExtractor:
    """Extractor for .rpyx package format."""
    
    def __init__(self, package_path: Union[str, Path]):
        self.package_path = Path(package_path)
        
        if not self.package_path.exists():
            raise ValueError(f"Package file not found: {package_path}")
        
        if not self.package_path.suffix == ".rpyx":
            raise ValueError(f"Not a .rpyx file: {package_path}")
    
    def validate_package(self) -> Dict[str, Any]:
        """Validate package integrity and structure."""
        
        validation_result = {
            "valid": False,
            "issues": [],
            "manifest": None,
            "build_info": None,
            "file_hash": "",
            "file_size": 0
        }
        
        try:
            # Calculate file hash and size
            with open(self.package_path, "rb") as f:
                package_data = f.read()
                validation_result["file_hash"] = hashlib.sha256(package_data).hexdigest()
                validation_result["file_size"] = len(package_data)
            
            # Check if it's a valid ZIP file
            if not zipfile.is_zipfile(self.package_path):
                validation_result["issues"].append("Not a valid ZIP/RPYX file")
                return validation_result
            
            with zipfile.ZipFile(self.package_path, 'r') as zf:
                file_list = zf.namelist()
                
                # Check for required files
                if "rpyx-manifest.json" not in file_list:
                    validation_result["issues"].append("Missing rpyx-manifest.json")
                    return validation_result
                
                # Load and validate manifest
                try:
                    manifest_data = json.loads(zf.read("rpyx-manifest.json").decode())
                    validation_result["manifest"] = manifest_data
                    
                    # Basic manifest validation
                    required_fields = ["name", "version", "description", "author"]
                    for field in required_fields:
                        if field not in manifest_data:
                            validation_result["issues"].append(f"Missing required manifest field: {field}")
                
                except json.JSONDecodeError as e:
                    validation_result["issues"].append(f"Invalid manifest JSON: {e}")
                    return validation_result
                
                # Load build info if available
                if "rpyx-build.json" in file_list:
                    try:
                        build_data = json.loads(zf.read("rpyx-build.json").decode())
                        validation_result["build_info"] = build_data
                    except json.JSONDecodeError:
                        validation_result["issues"].append("Invalid build metadata")
                
                # Check for Python files
                python_files = [f for f in file_list if f.endswith('.py')]
                if not python_files:
                    validation_result["issues"].append("No Python files found in package")
                
                # Validate entry points if specified
                manifest = validation_result["manifest"]
                entry_points = manifest.get("entry_points", {})
                for entry_name, script_path in entry_points.items():
                    if script_path not in file_list:
                        validation_result["issues"].append(f"Entry point script not found: {script_path}")
            
            validation_result["valid"] = len([issue for issue in validation_result["issues"] 
                                            if "Missing required" in issue or "Entry point" in issue]) == 0
            
        except Exception as e:
            validation_result["issues"].append(f"Package validation error: {e}")
        
        return validation_result
    
    def extract_to(self, destination: Union[str, Path], overwrite: bool = False) -> Dict[str, Any]:
        """Extract package to destination directory."""
        
        destination = Path(destination)
        
        if destination.exists() and not overwrite:
            if any(destination.iterdir()):
                raise ValueError(f"Destination directory not empty: {destination}")
        
        # Create destination if it doesn't exist
        destination.mkdir(parents=True, exist_ok=True)
        
        extraction_info = {
            "extracted_files": [],
            "manifest": None,
            "extraction_timestamp": datetime.now().isoformat()
        }
        
        with zipfile.ZipFile(self.package_path, 'r') as zf:
            # Extract all files
            for file_info in zf.infolist():
                if file_info.is_dir():
                    continue
                
                # Skip metadata files from extraction
                if file_info.filename.startswith("rpyx-"):
                    continue
                
                # Extract file
                zf.extract(file_info, destination)
                extraction_info["extracted_files"].append(file_info.filename)
            
            # Load manifest for return info
            if "rpyx-manifest.json" in zf.namelist():
                manifest_data = json.loads(zf.read("rpyx-manifest.json").decode())
                extraction_info["manifest"] = manifest_data
        
        return extraction_info
    
    def get_manifest(self) -> Dict[str, Any]:
        """Get package manifest without extraction."""
        
        with zipfile.ZipFile(self.package_path, 'r') as zf:
            if "rpyx-manifest.json" not in zf.namelist():
                raise ValueError("No manifest found in package")
            
            return json.loads(zf.read("rpyx-manifest.json").decode())
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get comprehensive package metadata."""
        
        validation = self.validate_package()
        
        metadata = {
            "package_file": str(self.package_path),
            "file_size": validation["file_size"],
            "file_hash": validation["file_hash"],
            "valid": validation["valid"],
            "issues": validation["issues"],
            "manifest": validation["manifest"],
            "build_info": validation.get("build_info"),
        }
        
        # Add compatibility information
        if validation["manifest"]:
            manifest = validation["manifest"]
            metadata.update({
                "package_name": manifest.get("name"),
                "version": manifest.get("version"),
                "package_type": manifest.get("package_type", "addon"),
                "revit_compatibility": manifest.get("revit_compatibility", {}),
                "performance_impact": manifest.get("performance_impact", "unknown"),
                "requires_admin": manifest.get("requires_admin", False)
            })
        
        return metadata


class RPYXValidator:
    """Comprehensive validator for .rpyx packages."""
    
    @staticmethod
    def validate_compatibility(package_path: Union[str, Path], revit_version: str) -> Dict[str, Any]:
        """Validate package compatibility with specific Revit version."""
        
        extractor = RPYXExtractor(package_path)
        manifest = extractor.get_manifest()
        
        compatibility = manifest.get("revit_compatibility", {})
        result = {
            "compatible": True,
            "warnings": [],
            "errors": [],
            "tested": False
        }
        
        # Check version constraints
        min_version = compatibility.get("min_version")
        max_version = compatibility.get("max_version")
        tested_versions = compatibility.get("tested_versions", [])
        
        if min_version:
            try:
                import packaging.version
                if packaging.version.parse(revit_version) < packaging.version.parse(min_version):
                    result["compatible"] = False
                    result["errors"].append(f"Revit {revit_version} is below minimum required version {min_version}")
            except Exception:
                result["warnings"].append("Could not parse version constraints")
        
        if max_version:
            try:
                import packaging.version
                if packaging.version.parse(revit_version) > packaging.version.parse(max_version):
                    result["compatible"] = False
                    result["errors"].append(f"Revit {revit_version} is above maximum supported version {max_version}")
            except Exception:
                result["warnings"].append("Could not parse version constraints")
        
        # Check if version was tested
        if revit_version in tested_versions:
            result["tested"] = True
        elif tested_versions:
            result["warnings"].append(f"Package not tested with Revit {revit_version}. Tested versions: {', '.join(tested_versions)}")
        
        # Check known issues
        known_issues = compatibility.get("known_issues", [])
        for issue in known_issues:
            if revit_version in issue.get("affected_versions", []):
                result["warnings"].append(f"Known issue: {issue.get('description', 'Unspecified issue')}")
        
        return result
    
    @staticmethod
    def security_scan(package_path: Union[str, Path]) -> Dict[str, Any]:
        """Basic security scan of package contents."""
        
        security_result = {
            "risk_level": "low",
            "issues": [],
            "suspicious_files": [],
            "external_connections": []
        }
        
        try:
            extractor = RPYXExtractor(package_path)
            validation = extractor.validate_package()
            
            if not validation["valid"]:
                security_result["risk_level"] = "high"
                security_result["issues"].append("Package failed basic validation")
                return security_result
            
            with zipfile.ZipFile(package_path, 'r') as zf:
                for filename in zf.namelist():
                    if filename.endswith('.py'):
                        # Read Python file and scan for suspicious patterns
                        try:
                            content = zf.read(filename).decode('utf-8', errors='ignore')
                            
                            suspicious_patterns = [
                                ('subprocess', 'System command execution'),
                                ('os.system', 'System command execution'),
                                ('eval(', 'Dynamic code execution'),
                                ('exec(', 'Dynamic code execution'), 
                                ('__import__', 'Dynamic imports'),
                                ('urllib', 'Network requests'),
                                ('requests', 'Network requests'),
                                ('socket', 'Network communication'),
                                ('pickle.loads', 'Unsafe deserialization'),
                                ('marshal.loads', 'Unsafe deserialization')
                            ]
                            
                            for pattern, description in suspicious_patterns:
                                if pattern in content:
                                    security_result["suspicious_files"].append({
                                        "file": filename,
                                        "pattern": pattern,
                                        "description": description
                                    })
                                    
                                    if pattern in ['eval(', 'exec(', 'os.system']:
                                        security_result["risk_level"] = "high"
                                    elif security_result["risk_level"] == "low":
                                        security_result["risk_level"] = "medium"
                        
                        except Exception:
                            continue  # Skip files that can't be decoded
            
            # Summarize issues
            if security_result["suspicious_files"]:
                security_result["issues"] = [
                    f"{item['description']} in {item['file']}"
                    for item in security_result["suspicious_files"]
                ]
        
        except Exception as e:
            security_result["risk_level"] = "high"
            security_result["issues"].append(f"Security scan failed: {e}")
        
        return security_result


def create_sample_manifest() -> Dict[str, Any]:
    """Create a sample manifest for .rpyx packages."""
    
    return {
        "name": "sample-revit-addon",
        "version": "1.0.0",
        "description": "A sample RevitPy add-in for demonstration",
        "summary": "Sample add-in showing RevitPy capabilities",
        "author": "RevitPy Developer",
        "author_email": "developer@example.com",
        "license": "MIT",
        "homepage_url": "https://github.com/user/sample-revit-addon",
        "repository_url": "https://github.com/user/sample-revit-addon",
        "documentation_url": "https://docs.example.com/sample-addon",
        
        "package_type": "addon",
        "performance_impact": "low",
        "requires_admin": False,
        
        "revit_compatibility": {
            "min_version": "2022",
            "max_version": None,
            "tested_versions": ["2022", "2023", "2024"],
            "known_issues": []
        },
        
        "entry_points": {
            "main_command": "src/main.py",
            "ribbon_panel": "src/ribbon.py"
        },
        
        "dependencies": [
            {"name": "revitpy", "version": ">=2.0.0"}
        ],
        
        "revit_dependencies": [
            "Autodesk.Revit.DB",
            "Autodesk.Revit.UI"
        ],
        
        "keywords": ["revit", "bim", "automation"],
        "categories": ["utilities", "modeling"]
    }